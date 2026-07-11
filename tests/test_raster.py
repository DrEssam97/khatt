"""Rasterizer tests: determinism, grid geometry, bundled-font rendering."""

from __future__ import annotations

from PIL import Image

from khatt.fonts import available_fonts, font_path
from khatt.raster import rasterize, to_grid
from khatt.shaping import shape

AMIRI = font_path("amiri")


def ink(text: str, font: str = "amiri") -> Image.Image:
    path = font_path(font)
    image = rasterize(shape(text, path), path)
    assert image is not None
    return image


class TestDeterminism:
    def test_identical_bytes_across_runs(self) -> None:
        first = ink("مرحبا")
        second = ink("مرحبا")
        assert first.size == second.size
        assert first.tobytes() == second.tobytes()

    def test_downsampled_grid_identical_across_runs(self) -> None:
        a = to_grid(ink("خط"), 40)
        b = to_grid(ink("خط"), 40)
        assert a.tobytes() == b.tobytes()


class TestGridGeometry:
    def test_grid_width_matches_columns(self) -> None:
        for columns in (10, 40, 80, 120):
            grid = to_grid(ink("القاهرة"), columns)
            assert grid.size[0] == columns

    def test_grid_respects_cell_subdivision(self) -> None:
        grid = to_grid(ink("خط"), 30, cell=(2, 4))
        assert grid.size[0] == 30 * 2
        assert grid.size[1] % 4 == 0

    def test_at_least_one_row(self) -> None:
        grid = to_grid(ink("ـــــــــــــــ"), 120)  # a very wide, flat tatweel line
        assert grid.size[1] >= 1


class TestFonts:
    def test_every_bundled_font_renders_ink(self) -> None:
        for name in available_fonts():
            image = ink("خط", font=name)
            assert image.getbbox() is not None, f"font {name} produced no ink"


class TestEmptyInput:
    def test_no_glyphs_returns_none(self) -> None:
        assert rasterize([], AMIRI) is None

    def test_whitespace_only_returns_none(self) -> None:
        assert rasterize(shape("   ", AMIRI), AMIRI) is None
