"""Word art: every effect keeps the shaped text intact and paints what it says."""

from __future__ import annotations

import warnings
from dataclasses import replace
from typing import Any

import pytest
from PIL import Image, ImageChops

import khatt
from khatt.effects import _gradient_image, _ramp, compose, margin
from khatt.fonts import font_path
from khatt.layout import layout_block

TEXT = "خط جميل"
VOCALIZED = "بِسْمِ اللَّهِ"
BOX = (40, 40, 560, 220)


def blank(mode: str = "RGB", size: tuple[int, int] = (600, 300)) -> Image.Image:
    return Image.new(mode, size, "white" if mode == "RGB" else (255, 255, 255, 255))


def changed(before: Image.Image, after: Image.Image) -> tuple[int, int, int, int]:
    box = ImageChops.difference(before.convert("RGB"), after.convert("RGB")).getbbox()
    assert box is not None, "nothing was drawn"
    return box


def largest_difference(one: Image.Image, other: Image.Image) -> int:
    extrema = ImageChops.difference(one.convert("RGB"), other.convert("RGB")).getextrema()
    return max(high for _, high in extrema)


def art(effect: khatt.Effect | str, **kwargs: Any) -> Image.Image:
    image = khatt.word_art(TEXT, effect=effect, font="cairo", size_px=100, **kwargs)
    assert image is not None
    return image


def ink_box(image: Image.Image) -> tuple[int, int, int, int]:
    box = image.getchannel("A").getbbox()
    assert box is not None, "nothing was drawn"
    return box


def block_for(effect: khatt.Effect, size: int = 100) -> tuple[Image.Image, int, int]:
    laid_out = layout_block(
        TEXT,
        font_path("cairo"),
        size_px=size,
        line_spacing=1.2,
        keep_tashkeel=True,
        stroke_width=effect.outline * size,
    )
    assert laid_out is not None
    return compose(laid_out.block, effect, size)


class TestPresets:
    def test_listed(self) -> None:
        names = khatt.list_effects()
        assert names == sorted(names)
        assert {"gold", "neon", "fire", "3d"} <= set(names)

    @pytest.mark.parametrize("name", khatt.list_effects())
    @pytest.mark.parametrize("mode", ["RGB", "RGBA"])
    def test_draw_text(self, name: str, mode: str) -> None:
        image = khatt.draw_text(blank(mode), (40, 40), TEXT, size_px=80, effect=name)
        assert image.mode == mode
        changed(blank(mode), image)

    @pytest.mark.parametrize("name", khatt.list_effects())
    @pytest.mark.parametrize("size", [12, 48, 300])
    def test_word_art_at_any_size(self, name: str, size: int) -> None:
        image = khatt.word_art(TEXT, effect=name, size_px=size)
        assert image is not None and image.mode == "RGBA"
        assert image.getchannel("A").getextrema()[1] > 0

    @pytest.mark.parametrize("font", khatt.list_fonts())
    def test_every_font(self, font: str) -> None:
        assert khatt.word_art(VOCALIZED, effect="gold", font=font) is not None

    def test_names_ignore_case(self) -> None:
        assert khatt.get_effect(" NEON ") == khatt.get_effect("neon")

    def test_drawing_twice_gives_the_same_pixels(self) -> None:
        assert art("gold").tobytes() == art("gold").tobytes()

    def test_a_preset_is_a_starting_point(self) -> None:
        blue = replace(khatt.get_effect("3d"), fill="#2563eb")
        assert art(blue).tobytes() != art("3d").tobytes()


class TestTextStaysIntact:
    """An effect paints the finished text: the letters themselves never change."""

    @pytest.mark.parametrize("mode", ["RGB", "RGBA"])
    @pytest.mark.parametrize("text", [TEXT, VOCALIZED, "مرحبا\nبالعالم"])
    def test_plain_effect_is_plain_text(self, mode: str, text: str) -> None:
        plain = khatt.draw_text(blank(mode), (40, 40), text, size_px=70, fill="#123456")
        styled = khatt.draw_text(
            blank(mode), (40, 40), text, size_px=70, effect=khatt.Effect(fill="#123456")
        )
        assert largest_difference(plain, styled) <= 1

    def test_plain_effect_in_overlay(self) -> None:
        plain = khatt.overlay(blank(), TEXT, BOX, fill="#123456")
        styled = khatt.overlay(blank(), TEXT, BOX, effect=khatt.Effect(fill="#123456"))
        assert largest_difference(plain, styled) <= 1

    def test_outline_matches_stroke_width(self) -> None:
        plain = khatt.draw_text(
            blank(), (40, 40), TEXT, size_px=100, fill="red", stroke_width=5, stroke_fill="blue"
        )
        effect = khatt.Effect(fill="red", outline=0.05, outline_fill="blue")
        styled = khatt.draw_text(blank(), (40, 40), TEXT, size_px=100, effect=effect)
        assert largest_difference(plain, styled) <= 1

    def test_anchor_works_as_without_an_effect(self) -> None:
        kwargs: dict[str, Any] = {"size_px": 70, "anchor": "mm"}
        plain = khatt.draw_text(blank(), (300, 150), TEXT, fill="black", **kwargs)
        styled = khatt.draw_text(
            blank(), (300, 150), TEXT, effect=khatt.Effect(fill="black"), **kwargs
        )
        assert changed(blank(), plain) == changed(blank(), styled)


