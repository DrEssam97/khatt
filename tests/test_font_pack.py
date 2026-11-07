"""The khatt-fonts package, when it is installed: CI's font pack job runs this."""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest
from PIL import Image

import khatt
from khatt.fonts import _REGISTRY, _STYLES, font_path

khatt_fonts = pytest.importorskip("khatt_fonts")

FONTS: dict[str, Path] = khatt_fonts.fonts()
STYLES: dict[str, list[str]] = khatt_fonts.styles()
BUNDLED = set(_REGISTRY)
LETTERS = "ابتثجحخدذرزسشصضطظعغفقكلمنهوي"


def test_the_pack_is_complete() -> None:
    assert len(FONTS) == 22
    assert sorted(name for names in STYLES.values() for name in names) == sorted(FONTS)
    assert all(path.is_file() for path in FONTS.values())


def test_every_font_has_its_licence() -> None:
    licences = Path(khatt_fonts.__file__).parent / "licenses"
    assert len(list(licences.glob("OFL-*.txt"))) == len(FONTS)
    for licence in licences.glob("OFL-*.txt"):
        assert "SIL OPEN FONT LICENSE Version 1.1" in licence.read_text(encoding="utf-8")


def test_listed_next_to_the_bundled_fonts() -> None:
    assert set(khatt.list_fonts()) == BUNDLED | set(FONTS)


def test_names_are_not_taken_twice() -> None:
    assert not BUNDLED & set(FONTS)
    assert not (BUNDLED | set(FONTS)) & (set(STYLES) | set(_STYLES))


@pytest.mark.parametrize("name", sorted(FONTS))
def test_every_font_draws_arabic(name: str) -> None:
    assert font_path(name) == FONTS[name]
    assert khatt.missing_characters(LETTERS, font=name) == []
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        image = khatt.word_art("خط جميل", effect="gold", font=name, size_px=60)
    assert image is not None and image.width > 60


@pytest.mark.parametrize("name", sorted(FONTS))
def test_letters_are_joined(name: str) -> None:
    """Joined letters draw as one shape, so the word is narrower than its letters apart."""
    word = khatt.text_bbox("سلم", font=name, size_px=100)
    apart = khatt.text_bbox("س ل م", font=name, size_px=100)
    assert word[2] - word[0] < apart[2] - apart[0]


@pytest.mark.parametrize("style", sorted(set(STYLES) - set(_STYLES)))
def test_a_style_only_the_pack_has_draws_with_its_first_font(style: str) -> None:
    assert font_path(style) == FONTS[STYLES[style][0]]


@pytest.mark.parametrize("style", sorted(_STYLES))
def test_a_bundled_style_stays_bundled(style: str) -> None:
    assert font_path(style) == font_path(_STYLES[style])


def test_names_ignore_case() -> None:
    assert font_path(" Noto-Kufi ") == FONTS["noto-kufi"]
    assert font_path("NASTALIQ") == FONTS["gulzar"]


def test_works_everywhere_a_font_is_taken() -> None:
    assert khatt.render("خط", font="nastaliq").strip()
    assert khatt.render_image("خط", font="kufam") is not None
    image = Image.new("RGB", (400, 200), "white")
    khatt.overlay(image, "خط جميل", (10, 10, 390, 190), font="jomhuria")
    assert image.getextrema()[0][0] == 0
