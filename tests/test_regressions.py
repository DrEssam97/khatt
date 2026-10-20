"""Arabic-script regressions, checked against HarfBuzz itself.

The reference for where ink belongs is HarfBuzz's own output: its glyph
positions plus each glyph's extents, as ``hb-view`` would draw them. khatt
shapes with HarfBuzz too, but rasterizes and lays out on its own, which is
where marks have gone wrong in other projects (``بِتَ`` with its kasra drawn
far below the letter, for one).
"""

from __future__ import annotations

import math
import warnings

import pytest
import uharfbuzz as hb
from PIL import Image

import khatt
from khatt.fonts import font_path
from khatt.raster import _place
from khatt.shaping import shape, variations

Box = tuple[int, int, int, int]

FATIHA = """بِسْمِ ٱللَّهِ ٱلرَّحْمَٰنِ ٱلرَّحِيمِ
ٱلْحَمْدُ لِلَّهِ رَبِّ ٱلْعَٰلَمِينَ
ٱلرَّحْمَٰنِ ٱلرَّحِيمِ
مَٰلِكِ يَوْمِ ٱلدِّينِ
إِيَّاكَ نَعْبُدُ وَإِيَّاكَ نَسْتَعِينُ
ٱهْدِنَا ٱلصِّرَٰطَ ٱلْمُسْتَقِيمَ
صِرَٰطَ ٱلَّذِينَ أَنْعَمْتَ عَلَيْهِمْ غَيْرِ ٱلْمَغْضُوبِ عَلَيْهِمْ وَلَا ٱلضَّآلِّينَ"""

# Quranic pause and recitation marks (U+06D6-U+06ED).
QURANIC_MARKS = "ۖۗۘۙۚۛۜ۝۞ۡۢۤۥۦ۪ۭ"
PERSIAN = "پ چ ژ گ ک ی"
URDU = "ٹ ڈ ڑ ں ے ھ ہ ۂ ۓ ۃ"


def harfbuzz_boxes(text: str, font: str, size: int) -> list[tuple[int, Box]]:
    """``(cluster, ink box)`` of each glyph as HarfBuzz places it, in 1/64 px.

    x grows rightwards from the pen origin, y downwards from the baseline.
    """
    path = font_path(font)
    hb_font = hb.Font(hb.Face(hb.Blob.from_file_path(str(path))))
    if settings := variations(path):
        hb_font.set_variations(settings)
    hb_font.scale = (size * 64, size * 64)
    buffer = hb.Buffer()
    buffer.add_str(text)
    buffer.guess_segment_properties()
    buffer.cluster_level = hb.BufferClusterLevel.MONOTONE_CHARACTERS
    hb.shape(hb_font, buffer, None)
    boxes = []
    pen = 0
    for info, position in zip(buffer.glyph_infos, buffer.glyph_positions, strict=True):
        extents = hb_font.get_glyph_extents(info.codepoint)
        if extents is not None and extents.width and extents.height:
            left = pen + position.x_offset + extents.x_bearing
            top = -(position.y_offset + extents.y_bearing)
            boxes.append((info.cluster, (left, top, left + extents.width, top - extents.height)))
        pen += position.x_advance
    return boxes


def to_pixels(boxes: list[Box]) -> Box:
    """The union of ``boxes`` (1/64 px), widened to whole pixels."""
    return (
        math.floor(min(b[0] for b in boxes) / 64),
        math.floor(min(b[1] for b in boxes) / 64),
        math.ceil(max(b[2] for b in boxes) / 64),
        math.ceil(max(b[3] for b in boxes) / 64),
    )


def assert_close(ours: Box, reference: Box, tolerance: int) -> None:
    assert all(abs(a - b) <= tolerance for a, b in zip(ours, reference, strict=True)), (
        ours,
        reference,
    )


def word_box(text: str, font: str, size: int) -> Box:
    """khatt's ink box: x from the ink's left edge, y from the baseline."""
    return khatt.text_bbox(text, font=font, size_px=size, anchor="ls")


def harfbuzz_word_box(text: str, font: str, size: int) -> Box:
    left, top, right, bottom = to_pixels([box for _, box in harfbuzz_boxes(text, font, size)])
    return 0, top, right - left, bottom


