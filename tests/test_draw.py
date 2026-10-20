"""Pixel-level tests for drawing shaped text onto Pillow images."""

from __future__ import annotations

import warnings
from collections.abc import Callable, Iterator
from typing import Any

import pytest
from PIL import Image, ImageChops, ImageDraw, ImageFont, features

import khatt
from khatt.draw import _largest_fitting
from khatt.fonts import font_path
from khatt.layout import layout_block, line_pitch, measure_block
from khatt.raster import compose_block, estimate
from khatt.shaping import shape, units_per_em, vertical_metrics

WHITE = (255, 255, 255)
CLEAR = (0, 0, 0, 0)

Box = tuple[int, int, int, int]


def blank(size: tuple[int, int] = (600, 300), color: tuple[int, ...] = WHITE) -> Image.Image:
    return Image.new("RGBA" if len(color) == 4 else "RGB", size, color)


def ink(image: Image.Image, background: tuple[int, ...] = WHITE) -> Box:
    """Bounding box of every pixel that differs from the background."""
    difference = ImageChops.difference(image, Image.new(image.mode, image.size, background))
    box = difference.getbbox(alpha_only=False)
    assert box is not None, "nothing was drawn"
    return box


def band_ink(image: Image.Image, top: int, bottom: int) -> Box:
    """Ink box of the rows ``top`` to ``bottom``, in image coordinates."""
    x0, y0, x1, y1 = ink(image.crop((0, top, image.size[0], bottom)))
    return x0, y0 + top, x1, y1 + top


def pixels(image: Image.Image) -> Iterator[tuple[int, ...]]:
    width, height = image.size
    data = image.load()
    assert data is not None
    for y in range(height):
        for x in range(width):
            pixel = data[x, y]
            assert isinstance(pixel, tuple)
            yield pixel


class TestPlacement:
    def test_draws_in_place_and_returns_the_image(self) -> None:
        image = blank()
        assert khatt.draw_text(image, (20, 20), "مرحبا") is image
        ink(image)

    @pytest.mark.parametrize(
        ("anchor", "check"),
        [
            ("la", lambda box: box[0] == 300),
            ("ra", lambda box: box[2] == 300),
            ("ma", lambda box: abs((box[0] + box[2]) / 2 - 300) <= 1),
            ("lt", lambda box: box[1] == 150),
            ("lb", lambda box: box[3] == 150),
            ("lm", lambda box: box[1] < 150 < box[3]),
            ("ls", lambda box: box[1] < 150 < box[3]),  # ر descends below the baseline
        ],
    )
    def test_anchor(self, anchor: str, check: Callable[[Box], bool]) -> None:
        image = khatt.draw_text(blank(), (300, 150), "مرحبا", anchor=anchor)
        assert check(ink(image)), (anchor, ink(image))

    def test_baseline_and_ascender_anchors(self) -> None:
        path = font_path("rubik")
        size = 60
        on_baseline = ink(
            khatt.draw_text(blank(), (20, 150), "HHH", font="rubik", size_px=size, anchor="ls")
        )
        assert abs(on_baseline[3] - 150) <= 1  # "H" sits on the baseline
        below_ascender = ink(
            khatt.draw_text(blank(), (20, 150), "HHH", font="rubik", size_px=size, anchor="la")
        )
        ascender, descender = vertical_metrics(path)
        scale = size / units_per_em(path)
        assert abs(below_ascender[3] - on_baseline[3] - round(ascender * scale)) <= 1
        above_descender = ink(
            khatt.draw_text(blank(), (20, 150), "HHH", font="rubik", size_px=size, anchor="ld")
        )
        assert abs(on_baseline[3] - above_descender[3] + round(descender * scale)) <= 1

    def test_text_partly_outside_the_image_is_clipped(self) -> None:
        image = khatt.draw_text(blank((100, 100)), (-40, -10), "مرحبا بالعالم", size_px=60)
        assert ink(image)[0] == 0

    def test_nothing_to_draw_leaves_the_image_unchanged(self) -> None:
        for text in ("", "   ", "\n\n"):
            image = blank()
            khatt.draw_text(image, (10, 10), text)
            assert image.tobytes() == blank().tobytes()

    def test_invisible_text_leaves_the_image_unchanged(self) -> None:
        off_image = khatt.draw_text(blank(), (5000, 10), "مرحبا")
        transparent = khatt.draw_text(blank(), (10, 10), "مرحبا", fill=(0, 0, 0, 0))
        assert off_image.tobytes() == transparent.tobytes() == blank().tobytes()

    def test_empty_lines_keep_their_slot(self) -> None:
        def bottom(text: str) -> int:
            image = khatt.draw_text(blank((300, 400)), (150, 20), text, anchor="ma", size_px=40)
            return ink(image)[3]

        pitch = round(1.2 * 40)
        assert bottom("خط\n\nخط") - bottom("خط\nخط") == pitch


