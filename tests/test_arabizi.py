"""Arabizi to Arabic letters, and the --arabizi option."""

from __future__ import annotations

from pathlib import Path

import pytest
from cli_runner import invoke

import khatt
from khatt.cli import main


@pytest.mark.parametrize(
    ("arabizi", "arabic"),
    [
        # common words, converted whole
        ("yalla", "يلا"),
        ("inshallah", "إن شاء الله"),
        ("Habibi", "حبيبي"),
        # digit letters and letter pairs
        ("3arabi", "عربي"),
        ("ta3ban", "تعبان"),
        ("shams", "شمس"),
        ("khamsa", "خمسة"),
        ("ghali", "غالي"),
        ("3'ali", "غالي"),
        ("thalj", "ثلج"),
        # vowels
        ("kitab", "كتاب"),
        ("kalam", "كلام"),
        ("baba", "بابا"),
        ("kbir", "كبير"),
        ("mamnoo3", "ممنوع"),
        ("ezay", "إزاي"),
        ("oola", "أولا"),
        # feminine endings
        ("gama3a", "جماعة"),
        ("madrasah", "مدرسة"),
        ("sayyara", "سيارة"),
        # pronoun endings keep a short vowel
        ("kifik", "كيفك"),
        ("baitak", "بيتك"),
        # the article
        ("elbait", "البيت"),
        ("el-bait", "البيت"),
        ("al-shams", "الشمس"),
        # numbers, punctuation and Arabic stay
        ("2026", "2026"),
        ("enta fein?", "إنت فين؟"),
        ("salam, ya 7abibi; yalla", "سلام، يا حبيبي؛ يلا"),
        ("salam مرحبا", "سلام مرحبا"),
    ],
)
def test_from_arabizi(arabizi: str, arabic: str) -> None:
    assert khatt.from_arabizi(arabizi) == arabic


def test_hamza_digit() -> None:
    assert khatt.from_arabizi("2ana") == "أنا"
    assert khatt.from_arabizi("so2al") == "سءال"  # a known limit: the seat isn't guessed


def test_curly_apostrophe() -> None:
    assert khatt.from_arabizi("3’ali") == khatt.from_arabizi("3'ali")


def test_your_words_win() -> None:
    assert khatt.from_arabizi("ana fahem", {"FAHEM": "فاهم"}) == "أنا فاهم"
    assert khatt.from_arabizi("yalla", {"yalla": "يللا"}) == "يللا"


@pytest.mark.parametrize(
    ("arabizi", "guess", "right"),
    [
        ("mabsoot", "مبسوت", "مبسوط"),  # t could be ت or ط
        ("ketabak", "كتبك", "كتابك"),  # a long vowel written short
        ("fahem", "فهيم", "فاهم"),  # the long vowel is in the other syllable
    ],
)
def test_known_limits_are_fixed_by_your_words(arabizi: str, guess: str, right: str) -> None:
    assert khatt.from_arabizi(arabizi) == guess
    assert khatt.from_arabizi(arabizi, {arabizi: right}) == right


@pytest.mark.parametrize(
    ("text", "looks"),
    [
        ("7abibi", True),
        ("ana ta3ban", True),
        ("salam", True),
        ("Hello, world", False),
        ("Khatt 2026", False),
        ("2026", False),
        ("مرحبا 7", False),
    ],
)
def test_is_arabizi(text: str, looks: bool) -> None:
    assert khatt.is_arabizi(text) is looks


class TestCli:
    def test_converts_before_drawing(self) -> None:
        converted = invoke(main, ["7abibi", "--arabizi", "--size", "6"])
        arabic = invoke(main, ["حبيبي", "--size", "6"])
        assert converted.exit_code == 0
        assert converted.output == arabic.output

    def test_both_keeps_the_arabizi_under_the_arabic(self) -> None:
        both = invoke(main, ["7abibi", "--arabizi", "both", "--size", "6"])
        same = invoke(main, ["حبيبي\n7abibi", "--size", "6"])
        assert both.exit_code == 0
        assert both.output == same.output.replace(
            "hint: this looks like Arabizi; add --arabizi to write it in Arabic letters\n", ""
        )

    def test_hint_without_the_option(self) -> None:
        assert "--arabizi" in invoke(main, ["7abibi", "--size", "6"]).output
        assert "hint" not in invoke(main, ["Hello", "-f", "rubik", "--size", "6"]).output

    def test_stdin_and_animation(self, tmp_path: Path) -> None:
        result = invoke(main, ["--arabizi"], input="yalla\n")
        assert result.exit_code == 0
        assert result.output == invoke(main, ["يلا"]).output
        target = tmp_path / "anim.gif"
        assert invoke(main, ["yalla", "--arabizi", "-a", "type", "-o", str(target)]).exit_code == 0

    def test_fetch_logo(self) -> None:
        result = invoke(main, ["--fetch", "yalla", "--arabizi", "--private", "--color", "never"])
        assert result.exit_code == 0

    def test_words_file(self, tmp_path: Path) -> None:
        words = tmp_path / "words.txt"
        words.write_text("# my spellings\nfahem = فاهم\nma3lesh معلش\n", encoding="utf-8")
        result = invoke(main, ["fahem", "--arabizi", "--arabizi-words", str(words), "--size", "6"])
        assert result.output == invoke(main, ["فاهم", "--size", "6"]).output

    def test_bad_words_file(self, tmp_path: Path) -> None:
        words = tmp_path / "words.txt"
        words.write_text("fahem =\n", encoding="utf-8")
        bad = invoke(main, ["fahem", "--arabizi", "--arabizi-words", str(words)])
        missing = invoke(main, ["fahem", "--arabizi", "--arabizi-words", str(tmp_path / "x")])
        assert bad.exit_code == 2
        assert "words.txt:1" in bad.output
        assert missing.exit_code == 2
