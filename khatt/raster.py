"""Rasterize shaped glyphs to grayscale bitmaps and character grids.

Glyphs are rendered individually by FreeType at the pen positions computed by
HarfBuzz, max-blended onto a high-resolution canvas (Arabic joins overlap, so
plain pasting would clip strokes), cropped to the ink extents, and finally
downsampled to the requested character grid.

Rendered glyph bitmaps are cached per (font, glyph ID): text repeats the same
few dozen glyphs, and reading a FreeType bitmap is the expensive step.

Determinism: hinting is disabled, pen positions are rounded identically
everywhere, the freetype-py wheel bundles its own libfreetype, and font files
are bundled — so output is byte-identical across platforms for a locked
dependency set (this is what makes the golden-file tests portable).
"""

from __future__ import annotations

import ctypes
import io
import threading
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import freetype
from PIL import Image, ImageChops

from khatt.shaping import ShapedGlyph, units_per_em

RENDER_PPEM = 256
"""Pixels per em of the high-resolution render stage."""

CELL_ASPECT = 0.5
"""Assumed terminal cell width:height ratio (cells are twice as tall as wide)."""

_LOAD_FLAGS = freetype.FT_LOAD_RENDER | freetype.FT_LOAD_NO_HINTING

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
def _glyph(path: str, gid: int) -> _Glyph:
    face = _face(path)
    with _FACE_LOCK:
        face.load_glyph(gid, _LOAD_FLAGS)
        slot = face.glyph
        if not (slot.bitmap.width and slot.bitmap.rows):
            return _Glyph(None, 0, 0)
        return _Glyph(_bitmap_to_image(slot.bitmap), slot.bitmap_left, slot.bitmap_top)


def _place(glyphs: Sequence[ShapedGlyph], path: str) -> list[_Placed]:
    """Position each inked glyph bitmap relative to the pen origin."""
    scale = RENDER_PPEM / units_per_em(path)
    placed: list[_Placed] = []
    pen_x = 0.0
    for glyph in glyphs:
        rendered = _glyph(path, glyph.gid)
        if rendered.image is not None:
            x = round(pen_x + glyph.x_offset * scale) + rendered.left
            y = -rendered.top - round(glyph.y_offset * scale)
            placed.append(_Placed(rendered.image, x, y))
        pen_x += glyph.x_advance * scale
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
    alignments = list(align) if align is not None else ["left"] * len(lines)
    if len(alignments) != len(lines):
        raise ValueError(f"got {len(alignments)} alignments for {len(lines)} lines")

    top = min(box[1] for box in inked)
    bottom = max(box[3] for box in inked)
    width = max(box[2] - box[0] for box in inked)

    canvases: list[Image.Image] = []
    for line, box, alignment in zip(placed, boxes, alignments, strict=True):
        canvas = Image.new("L", (width, bottom - top), 0)
        canvases.append(canvas)
        if box is None:
            continue
        slack = width - (box[2] - box[0])
        if alignment == "right":
            shift = slack
        elif alignment == "center":
            shift = slack // 2
        elif alignment == "left":
            shift = 0
        else:
            raise ValueError(f"unknown alignment {alignment!r}")
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
