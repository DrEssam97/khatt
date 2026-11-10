"""SVG output: the same shaping and layout as images, as real glyph outlines."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from itertools import pairwise
from typing import Any

import pytest
from PIL import Image, ImageChops, ImageDraw, ImageFilter

import khatt

SVG = "{http://www.w3.org/2000/svg}"
TEXT = "خط جميل بالعربية"
VOCALIZED = "بِسْمِ اللَّهِ الرَّحْمَٰنِ"
SCALE = 4
"""Outlines are drawn this many times too big, then shrunk, for smooth edges."""


def parse(svg: str) -> ET.Element:
    root = ET.fromstring(svg)
    assert root.tag == f"{SVG}svg"
    return root


def _numbers(text: str) -> list[float]:
    return [float(v) for v in re.findall(r"-?\d+(?:\.\d+)?", text)]


def contours(data: str, dx: float) -> list[list[tuple[float, float]]]:
    """Path data flattened to polygons: curves become short straight lines."""
    shapes: list[list[tuple[float, float]]] = []
    here = (0.0, 0.0)
    for command, args in re.findall(r"([MLQCZ])([^MLQCZ]*)", data):
        values = _numbers(args)
        points = [(values[i] + dx, values[i + 1]) for i in range(0, len(values), 2)]
        if command == "M":
            shapes.append([points[0]])
            here = points[0]
        elif command == "L":
            shapes[-1].append(points[0])
            here = points[0]
        elif command in "QC":
            control = [here, *points]
            for step in range(1, 9):
                t = step / 8
                level = control
                while len(level) > 1:
                    level = [
                        (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
                        for a, b in pairwise(level)
                    ]
                shapes[-1].append(level[0])
            here = points[-1]
    return shapes


def draw_svg(svg: str) -> Image.Image:
    """What the SVG's text looks like: each glyph even-odd, glyphs added together."""
    root = parse(svg)
    left, top, width, height = _numbers(root.attrib["viewBox"])
    size = (round(width * SCALE), round(height * SCALE))
    canvas = Image.new("L", size, 0)
    text_group = root.findall(f"{SVG}g")[-1]
    for element in text_group.findall(f"{SVG}path"):
        dx = _numbers(element.attrib.get("transform", "translate(0 0)"))[0]
        glyph = Image.new("L", size, 0)
        for contour in contours(element.attrib["d"], dx):
            if len(contour) < 3:
                continue
            ring = Image.new("L", size, 0)
            scaled = [((x - left) * SCALE, (y - top) * SCALE) for x, y in contour]
            ImageDraw.Draw(ring).polygon(scaled, fill=255)
            glyph = ImageChops.logical_xor(glyph.convert("1"), ring.convert("1")).convert("L")
        canvas = ImageChops.lighter(canvas, glyph)
    return canvas.reduce(SCALE)


def draw_png(text: str, **kwargs: Any) -> Image.Image:
    canvas = Image.new("RGB", (1600, 700), "black")
    return khatt.draw_text(canvas, (40, 40), text, fill="white", **kwargs).convert("L")


def overlap(a: Image.Image, b: Image.Image) -> float:
    """How much of each drawing's ink lies within a pixel of the other's, after lining them up.

    Images snap glyphs to quarter pixels and outlines don't, so edges can
    differ by a pixel; anything further apart is a real difference.
    """
    a, b = (im.point(lambda v: 255 if v >= 128 else 0) for im in (a, b))
    a, b = a.crop(a.getbbox()), b.crop(b.getbbox())
    size = (max(a.width, b.width), max(a.height, b.height))
    canvas_a, canvas_b = Image.new("L", size, 0), Image.new("L", size, 0)
    canvas_a.paste(a, (0, 0))
    canvas_b.paste(b, (0, 0))

    def near(ink: Image.Image, other: Image.Image) -> float:
        grown = other.filter(ImageFilter.MaxFilter(3))
        hit = ImageChops.logical_and(ink.convert("1"), grown.convert("1")).convert("L")
        return hit.histogram()[255] / ink.histogram()[255]

    return min(near(canvas_a, canvas_b), near(canvas_b, canvas_a))


