"""Quran text: shaped exactly as HarfBuzz shapes it, and highlighted without a change.

The verses come unchanged from the Tanzil Quran Text (Uthmani), see
tests/data/quran-uthmani-sample.txt and https://tanzil.net.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest
import uharfbuzz as hb
from PIL import Image

import khatt
from khatt import Word
from khatt.fonts import font_path
from khatt.shaping import _load_font, shape
from khatt.words import _tokens

SAMPLE = Path(__file__).parent / "data" / "quran-uthmani-sample.txt"


def _verses() -> dict[str, str]:
    verses = {}
    for line in SAMPLE.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            surah, ayah, text = line.split("|", 2)
            verses[f"{surah}:{ayah}"] = text
    return verses


VERSES = _verses()
GOLD = (218, 165, 32)
WHITE = bytes((255, 255, 255))


def test_sample() -> None:
    assert len(VERSES) == 23
    assert VERSES["1:1"].startswith("بِسْمِ")


@pytest.mark.parametrize("font", ["amiri", "noto-naskh"])
def test_every_character_has_a_glyph(font: str) -> None:
    assert not khatt.missing_characters(" ".join(VERSES.values()), font=font)


@pytest.mark.parametrize("font", ["amiri", "noto-naskh"])
@pytest.mark.parametrize("key", sorted(VERSES))
def test_shaped_as_harfbuzz_shapes_the_whole_verse(font: str, key: str) -> None:
    # khatt splits text by direction before shaping; a Quran verse must come
    # out exactly as HarfBuzz shapes it in one piece, joins and marks alike.
    text, path = VERSES[key], str(font_path(font))
    buffer = hb.Buffer()
    buffer.add_str(text)
    buffer.guess_segment_properties()
    buffer.language = "ar"
    hb.shape(_load_font(path), buffer, None)
    expected = [
        (info.codepoint, pos.x_advance, pos.x_offset, pos.y_offset)
        for info, pos in zip(buffer.glyph_infos, buffer.glyph_positions, strict=True)
    ]
    glyphs = shape(text, path, keep_tashkeel=True)
    assert [(g.gid, g.x_advance, g.x_offset, g.y_offset) for g in glyphs] == expected


def _ranges(text: str) -> list[tuple[int, int]]:
    ranges, at = [], 0
    for token in _tokens(text):
        start = text.index(token.split()[0], at)
        end = start + len(token)
        assert text[start:end] == token
        ranges.append((start, end))
        at = end
    return ranges


def _inked(image: Image.Image) -> bytes:
    """Where anything is drawn: every pixel that isn't white."""
    data = image.tobytes()
    return bytes(data[i : i + 3] != WHITE for i in range(0, len(data), 3))


def _draw(text: str, spans=()) -> Image.Image:
    image = Image.new("RGB", (1200, 620), "white")
    khatt.draw_text(
        image,
        (1180, 20),
        text,
        size_px=40,
        anchor="ra",
        max_width=1150,
        line_spacing=2.0,
        spans=spans,
    )
    return image


@pytest.mark.parametrize("key", ["1:7", "2:2", "2:26", "2:255", "112:4"])
def test_highlighting_a_word_changes_only_its_colour(key: str) -> None:
    text = VERSES[key]
    plain = _draw(text)
    shapes = _inked(plain)
    for start, end in _ranges(text):
        lit = _draw(text, spans=[(start, end, GOLD)])
        assert _inked(lit) == shapes
        assert GOLD in {color for _, color in lit.getcolors(1 << 20) or []}


class TestTanzilWithQuranComTimings:
    def test_pause_signs_and_rub_el_hizb(self) -> None:
        assert _tokens(VERSES["2:2"])[3:5] == ["رَيْبَ ۛ", "فِيهِ ۛ"]
        assert _tokens(VERSES["2:26"])[0].startswith("۞ ")
        assert len(_tokens(VERSES["2:2"])) == 7

    def test_basmala_before_the_first_verse(self) -> None:
        # Quran.com's timings for 2:1 count one word; Tanzil's text starts with the basmala.
        words = khatt.words_from_quran({"2:1": {"segments": [[1, 6200, 7400]]}}, VERSES)
        assert words == [
            Word(" ".join(VERSES["2:1"].split()[:4]), 0.0, 6.2),
            Word(VERSES["2:1"].split()[4], 6.2, 7.4),
            Word("۝١", 7.4, 7.4),
        ]

    def test_no_basmala_in_al_fatiha_or_at_tawbah(self) -> None:
        words = khatt.words_from_quran(
            {"1:1": {"segments": [[n, n * 500, n * 500 + 400] for n in range(1, 5)]}}, VERSES
        )
        assert [w.text for w in words[:4]] == VERSES["1:1"].split()
        with pytest.warns(UserWarning, match="timings stop at word 1"):
            nine = khatt.words_from_quran({"9:1": {"segments": [[1, 0, 400]]}}, VERSES)
        assert nine[0].text == VERSES["9:1"].split()[0]

    def test_basmala_kept_when_the_timings_count_it(self) -> None:
        segments = [[n, n * 500, n * 500 + 400] for n in range(1, 6)]
        words = khatt.words_from_quran({"2:1": {"segments": segments}}, VERSES, verse_numbers=False)
        assert [w.text for w in words] == VERSES["2:1"].split()

    def test_warns_where_editions_count_words_differently(self) -> None:
        # Quran.com counts "بَعْدَ مَا" in 2:181 as one word: 13 words, Tanzil's text 14.
        segments = [[n, n * 500, n * 500 + 400] for n in range(1, 14)]
        with pytest.warns(UserWarning, match="2:181 has 14 words, but its timings stop at word 13"):
            khatt.words_from_quran({"2:181": {"segments": segments}}, VERSES)

    def test_no_warning_when_they_match(self) -> None:
        segments = [[n, n * 500, n * 500 + 400] for n in range(1, 10)]
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            words = khatt.words_from_quran({"1:7": {"segments": segments}}, VERSES)
        assert len(words) == 10  # nine words and the verse medallion
