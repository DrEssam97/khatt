"""Receipts for thermal printers: Arabic laid out at the printer's width, in black and white.

Thermal (ESC/POS) printers have no Arabic fonts of their own, so receipts are
printed as images. :func:`receipt_image` lays out a title, lines, two-column
rows such as an item and its price, and a footer, then returns a 1-bit image
the printer's exact width::

    from escpos.printer import Usb
    import khatt

    receipt = khatt.receipt_image(
        [("قهوة عربية", "15.00"), ("كعكة", "12.50"), "---", ("المجموع", "27.50")],
        title="مقهى الخط",
        footer="شكرا لزيارتكم",
    )
    Usb(0x04B8, 0x0202).image(receipt)
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from PIL import Image

from khatt.draw import draw_text, text_bbox
from khatt.fonts import Font, font_path, font_paths
from khatt.layout import _shape_lines
from khatt.shaping import base_direction

PRINTER_WIDTHS = {"58mm": 384, "80mm": 576}
"""Printable width in dots of the two common paper widths, at 203 dpi."""

Row = str | tuple[str, str]
"""A receipt row: a line of text, or a ``(start, end)`` pair such as an item and its price."""

_RULE_CHARACTERS = frozenset("-=_")


@dataclass(frozen=True)
class _Block:
    kind: str  # "line", "pair", "rule", "centered"
    texts: tuple[str, ...]
    size_px: int
    height: int


def _is_rule(row: object) -> bool:
    return isinstance(row, str) and len(row.strip()) >= 3 and set(row.strip()) <= _RULE_CHARACTERS


def receipt_image(
    rows: Sequence[Row],
    *,
    width: int | str = "80mm",
    title: str = "",
    footer: str = "",
    font: Font = "noto-naskh",
    size_px: int = 28,
    title_size_px: int | None = None,
    line_spacing: float = 1.3,
    margin: int = 12,
    direction: str | None = None,
    threshold: int = 128,
    fallback_fonts: Font | Sequence[Font] = (),
) -> Image.Image:
    """A receipt as a black-and-white image for a thermal printer.

    Args:
        rows: The body, top to bottom. A string is a line, wrapped at spaces
            to the width and starting from its own side (Arabic from the
            right, English from the left); an empty string is a blank line;
            a string of three or more ``-``, ``=`` or ``_`` is a dividing
            line. A ``(start, end)`` pair puts ``start`` on the receipt's
            starting side and ``end`` on the other, as an item and its
            price; a long ``start`` wraps without running into ``end``.
        width: Printable width in dots: ``"80mm"`` (576), ``"58mm"`` (384)
            or a number.
        title: Centered at the top, larger; line breaks start new lines.
        footer: Centered at the bottom.
        font: A bundled font name or a font file path.
        size_px: Font size of the body, in dots per em.
        title_size_px: Font size of the title; default 1.4 times
            ``size_px``.
        line_spacing: Distance between baselines, in multiples of the size.
        margin: Blank dots around the receipt.
        direction: ``"rtl"`` or ``"ltr"``: which side a pair starts on.
            Default: the direction of the first letter in the receipt.
        threshold: Coverage (0 to 255) from which a dot prints black.
        fallback_fonts: Fonts for characters ``font`` has no glyph for.

    Returns:
        A mode ``"1"`` image, ``width`` dots wide, black text on white:
        ready for ``escpos`` ``printer.image(...)``.
    """
    dots = PRINTER_WIDTHS.get(width, 0) if isinstance(width, str) else int(width)
    if dots <= 2 * margin:
        raise ValueError(
            f"width must be '58mm', '80mm' or more than twice the margin, got {width!r}"
        )
    if direction not in (None, "rtl", "ltr"):
        raise ValueError(f"direction must be 'rtl', 'ltr' or None, got {direction!r}")
    if not 0 <= threshold <= 255:
        raise ValueError(f"threshold must be from 0 to 255, got {threshold}")
    for row in rows:
        if isinstance(row, tuple):
            if len(row) != 2 or not all(isinstance(part, str) for part in row):
                raise ValueError(f"a pair row is (start, end), two strings; got {row!r}")
        elif not isinstance(row, str):
            raise ValueError(f"a row is a string or a (start, end) pair, got {row!r}")
    usable = dots - 2 * margin
    path = font_path(font)
    fallbacks = font_paths(fallback_fonts)
    big = title_size_px or round(size_px * 1.4)
    every_text = [title, *(r if isinstance(r, str) else " ".join(r) for r in rows), footer]
    if direction is None:
        direction = base_direction(" ".join(every_text))

    def pitch(size: int) -> int:
        return math.ceil(size * line_spacing)

    def line_count(text: str, size: int, room: int) -> int:
        lines = _shape_lines(
            text, path, True, max(1, room), ppem=size, warn=False, fallbacks=fallbacks
        )
        return max(1, len(lines.glyphs))

    def text_width(text: str, size: int) -> int:
        left, _, right, _ = text_bbox(text, font=font, size_px=size, fallback_fonts=fallback_fonts)
        return right - left

    gap = size_px
    blocks: list[_Block] = []
    if title:
        blocks.append(
            _Block("centered", (title,), big, line_count(title, big, usable) * pitch(big))
        )
    for row in rows:
        if isinstance(row, tuple):
            start, end = row
            room = usable - (text_width(end, size_px) + gap if end.strip() else 0)
            lines = line_count(start, size_px, room) if start.strip() else 1
            blocks.append(_Block("pair", (start, end), size_px, lines * pitch(size_px)))
        elif _is_rule(row):
            blocks.append(_Block("rule", (), size_px, pitch(size_px) // 2 + 2))
        elif not row.strip():
            blocks.append(_Block("line", ("",), size_px, pitch(size_px)))
        else:
            blocks.append(
                _Block("line", (row,), size_px, line_count(row, size_px, usable) * pitch(size_px))
            )
    if footer:
        blocks.append(
            _Block(
                "centered", (footer,), size_px, line_count(footer, size_px, usable) * pitch(size_px)
            )
        )

    height = 2 * margin + sum(block.height for block in blocks)
    canvas = Image.new("RGB", (dots, max(height, 2 * margin + 1)), "white")
    right, left, center = dots - margin, margin, dots // 2
    start_x, start_anchor = (right, "r") if direction == "rtl" else (left, "l")
    end_x, end_anchor = (left, "l") if direction == "rtl" else (right, "r")
    y = margin
    for block in blocks:
        common: dict[str, Any] = {
            "font": font,
            "size_px": block.size_px,
            "line_spacing": line_spacing,
            "fallback_fonts": fallback_fonts,
            "fill": "black",
        }
        # Each line's ascender sits where the line's slot starts, with the
        # extra spacing split above and below.
        top = y + (pitch(block.size_px) - block.size_px) // 2
        if block.kind == "centered":
            draw_text(
                canvas,
                (center, top),
                block.texts[0],
                anchor="ma",
                align="center",
                max_width=usable,
                **common,
            )
        elif block.kind == "line" and block.texts[0]:
            text = block.texts[0]
            own_right = base_direction(text) == "rtl"
            draw_text(
                canvas,
                (right if own_right else left, top),
                text,
                anchor="ra" if own_right else "la",
                max_width=usable,
                **common,
            )
        elif block.kind == "pair":
            start, end = block.texts
            if end.strip():
                draw_text(canvas, (end_x, top), end, anchor=end_anchor + "a", **common)
            if start.strip():
                room = usable - (text_width(end, block.size_px) + gap if end.strip() else 0)
                draw_text(
                    canvas,
                    (start_x, top),
                    start,
                    anchor=start_anchor + "a",
                    max_width=max(1, room),
                    **common,
                )
        elif block.kind == "rule":
            middle = y + block.height // 2
            canvas.paste("black", (left, middle - 1, right, middle + 1))
        y += block.height
    return canvas.convert("L").point(lambda value: 0 if value < threshold else 255, mode="1")