class TestGradient:
    def test_left_to_right(self) -> None:
        image = _gradient_image(khatt.Gradient(("#ff0000", "#0000ff"), angle=0), (100, 10))
        assert image.getpixel((0, 5))[0] > 240
        assert image.getpixel((99, 5))[2] > 240

    def test_top_to_bottom_by_default(self) -> None:
        image = _gradient_image(khatt.Gradient(("#ff0000", "#0000ff")), (10, 100))
        assert image.getpixel((5, 0))[0] > 240
        assert image.getpixel((5, 99))[2] > 240

    def test_turning_it_around(self) -> None:
        image = _gradient_image(khatt.Gradient(("#ff0000", "#0000ff"), angle=180), (100, 10))
        assert image.getpixel((0, 5))[2] > 240

    def test_diagonal_runs_corner_to_corner(self) -> None:
        ramp = _ramp((100, 100), 45)
        assert ramp.getpixel((0, 0)) < 8
        assert ramp.getpixel((99, 99)) > 247
        assert 110 < ramp.getpixel((50, 50)) < 145

    def test_stops_are_evenly_spaced(self) -> None:
        image = _gradient_image(khatt.Gradient(("black", "white", "black"), angle=0), (101, 4))
        assert image.getpixel((50, 2))[0] > 240
        assert image.getpixel((0, 2))[0] < 16 and image.getpixel((100, 2))[0] < 16

    def test_transparency_is_blended_too(self) -> None:
        image = _gradient_image(khatt.Gradient(("#00000000", "#000000ff"), angle=0), (100, 4))
        assert image.getpixel((0, 2))[3] < 16 and image.getpixel((99, 2))[3] > 240

    def test_spans_the_text(self) -> None:
        effect = khatt.Effect(fill=khatt.Gradient(("#ff0000", "#0000ff"), angle=0))
        image = art(effect)
        left, top, right, bottom = ink_box(image)
        row = range(top, bottom)
        first = next(p for y in row if (p := image.getpixel((left + 1, y)))[3] > 128)
        last = next(p for y in row if (p := image.getpixel((right - 2, y)))[3] > 128)
        assert first[0] > first[2] and last[2] > last[0]


