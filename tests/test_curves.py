"""Text on curves: the line bends, and its letters stay joined."""

from __future__ import annotations

from typing import Any

import pytest
from PIL import Image

import khatt
from khatt.curves import _arc, _wave

TEXT = "خط جميل بالعربية"
VOCALIZED = "بِسْمِ اللَّهِ الرَّحْمَٰنِ"
PLAIN = khatt.Effect(fill="black")
UNBENT = khatt.Wave(height=0)
"""Takes the same path as a curve, so that a difference can only come from the bend."""


def art(curve: Any = None, text: str = TEXT, **kwargs: Any) -> Image.Image:
    kwargs.setdefault("effect", PLAIN)
    kwargs.setdefault("font", "lalezar")
    kwargs.setdefault("size_px", 60)
    image = khatt.word_art(text, curve=curve, **kwargs)
    assert image is not None
    return image


def ink(image: Image.Image) -> list[list[bool]]:
    alpha = image.getchannel("A")
    pixels = alpha.load()
    return [[pixels[x, y] > 127 for x in range(alpha.width)] for y in range(alpha.height)]


def pieces(image: Image.Image, smallest: int = 6) -> int:
    """How many separate shapes the text is drawn in: words, and dots too."""
    grid = ink(image)
    height, width = len(grid), len(grid[0])
    seen = [[False] * width for _ in range(height)]
    found = 0
    for y in range(height):
        for x in range(width):
            if not grid[y][x] or seen[y][x]:
                continue
            seen[y][x] = True
            stack, size = [(x, y)], 0
            while stack:
                cx, cy = stack.pop()
                size += 1
                for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                    if 0 <= nx < width and 0 <= ny < height and grid[ny][nx] and not seen[ny][nx]:
                        seen[ny][nx] = True
                        stack.append((nx, ny))
            found += size >= smallest
    return found


def ink_top(image: Image.Image, x: int) -> int:
    grid = ink(image)
    return next((y for y, row in enumerate(grid) if row[x]), len(grid))


def weight(image: Image.Image, box: tuple[int, int, int, int]) -> int:
    return sum(image.getchannel("A").crop(box).histogram()[128:])


class TestLettersStayJoined:
    """The point of bending the line: no join opens up, and nothing merges."""

    @pytest.mark.parametrize("curve", ["arc", "smile", "wave", khatt.Arc(60), khatt.Arc(-200)])
    @pytest.mark.parametrize("font", ["lalezar", "cairo", "aref-ruqaa", "amiri"])
    def test_same_shapes_as_flat_text(self, curve: Any, font: str) -> None:
        # 100 px and up: smaller, a hairline in aref-ruqaa flickers even with no bend at all.
        kwargs: dict[str, Any] = {"font": font, "size_px": 110}
        assert pieces(art(curve, **kwargs)) == pieces(art(UNBENT, **kwargs))

    def test_full_ring(self) -> None:
        text = "مرحبا بكم في مدينة القاهرة الجميلة"
        assert pieces(art("ring", text)) == pieces(art(UNBENT, text))

    def test_tashkeel_keeps_its_marks(self) -> None:
        kwargs: dict[str, Any] = {"font": "amiri", "size_px": 90}
        assert pieces(art("arc", VOCALIZED, **kwargs)) == pieces(art(UNBENT, VOCALIZED, **kwargs))

    def test_sharp_edges(self) -> None:
        histogram = art("arc", size_px=120).getchannel("A").histogram()
        drawn = sum(histogram[1:])
        assert sum(histogram[250:]) / drawn > 0.6  # mostly solid, not blurred


