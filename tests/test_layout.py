"""Line layout: multi-line input, word-wrap, FIGlet-style sizing and image output."""

from __future__ import annotations

import warnings

import pytest

import khatt
from khatt.layout import paragraphs, wrap

SENTENCE = "السلام عليكم ورحمة الله وبركاته"


def rows(art: str) -> list[str]:
    return art.split("\n")


def bands(art: str) -> list[list[str]]:
    """Group consecutive non-blank art lines: one group per rendered text line."""
    groups: list[list[str]] = [[]]
    for line in rows(art):
        if line.strip(" ⠀"):
            groups[-1].append(line)
        elif groups[-1]:
            groups.append([])
    return [group for group in groups if group]


def widest(art: str) -> int:
    return max(len(line) for line in rows(art))


class TestParagraphs:
    def test_every_line_break_style(self) -> None:
        assert paragraphs("a\r\nb\rc\nd") == ["a", "b", "c", "d"]

    def test_tabs_become_spaces(self) -> None:
        assert paragraphs("a\tb") == ["a b"]

    def test_blank_lines_are_kept(self) -> None:
        assert paragraphs("a\n\nb") == ["a", "", "b"]


class TestWrap:
    def test_fitting_paragraph_is_kept_verbatim(self) -> None:
        assert wrap("a  b", lambda line: True) == ["a  b"]

    def test_greedy_fill(self) -> None:
        assert wrap("aa bb cc dd", lambda line: len(line) <= 5) == ["aa bb", "cc dd"]

    def test_overlong_word_gets_its_own_line(self) -> None:
        assert wrap("a bbbbbbb c", lambda line: len(line) <= 3) == ["a", "bbbbbbb", "c"]

    def test_blank_paragraph(self) -> None:
        assert wrap("", lambda line: False) == [""]


class TestMultiLine:
    def test_line_break_is_not_an_unsupported_character(self) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            art = khatt.render("سطر\nسطر")
        assert len(bands(art)) == 2

    def test_lines_stack_vertically(self) -> None:
        one = khatt.render("مرحبا")
        two = khatt.render("مرحبا\nمرحبا")
        assert len(rows(two)) > 2 * len(rows(one))

    def test_crlf_renders_like_lf(self) -> None:
        assert khatt.render("خط\r\nمرحبا") == khatt.render("خط\nمرحبا")

    def test_blank_line_keeps_its_slot(self) -> None:
        assert len(rows(khatt.render("خط\n\nخط"))) > len(rows(khatt.render("خط\nخط")))


class TestSizing:
    def test_row_count_does_not_depend_on_text_length(self) -> None:
        short = khatt.render("خط", width=None)
        long = khatt.render("خط خط خط خط", width=None)
        assert len(rows(short)) == len(rows(long))
        assert widest(long) > widest(short)

    def test_bigger_size_means_more_rows(self) -> None:
        small = khatt.render("مرحبا", size=6, width=None)
        large = khatt.render("مرحبا", size=12, width=None)
        assert len(rows(large)) > len(rows(small))

    def test_same_height_in_every_style(self) -> None:
        heights = {len(rows(khatt.render("مرحبا", style=s))) for s in khatt.list_styles()}
        assert len(heights) == 1

    def test_no_width_never_wraps(self) -> None:
        assert len(bands(khatt.render(SENTENCE, width=None))) == 1


class TestWrapping:
    @pytest.mark.parametrize("width", [30, 60, 90])
    def test_lines_never_exceed_width(self, width: int) -> None:
        assert widest(khatt.render(SENTENCE, width=width)) <= width

    def test_long_text_wraps_into_several_lines(self) -> None:
        assert len(bands(khatt.render(SENTENCE, width=60))) >= 2

    def test_overlong_word_shrinks_to_fit(self) -> None:
        art = khatt.render("بالمستشفيات", width=20)
        assert art.strip()
        assert widest(art) <= 20

    def test_rtl_lines_are_right_aligned(self) -> None:
        right_edges = [max(len(line) for line in band) for band in bands(khatt.render(SENTENCE))]
        assert len(right_edges) >= 2
        assert max(right_edges) - min(right_edges) <= 1

    def test_ltr_lines_are_left_aligned(self) -> None:
        art = khatt.render("hello world from khatt", font="rubik", width=50)
        left_edges = [min(len(line) - len(line.lstrip()) for line in band) for band in bands(art)]
        assert len(left_edges) >= 2
        assert max(left_edges) <= 1


class TestFitMode:
    def test_fills_the_width(self) -> None:
        art = khatt.render("خط", width=40, size=None)
        assert 38 <= widest(art) <= 40

    def test_multi_line(self) -> None:
        art = khatt.render("خط\nمرحبا", width=40, size=None)
        assert len(bands(art)) == 2
        assert widest(art) <= 40

    def test_needs_a_width(self) -> None:
        with pytest.raises(ValueError, match="width"):
            khatt.render("خط", width=None, size=None)


class TestValidation:
    def test_width_must_be_positive(self) -> None:
        with pytest.raises(ValueError, match="width"):
            khatt.render("خط", width=0)

    def test_size_must_be_positive(self) -> None:
        with pytest.raises(ValueError, match="size"):
            khatt.render("خط", size=0)

    def test_threshold_out_of_range(self) -> None:
        with pytest.raises(ValueError, match="threshold"):
            khatt.render("خط", threshold=2)


class TestRenderImage:
    def test_black_ink_on_white(self) -> None:
        image = khatt.render_image("مرحبا")
        assert image is not None
        assert image.mode == "L"
        assert image.getpixel((0, 0)) == 255
        assert image.getextrema() == (0, 255)

    def test_multi_line_is_taller(self) -> None:
        one = khatt.render_image("مرحبا")
        two = khatt.render_image("مرحبا\nمرحبا")
        assert one is not None
        assert two is not None
        assert two.size[1] > 2 * one.size[1]

    def test_lines_align_by_direction(self) -> None:
        image = khatt.render_image("مرحبا\nKhatt 2026")
        assert image is not None
        width, height = image.size
        ink = image.point(lambda v: 255 - v)  # bbox wants non-zero ink
        top = ink.crop((0, 0, width, height // 2)).getbbox()
        bottom = ink.crop((0, height // 2, width, height)).getbbox()
        assert top is not None
        assert bottom is not None
        assert top[2] >= width - 2  # Arabic line: right-aligned
        assert bottom[0] <= 2  # Latin line: left-aligned

    def test_nothing_renderable_returns_none(self) -> None:
        assert khatt.render_image("   ") is None

    def test_unknown_font_raises(self) -> None:
        with pytest.raises(KeyError, match="available fonts"):
            khatt.render_image("خط", font="nope")
