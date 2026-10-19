"""Draw text art (the output of :func:`khatt.render`) as an image.

Braille dots and shade blocks are drawn as shapes, so they come out crisp at
any size and match the terminal art exactly. Any other character (the
``ascii`` ramp) is drawn with a bundled font, centred in its cell and
condensed to fit when it is wider than the cell.

Cells are ``cell_width`` pixels wide and twice as tall — the terminal cell
aspect khatt renders for — so the art keeps its proportions.
"""

from __future__ import annotations

from functools import lru_cache

from PIL import Image, ImageColor, ImageDraw, ImageFont

from khatt.fonts import font_path
from khatt.mapper import _BRAILLE_BITS
from khatt.raster import CELL_ASPECT

_SHADES = {"░": 0.25, "▒": 0.5, "▓": 0.75, "█": 1.0}
_BLANKS = frozenset(" ⠀")
_SUPERSAMPLE = 4
"""Shapes are drawn this many times larger, then box-filtered down (antialiasing)."""

_GLYPH_FONT = "rubik"
"""Bundled font whose Latin glyphs draw the ``ascii`` ramp."""

_GLYPH_WEIGHT = 700
"""Bold: thin ramp characters read too faint once drawn into cells."""

_DOT_RADIUS = 0.36
"""Braille dot radius as a fraction of the dot spacing (dots never touch)."""


def art_to_image(
    art: str,
    *,
    fg: str | tuple[int, int, int] = "black",
    bg: str | tuple[int, int, int] | None = "white",
    cell_width: int = 12,
    padding: int | None = None,
) -> Image.Image | None:
    """Draw text art as an image, one cell per character.

    Args:
        art: Text art as returned by :func:`khatt.render`, in any style.
        fg: Ink colour: a Pillow colour name, ``#rrggbb`` or an RGB tuple.
        bg: Background colour, or ``None`` for a transparent background.
        cell_width: Width of one character cell in pixels; cells are twice
            as tall.
        padding: Margin around the art in pixels (default: one cell width).

    Returns:
        An RGB image (RGBA when ``bg`` is ``None``), or ``None`` when the
        art contains nothing to draw.
    """
    if cell_width < 2:
        raise ValueError(f"cell_width must be at least 2, got {cell_width}")
    if padding is not None and padding < 0:
        raise ValueError(f"padding must not be negative, got {padding}")
    lines = art.split("\n")
    if all(char in _BLANKS for line in lines for char in line):
        return None

    cell_height = round(cell_width / CELL_ASPECT)
    columns, rows = max(len(line) for line in lines), len(lines)
    big_w, big_h = cell_width * _SUPERSAMPLE, cell_height * _SUPERSAMPLE

    coverage = Image.new("L", (columns * big_w, rows * big_h), 0)
    draw = ImageDraw.Draw(coverage)
    for row, line in enumerate(lines):
        for col, char in enumerate(line):
            if char in _BLANKS:
                continue
            x0, y0 = col * big_w, row * big_h
            dots = ord(char) - 0x2800
            if 0 < dots <= 0xFF:
                _draw_braille(draw, x0, y0, big_w, big_h, dots)
            elif char in _SHADES:
                level = round(255 * _SHADES[char])
                draw.rectangle((x0, y0, x0 + big_w - 1, y0 + big_h - 1), fill=level)
            else:
                coverage.paste(_glyph_tile(char, big_w, big_h), (x0, y0))

    margin = cell_width if padding is None else padding
    mask = Image.new("L", (columns * cell_width + 2 * margin, rows * cell_height + 2 * margin), 0)
    mask.paste(coverage.reduce(_SUPERSAMPLE), (margin, margin))
    return paint(mask, fg, bg)


def paint(
    mask: Image.Image,
    fg: str | tuple[int, int, int],
    bg: str | tuple[int, int, int] | None,
) -> Image.Image:
    """Colour an ink-coverage mask (``"L"``, 255 = ink): ``fg`` ink over ``bg``.

    ``bg=None`` gives an RGBA image whose alpha is the coverage.
    """
    ink = _rgb(fg)
    if bg is None:
        image = Image.new("RGBA", mask.size, (*ink, 0))
        image.putalpha(mask)
        return image
    image = Image.new("RGB", mask.size, _rgb(bg))
    image.paste(ink, (0, 0), mask)
    return image


def _rgb(color: str | tuple[int, int, int]) -> tuple[int, int, int]:
    if isinstance(color, str):
        red, green, blue = ImageColor.getrgb(color)[:3]
        return red, green, blue
    red, green, blue = color
    return red, green, blue


def _draw_braille(
    draw: ImageDraw.ImageDraw, x0: int, y0: int, width: int, height: int, dots: int
) -> None:
    step_x, step_y = width / 2, height / 4
    radius = _DOT_RADIUS * min(step_x, step_y)
    for (dot_x, dot_y), bit in _BRAILLE_BITS.items():
        if dots & bit:
            cx = x0 + (dot_x + 0.5) * step_x
            cy = y0 + (dot_y + 0.5) * step_y
            draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=255)


@lru_cache(maxsize=256)
def _glyph_tile(char: str, width: int, height: int) -> Image.Image:
    """Coverage of ``char`` in a ``width`` x ``height`` cell, condensed to fit."""
    font = ImageFont.truetype(str(font_path(_GLYPH_FONT)), size=round(height * 0.95))
    font.set_variation_by_axes([_GLYPH_WEIGHT])  # Rubik is a variable font (weight axis)
    baseline = round(height * 0.8)
    left, _, right, _ = font.getbbox(char, anchor="ls")
    ink_width = max(1, round(right - left))
    canvas = Image.new("L", (ink_width, height), 0)
    ImageDraw.Draw(canvas).text((-left, baseline), char, font=font, fill=255, anchor="ls")
    fit_width = round(width * 0.95)
    if ink_width > fit_width:
        canvas = canvas.resize((fit_width, height), Image.Resampling.LANCZOS)
    tile = Image.new("L", (width, height), 0)
    tile.paste(canvas, ((width - canvas.width) // 2, 0))
    return tile
