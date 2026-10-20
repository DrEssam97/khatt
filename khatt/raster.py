"""Rasterize shaped glyphs to grayscale bitmaps and character grids.

Glyphs are rendered individually by FreeType at the pen positions computed by
HarfBuzz, max-blended onto a high-resolution canvas (Arabic joins overlap, so
plain pasting would clip strokes), cropped to the ink extents, and finally
downsampled to the requested character grid.

Rendered glyph bitmaps are cached per (font, glyph ID, size, subpixel
offset): text repeats the same few dozen glyphs, and reading a FreeType bitmap
is the expensive step.

The text-art path renders at :data:`RENDER_PPEM` with whole-pixel pen
positions. Drawing onto images (:func:`compose_block`) renders at the target
size instead, with pen positions quantized to a quarter pixel: at small sizes,
whole-pixel rounding visibly misplaces joined Arabic letters.

Determinism: hinting is disabled, pen positions are rounded identically
everywhere, the freetype-py wheel bundles its own libfreetype, and font files
are bundled — so output is byte-identical across platforms for a locked
dependency set (this is what makes the golden-file tests portable).
"""

from __future__ import annotations

import ctypes
import io
import math
import threading
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import freetype
from PIL import Image, ImageChops

from khatt.shaping import ShapedGlyph, units_per_em, variations

RENDER_PPEM = 256
"""Pixels per em of the high-resolution render stage."""

CELL_ASPECT = 0.5
"""Assumed terminal cell width:height ratio (cells are twice as tall as wide)."""

SUBPIXEL_STEPS = 4
"""Horizontal pen positions per pixel when drawing onto images."""

_LOAD_FLAGS = freetype.FT_LOAD_RENDER | freetype.FT_LOAD_NO_HINTING
_IDENTITY = freetype.Matrix(0x10000, 0, 0, 0x10000)

# A FreeType face is not thread-safe, and the cached faces are shared (the
# Gradio app renders from worker threads).
_FACE_LOCK = threading.Lock()

Box = tuple[int, int, int, int]
"""``(x0, y0, x1, y1)`` in render pixels: pen origin on the baseline, y down."""


@dataclass(frozen=True)
class _Glyph:
    image: Image.Image | None
    """Coverage bitmap, or ``None`` for ink-less glyphs such as spaces."""
    left: int
    top: int


@dataclass(frozen=True)
class _Placed:
    image: Image.Image
    x: int
    y: int
    """Top edge relative to the baseline (negative above it)."""


@lru_cache(maxsize=8)
def _face(path: str) -> freetype.Face:
    # Load via a byte stream: freetype's own file handling can trip over
    # non-ASCII paths on Windows.
    face = freetype.Face(io.BytesIO(Path(path).read_bytes()))
    settings = variations(path)
    if settings:  # the same instance HarfBuzz shapes with
        axes = face.get_variation_info().axes
        face.set_var_design_coords([settings.get(axis.tag, axis.default) for axis in axes])
    face.set_pixel_sizes(0, RENDER_PPEM)
    return face


def _bitmap_bytes(bitmap: Any) -> bytes:
    pitch, rows = bitmap.pitch, bitmap.rows
    if pitch > 0:
        try:
            # freetype-py's ``bitmap.buffer`` builds a Python list of every
            # pixel; copying the raw buffer is orders of magnitude faster.
            return ctypes.string_at(bitmap._FT_Bitmap.buffer, pitch * rows)
        except (AttributeError, TypeError, ValueError):
            pass
    return bytes(bitmap.buffer)


def _bitmap_to_image(bitmap: Any) -> Image.Image:
    pitch, width, rows = bitmap.pitch, bitmap.width, bitmap.rows
    data = _bitmap_bytes(bitmap)
    if pitch != width:
        data = b"".join(data[r * pitch : r * pitch + width] for r in range(rows))
    return Image.frombytes("L", (width, rows), data)