class TestMatchesImages:
    """The SVG is the same text as khatt's images, drawn as outlines."""

    @pytest.mark.parametrize("font", ["amiri", "lalezar", "cairo", "aref-ruqaa", "rubik"])
    def test_one_line(self, font: str) -> None:
        kwargs = {"font": font, "size_px": 80}
        svg = khatt.render_svg(TEXT, **kwargs)
        assert svg is not None
        assert overlap(draw_svg(svg), draw_png(TEXT, **kwargs)) > 0.99

    def test_tashkeel(self) -> None:
        svg = khatt.render_svg(VOCALIZED, size_px=90)
        assert svg is not None
        assert overlap(draw_svg(svg), draw_png(VOCALIZED, size_px=90)) > 0.99

    @pytest.mark.parametrize("align", [None, "center", "left"])
    def test_lines_and_alignment(self, align: str | None) -> None:
        text = "مرحبا بالعالم\nأهلا"
        kwargs: dict[str, Any] = {"size_px": 70, "align": align}
        svg = khatt.render_svg(text, **kwargs)
        assert svg is not None
        assert overlap(draw_svg(svg), draw_png(text, **kwargs)) > 0.99

    def test_wrapping(self) -> None:
        text = f"{TEXT} {TEXT} {TEXT}"
        kwargs: dict[str, Any] = {"size_px": 60, "max_width": 500}
        svg = khatt.render_svg(text, **kwargs)
        assert svg is not None
        assert overlap(draw_svg(svg), draw_png(text, **kwargs)) > 0.99

    def test_mixed_scripts_and_brackets(self) -> None:
        text = "Cairo القاهرة (2026)"
        svg = khatt.render_svg(text, font="rubik", size_px=70)
        assert svg is not None
        assert overlap(draw_svg(svg), draw_png(text, font="rubik", size_px=70)) > 0.99

    def test_fallback_fonts(self) -> None:
        text = "مرحبا שלום"
        kwargs: dict[str, Any] = {"font": "amiri", "size_px": 70, "fallback_fonts": ["rubik"]}
        svg = khatt.render_svg(text, **kwargs)
        assert svg is not None
        assert overlap(draw_svg(svg), draw_png(text, **kwargs)) > 0.99

    def test_size_matches_text_bbox(self) -> None:
        svg = khatt.render_svg(TEXT, font="lalezar", size_px=100)
        assert svg is not None
        root = parse(svg)
        left, top, right, bottom = khatt.text_bbox(TEXT, font="lalezar", size_px=100)
        assert float(root.attrib["width"]) == pytest.approx(right - left, abs=3)
        assert float(root.attrib["height"]) == pytest.approx(bottom - top, abs=3)


class TestDocument:
    def test_valid_svg_with_a_title(self) -> None:
        root = parse(khatt.render_svg(TEXT) or "")
        assert root.find(f"{SVG}title") is not None
        assert root.find(f"{SVG}title").text == TEXT  # type: ignore[union-attr]

    def test_one_path_per_glyph_with_ink(self) -> None:
        root = parse(khatt.render_svg("خط", font="lalezar") or "")
        assert len(root.findall(f".//{SVG}path")) == 2

    def test_colour_and_opacity(self) -> None:
        root = parse(khatt.render_svg(TEXT, fill="#ff000080") or "")
        group = root.findall(f"{SVG}g")[-1]
        assert group.attrib["fill"] == "#ff0000"
        assert float(group.attrib["fill-opacity"]) == pytest.approx(0.5, abs=0.01)

    def test_background_and_padding(self) -> None:
        plain = parse(khatt.render_svg(TEXT) or "")
        padded = parse(khatt.render_svg(TEXT, padding=10, background="white") or "")
        assert float(padded.attrib["width"]) == pytest.approx(
            float(plain.attrib["width"]) + 20, abs=1
        )
        rect = padded.find(f"{SVG}rect")
        assert rect is not None and rect.attrib["fill"] == "#ffffff"

    def test_outline_goes_under_the_text(self) -> None:
        root = parse(khatt.render_svg(TEXT, stroke_width=4, stroke_fill="gold", fill="black") or "")
        outline, text = root.findall(f"{SVG}g")
        assert outline.attrib["stroke"] == "#ffd700" and outline.attrib["stroke-width"] == "8"
        assert text.attrib["fill"] == "#000000"

    def test_title_is_escaped(self) -> None:
        root = parse(khatt.render_svg("a < b & c") or "")
        assert root.find(f"{SVG}title").text == "a < b & c"  # type: ignore[union-attr]

    def test_nothing_to_draw(self) -> None:
        assert khatt.render_svg("") is None
        assert khatt.render_svg("   ") is None

    def test_same_text_same_svg(self) -> None:
        assert khatt.render_svg(TEXT) == khatt.render_svg(TEXT)


class TestErrors:
    @pytest.mark.parametrize(
        ("kwargs", "match"),
        [
            ({"size_px": 0}, "size_px"),
            ({"fill": "nope"}, ""),
            ({"stroke_width": -1}, "stroke_width"),
            ({"padding": -1}, "padding"),
            ({"max_width": 0}, "max_width"),
            ({"align": "middle"}, "align"),
            ({"line_spacing": 1.2, "spacing": 4}, "not both"),
        ],
    )
    def test_bad_values(self, kwargs: dict[str, Any], match: str) -> None:
        with pytest.raises(ValueError, match=match or None):
            khatt.render_svg(TEXT, **kwargs)

    def test_unknown_font(self) -> None:
        with pytest.raises(KeyError):
            khatt.render_svg(TEXT, font="nope")
