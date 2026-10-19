"""Rasterizer tests: determinism, grid geometry, bundled-font rendering."""

from __future__ import annotations

import freetype
from PIL import Image

from khatt.fonts import available_fonts, font_path
from khatt.raster import _bitmap_bytes, _face, _glyph, rasterize, to_grid
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


class TestGlyphCache:
    def test_fast_buffer_read_matches_freetype_py(self) -> None:
        face = _face(str(AMIRI))
        gid = shape("خ", AMIRI)[0].gid
        face.load_glyph(gid, freetype.FT_LOAD_RENDER | freetype.FT_LOAD_NO_HINTING)
        bitmap = face.glyph.bitmap
        assert _bitmap_bytes(bitmap) == bytes(bitmap.buffer)

    def test_glyphs_are_cached(self) -> None:
        gid = shape("خ", AMIRI)[0].gid
        assert _glyph(str(AMIRI), gid) is _glyph(str(AMIRI), gid)

    def test_cached_render_is_stable(self) -> None:
        cold = ink("القاهرة").tobytes()
        _glyph.cache_clear()
        assert ink("القاهرة").tobytes() == cold