@lru_cache(maxsize=4096)
def _glyph(path: str, gid: int, ppem: int = RENDER_PPEM, shift: int = 0) -> _Glyph:
    """Render one glyph at ``ppem``, its origin moved right by ``shift`` 1/64 px."""
    face = _face(path)
    with _FACE_LOCK:
        face.set_pixel_sizes(0, ppem)
        face.set_transform(_IDENTITY, freetype.Vector(shift, 0))
        face.load_glyph(gid, _LOAD_FLAGS)
        slot = face.glyph
        if not (slot.bitmap.width and slot.bitmap.rows):
            return _Glyph(None, 0, 0)
        return _Glyph(_bitmap_to_image(slot.bitmap), slot.bitmap_left, slot.bitmap_top)


@lru_cache(maxsize=4096)
def _outline_box(path: str, gid: int) -> tuple[int, int, int, int] | None:
    """Control box of a glyph outline in font units (y up), or ``None`` if it is empty."""
    face = _face(path)
    with _FACE_LOCK:
        face.set_transform(_IDENTITY, freetype.Vector(0, 0))
        face.load_glyph(gid, freetype.FT_LOAD_NO_SCALE | freetype.FT_LOAD_NO_HINTING)
        outline = face.glyph.outline
        if not outline.n_points:
            return None
        box = outline.get_cbox()
        return box.xMin, box.yMin, box.xMax, box.yMax


def _pen(
    glyphs: Sequence[ShapedGlyph], path: str, ppem: int, subpixel: bool
) -> list[tuple[ShapedGlyph, int, int, int]]:
    """Pen position of each glyph: ``(glyph, x, shift, y)``.

    ``x`` and ``y`` are whole pixels (``y`` is the baseline offset, down);
    ``shift`` is the remaining horizontal fraction in 1/64 px, always 0
    unless ``subpixel``.
    """
    scale = ppem / units_per_em(path)
    positions = []
    pen_x = 0.0
    for glyph in glyphs:
        exact = pen_x + glyph.x_offset * scale
        if subpixel:
            x, phase = divmod(math.floor(exact * SUBPIXEL_STEPS + 0.5), SUBPIXEL_STEPS)
            shift = phase * 64 // SUBPIXEL_STEPS
        else:
            x, shift = round(exact), 0
        positions.append((glyph, x, shift, -round(glyph.y_offset * scale)))
        pen_x += glyph.x_advance * scale
    return positions


def _place(
    glyphs: Sequence[ShapedGlyph], path: str, ppem: int = RENDER_PPEM, subpixel: bool = False
) -> list[_Placed]:
    """Position each inked glyph bitmap relative to the pen origin."""
    placed: list[_Placed] = []
    for glyph, x, shift, y in _pen(glyphs, path, ppem, subpixel):
        rendered = _glyph(path, glyph.gid, ppem, shift)
        if rendered.image is not None:
            placed.append(_Placed(rendered.image, x + rendered.left, y - rendered.top))
    return placed


def _bounds(placed: Sequence[_Placed]) -> Box | None:
    if not placed:
        return None
    return (
        min(p.x for p in placed),
        min(p.y for p in placed),
        max(p.x + p.image.size[0] for p in placed),
        max(p.y + p.image.size[1] for p in placed),
    )


def measure(glyphs: Sequence[ShapedGlyph], font_path: str | Path) -> Box | None:
    """Bounding box of a shaped line's glyph bitmaps, or ``None`` if it has no ink.

    The box is in render pixels (see :data:`Box`); it can be a little larger
    than the visible ink, never smaller.
    """
    return _bounds(_place(glyphs, str(font_path)))


def estimate(glyphs: Sequence[ShapedGlyph], font_path: str | Path, *, ppem: int) -> Box | None:
    """Bounding box of a shaped line as :func:`compose_block` draws it, without rendering.

    Computed from cached glyph outline boxes, so it is cheap at any size. It
    is never smaller than the drawn ink, and at most a pixel or so larger on
    each side. ``None`` means the line has no ink.
    """
    path = str(font_path)
    scale = ppem / units_per_em(path)
    margin = 1 / 64  # FreeType scales outlines in 26.6 fixed point
    boxes = []
    for glyph, x, shift, y in _pen(glyphs, path, ppem, subpixel=True):
        outline = _outline_box(path, glyph.gid)
        if outline is None:
            continue
        x_min, y_min, x_max, y_max = outline
        boxes.append(
            (
                x + math.floor(shift / 64 + x_min * scale - margin),
                y - math.ceil(y_max * scale + margin),
                x + math.ceil(shift / 64 + x_max * scale + margin),
                y - math.floor(y_min * scale - margin),
            )
        )
    if not boxes:
        return None
    return (
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        max(b[2] for b in boxes),
        max(b[3] for b in boxes),
    )


