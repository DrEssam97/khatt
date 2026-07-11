"""Khatt (خَطّ) — render Arabic text as ASCII/Unicode-block art.

FIGlet-style per-character fonts cannot express Arabic contextual shaping,
mandatory ligatures or right-to-left layout, so khatt shapes text with
HarfBuzz, rasterizes it with a real Arabic font via FreeType, and maps pixel
coverage onto character ramps.

    >>> import khatt
    >>> print(khatt.render("مرحبا"))
"""

from __future__ import annotations

from khatt.fonts import available_fonts as list_fonts
from khatt.fonts import font_path
from khatt.mapper import available_styles as list_styles
from khatt.mapper import get_style, map_image
from khatt.raster import rasterize, to_grid
from khatt.shaping import UnsupportedCharacterWarning, shape

__version__ = "0.1.0"

__all__ = [
    "UnsupportedCharacterWarning",
    "__version__",
    "list_fonts",
    "list_styles",
    "render",
]


def render(
    text: str,
    font: str = "amiri",
    style: str = "blocks",
    width: int = 80,
    threshold: float | None = None,
    *,
    keep_tashkeel: bool = False,
) -> str:
    """Render Arabic (or mixed-direction) text as text art.

    Args:
        text: The text to render; Arabic is shaped with correct positional
            forms and ligatures, and mixed Arabic/Latin/digit strings come
            out in visual order.
        font: A bundled font name (see :func:`list_fonts`).
        style: Output character set (see :func:`list_styles`).
        width: Output width in terminal columns.
        threshold: Optional coverage cutoff in [0, 1]: coverage below it
            renders blank; for ``braille`` it is the per-dot cutoff.
        keep_tashkeel: Keep Arabic diacritics instead of stripping them
            (they are usually illegible at character-grid resolution).

    Returns:
        The rendered art, ``\\n``-separated, or an empty string when the
        input contains nothing renderable. Characters the font does not
        cover are skipped with an :class:`UnsupportedCharacterWarning`.
    """
    path = font_path(font)
    resolved_style = get_style(style)
    glyphs = shape(text, path, keep_tashkeel=keep_tashkeel)
    image = rasterize(glyphs, path)
    if image is None:
        return ""
    grid = to_grid(image, width, cell=resolved_style.cell)
    return map_image(grid, resolved_style.name, threshold)
