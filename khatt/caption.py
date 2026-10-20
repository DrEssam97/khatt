"""Caption images with moviepy's ``TextClip`` geometry, drawn by khatt.

:func:`caption_image` takes the arguments of moviepy's ``TextClip`` and
returns the image such a clip shows; :class:`khatt.video.TextClip` is a thin
wrapper around it. It needs no moviepy, so the image also works anywhere a
caption frame does (ffmpeg overlays, thumbnails).

Text is shaped and drawn by khatt, never by Pillow's text layout, so Arabic
comes out right with or without Raqm. The height follows moviepy's
documented formula (ascent + descent + twice the stroke, plus the pitch of
each further line) and grows if the ink reaches beyond it, e.g. stacked
diacritics, so nothing is ever cut off.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from khatt.draw import Fill, _check_stroke, _is_number, _paint_text, _rgba
from khatt.fonts import Font, font_path
from khatt.layout import TextBlock, _ascender_px, _descender_px, layout_block
from khatt.raster import Box

_METHODS = ("label", "caption")
_TEXT_ALIGNS = ("left", "right", "center")
_HORIZONTAL_ALIGNS = ("left", "center", "right")
_VERTICAL_ALIGNS = ("top", "center", "bottom")


@dataclass(frozen=True)
class _Measured:
    """Caption text laid out at one size, in pixels from the first baseline."""

    laid_out: TextBlock | None
    """``None`` when there is no ink (empty text, only spaces)."""
    ink: Box
    """Box of everything painted, outline included (empty without ink)."""
    top: int
    """Top of the text block: the ascender line plus the outline, or the ink if higher."""
    bottom: int
    """Bottom of the text block: the last descender line plus the outline, or the ink."""

    @property
    def width(self) -> int:
        return self.ink[2] - self.ink[0]

    @property
    def height(self) -> int:
        return self.bottom - self.top


def _ink_box(laid_out: TextBlock) -> Box:
    """Box of everything painted for ``laid_out``, text and outline."""
    block = laid_out.block
    width, height = block.mask.size
    boxes = [(block.left, block.top, block.left + width, block.top + height)]
    if block.stroke is not None:
        mask, left, top = block.stroke
        boxes.append((left, top, left + mask.size[0], top + mask.size[1]))
    return (
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        max(b[2] for b in boxes),
        max(b[3] for b in boxes),
    )


def _measure(
    text: str,
    path: Path,
    size_px: int,
    *,
    max_width: int | None,
    align: str | None,
    interline: float,
    stroke_width: float,
    keep_tashkeel: bool,
) -> _Measured:
    laid_out = layout_block(
        text,
        path,
        size_px=size_px,
        max_width=max_width,
        align=align,
        line_spacing=1.0,  # unused: spacing always decides
        spacing=interline,
        keep_tashkeel=keep_tashkeel,
        stroke_width=stroke_width,
    )
    stroke = math.ceil(stroke_width)
    if laid_out is None:
        ascender, descender = _ascender_px(path, size_px), _descender_px(path, size_px)
        return _Measured(None, (0, 0, 0, 0), -ascender - stroke, descender + stroke)
    ink = _ink_box(laid_out)
    top = min(laid_out.ascender - stroke, ink[1])
    bottom = max(laid_out.descender + stroke, ink[3])
    return _Measured(laid_out, ink, top, bottom)


def _largest_size(fits: Callable[[int], bool], high: int) -> int:
    """The largest size from 1 to ``high`` for which ``fits`` holds; 1 if none."""
    low = 1
    if not fits(low):
        return low
    while low < high:
        middle = (low + high + 1) // 2
        if fits(middle):
            low = middle
        else:
            high = middle - 1
    return low


def _margins(margin: Sequence[int | None]) -> tuple[int, int, int, int]:
    """``(left, top, right, bottom)`` from moviepy's 2- or 4-tuple; ``None`` is 0."""
    if len(margin) == 2:
        horizontal, vertical = (int(m or 0) for m in margin)
        return horizontal, vertical, horizontal, vertical
    if len(margin) == 4:
        left, top, right, bottom = (int(m or 0) for m in margin)
        return left, top, right, bottom
    raise ValueError(f"margin must have 2 or 4 values, got {margin!r}")


def _check_choice(name: str, value: str | None, choices: Sequence[str], none: bool) -> None:
    if (value is None and none) or value in choices:
        return
    allowed = ", ".join(choices) + (" or None" if none else "")
    raise ValueError(f"{name} must be one of {allowed}, got {value!r}")