def _blend_max(canvas: Image.Image, glyph_image: Image.Image, x: int, y: int) -> None:
    """Blend a glyph bitmap onto the canvas keeping the maximum coverage."""
    canvas_w, canvas_h = canvas.size
    width, height = glyph_image.size
    x0, y0 = max(x, 0), max(y, 0)
    x1, y1 = min(x + width, canvas_w), min(y + height, canvas_h)
    if x0 >= x1 or y0 >= y1:
        return
    source = glyph_image.crop((x0 - x, y0 - y, x1 - x, y1 - y))
    region = canvas.crop((x0, y0, x1, y1))
    canvas.paste(ImageChops.lighter(region, source), (x0, y0))


def _alignments(align: Sequence[str] | None, count: int) -> list[str]:
    alignments = list(align) if align is not None else ["left"] * count
    if len(alignments) != count:
        raise ValueError(f"got {len(alignments)} alignments for {count} lines")
    return alignments


def _shift(alignment: str, slack: int) -> int:
    """Offset of a line ``slack`` pixels narrower than its layout width."""
    if alignment == "right":
        return slack
    if alignment == "center":
        return slack // 2
    if alignment == "left":
        return 0
    raise ValueError(f"unknown alignment {alignment!r}")


def compose_lines(
    lines: Sequence[Sequence[ShapedGlyph]],
    font_path: str | Path,
    *,
    align: Sequence[str] | None = None,
    tight: bool = False,
) -> list[Image.Image] | None:
    """Render shaped lines as separate images, one per line.

    All images have the same width, with each line aligned within it;
    ``align`` holds ``"left"``, ``"right"`` or ``"center"`` per line
    (default: all left). By default they also share one height, cropped to
    the union of all lines' ink with the baseline at the same row, so they
    stack into evenly spaced lines; lines without ink come back blank.
    ``tight=True`` instead crops each line to its own ink vertically (an
    ink-less line becomes one blank pixel row).

    Returns ``None`` when there is nothing to draw.
    """
    path = str(font_path)
    placed = [_place(line, path) for line in lines]
    boxes = [_bounds(line) for line in placed]
    inked = [box for box in boxes if box is not None]
    if not inked:
        return None
    alignments = _alignments(align, len(lines))

    top = min(box[1] for box in inked)
    bottom = max(box[3] for box in inked)
    width = max(box[2] - box[0] for box in inked)

    canvases: list[Image.Image] = []
    for line, box, alignment in zip(placed, boxes, alignments, strict=True):
        canvas = Image.new("L", (width, bottom - top), 0)
        canvases.append(canvas)
        if box is None:
            continue
        shift = _shift(alignment, width - (box[2] - box[0]))
        for glyph in line:
            _blend_max(canvas, glyph.image, glyph.x + shift - box[0], glyph.y - top)

    # Glyph bitmap boxes can exceed the visible ink; crop to the real ink so
    # a single line matches a plain ink crop.
    ink = [canvas.getbbox() for canvas in canvases]
    inked_boxes = [bbox for bbox in ink if bbox is not None]
    if not inked_boxes:
        return None
    left = min(b[0] for b in inked_boxes)
    right = max(b[2] for b in inked_boxes)
    if not tight:
        top = min(b[1] for b in inked_boxes)
        bottom = max(b[3] for b in inked_boxes)
        return [canvas.crop((left, top, right, bottom)) for canvas in canvases]
    return [
        canvas.crop((left, bbox[1], right, bbox[3]))
        if bbox is not None
        else Image.new("L", (right - left, 1), 0)
        for canvas, bbox in zip(canvases, ink, strict=True)
    ]


