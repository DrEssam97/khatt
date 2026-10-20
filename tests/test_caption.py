"""Caption images with moviepy's TextClip geometry (no moviepy needed)."""

from __future__ import annotations

from itertools import pairwise
from pathlib import Path
from typing import Any

import pytest
from PIL import Image, ImageChops, ImageDraw, ImageFont, features

import khatt
from khatt.caption import _measure
from khatt.fonts import font_path

Box = tuple[int, int, int, int]
VOCALIZED = "بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ"


def alpha_box(image: Image.Image) -> Box:
    box = image.getchannel("A").getbbox()
    assert box is not None, "nothing was drawn"
    return box


def alpha_sum(image: Image.Image) -> int:
    return sum(i * n for i, n in enumerate(image.getchannel("A").histogram()))


def line_boxes(image: Image.Image, count: int = 2) -> list[Box]:
    """Ink box of each of ``count`` lines, split at the widest blank row gaps.

    (Dots and diacritics leave blank rows inside a line too.)
    """
    alpha = image.getchannel("A")
    width = image.size[0]
    inked = [
        y for y in range(image.size[1]) if alpha.crop((0, y, width, y + 1)).getbbox() is not None
    ]
    gaps = sorted(
        ((below - above, above, below) for above, below in pairwise(inked) if below > above + 1),
        reverse=True,
    )[: count - 1]
    cuts = [inked[0], *sorted(below for _, _, below in gaps), inked[-1] + 1]
    boxes = []
    for top, bottom in pairwise(cuts):
        x0, y0, x1, y1 = alpha_box(image.crop((0, top, width, bottom)))
        boxes.append((x0, y0 + top, x1, y1 + top))
    return boxes


def colours(image: Image.Image) -> set[tuple[int, ...]]:
    """The distinct opaque RGB colours of an RGBA image."""
    data = image.tobytes()
    pixels = zip(data[0::4], data[1::4], data[2::4], data[3::4], strict=True)
    return {(r, g, b) for r, g, b, a in pixels if a == 255}


def inked_colours(image: Image.Image) -> set[tuple[int, ...]]:
    """The distinct RGB colours of every pixel with any ink."""
    data = image.tobytes()
    pixels = zip(data[0::4], data[1::4], data[2::4], data[3::4], strict=True)
    return {(r, g, b) for r, g, b, a in pixels if a}


class TestLabel:
    def test_height_is_moviepys_formula(self) -> None:
        # ascent + descent + twice the stroke + one pitch per further line.
        size, stroke, interline = 48, 3, 4
        pillow = ImageFont.truetype(str(font_path("amiri")), size)
        ascent, descent = pillow.getmetrics()
        a_bottom = pillow.getbbox("A", stroke_width=stroke)[3]
        pitch = a_bottom + stroke + interline
        for lines in (1, 2, 3):
            image = khatt.caption_image(
                "\n".join(["Khatt"] * lines), font_size=size, stroke_width=stroke
            )
            expected = ascent + descent + 2 * stroke + (lines - 1) * pitch
            assert abs(image.size[1] - expected) <= lines - 1, (lines, image.size)

    def test_width_is_the_ink_width(self) -> None:
        image = khatt.caption_image("مرحبا بالعالم", font_size=48)
        box = alpha_box(image)
        assert (box[0], box[2]) == (0, image.size[0])

    @pytest.mark.parametrize("text", [VOCALIZED, "Hyp gjq", "سطر أول\nسطر ثانٍ", "Khatt خط 2026"])
    @pytest.mark.parametrize("stroke", [0, 4])
    def test_nothing_is_cut_off(self, text: str, stroke: int) -> None:
        image = khatt.caption_image(text, font_size=48, stroke_width=stroke, stroke_color="red")
        on_canvas = khatt.draw_text(
            Image.new("RGBA", (1200, 600), (0, 0, 0, 0)),
            (100, 200),
            text,
            size_px=48,
            fill="black",
            spacing=4,
            stroke_width=stroke,
            stroke_fill="red",
        )
        assert alpha_sum(image) == alpha_sum(on_canvas)

    def test_room_above_and_below_like_moviepy(self) -> None:
        # Text without tall marks or descenders keeps the ascent and descent
        # moviepy reserves, so captions of one size line up.
        image = khatt.caption_image("ama", font_size=60)
        box = alpha_box(image)
        assert box[1] > 0
        assert box[3] < image.size[1]

    def test_tall_marks_grow_the_image(self) -> None:
        plain = khatt.caption_image("للّٰه", font_size=60, keep_tashkeel=False)
        marked = khatt.caption_image("للّٰه", font_size=60)
        assert marked.size[1] >= plain.size[1]
        assert alpha_box(marked)[1] >= 0

    def test_empty_text(self) -> None:
        image = khatt.caption_image("", font_size=40)
        assert image.size[0] == 1
        assert image.getchannel("A").getbbox() is None