def caption_image(
    text: str,
    *,
    font: Font | None = "amiri",
    font_size: int | None = None,
    size: tuple[int | None, int | None] = (None, None),
    margin: Sequence[int | None] = (None, None),
    color: Fill = "black",
    bg_color: Fill | None = None,
    stroke_color: Fill | None = None,
    stroke_width: float = 0,
    method: str = "label",
    text_align: str | None = None,
    horizontal_align: str = "center",
    vertical_align: str = "center",
    interline: float = 4,
    transparent: bool = True,
    keep_tashkeel: bool = True,
) -> Image.Image:
    """Draw ``text`` as moviepy's ``TextClip`` would show it, shaped by khatt.

    The arguments are ``TextClip``'s (moviepy 2.2), with the same meaning
    and defaults except ``font`` and ``text_align``.

    Args:
        text: The text, as typed. Line breaks start new lines.
        font: A bundled font name (see :func:`khatt.list_fonts`) or the path
            to a .ttf/.otf font file; ``None`` means ``"amiri"``.
        font_size: Font size in pixels per em. ``None`` picks the largest
            size that fits ``size`` (the width; for ``"caption"`` the height
            too, and for ``"label"`` the height if given).
        size: ``(width, height)`` of the text area, without margins. ``None``
            for either sizes it to the text. ``"caption"`` needs the width.
        margin: Space added around the text area: ``(horizontal,
            vertical)`` or ``(left, top, right, bottom)``; ``None`` is 0.
        color: Text colour: a name, ``#rrggbb[aa]``, or an RGB(A) tuple.
        bg_color: Background colour; default: transparent (or black when
            ``transparent`` is ``False``).
        stroke_color: Outline colour; ``None`` draws the outline (if
            ``stroke_width`` is set) in ``color``, as moviepy does.
        stroke_width: Outline width in pixels.
        method: ``"label"`` sizes the image to the text; ``"caption"`` wraps
            the text at spaces to the width.
        text_align: ``"left"``, ``"right"`` or ``"center"`` alignment of
            lines within the text. ``None`` (default; moviepy's is
            ``"left"``) aligns right-to-left paragraphs right and
            left-to-right ones left.
        horizontal_align: ``"left"``, ``"center"`` or ``"right"``: where the
            text sits in a wider area.
        vertical_align: ``"top"``, ``"center"`` or ``"bottom"``: where the
            text sits in a taller area.
        interline: Pixels between lines, as Pillow's ``spacing`` (see
            :func:`khatt.draw_text`).
        transparent: RGBA image (``True``) or RGB.
        keep_tashkeel: Keep Arabic diacritics (``False`` strips them).

    Returns:
        An RGBA image (RGB when ``transparent`` is ``False``). Characters
        the font does not cover are skipped with a
        :class:`khatt.UnsupportedCharacterWarning`.
    """
    _check_choice("method", method, _METHODS, none=False)
    _check_choice("text_align", text_align, _TEXT_ALIGNS, none=True)
    _check_choice("horizontal_align", horizontal_align, _HORIZONTAL_ALIGNS, none=False)
    _check_choice("vertical_align", vertical_align, _VERTICAL_ALIGNS, none=False)
    _check_stroke(stroke_width)
    if not _is_number(interline):
        raise ValueError(f"interline must be a number of pixels, got {interline!r}")
    if font_size is not None and font_size < 1:
        raise ValueError(f"font_size must be at least 1, got {font_size}")
    width, height = size
    for name, value in (("width", width), ("height", height)):
        if value is not None and value < 1:
            raise ValueError(f"size: the {name} must be at least 1, got {value}")
    left, top, right, bottom = _margins(margin)
    color_rgba = _rgba(color)
    stroke_rgba = color_rgba if stroke_color is None else _rgba(stroke_color)
    background = _rgba(bg_color) if bg_color is not None else (0, 0, 0, 0 if transparent else 255)
    path = font_path("amiri" if font is None else font)

    wrap: int | None = None
    if method == "caption":
        if width is None:
            raise ValueError("method='caption' needs a width in size")
        if font_size is None and height is None:
            raise ValueError("method='caption' needs a height in size, or a font_size")
        # Wrap the text so that its outline fits the width too.
        wrap = max(1, width - 2 * math.ceil(stroke_width))

    def measure(size_px: int) -> _Measured:
        return _measure(
            text,
            path,
            size_px,
            max_width=wrap,
            align=text_align,
            interline=interline,
            stroke_width=stroke_width,
            keep_tashkeel=keep_tashkeel,
        )

    if font_size is None:
        if width is None:
            raise ValueError("method='label' needs a font_size, or a width in size")
        area = (width, height)

        def fits(size_px: int) -> bool:
            measured = measure(size_px)
            return measured.width <= area[0] and (area[1] is None or measured.height <= area[1])

        font_size = _largest_size(fits, high=width)
    measured = measure(font_size)
    area_width = width if width is not None else max(1, measured.width)
    area_height = height if height is not None else measured.height

    mode = "RGBA" if transparent else "RGB"
    image = Image.new(
        mode,
        (area_width + left + right, area_height + top + bottom),
        background if transparent else background[:3],
    )
    if measured.laid_out is None:
        return image
    free_x, free_y = area_width - measured.width, area_height - measured.height
    x = left + {"left": 0, "center": free_x // 2, "right": free_x}[horizontal_align]
    y = top + {"top": 0, "center": free_y // 2, "bottom": free_y}[vertical_align]
    # (x, y) is where the text block's top-left goes; place the layout origin
    # (the first baseline's left end) accordingly.
    origin_x, origin_y = x - measured.ink[0], y - measured.top
    block = measured.laid_out.block
    corner = (origin_x + block.left, origin_y + block.top)
    _paint_text(image, block, corner, color_rgba, stroke_rgba)
    return image