def compose(
    lines: Sequence[Sequence[ShapedGlyph]],
    font_path: str | Path,
    *,
    align: Sequence[str] | None = None,
    line_gap: int = 0,
) -> Image.Image | None:
    """Render shaped lines stacked top to bottom on one image.

    Lines are laid out as in :func:`compose_lines` and stacked ``line_gap``
    pixels apart; the result is cropped to the ink extents, and empty lines
    between inked ones keep their slot.

    Returns ``None`` when there is nothing to draw.
    """
    bands = compose_lines(lines, font_path, align=align)
    if bands is None:
        return None
    width, height = bands[0].size
    pitch = height + line_gap
    canvas = Image.new("L", (width, pitch * len(bands) - line_gap), 0)
    for index, band in enumerate(bands):
        canvas.paste(band, (0, index * pitch))
    bbox = canvas.getbbox()
    return None if bbox is None else canvas.crop(bbox)


@dataclass(frozen=True)
class Block:
    """Lines drawn by :func:`compose_block`, as a coverage mask.

    Positions are in pixels relative to the first line's baseline (y down)
    and the left edge of the layout width.
    """

    mask: Image.Image
    """Coverage (mode ``"L"``), cropped to the ink."""
    left: int
    top: int
    """Position of the mask's top-left corner."""
    width: int
    """The layout width the lines were aligned in."""


def compose_block(
    lines: Sequence[Sequence[ShapedGlyph]],
    font_path: str | Path,
    *,
    ppem: int,
    pitch: float,
    align: Sequence[str] | None = None,
    width: int | None = None,
) -> Block | None:
    """Draw shaped lines at ``ppem`` pixels per em, baselines ``pitch`` pixels apart.

    Each line is aligned (``"left"``, ``"right"`` or ``"center"`` per line,
    default all left) within ``width`` pixels, or within the widest line if
    that is wider or ``width`` is ``None``. Unlike :func:`compose`, glyphs
    are rendered at the target size with quarter-pixel pen positions, and
    empty lines keep their slot.

    Returns ``None`` when there is nothing to draw.
    """
    path = str(font_path)
    alignments = _alignments(align, len(lines))
    placed = [_place(line, path, ppem, subpixel=True) for line in lines]
    boxes = [_bounds(line) for line in placed]
    inked = [box for box in boxes if box is not None]
    if not inked:
        return None
    layout_width = max(box[2] - box[0] for box in inked)
    if width is not None:
        layout_width = max(layout_width, width)

    glyphs: list[_Placed] = []
    for index, (line, box, alignment) in enumerate(zip(placed, boxes, alignments, strict=True)):
        if box is None:
            continue
        dx = _shift(alignment, layout_width - (box[2] - box[0])) - box[0]
        dy = round(index * pitch)
        glyphs.extend(_Placed(glyph.image, glyph.x + dx, glyph.y + dy) for glyph in line)

    x0, y0, x1, y1 = _bounds(glyphs) or (0, 0, 0, 0)
    canvas = Image.new("L", (x1 - x0, y1 - y0), 0)
    for glyph in glyphs:
        _blend_max(canvas, glyph.image, glyph.x - x0, glyph.y - y0)
    ink = canvas.getbbox()
    if ink is None:
        return None
    return Block(canvas.crop(ink), x0 + ink[0], y0 + ink[1], layout_width)


def rasterize(glyphs: Sequence[ShapedGlyph], font_path: str | Path) -> Image.Image | None:
    """Render one shaped line to a grayscale image cropped to the ink extents.

    Returns ``None`` when there is nothing to draw (no glyphs, or only
    ink-less glyphs such as spaces).
    """
    return compose([glyphs], font_path)


def to_grid(
    image: Image.Image,
    columns: int,
    cell: tuple[int, int] = (1, 1),
    cell_aspect: float = CELL_ASPECT,
    rows: int | None = None,
) -> Image.Image:
    """Downsample an ink image to a character grid of ``columns`` cells.

    Unless ``rows`` is given, the row count preserves the ink aspect ratio
    corrected by ``cell_aspect``; the returned image measures
    ``columns * cell[0]`` by ``rows * cell[1]`` pixels, one pixel per ramp
    character or braille dot.
    """
    if columns < 1:
        raise ValueError(f"columns must be at least 1, got {columns}")
    if rows is not None and rows < 1:
        raise ValueError(f"rows must be at least 1, got {rows}")
    width, height = image.size
    if rows is None:
        rows = max(1, round((height / width) * columns * cell_aspect))
    dx, dy = cell
    return image.resize((columns * dx, rows * dy), Image.Resampling.LANCZOS)
