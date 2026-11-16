"""Draw text art (the output of :func:`khatt.render`) as an image.

Braille dots, shade blocks and block mosaics are drawn as shapes, so they come
out crisp at any size and match the terminal art exactly. Any other character
(the ``ascii`` ramp) is drawn with a bundled font, centred in its cell and
condensed to fit when it is wider than the cell.

With a palette, every cell is painted in its own colour (see
:mod:`khatt.palette`), the same colours :func:`khatt.color_art` prints.

Cells are ``cell_width`` pixels wide and twice as tall (the terminal cell
aspect khatt renders for), so the art keeps its proportions.
"""

from __future__ import annotations

import unicodedata
from functools import lru_cache
from html import escape

from PIL import Image, ImageColor, ImageDraw, ImageFont

from khatt.fonts import font_path
from khatt.mapper import _BRAILLE_BITS, STYLES
from khatt.palette import RGB, Palette, cell_colors
from khatt.raster import CELL_ASPECT

_SHADES = {"░": 0.25, "▒": 0.5, "▓": 0.75, "█": 1.0}
_BLANKS = frozenset(" ⠀")
_SUPERSAMPLE = 4
"""Shapes are drawn this many times larger, then box-filtered down (antialiasing)."""

_GLYPH_FONT = "rubik"
"""Bundled font whose Latin glyphs draw the ``ascii`` ramp."""

_GLYPH_WEIGHT = 700
"""Bold: thin ramp characters read too faint once drawn into cells."""

_ARABIC_GLYPH_FONT = "cairo"
"""Bundled font that draws the Arabic letters of the ``letters`` style."""

_DOT_RADIUS = 0.36
"""Braille dot radius as a fraction of the dot spacing (dots never touch)."""

_MOSAICS: dict[str, tuple[int, int, int]] = {}
"""Block mosaic characters: ``(columns, rows, mask)`` of the sub-cells each one inks."""
for _style in STYLES.values():
    if _style.mosaic is not None:
        for _mask, _char in enumerate(_style.mosaic):
            if _char not in _MOSAICS and _char.strip():
                _MOSAICS[_char] = (*_style.cell, _mask)


def _blocks(char: str) -> list[tuple[float, float, float, float]]:
    """The inked rectangles of a mosaic character, as fractions of its cell."""
    columns, rows, mask = _MOSAICS[char]
    return [
        (x / columns, y / rows, (x + 1) / columns, (y + 1) / rows)
        for y in range(rows)
        for x in range(columns)
        if mask >> (y * columns + x) & 1
    ]


