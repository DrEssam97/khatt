"""Rasterize shaped glyphs to grayscale bitmaps and character grids.

Glyphs are rendered individually by FreeType at the pen positions computed by
HarfBuzz, max-blended onto a high-resolution canvas (Arabic joins overlap, so
plain pasting would clip strokes), cropped to the ink extents, and finally
downsampled to the requested character grid.

Determinism: hinting is disabled, pen positions are rounded identically
everywhere, the freetype-py wheel bundles its own libfreetype, and font files
are bundled — so output is byte-identical across platforms for a locked
dependency set (this is what makes the golden-file tests portable).
"""

from __future__ import annotations

import io
from functools import lru_cache
from pathlib import Path

import freetype
from PIL import Image, ImageChops

from khatt.shaping import ShapedGlyph, units_per_em

RENDER_PPEM = 256
"""Pixels per em of the high-resolution render stage."""

CELL_ASPECT = 0.5
"""Assumed terminal cell width:height ratio (cells are twice as tall as wide)."""

_LOAD_FLAGS = freetype.FT_LOAD_RENDER | freetype.FT_LOAD_NO_HINTING


@lru_cache(maxsize=8)
def _face(path: str) -> freetype.Face:
    # Load via a byte stream: freetype's own file handling can trip over
    # non-ASCII paths on Windows.
    face = freetype.Face(io.BytesIO(Path(path).read_bytes()))
    face.set_pixel_sizes(0, RENDER_PPEM)
    return face


def _bitmap_to_image(bitmap: freetype.Bitmap) -> Image.Image:
    pitch, width, rows = bitmap.pitch, bitmap.width, bitmap.rows
    data = bytes(bitmap.buffer)
    if pitch != width:
        data = b"".join(data[r * pitch : r * pitch + width] for r in range(rows))
    return Image.frombytes("L", (width, rows), data)


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


def rasterize(glyphs: list[ShapedGlyph], font_path: str | Path) -> Image.Image | None:
    """Render shaped glyphs to a grayscale image cropped to the ink extents.

    Returns ``None`` when there is nothing to draw (no glyphs, or only
    ink-less glyphs such as spaces).
    """
    if not glyphs:
        return None

    path = str(font_path)
    face = _face(path)
    scale = RENDER_PPEM / units_per_em(path)

    ascender = face.size.ascender >> 6
    descender = abs(face.size.descender >> 6)
    total_advance = sum(g.x_advance for g in glyphs) * scale
    # Generous margin: swashes and mark stacks can extend well past both the
    # advance width and the nominal ascender/descender.
    margin = RENDER_PPEM
    canvas = Image.new(
        "L",
        (int(total_advance) + 2 * margin, ascender + descender + 2 * margin),
        0,
    )
    baseline = margin + ascender

    pen_x = float(margin)
    for glyph in glyphs:
        face.load_glyph(glyph.gid, _LOAD_FLAGS)
        slot = face.glyph
        if slot.bitmap.width and slot.bitmap.rows:
            x = round(pen_x + glyph.x_offset * scale) + slot.bitmap_left
            y = baseline - slot.bitmap_top - round(glyph.y_offset * scale)
            _blend_max(canvas, _bitmap_to_image(slot.bitmap), x, y)
        pen_x += glyph.x_advance * scale

    bbox = canvas.getbbox()
    if bbox is None:
        return None
    return canvas.crop(bbox)


def to_grid(
    image: Image.Image,
    columns: int,
    cell: tuple[int, int] = (1, 1),
    cell_aspect: float = CELL_ASPECT,
) -> Image.Image:
    """Downsample an ink image to a character grid of ``columns`` cells.

    The row count preserves the ink aspect ratio corrected by ``cell_aspect``;
    the returned image measures ``columns * cell[0]`` by ``rows * cell[1]``
    pixels, one pixel per ramp character or braille dot.
    """
    if columns < 1:
        raise ValueError(f"columns must be at least 1, got {columns}")
    width, height = image.size
    rows = max(1, round((height / width) * columns * cell_aspect))
    dx, dy = cell
    return image.resize((columns * dx, rows * dy), Image.Resampling.LANCZOS)
