"""Spans: parts of the text drawn in their own colour, shaped with the rest."""

from __future__ import annotations

import random
import unicodedata
import warnings

import pytest
from bidi import get_display
from PIL import Image, ImageChops

import khatt
from khatt.fonts import font_path
from khatt.shaping import _logical_order, shape

BASMALA = "بسم الله الرحمن الرحيم"
GOLD = (218, 165, 32)


def _canvas(width: int = 900, height: int = 140) -> Image.Image:
    return Image.new("RGB", (width, height), "white")


def _draw(text: str, spans=(), **kwargs) -> Image.Image:
    image = _canvas(kwargs.pop("width", 900), kwargs.pop("height", 140))
    kwargs.setdefault("size_px", 64)
    anchor = kwargs.pop("anchor", "ra")
    x = image.width - 20 if anchor[0] == "r" else 20
    return khatt.draw_text(image, (x, 20), text, anchor=anchor, spans=spans, **kwargs)


def _pixels(image: Image.Image) -> list[tuple[int, ...]]:
    data, bands = image.tobytes(), len(image.getbands())
    return [tuple(data[i : i + bands]) for i in range(0, len(data), bands)]


def _colored(image: Image.Image, color: tuple[int, int, int]) -> tuple[int, int, int, int] | None:
    """Box of the pixels exactly ``color``."""
    mask = Image.new("L", image.size, 0)
    mask.putdata([255 if pixel == color else 0 for pixel in _pixels(image)])
    return mask.getbbox()


def _inked(image: Image.Image) -> list[bool]:
    return [pixel != (255, 255, 255) for pixel in _pixels(image)]


def _word(text: str, word: str) -> tuple[int, int]:
    start = text.index(word)
    return start, start + len(word)


class TestLogicalOrder:
    @pytest.mark.parametrize(
        "text",
        [
            BASMALA,
            "abc مرحبا (12) def",
            "(مرحبا)",
            "العدد 123 و 456 فقط  ",
            "Hello مرحبا 3.14 world!",
            "price ٣٤٥ ريال (approx)",
            "😀 مرحبا 😀",
            "9‌",
        ],
    )
    @pytest.mark.parametrize("direction", [None, "ltr", "rtl"])
    def test_matches_python_bidi(self, text: str, direction: str | None) -> None:
        order = _logical_order(text, direction)
        assert order is not None
        assert sorted(order) == list(range(len(text)))
        base = {None: None, "ltr": "L", "rtl": "R"}[direction]
        shown = get_display(text, base_dir=base)
        for ch, i in zip(shown, order, strict=True):
            assert ch == text[i] or unicodedata.mirrored(ch)

    def test_random_mixed_text(self) -> None:
        pool = [*"مرحبالعسيكةأإآى", *"abcXYZ", *"0123456789٠١٢٣", *" ()[].,:;!?-+/%$#'"]
        pool += ["َ", "ّ", "‍", "‌", "ـ", " ", "😀"]
        chooser = random.Random(5)
        for _ in range(1500):
            text = "".join(chooser.choice(pool) for _ in range(chooser.randint(1, 25)))
            for direction in (None, "ltr", "rtl"):
                assert _logical_order(text, direction) is not None, (text, direction)

    def test_empty(self) -> None:
        assert _logical_order("") == []


class TestGlyphIndex:
    def test_every_character_once(self) -> None:
        glyphs = shape(BASMALA, font_path("amiri"), keep_tashkeel=True, track=True)
        assert sorted(g.index for g in glyphs) == list(range(len(BASMALA)))

    def test_untracked_by_default(self) -> None:
        assert {g.index for g in shape(BASMALA, font_path("amiri"))} == {-1}

    def test_stripped_tashkeel_keeps_positions(self) -> None:
        text = "مَرْحَبًا بِكُمْ"
        glyphs = shape(text, font_path("amiri"), keep_tashkeel=False, track=True)
        indices = sorted(g.index for g in glyphs)
        assert indices == [i for i, ch in enumerate(text) if not unicodedata.combining(ch)]