class TestAlignment:
    TEXT = "سطر أول طويل جدا\nقصير"

    def test_right_to_left_lines_align_right_by_default(self) -> None:
        long, short = line_boxes(khatt.caption_image(self.TEXT, font_size=40))
        assert abs(long[2] - short[2]) <= 1
        assert short[0] > long[0] + 50

    def test_left_to_right_lines_align_left_by_default(self) -> None:
        long, short = line_boxes(khatt.caption_image("A long first line\nshort", font_size=40))
        assert abs(long[0] - short[0]) <= 2

    @pytest.mark.parametrize("align", ["left", "center", "right"])
    def test_text_align(self, align: str) -> None:
        long, short = line_boxes(khatt.caption_image(self.TEXT, font_size=40, text_align=align))
        if align == "left":
            assert abs(long[0] - short[0]) <= 1
        elif align == "right":
            assert abs(long[2] - short[2]) <= 1
        else:
            assert abs((short[0] - long[0]) - (long[2] - short[2])) <= 2

    @pytest.mark.parametrize("horizontal", ["left", "center", "right"])
    @pytest.mark.parametrize("vertical", ["top", "center", "bottom"])
    def test_placement_in_a_larger_area(self, horizontal: str, vertical: str) -> None:
        fitted = khatt.caption_image("مرحبا", font_size=40)
        image = khatt.caption_image(
            "مرحبا",
            font_size=40,
            size=(400, 200),
            horizontal_align=horizontal,
            vertical_align=vertical,
        )
        assert image.size == (400, 200)
        x0, y0, _, _ = alpha_box(image)
        fx0, fy0, _, _ = alpha_box(fitted)
        expected_x = {
            "left": 0,
            "center": (400 - fitted.size[0]) // 2,
            "right": 400 - fitted.size[0],
        }
        expected_y = {
            "top": 0,
            "center": (200 - fitted.size[1]) // 2,
            "bottom": 200 - fitted.size[1],
        }
        assert x0 - fx0 == expected_x[horizontal]
        assert y0 - fy0 == expected_y[vertical]


class TestCaption:
    TEXT = "تُمنح هذه الشهادة إلى الطالب المتميز تقديرا لجهوده الكبيرة في العام الدراسي"

    def test_wraps_to_the_width(self) -> None:
        image = khatt.caption_image(self.TEXT, font_size=36, method="caption", size=(420, None))
        single_line = khatt.caption_image(self.TEXT, font_size=36)
        assert single_line.size[0] > 2 * 420
        assert image.size[0] == 420
        assert image.size[1] > single_line.size[1] + 2 * 36  # three lines or more
        box = alpha_box(image)
        assert box[0] >= 0 and box[2] <= 420

    def test_outline_fits_the_width_too(self) -> None:
        image = khatt.caption_image(
            self.TEXT, font_size=36, method="caption", size=(420, None), stroke_width=6
        )
        box = alpha_box(image)
        assert box[0] >= 0 and box[2] <= 420

    def test_picks_the_largest_size_that_fits(self) -> None:
        image = khatt.caption_image(self.TEXT, method="caption", size=(420, 300))
        assert image.size == (420, 300)
        path = font_path("amiri")

        def extent(size: int) -> tuple[int, int]:
            measured = _measure(
                self.TEXT,
                path,
                size,
                max_width=420,
                align=None,
                interline=4,
                stroke_width=0,
                keep_tashkeel=True,
            )
            return measured.width, measured.height

        fitted = [
            size for size in range(8, 120) if extent(size)[0] <= 420 and extent(size)[1] <= 300
        ]
        best = max(fitted)
        bigger = extent(best + 1)
        assert bigger[0] > 420 or bigger[1] > 300
        drawn = alpha_box(image)
        assert drawn[3] - drawn[1] > 150  # it fills the box

    def test_a_box_too_small_for_any_size_gets_the_smallest(self) -> None:
        image = khatt.caption_image("مرحبا", method="caption", size=(10, 1))
        assert image.size == (10, 1)

    def test_label_with_a_width_picks_the_size(self) -> None:
        image = khatt.caption_image("مرحبا بالعالم", size=(300, None))
        assert image.size[0] == 300
        box = alpha_box(image)
        assert box[2] - box[0] > 280


