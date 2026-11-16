"""Animated text art: frames stay joined, aligned and coloured, and save in every format."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from cli_runner import invoke
from PIL import Image

import khatt
from khatt.animate import _clusters
from khatt.cli import main

BLANKS = " ⠀"


def inked_columns(frame: str) -> list[int]:
    return sorted(
        {col for line in frame.split("\n") for col, char in enumerate(line) if char not in BLANKS}
    )


class TestType:
    def test_a_frame_per_letter_after_a_blank_one(self) -> None:
        animation = khatt.animate("مرحبا", "type", size=6)
        assert len(animation.frames) == 6
        assert not inked_columns(animation.frames[0])
        assert all(inked_columns(frame) for frame in animation.frames[1:])

    def test_every_frame_is_the_same_size(self) -> None:
        animation = khatt.animate("مرحبا بالعالم", "type", style="quadrants", size=6)
        shapes = {
            (len(frame.split("\n")), *{len(line) for line in frame.split("\n")})
            for frame in animation.frames
        }
        assert len(shapes) == 1

    def test_arabic_grows_from_a_fixed_right_edge(self) -> None:
        animation = khatt.animate("مرحبا", "type", size=8)
        right = max(inked_columns(animation.frames[-1]))
        for frame in animation.frames[1:]:
            assert max(inked_columns(frame)) >= right - 1
        # The first letter alone is narrower than the whole word.
        assert min(inked_columns(animation.frames[1])) > min(inked_columns(animation.frames[-1]))

    def test_latin_grows_from_the_left(self) -> None:
        animation = khatt.animate("Hello", "type", font="rubik", size=6)
        lefts = {min(inked_columns(frame)) for frame in animation.frames[1:]}
        assert len(lefts) == 1

    def test_marks_arrive_with_their_letter(self) -> None:
        assert _clusters("بَب") == [2, 3]
        animation = khatt.animate("بَب", "type", size=6, keep_tashkeel=True)
        assert len(animation.frames) == 3

    def test_the_finished_text_is_held(self) -> None:
        animation = khatt.animate("خط", "type", fps=10, hold=2)
        assert animation.durations[:-1] == [0.1] * (len(animation.frames) - 1)
        assert animation.durations[-1] == 2


class TestOtherEffects:
    def test_wipe_uncovers_arabic_from_the_right(self) -> None:
        animation = khatt.animate("القاهرة", "wipe", size=6, fps=8)
        assert len(animation.frames) == 9
        assert not inked_columns(animation.frames[0])
        half = inked_columns(animation.frames[4])
        whole = inked_columns(animation.frames[-1])
        assert half
        assert min(half) > min(whole)
        assert max(half) == max(whole)

    def test_wipe_uncovers_latin_from_the_left(self) -> None:
        animation = khatt.animate("Khatt", "wipe", font="rubik", size=6, fps=8)
        half = inked_columns(animation.frames[4])
        assert min(half) == min(inked_columns(animation.frames[-1]))

    def test_kashida_stretches_and_settles(self) -> None:
        animation = khatt.animate("محمد", "kashida", size=6)
        widths = [len(inked_columns(frame)) for frame in animation.frames]
        middle = len(widths) // 2
        assert widths[0] == widths[-1]
        assert widths[middle] > widths[0]
        assert animation.frames[0] == animation.frames[-1]

    def test_kashida_needs_joining_letters(self) -> None:
        with pytest.raises(ValueError, match="kashida"):
            khatt.animate("Khatt", "kashida", font="rubik")

    def test_shimmer_moves_the_colours(self) -> None:
        animation = khatt.animate("خط", "shimmer", palette="gold", size=6, fps=4)
        assert animation.colors is not None
        assert len(set(animation.frames)) == 1
        assert animation.colors[0] != animation.colors[1]

    def test_shimmer_needs_a_palette(self) -> None:
        with pytest.raises(ValueError, match="palette"):
            khatt.animate("خط", "shimmer")


class TestColours:
    def test_a_cell_keeps_its_colour_as_the_text_grows(self) -> None:
        animation = khatt.animate("مرحبا", "type", palette="red,blue", size=6)
        assert animation.colors is not None
        final = animation.colors[-1]
        for frame_colors in animation.colors[1:]:
            for row, line in enumerate(frame_colors):
                for col, color in enumerate(line):
                    if color is not None and final[row][col] is not None:
                        assert color == final[row][col]

    def test_blank_cells_have_no_colour(self) -> None:
        animation = khatt.animate("خط", "type", palette="gold", size=6)
        assert animation.colors is not None
        assert all(color is None for row in animation.colors[0] for color in row)

    def test_ansi(self) -> None:
        plain = khatt.animate("خط", "type", size=6)
        assert plain.ansi(2) == plain.frames[2]
        coloured = khatt.animate("خط", "type", palette="red", size=6)
        assert "\033[38;2;255;0;0m" in coloured.ansi(2)
        assert "\033[38;5;196m" in coloured.ansi(2, "256")


class TestBadInput:
    @pytest.mark.parametrize(
        ("options", "match"),
        [
            ({"effect": "spin"}, "effect"),
            ({"fps": 0}, "fps"),
            ({"size": 0}, "size"),
        ],
    )
    def test_rejected(self, options: dict[str, object], match: str) -> None:
        with pytest.raises(ValueError, match=match):
            khatt.animate("خط", **options)  # type: ignore[arg-type]

    def test_nothing_to_draw(self) -> None:
        with pytest.raises(ValueError, match="no renderable"):
            khatt.animate("   ")


class TestSaving:
    @pytest.mark.parametrize("name", ["anim.gif", "anim.png", "anim.apng", "anim.webp"])
    def test_image_formats(self, tmp_path: Path, name: str) -> None:
        animation = khatt.animate("خط", "type", palette="gold", size=6)
        target = tmp_path / name
        animation.save(target, bg="#1e1e2e")
        with Image.open(target) as image:
            assert getattr(image, "n_frames", 1) == len(animation.frames)

    def test_frames_share_one_size(self) -> None:
        images = khatt.animate("مرحبا", "type", size=6).images(cell_width=6)
        assert len({image.size for image in images}) == 1

    def test_cast(self, tmp_path: Path) -> None:
        animation = khatt.animate("خط", "type", palette="gold", size=6)
        target = tmp_path / "anim.cast"
        animation.save(target)
        events = [json.loads(line) for line in target.read_text(encoding="utf-8").splitlines()]
        header = events[0]
        assert header["version"] == 2
        assert header["height"] == len(animation.frames[0].split("\n"))
        assert len(events) == len(animation.frames) + 2
        assert [event[0] for event in events[1:]] == sorted(event[0] for event in events[1:])

    def test_unknown_format(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="gif"):
            khatt.animate("خط").save(tmp_path / "anim.mp4")


def test_play_redraws_in_place(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("time.sleep", lambda _: None)
    animation = khatt.animate("خط", "type", size=6)
    out = io.StringIO()
    animation.play(out, loops=2, mode=None)
    written = out.getvalue()
    height = len(animation.frames[0].split("\n"))
    assert written.startswith("\033[?25l")
    assert written.endswith("\033[?25h")
    assert written.count(f"\033[{height - 1}A") == 2 * len(animation.frames) - 1


class TestCli:
    def test_saves_an_animation(self, tmp_path: Path) -> None:
        target = tmp_path / "anim.gif"
        result = invoke(
            main, ["مرحبا", "-a", "type", "-s", "quadrants", "-p", "gold", "-o", str(target)]
        )
        assert result.exit_code == 0, result.output
        with Image.open(target) as image:
            assert getattr(image, "n_frames", 1) == 6

    def test_prints_the_finished_text_when_not_a_terminal(self) -> None:
        result = invoke(main, ["خط", "-a", "wipe"])
        assert result.exit_code == 0
        assert result.output.strip()
        assert "\033[" not in result.output

    def test_shimmer_without_a_palette_fails(self) -> None:
        result = invoke(main, ["خط", "-a", "shimmer"])
        assert result.exit_code == 2
        assert "palette" in result.output

    def test_unknown_format_fails(self, tmp_path: Path) -> None:
        result = invoke(main, ["خط", "-a", "type", "-o", str(tmp_path / "anim.mp4")])
        assert result.exit_code == 2

    def test_fps_must_be_positive(self) -> None:
        result = invoke(main, ["خط", "-a", "type", "--fps", "0"])
        assert result.exit_code == 2
