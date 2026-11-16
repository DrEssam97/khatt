"""Palettes, gradients and terminal colour codes for text art."""

from __future__ import annotations

import pytest

import khatt
from khatt.palette import PALETTES, _xterm256, cell_colors, palette_colors

RED, WHITE, BLACK = (255, 0, 0), (255, 255, 255), (0, 0, 0)


class TestPaletteColors:
    def test_named_palettes(self) -> None:
        assert khatt.list_palettes() == sorted(PALETTES)
        for name in khatt.list_palettes():
            assert len(palette_colors(name)) >= 2

    def test_names_ignore_case_and_spaces(self) -> None:
        assert palette_colors(" Gold ") == palette_colors("gold")

    def test_colours_separated_by_commas(self) -> None:
        assert palette_colors("#ff0000, white,black") == [RED, WHITE, BLACK]

    def test_a_single_colour(self) -> None:
        assert palette_colors("red") == [RED]

    def test_a_list_of_colours(self) -> None:
        assert palette_colors(["red", (255, 255, 255), (0, 0, 0, 128)]) == [RED, WHITE, BLACK]

    def test_unknown_name_lists_the_palettes(self) -> None:
        with pytest.raises(KeyError, match="gold"):
            palette_colors("not-a-palette")

    def test_bad_colour_in_a_list(self) -> None:
        with pytest.raises(ValueError):
            palette_colors("red,not-a-colour")

    def test_empty_palette(self) -> None:
        with pytest.raises(ValueError, match="at least one"):
            palette_colors([])


class TestCellColors:
    def test_rtl_starts_at_the_right_edge(self) -> None:
        colors = cell_colors("███", "red,black")
        assert colors == [[BLACK, (128, 0, 0), RED]]

    def test_ltr_starts_at_the_left_edge(self) -> None:
        colors = cell_colors("███", "red,black", direction="ltr")
        assert colors == [[RED, (128, 0, 0), BLACK]]

    def test_down_and_up(self) -> None:
        art = "█\n█"
        assert cell_colors(art, "red,black", direction="down") == [[RED], [BLACK]]
        assert cell_colors(art, "red,black", direction="up") == [[BLACK], [RED]]

    def test_blank_cells_have_no_colour(self) -> None:
        assert cell_colors("█ ⠀█", "red,black") == [[BLACK, None, None, RED]]

    def test_gradient_spans_the_ink_only(self) -> None:
        # The blank margin on the left doesn't take a share of the gradient.
        assert cell_colors("   █ █", "red,black") == [[None, None, None, BLACK, None, RED]]

    def test_bands_are_solid(self) -> None:
        colors = cell_colors("██████", "red,white,black", direction="ltr", bands=True)
        assert colors == [[RED, RED, WHITE, WHITE, BLACK, BLACK]]

    def test_one_colour_is_solid(self) -> None:
        assert cell_colors("█\n██", "red") == [[RED], [RED, RED]]

    def test_blank_art(self) -> None:
        assert cell_colors("  \n", "gold") == [[None, None], []]

    def test_unknown_direction(self) -> None:
        with pytest.raises(ValueError, match="rtl"):
            cell_colors("█", "gold", direction="sideways")


class TestColorArt:
    def test_truecolor_codes_and_reset(self) -> None:
        assert khatt.color_art("██", "red") == "\033[38;2;255;0;0m██\033[0m"

    def test_codes_only_when_the_colour_changes(self) -> None:
        out = khatt.color_art("█ █", "red,black")
        assert out == "\033[38;2;0;0;0m█ \033[38;2;255;0;0m█\033[0m"

    def test_256_colours(self) -> None:
        assert khatt.color_art("█", "red", mode="256") == "\033[38;5;196m█\033[0m"

    def test_lines_reset_separately_and_blank_lines_stay_plain(self) -> None:
        out = khatt.color_art("█\n\n█", "red")
        assert out.split("\n") == ["\033[38;2;255;0;0m█\033[0m", "", "\033[38;2;255;0;0m█\033[0m"]

    def test_text_is_kept(self) -> None:
        art = khatt.render("خط", style="quadrants", size=6)
        coloured = khatt.color_art(art, "andalus")
        plain = "".join(part.split("m", 1)[-1] for part in coloured.split("\033["))
        assert plain == art

    def test_unknown_mode(self) -> None:
        with pytest.raises(ValueError, match="truecolor"):
            khatt.color_art("█", "gold", mode="16")


@pytest.mark.parametrize(
    ("color", "index"),
    [((255, 0, 0), 196), ((255, 255, 255), 231), ((0, 0, 0), 16), ((128, 128, 128), 244)],
)
def test_nearest_of_256_colours(color: tuple[int, int, int], index: int) -> None:
    assert _xterm256(color) == index
