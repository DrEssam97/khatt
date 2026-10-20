"""Tests for the bundled-font registry and user font files."""

from __future__ import annotations

import shutil
import struct
import warnings
from pathlib import Path

import pytest
from PIL import Image
from typer.testing import CliRunner

import khatt
from khatt import fonts
from khatt.cli import app
from khatt.fonts import available_fonts, font_path
from khatt.raster import _face
from khatt.shaping import REGULAR_WEIGHT, variations


def test_all_registered_fonts_exist_on_disk() -> None:
    for name in available_fonts():
        assert font_path(name).is_file()


def test_lookup_is_case_insensitive() -> None:
    assert font_path("Amiri") == font_path("amiri")


def test_unknown_font_raises_with_available_names() -> None:
    with pytest.raises(KeyError, match="amiri"):
        font_path("definitely-not-a-font")


def test_amiri_is_bundled() -> None:
    assert "amiri" in available_fonts()


def test_every_font_family_has_a_license() -> None:
    licenses_dir = font_path("amiri").parent / "LICENSES"
    assert licenses_dir.is_dir()
    assert any(licenses_dir.iterdir())


def to_woff(sfnt: bytes) -> bytes:
    """Wrap a TrueType font as an (uncompressed) WOFF 1.0 web font."""
    flavor, count = struct.unpack(">IH", sfnt[:6])
    records = [struct.unpack(">4sIII", sfnt[12 + 16 * i : 28 + 16 * i]) for i in range(count)]
    offset = 44 + 20 * count
    directory, data = b"", b""
    for tag, checksum, start, length in records:
        directory += struct.pack(">4sIIII", tag, offset + len(data), length, length, checksum)
        table = sfnt[start : start + length]
        data += table + b"\0" * (-len(table) % 4)
    sfnt_size = 12 + 16 * count + sum(length + (-length % 4) for *_, length in records)
    length = 44 + len(directory) + len(data)
    # signature, flavor, length, numTables, reserved, totalSfntSize, version 1.0,
    # then no metadata or private blocks.
    header = struct.pack(
        ">4sIIHHIHH5I", b"wOFF", flavor, length, count, 0, sfnt_size, 1, 0, *[0] * 5
    )
    return header + directory + data


class TestFontFiles:
    @pytest.fixture
    def amiri_copy(self, tmp_path: Path) -> Path:
        """The bundled Amiri copied under a non-ASCII directory and file name."""
        folder = tmp_path / "خطوط"
        folder.mkdir()
        return Path(shutil.copy(font_path("amiri"), folder / "أميري.ttf"))

    def test_path_resolves_to_the_file(self, amiri_copy: Path) -> None:
        assert font_path(amiri_copy) == amiri_copy.resolve()
        assert font_path(str(amiri_copy)) == amiri_copy.resolve()

    def test_relative_path(self, amiri_copy: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(amiri_copy.parent)
        assert font_path("أميري.ttf") == amiri_copy.resolve()

    def test_renders_like_the_bundled_font(self, amiri_copy: Path) -> None:
        assert khatt.render("مرحبا بالعالم", font=amiri_copy) == khatt.render("مرحبا بالعالم")
        own = khatt.render_image("خط", font=str(amiri_copy))
        bundled = khatt.render_image("خط")
        assert own is not None
        assert bundled is not None
        assert own.tobytes() == bundled.tobytes()

    def test_draws_like_the_bundled_font(self, amiri_copy: Path) -> None:
        def draw(font: fonts.Font) -> bytes:
            image = Image.new("RGB", (400, 200), "white")
            khatt.draw_text(image, (380, 10), "مرحبا", font=font, anchor="ra")
            khatt.overlay(image, "شهادة تقدير", (10, 100, 390, 190), font=font)
            return image.tobytes()

        assert draw(amiri_copy) == draw("amiri")

    def test_bundled_name_wins_over_a_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / "amiri").write_bytes(b"not a font")
        monkeypatch.chdir(tmp_path)
        assert font_path("amiri") == font_path("AMIRI")
        assert font_path("amiri").parent == Path(fonts.__file__).resolve().parent

    @pytest.mark.parametrize("missing", ["missing.ttf", Path("no/such/font.otf"), "", "."])
    def test_missing_file(self, missing: str | Path) -> None:
        with pytest.raises(KeyError, match=r"available fonts: amiri.*\.ttf"):
            font_path(missing)

    def test_not_a_font(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.ttf"
        bad.write_bytes(b"definitely not a font")
        with pytest.raises(ValueError, match="not a TrueType or OpenType font"):
            font_path(bad)
        with pytest.raises(ValueError, match="not a TrueType or OpenType font"):
            khatt.render("خط", font=bad)

    def test_web_font(self, tmp_path: Path) -> None:
        woff = tmp_path / "amiri.woff"
        woff.write_bytes(to_woff(font_path("amiri").read_bytes()))
        with pytest.raises(ValueError, match=r"web font .*\.ttf or \.otf"):
            font_path(woff)

    def test_bitmap_only_font(self, amiri_copy: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        class BitmapFace:
            is_scalable = False

            def __init__(self, stream: object) -> None:
                pass

        monkeypatch.setattr(fonts.freetype, "Face", BitmapFace)
        fonts._check_font_file.cache_clear()
        try:
            with pytest.raises(ValueError, match="bitmap-only"):
                font_path(amiri_copy)
        finally:
            fonts._check_font_file.cache_clear()

    def test_cli_font_file(self, amiri_copy: Path, tmp_path: Path) -> None:
        runner = CliRunner()
        own = runner.invoke(app, ["خط", "-w", "40", "--font", str(amiri_copy)])
        bundled = runner.invoke(app, ["خط", "-w", "40"])
        assert own.exit_code == 0
        assert own.output == bundled.output

        bad = tmp_path / "bad.otf"
        bad.write_bytes(b"nope")
        result = runner.invoke(app, ["خط", "--font", str(bad)])
        assert result.exit_code == 2
        assert "error: cannot load font file" in result.output


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("amiri", {}),  # static font: nothing to set
        ("cairo", {"wght": REGULAR_WEIGHT}),
        ("noto-naskh", {"wght": REGULAR_WEIGHT}),
        ("rubik", {"wght": REGULAR_WEIGHT}),  # its default instance is Light (300)
    ],
)
def test_variable_fonts_render_at_regular_weight(name: str, expected: dict[str, float]) -> None:
    assert variations(font_path(name)) == expected