class TestArc:
    def test_arches_up(self) -> None:
        image = art("arc")
        left, _, right, _ = image.getchannel("A").getbbox()
        assert ink_top(image, (left + right) // 2) < ink_top(image, left + 8)

    def test_negative_dips_down(self) -> None:
        image = art("smile")
        left, _, right, _ = image.getchannel("A").getbbox()
        middle = (left + right) // 2
        assert ink_top(image, middle) > ink_top(image, left + 8)

    def test_a_bigger_angle_curls_tighter(self) -> None:
        gentle, tight = art(khatt.Arc(60)), art(khatt.Arc(200))
        assert tight.width < gentle.width and tight.height > gentle.height

    def test_ring_goes_all_the_way_round(self) -> None:
        image = art("ring", "مرحبا بكم في مدينة القاهرة الجميلة")
        width, height = image.size
        assert 0.8 < width / height < 1.25
        third = height // 3
        assert weight(image, (0, 0, width, third)) > 0
        assert weight(image, (0, height - third, width, height)) > 0
        hole = (width // 2 - 8, height // 2 - 8, width // 2 + 8, height // 2 + 8)
        assert weight(image, hole) == 0

    def test_text_keeps_its_length_along_the_middle(self) -> None:
        flat, bent = art(None), art(khatt.Arc(90))
        assert bent.width < flat.width  # the chord of an arc is shorter than the arc
        assert bent.width > flat.width * 0.8

    def test_the_start_of_the_line_stays_where_it_was(self) -> None:
        """Right-to-left or not, what is on the right of the flat text stays on the right."""
        text = "مـــــــــــــــــــــ بالعربية"
        flat, bent = art(None, text), art("arc", text)
        for image in (flat, bent):
            half = image.width // 2
            right = weight(image, (half, 0, image.width, image.height))
            left = weight(image, (0, 0, half, image.height))
            assert (right < left) == (
                weight(flat, (flat.width // 2, 0, flat.width, flat.height))
                < weight(flat, (0, 0, flat.width // 2, flat.height))
            )

    def test_too_tight_for_short_text(self) -> None:
        with pytest.raises(ValueError, match="too short"):
            art("ring", "خط")

    def test_geometry_at_the_top_of_the_arc(self) -> None:
        size, source = _arc(khatt.Arc(90), 400, 100)
        x, y = source(size[0] / 2, 0)
        assert x == pytest.approx(200, abs=1) and y == pytest.approx(0, abs=1)


class TestWave:
    def test_rises_and_falls(self) -> None:
        image = art("wave", size_px=80)
        left, _, right, _ = image.getchannel("A").getbbox()
        quarter = (right - left) // 4
        tops = [ink_top(image, left + quarter * n + 4) for n in (1, 3)]
        assert tops[0] != tops[1]

    def test_grows_by_its_height(self) -> None:
        flat, wavy = art(None), art(khatt.Wave(height=0.5))
        assert wavy.height > flat.height + 30
        assert wavy.width == pytest.approx(flat.width, abs=8)

    def test_no_height_is_flat(self) -> None:
        size, source = _wave(khatt.Wave(height=0), 200, 50, 100)
        assert size == (200, 50)
        assert source(120, 30) == (120, 30)


class TestWithWordArt:
    @pytest.mark.parametrize("curve", khatt.list_curves())
    @pytest.mark.parametrize("effect", khatt.list_effects())
    def test_every_effect_on_every_curve(self, curve: str, effect: str) -> None:
        text = "مرحبا بكم في مدينة القاهرة الجميلة"
        image = khatt.word_art(text, effect=effect, curve=curve, size_px=50)
        assert image is not None and image.mode == "RGBA"

    def test_outline_follows_the_curve(self) -> None:
        effect = khatt.Effect(fill="black", outline=0.05, outline_fill="red")
        plain, outlined = art("arc"), art("arc", effect=effect)
        assert outlined.width > plain.width
        counts = outlined.convert("RGB").getcolors(1 << 24)
        assert counts is not None
        assert any(r > 200 and g < 60 for _, (r, g, b) in counts)

    def test_effects_are_drawn_after_the_bend(self) -> None:
        """A shadow falls the same way everywhere on the curve, not along it."""
        shadow = khatt.Shadow(offset=(0.2, 0.2), blur=0, color="#ff0000")
        image = art("arc", effect=khatt.Effect(shadow=shadow))
        left, top, right, bottom = image.getchannel("A").getbbox()
        plain = art("arc")
        assert right - left == pytest.approx(plain.width + 12, abs=2)
        assert bottom - top == pytest.approx(plain.height + 12, abs=2)

    def test_lines_bend_together(self) -> None:
        two = art("arc", "خط جميل بالعربية\nخط جميل بالعربية")
        assert two.height > art("arc").height * 1.2

    def test_padding_and_background(self) -> None:
        image = art("arc", padding=5, background="white")
        assert image.getpixel((0, 0)) == (255, 255, 255, 255)

    def test_scale_does_not_change_spacing_or_wrapping(self) -> None:
        text = "خط جميل\nخط جميل"
        flat, bent = art(None, text, spacing=10), art(UNBENT, text, spacing=10)
        assert bent.height == pytest.approx(flat.height, abs=8)
        words = "خط جميل بالعربية " * 2
        wrapped = art(UNBENT, words, max_width=300)
        assert wrapped.width <= 310

    def test_nothing_to_draw(self) -> None:
        assert khatt.word_art("", curve="arc") is None

    def test_drawing_twice_gives_the_same_pixels(self) -> None:
        assert art("arc").tobytes() == art("arc").tobytes()

    def test_numpy_size(self) -> None:
        np = pytest.importorskip("numpy")
        image = art("arc", size_px=np.int64(60))
        assert image.tobytes() == art("arc").tobytes()


class TestErrors:
    def test_listed(self) -> None:
        assert khatt.list_curves() == ["arc", "ring", "smile", "wave"]

    def test_unknown_curve(self) -> None:
        with pytest.raises(KeyError, match="ring"):
            khatt.word_art(TEXT, curve="zigzag")

    def test_names_ignore_case(self) -> None:
        assert art(" ARC ").tobytes() == art("arc").tobytes()

    def test_not_a_curve(self) -> None:
        with pytest.raises(ValueError, match="curve"):
            khatt.word_art(TEXT, curve=5)  # type: ignore[arg-type]

    @pytest.mark.parametrize(
        ("make", "match"),
        [
            (lambda: khatt.Arc(0), "angle"),
            (lambda: khatt.Arc(351), "angle"),
            (lambda: khatt.Arc(-351), "angle"),
            (lambda: khatt.Arc(float("nan")), "angle"),
            (lambda: khatt.Arc("120"), "angle"),
            (lambda: khatt.Wave(height=-1), "height"),
            (lambda: khatt.Wave(height=float("inf")), "height"),
            (lambda: khatt.Wave(waves=0), "waves"),
        ],
    )
    def test_bad_values(self, make: Any, match: str) -> None:
        with pytest.raises(ValueError, match=match):
            make()
