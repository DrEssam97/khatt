"""CLI smoke tests via typer's CliRunner."""

from __future__ import annotations

from itertools import pairwise
from pathlib import Path

from PIL import Image
from typer.testing import CliRunner

import khatt
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


def bands(output: str) -> int:
    lines = output.strip("\n").split("\n")
    return 1 + sum(1 for a, b in pairwise(lines) if not a.strip() and b.strip())


def test_multiline_stdin_without_warnings() -> None:
    result = runner.invoke(app, ["-w", "80"], input="سطر\nسطر\n")
    assert result.exit_code == 0
    assert "warning" not in result.output
    assert bands(result.output) == 2


def test_size_flag() -> None:
    small = runner.invoke(app, ["خط", "-w", "200", "--size", "6"])
    large = runner.invoke(app, ["خط", "-w", "200", "--size", "14"])
    assert small.exit_code == large.exit_code == 0
    assert large.output.count("\n") > small.output.count("\n")


def test_fit_flag_fills_width() -> None:
    result = runner.invoke(app, ["خط", "-w", "30", "--fit"])
    assert result.exit_code == 0
    assert 28 <= max(len(line) for line in result.output.split("\n")) <= 30


def test_default_width_follows_terminal() -> None:
    result = runner.invoke(app, ["مرحبا بالعالم يا أصدقاء"], env={"COLUMNS": "40"})
    assert result.exit_code == 0
    assert max(len(line) for line in result.output.split("\n")) <= 40
    assert bands(result.output) >= 2


def test_output_png_text_multiline(tmp_path: Path) -> None:
    one, two = tmp_path / "one.png", tmp_path / "two.png"
    assert runner.invoke(app, ["خط", "--png", "text", "-o", str(one)]).exit_code == 0
    assert runner.invoke(app, ["--png", "text", "-o", str(two)], input="خط\nخط\n").exit_code == 0
    with Image.open(one) as a, Image.open(two) as b:
        assert b.size[1] > 2 * a.size[1]
        assert a.getpixel((0, 0)) == (255, 255, 255)  # black on white


def test_png_text_keeps_tashkeel_unless_stripped(tmp_path: Path) -> None:
    kept, stripped, plain = (tmp_path / f"{name}.png" for name in ("kept", "stripped", "plain"))
    voweled, text_png = "مَرْحَبًا", ["--png", "text", "-o"]
    strip = "--strip-tashkeel"
    assert runner.invoke(app, [voweled, *text_png, str(kept)]).exit_code == 0
    assert runner.invoke(app, [voweled, strip, *text_png, str(stripped)]).exit_code == 0
    assert runner.invoke(app, ["مرحبا", *text_png, str(plain)]).exit_code == 0
    with Image.open(kept) as a, Image.open(stripped) as b, Image.open(plain) as c:
        assert b.tobytes() == c.tobytes()
        assert a.tobytes() != c.tobytes()


def test_png_draws_the_art_by_default(tmp_path: Path) -> None:
    target = tmp_path / "art.png"
    args = ["مرحبا", "-s", "braille", "-w", "60"]
    art = runner.invoke(app, args).output.rstrip("\n").split("\n")
    assert runner.invoke(app, [*args, "-o", str(target)]).exit_code == 0
    with Image.open(target) as image:
        # Default cells are 12 px wide and 24 px tall, with one cell of padding.
        assert image.size == (12 * max(map(len, art)) + 24, 24 * len(art) + 24)


def test_png_colours_and_transparent_background(tmp_path: Path) -> None:
    target = tmp_path / "art.png"
    args = ["خط", "-w", "40", "--fg", "#ff0000", "--bg", "none", "-o", str(target)]
    assert runner.invoke(app, args).exit_code == 0
    with Image.open(target) as image:
        assert image.mode == "RGBA"
        assert image.getpixel((0, 0))[3] == 0
        opaque = {color[:3] for _, color in image.getcolors(1 << 20) or [] if color[3] == 255}
        assert opaque == {(255, 0, 0)}