class TestLayers:
    def test_shadow_falls_where_it_is_told(self) -> None:
        plain = ink_box(art(khatt.Effect()))
        shadow = khatt.Shadow(offset=(0.3, 0.2), blur=0, color="black")
        shadowed = art(khatt.Effect(shadow=shadow))
        assert shadowed.size[0] - plain[2] == pytest.approx(30, abs=2)
        assert shadowed.size[1] - plain[3] == pytest.approx(20, abs=2)

    def test_shadow_goes_behind_the_text(self) -> None:
        effect = khatt.Effect(fill="#ff0000", shadow=khatt.Shadow((0.02, 0.02), 0, "#0000ff"))
        counts = block_for(effect)[0].convert("RGB").getcolors(1 << 24)
        assert counts is not None
        reds = sum(n for n, (r, g, b) in counts if r > 240 and b < 16)
        solid = block_for(khatt.Effect(fill="#ff0000"))[0].getchannel("A")
        assert reds >= solid.point(lambda v: 255 if v > 250 else 0).histogram()[255] * 0.98

    def test_glow_spreads_all_round(self) -> None:
        plain = art(khatt.Effect()).size
        glowing = art(khatt.Effect(glows=khatt.Glow(radius=0.1, color="red"))).size
        assert glowing[0] > plain[0] + 20 and glowing[1] > plain[1] + 20

    def test_glows_stack(self) -> None:
        one = khatt.Glow(radius=0.05, color="red")
        two = khatt.Glow(radius=0.2, color="blue")
        assert art(khatt.Effect(glows=(two, one))).size > art(khatt.Effect(glows=one)).size

    def test_extrude_runs_along_its_angle(self) -> None:
        plain = art(khatt.Effect()).size
        right = art(khatt.Effect(extrude=khatt.Extrude(depth=0.2, angle=0))).size
        down = art(khatt.Effect(extrude=khatt.Extrude(depth=0.2, angle=90))).size
        assert right[0] == pytest.approx(plain[0] + 20, abs=1) and right[1] == plain[1]
        assert down[1] == pytest.approx(plain[1] + 20, abs=1) and down[0] == plain[0]

    def test_extrude_fades_to_its_end_colour(self) -> None:
        extrude = khatt.Extrude(depth=0.3, angle=0, color="#ff0000", end_color="#0000ff")
        image = art(khatt.Effect(fill="#00ff00", extrude=extrude))
        pixels = image.convert("RGB").getcolors(1 << 24)
        assert pixels is not None
        assert any(r > 200 and b < 50 for _, (r, g, b) in pixels)
        assert any(b > 200 and r < 50 for _, (r, g, b) in pixels)

    def test_outline_widens_the_text(self) -> None:
        plain = art(khatt.Effect()).size
        outlined = art(khatt.Effect(outline=0.1, outline_fill="red")).size
        assert outlined[0] == pytest.approx(plain[0] + 20, abs=3)

    def test_bevel_stays_inside_the_letters(self) -> None:
        plain = block_for(khatt.Effect(fill="#808080"))[0]
        bevelled = block_for(khatt.Effect(fill="#808080", bevel=0.05))[0]
        room = (bevelled.size[0] - plain.size[0]) // 2
        cropped = bevelled.crop((room, room, room + plain.size[0], room + plain.size[1]))
        assert plain.getchannel("A").tobytes() == cropped.getchannel("A").tobytes()
        assert plain.tobytes() != cropped.tobytes()

    def test_bevel_is_lit_from_the_top_left(self) -> None:
        bevelled = block_for(khatt.Effect(fill="#808080", bevel=0.05))[0]
        counts = bevelled.convert("RGB").getcolors(1 << 24)
        assert counts is not None
        assert any(r > 180 for _, (r, g, b) in counts) and any(r < 80 for _, (r, g, b) in counts)

    def test_margin_covers_the_effect_at_any_size(self) -> None:
        for name in khatt.list_effects():
            effect = khatt.get_effect(name)
            layer = block_for(effect)[0]
            box = ink_box(layer)
            room = margin(effect, 100)
            assert box[0] > 0 and box[1] > 0, name
            assert box[2] < layer.size[0] and box[3] < layer.size[1], name
            assert room > 0

    def test_effects_grow_with_the_text(self) -> None:
        for name in khatt.list_effects():
            small = khatt.word_art(TEXT, effect=name, font="cairo", size_px=80)
            large = khatt.word_art(TEXT, effect=name, font="cairo", size_px=160)
            assert small is not None and large is not None
            assert large.size[0] / small.size[0] == pytest.approx(2, rel=0.05), name


class TestOverlay:
    def test_fits_the_same_size_as_plain_text(self) -> None:
        plain = changed(blank(), khatt.overlay(blank(), TEXT, BOX))
        styled = khatt.overlay(blank(), TEXT, BOX, effect=khatt.Effect())
        assert changed(blank(), styled) == plain

    def test_glow_may_leave_the_box(self) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            image = khatt.overlay(blank(), TEXT, BOX, effect="neon")
        left, top, right, bottom = changed(blank(), image)
        assert left < BOX[0] or top < BOX[1] or right > BOX[2] or bottom > BOX[3]

    def test_effect_outline_does_not_warn(self) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            khatt.overlay(blank(), TEXT, BOX, effect="sticker")

    def test_text_that_does_not_fit_is_clipped_to_the_box(self) -> None:
        box = (100, 100, 180, 140)
        with pytest.warns(khatt.TextOverflowWarning):
            image = khatt.overlay(
                blank(), TEXT, box, fit="none", max_size_px=120, effect="neon", font="cairo"
            )
        left, top, right, bottom = changed(blank(), image)
        assert left >= box[0] and top >= box[1] and right <= box[2] and bottom <= box[3]

    @pytest.mark.parametrize("fit", ["shrink", "wrap", "none"])
    def test_every_fit(self, fit: str) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", khatt.TextOverflowWarning)
            changed(
                blank(), khatt.overlay(blank(), TEXT, BOX, fit=fit, max_size_px=60, effect="3d")
            )


