"""word_boxes: each word's box and mask, as draw_text draws the text."""

from __future__ import annotations

from typing import Any

import pytest
from PIL import Image, ImageChops

import khatt

TEXT = "بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ"
SIZE = (700, 400)


def drawn(text: str, **options: Any) -> Image.Image:
    """What draw_text paints, white on black, as coverage."""
    image = Image.new("RGB", SIZE, "black")
    khatt.draw_text(image, options.pop("xy", (20, 20)), text, fill="white", **options)
    return image.convert("L")


def union(words: list[khatt.WordBox]) -> Image.Image:
    canvas = Image.new("L", SIZE, 0)
    for word in words:
        region = canvas.crop(word.box)
        canvas.paste(ImageChops.lighter(region, word.mask), word.box[:2])
    return canvas


@pytest.mark.parametrize(
    "options",
    [
        {"size_px": 56},
        {"size_px": 56, "max_width": 260},  # wrapped onto two lines
        {"size_px": 40, "anchor": "mm", "xy": (350, 200), "keep_tashkeel": False},
        {"size_px": 40, "font": "rubik", "text": "Hello wide world"},
    ],
)
def test_masks_together_are_exactly_what_draw_text_paints(options: dict[str, Any]) -> None:
    text = options.pop("text", TEXT)
    xy = options.pop("xy", (20, 20))
    words = khatt.word_boxes(text, xy=xy, **options)
    assert len(words) == len(text.split())
    assert union(words).tobytes() == drawn(text, xy=xy, **options).tobytes()


def test_words_in_reading_order_with_their_positions() -> None:
    words = khatt.word_boxes(TEXT, xy=(20, 20), size_px=56)
    assert [word.text for word in words] == TEXT.split()
    for word in words:
        assert TEXT[word.start : word.end] == word.text
        assert word.mask.size == (word.box[2] - word.box[0], word.box[3] - word.box[1])
        assert word.mask.mode == "L"
    # Arabic reads right to left: the first word is the rightmost.
    lefts = [word.box[0] for word in words]
    assert lefts == sorted(lefts, reverse=True)


def test_boxes_fill_the_text_box() -> None:
    words = khatt.word_boxes(TEXT, xy=(20, 20), size_px=56)
    left = min(word.box[0] for word in words)
    top = min(word.box[1] for word in words)
    right = max(word.box[2] for word in words)
    bottom = max(word.box[3] for word in words)
    assert (left, top, right, bottom) == khatt.text_bbox(TEXT, xy=(20, 20), size_px=56)


def test_wrapped_words_go_to_the_next_line() -> None:
    words = khatt.word_boxes(TEXT, size_px=56, max_width=260)
    first, last = words[0].box, words[-1].box
    assert (last[1] + last[3]) / 2 > (first[1] + first[3]) / 2 + 40  # a line lower


def test_ranges() -> None:
    text = "سورة الفاتحة ١"
    (number,) = khatt.word_boxes(text, ranges=[(13, 14)], size_px=40)
    assert number.text == "١"
    first, *_ = khatt.word_boxes(text, ranges=[(0, 4), (4, 5)], size_px=40)
    assert first.text == "سورة"
    assert len(khatt.word_boxes(text, ranges=[(0, 4), (4, 5)], size_px=40)) == 1  # a space
    with pytest.raises(ValueError, match="range"):
        khatt.word_boxes(text, ranges=[(5, 99)])


@pytest.mark.parametrize("text", ["", "   "])
def test_nothing_to_draw(text: str) -> None:
    assert khatt.word_boxes(text) == []
