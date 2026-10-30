"""Draw correctly shaped text onto existing Pillow images.

Text goes through khatt's own pipeline (HarfBuzz shaping, FreeType
rasterization, khatt's line layout) and only the finished coverage mask is
composited onto the image. Pillow's text layout (``ImageDraw.text``) is never
used, so the output is identical whether or not Pillow was built with Raqm,
and text is never shaped twice.
"""

from __future__ import annotations

import math
import numbers
import warnings
from collections.abc import Sequence
from pathlib import Path

from PIL import Image, ImageChops, ImageColor

from khatt.fonts import Font, font_path, font_paths
from khatt.layout import largest_size, layout_block, measure_block, smallest_spaced_size
from khatt.raster import Block, Box

Fill = str | tuple[int, int, int] | tuple[int, int, int, int]
"""A colour name or ``#rrggbb[aa]`` string, or an RGB / RGBA tuple."""

_MODES = ("RGB", "RGBA")
_ALIGNS = ("left", "right", "center")
_VALIGNS = ("top", "middle", "bottom")
_FITS = ("shrink", "wrap", "none")

DEFAULT_LINE_SPACING = 1.2
"""Distance between baselines, in multiples of the size, unless told otherwise."""


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


def _is_number(value: object) -> bool:
    """A finite real number, NumPy scalars included."""
    return isinstance(value, numbers.Real) and math.isfinite(value)


def _check_layout(
    size_px: int, line_spacing: float | None, spacing: float | None, align: str | None
) -> float:
    """Check the layout arguments; return the ``line_spacing`` multiplier to use."""
    if size_px < 1:
        raise ValueError(f"size_px must be at least 1, got {size_px}")
    if line_spacing is not None and spacing is not None:
        raise ValueError("pass line_spacing (a multiple of the size) or spacing (pixels), not both")
    if spacing is not None and not _is_number(spacing):
        raise ValueError(f"spacing must be a number of pixels, got {spacing!r}")
    if line_spacing is None:
        line_spacing = DEFAULT_LINE_SPACING
    if not (_is_number(line_spacing) and line_spacing > 0):
        raise ValueError(f"line_spacing must be a positive number, got {line_spacing!r}")
    if align is not None and align not in _ALIGNS:
        raise ValueError(f"align must be one of {', '.join(_ALIGNS)} or None, got {align!r}")
    return line_spacing


def _check_stroke(stroke_width: float) -> None:
    if not (_is_number(stroke_width) and stroke_width >= 0):
        raise ValueError(f"stroke_width must be a non-negative number, got {stroke_width!r}")


def _paint_text(
    image: Image.Image,
    block: Block,
    xy: tuple[int, int],
    color: tuple[int, int, int, int],
    stroke_color: tuple[int, int, int, int],
    clip: tuple[int, int, int, int] | None = None,
) -> None:
    """Paint ``block``'s stroke (if any) and then its text, the text mask's corner at ``xy``."""
    if block.stroke is None:
        _paint(image, block.mask, xy, color, clip)
        return
    stroke, left, top = block.stroke
    stroke_xy = (xy[0] + left - block.left, xy[1] + top - block.top)
    if stroke_color != color:
        _paint(image, stroke, stroke_xy, stroke_color, clip)
        _paint(image, block.mask, xy, color, clip)
        return
    # Same colour: one coat over text and outline together, as Pillow paints
    # it. Two coats would darken a translucent fill where they overlap.
    x0, y0, x1, y1 = _extent(block, xy)
    union = Image.new("L", (x1 - x0, y1 - y0), 0)
    for mask, (x, y) in ((stroke, stroke_xy), (block.mask, xy)):
        region = (x - x0, y - y0, x - x0 + mask.size[0], y - y0 + mask.size[1])
        union.paste(ImageChops.lighter(union.crop(region), mask), region[:2])
    _paint(image, union, (x0, y0), color, clip)


def _extent(block: Block, xy: tuple[int, int]) -> Box:
    """Box of everything :func:`_paint_text` paints for ``block`` at ``xy``: text and outline."""
    x, y = xy
    width, height = block.mask.size
    boxes = [(x, y, x + width, y + height)]
    if block.stroke is not None:
        mask, left, top = block.stroke
        sx, sy = x + left - block.left, y + top - block.top
        boxes.append((sx, sy, sx + mask.size[0], sy + mask.size[1]))
    return (
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        max(b[2] for b in boxes),
        max(b[3] for b in boxes),
    )


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


def _place_text(
    xy: tuple[float, float],
    text: str,
    *,
    font: Font,
    size_px: int,
    align: str | None,
    anchor: str,
    max_width: int | None,
    line_spacing: float | None,
    spacing: float | None,
    keep_tashkeel: bool,
    stroke_width: float,
    fallback_fonts: Font | Sequence[Font],
) -> tuple[Block, tuple[int, int]] | None:
    """Lay out text as :func:`draw_text` draws it: the block, and where its mask's corner goes.

    ``None`` means there is nothing to draw.
    """
    _check_stroke(stroke_width)
    line_spacing = _check_layout(size_px, line_spacing, spacing, align)
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
        spacing=spacing,
        keep_tashkeel=keep_tashkeel,
        stroke_width=stroke_width,
        fallbacks=font_paths(fallback_fonts),
    )
    if laid_out is None:
        return None
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
    return block, (_round(xy[0] - anchor_x), _round(xy[1] - anchor_y) + block.top)


