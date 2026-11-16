"""khatt --fetch: Arabic for terminals, the system facts and the card."""

from __future__ import annotations

import datetime
import sys
import types
import unicodedata
from pathlib import Path

import pytest
from cli_runner import invoke
from PIL import Image

import khatt
from khatt.cli import main
from khatt.fetch import (
    Fact,
    _hijri,
    _os_release,
    counted,
    date_text,
    logo_text,
    system_facts,
    uptime_text,
)
from khatt.terminal import for_terminal, join_letters, terminal_shapes_arabic

FACTS = [
    Fact("النظام", "Linux 6.8"),
    Fact("الذاكرة", "3.5 / 16.0 جيجابايت", numeric=True),
    Fact("بايثون", "3.13.1"),
]


def names(text: str) -> list[str]:
    return [unicodedata.name(char) for char in text]


class TestJoinLetters:
    def test_positional_forms(self) -> None:
        assert names(join_letters("ببب")) == [
            "ARABIC LETTER BEH INITIAL FORM",
            "ARABIC LETTER BEH MEDIAL FORM",
            "ARABIC LETTER BEH FINAL FORM",
        ]

    def test_right_joining_letters_break_the_word(self) -> None:
        # dal joins only to the letter before it, so the beh after it starts again
        assert names(join_letters("بدب")) == [
            "ARABIC LETTER BEH INITIAL FORM",
            "ARABIC LETTER DAL FINAL FORM",
            "ARABIC LETTER BEH ISOLATED FORM",
        ]

    def test_lam_alef_ligatures(self) -> None:
        assert join_letters("لا") == "ﻻ"
        assert join_letters("الا") == "ﺍﻻ"  # alef doesn't join after it: isolated
        assert join_letters("بلا") == "ﺑﻼ"
        assert join_letters("لأ") == "ﻷ"

    def test_lam_with_other_letters_stays_apart(self) -> None:
        assert names(join_letters("لم")) == [
            "ARABIC LETTER LAM INITIAL FORM",
            "ARABIC LETTER MEEM FINAL FORM",
        ]

    def test_marks_and_tatweel_keep_letters_joined(self) -> None:
        assert names(join_letters("بَب"))[0] == "ARABIC LETTER BEH INITIAL FORM"
        assert names(join_letters("بـ")) == ["ARABIC LETTER BEH INITIAL FORM", "ARABIC TATWEEL"]

    def test_other_characters_are_kept(self) -> None:
        assert join_letters("abc 123") == "abc 123"


class TestForTerminal:
    def test_as_typed_when_the_terminal_lays_arabic_out(self) -> None:
        assert for_terminal("مرحبا", shaped_by_terminal=True) == "مرحبا"

    def test_text_without_arabic_is_unchanged(self) -> None:
        assert for_terminal("Windows 11 (64-bit)", shaped_by_terminal=False) == (
            "Windows 11 (64-bit)"
        )

    def test_display_order_joined_and_without_tashkeel(self) -> None:
        shown = for_terminal("مُحَمَّد", shaped_by_terminal=False)
        assert shown == join_letters("محمد")[::-1]

    def test_mixed_line_in_right_to_left_order(self) -> None:
        shown = for_terminal("النظام: Windows 11 (64-bit)", shaped_by_terminal=False)
        assert shown == "Windows 11 (64-bit) :" + join_letters("النظام")[::-1]

    def test_brackets_in_arabic_face_the_right_way(self) -> None:
        shown = for_terminal("سلام (عليكم)", shaped_by_terminal=False)
        assert shown == "(" + join_letters("عليكم")[::-1] + ") " + join_letters("سلام")[::-1]

    def test_direction_can_be_given(self) -> None:
        assert for_terminal("1 خط", shaped_by_terminal=False, direction="ltr").startswith("1")
        assert for_terminal("1 خط", shaped_by_terminal=False, direction="rtl").endswith("1")


@pytest.mark.parametrize(
    ("environ", "shapes"),
    [
        ({"KONSOLE_VERSION": "230804"}, True),
        ({"MLTERM": "3.9.3"}, True),
        ({"TERM_PROGRAM": "Apple_Terminal"}, True),
        ({"VTE_VERSION": "7600"}, True),
        ({"VTE_VERSION": "5202"}, False),
        ({"WT_SESSION": "x"}, False),
        ({"TERM_PROGRAM": "iTerm.app"}, False),
        ({}, False),
    ],
)
def test_which_terminals_lay_arabic_out(environ: dict[str, str], shapes: bool) -> None:
    assert terminal_shapes_arabic(environ) is shapes