class TestOptions:
    def test_margins(self) -> None:
        plain = khatt.caption_image("مرحبا", font_size=40)
        two = khatt.caption_image("مرحبا", font_size=40, margin=(10, 20))
        four = khatt.caption_image("مرحبا", font_size=40, margin=(1, 2, 3, 4))
        assert two.size == (plain.size[0] + 20, plain.size[1] + 40)
        assert four.size == (plain.size[0] + 4, plain.size[1] + 6)
        assert alpha_box(four)[:2] == (alpha_box(plain)[0] + 1, alpha_box(plain)[1] + 2)

    def test_background_and_transparency(self) -> None:
        clear = khatt.caption_image("مرحبا", font_size=40, color="white")
        assert clear.mode == "RGBA"
        assert clear.getpixel((0, 0)) == (0, 0, 0, 0)
        filled = khatt.caption_image("مرحبا", font_size=40, bg_color="navy", color="white")
        assert filled.getpixel((0, 0)) == (0, 0, 128, 255)
        opaque = khatt.caption_image("مرحبا", font_size=40, transparent=False, color="white")
        assert opaque.mode == "RGB"
        assert opaque.getpixel((0, 0)) == (0, 0, 0)

    def test_outline_colour(self) -> None:
        image = khatt.caption_image(
            "مرحبا", font_size=60, color="white", stroke_color="black", stroke_width=3
        )
        opaque = colours(image)
        assert (255, 255, 255) in opaque
        assert (0, 0, 0) in opaque

    def test_outline_without_a_colour_is_bolder_text(self) -> None:
        plain = khatt.caption_image("مرحبا", font_size=60, color="white")
        bold = khatt.caption_image("مرحبا", font_size=60, color="white", stroke_width=3)
        assert inked_colours(bold) == {(255, 255, 255)}
        assert alpha_sum(bold) > alpha_sum(plain)

    def test_interline_is_pillows_spacing(self) -> None:
        tight = line_boxes(khatt.caption_image("خط\nخط", font_size=40, interline=0))
        loose = line_boxes(khatt.caption_image("خط\nخط", font_size=40, interline=30))
        assert (loose[1][1] - loose[0][1]) - (tight[1][1] - tight[0][1]) == 30

    def test_font_file_and_default_font(self) -> None:
        by_name = khatt.caption_image("مرحبا", font="amiri", font_size=40)
        by_none = khatt.caption_image("مرحبا", font=None, font_size=40)
        by_path = khatt.caption_image("مرحبا", font=Path(font_path("amiri")), font_size=40)
        assert by_name.tobytes() == by_none.tobytes() == by_path.tobytes()

    def test_identical_with_raqm_reported_on_and_off(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def forbidden(*args: object, **kwargs: object) -> None:
            raise AssertionError("Pillow's text layout was used")

        monkeypatch.setattr(ImageDraw.ImageDraw, "text", forbidden)
        monkeypatch.setattr(ImageFont, "truetype", forbidden)
        real_check = features.check
        outputs = []
        for raqm in (True, False):
            monkeypatch.setattr(
                features,
                "check",
                lambda name, raqm=raqm: raqm if name == "raqm" else real_check(name),
            )
            outputs.append(khatt.caption_image(VOCALIZED + "\nKhatt", font_size=40).tobytes())
        assert outputs[0] == outputs[1]

    def test_deterministic(self) -> None:
        first = khatt.caption_image(VOCALIZED, font_size=33, stroke_width=2)
        second = khatt.caption_image(VOCALIZED, font_size=33, stroke_width=2)
        assert ImageChops.difference(first, second).getbbox() is None


class TestErrors:
    @pytest.mark.parametrize(
        ("kwargs", "match"),
        [
            ({"method": "paragraph"}, "method"),
            ({"method": "caption", "font_size": 40}, "width"),
            ({"method": "caption", "size": (300, None)}, "height"),
            ({}, "font_size"),
            ({"font_size": 40, "margin": (1, 2, 3)}, "margin"),
            ({"font_size": 40, "text_align": "justify"}, "text_align"),
            ({"font_size": 40, "horizontal_align": "middle"}, "horizontal_align"),
            ({"font_size": 40, "vertical_align": "middle"}, "vertical_align"),
            ({"font_size": 0}, "font_size"),
            ({"font_size": 40, "size": (0, None)}, "width"),
            ({"font_size": 40, "interline": float("nan")}, "interline"),
            ({"font_size": 40, "stroke_width": -1}, "stroke_width"),
            ({"font_size": 40, "color": "no-such-colour"}, "colour|color"),
        ],
    )
    def test_bad_arguments(self, kwargs: dict[str, Any], match: str) -> None:
        with pytest.raises(ValueError, match=match):
            khatt.caption_image("خط", **kwargs)
