"""align="justify" (kashida, then spaces) and khatt.poem."""

from __future__ import annotations

import pytest
from PIL import Image, ImageChops

import khatt
from khatt.fonts import font_path
from khatt.kashida import MOST_KASHIDA, TATWEEL, justify, justify_point
from khatt.layout import _shape_lines
from khatt.raster import estimate

PARAGRAPH = (
    "الخط العربي فن عريق يجمع بين الجمال والدقة، وقد تطور عبر القرون على أيدي الخطاطين "
    "في بغداد ودمشق والقاهرة وإسطنبول، فظهرت أنواع كثيرة مثل النسخ والثلث والرقعة "
    "والديواني، ولكل نوع منها قواعده وموازينه التي يتعلمها الطالب سنوات طويلة"
)
ENGLISH = (
    "The quick brown fox jumps over the lazy dog while the cat sleeps by the warm fire "
    "and the rain falls on the old roof of the house"
)
POEM = (
    "قفا نبك من ذكرى حبيب ومنزل * بسقط اللوى بين الدخول فحومل\n"
    "فتوضح فالمقراة لم يعف رسمها * لما نسجتها من جنوب وشمأل"
)


def widths(text: str, target: int, font: str = "amiri", size: int = 36) -> list[int]:
    path = font_path(font)
    lines = _shape_lines(text, path, True, target, ppem=size, justify=target)
    boxes = [estimate(glyphs, path, ppem=size) for glyphs in lines.glyphs]
    return [box[2] - box[0] for box in boxes if box is not None]


def same(a: Image.Image, b: Image.Image) -> bool:
    return a.size == b.size and ImageChops.difference(a, b).getbbox() is None


class TestKashidaPoints:
    @pytest.mark.parametrize("word", ["الله", "لله", "بالله", "في", "من", "و"])
    def test_left_alone(self, word: str) -> None:
        assert justify_point(word) is None

    def test_after_seen_like_letters(self) -> None:
        assert justify_point("مسجد") == 2  # مسـجد
        assert justify_point("يصبر") == 2  # يصـبر

    def test_before_the_last_joined_letter(self) -> None:
        assert justify_point("كتاب") == 2  # كتـاب: ا never joins the ب after it
        assert justify_point("محمد") == 3  # محمـد

    def test_marks_stay_on_their_letter(self) -> None:
        word = "مُحَمَّد"
        point = justify_point(word)
        assert point is not None
        assert word[:point] + TATWEEL + word[point:] == "مُحَمَّـد"

    def test_justify_spreads_and_caps(self) -> None:
        line = "كتب محمد درسا طويلا"
        stretched = justify(line, 100)
        assert stretched.replace(TATWEEL, "") == line
        assert stretched.count(TATWEEL) == 4 * MOST_KASHIDA
        assert all(word.count(TATWEEL) <= MOST_KASHIDA for word in stretched.split())
        assert justify(line, 2).count(TATWEEL) == 2
        assert justify("في من", 5) == "في من"