class TestWordArt:
    def test_is_transparent_around_the_text(self) -> None:
        image = art(khatt.Effect(fill="black"))
        assert image.getpixel((0, image.height - 1))[3] == 0

    def test_is_as_big_as_the_effect(self) -> None:
        image = art("neon")
        assert ink_box(image) == (0, 0, *image.size)

    def test_padding(self) -> None:
        plain, padded = art("gold"), art("gold", padding=20)
        assert padded.size == (plain.width + 40, plain.height + 40)
        assert ink_box(padded) == (20, 20, plain.width + 20, plain.height + 20)

    def test_background(self) -> None:
        image = art(khatt.Effect(), padding=4, background="#112233")
        assert image.getpixel((0, 0)) == (0x11, 0x22, 0x33, 255)

    def test_starts_with_a_heavy_font(self) -> None:
        plain = khatt.word_art(TEXT)
        heavy = khatt.word_art(TEXT, effect="gold", font="lalezar", size_px=160)
        assert plain is not None and heavy is not None
        assert plain.tobytes() == heavy.tobytes()

    def test_nothing_to_draw(self) -> None:
        assert khatt.word_art("") is None
        assert khatt.word_art("   ") is None

    def test_lines_and_wrapping(self) -> None:
        one = art("gold")
        two = khatt.word_art(f"{TEXT}\n{TEXT}", effect="gold", font="cairo", size_px=100)
        assert two is not None and two.height > one.height * 1.4
        wrapped = khatt.word_art(
            f"{TEXT} {TEXT}", effect="gold", font="cairo", size_px=100, max_width=one.width + 40
        )
        assert wrapped is not None and wrapped.height > one.height * 1.4

    def test_keep_tashkeel(self) -> None:
        kept = khatt.word_art(VOCALIZED, effect=khatt.Effect())
        stripped = khatt.word_art(VOCALIZED, effect=khatt.Effect(), keep_tashkeel=False)
        assert kept is not None and stripped is not None
        assert kept.tobytes() != stripped.tobytes()

    def test_numpy_size(self) -> None:
        np = pytest.importorskip("numpy")
        image = khatt.word_art(TEXT, effect="gold", font="cairo", size_px=np.int64(100))
        assert image is not None and image.tobytes() == art("gold").tobytes()


class TestErrors:
    def test_unknown_effect(self) -> None:
        with pytest.raises(KeyError, match="gold"):
            khatt.get_effect("glitter")
        with pytest.raises(KeyError, match="glitter"):
            khatt.draw_text(blank(), (0, 0), TEXT, effect="glitter")
        with pytest.raises(KeyError, match="glitter"):
            khatt.overlay(blank(), TEXT, BOX, effect="glitter")
        with pytest.raises(KeyError, match="glitter"):
            khatt.word_art(TEXT, effect="glitter")

    def test_not_an_effect(self) -> None:
        with pytest.raises(ValueError, match="effect"):
            khatt.get_effect(5)  # type: ignore[arg-type]

    def test_effect_or_stroke_width(self) -> None:
        with pytest.raises(ValueError, match="stroke_width"):
            khatt.draw_text(blank(), (0, 0), TEXT, effect="gold", stroke_width=2)
        with pytest.raises(ValueError, match="stroke_width"):
            khatt.overlay(blank(), TEXT, BOX, effect="gold", stroke_width=2)

    def test_word_art_padding(self) -> None:
        with pytest.raises(ValueError, match="padding"):
            khatt.word_art(TEXT, padding=-1)

    @pytest.mark.parametrize(
        ("make", "match"),
        [
            (lambda: khatt.Gradient(("red",)), "two colours"),
            (lambda: khatt.Gradient("red"), "two colours"),
            (lambda: khatt.Gradient(("red", "nope")), None),
            (lambda: khatt.Gradient(("red", "blue"), angle=float("nan")), "angle"),
            (lambda: khatt.Shadow(blur=-1), "blur"),
            (lambda: khatt.Shadow(offset=(1,)), "offset"),  # type: ignore[arg-type]
            (lambda: khatt.Shadow(color="nope"), None),
            (lambda: khatt.Glow(radius=float("inf")), "radius"),
            (lambda: khatt.Glow(strength=-1), "strength"),
            (lambda: khatt.Extrude(depth=-0.1), "depth"),
            (lambda: khatt.Extrude(angle=float("nan")), "angle"),
            (lambda: khatt.Effect(fill="nope"), None),
            (lambda: khatt.Effect(outline=-1), "outline"),
            (lambda: khatt.Effect(bevel=-1), "bevel"),
            (lambda: khatt.Effect(glows=("red",)), "glows"),  # type: ignore[arg-type]
            (lambda: khatt.Effect(shadow="red"), "shadow"),  # type: ignore[arg-type]
            (lambda: khatt.Effect(extrude="red"), "extrude"),  # type: ignore[arg-type]
        ],
    )
    def test_bad_values(self, make: Any, match: str | None) -> None:
        with pytest.raises(ValueError, match=match):
            make()