class TestArabicWording:
    @pytest.mark.parametrize(
        ("number", "text"),
        [
            (1, "يوم"),
            (2, "يومان"),
            (3, "3 أيام"),
            (10, "10 أيام"),
            (11, "11 يومًا"),
            (100, "100 يوم"),
            (103, "103 أيام"),
        ],
    )
    def test_counted_days(self, number: int, text: str) -> None:
        assert counted(number, "day") == text

    def test_uptime(self) -> None:
        assert uptime_text(3 * 86400 + 4 * 3600 + 12 * 60 + 30) == "3 أيام و4 ساعات و12 دقيقة"
        assert uptime_text(3600) == "ساعة"
        assert uptime_text(2 * 60) == "دقيقتان"
        assert uptime_text(30) == "أقل من دقيقة"

    def test_date(self) -> None:
        assert date_text(datetime.date(2026, 11, 16)) == "الإثنين 16 نوفمبر 2026"


class TestSystemFacts:
    def test_the_facts_every_system_has(self) -> None:
        day = datetime.date(2026, 1, 2)
        facts = system_facts(today=day, hijri=lambda _: None)
        labels = [fact.label for fact in facts]
        assert labels[0] == "النظام"
        assert {"بايثون", "خط", "التاريخ"} <= set(labels)
        assert "الهجري" not in labels
        assert Fact("خط", khatt.__version__) in facts
        assert Fact("التاريخ", "الجمعة 2 يناير 2026", numeric=True) in facts

    def test_hijri_date_when_available(self) -> None:
        facts = system_facts(hijri=lambda _: "25 جمادى الأولى 1448 هـ")
        assert facts[-1] == Fact("الهجري", "25 جمادى الأولى 1448 هـ", numeric=True)

    def test_terminal_and_shell_from_the_environment(self) -> None:
        facts = system_facts(environ={"SHELL": "/usr/bin/zsh", "WT_SESSION": "1"})
        assert Fact("الصدفة", "zsh") in facts
        assert Fact("الطرفية", "Windows Terminal") in facts

    def test_os_release(self, tmp_path: Path) -> None:
        release = tmp_path / "os-release"
        release.write_text('NAME="Ubuntu"\nID=ubuntu\nPRETTY_NAME="Ubuntu 24.04 LTS"\n')
        assert _os_release(release)["PRETTY_NAME"] == "Ubuntu 24.04 LTS"
        assert _os_release(tmp_path / "missing") == {}

    @pytest.mark.parametrize(
        ("release", "logo"),
        [
            ({"ID": "ubuntu"}, "أوبونتو"),
            ({"ID": "endeavouros", "ID_LIKE": "arch"}, "آرتش"),
            ({"ID": "opensuse-tumbleweed"}, "سوزي"),
            ({"ID": "something-new"}, "لينكس"),
        ],
    )
    def test_linux_logos(
        self, monkeypatch: pytest.MonkeyPatch, release: dict[str, str], logo: str
    ) -> None:
        monkeypatch.setattr(sys, "platform", "linux")
        assert logo_text(release) == logo

    def test_logo_of_this_system(self) -> None:
        assert logo_text()