class TestJustify:
    @pytest.mark.parametrize(
        ("text", "target"), [(PARAGRAPH, 580), (PARAGRAPH, 300), (ENGLISH, 500)]
    )
    def test_lines_fill_the_width_but_the_last(self, text: str, target: int) -> None:
        lines = widths(text, target)
        assert len(lines) > 2
        assert all(abs(width - target) <= 1 for width in lines[:-1]), lines
        assert lines[-1] < target - 20

    def test_arabic_gets_kashida_and_keeps_its_words(self) -> None:
        path = font_path("amiri")
        lines = _shape_lines(PARAGRAPH, path, True, 300, ppem=36, justify=300, track=True)
        indexes = sorted({glyph.index for line in lines.glyphs for glyph in line})
        assert indexes[0] >= 0 and indexes[-1] < len(PARAGRAPH)

    def test_draw_text(self) -> None:
        image = Image.new("RGB", (620, 260), "white")
        khatt.draw_text(
            image, (600, 10), PARAGRAPH, anchor="ra", size_px=36, max_width=580, align="justify"
        )
        assert khatt.text_bbox(PARAGRAPH, size_px=36, max_width=580, align="justify")[2] == 580
        plain = Image.new("RGB", (620, 260), "white")
        khatt.draw_text(plain, (600, 10), PARAGRAPH, anchor="ra", size_px=36, max_width=580)
        assert not same(image, plain)

    def test_nothing_to_justify_without_wrapping(self) -> None:
        one = khatt.draw_text(
            Image.new("RGB", (500, 80), "white"), (10, 10), "مرحبا بالعالم", align="justify"
        )
        two = khatt.draw_text(Image.new("RGB", (500, 80), "white"), (10, 10), "مرحبا بالعالم")
        assert same(one, two)

    def test_spans_keep_the_layout(self) -> None:
        start = PARAGRAPH.index("الجمال")
        coloured = Image.new("RGB", (620, 260), "white")
        khatt.draw_text(
            coloured,
            (10, 10),
            PARAGRAPH,
            size_px=36,
            max_width=580,
            align="justify",
            spans=[(start, start + 6, "red")],
        )
        plain = Image.new("RGB", (620, 260), "white")
        khatt.draw_text(plain, (10, 10), PARAGRAPH, size_px=36, max_width=580, align="justify")
        assert (
            coloured.convert("L").point(lambda v: v < 250).getbbox()
            == plain.convert("L").point(lambda v: v < 250).getbbox()
        )
        assert (255, 0, 0) in {colour for _, colour in coloured.getcolors(1 << 16) or []}

    def test_word_boxes(self) -> None:
        words = khatt.word_boxes(PARAGRAPH, size_px=36, max_width=580, align="justify")
        assert [word.text for word in words] == PARAGRAPH.split()

    def test_overlay_caption_svg_and_tk_names(self) -> None:
        image = Image.new("RGB", (400, 300), "white")
        khatt.overlay(image, PARAGRAPH, (0, 0, 400, 300), align="justify")
        caption = khatt.caption_image(
            PARAGRAPH, font_size=30, size=(400, None), method="caption", text_align="justify"
        )
        assert caption.size[0] == 400
        svg = khatt.render_svg(PARAGRAPH, size_px=30, max_width=400, align="justify")
        assert svg is not None and "<path" in svg
        with pytest.raises(ValueError, match="align"):
            khatt.draw_text(image, (0, 0), "x", align="justified")


class TestPoem:
    def test_two_columns_with_straight_edges(self) -> None:
        image = khatt.poem(POEM, size_px=40)
        assert image is not None and image.mode == "RGBA"
        alpha = image.getchannel("A")
        middle = image.width // 2
        gap_columns = [
            x
            for x in range(image.width)
            if alpha.crop((x, 0, x + 1, image.height)).getbbox() is None
        ]
        assert any(abs(x - middle) < 40 for x in gap_columns)  # the gap between halves

    def test_text_forms(self) -> None:
        pairs = [
            ("قفا نبك من ذكرى حبيب ومنزل", "بسقط اللوى بين الدخول فحومل"),
            ("فتوضح فالمقراة لم يعف رسمها", "لما نسجتها من جنوب وشمأل"),
        ]
        expected = khatt.poem(pairs, size_px=30)
        assert expected is not None
        for text in (
            POEM,
            POEM.replace(" * ", "\t"),
            POEM.replace(" * ", "    "),
            POEM.replace(" * ", " *** "),
            "\n" + POEM + "\n\n",
        ):
            drawn = khatt.poem(text, size_px=30)
            assert drawn is not None and same(drawn, expected)

    def test_first_half_on_the_right(self) -> None:
        image = khatt.poem([("كتب محمد درسا طويلا جدا", "ب")], size_px=40)
        assert image is not None
        alpha = image.getchannel("A")
        half = image.width // 2
        right = sum(alpha.crop((half, 0, image.width, image.height)).histogram()[128:])
        left = sum(alpha.crop((0, 0, half, image.height)).histogram()[128:])
        assert right > 4 * left

    def test_options(self) -> None:
        plain = khatt.poem(POEM, size_px=30)
        wide = khatt.poem(POEM, size_px=30, gap=100, padding=10, background="white")
        assert plain is not None and wide is not None
        assert wide.width == plain.width + (100 - 45) + 20
        assert wide.getpixel((0, 0)) == (255, 255, 255, 255)
        digits = khatt.poem([("صفحة 15 من الكتاب", "سطر 20 في الصفحة")], digits="arabic-indic")
        typed = khatt.poem([("صفحة ١٥ من الكتاب", "سطر ٢٠ في الصفحة")])
        assert digits is not None and typed is not None and same(digits, typed)
        assert khatt.poem("") is None
        assert khatt.poem(POEM, stroke_width=2, stroke_fill="white") is not None

    @pytest.mark.parametrize("verses", ["نصف واحد فقط", [("one",)], [("a", 1)]])
    def test_a_verse_needs_two_halves(self, verses: object) -> None:
        with pytest.raises(ValueError, match="two"):
            khatt.poem(verses)  # type: ignore[arg-type]