def test_unknown_colour_fails() -> None:
    result = runner.invoke(app, ["خط", "--fg", "not-a-colour"])
    assert result.exit_code == 2


def test_art_strips_tashkeel_unless_kept() -> None:
    plain = runner.invoke(app, ["مرحبا", "-w", "60"]).output
    voweled = runner.invoke(app, ["مَرْحَبًا", "-w", "60"]).output
    kept = runner.invoke(app, ["مَرْحَبًا", "-w", "60", "--keep-tashkeel"]).output
    assert voweled == plain
    assert kept != plain


class TestEffect:
    def test_writes_word_art(self, tmp_path: Path) -> None:
        target = tmp_path / "gold.png"
        result = runner.invoke(app, ["خط", "--effect", "gold", "-o", str(target)])
        assert result.exit_code == 0
        image = Image.open(target)
        assert image.mode == "RGBA"
        assert image.getpixel((0, 0))[3] == 0  # transparent unless --bg says otherwise

    def test_size_and_background(self, tmp_path: Path) -> None:
        small, large = tmp_path / "small.png", tmp_path / "large.png"
        for target, size in ((small, "60"), (large, "120")):
            result = runner.invoke(
                app, ["خط", "-e", "gold", "--size-px", size, "--bg", "white", "-o", str(target)]
            )
            assert result.exit_code == 0
        assert Image.open(large).width > Image.open(small).width * 1.8
        assert Image.open(small).getpixel((0, 0)) == (255, 255, 255, 255)

    def test_starts_with_a_heavy_font(self, tmp_path: Path) -> None:
        target = tmp_path / "a.png"
        assert runner.invoke(app, ["خط", "-e", "gold", "-o", str(target)]).exit_code == 0
        expected = khatt.word_art("خط", effect="gold")
        assert expected is not None
        assert Image.open(target).tobytes() == expected.tobytes()

    def test_text_art_keeps_its_default_font(self) -> None:
        assert runner.invoke(app, ["خط"]).output == runner.invoke(app, ["خط", "-f", "amiri"]).output

    def test_lists_effects(self) -> None:
        result = runner.invoke(app, ["--list-effects"])
        assert result.exit_code == 0
        assert result.output.split() == khatt.list_effects()

    def test_needs_a_png(self, tmp_path: Path) -> None:
        for arguments in ([], ["-o", str(tmp_path / "art.txt")]):
            result = runner.invoke(app, ["خط", "--effect", "gold", *arguments])
            assert result.exit_code == 2
            assert ".png" in result.output

    def test_unknown_effect(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["خط", "-e", "glitter", "-o", str(tmp_path / "a.png")])
        assert result.exit_code == 2
        assert "glitter" in result.output

    def test_nothing_to_draw(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["   ", "-e", "gold", "-o", str(tmp_path / "a.png")])
        assert result.exit_code == 1


class TestCurve:
    def test_writes_curved_word_art(self, tmp_path: Path) -> None:
        target = tmp_path / "arc.png"
        result = runner.invoke(app, ["خط جميل", "--curve", "arc", "-o", str(target)])
        assert result.exit_code == 0
        expected = khatt.word_art("خط جميل", effect="gold", curve="arc")
        assert expected is not None
        assert Image.open(target).tobytes() == expected.tobytes()

    def test_with_an_effect(self, tmp_path: Path) -> None:
        target = tmp_path / "wave.png"
        result = runner.invoke(app, ["خط جميل", "-e", "neon", "--curve", "wave", "-o", str(target)])
        assert result.exit_code == 0
        assert target.is_file()

    def test_lists_curves(self) -> None:
        result = runner.invoke(app, ["--list-curves"])
        assert result.exit_code == 0
        assert result.output.split() == khatt.list_curves()

    def test_needs_a_png(self) -> None:
        result = runner.invoke(app, ["خط", "--curve", "arc"])
        assert result.exit_code == 2
        assert ".png" in result.output

    def test_unknown_curve(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["خط", "--curve", "zigzag", "-o", str(tmp_path / "a.png")])
        assert result.exit_code == 2
        assert "zigzag" in result.output

    def test_text_too_short(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["خط", "--curve", "ring", "-o", str(tmp_path / "a.png")])
        assert result.exit_code == 2
        assert "too short" in result.output