def art_to_image(
    art: str,
    *,
    fg: str | tuple[int, int, int] = "black",
    bg: str | tuple[int, int, int] | None = "white",
    cell_width: int = 12,
    padding: int | None = None,
    palette: Palette | None = None,
    direction: str = "rtl",
    bands: bool = False,
) -> Image.Image | None:
    """Draw text art as an image, one cell per character.

    Args:
        art: Text art as returned by :func:`khatt.render`, in any style.
        fg: Ink colour: a Pillow colour name, ``#rrggbb`` or an RGB tuple.
        bg: Background colour, or ``None`` for a transparent background.
        cell_width: Width of one character cell in pixels; cells are twice
            as tall.
        padding: Margin around the art in pixels (default: one cell width).
        palette: Colour the art with a palette instead of ``fg``: a palette
            name (see :func:`khatt.list_palettes`), colours separated by
            commas, or a list of colours.
        direction: Where the palette's gradient starts: ``"rtl"`` (the right
            edge, the default), ``"ltr"``, ``"down"`` or ``"up"``.
        bands: Solid bands of each palette colour instead of a blend.

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
            elif char in _MOSAICS:
                for left, top, right, bottom in _blocks(char):
                    draw.rectangle(
                        (
                            x0 + round(left * big_w),
                            y0 + round(top * big_h),
                            x0 + round(right * big_w) - 1,
                            y0 + round(bottom * big_h) - 1,
                        ),
                        fill=255,
                    )
            elif char in _SHADES:
                level = round(255 * _SHADES[char])
                draw.rectangle((x0, y0, x0 + big_w - 1, y0 + big_h - 1), fill=level)
            else:
                coverage.paste(_glyph_tile(char, big_w, big_h), (x0, y0))

    margin = cell_width if padding is None else padding
    mask = Image.new("L", (columns * cell_width + 2 * margin, rows * cell_height + 2 * margin), 0)
    mask.paste(coverage.reduce(_SUPERSAMPLE), (margin, margin))
    if palette is None:
        return paint(mask, fg, bg)
    ink = Image.new("RGB", mask.size, _rgb(fg))
    ink_draw = ImageDraw.Draw(ink)
    colors = cell_colors(art, palette, direction=direction, bands=bands)
    for row, line_colors in enumerate(colors):
        for col, color in enumerate(line_colors):
            if color is not None:
                x0, y0 = margin + col * cell_width, margin + row * cell_height
                ink_draw.rectangle((x0, y0, x0 + cell_width - 1, y0 + cell_height - 1), fill=color)
    return _paint_ink(mask, ink, bg)


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


def _paint_ink(
    mask: Image.Image, ink: Image.Image, bg: str | tuple[int, int, int] | None
) -> Image.Image:
    """Lay ``ink`` (an RGB image) over ``bg`` through the coverage ``mask``."""
    if bg is None:
        image = ink.convert("RGBA")
        image.putalpha(mask)
        return image
    image = Image.new("RGB", mask.size, _rgb(bg))
    image.paste(ink, (0, 0), mask)
    return image


def _hex(color: RGB) -> str:
    return "#{:02x}{:02x}{:02x}".format(*color)


def _art_colors(
    art: str,
    fg: str | tuple[int, int, int],
    palette: Palette | None,
    direction: str,
    bands: bool,
) -> list[list[RGB | None]]:
    """Every cell's colour: the palette's, or ``fg`` for every inked cell."""
    if palette is not None:
        return cell_colors(art, palette, direction=direction, bands=bands)
    return cell_colors(art, [_rgb(fg)])


def art_to_svg(
    art: str,
    *,
    fg: str | tuple[int, int, int] = "black",
    bg: str | tuple[int, int, int] | None = "white",
    cell_width: int = 12,
    padding: int | None = None,
    palette: Palette | None = None,
    direction: str = "rtl",
    bands: bool = False,
) -> str | None:
    """Draw text art as an SVG image, the vector twin of :func:`art_to_image`.

    Braille dots, shade blocks and block mosaics become circles and rectangles, so the
    art stays sharp at any zoom; other characters (the ``ascii`` ramp) are SVG text in
    a bold sans font. The arguments mean what they mean for :func:`art_to_image`.

    Returns:
        The SVG document, or ``None`` when the art contains nothing to draw.
    """
    if cell_width < 2:
        raise ValueError(f"cell_width must be at least 2, got {cell_width}")
    if padding is not None and padding < 0:
        raise ValueError(f"padding must not be negative, got {padding}")
    lines = art.split("\n")
    if all(char in _BLANKS for line in lines for char in line):
        return None
    colors = _art_colors(art, fg, palette, direction, bands)
    cell_height = round(cell_width / CELL_ASPECT)
    margin = cell_width if padding is None else padding
    width = max(len(line) for line in lines) * cell_width + 2 * margin
    height = len(lines) * cell_height + 2 * margin
    shapes: list[str] = []
    for row, line in enumerate(lines):
        for col, char in enumerate(line):
            color = colors[row][col]
            if color is None:
                continue
            fill = _hex(color)
            x0, y0 = margin + col * cell_width, margin + row * cell_height
            dots = ord(char) - 0x2800
            if 0 < dots <= 0xFF:
                step_x, step_y = cell_width / 2, cell_height / 4
                radius = _DOT_RADIUS * min(step_x, step_y)
                for (dot_x, dot_y), bit in _BRAILLE_BITS.items():
                    if dots & bit:
                        shapes.append(
                            f'<circle cx="{x0 + (dot_x + 0.5) * step_x:g}" '
                            f'cy="{y0 + (dot_y + 0.5) * step_y:g}" r="{radius:g}" fill="{fill}"/>'
                        )
            elif char in _MOSAICS:
                for left, top, right, bottom in _blocks(char):
                    shapes.append(
                        f'<rect x="{x0 + left * cell_width:g}" y="{y0 + top * cell_height:g}" '
                        f'width="{(right - left) * cell_width:g}" '
                        f'height="{(bottom - top) * cell_height:g}" fill="{fill}"/>'
                    )
            elif char in _SHADES:
                shapes.append(
                    f'<rect x="{x0}" y="{y0}" width="{cell_width}" height="{cell_height}" '
                    f'fill="{fill}" fill-opacity="{_SHADES[char]:g}"/>'
                )
            else:
                shapes.append(
                    f'<text x="{x0 + cell_width / 2:g}" y="{y0 + cell_height * 0.8:g}" '
                    f'fill="{fill}">{escape(char)}</text>'
                )
    background = "" if bg is None else f'<rect width="100%" height="100%" fill="{_hex(_rgb(bg))}"/>'
    font = (
        "<style>text{font-family:Rubik,Cairo,'Noto Naskh Arabic',Arial,sans-serif;"
        f"font-weight:{_GLYPH_WEIGHT};"
        f"font-size:{cell_height * 0.95:g}px;text-anchor:middle}}</style>"
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">{font}{background}{"".join(shapes)}</svg>\n'
    )


def art_to_html(
    art: str,
    *,
    fg: str | tuple[int, int, int] = "black",
    bg: str | tuple[int, int, int] | None = "white",
    palette: Palette | None = None,
    direction: str = "rtl",
    bands: bool = False,
) -> str:
    """Text art as an HTML ``<pre>`` block, each run of one colour in a ``<span>``.

    Unlike an image, the art stays text: it can be copied, and it is drawn by the
    browser's monospace font. The arguments mean what they mean for
    :func:`art_to_image`.
    """
    colors = _art_colors(art, fg, palette, direction, bands)
    out: list[str] = []
    for line, line_colors in zip(art.split("\n"), colors, strict=True):
        parts: list[str] = []
        run: list[str] = []
        current: RGB | None = None
        for char, color in zip(line, line_colors, strict=True):
            if color is not None and color != current:
                parts.append(_html_run(run, current))
                run = []
                current = color
            run.append(char)
        parts.append(_html_run(run, current))
        out.append("".join(parts))
    # bidi-override keeps every character in its cell: Arabic letters in the
    # ``letters`` style would otherwise be reordered by the browser.
    style = "line-height:1;font-family:monospace;direction:ltr;unicode-bidi:bidi-override"
    if bg is not None:
        style += f";background:{_hex(_rgb(bg))};padding:1em"
    return f'<pre style="{style}">' + "\n".join(out) + "</pre>\n"


def _html_run(chars: list[str], color: RGB | None) -> str:
    text = escape("".join(chars))
    if not text or color is None:
        return text
    return f'<span style="color:{_hex(color)}">{text}</span>'


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
    """Coverage of ``char`` in a ``width`` x ``height`` cell, condensed to fit.

    Arabic letters (the ``letters`` style writes them in isolated presentation
    forms) are drawn in an Arabic font from their plain letter, which alone is
    drawn isolated.
    """
    arabic = unicodedata.bidirectional(char) in ("R", "AL")
    if arabic:
        char = unicodedata.normalize("NFKC", char)
        font = ImageFont.truetype(str(font_path(_ARABIC_GLYPH_FONT)), size=round(height * 0.7))
        font.set_variation_by_axes([_GLYPH_WEIGHT, 0])  # Cairo: weight and slant axes
        baseline = round(height * 0.72)
    else:
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
