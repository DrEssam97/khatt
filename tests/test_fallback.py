"""Fallback fonts: characters the font has no glyph for come from the next font that has one.

Amiri covers Arabic and Latin but not Hebrew or Cyrillic; Rubik covers all
four, so it serves as the fallback.
"""

from __future__ import annotations

import warnings

import pytest
from PIL import Image

import khatt
from khatt.fonts import font_path, font_paths
from khatt.shaping import UnsupportedCharacterWarning, shape

AMIRI = font_path("amiri")
RUBIK = font_path("rubik")
WHITE = (255, 255, 255)


def fonts_used(text: str) -> list[str | None]:
    return [glyph.font for glyph in shape(text, AMIRI, fallback_fonts=[RUBIK], keep_tashkeel=True)]


def drawn(text: str, **kwargs: object) -> Image.Image:
    image = Image.new("RGB", (900, 200), WHITE)
    with warnings.catch_warnings():
        warnings.simplefilter("error", UnsupportedCharacterWarning)
        return khatt.draw_text(image, (20, 120), text, size_px=60, anchor="ls", **kwargs)


class TestShaping:
    def test_text_the_font_covers_shapes_exactly_as_without_fallbacks(self) -> None:
        text = "مرحبا بالعالم Hello 2026"
        assert shape(text, AMIRI, fallback_fonts=[RUBIK]) == shape(text, AMIRI)

    def test_glyphs_from_a_fallback_name_their_font(self) -> None:
        assert set(fonts_used("مرحبا Жук")) == {None, str(RUBIK)}
        assert set(fonts_used("Жук")) == {str(RUBIK)}

    def test_right_to_left_runs_in_different_fonts_keep_visual_order(self) -> None:
        # Arabic then Hebrew, both right to left: Hebrew is on the left.
        glyphs = shape("مرحبا שלום", AMIRI, fallback_fonts=[RUBIK])
        fonts = [glyph.font for glyph in glyphs]
        assert fonts[:4] == [str(RUBIK)] * 4
        assert fonts[-1] is None
        # Visual order left to right is the logical order reversed: ם is first.
        assert [glyph.cluster for glyph in glyphs[:4]] == [9, 8, 7, 6]

    def test_a_mark_stays_in_its_base_letter_font(self) -> None:
        # U+0301 after a Cyrillic letter is shaped with Rubik, like the letter.
        assert fonts_used("Жу́к") == [str(RUBIK)] * len(fonts_used("Жу́к"))

    def test_spaces_and_punctuation_stay_with_the_text_before_them(self) -> None:
        assert fonts_used("Жук, Жук") == [str(RUBIK)] * len(fonts_used("Жук, Жук"))

    def test_characters_no_font_has_are_still_reported(self) -> None:
        with pytest.warns(UnsupportedCharacterWarning, match="U\\+2713"):
            shape("Жук ✓", AMIRI, fallback_fonts=[RUBIK])


class TestMissingCharacters:
    def test_only_characters_no_font_has_are_missing(self) -> None:
        text = "مرحبا שלום Жук ✓"
        assert khatt.missing_characters(text, "amiri") == list("שלוםЖук✓")
        assert khatt.missing_characters(text, "amiri", fallback_fonts=["rubik"]) == ["✓"]

    def test_a_single_fallback_font_needs_no_list(self) -> None:
        assert khatt.missing_characters("Жук", "amiri", fallback_fonts="rubik") == []
        assert font_paths("rubik") == (RUBIK,)


class TestDrawing:
    def test_fallback_glyphs_draw_as_in_their_own_font(self) -> None:
        # On the same baseline, Cyrillic drawn through the fallback matches
        # Cyrillic drawn with Rubik itself.
        assert drawn("Жук", font="amiri", fallback_fonts=["rubik"]).tobytes() == (
            drawn("Жук", font="rubik").tobytes()
        )

    def test_mixed_text_keeps_every_script(self) -> None:
        # In this right-to-left line the Cyrillic word comes first from the
        # left, so its ink is exactly Rubik's "Жук" drawn on its own.
        mixed = drawn("مرحبا Жук", font="amiri", fallback_fonts=["rubik"])
        cyrillic = drawn("Жук", font="rubik")
        box = Image.eval(cyrillic.convert("L"), lambda value: 255 - value).getbbox()
        assert box is not None
        assert mixed.crop(box).tobytes() == cyrillic.crop(box).tobytes()
        # And the Arabic word follows it on the right.
        assert mixed.crop((box[2] + 10, 0, 900, 200)).convert("L").getextrema()[0] < 128

    def test_text_bbox_matches_the_drawn_ink(self) -> None:
        text = "مرحبا שלום Жук"
        image = drawn(text, font="amiri", fallback_fonts=["rubik"])
        box = khatt.text_bbox(
            text, xy=(20, 120), font="amiri", size_px=60, anchor="ls", fallback_fonts=["rubik"]
        )
        inverted = Image.eval(image.convert("L"), lambda value: 255 - value)
        assert inverted.getbbox() == box

    def test_caption_image_draws_fallback_characters(self) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("error", UnsupportedCharacterWarning)
            with_fallback = khatt.caption_image(
                "مرحبا Жук", font="amiri", font_size=48, fallback_fonts=["rubik"]
            )
        with pytest.warns(UnsupportedCharacterWarning):
            without = khatt.caption_image("مرحبا Жук", font="amiri", font_size=48)
        assert with_fallback.width > without.width

    def test_render_uses_fallbacks_too(self) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("error", UnsupportedCharacterWarning)
            art = khatt.render("Жук", font="amiri", fallback_fonts=["rubik"], width=None)
            image = khatt.render_image("Жук", font="amiri", fallback_fonts=["rubik"])
        assert art.strip()
        assert image is not None
