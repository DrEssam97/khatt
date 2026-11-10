"""Calligrams: text flows inside a shape, whole, and Arabic lines stretch with kashida."""

from __future__ import annotations

import warnings
from typing import Any

import pytest
from PIL import Image, ImageChops, ImageDraw, ImageFilter

import khatt
from khatt.calligram import _draw_lines, _flow, _Measure, _segments, _shape_mask
from khatt.fonts import font_path
from khatt.kashida import TATWEEL, kashida_points, stretch
from khatt.raster import size_metrics
from khatt.shaping import base_direction

LOVE = "أحبك"
POEM = (
    "إذا الشعب يوما أراد الحياة فلا بد أن يستجيب القدر ولا بد لليل أن ينجلي ولا بد للقيد أن ينكسر"
)


def lay_out(
    text: str, shape: Any = "heart", size: int = 24, repeat: bool = True, **kwargs: Any
) -> Any:
    """The calligram's lines and coverage, on a canvas as big as the shape."""
    mask = _shape_mask(shape, kwargs.pop("width", 400))
    path = font_path(kwargs.get("font", "amiri"))
    direction = base_direction(text)
    measure = _Measure(path, direction, size, True, ())
    ascent, descent = size_metrics(str(path), size)
    lines, placed = _flow(
        text.split(),
        mask,
        measure,
        pitch=1.15 * size,
        ascent=ascent,
        descent=descent,
        repeat=repeat,
    )
    coverage, _ = _draw_lines(
        lines,
        mask.size,
        measure,
        justify=kwargs.get("justify", True),
        last_is_end=not repeat,
        font=kwargs.get("font", "amiri"),
        keep_tashkeel=True,
        stroke_width=0,
        fallback_fonts=(),
    )
    return mask, lines, placed, coverage


def ink_outside(mask: Image.Image, coverage: Image.Image) -> int:
    """Pixels of text drawn where the shape isn't, allowing a pixel of antialiasing."""
    inside = mask.point(lambda v: 255 if v >= 128 else 0).filter(ImageFilter.MaxFilter(3))
    outside = ImageChops.subtract(coverage.point(lambda v: 255 if v >= 128 else 0), inside)
    return outside.histogram()[255]


class TestKashida:
    @pytest.mark.parametrize(
        ("word", "points"),
        [
            ("بسم", [1, 2]),
            ("دار", []),  # dal, alef and reh never join the letter after them
            ("سلام", [1]),  # never inside lam-alef
            ("بِسْمِ", [2, 4]),  # after each letter's marks
            ("محمد", [1, 2, 3]),
            ("Cairo", []),
            ("ب", []),
        ],
    )
    def test_where_it_may_go(self, word: str, points: list[int]) -> None:
        assert kashida_points(word) == points

    def test_adds_what_is_asked(self) -> None:
        line = "بسم الله الرحمن"
        stretched = stretch(line, 5)
        assert stretched.count(TATWEEL) == 5
        assert stretched.replace(TATWEEL, "") == line

    def test_spreads_over_the_words(self) -> None:
        stretched = stretch("بسم بسم بسم", 3)
        assert [word.count(TATWEEL) for word in stretched.split()] == [1, 1, 1]

    def test_has_a_limit_per_place(self) -> None:
        assert stretch("بب", 50).count(TATWEEL) == 3

    def test_words_that_cannot_stretch_stay_as_they_are(self) -> None:
        assert stretch("دار وزار", 4) == "دار وزار"
        assert stretch("بسم", 0) == "بسم"

    def test_marks_stay_with_their_letter(self) -> None:
        stretched = stretch("بِسْمِ", 2)
        assert stretched == f"بِ{TATWEEL}سْ{TATWEEL}مِ"


class TestFlow:
    @pytest.mark.parametrize("shape", khatt.list_shapes())
    def test_text_stays_inside_the_shape(self, shape: str) -> None:
        mask, lines, _, coverage = lay_out(LOVE, shape)
        assert lines
        assert ink_outside(mask, coverage) == 0

    @pytest.mark.parametrize("font", ["amiri", "lalezar", "cairo", "aref-ruqaa"])
    def test_every_font_stays_inside(self, font: str) -> None:
        mask, lines, _, coverage = lay_out(POEM, "circle", font=font)
        assert lines and ink_outside(mask, coverage) == 0

    def test_lines_fit_their_stretch_of_the_shape(self) -> None:
        _, lines, _, _ = lay_out(POEM, "circle", justify=False)
        measure = _Measure(font_path("amiri"), "rtl", 24, True, ())
        for taken, (left, right), _ in lines:
            assert measure.exact(" ".join(taken)) <= right - left

    def test_arabic_starts_on_the_right(self) -> None:
        _, lines, _, _ = lay_out(LOVE, "heart")
        first_row = [line for line in lines if line[2] == lines[0][2]]
        assert len(first_row) == 2  # the two lobes of the heart
        assert first_row[0][1][0] > first_row[1][1][0]

    def test_latin_starts_on_the_left(self) -> None:
        _, lines, _, _ = lay_out("love", "heart", font="rubik")
        first_row = [line for line in lines if line[2] == lines[0][2]]
        assert first_row[0][1][0] < first_row[1][1][0]

    def test_without_repeat_every_word_once(self) -> None:
        words = POEM.split()
        _, lines, placed, _ = lay_out(POEM, "circle", size=20, repeat=False)
        assert placed == len(words)
        assert [w for taken, _, _ in lines for w in taken] == words

    def test_repeat_fills_the_shape(self) -> None:
        _, once, _, _ = lay_out(POEM, "circle", size=20, repeat=False)
        _, full, _, _ = lay_out(POEM, "circle", size=20, repeat=True)
        assert len(full) > len(once)

    def test_narrow_parts_are_skipped(self) -> None:
        mask = Image.new("L", (400, 100), 0)
        ImageDraw.Draw(mask).rectangle((0, 0, 30, 99), fill=255)
        ImageDraw.Draw(mask).rectangle((100, 0, 399, 99), fill=255)
        segments = _segments(mask, 10, 60, narrowest=40, inset=2)
        assert segments == [(102, 398)]


