"""Drawing text art as an image: braille dots, shade blocks and ascii glyphs."""

from __future__ import annotations

import pytest
from PIL import Image

import khatt

CELL = 40  # large cells keep the geometry checks clear of antialiasing
DOT_STEP = CELL // 2  # braille dot spacing, both directions (cells are 2x tall)

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)


Colour = str | tuple[int, int, int]


def draw(art: str, fg: Colour = "black", bg: Colour | None = "white") -> Image.Image:
    image = khatt.art_to_image(art, fg=fg, bg=bg, cell_width=CELL, padding=0)
    assert image is not None
    return image


def dot_centre(dot_x: int, dot_y: int) -> tuple[int, int]:
    return round((dot_x + 0.5) * DOT_STEP), round((dot_y + 0.5) * DOT_STEP)


class TestGeometry:
    def test_one_cell_per_character_plus_padding(self) -> None:
        image = khatt.art_to_image("ab\nc", cell_width=10, padding=3)
        assert image is not None
        assert image.size == (2 * 10 + 6, 2 * 20 + 6)

    def test_default_padding_is_one_cell(self) -> None:
        image = khatt.art_to_image("█", cell_width=10)
        assert image is not None
        assert image.size == (30, 40)

    @pytest.mark.parametrize("art", ["", "   ", "⠀⠀\n  "])
    def test_blank_art_returns_none(self, art: str) -> None:
        assert khatt.art_to_image(art) is None

    def test_rejects_tiny_cells_and_negative_padding(self) -> None:
        with pytest.raises(ValueError, match="cell_width"):
            khatt.art_to_image("█", cell_width=1)
        with pytest.raises(ValueError, match="padding"):
            khatt.art_to_image("█", padding=-1)


class TestBraille:
    def test_single_dot_lands_in_its_slot(self) -> None:
        image = draw("⠁")  # U+2801: dot 1, top-left
        assert image.getpixel(dot_centre(0, 0)) == BLACK
        others = [(x, y) for x in range(2) for y in range(4) if (x, y) != (0, 0)]
        for slot in others:
            assert image.getpixel(dot_centre(*slot)) == WHITE

    def test_full_cell_has_eight_separate_dots(self) -> None:
        image = draw("⣿")
        for slot in [(x, y) for x in range(2) for y in range(4)]:
            assert image.getpixel(dot_centre(*slot)) == BLACK
        assert image.getpixel((DOT_STEP, DOT_STEP // 2)) == WHITE  # gap between columns
        assert image.getpixel((DOT_STEP // 2, DOT_STEP)) == WHITE  # gap between rows


class TestBlocks:
    def test_full_block_fills_its_cell(self) -> None:
        image = draw("█ ")
        assert image.getpixel((1, 1)) == BLACK
        assert image.getpixel((CELL - 2, 2 * CELL - 2)) == BLACK
        assert image.getpixel((CELL + CELL // 2, CELL)) == WHITE

    def test_shades_get_darker_along_the_ramp(self) -> None:
        image = draw("░▒▓█").convert("L")
        levels = [image.getpixel((col * CELL + CELL // 2, CELL)) for col in range(4)]
        assert levels == sorted(levels, reverse=True)
        assert len(set(levels)) == 4


class TestAscii:
    def test_glyphs_stay_inside_their_cell(self) -> None:
        image = draw(" @ ").convert("L")
        box = image.point(lambda v: 255 - v).getbbox()
        assert box is not None
        assert box[0] >= CELL
        assert box[2] <= 2 * CELL

    def test_period_sits_low_in_the_cell(self) -> None:
        image = draw(".").convert("L")
        box = image.point(lambda v: 255 - v).getbbox()
        assert box is not None
        assert box[1] > CELL  # below the middle of a 2*CELL tall cell


class TestColours:
    def test_foreground_and_background(self) -> None:
        image = draw("█ ", fg="#ff0000", bg=(0, 0, 255))
        assert image.mode == "RGB"
        assert image.getpixel((CELL // 2, CELL)) == (255, 0, 0)
        assert image.getpixel((CELL + CELL // 2, CELL)) == (0, 0, 255)

    def test_transparent_background(self) -> None:
        image = draw("█ ", fg="white", bg=None)
        assert image.mode == "RGBA"
        assert image.getpixel((CELL // 2, CELL)) == (255, 255, 255, 255)
        assert image.getpixel((CELL + CELL // 2, CELL))[3] == 0

    def test_unknown_colour_raises(self) -> None:
        with pytest.raises(ValueError):
            khatt.art_to_image("█", fg="not-a-colour")


@pytest.mark.parametrize("style", khatt.list_styles())
@pytest.mark.parametrize("font", khatt.list_fonts())
def test_every_font_and_style_draws(font: str, style: str) -> None:
    art = khatt.render("مرحبا", font=font, style=style)
    lines = art.split("\n")
    image = khatt.art_to_image(art, cell_width=8, padding=0)
    assert image is not None
    assert image.size == (8 * max(map(len, lines)), 16 * len(lines))
    assert image.convert("L").getextrema()[0] < 128  # some real ink