class TestShape:
    def test_writes_a_calligram(self, tmp_path: Path) -> None:
        target = tmp_path / "heart.png"
        result = runner.invoke(app, ["أحبك", "--shape", "heart", "-o", str(target)])
        assert result.exit_code == 0
        expected = khatt.calligram("أحبك", "heart")
        assert expected is not None
        assert Image.open(target).tobytes() == expected.tobytes()

    def test_once_with_an_effect_and_colour(self, tmp_path: Path) -> None:
        target = tmp_path / "circle.png"
        result = runner.invoke(
            app, ["خط جميل", "--shape", "circle", "--no-repeat", "-e", "gold", "-o", str(target)]
        )
        assert result.exit_code == 0
        assert target.is_file()

    def test_an_image_as_the_shape(self, tmp_path: Path) -> None:
        silhouette = tmp_path / "shape.png"
        image = Image.new("RGB", (200, 200), "white")
        image.paste("black", (20, 20, 180, 180))
        image.save(silhouette)
        target = tmp_path / "out.png"
        result = runner.invoke(app, ["أحبك", "--shape", str(silhouette), "-o", str(target)])
        assert result.exit_code == 0
        assert target.is_file()

    def test_lists_shapes(self) -> None:
        result = runner.invoke(app, ["--list-shapes"])
        assert result.exit_code == 0
        assert result.output.split() == khatt.list_shapes()

    def test_needs_a_png(self) -> None:
        result = runner.invoke(app, ["خط", "--shape", "heart"])
        assert result.exit_code == 2
        assert ".png" in result.output

    def test_unknown_shape(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["خط", "--shape", "triangle", "-o", str(tmp_path / "a.png")])
        assert result.exit_code == 2
        assert "triangle" in result.output

    def test_shape_or_curve(self, tmp_path: Path) -> None:
        result = runner.invoke(
            app, ["خط", "--shape", "heart", "--curve", "arc", "-o", str(tmp_path / "a.png")]
        )
        assert result.exit_code == 2
        assert "not both" in result.output

    def test_an_unreadable_image(self, tmp_path: Path) -> None:
        broken = tmp_path / "broken.png"
        broken.write_bytes(b"not an image")
        result = runner.invoke(app, ["خط", "--shape", str(broken), "-o", str(tmp_path / "a.png")])
        assert result.exit_code == 2
        assert "cannot read" in result.output


class TestZakhrafa:
    def test_one_style(self) -> None:
        result = runner.invoke(app, ["محمد", "--zakhrafa", "royal"])
        assert result.exit_code == 0
        assert result.output.strip() == khatt.zakhrafa("محمد", "royal")

    def test_all_styles(self) -> None:
        result = runner.invoke(app, ["محمد", "-z", "all"])
        assert result.exit_code == 0
        lines = result.output.strip().split("\n")
        assert [line.split()[0] for line in lines] == khatt.list_zakhrafa()

    def test_unknown_style(self) -> None:
        result = runner.invoke(app, ["محمد", "--zakhrafa", "sparkles"])
        assert result.exit_code == 2
        assert "sparkles" in result.output


class TestSvg:
    def test_writes_svg(self, tmp_path: Path) -> None:
        target = tmp_path / "khatt.svg"
        result = runner.invoke(app, ["خط جميل", "--font", "lalezar", "-o", str(target)])
        assert result.exit_code == 0
        svg = target.read_text(encoding="utf-8")
        assert svg == khatt.render_svg("خط جميل", font="lalezar", size_px=160)

    def test_colours(self, tmp_path: Path) -> None:
        target = tmp_path / "khatt.svg"
        result = runner.invoke(
            app, ["خط", "--fg", "#ff0000", "--bg", "white", "--size-px", "60", "-o", str(target)]
        )
        assert result.exit_code == 0
        svg = target.read_text(encoding="utf-8")
        assert 'fill="#ff0000"' in svg and "<rect" in svg