def test_freetype_rasterizes_the_instance_harfbuzz_shapes() -> None:
    for name in available_fonts():
        path = str(font_path(name))
        settings = variations(path)
        if not settings:
            continue
        face = _face(path)
        coords = dict(
            zip(
                (a.tag for a in face.get_variation_info().axes),
                face.get_var_design_coords(),
                strict=True,
            )
        )
        assert coords["wght"] == settings["wght"], name


class TestMissingCharacters:
    def test_bundled_fonts_cover_arabic_persian_and_latin(self) -> None:
        text = "بِسْمِ اللَّهِ الرَّحْمَٰنِ — پ چ ژ گ — Khatt 2026 ٠١٢"
        for name in available_fonts():
            assert khatt.missing_characters(text, name) == [], name

    def test_urdu_letters_rubik_lacks(self) -> None:
        assert khatt.missing_characters("پاکستان ے ٹ ڈ", "amiri") == []
        assert khatt.missing_characters("ٹیکسی ے", "rubik") == ["ٹ", "ے"]

    def test_each_once_in_logical_order(self) -> None:
        # Right-to-left text: in the order typed, not the order displayed.
        assert khatt.missing_characters("ے 😀 ٹ 😀 ے", "rubik") == ["ے", "😀", "ٹ"]

    def test_a_missing_diacritic_is_reported_not_its_letter(self) -> None:
        assert khatt.missing_characters("بٟت", "rubik") == ["ٟ"]

    def test_stripped_diacritics_are_not_missing(self) -> None:
        # As drawing with keep_tashkeel=False, or render(), would skip nothing.
        assert khatt.missing_characters("بٟت", "rubik", keep_tashkeel=False) == []

    def test_invisible_characters_and_line_breaks_are_not_missing(self) -> None:
        text = "لا‍م‌ا‏ب\nسطر\tآخر\r\nKhatt"
        assert khatt.missing_characters(text, "amiri") == []

    def test_empty_text(self) -> None:
        assert khatt.missing_characters("", "amiri") == []

    def test_names_exactly_what_drawing_skips(self) -> None:
        text = "خط ے 😀 ✓ a͙ ٹ\nسطر"
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            khatt.draw_text(Image.new("RGB", (900, 300), "white"), (10, 10), text, font="rubik")
        skipped = {
            str(w.message).split("'")[1]
            for w in caught
            if issubclass(w.category, khatt.UnsupportedCharacterWarning)
        }
        assert skipped == set(khatt.missing_characters(text, "rubik"))
        assert len(skipped) == 5

    def test_font_file(self, tmp_path: Path) -> None:
        copy = Path(shutil.copy(font_path("rubik"), tmp_path / "brand.ttf"))
        assert khatt.missing_characters("ے", copy) == ["ے"]

    def test_unknown_font(self) -> None:
        with pytest.raises(KeyError):
            khatt.missing_characters("خط", "nope")
