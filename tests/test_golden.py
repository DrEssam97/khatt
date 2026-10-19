"""Golden-file snapshot tests for the full rendering pipeline.

Snapshots live in tests/golden/. After an intentional rendering change,
regenerate them with ``pytest --update-golden`` and commit the diff.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

import khatt

GoldenCheck = Callable[[str, str], None]

WORDS = {
    "marhaba": "مرحبا",
    "khatt": "خط",
    "alqahira": "القاهرة",
}
STYLES = ("ascii", "blocks", "braille")


@pytest.mark.parametrize("style", STYLES)
@pytest.mark.parametrize("word", sorted(WORDS))
def test_golden_snapshot(word: str, style: str, golden: GoldenCheck) -> None:
    # Fit mode (size=None): the 0.1.0 sizing, kept byte-identical.
    art = khatt.render(WORDS[word], style=style, width=40, size=None)
    golden(f"{word}_{style}_amiri.txt", art + "\n")


@pytest.mark.parametrize("style", STYLES)
@pytest.mark.parametrize("font", khatt.list_fonts())
def test_golden_default_size(font: str, style: str, golden: GoldenCheck) -> None:
    # Every bundled font in every style: a newly registered font fails here
    # until its snapshots are generated with --update-golden.
    art = khatt.render(WORDS["marhaba"], font=font, style=style)
    golden(f"sized_marhaba_{style}_{font}.txt", art + "\n")


def test_golden_wrapped_paragraphs(golden: GoldenCheck) -> None:
    art = khatt.render("السلام عليكم ورحمة الله\nصباح الخير", width=60)
    golden("wrapped_paragraphs_blocks_amiri.txt", art + "\n")


def test_golden_mixed_direction(golden: GoldenCheck) -> None:
    art = khatt.render("مرحبا Khatt 2026", font="rubik", style="ascii", width=70)
    golden("mixed_ascii_rubik.txt", art + "\n")