def draw_text(
    image: Image.Image,
    xy: tuple[float, float],
    text: str,
    *,
    font: Font = "amiri",
    size_px: int = 48,
    fill: Fill = "black",
    align: str | None = None,
    anchor: str = "la",
    max_width: int | None = None,
    line_spacing: float | None = None,
    spacing: float | None = None,
    keep_tashkeel: bool = True,
    stroke_width: float = 0,
    stroke_fill: Fill | None = None,
    fallback_fonts: Font | Sequence[Font] = (),
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
        font: A bundled font name (see :func:`khatt.list_fonts`) or the path
            to a .ttf/.otf font file.
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
        line_spacing: Distance between baselines, in multiples of
            ``size_px``; default 1.2.
        spacing: Pixels between lines instead of ``line_spacing``, as in
            Pillow's ``multiline_text``: each line's ascender line sits
            ``spacing`` pixels below the previous line's baseline (plus
            twice ``stroke_width``, so outlines don't eat into it). Negative
            values pull lines closer.
        keep_tashkeel: Keep Arabic diacritics (``False`` strips them).
        stroke_width: Width in pixels of an outline drawn around the text,
            as in Pillow: the text grown outward by this much, with round
            corners, painted under it. It doesn't move the text: anchors and
            alignment work as without it (but with ``spacing``, lines also
            move apart by twice the width, as in Pillow).
        stroke_fill: Outline colour, in the same formats as ``fill``;
            default: ``fill`` (which makes the text bolder).
        fallback_fonts: Fonts tried in order (bundled names or file paths)
            for characters ``font`` has no glyph for, such as a CJK font
            for Chinese inside Arabic text. Line spacing and anchors still
            follow ``font``.

    Returns:
        ``image``, drawn on. Characters the font does not cover are skipped
        with a :class:`khatt.UnsupportedCharacterWarning` (see
        :func:`khatt.missing_characters`).
    """
    _check_image(image)
    color = _rgba(fill)
    stroke_color = color if stroke_fill is None else _rgba(stroke_fill)
    placed = _place_text(
        xy,
        text,
        font=font,
        size_px=size_px,
        align=align,
        anchor=anchor,
        max_width=max_width,
        line_spacing=line_spacing,
        spacing=spacing,
        keep_tashkeel=keep_tashkeel,
        stroke_width=stroke_width,
        fallback_fonts=fallback_fonts,
    )
    if placed is not None:
        _paint_text(image, *placed, color, stroke_color)
    return image


def text_bbox(
    text: str,
    *,
    xy: tuple[float, float] = (0, 0),
    font: Font = "amiri",
    size_px: int = 48,
    align: str | None = None,
    anchor: str = "la",
    max_width: int | None = None,
    line_spacing: float | None = None,
    spacing: float | None = None,
    keep_tashkeel: bool = True,
    stroke_width: float = 0,
    fallback_fonts: Font | Sequence[Font] = (),
) -> Box:
    """The box :func:`draw_text` would draw ``text`` in, without drawing it.

    Like Pillow's ``ImageDraw.textbbox``, and with :func:`draw_text`'s
    arguments, which mean the same here. The box is exact: it holds every
    pixel that :func:`draw_text` would paint at ``xy``, the outline
    included, and no row or column of it is blank.

    Returns:
        ``(left, top, right, bottom)`` in pixels, ``right`` and ``bottom``
        exclusive (so ``right - left`` is the width). Text with nothing to
        draw (empty, or only spaces) gives an empty box at ``xy``.
    """
    placed = _place_text(
        xy,
        text,
        font=font,
        size_px=size_px,
        align=align,
        anchor=anchor,
        max_width=max_width,
        line_spacing=line_spacing,
        spacing=spacing,
        keep_tashkeel=keep_tashkeel,
        stroke_width=stroke_width,
        fallback_fonts=fallback_fonts,
    )
    if placed is None:
        x, y = _round(xy[0]), _round(xy[1])
        return x, y, x, y
    return _extent(*placed)


def _largest_fitting(
    text: str,
    path: Path,
    *,
    sizes: tuple[int, int],
    box: tuple[int, int],
    line_spacing: float,
    keep_tashkeel: bool,
    spacing: float | None = None,
    stroke_width: float = 0,
    fallbacks: Sequence[Path] = (),
) -> int:
    """The largest size in ``sizes`` whose wrapped text fits ``box``.

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
            spacing=spacing,
            stroke_width=stroke_width,
            fallbacks=fallbacks,
        )
        return extent is None or (extent[0] <= width and extent[1] <= height)

    low = smallest_spaced_size(
        path, sizes, line_spacing=line_spacing, spacing=spacing, stroke_width=stroke_width
    )
    return largest_size(fits, (low, sizes[1]))


