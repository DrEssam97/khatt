"""Pillow's text calls, with Arabic drawn by khatt.

:func:`text`, :func:`textbbox` and :func:`textlength` take the same arguments as
``ImageDraw.text``, ``textbbox`` and ``textlength`` (with the ``ImageDraw`` first).
Text with Arabic letters is drawn by khatt, so it comes out the same whether or not
Pillow has Raqm. Text that was already shaped with arabic_reshaper and
``get_display`` is turned back first (see :func:`khatt.unreshape`), so old code that
pre-shapes keeps working when Pillow starts shaping too. Any other text goes to Pillow
untouched.

For code you can't change, such as a library that draws with ``ImageDraw.text``,
:func:`routing` sends its calls through khatt for as long as a ``with`` block lasts::

    import khatt

    with khatt.pillow.routing():
        image = some_library.render_card(name="محمد")
"""

from __future__ import annotations

import contextlib
import threading
import unicodedata
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

from PIL import Image, ImageColor, ImageDraw, ImageFont

from khatt.draw import draw_text, text_bbox
from khatt.fonts import font_path
from khatt.rescue import is_reshaped, unreshape

FALLBACK_FONT = "noto-naskh"
"""Bundled font for Arabic letters the given font has no glyphs for."""

_DEFAULT_SIZE = 10
"""Pillow's default font size."""

_ORIGINALS: dict[str, Callable[..., Any]] = {
    "text": ImageDraw.ImageDraw.text,
    "multiline_text": ImageDraw.ImageDraw.multiline_text,
    "textbbox": ImageDraw.ImageDraw.textbbox,
    "multiline_textbbox": ImageDraw.ImageDraw.multiline_textbbox,
    "textlength": ImageDraw.ImageDraw.textlength,
    "getbbox": ImageFont.FreeTypeFont.getbbox,
    "getlength": ImageFont.FreeTypeFont.getlength,
}
_routing = threading.RLock()


def _arabic(text: object) -> str | None:
    """``text`` ready for khatt if it holds Arabic letters, else ``None``."""
    if not isinstance(text, str):
        return None
    if is_reshaped(text):
        return unreshape(text)
    if any(unicodedata.bidirectional(char) == "AL" for char in text):
        return text
    return None


def _font_options(
    font: ImageFont.ImageFont | ImageFont.FreeTypeFont | ImageFont.TransposedFont | None,
    font_size: float | None,
) -> dict[str, Any]:
    """khatt's ``font``, ``size_px`` and ``fallback_fonts`` for a Pillow font."""
    path = getattr(font, "path", None)
    size = getattr(font, "size", None) or font_size or _DEFAULT_SIZE
    fallback = font_path(FALLBACK_FONT)
    if isinstance(path, str) and Path(path).is_file():
        return {"font": path, "size_px": round(size), "fallback_fonts": [fallback]}
    # Pillow's built-in bitmap font, or a font from bytes: no file to shape with.
    return {"font": FALLBACK_FONT, "size_px": round(size)}


def _ink(draw: ImageDraw.ImageDraw, fill: Any) -> tuple[int, int, int, int]:
    """Pillow's ``fill`` as an RGBA colour (white when not given, as in Pillow)."""
    if fill is None:
        return 255, 255, 255, 255
    if isinstance(fill, str):
        return ImageColor.getcolor(fill, "RGBA")  # type: ignore[return-value]
    if isinstance(fill, int | float):
        level = round(fill)
        return level, level, level, 255
    channels = tuple(round(value) for value in fill)
    if len(channels) == 2:  # LA
        return channels[0], channels[0], channels[0], channels[1]
    red, green, blue, alpha = (*channels, 255)[:4]
    return red, green, blue, alpha


def text(
    draw: ImageDraw.ImageDraw,
    xy: tuple[float, float],
    text: str,
    fill: Any = None,
    font: Any = None,
    anchor: str | None = None,
    spacing: float = 4,
    align: str = "left",
    direction: str | None = None,
    features: list[str] | None = None,
    language: str | None = None,
    stroke_width: float = 0,
    stroke_fill: Any = None,
    embedded_color: bool = False,
    *,
    font_size: float | None = None,
) -> None:
    """``draw.text(xy, text, ...)``, with Arabic drawn by khatt.

    Takes ``ImageDraw.text``'s arguments. ``direction``, ``features``, ``language``
    and ``embedded_color`` only apply to text Pillow draws: khatt lays Arabic out
    itself. Arabic is drawn on RGB, RGBA, L and LA images; on other modes Pillow
    draws everything.
    """
    arabic = _arabic(text)
    image = draw._image  # the image the ImageDraw draws on
    if arabic is None or image.mode not in ("RGB", "RGBA", "L", "LA"):
        _ORIGINALS["text"](
            draw,
            xy,
            text,
            fill,
            font,
            anchor,
            spacing,
            align,
            direction,
            features,
            language,
            stroke_width,
            stroke_fill,
            embedded_color,
            font_size=font_size,
        )
        return
    options = _font_options(font, font_size)
    layout = {
        "anchor": anchor or "la",
        "spacing": spacing,
        "align": align,
        "stroke_width": stroke_width,
        **options,
    }
    color = _ink(draw, fill)
    outline = None if stroke_fill is None else _ink(draw, stroke_fill)
    if image.mode in ("RGB", "RGBA"):
        draw_text(image, xy, arabic, fill=color, stroke_fill=outline, **layout)
        return
    # Grayscale: draw onto a tile in colour, then paste its lightness through its alpha.
    left, top, right, bottom = text_bbox(arabic, xy=xy, **layout)
    if right <= left or bottom <= top:
        return
    tile = Image.new("RGBA", (right - left, bottom - top), (0, 0, 0, 0))
    draw_text(
        tile,
        (xy[0] - left, xy[1] - top),
        arabic,
        fill=color,
        stroke_fill=outline,
        **layout,
    )
    gray = tile.convert("LA")
    image.paste(gray if image.mode == "LA" else gray.getchannel("L"), (left, top), tile)


