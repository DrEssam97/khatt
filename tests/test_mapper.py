"""Mapper tests: pure pixel-grid to character mapping, no fonts involved."""

from __future__ import annotations

import pytest
from PIL import Image

from khatt.mapper import STYLES, available_styles, map_image

BLOCKS_RAMP = " ░▒▓█"
ASCII_RAMP = " .:-=+*#%@"


def img(rows: list[list[int]]) -> Image.Image:
    """Build a grayscale image from a row-major list of coverage values."""
    height, width = len(rows), len(rows[0])
    data = bytes(v for row in rows for v in row)
    return Image.frombytes("L", (width, height), data)


def gradient(width: int = 256) -> Image.Image:
    return img([[min(v, 255) for v in range(width)]])


class TestCharsets:
    def test_blocks_uses_only_declared_ramp(self) -> None:
        art = map_image(gradient(), "blocks")
        assert set(art) <= set(BLOCKS_RAMP)

    def test_ascii_uses_only_declared_ramp(self) -> None:
        art = map_image(gradient(), "ascii")
        assert set(art) <= set(ASCII_RAMP)

    def test_braille_uses_only_braille_block(self) -> None:
        image = img([[0, 60, 120, 255] for _ in range(4)])  # 4x4 → 2 braille cells
        art = map_image(image, "braille")
        assert art
        assert all(0x2800 <= ord(ch) <= 0x28FF for ch in art)


class TestDensityMapping:
    def test_monotonic_coverage_to_density(self) -> None:
        art = map_image(gradient(), "ascii")
        indices = [ASCII_RAMP.index(ch) for ch in art]
        assert indices == sorted(indices)

    def test_extremes(self) -> None:
        # Zero coverage maps to blank; full coverage maps to the densest
        # character. Trailing blanks are trimmed, leading blanks are kept.
        assert map_image(img([[0, 255]]), "blocks") == " █"
        assert map_image(img([[255, 0]]), "blocks") == "█"


class TestThreshold:
    def test_below_threshold_is_blank(self) -> None:
        # 100/255 ≈ 0.39 < 0.5 → blank; put ink at the end so the blank
        # survives rstrip.
        art = map_image(img([[100, 255]]), "ascii", threshold=0.5)
        assert art[0] == " "
        assert art[1] != " "

    def test_no_threshold_keeps_faint_ink(self) -> None:
        art = map_image(img([[100, 255]]), "ascii")
        assert art[0] != " "

    def test_braille_threshold_gates_dots(self) -> None:
        cell = [[100, 100], [100, 100], [100, 100], [100, 100]]  # 2x4 = one cell
        # All dots below threshold → blank cell → trimmed to an empty line.
        assert map_image(img(cell), "braille", threshold=0.9) == ""
        # All dots above threshold → fully lit cell.
        assert map_image(img(cell), "braille", threshold=0.1) == "⣿"

    def test_invalid_threshold_rejected(self) -> None:
        with pytest.raises(ValueError, match="threshold"):
            map_image(gradient(), "blocks", threshold=1.5)


class TestGridShape:
    def test_one_line_per_cell_row(self) -> None:
        image = img([[255] * 4] * 3)
        assert len(map_image(image, "blocks").split("\n")) == 3

    def test_braille_consumes_2x4_pixels_per_cell(self) -> None:
        image = img([[255] * 6] * 8)  # 6x8 px → 3 cols x 2 rows of cells
        lines = map_image(image, "braille").split("\n")
        assert len(lines) == 2
        assert all(len(line) == 3 for line in lines)

    def test_trailing_blanks_trimmed(self) -> None:
        art = map_image(img([[255, 0, 0]]), "blocks")
        assert art == "█"


class TestStyleRegistry:
    def test_declared_styles(self) -> None:
        names = ["ascii", "blocks", "braille", "halfblocks", "quadrants", "sextants"]
        assert available_styles() == names
        assert set(STYLES) == set(names)

    def test_unknown_style_raises_with_names(self) -> None:
        with pytest.raises(KeyError, match="blocks"):
            map_image(gradient(), "neon")


class TestBlockMosaics:
    def test_halfblocks_top_and_bottom(self) -> None:
        assert map_image(img([[255], [0]]), "halfblocks") == "▀"
        assert map_image(img([[0], [255]]), "halfblocks") == "▄"
        assert map_image(img([[255], [255]]), "halfblocks") == "█"
        assert map_image(img([[0], [0]]), "halfblocks") == ""

    @pytest.mark.parametrize(
        ("rows", "char"),
        [
            ([[255, 0], [0, 0]], "▘"),
            ([[0, 255], [0, 0]], "▝"),
            ([[0, 0], [255, 0]], "▖"),
            ([[0, 0], [0, 255]], "▗"),
            ([[255, 0], [0, 255]], "▚"),
            ([[0, 255], [255, 255]], "▟"),
        ],
    )
    def test_quadrants_follow_their_corners(self, rows: list[list[int]], char: str) -> None:
        assert map_image(img(rows), "quadrants") == char

    def test_sextants_cover_every_pattern_once(self) -> None:
        mosaic = STYLES["sextants"].mosaic
        assert mosaic is not None
        assert len(mosaic) == 64
        assert len(set(mosaic)) == 64
        assert mosaic[1] == "\U0001fb00"  # top left only
        assert mosaic[62] == "\U0001fb3b"  # all but top left
        assert (mosaic[0], mosaic[21], mosaic[42], mosaic[63]) == (" ", "▌", "▐", "█")

    def test_sextant_rows_run_top_down(self) -> None:
        middle_right = img([[0, 0], [0, 255], [0, 0]])
        assert map_image(middle_right, "sextants") == chr(0x1FB00 + 8 - 1)

    def test_threshold_is_the_block_cutoff(self) -> None:
        faint = img([[100], [100]])
        assert map_image(faint, "halfblocks") == ""
        assert map_image(faint, "halfblocks", threshold=0.3) == "█"