def _block_alignment(alignments: Sequence[str]) -> str:
    """How a block wider than its box overhangs it: by its lines' common alignment."""
    return alignments[0] if len(set(alignments)) == 1 else "center"


def overlay(
    image: Image.Image,
    text: str,
    box: tuple[int, int, int, int],
    *,
    fit: str = "shrink",
    font: Font = "amiri",
    max_size_px: int | None = None,
    min_size_px: int = 8,
    fill: Fill = "black",
    align: str | None = None,
    valign: str = "middle",
    padding: int = 0,
    line_spacing: float | None = None,
    spacing: float | None = None,
    keep_tashkeel: bool = True,
    stroke_width: float = 0,
    stroke_fill: Fill | None = None,
    fallback_fonts: Font | Sequence[Font] = (),
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
        font: A bundled font name (see :func:`khatt.list_fonts`) or the path
            to a .ttf/.otf font file.
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
        line_spacing: Distance between baselines, in multiples of the size;
            default 1.2.
        spacing: Pixels between lines instead of ``line_spacing``, as in
            :func:`draw_text`.
        keep_tashkeel: Keep Arabic diacritics (``False`` strips them).
        stroke_width: Width in pixels of an outline around the text, as in
            :func:`draw_text`. The outline counts as part of the text: it is
            fitted inside the padding too.
        stroke_fill: Outline colour; default: ``fill``.
        fallback_fonts: Fonts tried in order (bundled names or file paths)
            for characters ``font`` has no glyph for, such as a CJK font
            for Chinese inside Arabic text. Line spacing and anchors still
            follow ``font``.

    Returns:
        ``image``, drawn on. Nothing is ever drawn outside ``box``: text that
        does not fit inside the padding (with ``"shrink"``, not even at
        ``min_size_px``) raises a :class:`TextOverflowWarning` and is clipped
        to the box.
    """
    _check_image(image)
    color = _rgba(fill)
    stroke_color = color if stroke_fill is None else _rgba(stroke_fill)
    _check_stroke(stroke_width)
    if fit not in _FITS:
        raise ValueError(f"fit must be one of {', '.join(_FITS)}, got {fit!r}")
    if valign not in _VALIGNS:
        raise ValueError(f"valign must be one of {', '.join(_VALIGNS)}, got {valign!r}")
    if padding < 0:
        raise ValueError(f"padding must not be negative, got {padding}")
    left, top, right, bottom = (_round(edge) for edge in box)
    inner = (left + padding, top + padding, right - padding, bottom - padding)
    # The text itself goes inside the padding minus the outline, which then
    # grows into that margin.
    inset = math.ceil(stroke_width)
    text_area = (inner[0] + inset, inner[1] + inset, inner[2] - inset, inner[3] - inset)
    inner_width, inner_height = text_area[2] - text_area[0], text_area[3] - text_area[1]
    if inner_width < 1 or inner_height < 1:
        room = f"a padding of {padding}" + (f" and a stroke of {stroke_width}" if inset else "")
        raise ValueError(f"box {box} has no room inside {room}")
    for name, value in (("max_size_px", max_size_px), ("min_size_px", min_size_px)):
        if value is not None and value < 1:
            raise ValueError(f"{name} must be at least 1, got {value}")
    size = inner_height if max_size_px is None else max_size_px
    line_spacing = _check_layout(size, line_spacing, spacing, align)

    path, fallbacks = font_path(font), font_paths(fallback_fonts)
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
            spacing=spacing,
            stroke_width=stroke_width,
            fallbacks=fallbacks,
        )
    laid_out = layout_block(
        text,
        path,
        size_px=size,
        max_width=None if fit == "none" else inner_width,
        align=align,
        line_spacing=line_spacing,
        spacing=spacing,
        keep_tashkeel=keep_tashkeel,
        width=inner_width,
        stroke_width=stroke_width,
        fallbacks=fallbacks,
    )
    if laid_out is None:
        return image
    block = laid_out.block
    height = block.mask.size[1]
    overhang = block.width - inner_width
    x = text_area[0] + block.left
    x -= {"left": 0, "right": overhang, "center": overhang // 2}[_block_alignment(laid_out.align)]
    y = {
        "top": text_area[1],
        "middle": text_area[1] + (inner_height - height) // 2,
        "bottom": text_area[3] - height,
    }[valign]
    # What has to fit is everything drawn: the outline too.
    x0, y0, x1, y1 = _extent(block, (x, y))
    if x0 < inner[0] or y0 < inner[1] or x1 > inner[2] or y1 > inner[3]:
        warnings.warn(
            f"text does not fit inside the box at {size}px; anything outside the box is clipped",
            TextOverflowWarning,
            stacklevel=2,
        )
    _paint_text(image, block, (x, y), color, stroke_color, clip=(left, top, right, bottom))
    return image