class TestMarkPlacement:
    """The ``بِتَ`` case from moviepy/MoneyPrinterTurbo reviews: kasra and fatha."""

    TEXT = "بِتَ"

    @pytest.mark.parametrize("font", ["amiri", "noto-naskh", "cairo", "rubik"])
    @pytest.mark.parametrize("size", [24, 48, 96])
    def test_every_glyph_sits_where_harfbuzz_puts_it(self, font: str, size: int) -> None:
        # Each rendered glyph, base letters and marks alike, against
        # HarfBuzz's position plus that glyph's extents.
        path = font_path(font)
        placed = _place(shape(self.TEXT, path, keep_tashkeel=True), str(path), size, True)
        reference = harfbuzz_boxes(self.TEXT, font, size)
        assert len(placed) == len(reference) >= 4  # two letters, two marks
        for glyph, (_, box) in zip(placed, reference, strict=True):
            ink = glyph.image.getbbox()
            assert ink is not None
            ours = (glyph.x + ink[0], glyph.y + ink[1], glyph.x + ink[2], glyph.y + ink[3])
            assert_close(ours, to_pixels([box]), tolerance=1)

    @pytest.mark.parametrize("font", ["amiri", "noto-naskh", "cairo", "rubik"])
    def test_the_kasra_adds_only_its_own_depth(self, font: str) -> None:
        # In the broken renders the box grew by tens of pixels below the
        # letter; here it grows exactly as HarfBuzz's kasra does.
        size = 96
        ours = word_box(self.TEXT, font, size)[3] - word_box("بتَ", font, size)[3]
        theirs = (
            harfbuzz_word_box(self.TEXT, font, size)[3] - harfbuzz_word_box("بتَ", font, size)[3]
        )
        assert abs(ours - theirs) <= 1


class TestAgainstHarfBuzz:
    @pytest.mark.parametrize("font", ["amiri", "noto-naskh"])
    @pytest.mark.parametrize("size", [24, 48])
    @pytest.mark.parametrize("verse", FATIHA.splitlines())
    def test_vocalized_quran(self, font: str, size: int, verse: str) -> None:
        assert_close(word_box(verse, font, size), harfbuzz_word_box(verse, font, size), 2)

    @pytest.mark.parametrize("font", ["amiri", "noto-naskh", "cairo", "rubik"])
    @pytest.mark.parametrize("text", ["پیچ‌وتاب ژرف گوشه کتاب", "خداحافظ دوستان گرامی"])
    def test_persian(self, font: str, text: str) -> None:
        assert_close(word_box(text, font, 48), harfbuzz_word_box(text, font, 48), 2)

    @pytest.mark.parametrize("font", ["amiri", "noto-naskh", "cairo"])
    @pytest.mark.parametrize("text", ["پاکستان ٹیکسی ڈاکٹر", "بڑے گھر میں ہم سب"])
    def test_urdu(self, font: str, text: str) -> None:
        assert_close(word_box(text, font, 48), harfbuzz_word_box(text, font, 48), 2)


class TestQuranText:
    @pytest.mark.parametrize("font", ["amiri", "noto-naskh"])
    def test_fonts_for_quran_text_cover_it_all(self, font: str) -> None:
        marks = "ب" + "ب".join(QURANIC_MARKS)
        assert khatt.missing_characters(FATIHA, font) == []
        assert khatt.missing_characters(marks, font) == []

    def test_fonts_without_the_pause_marks(self) -> None:
        # Documented gaps: Cairo and Rubik vocalize fully but lack the marks.
        marks = "ب" + "ب".join(QURANIC_MARKS)
        for font in ("cairo", "rubik"):
            assert khatt.missing_characters(FATIHA, font) == []
            assert khatt.missing_characters(marks, font) == list(QURANIC_MARKS)

    def test_the_whole_surah_fits_a_box_without_warnings(self) -> None:
        image = Image.new("RGB", (900, 700), "white")
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            khatt.overlay(image, FATIHA, (40, 40, 860, 660), padding=10)
        assert image.getbbox() is not None


class TestPersianAndUrduLetters:
    def test_every_bundled_font_covers_persian(self) -> None:
        for font in khatt.list_fonts():
            assert khatt.missing_characters(PERSIAN, font) == [], font

    def test_urdu_coverage(self) -> None:
        for font in ("amiri", "noto-naskh", "cairo"):
            assert khatt.missing_characters(URDU, font) == [], font
        # Rubik has the noon ghunna (ں) but none of the other Urdu letters.
        assert khatt.missing_characters(URDU, "rubik") == [c for c in URDU.split() if c != "ں"]

    @staticmethod
    def letter_glyphs(text: str, font: str, index: int) -> list[int]:
        """The glyphs drawn for the character at ``index`` (a letter may be
        a skeleton plus separate dots, as in Amiri and Noto)."""
        return [g.gid for g in shape(text, font_path(font)) if g.cluster == index]

    @pytest.mark.parametrize("font", ["amiri", "noto-naskh", "cairo"])
    @pytest.mark.parametrize("letter", ["پ", "چ", "گ", "ک", "ی", "ٹ", "ں", "ھ", "ہ"])
    def test_dual_joining_letters_join_on_both_sides(self, font: str, letter: str) -> None:
        # A tatweel on each side forces the medial form.
        isolated = self.letter_glyphs(letter, font, 0)
        assert isolated
        assert self.letter_glyphs(f"ـ{letter}ـ", font, 1) != isolated

    @pytest.mark.parametrize("font", ["amiri", "noto-naskh", "cairo"])
    @pytest.mark.parametrize("letter", ["ژ", "ڈ", "ڑ", "ے"])
    def test_right_joining_letters_take_their_final_form(self, font: str, letter: str) -> None:
        isolated = self.letter_glyphs(letter, font, 0)
        assert isolated
        assert self.letter_glyphs(f"ـ{letter}", font, 1) != isolated