class TestDrawText:
    def test_same_colour_draws_the_same(self) -> None:
        plain = _draw(BASMALA)
        spanned = _draw(BASMALA, spans=[(4, 8, "black")])
        assert plain.tobytes() == spanned.tobytes()

    def test_layout_unchanged(self) -> None:
        plain = _draw(BASMALA)
        spanned = _draw(BASMALA, spans=[(9, 15, "red")])
        ink = ImageChops.invert(plain.convert("L")).getbbox()
        assert ImageChops.invert(spanned.convert("L")).getbbox() == ink
        # The shapes only change colour: the same pixels are inked.
        moved = sum(a != b for a, b in zip(_inked(plain), _inked(spanned), strict=True))
        assert moved == 0

    def test_highlights_the_right_word(self) -> None:
        image = _draw(BASMALA, spans=[(*_word(BASMALA, "الله"), GOLD)])
        box = _colored(image, GOLD)
        assert box is not None
        # Right to left: the second word sits right of the middle, left of the first.
        first = _colored(_draw(BASMALA, spans=[(*_word(BASMALA, "بسم"), GOLD)]), GOLD)
        assert first is not None
        assert box[2] <= first[0] + 4
        assert box[0] > image.width // 2

    def test_joins_kept(self) -> None:
        # A span inside a word: its letters stay in their joined (medial) forms.
        word = "الرحمن"
        start = BASMALA.index(word)
        whole = _draw(BASMALA)
        part = _draw(BASMALA, spans=[(start + 2, start + 4, GOLD)])
        assert _inked(whole) == _inked(part)
        assert _colored(part, GOLD) is not None

    def test_mixed_direction(self) -> None:
        text = "abc مرحبا def"
        image = _draw(text, spans=[(*_word(text, "مرحبا"), GOLD)], anchor="la", width=700)
        box = _colored(image, GOLD)
        latin = _colored(_draw(text, spans=[(0, 3, GOLD)], anchor="la", width=700), GOLD)
        end = _colored(_draw(text, spans=[(10, 13, GOLD)], anchor="la", width=700), GOLD)
        assert box is not None and latin is not None and end is not None
        assert latin[2] <= box[0] + 2 and box[2] <= end[0] + 2

    def test_wrapped_lines(self) -> None:
        text = "كلمة أولى ثم كلمة ثانية بعدها كلمات كثيرة أخيرة"
        start, end = _word(text, "أخيرة")
        image = _draw(text, spans=[(start, end, GOLD)], max_width=300, height=400, size_px=48)
        box = _colored(image, GOLD)
        assert box is not None
        assert box[1] > 60  # not on the first line

    def test_line_breaks(self) -> None:
        text = "سطر أول\nسطر ثان"
        start, end = _word(text, "ثان")
        image = _draw(text, spans=[(start, end, GOLD)], height=260, size_px=48)
        box = _colored(image, GOLD)
        assert box is not None and box[1] > 80

    def test_stripped_tashkeel(self) -> None:
        text = "مَرْحَبًا بِكُمْ"
        start, end = _word(text, "بِكُمْ")
        second = _colored(_draw(text, spans=[(start, end, GOLD)], keep_tashkeel=False), GOLD)
        first = _colored(_draw(text, spans=[(0, start - 1, GOLD)], keep_tashkeel=False), GOLD)
        assert second is not None and first is not None
        assert second[2] <= first[0] + 2  # right to left: the second word is on the left

    def test_overlap_later_wins(self) -> None:
        image = _draw(BASMALA, spans=[(0, 22, "red"), (*_word(BASMALA, "الله"), GOLD)])
        assert _colored(image, GOLD) is not None
        assert _colored(image, (255, 0, 0)) is not None

    def test_span_class_and_rgba(self) -> None:
        image = Image.new("RGBA", (700, 120), (0, 0, 0, 0))
        khatt.draw_text(image, (20, 20), BASMALA, size_px=48, spans=[khatt.Span(0, 3, GOLD)])
        assert any(pixel[:3] == GOLD and pixel[3] == 255 for pixel in _pixels(image))

    def test_with_outline(self) -> None:
        image = _draw(BASMALA, spans=[(0, 3, GOLD)], stroke_width=3, stroke_fill="black")
        assert _colored(image, GOLD) is not None
        assert _colored(image, (0, 0, 0)) is not None

    def test_past_the_end_is_fine(self) -> None:
        assert _colored(_draw("خط", spans=[(0, 99, GOLD)]), GOLD) is not None

    @pytest.mark.parametrize(
        ("span", "message"),
        [
            ((3, 1, "red"), "start <= end"),
            ((-1, 2, "red"), "start <= end"),
            ((0.5, 2, "red"), "whole numbers"),
            ((0, 2), "Span or a"),
            ("abc", "Span or a"),
        ],
    )
    def test_bad_spans(self, span, message: str) -> None:
        with pytest.raises(ValueError, match=message):
            _draw(BASMALA, spans=[span])

    def test_bad_colour(self) -> None:
        with pytest.raises(ValueError):
            _draw(BASMALA, spans=[(0, 3, "not-a-colour")])

    def test_not_with_an_effect(self) -> None:
        with pytest.raises(ValueError, match="effect"):
            _draw(BASMALA, spans=[(0, 3, "red")], effect="gold")


class TestCaptionImage:
    def test_highlight(self) -> None:
        image = khatt.caption_image(
            BASMALA, font_size=60, color="white", spans=[(*_word(BASMALA, "الرحمن"), GOLD)]
        )
        assert any(pixel[:3] == GOLD for pixel in _pixels(image))

    def test_same_size_as_without(self) -> None:
        plain = khatt.caption_image(BASMALA, font_size=60)
        spanned = khatt.caption_image(BASMALA, font_size=60, spans=[(0, 3, "red")])
        assert plain.size == spanned.size


def test_no_warnings_for_plain_text() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        _draw(BASMALA, spans=[(0, 3, GOLD)])


class TestFallbacks:
    def test_tab_takes_the_paragraph_level(self) -> None:
        assert _logical_order("abc \tمرحبا ", "rtl") is not None

    def test_unreadable_levels(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("khatt.shaping.get_display", lambda text, **kwargs: "no levels here")
        assert _logical_order(BASMALA) is None

    def test_levels_of_the_wrong_length(self, monkeypatch: pytest.MonkeyPatch) -> None:
        info = "levels: [ Level(1) ], paragraphs: [ ParagraphInfo { level: Level(1) } ]"
        monkeypatch.setattr("khatt.shaping.get_display", lambda text, **kwargs: info)
        assert _logical_order(BASMALA) is None

    def test_order_that_does_not_match(self, monkeypatch: pytest.MonkeyPatch) -> None:
        real = get_display
        monkeypatch.setattr(
            "khatt.shaping.get_display",
            lambda text, **kwargs: real(text, **kwargs) if kwargs.get("debug") else "x" * len(text),
        )
        assert _logical_order(BASMALA) is None

    def test_draws_in_the_main_colour_with_a_warning(self, monkeypatch: pytest.MonkeyPatch) -> None:
        plain = _draw(BASMALA)
        monkeypatch.setattr("khatt.shaping._logical_order", lambda text, direction=None: None)
        with pytest.warns(UserWarning, match="spans are drawn in the main colour"):
            spanned = _draw(BASMALA, spans=[(0, 3, GOLD)])
        assert spanned.tobytes() == plain.tobytes()
