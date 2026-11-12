"""Rasterizer tests: determinism, grid geometry, bundled-font rendering."""

from __future__ import annotations

import pytest
from PIL import Image

from khatt.fonts import available_fonts, font_path
from khatt.raster import _glyph, compose, measure, rasterize, size_metrics, to_grid
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
    def test_upright(self) -> None:
        # HarfBuzz hands rows bottom to top: an alef stands on the baseline.
        alef = _glyph(str(AMIRI), shape("ا", AMIRI)[0].gid, 100)
        assert alef.image is not None
        width, height = alef.image.size
        assert height > 2 * width
        assert alef.top > 0  # above the baseline
        assert alef.top - height < alef.top / 4  # its foot is near the baseline

    def test_space_has_no_ink(self) -> None:
        assert _glyph(str(AMIRI), shape(" ", AMIRI)[0].gid, 100).image is None

    def test_outline_holds_the_glyph(self) -> None:
        gid = shape("ه", AMIRI)[0].gid
        plain = _glyph(str(AMIRI), gid, 80, 16)
        outlined = _glyph(str(AMIRI), gid, 80, 16, stroke=4 * 64)
        assert plain.image is not None and outlined.image is not None
        assert outlined.image.width - plain.image.width in range(7, 10)  # 4 px each side
        assert outlined.image.height - plain.image.height in range(7, 10)
        x, y = plain.left - outlined.left, outlined.top - plain.top
        under = outlined.image.crop((x, y, x + plain.image.width, y + plain.image.height))
        lit = [a for a, b in zip(under.tobytes(), plain.image.tobytes(), strict=True) if a < b]
        assert not lit  # every pixel of the glyph is covered by its outline

    def test_size_metrics_round_like_freetype(self) -> None:
        # Values FreeType gave for these fonts and sizes, including exact halves.
        assert size_metrics(str(AMIRI), 48) == (54, 31)
        assert size_metrics(str(AMIRI), 1) == (2, 1)

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
