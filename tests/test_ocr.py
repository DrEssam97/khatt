"""khatt.ocr_lines and write_ocr_dataset: OCR line images with exact labels."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from cli_runner import invoke
from PIL import Image, ImageChops

import khatt
from khatt.cli import main
from khatt.layout import _ascender_px
from khatt.ocr import _turned

TEXTS = [
    "مرحبا بالعالم",
    "السعر 1,250 ريالا (شامل الضريبة)",
    "بِسْمِ اللَّهِ الرَّحْمَنِ الرَّحِيمِ",
    "تم الشحن عبر DHL يوم 15 مارس",
]


def ink(image: Image.Image, background: str = "white") -> tuple[int, int, int, int] | None:
    """The box of every pixel that is not the background."""
    return ImageChops.difference(image, Image.new("RGB", image.size, background)).getbbox()


class TestLines:
    def test_label_is_the_text_and_words_cover_the_ink(self) -> None:
        for line, text in zip(khatt.ocr_lines(TEXTS), TEXTS, strict=True):
            assert line.text == text
            assert [word.text for word in line.words] == text.split()
            assert all(line.text[w.start : w.end] == w.text for w in line.words)
            boxes = [word.box for word in line.words]
            union = (
                min(b[0] for b in boxes),
                min(b[1] for b in boxes),
                max(b[2] for b in boxes),
                max(b[3] for b in boxes),
            )
            assert ink(line.image) == union
            for box in boxes:
                assert ink(line.image.crop(box)) is not None

    def test_the_image_is_what_draw_text_draws(self) -> None:
        # Exact by construction: drawing the label again at the same place gives the
        # same pixels.
        line = next(khatt.ocr_lines(["مرحبا بالعالم"], size_px=40, padding=8))
        left, top, right, _ = khatt.text_bbox(line.text, size_px=40, anchor="ls")
        top = min(top, -_ascender_px(khatt.font_path("amiri"), 40))
        drawn = Image.new("RGB", line.image.size, "white")
        khatt.draw_text(drawn, (8 - left, 8 - top), line.text, size_px=40, anchor="ls")
        assert ImageChops.difference(drawn, line.image).getbbox() is None
        assert line.image.width == right - left + 16

    def test_same_seed_same_data(self) -> None:
        options = {
            "fonts": ["amiri", "cairo"],
            "size_px": (28, 44),
            "rotate": 3,
            "blur": 1,
            "noise": 12,
        }
        first = list(khatt.ocr_lines(TEXTS, seed=5, **options))
        second = list(khatt.ocr_lines(TEXTS, seed=5, **options))
        for a, b in zip(first, second, strict=True):
            assert (a.font, a.size_px, a.words) == (b.font, b.size_px, b.words)
            assert ImageChops.difference(a.image, b.image).getbbox() is None

    def test_picks_come_from_the_choices(self) -> None:
        lines = list(
            khatt.ocr_lines(
                TEXTS * 5,
                fonts=["amiri", "cairo"],
                size_px=(30, 34),
                fill=["black", (20, 30, 90)],
                background=["white", "#f4efe2"],
                seed=1,
            )
        )
        assert {line.font for line in lines} == {"amiri", "cairo"}
        assert all(30 <= line.size_px <= 34 for line in lines)
        corners = {line.image.getpixel((0, 0)) for line in lines}
        assert corners == {(255, 255, 255), (244, 239, 226)}

    def test_turned_boxes_hold_their_word(self) -> None:
        plain = next(khatt.ocr_lines(TEXTS[1:2]))
        turned = next(khatt.ocr_lines(TEXTS[1:2], rotate=5, seed=2))
        assert turned.image.size != plain.image.size
        for word in turned.words:
            assert ink(turned.image.crop(word.box)) is not None
        everything = ink(turned.image)
        assert everything is not None
        assert min(w.box[0] for w in turned.words) <= everything[0] + 1
        assert max(w.box[2] for w in turned.words) >= everything[2] - 1

    def test_turning_a_box(self) -> None:
        assert _turned((0, 0, 10, 10), 0, (5, 5), (0, 0)) == (0, 0, 10, 10)
        assert _turned((0, 0, 10, 2), 90, (5, 5), (0, 0)) == (0, 0, 2, 10)

    def test_blur_and_noise_change_pixels_not_labels(self) -> None:
        clean = next(khatt.ocr_lines(TEXTS[:1]))
        rough = next(khatt.ocr_lines(TEXTS[:1], blur=1.5, noise=20, seed=4))
        assert rough.text == clean.text and rough.words == clean.words
        assert ImageChops.difference(rough.image, clean.image).getbbox() is not None

    def test_labels_follow_what_is_drawn(self) -> None:
        stripped = next(khatt.ocr_lines(["بِسْمِ اللَّهِ"], keep_tashkeel=False))
        assert stripped.text == "بسم الله"
        digits = next(khatt.ocr_lines(["صفحة 15"], digits="arabic-indic"))
        assert digits.text == "صفحة ١٥"

    def test_blank_lines_are_skipped_and_breaks_trimmed(self) -> None:
        lines = list(khatt.ocr_lines(["مرحبا\n", "", "   ", "بالعالم\r\n"]))
        assert [line.text for line in lines] == ["مرحبا", "بالعالم"]

    @pytest.mark.parametrize(
        ("options", "match"),
        [
            ({"fonts": []}, "fonts"),
            ({"rotate": -1}, "rotate"),
            ({"blur": "a"}, "blur"),
            ({"size_px": (40, 20)}, "size_px"),
            ({"size_px": 0}, "size_px"),
        ],
    )
    def test_bad_arguments(self, options: dict[str, object], match: str) -> None:
        with pytest.raises(ValueError, match=match):
            next(khatt.ocr_lines(TEXTS, **options))  # type: ignore[arg-type]

    def test_one_line_each(self) -> None:
        with pytest.raises(ValueError, match="line break"):
            next(khatt.ocr_lines(["سطر\nسطر"]))

    def test_unknown_font(self) -> None:
        with pytest.raises(KeyError, match="unknown font"):
            next(khatt.ocr_lines(TEXTS, fonts=["nope"]))


class TestDataset:
    def test_files(self, tmp_path: Path) -> None:
        count = khatt.write_ocr_dataset([*TEXTS, ""], tmp_path / "data", seed=0)
        assert count == len(TEXTS)
        root = tmp_path / "data"
        assert sorted(p.name for p in (root / "images").iterdir()) == [
            f"{n:06d}.png" for n in range(1, len(TEXTS) + 1)
        ]
        records = [
            json.loads(line) for line in (root / "metadata.jsonl").read_text("utf-8").splitlines()
        ]
        assert [record["text"] for record in records] == TEXTS
        assert records[0]["file_name"] == "images/000001.png"
        assert [word["text"] for word in records[1]["words"]] == TEXTS[1].split()
        with Image.open(root / records[0]["file_name"]) as image:
            assert image.mode == "RGB"
        labels = (root / "labels.txt").read_text("utf-8").splitlines()
        assert labels[2] == f"images/000003.png\t{TEXTS[2]}"


class TestCommand:
    def test_from_a_file(self, tmp_path: Path) -> None:
        source = tmp_path / "lines.txt"
        source.write_text("\n".join(TEXTS) + "\n", encoding="utf-8")
        result = invoke(
            main,
            [
                str(source),
                "--ocr-data",
                str(tmp_path / "out"),
                "--font",
                "amiri,cairo",
                "--augment",
                "--seed",
                "3",
                "--arabic-digits",
            ],
        )
        assert result.exit_code == 0, result.output
        assert "wrote 4 images" in result.output
        labels = (tmp_path / "out" / "labels.txt").read_text("utf-8")
        assert "١٬٢٥٠" in labels and "1,250" not in labels

    def test_from_stdin(self, tmp_path: Path) -> None:
        result = invoke(main, ["--ocr-data", str(tmp_path / "out")], input="مرحبا\nبالعالم\n")
        assert result.exit_code == 0, result.output
        assert len(list((tmp_path / "out" / "images").iterdir())) == 2

    def test_needs_a_file(self, tmp_path: Path) -> None:
        result = invoke(main, ["مرحبا", "--ocr-data", str(tmp_path / "out")])
        assert result.exit_code == 2
        assert "is not a file" in result.output

    def test_unknown_font(self, tmp_path: Path) -> None:
        result = invoke(main, ["--ocr-data", str(tmp_path), "--font", "nope"], input="مرحبا\n")
        assert result.exit_code == 2
        assert "unknown font" in result.output
