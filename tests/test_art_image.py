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


class TestMosaics:
    @pytest.mark.parametrize(
        ("char", "inked"),
        [
            ("▀", [(0, 0), (1, 0)]),
            ("▄", [(0, 1), (1, 1)]),
            ("▘", [(0, 0)]),
            ("▞", [(1, 0), (0, 1)]),
        ],
    )
    def test_blocks_fill_their_quarters(self, char: str, inked: list[tuple[int, int]]) -> None:
        image = draw(char)
        for x in range(2):
            for y in range(2):
                centre = (x * CELL // 2 + CELL // 4, y * CELL + CELL // 2)
                assert image.getpixel(centre) == (BLACK if (x, y) in inked else WHITE)

    def test_sextant_fills_a_third_of_the_height(self) -> None:
        image = draw(chr(0x1FB00 + 8 - 1))  # middle right sextant
        third = 2 * CELL // 3
        assert image.getpixel((3 * CELL // 4, third + third // 2)) == BLACK
        assert image.getpixel((3 * CELL // 4, third // 2)) == WHITE
        assert image.getpixel((CELL // 4, third + third // 2)) == WHITE


class TestPalette:
    def test_each_cell_takes_its_colour(self) -> None:
        image = khatt.art_to_image("██", palette="red,blue", cell_width=CELL, padding=0)
        assert image is not None
        assert image.getpixel((CELL // 2, CELL)) == (0, 0, 255)  # rtl: red at the right
        assert image.getpixel((CELL + CELL // 2, CELL)) == (255, 0, 0)

    def test_direction_and_bands(self) -> None:
        image = khatt.art_to_image(
            "████", palette="red,blue", direction="ltr", bands=True, cell_width=CELL, padding=0
        )
        assert image is not None
        colours = [image.getpixel((col * CELL + CELL // 2, CELL)) for col in range(4)]
        assert colours == [(255, 0, 0), (255, 0, 0), (0, 0, 255), (0, 0, 255)]

    def test_transparent_background(self) -> None:
        image = khatt.art_to_image("█ ", palette="gold", bg=None, cell_width=CELL, padding=0)
        assert image is not None
        assert image.mode == "RGBA"
        assert image.getpixel((CELL // 2, CELL))[3] == 255
        assert image.getpixel((CELL + CELL // 2, CELL))[3] == 0


class TestSvg:
    def test_blank_art_returns_none(self) -> None:
        assert khatt.art_to_svg(" ⠀\n") is None

    def test_size_and_background(self) -> None:
        svg = khatt.art_to_svg("██", cell_width=10, padding=0, bg="#102030")
        assert svg is not None
        assert 'width="20" height="20"' in svg
        assert 'fill="#102030"' in svg

    def test_shapes_for_each_kind_of_cell(self) -> None:
        svg = khatt.art_to_svg("⣿▘▒@", fg="red", bg=None)
        assert svg is not None
        assert svg.count("<circle") == 8
        assert svg.count("<rect") == 2  # the quadrant and the shade, no background
        assert 'fill-opacity="0.5"' in svg
        assert ">@</text>" in svg
        assert "#ff0000" in svg

    def test_palette_colours(self) -> None:
        svg = khatt.art_to_svg("██", palette="red,blue", bg=None)
        assert svg is not None
        assert svg.index("#0000ff") < svg.index("#ff0000")  # rtl: red on the right

    def test_rejects_tiny_cells_and_negative_padding(self) -> None:
        with pytest.raises(ValueError, match="cell_width"):
            khatt.art_to_svg("█", cell_width=1)
        with pytest.raises(ValueError, match="padding"):
            khatt.art_to_svg("█", padding=-1)


class TestHtml:
    def test_runs_of_one_colour_share_a_span(self) -> None:
        html = khatt.art_to_html("██ █", palette="red", bg=None)
        assert html == (
            '<pre style="line-height:1;font-family:monospace">'
            '<span style="color:#ff0000">██ █</span></pre>\n'
        )

    def test_escapes_and_background(self) -> None:
        html = khatt.art_to_html("<&>", fg="black", bg="white")
        assert "&lt;&amp;&gt;" in html
        assert "background:#ffffff" in html

    def test_blank_lines_stay_empty(self) -> None:
        html = khatt.art_to_html("█\n\n█", palette="red,blue", bg=None)
        assert html.split("\n")[1] == ""


@pytest.mark.parametrize("style", khatt.list_styles())
@pytest.mark.parametrize("font", khatt.list_fonts())
def test_every_font_and_style_draws(font: str, style: str) -> None:
    art = khatt.render("مرحبا", font=font, style=style)
    lines = art.split("\n")
    image = khatt.art_to_image(art, cell_width=8, padding=0)
    assert image is not None
    assert image.size == (8 * max(map(len, lines)), 16 * len(lines))
    assert image.convert("L").getextrema()[0] < 128  # some real ink
