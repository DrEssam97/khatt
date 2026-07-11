"""Edge-case behaviour of the public API: degrade gracefully, never crash."""

from __future__ import annotations

import pytest

import khatt


def test_empty_string() -> None:
    assert khatt.render("") == ""


def test_whitespace_only() -> None:
    assert khatt.render("   ") == ""


def test_single_letter() -> None:
    assert khatt.render("م").strip()


def test_very_long_string_vs_width() -> None:
    art = khatt.render("مرحبا بالعالم " * 10, width=40)
    lines = art.split("\n")
    assert max(len(line) for line in lines) <= 40
    # A long text squeezed into 40 columns flattens toward nothing tall;
    # the call must still succeed and produce at least one row.
    assert len(lines) >= 1


def test_diacritics_only_string() -> None:
    # Stripped by default → nothing to render, no crash.
    assert khatt.render("ًٌٍَ") == ""


def test_emoji_only_warns_and_returns_empty() -> None:
    with pytest.warns(UserWarning, match="not supported"):
        art = khatt.render("😀🎉")
    assert art == ""


def test_emoji_mixed_with_arabic_degrades_gracefully() -> None:
    with pytest.warns(UserWarning, match="not supported"):
        art = khatt.render("خط 😀")
    assert art.strip()


def test_mixed_arabic_latin_digits() -> None:
    assert khatt.render("خط Khatt 2026").strip()
