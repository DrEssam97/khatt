"""Tests for the public khatt API."""

from __future__ import annotations

import pytest

import khatt

BLOCKS_CHARS = set(" ░▒▓█\n")
ASCII_CHARS = set(" .:-=+*#%@\n")


def test_version() -> None:
    assert khatt.__version__ == "0.1.0"


def test_render_returns_art() -> None:
    art = khatt.render("مرحبا")
    assert isinstance(art, str)
    assert art.strip()
    assert set(art) <= BLOCKS_CHARS


def test_render_respects_width() -> None:
    for width in (20, 60, 100):
        art = khatt.render("القاهرة", width=width)
        assert max(len(line) for line in art.split("\n")) <= width


def test_render_styles() -> None:
    assert set(khatt.render("خط", style="ascii")) <= ASCII_CHARS
    braille = khatt.render("خط", style="braille")
    assert all(0x2800 <= ord(ch) <= 0x28FF for line in braille.split("\n") for ch in line)


def test_render_all_fonts() -> None:
    for font in khatt.list_fonts():
        assert khatt.render("خط", font=font).strip()


def test_render_threshold_thins_output() -> None:
    dense = khatt.render("مرحبا", threshold=None)
    sparse = khatt.render("مرحبا", threshold=0.8)
    count_ink = lambda art: sum(ch not in " \n" for ch in art)  # noqa: E731
    assert count_ink(sparse) < count_ink(dense)


def test_render_keep_tashkeel_changes_output() -> None:
    word = "مَرْحَبًا"
    assert khatt.render(word, keep_tashkeel=True) != khatt.render(word)


def test_render_unknown_font_raises() -> None:
    with pytest.raises(KeyError, match="available fonts"):
        khatt.render("خط", font="nope")


def test_render_unknown_style_raises() -> None:
    with pytest.raises(KeyError, match="available styles"):
        khatt.render("خط", style="nope")


def test_list_fonts_and_styles() -> None:
    assert khatt.list_fonts() == ["amiri", "cairo", "noto-naskh", "rubik"]
    assert khatt.list_styles() == ["ascii", "blocks", "braille"]
