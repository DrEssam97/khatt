"""digits="arabic-indic": numbers drawn in Arabic-Indic digits."""

from __future__ import annotations

import pytest
from cli_runner import invoke
from PIL import Image, ImageChops

import khatt
from khatt.cli import main
from khatt.digits import with_digits

PRICE = "السعر 1,250.5 ريال وخصم 15%"
PRICE_ARABIC_INDIC = "السعر ١٬٢٥٠٫٥ ريال وخصم ١٥٪"


class TestArabicDigits:
    def test_digits_and_separators_in_numbers(self) -> None:
        assert khatt.arabic_digits(PRICE) == PRICE_ARABIC_INDIC
        assert khatt.arabic_digits("0123456789") == "٠١٢٣٤٥٦٧٨٩"

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("نهاية الجملة 5.", "نهاية الجملة ٥."),
            ("1، 2، 3", "١، ٢، ٣"),
            ("a,b. c%", "a,b. c%"),
            ("5 %", "٥ %"),
            ("بدون أرقام", "بدون أرقام"),
        ],
    )
    def test_punctuation_outside_numbers_stays(self, text: str, expected: str) -> None:
        assert khatt.arabic_digits(text) == expected

    def test_positions_stay(self) -> None:
        # One character for one, so spans and word ranges keep pointing at the same text.
        assert len(khatt.arabic_digits(PRICE)) == len(PRICE)

    def test_converting_twice_changes_nothing(self) -> None:
        assert khatt.arabic_digits(PRICE_ARABIC_INDIC) == PRICE_ARABIC_INDIC

    def test_with_digits(self) -> None:
        assert with_digits(PRICE, None) == PRICE
        assert with_digits(PRICE, "arabic-indic") == PRICE_ARABIC_INDIC
        with pytest.raises(ValueError, match="digits must be"):
            with_digits(PRICE, "eastern")


def same(a: Image.Image, b: Image.Image) -> bool:
    return a.size == b.size and ImageChops.difference(a, b).getbbox() is None


class TestDrawing:
    def test_draw_text(self) -> None:
        drawn = khatt.draw_text(
            Image.new("RGB", (600, 80), "white"), (10, 10), PRICE, digits="arabic-indic"
        )
        typed = khatt.draw_text(Image.new("RGB", (600, 80), "white"), (10, 10), PRICE_ARABIC_INDIC)
        assert same(drawn, typed)
        plain = khatt.draw_text(Image.new("RGB", (600, 80), "white"), (10, 10), PRICE)
        assert not same(drawn, plain)

    def test_text_bbox(self) -> None:
        assert khatt.text_bbox(PRICE, digits="arabic-indic") == khatt.text_bbox(PRICE_ARABIC_INDIC)

    def test_overlay(self) -> None:
        def boxed(text: str, **options: str) -> Image.Image:
            image = Image.new("RGB", (400, 120), "white")
            return khatt.overlay(image, text, box=(0, 0, 400, 120), **options)

        assert same(boxed(PRICE, digits="arabic-indic"), boxed(PRICE_ARABIC_INDIC))

    def test_word_art(self) -> None:
        drawn = khatt.word_art("2026", size_px=60, digits="arabic-indic")
        typed = khatt.word_art("٢٠٢٦", size_px=60)
        assert drawn is not None and typed is not None
        assert same(drawn, typed)

    def test_caption_image(self) -> None:
        drawn = khatt.caption_image(PRICE, font_size=30, digits="arabic-indic")
        assert same(drawn, khatt.caption_image(PRICE_ARABIC_INDIC, font_size=30))

    def test_render_svg(self) -> None:
        assert khatt.render_svg(PRICE, digits="arabic-indic") == khatt.render_svg(
            PRICE_ARABIC_INDIC
        )

    def test_word_boxes(self) -> None:
        boxes = khatt.word_boxes(PRICE, digits="arabic-indic")
        assert [box.text for box in boxes] == PRICE_ARABIC_INDIC.split()

    def test_put_text(self) -> None:
        np = pytest.importorskip("numpy")
        drawn = khatt.put_text(
            np.zeros((80, 600, 3), np.uint8), PRICE, (10, 50), digits="arabic-indic"
        )
        typed = khatt.put_text(np.zeros((80, 600, 3), np.uint8), PRICE_ARABIC_INDIC, (10, 50))
        assert (drawn == typed).all()

    def test_text_clip(self) -> None:
        pytest.importorskip("moviepy")
        from khatt.video import TextClip

        clip = TextClip(text="2026", font_size=40, digits="arabic-indic")
        typed = TextClip(text="٢٠٢٦", font_size=40)
        assert (clip.get_frame(0) == typed.get_frame(0)).all()


class TestCommand:
    def test_arabic_digits_flag(self) -> None:
        converted = invoke(main, ["رقم 150", "--arabic-digits", "--size", "6"])
        typed = invoke(main, ["رقم ١٥٠", "--size", "6"])
        assert converted.exit_code == 0
        assert converted.output == typed.output

    def test_from_stdin(self) -> None:
        converted = invoke(main, ["--arabic-digits", "--size", "6"], input="150\n")
        typed = invoke(main, ["١٥٠", "--size", "6"])
        assert converted.output == typed.output
