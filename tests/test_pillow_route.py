"""khatt.pillow: Pillow's text calls with Arabic drawn by khatt."""

from __future__ import annotations

import pytest
from PIL import Image, ImageDraw, ImageFont

import khatt
from khatt.pillow import _ORIGINALS
from khatt.terminal import for_terminal

ARABIC = "مرحبا بالعالم"
FONT = ImageFont.truetype(str(khatt.font_path("noto-naskh")), 32)


def canvas(mode: str = "RGB") -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new(mode, (360, 80), "white" if mode in ("RGB", "RGBA") else 255)
    return image, ImageDraw.Draw(image)


def reshaped(text: str) -> str:
    """``text`` as arabic_reshaper and get_display leave it."""
    return for_terminal(text, shaped_by_terminal=False)


class TestText:
    def test_arabic_matches_khatt(self) -> None:
        image, draw = canvas()
        khatt.pillow.text(draw, (10, 10), ARABIC, fill="black", font=FONT)
        expected = Image.new("RGB", (360, 80), "white")
        khatt.draw_text(
            expected,
            (10, 10),
            ARABIC,
            font=str(khatt.font_path("noto-naskh")),
            size_px=32,
            fill="black",
            fallback_fonts=[khatt.font_path("noto-naskh")],
        )
        assert image.tobytes() == expected.tobytes()

    def test_latin_goes_to_pillow(self) -> None:
        image, draw = canvas()
        khatt.pillow.text(draw, (10, 10), "Hello 2026", fill="black", font=FONT)
        expected, plain = canvas()
        plain.text((10, 10), "Hello 2026", fill="black", font=FONT)
        assert image.tobytes() == expected.tobytes()

    def test_reshaped_text_is_drawn_as_typed(self) -> None:
        typed, draw = canvas()
        khatt.pillow.text(draw, (10, 10), ARABIC, fill="black", font=FONT)
        repaired, draw = canvas()
        khatt.pillow.text(draw, (10, 10), reshaped(ARABIC), fill="black", font=FONT)
        assert repaired.tobytes() == typed.tobytes()

    @pytest.mark.parametrize(("mode", "fill"), [("L", 0), ("LA", (0, 255))])
    def test_grayscale(self, mode: str, fill: object) -> None:
        image, draw = canvas(mode)
        khatt.pillow.text(draw, (10, 10), ARABIC, fill=fill, font=FONT)
        colour, draw = canvas()
        khatt.pillow.text(draw, (10, 10), ARABIC, fill="black", font=FONT)
        assert image.getchannel("L").tobytes() == colour.convert("L").tobytes()

    def test_other_modes_go_to_pillow(self) -> None:
        image = Image.new("1", (360, 80), 1)
        khatt.pillow.text(ImageDraw.Draw(image), (10, 10), ARABIC, fill=0, font=FONT)
        expected = Image.new("1", (360, 80), 1)
        ImageDraw.Draw(expected).text((10, 10), ARABIC, fill=0, font=FONT)
        assert image.tobytes() == expected.tobytes()

    def test_default_font_and_size(self) -> None:
        image, draw = canvas()
        khatt.pillow.text(draw, (10, 10), ARABIC, fill="black", font_size=24)
        assert image.convert("L").getextrema()[0] < 128

    def test_stroke(self) -> None:
        image, draw = canvas()
        khatt.pillow.text(
            draw, (10, 10), ARABIC, fill="white", font=FONT, stroke_width=2, stroke_fill="red"
        )
        assert (255, 0, 0) in {colour for _, colour in image.getcolors(1 << 16) or []}


class TestMeasuring:
    def test_textbbox(self) -> None:
        _, draw = canvas()
        assert khatt.pillow.textbbox(draw, (5, 5), ARABIC, font=FONT) == khatt.text_bbox(
            ARABIC,
            xy=(5, 5),
            font=str(khatt.font_path("noto-naskh")),
            size_px=32,
            fallback_fonts=[khatt.font_path("noto-naskh")],
        )
        assert khatt.pillow.textbbox(draw, (5, 5), "Hello", font=FONT) == draw.textbbox(
            (5, 5), "Hello", font=FONT
        )

    def test_textlength(self) -> None:
        _, draw = canvas()
        left, _, right, _ = khatt.pillow.textbbox(draw, (0, 0), ARABIC, anchor="ls", font=FONT)
        assert khatt.pillow.textlength(draw, ARABIC, font=FONT) == right - left
        assert khatt.pillow.textlength(draw, "Hello", font=FONT) == draw.textlength(
            "Hello", font=FONT
        )


class TestRouting:
    @staticmethod
    def library_card(name: str) -> Image.Image:
        """A stand-in for a library that measures and draws with Pillow."""
        image = Image.new("RGB", (360, 80), "white")
        draw = ImageDraw.Draw(image)
        width = draw.textlength(name, font=FONT)
        draw.text((350 - width, 10), name, fill="black", font=FONT)
        left, _, right, _ = FONT.getbbox(name)
        draw.rectangle((350 - width, 60, 350 - width + right - left, 62), fill="black")
        return image

    def test_library_calls_are_routed(self) -> None:
        with khatt.pillow.routing():
            routed = self.library_card(ARABIC)
        direct, draw = canvas()
        width = khatt.pillow.textlength(draw, ARABIC, font=FONT)
        khatt.pillow.text(draw, (350 - width, 10), ARABIC, fill="black", font=FONT)
        assert routed.crop((0, 0, 360, 59)).tobytes() == direct.crop((0, 0, 360, 59)).tobytes()

    def test_latin_is_unchanged_inside(self) -> None:
        before = self.library_card("Hello")
        with khatt.pillow.routing():
            inside = self.library_card("Hello")
        assert inside.tobytes() == before.tobytes()

    def test_restored_after_the_block_and_after_errors(self) -> None:
        with pytest.raises(RuntimeError), khatt.pillow.routing():
            assert ImageDraw.ImageDraw.text is not _ORIGINALS["text"]
            raise RuntimeError("boom")
        assert ImageDraw.ImageDraw.text is _ORIGINALS["text"]
        assert ImageDraw.ImageDraw.textbbox is _ORIGINALS["textbbox"]
        assert ImageFont.FreeTypeFont.getbbox is _ORIGINALS["getbbox"]

    def test_multiline(self) -> None:
        text = "سطر أول\nسطر ثاني"
        with khatt.pillow.routing():
            image, draw = canvas()
            draw.multiline_text((10, 5), text, fill="black", font=FONT, spacing=2)
            box = draw.multiline_textbbox((10, 5), text, font=FONT, spacing=2)
        assert box == khatt.pillow.textbbox(draw, (10, 5), text, font=FONT, spacing=2)
        assert image.convert("L").getextrema()[0] < 128
