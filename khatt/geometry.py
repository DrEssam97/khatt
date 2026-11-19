"""Where each word of a text lands when :func:`khatt.draw_text` draws it.

:func:`word_boxes` lays the text out exactly as ``draw_text`` does, and returns every
word's box and its own coverage mask, in reading order. Uses: highlighting the word
being recited (paint its mask), word-level labels for OCR training data, hit-testing a
tap on an image, or cutting a word out.

    import khatt

    for word in khatt.word_boxes("بسم الله الرحمن الرحيم", xy=(20, 20), size_px=64):
        print(word.text, word.box)
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from PIL import Image

from khatt.digits import with_digits
from khatt.draw import _place_text
from khatt.fonts import Font
from khatt.raster import Box

_WORD = re.compile(r"\S+")


@dataclass(frozen=True)
class WordBox:
    """One word as :func:`khatt.draw_text` draws it."""

    text: str
    """The word, as in the text given."""
    start: int
    end: int
    """Where it is in the text given: ``text[start:end]``."""
    box: Box
    """``(left, top, right, bottom)`` in pixels of the image, ``right`` and ``bottom``
    exclusive: exactly the pixels the word's ink covers."""
    mask: Image.Image
    """The word's coverage (mode ``"L"``, 255 is ink), the size of ``box``. Paste a
    colour through it at ``box[:2]`` to paint just that word."""


def word_boxes(
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
    digits: str | None = None,
    fallback_fonts: Font | Sequence[Font] = (),
    ranges: Sequence[tuple[int, int]] | None = None,
) -> list[WordBox]:
    """Each word's box and mask, as :func:`khatt.draw_text` would draw ``text`` at ``xy``.

    Takes ``draw_text``'s layout arguments, which mean the same here, so the boxes
    match what it draws: wrapped lines, alignment and anchors included. The text is
    shaped as a whole, so letters keep their joins and marks stay with their letter.

    Args:
        text: The text, as typed.
        ranges: The parts to measure, as ``(start, end)`` positions in ``text``,
            instead of its words (runs of characters between spaces). For example
            ``[(0, 3)]`` for the first three characters, or a verse number.

    Returns:
        One :class:`WordBox` per word (or range) that has ink, in the order of the
        text: reading order, whatever the direction. Words with nothing to draw, such
        as a lone space range, are left out.
    """
    text = with_digits(text, digits)
    if ranges is None:
        spans = [(match.start(), match.end()) for match in _WORD.finditer(text)]
    else:
        spans = []
        for start, end in ranges:
            if not 0 <= start <= end <= len(text):
                raise ValueError(
                    f"a range needs 0 <= start <= end <= {len(text)}, got {start}, {end}"
                )
            spans.append((start, end))
    if not spans:
        return []
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
        stroke_width=0,
        fallback_fonts=fallback_fonts,
        spans=[(start, end, number) for number, (start, end) in enumerate(spans, start=1)],
    )
    if placed is None:
        return []
    block, (x, y) = placed
    if block.parts is None:
        return []
    found = {}
    for number, mask, left, top in block.parts:
        if number:
            corner_x, corner_y = x + left - block.left, y + top - block.top
            found[number] = (
                mask,
                (corner_x, corner_y, corner_x + mask.width, corner_y + mask.height),
            )
    words = []
    for number, (start, end) in enumerate(spans, start=1):
        if number in found:
            mask, box = found[number]
            words.append(WordBox(text[start:end], start, end, box, mask))
    return words
