"""Rasterizer tests: determinism, grid geometry, bundled-font rendering."""

from __future__ import annotations

import freetype
import pytest
from PIL import Image

from khatt.fonts import available_fonts, font_path
from khatt.raster import _bitmap_bytes, _face, _glyph, compose, measure, rasterize, to_grid
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


class TestMeasure:
    def test_box_spans_the_ink(self) -> None:
        box = measure(shape("مرحبا", AMIRI), AMIRI)
        assert box is not None
        x0, y0, x1, y1 = box
        image = ink("مرحبا")
        assert x1 - x0 >= image.size[0]
        assert y1 - y0 >= image.size[1]
        assert y0 < 0 < y1  # straddles the baseline

    def test_spaces_have_no_box(self) -> None:
        assert measure(shape("   ", AMIRI), AMIRI) is None


class TestCompose:
    def test_lines_stack(self) -> None:
        one = compose([shape("خط", AMIRI)], AMIRI)
        two = compose([shape("خط", AMIRI), shape("خط", AMIRI)], AMIRI, line_gap=10)
        assert one is not None
        assert two is not None
        assert two.size[1] == 2 * one.size[1] + 10

    def test_alignment(self) -> None:
        lines = [shape("خط", AMIRI), shape("القاهرة", AMIRI)]
        for align, check in (
            ("left", lambda box, width: box[0] == 0),
            ("right", lambda box, width: box[2] == width),
            ("center", lambda box, width: box[0] > 0 and box[2] < width),
        ):
            image = compose(lines, AMIRI, align=[align, align])
            assert image is not None
            width, height = image.size
            short_line = image.crop((0, 0, width, height // 2)).getbbox()
            assert short_line is not None
            assert check(short_line, width), align

    def test_bad_alignment_rejected(self) -> None:
        with pytest.raises(ValueError, match="alignment"):
            compose([shape("خط", AMIRI)], AMIRI, align=["middle"])
        with pytest.raises(ValueError, match="alignments"):
            compose([shape("خط", AMIRI)], AMIRI, align=["left", "left"])

    def test_explicit_rows(self) -> None:
        assert to_grid(ink("خط"), 30, rows=7).size == (30, 7)
        with pytest.raises(ValueError, match="rows"):
            to_grid(ink("خط"), 30, rows=0)
