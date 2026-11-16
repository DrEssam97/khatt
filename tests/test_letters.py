"""The letters style: text art inked with the letters of a word or phrase."""

from __future__ import annotations

import unicodedata
from pathlib import Path

import pytest
from cli_runner import invoke
from PIL import Image

import khatt
from khatt.cli import main
from khatt.fetch import Fact
from khatt.mapper import fill_characters, map_image
from khatt.terminal import keep_in_cells

LRO, PDF = "‭", "‬"


def isolated(text: str) -> list[str]:
    return [unicodedata.lookup(f"{unicodedata.name(char)} ISOLATED FORM") for char in text]


def ink(art: str, rtl: bool = True) -> list[str]:
    """The art's characters in reading order: each row right to left, rows top down."""
    rows = art.split("\n")
    return [char for row in rows for char in (reversed(row) if rtl else row) if char != " "]


class TestFillCharacters:
    def test_arabic_letters_in_isolated_forms(self) -> None:
        chars, rtl = fill_characters("سلام")
        assert chars == isolated("سلام")
        assert rtl

    def test_spaces_and_tashkeel_are_left_out(self) -> None:
        chars, _ = fill_characters("سَلام عليكم")
        assert chars == isolated("سلامعليكم")

    def test_arabizi_reads_left_to_right(self) -> None:
        chars, rtl = fill_characters("7abibi 3la")
        assert chars == list("7abibi3la")
        assert not rtl

    def test_letters_without_forms_stay(self) -> None:
        chars, _ = fill_characters("ء1")
        assert chars == ["ﺀ", "1"]


class TestRender:
    def test_the_word_is_inked_with_its_own_letters(self) -> None:
        art = khatt.render("سلام", style="letters", size=10)
        letters = ink(art)
        cycle = isolated("سلام")
        assert letters
        assert letters == [cycle[n % 4] for n in range(len(letters))]

    def test_a_phrase_as_the_fill(self) -> None:
        art = khatt.render("خط", style="letters", size=10, fill="بسم الله")
        cycle = isolated("بسمالله")
        letters = ink(art)
        assert letters == [cycle[n % len(cycle)] for n in range(len(letters))]

    def test_arabizi_fill_runs_left_to_right(self) -> None:
        art = khatt.render("حب", style="letters", size=10, fill="7abibi")
        letters = ink(art, rtl=False)
        assert letters == [ch for n in range(len(letters)) for ch in ["7abibi"[n % 6]]]

    def test_an_empty_fill_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="fill"):
            khatt.render("خط", style="letters", fill=" َ ")

    def test_default_fill_of_the_mapper(self) -> None:
        grid = Image.new("L", (3, 1), 255)
        assert map_image(grid, "letters") == "".join(reversed(isolated("خطخ")))


class TestDrawing:
    def test_png_draws_the_arabic_letters(self) -> None:
        image = khatt.art_to_image(isolated("س")[0], cell_width=40, padding=0)
        assert image is not None
        assert image.convert("L").getextrema()[0] < 128

    def test_svg_writes_the_letters_as_text(self) -> None:
        svg = khatt.art_to_svg(isolated("س")[0])
        assert svg is not None
        assert ">ﺱ</text>" in svg
        assert "Cairo" in svg

    def test_html_keeps_every_letter_in_its_cell(self) -> None:
        assert "unicode-bidi:bidi-override" in khatt.art_to_html(isolated("سل")[0])


def test_keep_in_cells_marks_only_arabic_lines() -> None:
    art = "  " + isolated("س")[0] + "\n██\n"
    assert keep_in_cells(art) == f"{LRO}  ﺱ{PDF}\n██\n"


class TestElsewhere:
    def test_animation_inks_with_the_text(self) -> None:
        animation = khatt.animate("سلام", "type", style="letters", size=8)
        assert set(ink(animation.frames[-1])) <= set(isolated("سلام"))

    def test_fetch_logo_keeps_its_order_in_shaping_terminals(self) -> None:
        card = khatt.fetch(
            "خط",
            style="letters",
            facts=[Fact("النظام", "Linux")],
            color_mode=None,
            private=True,
            shaped_by_terminal=True,
        )
        assert LRO in card


class TestCli:
    def test_fill_option(self) -> None:
        result = invoke(main, ["خط", "-s", "letters", "--fill", "7abibi", "--size", "8"])
        assert result.exit_code == 0
        assert set(result.output) <= set("7abibi \n")

    def test_order_marks_only_for_shaping_terminals(self) -> None:
        marked = invoke(main, ["خط", "-s", "letters", "--rtl-terminal", "yes", "--size", "8"])
        plain = invoke(main, ["خط", "-s", "letters", "--rtl-terminal", "no", "--size", "8"])
        assert LRO in marked.output
        assert LRO not in plain.output

    def test_saved_text_keeps_its_order(self, tmp_path: Path) -> None:
        target = tmp_path / "art.txt"
        result = invoke(main, ["سلام", "-s", "letters", "--size", "8", "-o", str(target)])
        assert result.exit_code == 0
        assert LRO in target.read_text(encoding="utf-8")

    def test_saved_image(self, tmp_path: Path) -> None:
        target = tmp_path / "art.png"
        result = invoke(main, ["سلام", "-s", "letters", "-p", "gold", "-o", str(target)])
        assert result.exit_code == 0
        with Image.open(target) as image:
            assert image.width > 100
