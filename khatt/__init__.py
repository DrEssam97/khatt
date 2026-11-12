"""Khatt (خَطّ): render Arabic text as ASCII/Unicode-block art and onto images.

FIGlet-style per-character fonts cannot express Arabic contextual shaping,
mandatory ligatures or right-to-left layout, so khatt shapes text with
HarfBuzz, rasterizes it with a real Arabic font through HarfBuzz too, and maps pixel
coverage onto character ramps, or composites it onto Pillow images.

    >>> import khatt
    >>> print(khatt.render("مرحبا"))
    >>> khatt.draw_text(image, (20, 20), "مرحبا")
"""

from __future__ import annotations

from collections.abc import Sequence

from PIL import Image, ImageOps

from khatt.art_image import art_to_image
from khatt.calligram import available_shapes as list_shapes
from khatt.calligram import calligram
from khatt.caption import caption_image
from khatt.curves import Arc, Wave
from khatt.curves import available_curves as list_curves
from khatt.doctor import doctor, find_reshaping
from khatt.draw import Span, TextOverflowWarning, draw_text, overlay, text_bbox, word_art
from khatt.effects import Effect, Extrude, Glow, Gradient, Shadow, get_effect
from khatt.effects import available_effects as list_effects
from khatt.fonts import Font, font_path, font_paths
from khatt.fonts import available_fonts as list_fonts
from khatt.layout import DEFAULT_SIZE, paragraphs, render_grids, render_ink
from khatt.mapper import available_styles as list_styles
from khatt.mapper import get_style, map_image
from khatt.rescue import ReshapedTextWarning, is_reshaped, unreshape
from khatt.shaping import UnsupportedCharacterWarning, base_direction, strip_tashkeel
from khatt.shaping import missing_characters as _missing_in_line
from khatt.svg import render_svg
from khatt.words import (
    CaptionStep,
    Word,
    caption_steps,
    group_words,
    words_from_quran,
    words_from_whisper,
)
from khatt.zakhrafa import available_zakhrafa as list_zakhrafa
from khatt.zakhrafa import zakhrafa

__version__ = "0.8.0"

__all__ = [
    "DEFAULT_SIZE",
    "Arc",
    "CaptionStep",
    "Effect",
    "Extrude",
    "Glow",
    "Gradient",
    "ReshapedTextWarning",
    "Shadow",
    "Span",
    "TextOverflowWarning",
    "UnsupportedCharacterWarning",
    "Wave",
    "Word",
    "__version__",
    "art_to_image",
    "calligram",
    "caption_image",
    "caption_steps",
    "doctor",
    "draw_text",
    "find_reshaping",
    "get_effect",
    "group_words",
    "is_reshaped",
    "list_curves",
    "list_effects",
    "list_fonts",
    "list_shapes",
    "list_styles",
    "list_zakhrafa",
    "missing_characters",
    "overlay",
    "render",
    "render_image",
    "render_svg",
    "text_bbox",
    "unreshape",
    "word_art",
    "words_from_quran",
    "words_from_whisper",
    "zakhrafa",
]


def render(
    text: str,
    font: Font = "amiri",
    style: str = "blocks",
    width: int | None = 80,
    threshold: float | None = None,
    *,
    size: int | None = DEFAULT_SIZE,
    keep_tashkeel: bool = False,
    fallback_fonts: Font | Sequence[Font] = (),
) -> str:
    """Render Arabic (or mixed-direction) text as text art.

    Args:
        text: The text to render; Arabic is shaped with correct positional
            forms and ligatures, and mixed Arabic/Latin/digit strings come
            out in visual order. Line breaks start new lines; right-to-left
            paragraphs are right-aligned.
        font: A bundled font name (see :func:`list_fonts`) or the path
            to a .ttf/.otf font file.
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
        fallback_fonts: Fonts tried in order (bundled names or file paths)
            for characters ``font`` has no glyph for.

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
        fallbacks=font_paths(fallback_fonts),
    )
    # One blank line between text lines keeps them apart in any font.
    return "\n\n".join(map_image(grid, resolved_style.name, threshold) for grid in grids)


def render_image(
    text: str,
    font: Font = "amiri",
    *,
    keep_tashkeel: bool = True,
    fallback_fonts: Font | Sequence[Font] = (),
) -> Image.Image | None:
    """Render text as a high-resolution grayscale image, black on white.

    Uses the same shaping and line layout as :func:`render` (line breaks,
    right-aligned right-to-left paragraphs) at 256 pixels per em, without
    wrapping. The image is cropped to the ink.

    Args:
        text: The text to render.
        font: A bundled font name (see :func:`list_fonts`) or the path
            to a .ttf/.otf font file.
        keep_tashkeel: Keep Arabic diacritics (the default, unlike
            :func:`render`: images have the resolution to show them).
            Pass ``False`` to strip them.
        fallback_fonts: Fonts for characters ``font`` has no glyph for, as
            in :func:`render`.

    Returns:
        A Pillow image in mode ``"L"``, or ``None`` when the input contains
        nothing renderable. Unsupported characters are skipped with an
        :class:`UnsupportedCharacterWarning`.
    """
    image = render_ink(
        text, font_path(font), keep_tashkeel=keep_tashkeel, fallbacks=font_paths(fallback_fonts)
    )
    return None if image is None else ImageOps.invert(image)


def missing_characters(
    text: str,
    font: Font = "amiri",
    *,
    keep_tashkeel: bool = True,
    fallback_fonts: Font | Sequence[Font] = (),
) -> list[str]:
    """The characters of ``text`` that ``font`` has no glyph for.

    Check before drawing, e.g. to fall back to another font: khatt skips
    exactly these characters, with an :class:`UnsupportedCharacterWarning`.
    Characters the font can still show, such as an accented letter it has
    in decomposed form, and invisible ones (ZWJ, ZWNJ, bidi marks) are not
    missing, nor are line breaks and tabs.

    Args:
        text: The text, as typed.
        font: A bundled font name (see :func:`list_fonts`) or the path to a
            .ttf/.otf font file.
        keep_tashkeel: Count Arabic diacritics, as drawing on images does by
            default. Pass ``False`` to match ``keep_tashkeel=False`` and
            :func:`render`, which strip them.
        fallback_fonts: Fonts that draw what ``font`` cannot, as in
            :func:`draw_text`: then only the characters none of them has
            are missing.

    Returns:
        Each missing character once, in the order they first appear; an
        empty list when the font covers the whole text.
    """
    path, fallbacks = font_path(font), font_paths(fallback_fonts)
    if not keep_tashkeel:
        text = strip_tashkeel(text)
    missing = set().union(
        *(
            _missing_in_line(line, path, direction=base_direction(line), fallback_fonts=fallbacks)
            for line in paragraphs(text)
        )
    )
    return [ch for ch in dict.fromkeys(text) if ch in missing]
