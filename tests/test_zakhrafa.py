"""Zakhrafa: decorations go only where letters join, so words stay whole."""

from __future__ import annotations

import warnings

import pytest

import khatt
from khatt.kashida import TATWEEL
from khatt.zakhrafa import _STYLES

NAMES = ["محمد", "فاطمة", "عبد الله", "سلام", "مُحَمَّد", "نور الهدى"]


def undo(decorated: str, style: str) -> str:
    """Take a style's decorations back out."""
    spec = _STYLES[style]
    before, after = spec.frame
    assert decorated.startswith(before) and decorated.endswith(after)
    inner = decorated[len(before) : len(decorated) - len(after)]
    return inner.replace(spec.join, "") if spec.join else inner


class TestDecorations:
    def test_tatweel(self) -> None:
        assert khatt.zakhrafa("محمد") == f"م{TATWEEL}ح{TATWEEL}م{TATWEEL}د"

    def test_long(self) -> None:
        assert khatt.zakhrafa("محمد", "long").count(TATWEEL) == 9

    def test_only_where_letters_join(self) -> None:
        assert khatt.zakhrafa("دار") == "دار"  # dal, alef and reh join nothing after them
        assert khatt.zakhrafa("وزارة") == "وزارة"

    def test_never_inside_lam_alef(self) -> None:
        assert khatt.zakhrafa("سلام") == f"س{TATWEEL}لام"

    def test_tashkeel_stays_with_its_letter(self) -> None:
        assert khatt.zakhrafa("مُحَمَّد") == f"مُ{TATWEEL}حَ{TATWEEL}مَّ{TATWEEL}د"

    def test_frames(self) -> None:
        assert khatt.zakhrafa("محمد", "brackets") == "『محمد』"
        assert khatt.zakhrafa("محمد", "crown").startswith("♚ ")

    def test_royal(self) -> None:
        assert khatt.zakhrafa("محمد", "royal") == "꧁༺ مـ͜͡ـحـ͜͡ـمـ͜͡ـد ༻꧂"

    @pytest.mark.parametrize("style", khatt.list_zakhrafa())
    @pytest.mark.parametrize("name", NAMES)
    def test_takes_nothing_away(self, style: str, name: str) -> None:
        assert undo(khatt.zakhrafa(name, style), style) == name

    @pytest.mark.parametrize("style", khatt.list_zakhrafa())
    def test_every_style_changes_a_name(self, style: str) -> None:
        assert khatt.zakhrafa("محمد", style) != "محمد"

    def test_words_and_lines_keep_their_breaks(self) -> None:
        decorated = khatt.zakhrafa("نور الهدى\nمحمد علي")
        assert decorated.count(" ") == 2 and decorated.count("\n") == 1

    def test_other_scripts_are_left_alone(self) -> None:
        assert khatt.zakhrafa("Khatt 2026") == "Khatt 2026"
        assert khatt.zakhrafa("Khatt", "hearts") == "♡ Khatt ♡"
        assert khatt.zakhrafa("Khatt خط") == f"Khatt خ{TATWEEL}ط"

    def test_blank_text(self) -> None:
        assert khatt.zakhrafa("") == ""
        assert khatt.zakhrafa("  ", "crown") == "  "

    def test_names_ignore_case(self) -> None:
        assert khatt.zakhrafa("محمد", " ROYAL ") == khatt.zakhrafa("محمد", "royal")


class TestStillArabic:
    @pytest.mark.parametrize("style", ["tatweel", "long"])
    def test_draws_as_joined_text(self, style: str) -> None:
        plain = khatt.text_bbox("محمد", font="lalezar", size_px=80)
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            image = khatt.word_art(khatt.zakhrafa("محمد", style), effect="gold")
            stretched = khatt.text_bbox(khatt.zakhrafa("محمد", style), font="lalezar", size_px=80)
        assert image is not None
        assert stretched[2] - stretched[0] > plain[2] - plain[0]


class TestErrors:
    def test_listed(self) -> None:
        assert khatt.list_zakhrafa() == sorted(_STYLES)
        assert len(khatt.list_zakhrafa()) == 10

    def test_unknown_style(self) -> None:
        with pytest.raises(KeyError, match="royal"):
            khatt.zakhrafa("محمد", "sparkles")

    @pytest.mark.parametrize(("text", "style"), [(5, "royal"), ("محمد", 5)])
    def test_not_strings(self, text: object, style: object) -> None:
        with pytest.raises(ValueError):
            khatt.zakhrafa(text, style)  # type: ignore[arg-type]
