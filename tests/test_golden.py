"""Golden-file snapshot tests for the full rendering pipeline.

Snapshots live in tests/golden/. After an intentional rendering change,
regenerate them with ``pytest --update-golden`` and commit the diff.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from khatt.fonts import font_path
from khatt.mapper import map_image
from khatt.raster import rasterize, to_grid
from khatt.shaping import shape

GoldenCheck = Callable[[str, str], None]

WORDS = {
    "marhaba": "مرحبا",
    "khatt": "خط",
    "alqahira": "القاهرة",
}
STYLES = {"blocks": (1, 1), "ascii": (1, 1), "braille": (2, 4)}


def render_pipeline(text: str, style: str, width: int = 40) -> str:
    path = font_path("amiri")
    image = rasterize(shape(text, path), path)
    assert image is not None
    grid = to_grid(image, width, cell=STYLES[style])
    return map_image(grid, style)


@pytest.mark.parametrize("style", sorted(STYLES))
@pytest.mark.parametrize("word", sorted(WORDS))
def test_golden_snapshot(word: str, style: str, golden: GoldenCheck) -> None:
    art = render_pipeline(WORDS[word], style)
    golden(f"{word}_{style}_amiri.txt", art + "\n")
