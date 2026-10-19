"""Khatt (خَطّ) — render Arabic text as ASCII/Unicode-block art and onto images.

FIGlet-style per-character fonts cannot express Arabic contextual shaping,
mandatory ligatures or right-to-left layout, so khatt shapes text with
HarfBuzz, rasterizes it with a real Arabic font via FreeType, and maps pixel
coverage onto character ramps, or composites it onto Pillow images.

    >>> import khatt
    >>> print(khatt.render("مرحبا"))
    >>> khatt.draw_text(image, (20, 20), "مرحبا")
"""

from __future__ import annotations

from PIL import Image, ImageOps

from khatt.art_image import art_to_image
from khatt.doctor import doctor
from khatt.draw import TextOverflowWarning, draw_text, overlay
from khatt.fonts import available_fonts as list_fonts
from khatt.fonts import font_path
from khatt.layout import DEFAULT_SIZE, render_grids, render_ink
from khatt.mapper import available_styles as list_styles
from khatt.mapper import get_style, map_image
from khatt.shaping import UnsupportedCharacterWarning

__version__ = "0.2.0"

__all__ = [
    "DEFAULT_SIZE",
    "TextOverflowWarning",
    "UnsupportedCharacterWarning",
    "__version__",
    "art_to_image",
    "doctor",
    "draw_text",
    "list_fonts",
    "list_styles",
    "overlay",
    "render",
    "render_image",
]


def render(
    text: str,
    font: str = "amiri",
    style: str = "blocks",
    width: int | None = 80,
    threshold: float | None = None,
    *,
    size: int | None = DEFAULT_SIZE,
    keep_tashkeel: bool = False,
) -> str:
    """Render Arabic (or mixed-direction) text as text art.

    Args:
        text: The text to render; Arabic is shaped with correct positional
            forms and ligatures, and mixed Arabic/Latin/digit strings come
            out in visual order. Line breaks start new lines; right-to-left
            paragraphs are right-aligned.
        font: A bundled font name (see :func:`list_fonts`).
        style: Output character set (see :func:`list_styles`).
        width: Maximum output width in terminal columns; longer lines wrap
            at spaces. ``None`` means no limit (no wrapping).
        threshold: Optional coverage cutoff in [0, 1]: coverage below it
            renders blank; for ``braille`` it is the per-dot cutoff.
        size: Font size in character rows per em, the same for every
            style. If a single word is wider than ``width``, the whole text
            shrinks so it fits. ``None`` scales the widest line to fill
            exactly ``width`` columns, without wrapping.
        keep_tashkeel: Keep Arabic diacritics instead of stripping them
            (they are usually illegible at character-grid resolution).

    Returns:
        The rendered art, ``\\n``-separated, or an empty string when the
        input contains nothing renderable. Characters the font does not
        cover are skipped with an :class:`UnsupportedCharacterWarning`.
    """
    if width is not None and width < 1:
        raise ValueError(f"width must be at least 1, got {width}")
    if size is not None and size < 1:
        raise ValueError(f"size must be at least 1, got {size}")
    if size is None and width is None:
        raise ValueError("size=None scales the text to fill the width, so it needs a width")
    if threshold is not None and not 0.0 <= threshold <= 1.0:
        raise ValueError(f"threshold must be within [0, 1], got {threshold}")
    path = font_path(font)
    resolved_style = get_style(style)
    grids = render_grids(
        text,
        path,
        resolved_style.cell,
        width=width,
        size=size,
        keep_tashkeel=keep_tashkeel,
    )
    # One blank line between text lines keeps them apart in any font.
    return "\n\n".join(map_image(grid, resolved_style.name, threshold) for grid in grids)


def render_image(
    text: str, font: str = "amiri", *, keep_tashkeel: bool = True
) -> Image.Image | None:
    """Render text as a high-resolution grayscale image, black on white.

    Uses the same shaping and line layout as :func:`render` (line breaks,
    right-aligned right-to-left paragraphs) at 256 pixels per em, without
    wrapping. The image is cropped to the ink.

    Args:
        text: The text to render.
        font: A bundled font name (see :func:`list_fonts`).
        keep_tashkeel: Keep Arabic diacritics (the default, unlike
            :func:`render`: images have the resolution to show them).
            Pass ``False`` to strip them.

    Returns:
        A Pillow image in mode ``"L"``, or ``None`` when the input contains
        nothing renderable. Unsupported characters are skipped with an
        :class:`UnsupportedCharacterWarning`.
    """
    image = render_ink(text, font_path(font), keep_tashkeel=keep_tashkeel)
    return None if image is None else ImageOps.invert(image)
