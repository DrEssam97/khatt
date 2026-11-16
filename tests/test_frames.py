"""Frames around text art, their lines in images, and canvas sizes."""

from __future__ import annotations

from pathlib import Path

import pytest
from cli_runner import invoke
from PIL import Image

import khatt
from khatt.art_image import canvas_size
from khatt.cli import main
from khatt.frames import BOX_CHARACTERS, FRAMES, box_rects

ART = "██\n█"


class TestFrameArt:
    @pytest.mark.parametrize("style", sorted(FRAMES))
    def test_corners_and_sides(self, style: str) -> None:
        framed = khatt.frame_art(ART, style, padding=0).split("\n")
        top_left, _, top_right, vertical, bottom_left, bottom_right = FRAMES[style]
        assert framed[0][0] == top_left
        assert framed[0][-1] == top_right
        assert framed[-1][0] == bottom_left
        assert framed[-1][-1] == bottom_right
        assert all(line[0] == vertical and line[-1] == vertical for line in framed[1:-1])
        assert len({len(line) for line in framed}) == 1

    def test_padding_is_doubled_across(self) -> None:
        framed = khatt.frame_art(ART, "single", padding=1).split("\n")
        assert len(framed) == 2 + 2 + 2
        assert len(framed[0]) == 2 + 2 + 4
        assert framed[2] == "│  ██  │"
        assert framed[3] == "│  █   │"

    def test_lawha_has_an_ornament_in_the_middle(self) -> None:
        top = khatt.frame_art("█████", "lawha").split("\n")[0]
        assert top[0] == top[-1] == "۞"
        assert top[len(top) // 2] == "۞"

    def test_list_and_errors(self) -> None:
        assert khatt.list_frames() == ["double", "heavy", "lawha", "round", "single"]
        with pytest.raises(KeyError, match="lawha"):
            khatt.frame_art(ART, "nope")
        with pytest.raises(ValueError, match="padding"):
            khatt.frame_art(ART, padding=-1)


class TestBoxRects:
    @pytest.mark.parametrize("char", sorted(BOX_CHARACTERS))
    def test_inside_the_cell(self, char: str) -> None:
        for x0, y0, x1, y1 in box_rects(char, 40, 80):
            assert 0 <= x0 < x1 <= 40
            assert 0 <= y0 < y1 <= 80

    def test_arms_reach_the_edges(self) -> None:
        line = box_rects("─", 40, 80)
        assert min(x0 for x0, _, _, _ in line) == 0
        assert max(x1 for _, _, x1, _ in line) == 40
        corner = box_rects("╔", 40, 80)
        assert sum(1 for _, _, x1, _ in corner if x1 == 40) == 2  # both lines go right
        assert sum(1 for _, _, _, y1 in corner if y1 == 80) == 2  # and both go down

    def test_double_and_heavy(self) -> None:
        assert len(box_rects("═", 40, 80)) == 2
        light = box_rects("─", 40, 80)[0]
        heavy = box_rects("━", 40, 80)[0]
        assert heavy[3] - heavy[1] > light[3] - light[1]


class TestImages:
    def test_frame_lines_are_unbroken(self) -> None:
        framed = khatt.frame_art("█", "single", padding=0)
        image = khatt.art_to_image(framed, cell_width=20, padding=0)
        assert image is not None
        middle = 20  # the middle of the first row of cells, 40 px tall
        assert all(image.getpixel((x, middle)) == (0, 0, 0) for x in range(10, 50))

    def test_ornament_is_drawn(self) -> None:
        image = khatt.art_to_image("۞", cell_width=40, padding=0)
        assert image is not None
        assert image.convert("L").getextrema()[0] < 128

    def test_svg_draws_lines_as_rectangles(self) -> None:
        svg = khatt.art_to_svg("═", bg=None)
        assert svg is not None
        assert svg.count("<rect") == 2


class TestCanvas:
    def test_named_and_custom_sizes(self) -> None:
        assert canvas_size("social") == (1280, 640)
        assert canvas_size(" Square ") == (1080, 1080)
        assert canvas_size("800x200") == (800, 200)
        assert canvas_size((300, 100)) == (300, 100)

    def test_bad_canvases(self) -> None:
        with pytest.raises(KeyError, match="social"):
            canvas_size("poster")
        with pytest.raises(ValueError, match="16"):
            canvas_size("10x400")

    def test_art_is_centred_and_as_large_as_fits(self) -> None:
        image = khatt.art_to_image("██", canvas=(400, 200), bg="white")
        assert image is not None
        assert image.size == (400, 200)
        box = image.convert("L").point(lambda v: 255 - v).getbbox()
        assert box is not None
        left, top, right, bottom = box
        assert abs(left - (400 - right)) <= 1
        assert abs(top - (200 - bottom)) <= 1
        assert bottom - top >= 200 - 2 * 16 - 2  # as tall as fits inside the 8% margin

    def test_transparent_canvas(self) -> None:
        image = khatt.art_to_image("█", canvas="square", bg=None, palette="gold")
        assert image is not None
        assert image.mode == "RGBA"
        assert image.getpixel((0, 0))[3] == 0


def test_animation_in_a_frame() -> None:
    animation = khatt.animate("خط", "type", size=6, frame="round", palette="gold")
    assert all(frame.startswith("╭") for frame in animation.frames)
    assert animation.colors is not None
    assert animation.colors[0][0][0] is not None  # the frame is coloured from the start


class TestCli:
    def test_frame(self) -> None:
        result = invoke(main, ["خط", "--frame", "double", "--size", "6"])
        assert result.exit_code == 0
        assert result.output.startswith("╔")

    def test_lists(self) -> None:
        assert invoke(main, ["--list-frames"]).output.split() == khatt.list_frames()
        assert "social 1280x640" in invoke(main, ["--list-canvases"]).output

    def test_canvas(self, tmp_path: Path) -> None:
        target = tmp_path / "art.png"
        result = invoke(main, ["خط", "--frame", "lawha", "--canvas", "social", "-o", str(target)])
        assert result.exit_code == 0, result.output
        with Image.open(target) as image:
            assert image.size == (1280, 640)

    @pytest.mark.parametrize(
        "args",
        [
            ["خط", "--canvas", "social"],
            ["خط", "--canvas", "social", "-o", "x.png", "--png", "text"],
            ["خط", "--canvas", "poster", "-o", "x.png"],
            ["خط", "--frame", "nope"],
        ],
    )
    def test_errors(self, args: list[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        assert invoke(main, args).exit_code == 2
