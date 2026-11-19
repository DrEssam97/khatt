"""Arabic poetry laid out the classical way: two hemistichs per verse, side by side.

Each verse (bayt) has a first half (sadr) on the right and a second half (ajuz) on the
left. Every half is stretched to the same width with kashida, as poetry is printed,
so the two columns have straight edges.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from PIL import Image

from khatt.color import Fill, rgba
from khatt.digits import with_digits
from khatt.draw import _extent, _is_number, _paint_text, _pixels, text_bbox
from khatt.fonts import Font, font_path, font_paths
from khatt.layout import layout_block, line_pitch
from khatt.raster import Block

_HALVES = re.compile(r"\t+|\s*\*+\s*|\s{3,}")
"""What separates a verse's two halves in a line of text: a tab, asterisks, or 3+ spaces."""


def _verses(verses: str | Sequence[tuple[str, str]]) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    if not isinstance(verses, str):
        for number, verse in enumerate(verses, start=1):
            halves = list(verse)
            if len(halves) != 2 or not all(isinstance(half, str) for half in halves):
                raise ValueError(f"verse {number} must be two strings (first half, second half)")
            pairs.append((halves[0], halves[1]))
        return pairs
    for number, line in enumerate(verses.splitlines(), start=1):
        if not line.strip():
            continue
        parts = [half for half in _HALVES.split(line.strip()) if half]
        if len(parts) != 2:
            raise ValueError(
                f"line {number} needs two halves, split by a tab, '*' or three spaces: {line!r}"
            )
        pairs.append((parts[0], parts[1]))
    return pairs


def poem(
    verses: str | Sequence[tuple[str, str]],
    *,
    font: Font = "amiri",
    size_px: int = 48,
    fill: Fill = "black",
    background: Fill | None = None,
    gap: int | None = None,
    line_spacing: float = 1.8,
    padding: int = 0,
    stroke_width: float = 0,
    stroke_fill: Fill | None = None,
    keep_tashkeel: bool = True,
    digits: str | None = None,
    fallback_fonts: Font | Sequence[Font] = (),
) -> Image.Image | None:
    """Draw verses of Arabic poetry in two columns, on their own image.

    The first half of each verse goes on the right and the second on the left. All
    halves are stretched with kashida (then wider spaces) to the width of the longest,
    so both columns have straight edges, as poetry is printed.

    >>> khatt.poem([("قفا نبك من ذكرى حبيب ومنزل", "بسقط اللوى بين الدخول فحومل")])

    Args:
        verses: ``(first half, second half)`` pairs, or text with one verse per line
            and its halves split by a tab, asterisks (``*`` or ``***``) or three or
            more spaces.
        font: A bundled font name (see :func:`khatt.list_fonts`) or the path to a
            .ttf/.otf font file.
        size_px: Font size in pixels per em.
        fill: Text colour: a name, ``#rrggbb[aa]``, or an RGB(A) tuple.
        background: A colour behind the poem; default: transparent.
        gap: Pixels between the two halves; default: one and a half ``size_px``.
        line_spacing: Distance between verses' baselines, in multiples of
            ``size_px``.
        padding: Empty pixels around the poem.
        stroke_width: Width in pixels of an outline around the letters.
        stroke_fill: Outline colour; default: ``fill``.
        keep_tashkeel: Keep Arabic diacritics (``False`` strips them).
        digits: ``"arabic-indic"`` writes the digits 0 to 9 as ٠ to ٩ (see
            :func:`khatt.arabic_digits`); default: as typed.
        fallback_fonts: Fonts for characters ``font`` has no glyph for.

    Returns:
        An RGBA image, or ``None`` when there is nothing to draw.

    Raises:
        ValueError: a verse does not have exactly two halves.
    """
    pairs = [
        (with_digits(first, digits), with_digits(second, digits))
        for first, second in _verses(verses)
    ]
    size = _pixels("size_px", size_px)
    if not (_is_number(line_spacing) and line_spacing > 0):
        raise ValueError(f"line_spacing must be a positive number, got {line_spacing!r}")
    if not (_is_number(stroke_width) and stroke_width >= 0):
        raise ValueError(f"stroke_width must not be negative, got {stroke_width!r}")
    space = round(1.5 * size) if gap is None else _pixels("gap", gap)
    if space < 0 or padding < 0:
        raise ValueError("gap and padding must not be negative")
    path = font_path(font)
    fallbacks = font_paths(fallback_fonts)
    widths = []
    for half in (half for pair in pairs for half in pair):
        left, _, right, _ = text_bbox(
            half,
            font=font,
            size_px=size,
            keep_tashkeel=keep_tashkeel,
            fallback_fonts=fallback_fonts,
        )
        widths.append(right - left)
    column = max(widths, default=0)
    if column <= 0:
        return None
    pitch = line_pitch(path, size_px=size, line_spacing=line_spacing)

    placed: list[tuple[Block, tuple[int, int]]] = []
    for number, pair in enumerate(pairs):
        baseline = round(number * pitch)
        for half, column_left in zip(pair, (column + space, 0), strict=True):
            laid_out = layout_block(
                half,
                path,
                size_px=size,
                align="justify",
                width=column,
                justify_last=True,
                line_spacing=line_spacing,
                keep_tashkeel=keep_tashkeel,
                stroke_width=stroke_width,
                fallbacks=fallbacks,
            )
            if laid_out is None:
                continue
            block = laid_out.block
            # A half that can't stretch all the way (no joined letters, no spaces)
            # sits in the middle of its column.
            x = column_left + (column - block.mask.size[0]) // 2
            placed.append((block, (x, baseline + block.top)))
    if not placed:
        return None

    boxes = [_extent(block, corner) for block, corner in placed]
    # Both columns keep their full width, so the poem stays centred on its gap.
    left = min(0, *(box[0] for box in boxes))
    top = min(box[1] for box in boxes)
    right = max(2 * column + space, *(box[2] for box in boxes))
    bottom = max(box[3] for box in boxes)
    pad = _pixels("padding", padding)
    image = Image.new(
        "RGBA",
        (right - left + 2 * pad, bottom - top + 2 * pad),
        (0, 0, 0, 0) if background is None else rgba(background),
    )
    color = rgba(fill)
    outline = color if stroke_fill is None else rgba(stroke_fill)
    for block, (x, y) in placed:
        _paint_text(image, block, (x - left + pad, y - top + pad), color, outline)
    return image