class TestCard:
    def test_logo_on_the_right_of_the_facts(self) -> None:
        card = khatt.fetch("خط", facts=FACTS, color_mode=None, private=True)
        lines = card.split("\n")
        label = for_terminal("النظام:", shaped_by_terminal=False, direction="rtl")
        row = next(line for line in lines if label in line)
        assert row.index("Linux 6.8") < row.index(label)
        info_end = row.index(label) + len(label)
        logo_rows = [line for line in lines[:-1] if "█" in line]  # the last line: swatches
        assert logo_rows
        assert all(line.index("█") > info_end for line in logo_rows)

    def test_labels_as_typed_for_terminals_that_lay_arabic_out(self) -> None:
        card = khatt.fetch(facts=FACTS, color_mode=None, shaped_by_terminal=True, private=True)
        assert "النظام:" in card

    def test_colour_codes(self) -> None:
        card = khatt.fetch(facts=FACTS, palette="red,blue", private=True)
        assert "\033[38;2;0;0;255m" in card  # the labels take the second colour
        assert "\033[0m" in card
        assert "\033[" not in khatt.fetch(facts=FACTS, color_mode=None, private=True)

    def test_user_and_host_unless_private(self) -> None:
        card = khatt.fetch(facts=FACTS, color_mode=None)
        assert "@" in card
        assert "─" in card
        assert "@" not in khatt.fetch(facts=FACTS, color_mode=None, private=True)

    def test_arabic_digits_only_in_numbers(self) -> None:
        card = khatt.fetch(facts=FACTS, color_mode=None, private=True, arabic_digits=True)
        assert "١٦٫٠ / ٣٫٥" in card  # read right to left: 3.5 of 16.0
        assert "Linux 6.8" in card
        assert "3.13.1" in card

    def test_image(self) -> None:
        image = khatt.fetch_image("خط", facts=FACTS)
        assert image.mode == "RGB"
        assert image.width > image.height
        transparent = khatt.fetch_image("خط", facts=FACTS, bg=None, private=True)
        assert transparent.mode == "RGBA"
        assert transparent.getpixel((0, 0))[3] == 0


class TestCli:
    def test_card_in_the_terminal(self) -> None:
        result = invoke(main, ["--fetch", "--private", "--rtl-terminal", "yes"])
        assert result.exit_code == 0
        assert "النظام:" in result.output
        assert "\033[" not in result.output  # not a terminal

    def test_labels_joined_for_other_terminals(self) -> None:
        result = invoke(main, ["--fetch", "--private", "--rtl-terminal", "no"])
        assert for_terminal("النظام:", shaped_by_terminal=False, direction="rtl") in result.output

    def test_saved_as_image_text_and_ansi(self, tmp_path: Path) -> None:
        for name in ("card.png", "card.webp", "card.txt", "card.ans"):
            target = tmp_path / name
            result = invoke(main, ["--fetch", "مرحبا", "-p", "nile", "-o", str(target)])
            assert result.exit_code == 0, result.output
        with Image.open(tmp_path / "card.png") as image:
            assert image.width > 300
        assert "النظام:" in (tmp_path / "card.txt").read_text(encoding="utf-8")
        assert "\033[38;2;" in (tmp_path / "card.ans").read_text(encoding="utf-8")

    def test_transparent_image(self, tmp_path: Path) -> None:
        target = tmp_path / "card.png"
        assert invoke(main, ["--fetch", "--bg", "none", "-o", str(target)]).exit_code == 0
        with Image.open(target) as image:
            assert image.mode == "RGBA"

    def test_unknown_image_type_fails(self, tmp_path: Path) -> None:
        result = invoke(main, ["--fetch", "-o", str(tmp_path / "card.xyz")])
        assert result.exit_code == 2
        assert "error" in result.output

    def test_unknown_style_fails(self) -> None:
        result = invoke(main, ["--fetch", "-s", "nope"])
        assert result.exit_code == 2


def test_card_fits_the_given_width() -> None:
    wide = khatt.fetch("القاهرة", facts=FACTS, color_mode=None, private=True)
    narrow = khatt.fetch("القاهرة", facts=FACTS, color_mode=None, private=True, width=45)
    assert max(map(len, wide.split("\n"))) > 45
    assert max(map(len, narrow.split("\n"))) <= 45


def test_hijri_date_from_hijridate(monkeypatch: pytest.MonkeyPatch) -> None:
    class Hijri:
        day, year = 6, 1448

        def month_name(self, language: str) -> str:
            assert language == "ar"
            return "جمادى الآخرة"

    class Gregorian:
        def __init__(self, year: int, month: int, day: int) -> None:
            self.date = (year, month, day)

        def to_hijri(self) -> Hijri:
            if self.date[0] < 1900:
                raise OverflowError("out of range")
            return Hijri()

    module = types.ModuleType("hijridate")
    module.Gregorian = Gregorian  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "hijridate", module)
    assert _hijri(datetime.date(2026, 11, 16)) == "6 جمادى الآخرة 1448 هـ"
    assert _hijri(datetime.date(1800, 1, 1)) is None


def test_no_hijri_date_without_hijridate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "hijridate", None)
    assert _hijri(datetime.date(2026, 11, 16)) is None
