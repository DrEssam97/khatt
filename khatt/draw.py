"""Draw correctly shaped text onto existing Pillow images.

Text goes through khatt's own pipeline (HarfBuzz shaping, FreeType
rasterization, khatt's line layout) and only the finished coverage mask is
composited onto the image. Pillow's text layout (``ImageDraw.text``) is never
used, so the output is identical whether or not Pillow was built with Raqm,
and text is never shaped twice.
"""

from __future__ import annotations

import math
import warnings
from collections.abc import Sequence
from pathlib import Path

from PIL import Image, ImageColor

from khatt.fonts import font_path
from khatt.layout import layout_block, measure_block

Fill = str | tuple[int, int, int] | tuple[int, int, int, int]
"""A colour name or ``#rrggbb[aa]`` string, or an RGB / RGBA tuple."""

_MODES = ("RGB", "RGBA")
_ALIGNS = ("left", "right", "center")
_VALIGNS = ("top", "middle", "bottom")
_FITS = ("shrink", "wrap", "none")


class TextOverflowWarning(UserWarning):
    """Text did not fit in the box given to :func:`overlay`; it was clipped to the box."""


def _round(value: float) -> int:
    return math.floor(value + 0.5)


def _check_image(image: Image.Image) -> None:
    if image.mode not in _MODES:
        raise ValueError(
            f"image mode must be RGB or RGBA, got {image.mode!r}; "
            "convert it first, e.g. image.convert('RGBA')"
        )


def _check_layout(size_px: int, line_spacing: float, align: str | None) -> None:
    if size_px < 1:
        raise ValueError(f"size_px must be at least 1, got {size_px}")
    if line_spacing <= 0:
        raise ValueError(f"line_spacing must be positive, got {line_spacing}")
    if align is not None and align not in _ALIGNS:
        raise ValueError(f"align must be one of {', '.join(_ALIGNS)} or None, got {align!r}")


def _rgba(fill: Fill) -> tuple[int, int, int, int]:
    if isinstance(fill, str):
        color = ImageColor.getcolor(fill, "RGBA")  # raises ValueError if unknown
    elif isinstance(fill, (tuple, list)) and len(fill) in (3, 4):
        color = (*fill, 255)[:4]
    else:
        color = ()
    if not (
        isinstance(color, tuple)
        and len(color) == 4
        and all(isinstance(c, int) and 0 <= c <= 255 for c in color)
    ):
        raise ValueError(f"fill must be a colour string or an RGB(A) tuple of 0-255, got {fill!r}")
    red, green, blue, alpha = color
    return red, green, blue, alpha


