"""CLI smoke tests via typer's CliRunner."""

from __future__ import annotations

from pathlib import Path

from PIL import Image
from typer.testing import CliRunner

from khatt.cli import app

runner = CliRunner()

BLOCKS_CHARS = set(" ░▒▓█\n")


def test_basic_render() -> None:
    result = runner.invoke(app, ["مرحبا"])
    assert result.exit_code == 0
    assert result.output.strip()
    assert set(result.output) <= BLOCKS_CHARS


def test_style_flag() -> None:
    result = runner.invoke(app, ["خط", "--style", "ascii"])
    assert result.exit_code == 0
    assert set(result.output) <= set(" .:-=+*#%@\n")


def test_width_flag() -> None:
    result = runner.invoke(app, ["خط", "-w", "30"])
    assert result.exit_code == 0
    assert max(len(line) for line in result.output.split("\n")) <= 30


def test_font_flag() -> None:
    result = runner.invoke(app, ["خط", "--font", "cairo"])
    assert result.exit_code == 0
    assert result.output.strip()


def test_threshold_flag() -> None:
    result = runner.invoke(app, ["خط", "--threshold", "0.6"])
    assert result.exit_code == 0


def test_stdin_input() -> None:
    result = runner.invoke(app, [], input="خط\n")
    assert result.exit_code == 0
    assert result.output.strip()


def test_stdin_dash() -> None:
    result = runner.invoke(app, ["-"], input="خط\n")
    assert result.exit_code == 0
    assert result.output.strip()


def test_list_fonts() -> None:
    result = runner.invoke(app, ["--list-fonts"])
    assert result.exit_code == 0
    assert "amiri" in result.output
    assert "cairo" in result.output


def test_list_styles() -> None:
    result = runner.invoke(app, ["--list-styles"])
    assert result.exit_code == 0
    assert "blocks" in result.output
    assert "braille" in result.output


def test_output_txt(tmp_path: Path) -> None:
    target = tmp_path / "art.txt"
    result = runner.invoke(app, ["خط", "--output", str(target)])
    assert result.exit_code == 0
    content = target.read_text(encoding="utf-8")
    assert content.strip()
    assert set(content) <= BLOCKS_CHARS


def test_output_png(tmp_path: Path) -> None:
    target = tmp_path / "art.png"
    result = runner.invoke(app, ["خط", "--output", str(target)])
    assert result.exit_code == 0
    with Image.open(target) as image:
        assert image.size[0] > 0


def test_unknown_font_fails_with_hint() -> None:
    result = runner.invoke(app, ["خط", "--font", "nope"])
    assert result.exit_code == 2
    assert "available fonts" in result.output + str(result.exception or "")


def test_unrenderable_input_fails() -> None:
    result = runner.invoke(app, ["😀"])
    assert result.exit_code == 1


def test_empty_stdin_ok() -> None:
    result = runner.invoke(app, [], input="")
    assert result.exit_code == 0