class TestAlignment:
    # Baselines 2 em apart, so each line can be cropped to a band of its own.
    SIZE = 40
    PITCH = 2 * SIZE

    def lines(self, text: str, **kwargs: Any) -> tuple[Image.Image, list[Box]]:
        image = khatt.draw_text(
            blank((600, 400)),
            (300, 60),
            text,
            size_px=self.SIZE,
            line_spacing=2.0,
            anchor="ms",
            **kwargs,
        )
        count = text.count("\n") + 1
        boxes = [
            band_ink(image, 60 + i * self.PITCH - self.SIZE, 60 + i * self.PITCH + self.SIZE)
            for i in range(count)
        ]
        return image, boxes

    def test_rtl_paragraphs_align_right(self) -> None:
        _, boxes = self.lines("مرحبا بالعالم\nأهلا")
        assert abs(boxes[0][2] - boxes[1][2]) <= 1
        assert boxes[1][0] > boxes[0][0] + 20  # the short line is indented

    def test_ltr_paragraphs_align_left(self) -> None:
        _, boxes = self.lines("Hello world\nHi")
        assert abs(boxes[0][0] - boxes[1][0]) <= 1
        assert boxes[1][2] < boxes[0][2] - 20

    def test_mixed_paragraphs_align_by_their_own_direction(self) -> None:
        image, boxes = self.lines("Hello world, again\nمرحبا")
        whole = ink(image)
        assert abs(boxes[0][0] - whole[0]) <= 1
        assert abs(boxes[1][2] - whole[2]) <= 1

    @pytest.mark.parametrize("align", ["left", "right", "center"])
    def test_explicit_alignment(self, align: str) -> None:
        _, (long, short) = self.lines("مرحبا بالعالم\nأهلا", align=align)
        if align == "left":
            assert abs(long[0] - short[0]) <= 1
        elif align == "right":
            assert abs(long[2] - short[2]) <= 1
        else:
            assert abs((long[0] + long[2]) - (short[0] + short[2])) <= 2

    def test_max_width_wraps(self) -> None:
        text = "السلام عليكم ورحمة الله وبركاته"
        one_line = ink(khatt.draw_text(blank((900, 400)), (880, 20), text, anchor="ra"))
        wrapped = ink(
            khatt.draw_text(blank((900, 400)), (880, 20), text, anchor="ra", max_width=250)
        )
        assert wrapped[2] - wrapped[0] <= 250
        assert one_line[2] - one_line[0] > 250
        assert wrapped[3] - wrapped[1] > 2 * (one_line[3] - one_line[1])


class TestColor:
    def test_fill_colour_is_applied(self) -> None:
        image = khatt.draw_text(blank(), (20, 20), "مرحبا", fill="red")
        changed = [p for p in pixels(image) if p != WHITE]
        assert changed
        assert (255, 0, 0) in changed  # fully covered pixels
        assert all(r == 255 and g == b for r, g, b in changed)  # white→red blends only

    @pytest.mark.parametrize("fill", ["#00ff00", (0, 255, 0), (0, 255, 0, 255), "lime"])
    def test_fill_formats(self, fill: khatt.draw.Fill) -> None:
        image = khatt.draw_text(blank(), (20, 20), "خط", fill=fill)
        assert (0, 255, 0) in set(pixels(image))

    def test_translucent_fill_on_rgb(self) -> None:
        image = khatt.draw_text(blank(), (20, 20), "خط", fill=(0, 0, 0, 128))
        darkest = min(p[0] for p in pixels(image))
        assert abs(darkest - 127) <= 1


class TestRGBA:
    def test_transparent_background_stays_transparent(self) -> None:
        image = khatt.draw_text(blank(color=CLEAR), (20, 20), "مرحبا", fill=(0, 0, 255))
        drawn = [p for p in pixels(image) if p != CLEAR]
        assert drawn
        assert all(p[3] > 0 for p in drawn)  # untouched pixels are exactly CLEAR
        assert max(p[3] for p in drawn) == 255
        # Edges are blue at partial alpha, not darkened towards the black backdrop.
        assert all(abs(p[0]) <= 1 and abs(p[1]) <= 1 and abs(p[2] - 255) <= 1 for p in drawn)

    def test_background_alpha_is_preserved_around_the_text(self) -> None:
        background = (255, 255, 255, 128)
        image = khatt.draw_text(blank(color=background), (20, 20), "مرحبا", fill="black")
        box = ink(image, background)
        outside = [
            p
            for y in range(image.size[1])
            for x in range(image.size[0])
            if not (box[0] <= x < box[2] and box[1] <= y < box[3])
            for p in [image.getpixel((x, y))]
        ]
        assert set(outside) == {background}
        assert (0, 0, 0, 255) in set(pixels(image))

    def test_translucent_fill_on_rgba(self) -> None:
        image = khatt.draw_text(blank(color=CLEAR), (20, 20), "خط", fill=(255, 0, 0, 100))
        assert max(p[3] for p in pixels(image)) == 100