def _paint(
    image: Image.Image,
    mask: Image.Image,
    xy: tuple[int, int],
    color: tuple[int, int, int, int],
    clip: tuple[int, int, int, int] | None = None,
) -> None:
    """Composite ``color`` through the coverage ``mask`` placed at ``xy``.

    Only the part inside ``clip`` (default: the whole image) is drawn. RGBA
    images get Porter-Duff "over" compositing, so a transparent background
    stays transparent around the text and edges carry no dark fringe.
    """
    x, y = xy
    left, top, right, bottom = clip if clip is not None else (0, 0, *image.size)
    x0, y0 = max(x, left, 0), max(y, top, 0)
    x1 = min(x + mask.size[0], right, image.size[0])
    y1 = min(y + mask.size[1], bottom, image.size[1])
    *rgb, opacity = color
    if x0 >= x1 or y0 >= y1 or opacity == 0:
        return
    alpha = mask.crop((x0 - x, y0 - y, x1 - x, y1 - y))
    if opacity < 255:
        alpha = alpha.point([(v * opacity + 127) // 255 for v in range(256)])
    if image.mode == "RGBA":
        layer = Image.new("RGBA", alpha.size, (*rgb, 0))
        layer.putalpha(alpha)
        image.alpha_composite(layer, (x0, y0))
    else:
        image.paste(tuple(rgb), (x0, y0, x1, y1), alpha)


def draw_text(
    image: Image.Image,
    xy: tuple[float, float],
    text: str,
    *,
    font: str = "amiri",
    size_px: int = 48,
    fill: Fill = "black",
    align: str | None = None,
    anchor: str = "la",
    max_width: int | None = None,
    line_spacing: float = 1.2,
    keep_tashkeel: bool = True,
) -> Image.Image:
    """Draw shaped text onto ``image`` (in place) and return it.

    A drop-in for ``ImageDraw.text`` that shapes Arabic correctly whether or
    not Pillow has Raqm. Pass the text as typed (logical order): never
    reshape or reorder it first.

    Args:
        image: An RGB or RGBA Pillow image.
        xy: Where the ``anchor`` point of the text goes, in pixels.
        text: The text; line breaks start new lines and mixed Arabic/Latin
            text comes out in the correct visual order.
        font: A bundled font name (see :func:`khatt.list_fonts`).
        size_px: Font size in pixels per em, as in ``ImageFont.truetype``.
        fill: Text colour: a name, ``#rrggbb[aa]``, or an RGB(A) tuple. Its
            alpha makes the text translucent.
        align: ``"left"``, ``"right"`` or ``"center"`` alignment of lines
            within the block; ``None`` aligns right-to-left paragraphs right
            and left-to-right ones left.
        anchor: Two letters, as in Pillow. Horizontal: ``l`` / ``m`` / ``r``
            for the left, middle or right of the ink. Vertical: ``a``
            (first line's ascender), ``t`` (top of the ink), ``m`` (middle,
            ascender to descender), ``s`` (first line's baseline), ``b``
            (bottom of the ink) or ``d`` (last line's descender).
        max_width: Wrap lines at spaces to this many pixels. A word wider
            than that on its own still gets a line of its own.
        line_spacing: Distance between baselines, in multiples of ``size_px``.
        keep_tashkeel: Keep Arabic diacritics (``False`` strips them).

    Returns:
        ``image``, drawn on. Characters the font does not cover are skipped
        with a :class:`khatt.UnsupportedCharacterWarning`.
    """
    _check_image(image)
    color = _rgba(fill)
    _check_layout(size_px, line_spacing, align)
    if len(anchor) != 2 or anchor[0] not in "lmr" or anchor[1] not in "atmsbd":
        raise ValueError(f"anchor must be one of l/m/r followed by a/t/m/s/b/d, got {anchor!r}")
    if max_width is not None and max_width < 1:
        raise ValueError(f"max_width must be at least 1, got {max_width}")

    laid_out = layout_block(
        text,
        font_path(font),
        size_px=size_px,
        max_width=max_width,
        align=align,
        line_spacing=line_spacing,
        keep_tashkeel=keep_tashkeel,
    )
    if laid_out is None:
        return image
    block = laid_out.block
    width, height = block.mask.size
    anchor_x = {"l": 0.0, "m": width / 2, "r": float(width)}[anchor[0]]
    anchor_y = {
        "a": laid_out.ascender,
        "t": block.top,
        "m": (laid_out.ascender + laid_out.descender) / 2,
        "s": 0,
        "b": block.top + height,
        "d": laid_out.descender,
    }[anchor[1]]
    position = (_round(xy[0] - anchor_x), _round(xy[1] - anchor_y) + block.top)
    _paint(image, block.mask, position, color)
    return image


def _largest_fitting(
    text: str,
    path: Path,
    *,
    sizes: tuple[int, int],
    box: tuple[int, int],
    line_spacing: float,
    keep_tashkeel: bool,
) -> int:
    """Binary-search the largest size in ``sizes`` whose wrapped text fits ``box``.

    Returns the smallest size when none fits.
    """
    width, height = box

    def fits(size: int) -> bool:
        extent = measure_block(
            text,
            path,
            size_px=size,
            max_width=width,
            line_spacing=line_spacing,
            keep_tashkeel=keep_tashkeel,
        )
        return extent is None or (extent[0] <= width and extent[1] <= height)

    low, high = sizes
    if not fits(low):
        return low
    while low < high:
        middle = (low + high + 1) // 2
        if fits(middle):
            low = middle
        else:
            high = middle - 1
    return low


def _block_alignment(alignments: Sequence[str]) -> str:
    """How a block wider than its box overhangs it: by its lines' common alignment."""
    return alignments[0] if len(set(alignments)) == 1 else "center"


def overlay(
    image: Image.Image,
    text: str,
    box: tuple[int, int, int, int],
    *,
    fit: str = "shrink",
    font: str = "amiri",
    max_size_px: int | None = None,
    min_size_px: int = 8,
    fill: Fill = "black",
    align: str | None = None,
    valign: str = "middle",
    padding: int = 0,
    line_spacing: float = 1.2,
    keep_tashkeel: bool = True,
) -> Image.Image:
    """Place shaped text inside ``box`` on ``image`` (in place) and return it.

    Args:
        image: An RGB or RGBA Pillow image.
        text: The text, as typed (see :func:`draw_text`).
        box: ``(left, top, right, bottom)`` in pixels.
        fit: ``"shrink"`` (default) uses the largest size from
            ``max_size_px`` down to ``min_size_px`` at which the text, wrapped
            at spaces, fits the box. ``"wrap"`` wraps at ``max_size_px``;
            ``"none"`` draws at ``max_size_px`` without wrapping.
        font: A bundled font name (see :func:`khatt.list_fonts`).
        max_size_px: The font size for ``"wrap"`` and ``"none"`` and the
            largest size ``"shrink"`` tries, in pixels per em; default: the
            height inside the box.
        min_size_px: The smallest size ``"shrink"`` tries.
        fill: Text colour, as in :func:`draw_text`.
        align: ``"left"``, ``"right"`` or ``"center"`` within the box;
            ``None`` aligns right-to-left paragraphs right and left-to-right
            ones left.
        valign: ``"top"``, ``"middle"`` or ``"bottom"``: where the ink sits
            in the box.
        padding: Pixels kept clear inside each edge of the box.
        line_spacing: Distance between baselines, in multiples of the size.
        keep_tashkeel: Keep Arabic diacritics (``False`` strips them).

    Returns:
        ``image``, drawn on. Nothing is ever drawn outside ``box``: text that
        does not fit inside the padding (with ``"shrink"``, not even at
        ``min_size_px``) raises a :class:`TextOverflowWarning` and is clipped
        to the box.
    """
    _check_image(image)
    color = _rgba(fill)
    if fit not in _FITS:
        raise ValueError(f"fit must be one of {', '.join(_FITS)}, got {fit!r}")
    if valign not in _VALIGNS:
        raise ValueError(f"valign must be one of {', '.join(_VALIGNS)}, got {valign!r}")
    if padding < 0:
        raise ValueError(f"padding must not be negative, got {padding}")
    left, top, right, bottom = (_round(edge) for edge in box)
    inner = (left + padding, top + padding, right - padding, bottom - padding)
    inner_width, inner_height = inner[2] - inner[0], inner[3] - inner[1]
    if inner_width < 1 or inner_height < 1:
        raise ValueError(f"box {box} has no room inside a padding of {padding}")
    for name, value in (("max_size_px", max_size_px), ("min_size_px", min_size_px)):
        if value is not None and value < 1:
            raise ValueError(f"{name} must be at least 1, got {value}")
    size = inner_height if max_size_px is None else max_size_px
    _check_layout(size, line_spacing, align)

    path = font_path(font)
    if fit == "shrink":
        if min_size_px > size:
            raise ValueError(f"min_size_px ({min_size_px}) is larger than the size ({size})")
        size = _largest_fitting(
            text,
            path,
            sizes=(min_size_px, size),
            box=(inner_width, inner_height),
            line_spacing=line_spacing,
            keep_tashkeel=keep_tashkeel,
        )
    laid_out = layout_block(
        text,
        path,
        size_px=size,
        max_width=None if fit == "none" else inner_width,
        align=align,
        line_spacing=line_spacing,
        keep_tashkeel=keep_tashkeel,
        width=inner_width,
    )
    if laid_out is None:
        return image
    block = laid_out.block
    width, height = block.mask.size
    overhang = block.width - inner_width
    x = inner[0] + block.left
    x -= {"left": 0, "right": overhang, "center": overhang // 2}[_block_alignment(laid_out.align)]
    y = {
        "top": inner[1],
        "middle": inner[1] + (inner_height - height) // 2,
        "bottom": inner[3] - height,
    }[valign]
    if x < inner[0] or y < inner[1] or x + width > inner[2] or y + height > inner[3]:
        warnings.warn(
            f"text does not fit inside the box at {size}px; anything outside the box is clipped",
            TextOverflowWarning,
            stacklevel=2,
        )
    _paint(image, block.mask, (x, y), color, clip=(left, top, right, bottom))
    return image
