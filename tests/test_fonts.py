"""Tests for the bundled-font registry."""

from __future__ import annotations

import pytest

from khatt.fonts import available_fonts, font_path


def test_all_registered_fonts_exist_on_disk() -> None:
    for name in available_fonts():
        assert font_path(name).is_file()


def test_lookup_is_case_insensitive() -> None:
    assert font_path("Amiri") == font_path("amiri")


def test_unknown_font_raises_with_available_names() -> None:
    with pytest.raises(KeyError, match="amiri"):
        font_path("definitely-not-a-font")


def test_amiri_is_bundled() -> None:
    assert "amiri" in available_fonts()


def test_every_font_family_has_a_license() -> None:
    licenses_dir = font_path("amiri").parent / "LICENSES"
    assert licenses_dir.is_dir()
    assert any(licenses_dir.iterdir())