class TestNoPillowTextLayout:
    """draw_text never touches Pillow's text stack, so Raqm can't change its output."""

    TEXT = "بِسْمِ اللَّهِ\nKhatt 2026 مرحبا"

    def render(self) -> bytes:
        image = khatt.draw_text(blank((700, 260)), (680, 20), self.TEXT, anchor="ra")
        khatt.overlay(image, "شهادة تقدير", (20, 140, 400, 250))
        return image.tobytes()

    @staticmethod
    def forbid_pillow_text(monkeypatch: pytest.MonkeyPatch) -> None:
        def forbidden(*args: object, **kwargs: object) -> None:
            raise AssertionError("Pillow's text layout was used")

        monkeypatch.setattr(ImageDraw.ImageDraw, "text", forbidden)
        monkeypatch.setattr(ImageDraw.ImageDraw, "multiline_text", forbidden)
        monkeypatch.setattr(ImageFont, "truetype", forbidden)
        monkeypatch.setattr(ImageFont.FreeTypeFont, "__init__", forbidden)

    def test_identical_output_with_raqm_reported_on_and_off(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self.forbid_pillow_text(monkeypatch)
        real_check = features.check
        outputs = []
        for raqm in (True, False):
            monkeypatch.setattr(
                features,
                "check",
                lambda name, raqm=raqm: raqm if name == "raqm" else real_check(name),
            )
            outputs.append(self.render())
        assert outputs[0] == outputs[1]

    @pytest.mark.skipif(not features.check("raqm"), reason="this Pillow has no Raqm")
    def test_real_raqm_changes_nothing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        with_raqm = self.render()
        self.forbid_pillow_text(monkeypatch)
        assert self.render() == with_raqm


class TestQuality:
    @pytest.mark.parametrize("size", [9, 14, 24, 48, 131])
    @pytest.mark.parametrize("text", ["مرحبا", "بِسْمِ اللَّهِ", "Khatt 3arabi", "لا إله"])
    def test_estimate_contains_the_drawn_ink(self, size: int, text: str) -> None:
        path = font_path("amiri")
        glyphs = shape(text, path, keep_tashkeel=True)
        box = estimate(glyphs, path, ppem=size)
        block = compose_block([glyphs], path, ppem=size, pitch=size)
        assert box is not None
        assert block is not None
        width, height = block.mask.size
        assert box[2] - box[0] >= width
        assert box[1] <= block.top
        assert box[3] >= block.top + height
        assert box[2] - box[0] <= width + 4  # and stays tight

    def test_keep_tashkeel(self) -> None:
        voweled = "مَرْحَبًا"
        kept = khatt.draw_text(blank(), (20, 20), voweled, keep_tashkeel=True)
        stripped = khatt.draw_text(blank(), (20, 20), voweled, keep_tashkeel=False)
        assert kept.tobytes() != stripped.tobytes()
        plain = khatt.draw_text(blank(), (20, 20), "مرحبا")
        assert stripped.tobytes() == plain.tobytes()

    def test_deterministic(self) -> None:
        first = khatt.draw_text(blank(), (20, 20), "القاهرة 2026", size_px=31).tobytes()
        assert khatt.draw_text(blank(), (20, 20), "القاهرة 2026", size_px=31).tobytes() == first


class TestDrawTextErrors:
    @pytest.mark.parametrize(
        ("kwargs", "match"),
        [
            ({"anchor": "xx"}, "anchor"),
            ({"anchor": "l"}, "anchor"),
            ({"align": "justify"}, "align"),
            ({"size_px": 0}, "size_px"),
            ({"line_spacing": 0}, "line_spacing"),
            ({"max_width": 0}, "max_width"),
            ({"fill": "not-a-colour"}, "colour|color"),
            ({"fill": (300, 0, 0)}, "fill"),
            ({"fill": (1, 2)}, "fill"),
            ({"fill": 5}, "fill"),
        ],
    )
    def test_bad_arguments(self, kwargs: dict[str, Any], match: str) -> None:
        with pytest.raises(ValueError, match=match):
            khatt.draw_text(blank(), (0, 0), "خط", **kwargs)

    def test_unsupported_image_mode(self) -> None:
        with pytest.raises(ValueError, match="RGB or RGBA"):
            khatt.draw_text(Image.new("L", (50, 50)), (0, 0), "خط")

    def test_unknown_font(self) -> None:
        with pytest.raises(KeyError):
            khatt.draw_text(blank(), (0, 0), "خط", font="nope")


class TestOverlay:
    BOX = (50, 40, 450, 200)

    def inner(self, padding: int = 0) -> Box:
        left, top, right, bottom = self.BOX
        return left + padding, top + padding, right - padding, bottom - padding

    def assert_inside(self, box: Box, bounds: Box) -> None:
        assert box[0] >= bounds[0]
        assert box[1] >= bounds[1]
        assert box[2] <= bounds[2]
        assert box[3] <= bounds[3]

    @pytest.mark.parametrize(
        "text",
        [
            "شهادة",
            "شهادة تقدير",
            "تُمنح هذه الشهادة إلى الطالب المتميز تقديرا لجهوده الكبيرة في العام الدراسي",
            "سطر أول\nسطر ثاني\nسطر ثالث",
            "Mohammed Essam محمد عصام",
            "Supercalifragilisticexpialidocious",
        ],
    )
    @pytest.mark.parametrize("padding", [0, 12])
    def test_shrink_never_overflows(self, text: str, padding: int) -> None:
        image = blank()
        with warnings.catch_warnings():
            warnings.simplefilter("error", khatt.TextOverflowWarning)
            khatt.overlay(image, text, self.BOX, padding=padding)
        drawn = ink(image)
        inner = self.inner(padding)
        self.assert_inside(drawn, inner)
        # ... and picks a size that fills the box in at least one direction.
        fill_ratio = max(
            (drawn[2] - drawn[0]) / (inner[2] - inner[0]),
            (drawn[3] - drawn[1]) / (inner[3] - inner[1]),
        )
        assert fill_ratio > 0.8, fill_ratio

    @pytest.mark.parametrize(
        ("text", "box"),
        [
            ("خط", (400, 160)),
            ("خط " * 12, (400, 160)),
            ("خط " * 12, (120, 300)),
            ("مرحبا بالعالم\nKhatt", (250, 90)),
        ],
    )
    def test_shrink_picks_the_largest_size_that_fits(self, text: str, box: tuple[int, int]) -> None:
        path = font_path("amiri")
        size = _largest_fitting(
            text, path, sizes=(8, 300), box=box, line_spacing=1.2, keep_tashkeel=True
        )

        def extent(size: int) -> tuple[int, int]:
            measured = measure_block(
                text, path, size_px=size, max_width=box[0], line_spacing=1.2, keep_tashkeel=True
            )
            assert measured is not None
            return measured

        width, height = extent(size)
        assert width <= box[0]
        assert height <= box[1]
        width, height = extent(size + 1)
        assert width > box[0] or height > box[1]

    def test_shrink_gives_longer_text_smaller_letters(self) -> None:
        path = font_path("amiri")
        short, long = (
            _largest_fitting(
                text, path, sizes=(8, 300), box=(400, 160), line_spacing=1.2, keep_tashkeel=True
            )
            for text in ("خط", "خط " * 12)
        )
        assert long < short

    def test_default_alignment_follows_the_direction(self) -> None:
        rtl = ink(khatt.overlay(blank(), "مرحبا", self.BOX, max_size_px=40))
        ltr = ink(khatt.overlay(blank(), "Hello", self.BOX, max_size_px=40))
        assert abs(rtl[2] - self.BOX[2]) <= 1
        assert abs(ltr[0] - self.BOX[0]) <= 1

    @pytest.mark.parametrize("align", ["left", "right", "center"])
    def test_explicit_alignment(self, align: str) -> None:
        box = ink(khatt.overlay(blank(), "مرحبا", self.BOX, max_size_px=40, align=align))
        left, _, right, _ = self.BOX
        if align == "left":
            assert abs(box[0] - left) <= 1
        elif align == "right":
            assert abs(box[2] - right) <= 1
        else:
            assert abs((box[0] - left) - (right - box[2])) <= 2

    @pytest.mark.parametrize("valign", ["top", "middle", "bottom"])
    def test_vertical_alignment(self, valign: str) -> None:
        box = ink(khatt.overlay(blank(), "مرحبا", self.BOX, max_size_px=40, valign=valign))
        _, top, _, bottom = self.BOX
        if valign == "top":
            assert box[1] == top
        elif valign == "bottom":
            assert box[3] == bottom
        else:
            assert abs((box[1] - top) - (bottom - box[3])) <= 1

    def test_wrap_keeps_the_size_and_wraps(self) -> None:
        text = "السلام عليكم ورحمة الله وبركاته"
        unwrapped = ink(khatt.draw_text(blank((900, 300)), (10, 100), text, size_px=40))
        assert unwrapped[2] - unwrapped[0] > 300  # too wide for the box below
        box = (50, 40, 350, 260)
        image = khatt.overlay(blank(), text, box, fit="wrap", max_size_px=40)
        drawn = ink(image)
        self.assert_inside(drawn, box)
        pitch = 1.2 * 40
        assert drawn[3] - drawn[1] > unwrapped[3] - unwrapped[1] + pitch / 2

    def test_none_overflows_with_a_warning_and_clips_to_the_box(self) -> None:
        image = blank()
        text = "نص طويل جدا لا يتسع داخل الصندوق مهما حاولنا"
        with pytest.warns(khatt.TextOverflowWarning):
            khatt.overlay(image, text, self.BOX, fit="none", max_size_px=60)
        drawn = ink(image)
        self.assert_inside(drawn, self.BOX)
        # Right-to-left text overflows on the left, keeping its start visible.
        assert abs(drawn[2] - self.BOX[2]) <= 1
        assert drawn[0] == self.BOX[0]

    def test_shrink_warns_when_even_the_minimum_does_not_fit(self) -> None:
        image = blank()
        with pytest.warns(khatt.TextOverflowWarning):
            khatt.overlay(image, "خط " * 200, self.BOX, min_size_px=30)
        self.assert_inside(ink(image), self.BOX)

    def test_on_rgba(self) -> None:
        image = khatt.overlay(blank(color=CLEAR), "مرحبا", self.BOX, fill="navy")
        self.assert_inside(ink(image, CLEAR), self.BOX)

    def test_nothing_to_draw(self) -> None:
        image = blank()
        khatt.overlay(image, " ", self.BOX)
        assert image.tobytes() == blank().tobytes()

    @pytest.mark.parametrize(
        ("kwargs", "match"),
        [
            ({"fit": "stretch"}, "fit"),
            ({"valign": "center"}, "valign"),
            ({"padding": -1}, "padding"),
            ({"padding": 80}, "room"),
            ({"max_size_px": 0}, "max_size_px"),
            ({"min_size_px": 0}, "min_size_px"),
            ({"max_size_px": 10, "min_size_px": 20}, "min_size_px"),
            ({"align": "justify"}, "align"),
        ],
    )
    def test_bad_arguments(self, kwargs: dict[str, Any], match: str) -> None:
        with pytest.raises(ValueError, match=match):
            khatt.overlay(blank(), "خط", self.BOX, **kwargs)


class TestStroke:
    TEXT = "مرحبا بالعالم"
    RED = (255, 0, 0)

    def draw(self, **kwargs: Any) -> Image.Image:
        image = blank()
        khatt.draw_text(image, (580, 40), self.TEXT, anchor="ra", size_px=80, **kwargs)
        return image

    @pytest.mark.parametrize("width", [1, 3, 6])
    def test_outline_grows_the_ink_by_its_width(self, width: int) -> None:
        plain = ink(self.draw())
        stroked = ink(self.draw(stroke_width=width, stroke_fill="red"))
        for side, grows in zip(range(4), (-1, -1, 1, 1), strict=True):
            assert abs((stroked[side] - plain[side]) * grows - width) <= 1, (side, plain, stroked)

    def test_outline_does_not_move_the_text(self) -> None:
        # Every fully opaque text pixel is drawn in exactly the same place:
        # the outline grows around the text and under it, never moving it.
        def solid_text(image: Image.Image) -> set[tuple[int, int]]:
            width = image.size[0]
            return {(i % width, i // width) for i, p in enumerate(pixels(image)) if p == (0, 0, 0)}

        plain = solid_text(self.draw())
        stroked = solid_text(self.draw(stroke_width=4, stroke_fill="red"))
        assert plain
        assert plain == stroked

    def test_text_is_painted_over_its_outline(self) -> None:
        image = self.draw(stroke_width=4, stroke_fill="red")
        colours = set(pixels(image))
        assert (0, 0, 0) in colours
        assert self.RED in colours

    def test_stroke_fill_defaults_to_fill(self) -> None:
        # Like Pillow: an outline in the text colour just makes it bolder.
        bolder = self.draw(fill="navy", stroke_width=3)
        plain = self.draw(fill="navy")
        assert self.RED not in set(pixels(bolder))
        assert ink(bolder)[2] - ink(bolder)[0] > ink(plain)[2] - ink(plain)[0]

    def test_zero_width_draws_no_outline(self) -> None:
        assert self.draw(stroke_width=0, stroke_fill="red").tobytes() == self.draw().tobytes()

    def test_matches_pillows_outline_on_latin_text(self) -> None:
        # Amiri is a static font, so Pillow and khatt render the same instance.
        size, width, text = 90, 5, "Khatt"
        pillow = blank()
        font = ImageFont.truetype(str(font_path("amiri")), size)
        ImageDraw.Draw(pillow).text((40, 40), text, font=font, fill="black", stroke_width=width)
        ours = blank()
        khatt.draw_text(ours, (40, 40), text, font="amiri", size_px=size, stroke_width=width)
        (px0, py0, px1, py1), (kx0, ky0, kx1, ky1) = ink(pillow), ink(ours)
        assert abs((px1 - px0) - (kx1 - kx0)) <= 2
        assert abs((py1 - py0) - (ky1 - ky0)) <= 2

    def test_translucent_outline_on_rgba(self) -> None:
        image = blank(color=CLEAR)
        khatt.draw_text(
            image,
            (20, 20),
            "خط",
            size_px=80,
            fill="white",
            stroke_width=4,
            stroke_fill=(0, 0, 0, 128),
        )
        alphas = {p[3] for p in pixels(image)}
        assert 0 in alphas  # background stays transparent
        assert 255 in alphas  # the opaque text
        assert any(0 < a < 255 for a in alphas)  # the half-transparent outline

    @staticmethod
    def stem_row(**kwargs: Any) -> list[tuple[int, ...]]:
        """The pixels across the stem of a large translucent "I", edge to edge."""
        image = blank((400, 500))
        khatt.draw_text(
            image, (100, 20), "I", size_px=400, fill=(0, 0, 255, 128), stroke_width=4, **kwargs
        )
        row = [image.getpixel((x, 250)) for x in range(image.size[0])]
        inked = [x for x, p in enumerate(row) if p != WHITE]
        return [p for p in row[inked[0] : inked[-1] + 1] if isinstance(p, tuple)]

    def test_outline_is_filled_under_translucent_text(self) -> None:
        # The outline covers the whole letter, as Pillow's does, so a
        # translucent fill shows the outline colour evenly, with no ring.
        row = self.stem_row(stroke_fill=(255, 0, 0))
        inside = row[8:-8]
        assert set(inside) == {(127, 0, 128)}

    def test_same_colour_outline_is_one_coat(self) -> None:
        # Text and outline in one colour are painted once: a second coat would
        # darken a translucent fill where they overlap.
        row = self.stem_row()
        assert set(row[4:-4]) == {(127, 127, 255)}

    @pytest.mark.parametrize(
        ("kwargs", "match"),
        [
            ({"stroke_width": -1}, "stroke_width"),
            ({"stroke_width": float("inf")}, "stroke_width"),
            ({"stroke_width": 2, "stroke_fill": "no-such-colour"}, "colour|color"),
        ],
    )
    def test_bad_arguments(self, kwargs: dict[str, Any], match: str) -> None:
        with pytest.raises(ValueError, match=match):
            khatt.draw_text(blank(), (10, 10), "خط", **kwargs)


class TestOverlayStroke:
    BOX = (50, 40, 450, 200)

    @pytest.mark.parametrize(
        "text", ["شهادة", "شهادة تقدير للطالب المتميز", "سطر أول\nسطر ثاني", "Mohammed محمد"]
    )
    @pytest.mark.parametrize(("stroke", "padding"), [(3, 0), (8, 0), (6, 10)])
    def test_outline_stays_inside_the_padding(self, text: str, stroke: int, padding: int) -> None:
        image = blank()
        with warnings.catch_warnings():
            warnings.simplefilter("error", khatt.TextOverflowWarning)
            khatt.overlay(
                image, text, self.BOX, padding=padding, stroke_width=stroke, stroke_fill="red"
            )
        left, top, right, bottom = self.BOX
        x0, y0, x1, y1 = ink(image)
        assert x0 >= left + padding
        assert y0 >= top + padding
        assert x1 <= right - padding
        assert y1 <= bottom - padding

    def test_thicker_outline_means_smaller_text(self) -> None:
        def text_height(stroke: int) -> int:
            image = blank()
            khatt.overlay(
                image, "شهادة", self.BOX, fill="black", stroke_width=stroke, stroke_fill="white"
            )
            box = ImageChops.difference(image, blank()).getbbox()
            assert box is not None
            return box[3] - box[1]

        assert text_height(12) < text_height(0)

    def test_no_room_for_the_outline(self) -> None:
        with pytest.raises(ValueError, match="stroke"):
            khatt.overlay(blank(), "خط", (0, 0, 20, 20), stroke_width=10)


class TestTextBbox:
    @pytest.mark.parametrize(
        ("text", "kwargs"),
        [
            ("مرحبا", {}),
            ("مرحبا", {"anchor": "ms"}),
            ("بِسْمِ اللَّهِ الرَّحْمَنِ الرَّحِيمِ", {"anchor": "rd", "size_px": 37}),
            ("Khatt 2026 خط", {"anchor": "mm", "stroke_width": 4}),
            ("سطر أول\nسطر ثاني أطول\n\nبعد سطر فارغ", {"anchor": "ra", "align": "center"}),
            ("السلام عليكم ورحمة الله وبركاته", {"max_width": 260, "anchor": "lt"}),
            ("سطر أول\nسطر ثاني", {"spacing": 10, "stroke_width": 2.5, "anchor": "lb"}),
            ("مَرْحَبًا", {"keep_tashkeel": False, "line_spacing": 2.0}),
        ],
    )
    def test_is_exactly_what_draw_text_paints(self, text: str, kwargs: dict[str, Any]) -> None:
        xy = (450.3, 220.7)
        image = khatt.draw_text(blank((900, 500)), xy, text, stroke_fill="red", **kwargs)
        assert khatt.text_bbox(text, xy=xy, **kwargs) == ink(image)

    def test_moves_with_xy(self) -> None:
        x0, y0, x1, y1 = khatt.text_bbox("مرحبا بالعالم", size_px=31)
        assert khatt.text_bbox("مرحبا بالعالم", xy=(17, -5), size_px=31) == (
            x0 + 17,
            y0 - 5,
            x1 + 17,
            y1 - 5,
        )

    def test_nothing_to_draw_is_an_empty_box_at_xy(self) -> None:
        for text in ("", "   ", "\n"):
            assert khatt.text_bbox(text, xy=(10.4, 20.6)) == (10, 21, 10, 21)

    @pytest.mark.parametrize(("text", "anchor"), [("Khatt", "la"), ("Hello, world", "ms")])
    def test_close_to_pillows_textbbox_on_latin_text(self, text: str, anchor: str) -> None:
        font = ImageFont.truetype(str(font_path("amiri")), 60)
        pillow = ImageDraw.Draw(blank()).textbbox((300, 150), text, font=font, anchor=anchor)
        ours = khatt.text_bbox(text, xy=(300, 150), size_px=60, anchor=anchor)
        assert all(abs(a - b) <= 2 for a, b in zip(pillow, ours, strict=True)), (pillow, ours)

    def test_measures_words_for_wrapping(self) -> None:
        # The width of a line is the sum of its words' widths, and then some.
        words = ["تُمنح", "هذه", "الشهادة"]
        widths = [box[2] - box[0] for box in map(khatt.text_bbox, words)]
        line = khatt.text_bbox(" ".join(words))
        assert line[2] - line[0] > sum(widths)

    @pytest.mark.parametrize(
        ("kwargs", "match"),
        [
            ({"anchor": "xx"}, "anchor"),
            ({"size_px": 0}, "size_px"),
            ({"max_width": 0}, "max_width"),
            ({"stroke_width": -1}, "stroke_width"),
            ({"line_spacing": 1.5, "spacing": 4}, "not both"),
        ],
    )
    def test_bad_arguments(self, kwargs: dict[str, Any], match: str) -> None:
        with pytest.raises(ValueError, match=match):
            khatt.text_bbox("خط", **kwargs)


class TestSpacing:
    TEXT = "H\nH\nH"

    @staticmethod
    def line_tops(image: Image.Image) -> list[int]:
        """The top row of each separate run of inked rows."""
        rows = [
            ImageChops.difference(
                image.crop((0, y, image.size[0], y + 1)), blank((image.size[0], 1))
            ).getbbox()
            is not None
            for y in range(image.size[1])
        ]
        return [y for y, inked in enumerate(rows) if inked and (y == 0 or not rows[y - 1])]

    @pytest.mark.parametrize("font", ["amiri", "rubik"])
    @pytest.mark.parametrize("size", [19, 48, 90])
    @pytest.mark.parametrize(("spacing", "stroke"), [(0, 0), (4, 0), (17, 3), (-3, 2)])
    def test_matches_pillows_multiline_spacing(
        self, font: str, size: int, spacing: int, stroke: int
    ) -> None:
        pillow = blank((300, 600))
        ImageDraw.Draw(pillow).multiline_text(
            (20, 20),
            self.TEXT,
            font=ImageFont.truetype(str(font_path(font)), size),
            fill="black",
            spacing=spacing,
            stroke_width=stroke,
        )
        ours = khatt.draw_text(
            blank((300, 600)),
            (20, 20),
            self.TEXT,
            font=font,
            size_px=size,
            spacing=spacing,
            stroke_width=stroke,
        )
        theirs, mine = self.line_tops(pillow), self.line_tops(ours)
        assert len(theirs) == len(mine) == 3
        for line in (1, 2):
            pitch_theirs = theirs[line] - theirs[line - 1]
            pitch_mine = mine[line] - mine[line - 1]
            assert abs(pitch_theirs - pitch_mine) <= 1, (theirs, mine)

    def test_adds_pixels_between_lines(self) -> None:
        def bottom(spacing: float) -> int:
            box = khatt.text_bbox("خط\nخط\nخط", size_px=40, spacing=spacing)
            return box[3]

        assert bottom(25) - bottom(0) == 50
        assert bottom(-10) - bottom(0) == -20

    def test_outline_widens_the_spacing_by_twice_its_width(self) -> None:
        # As in Pillow, so neither line's outline eats into the spacing.
        def pitch(stroke: int) -> int:
            image = khatt.draw_text(
                blank(), (20, 20), self.TEXT, size_px=40, spacing=6, stroke_width=stroke
            )
            tops = self.line_tops(image)
            return tops[1] - tops[0]

        assert pitch(3) - pitch(0) == 2 * 3

    def test_line_spacing_is_unchanged_by_default(self) -> None:
        explicit = khatt.draw_text(blank(), (20, 20), "خط\nخط", line_spacing=1.2)
        default = khatt.draw_text(blank(), (20, 20), "خط\nخط")
        assert explicit.tobytes() == default.tobytes()

    @pytest.mark.parametrize("spacing", [0, 12, 40])
    def test_overlay_fits_spaced_lines(self, spacing: int) -> None:
        box = (50, 40, 450, 260)
        image = blank()
        with warnings.catch_warnings():
            warnings.simplefilter("error", khatt.TextOverflowWarning)
            khatt.overlay(image, "سطر أول\nسطر ثاني\nسطر ثالث", box, spacing=spacing)
        x0, y0, x1, y1 = ink(image)
        assert x0 >= box[0] and y0 >= box[1] and x1 <= box[2] and y1 <= box[3]

    def test_overlay_shrinks_more_with_more_spacing(self) -> None:
        def width(spacing: int) -> int:
            box = ink(
                khatt.overlay(blank(), "سطر أول\nسطر ثاني", (50, 40, 450, 260), spacing=spacing)
            )
            return box[2] - box[0]

        assert width(60) < width(0)

    def test_spacing_does_not_apply_to_a_single_line(self) -> None:
        # As in Pillow: with one line there is no gap for spacing to set.
        single = khatt.text_bbox("سطر", size_px=8, spacing=-20)
        assert single == khatt.text_bbox("سطر", size_px=8)
        assert khatt.text_bbox("", size_px=8, spacing=-20) == (0, 0, 0, 0)

    def test_overlay_shrink_with_negative_spacing(self) -> None:
        # -10 is too tight for the smallest sizes but fine for the size picked.
        box = (0, 0, 600, 300)
        image = khatt.overlay(blank(), "سطر أول\nسطر ثاني", box, spacing=-10)
        _, top, _, bottom = ink(image)
        assert bottom - top > 150

    @pytest.mark.parametrize("font", ["amiri", "rubik", "noto-naskh", "cairo"])
    @pytest.mark.parametrize("size", [19, 48, 91])
    def test_ascender_matches_pillow_and_the_pitch(self, font: str, size: int) -> None:
        # The "a" anchor and the spacing rule share one ascender: Pillow's.
        path = font_path(font)
        laid_out = layout_block(
            "خط", path, size_px=size, line_spacing=1.2, keep_tashkeel=True, spacing=0
        )
        assert laid_out is not None
        pillow_ascent = ImageFont.truetype(str(path), size).getmetrics()[0]
        assert -laid_out.ascender == pillow_ascent
        pitch = line_pitch(path, size_px=size, line_spacing=1.2, spacing=7)
        assert pitch == -laid_out.ascender + 7

    def test_numpy_numbers(self) -> None:
        np = pytest.importorskip("numpy")
        kwargs = {"spacing": np.int64(6), "stroke_width": np.float32(2.0)}
        assert khatt.text_bbox("خط\nخط", **kwargs) == khatt.text_bbox(
            "خط\nخط", spacing=6, stroke_width=2
        )

    @pytest.mark.parametrize(
        ("kwargs", "match"),
        [
            ({"spacing": 4, "line_spacing": 1.2}, "not both"),
            ({"spacing": float("nan")}, "spacing"),
            ({"spacing": "4"}, "spacing"),
            ({"spacing": -500}, "spacing"),
            ({"line_spacing": float("nan")}, "line_spacing"),
            ({"line_spacing": float("inf")}, "line_spacing"),
        ],
    )
    def test_bad_arguments(self, kwargs: dict[str, Any], match: str) -> None:
        with pytest.raises(ValueError, match=match):
            khatt.draw_text(blank(), (10, 10), "خط\nخط", **kwargs)
        with pytest.raises(ValueError, match=match):
            khatt.overlay(blank(), "خط\nخط", (10, 10, 300, 200), **kwargs)