def textbbox(
    draw: ImageDraw.ImageDraw,
    xy: tuple[float, float],
    text: str,
    font: Any = None,
    anchor: str | None = None,
    spacing: float = 4,
    align: str = "left",
    direction: str | None = None,
    features: list[str] | None = None,
    language: str | None = None,
    stroke_width: float = 0,
    embedded_color: bool = False,
    *,
    font_size: float | None = None,
) -> tuple[float, float, float, float]:
    """``draw.textbbox(xy, text, ...)``: the box :func:`text` draws Arabic in."""
    arabic = _arabic(text)
    if arabic is None:
        box: tuple[float, float, float, float] = _ORIGINALS["textbbox"](
            draw,
            xy,
            text,
            font,
            anchor,
            spacing,
            align,
            direction,
            features,
            language,
            stroke_width,
            embedded_color,
            font_size=font_size,
        )
        return box
    return text_bbox(
        arabic,
        xy=xy,
        anchor=anchor or "la",
        spacing=spacing,
        align=align,
        stroke_width=stroke_width,
        **_font_options(font, font_size),
    )


def textlength(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: Any = None,
    direction: str | None = None,
    features: list[str] | None = None,
    language: str | None = None,
    embedded_color: bool = False,
    *,
    font_size: float | None = None,
) -> float:
    """``draw.textlength(text, ...)``: for Arabic, the width :func:`text` draws it at."""
    arabic = _arabic(text)
    if arabic is None:
        length: float = _ORIGINALS["textlength"](
            draw, text, font, direction, features, language, embedded_color, font_size=font_size
        )
        return length
    left, _, right, _ = text_bbox(arabic, anchor="ls", **_font_options(font, font_size))
    return float(right - left)


def _getbbox(
    font: ImageFont.FreeTypeFont,
    text: str,
    mode: str = "",
    direction: str | None = None,
    features: list[str] | None = None,
    language: str | None = None,
    stroke_width: float = 0,
    anchor: str | None = None,
) -> tuple[float, float, float, float]:
    arabic = _arabic(text)
    if arabic is None:
        box: tuple[float, float, float, float] = _ORIGINALS["getbbox"](
            font, text, mode, direction, features, language, stroke_width, anchor
        )
        return box
    return text_bbox(
        arabic, anchor=anchor or "la", stroke_width=stroke_width, **_font_options(font, None)
    )


def _getlength(
    font: ImageFont.FreeTypeFont,
    text: str,
    mode: str = "",
    direction: str | None = None,
    features: list[str] | None = None,
    language: str | None = None,
) -> float:
    arabic = _arabic(text)
    if arabic is None:
        length: float = _ORIGINALS["getlength"](font, text, mode, direction, features, language)
        return length
    left, _, right, _ = text_bbox(arabic, anchor="ls", **_font_options(font, None))
    return float(right - left)


@contextlib.contextmanager
def routing() -> Iterator[None]:
    """Send Pillow's text drawing and measuring through khatt inside a ``with`` block.

    ``ImageDraw.text``, ``multiline_text``, ``textbbox``, ``multiline_textbbox`` and
    ``textlength``, and ``FreeTypeFont.getbbox`` and ``getlength``, behave as
    :func:`text`, :func:`textbbox` and :func:`textlength` until the block ends, also
    inside libraries that call them. Only text with Arabic letters changes. The
    methods are restored when the block ends, even after an error. It changes them
    for the whole process, so other threads see the routing while it lasts.
    """
    with _routing:
        patched = {
            "text": text,
            "multiline_text": text,
            "textbbox": textbbox,
            "multiline_textbbox": textbbox,
            "textlength": textlength,
        }
        for name, function in patched.items():
            setattr(ImageDraw.ImageDraw, name, function)
        ImageFont.FreeTypeFont.getbbox = _getbbox  # type: ignore[assignment,method-assign]
        ImageFont.FreeTypeFont.getlength = _getlength  # type: ignore[assignment,method-assign]
        try:
            yield
        finally:
            for name in patched:
                setattr(ImageDraw.ImageDraw, name, _ORIGINALS[name])
            ImageFont.FreeTypeFont.getbbox = _ORIGINALS["getbbox"]  # type: ignore[method-assign]
            ImageFont.FreeTypeFont.getlength = _ORIGINALS["getlength"]  # type: ignore[method-assign]
