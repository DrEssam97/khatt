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
    art = khatt.render(WORDS[word], style=style, width=40)
    golden(f"{word}_{style}_amiri.txt", art + "\n")
