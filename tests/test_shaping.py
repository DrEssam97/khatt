"""Shaping correctness tests.

The bundled font builds ship without a ``post`` glyph-name table, so these
tests assert *relationships* between glyph IDs (a ligature or positional form
must differ from the isolated form of the same letter) instead of matching
glyph names.
"""

from __future__ import annotations

import pytest

from khatt.fonts import font_path
from khatt.shaping import shape, strip_tashkeel

AMIRI = font_path("amiri")


def gids(text: str, keep_tashkeel: bool = False) -> list[int]:
    return [g.gid for g in shape(text, AMIRI, keep_tashkeel=keep_tashkeel)]


class TestLigatures:
    def test_lam_alef_is_not_two_isolated_glyphs(self) -> None:
        liga = gids("لا")
        isolated = {gids("ل")[0], gids("ا")[0]}
        assert not set(liga) & isolated

    def test_lam_alef_is_not_plain_initial_lam(self) -> None:
        # In "لب" the lam takes its ordinary initial form (visual order is
        # left-to-right, so the lam is the last glyph). The lam of the
        # mandatory lam-alef ligature must be a different glyph.
        lam_init = gids("لب")[-1]
        assert lam_init not in gids("لا")


class TestPositionalForms:
    def test_muhammad_has_no_isolated_forms(self) -> None:
        word = gids("محمد")
        assert len(word) == 4
        isolated = {gids(c)[0] for c in set("محمد")}
        assert not set(word) & isolated

    def test_initial_and_medial_meem_differ(self) -> None:
        # محمد is visually (left to right): dal.fina, meem.medi, hah.medi,
        # meem.init — the two meems must resolve to different glyphs.
        word = gids("محمد")
        assert word[1] != word[3]


class TestBidi:
    def test_mixed_direction_visual_order(self) -> None:
        shaped = gids("سلام Hi 123")
        # Base direction is RTL, so the Latin/digit run sits at the visual
        # left: H i ... 1 2 3 ... then the Arabic word.
        assert shaped[0] == gids("H")[0]
        assert shaped[1] == gids("i")[0]
        one, two, three = (gids(d)[0] for d in "123")
        i = shaped.index(one)
        assert shaped[i : i + 3] == [one, two, three]
        arabic = gids("سلام")
        assert shaped[-len(arabic) :] == arabic

    def test_arabic_indic_digits_stay_left_to_right(self) -> None:
        assert gids("١٢٣") == [gids(d)[0] for d in "١٢٣"]

    def test_digits_inside_arabic_sentence(self) -> None:
        shaped = gids("صفحة ١٢ من ٣٤")
        one_two = [gids(d)[0] for d in "١٢"]
        i = shaped.index(one_two[0])
        assert shaped[i : i + 2] == one_two


class TestTashkeel:
    def test_stripped_by_default(self) -> None:
        assert gids("مَرْحَبًا") == gids("مرحبا")

    def test_kept_with_flag(self) -> None:
        shaped = shape("مَ", AMIRI, keep_tashkeel=True)
        assert len(shaped) == 2
        # Combining marks carry no horizontal advance.
        assert any(g.x_advance == 0 for g in shaped)

    def test_strip_tashkeel_utility(self) -> None:
        assert strip_tashkeel("مَرْحَبًا") == "مرحبا"
        assert strip_tashkeel("خَطّ") == "خط"
        assert strip_tashkeel("no marks") == "no marks"

    def test_tashkeel_only_string_strips_to_nothing(self) -> None:
        assert shape("ًٌَ", AMIRI) == []


class TestEdgeCases:
    def test_empty_string(self) -> None:
        assert shape("", AMIRI) == []

    def test_unsupported_char_warns_and_is_dropped(self) -> None:
        with pytest.warns(UserWarning, match="not supported"):
            shaped = shape("😀", AMIRI)
        assert shaped == []

    def test_unsupported_char_does_not_take_arabic_down_with_it(self) -> None:
        with pytest.warns(UserWarning, match="not supported"):
            shaped = shape("خط😀", AMIRI)
        assert [g.gid for g in shaped] == gids("خط")

    def test_shaped_glyph_fields(self) -> None:
        glyph = shape("خ", AMIRI)[0]
        assert glyph.gid > 0
        assert glyph.x_advance > 0
        assert isinstance(glyph.cluster, int)