class TestCalligram:
    @pytest.mark.parametrize("shape", khatt.list_shapes())
    def test_every_shape(self, shape: str) -> None:
        image = khatt.calligram(LOVE, shape, width=300)
        assert image is not None and image.mode == "RGBA"

    @pytest.mark.parametrize("effect", khatt.list_effects())
    def test_every_effect(self, effect: str) -> None:
        image = khatt.calligram(LOVE, "circle", width=300, effect=effect, font="lalezar")
        assert image is not None

    def test_fits_the_text_once_without_repeat(self) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            image = khatt.calligram(POEM, "circle", width=400, repeat=False)
        assert image is not None

    def test_a_bigger_shape_gets_bigger_text(self) -> None:
        small = khatt.calligram(POEM, "circle", width=300, repeat=False)
        large = khatt.calligram(POEM, "circle", width=600, repeat=False)
        assert small is not None and large is not None
        assert large.width > small.width * 1.6

    def test_too_much_text_warns(self) -> None:
        with pytest.warns(khatt.TextOverflowWarning, match="left out"):
            khatt.calligram(POEM * 20, "circle", width=100, repeat=False)

    def test_justify_stretches_lines(self) -> None:
        stretched = khatt.calligram(POEM, "circle", width=400)
        plain = khatt.calligram(POEM, "circle", width=400, justify=False)
        assert stretched is not None and plain is not None
        assert stretched.tobytes() != plain.tobytes()

    def test_size_px(self) -> None:
        small = khatt.calligram(LOVE, "circle", width=400, size_px=14)
        large = khatt.calligram(LOVE, "circle", width=400, size_px=40)
        assert small is not None and large is not None

    def test_colour_padding_and_background(self) -> None:
        image = khatt.calligram(
            LOVE, "circle", width=200, fill="#ff0000", padding=6, background="white"
        )
        assert image is not None
        assert image.getpixel((0, 0)) == (255, 255, 255, 255)
        counts = image.convert("RGB").getcolors(1 << 24)
        assert counts is not None and any(r > 200 and g < 60 for _, (r, g, b) in counts)

    def test_mixed_scripts_keep_right_to_left_lines(self) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            image = khatt.calligram("Cairo القاهرة 2026 مصر", "circle", width=300)
        assert image is not None

    def test_line_breaks_are_spaces(self) -> None:
        one = khatt.calligram("خط جميل", "circle", width=300)
        two = khatt.calligram("خط\nجميل", "circle", width=300)
        assert one is not None and two is not None and one.tobytes() == two.tobytes()

    def test_nothing_to_draw(self) -> None:
        assert khatt.calligram("", "heart") is None
        assert khatt.calligram("  \n ", "heart") is None

    def test_drawing_twice_gives_the_same_pixels(self) -> None:
        one = khatt.calligram(LOVE, "heart", width=300)
        two = khatt.calligram(LOVE, "heart", width=300)
        assert one is not None and two is not None and one.tobytes() == two.tobytes()


class TestYourOwnShape:
    def silhouette(self, mode: str) -> Image.Image:
        if mode == "RGBA":
            image = Image.new("RGBA", (300, 200), (0, 0, 0, 0))
            ImageDraw.Draw(image).rectangle((50, 20, 250, 180), fill=(10, 10, 10, 255))
        else:
            image = Image.new(mode, (300, 200), "white")
            ImageDraw.Draw(image).rectangle((50, 20, 250, 180), fill="black")
        return image

    @pytest.mark.parametrize("mode", ["RGBA", "RGB", "L"])
    def test_opaque_or_dark_is_inside(self, mode: str) -> None:
        mask = _shape_mask(self.silhouette(mode), 201)
        assert mask.size == (201, 161)
        assert mask.getpixel((100, 80)) == 255

    def test_drawn_inside_it(self) -> None:
        mask, lines, _, coverage = lay_out(LOVE, self.silhouette("RGBA"))
        assert lines and ink_outside(mask, coverage) == 0

    def test_an_empty_image_is_refused(self) -> None:
        with pytest.raises(ValueError, match="no inside"):
            khatt.calligram(LOVE, Image.new("RGB", (100, 100), "white"))


class TestErrors:
    def test_listed(self) -> None:
        assert khatt.list_shapes() == ["arch", "circle", "crescent", "diamond", "heart"]

    def test_unknown_shape(self) -> None:
        with pytest.raises(KeyError, match="heart"):
            khatt.calligram(LOVE, "triangle")

    def test_names_ignore_case(self) -> None:
        one, two = (
            khatt.calligram(LOVE, " HEART ", width=200),
            khatt.calligram(LOVE, "heart", width=200),
        )
        assert one is not None and two is not None and one.tobytes() == two.tobytes()

    @pytest.mark.parametrize(
        ("kwargs", "match"),
        [
            ({"shape": 5}, "shape"),
            ({"width": 10}, "width"),
            ({"width": float("nan")}, "width"),
            ({"padding": -1}, "padding"),
            ({"line_spacing": 0}, "line_spacing"),
            ({"size_px": 0}, "size_px"),
            ({"effect": 5}, "effect"),
        ],
    )
    def test_bad_values(self, kwargs: dict[str, Any], match: str) -> None:
        with pytest.raises(ValueError, match=match):
            khatt.calligram(LOVE, **kwargs)
