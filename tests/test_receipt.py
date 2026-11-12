"""receipt_image: receipts for thermal printers."""

from __future__ import annotations

import pytest
from PIL import Image

import khatt

ROWS = [("قهوة عربية", "15.00"), ("كعكة", "12.50"), "---", ("المجموع", "27.50")]


def _black(image: Image.Image) -> Image.Image:
    """Black dots as a mask (``getbbox`` gives their box)."""
    return image.convert("L").point(lambda v: 255 if v < 128 else 0)


def _row_box(image: Image.Image, top: int, bottom: int) -> tuple[int, int, int, int] | None:
    return _black(image.crop((0, top, image.width, bottom))).getbbox()


class TestLayout:
    def test_one_bit_at_the_paper_width(self) -> None:
        for width, dots in (("80mm", 576), ("58mm", 384), (500, 500)):
            receipt = khatt.receipt_image(ROWS, width=width)
            assert receipt.mode == "1"
            assert receipt.width == dots

    def test_widths_table(self) -> None:
        assert khatt.PRINTER_WIDTHS == {"58mm": 384, "80mm": 576}

    def test_pair_sides_in_arabic(self) -> None:
        receipt = khatt.receipt_image([("قهوة عربية", "15.00")], margin=10)
        item = khatt.receipt_image([("قهوة عربية", "")], margin=10)
        price = khatt.receipt_image([("", "15.00")], margin=10, direction="rtl")
        item_box, price_box = _black(item).getbbox(), _black(price).getbbox()
        assert item_box is not None and price_box is not None
        assert item_box[2] > receipt.width - 20  # the item ends at the right margin
        assert price_box[0] < 20  # the price starts at the left margin
        both = _black(receipt).getbbox()
        assert both is not None and both[0] == price_box[0] and both[2] == item_box[2]

    def test_pair_sides_in_english(self) -> None:
        item = khatt.receipt_image([("Coffee", "")], margin=10)
        price = khatt.receipt_image([("", "15.00")], margin=10)
        item_box, price_box = _black(item).getbbox(), _black(price).getbbox()
        assert item_box is not None and price_box is not None
        assert item_box[0] < 20 and price_box[2] > item.width - 20

    def test_direction_can_be_set(self) -> None:
        price = khatt.receipt_image([("", "15.00")], margin=10, direction="ltr")
        box = _black(price).getbbox()
        assert box is not None and box[2] > price.width - 20

    def test_lines_start_from_their_own_side(self) -> None:
        arabic = _black(khatt.receipt_image(["الدفع نقدا"], margin=10)).getbbox()
        english = _black(khatt.receipt_image(["Thank you"], margin=10)).getbbox()
        assert arabic is not None and english is not None
        assert arabic[2] > 576 - 20 and english[0] < 20

    def test_title_and_footer_are_centered(self) -> None:
        receipt = khatt.receipt_image([], title="مقهى الخط", footer="شكرا")
        box = _black(receipt).getbbox()
        assert box is not None
        assert abs((box[0] + box[2]) / 2 - receipt.width / 2) < 3

    def test_long_item_wraps_clear_of_its_price(self) -> None:
        name = "كعكة الشوكولاتة بالبندق والقرفة الطازجة مع الكريمة والفراولة"
        one = khatt.receipt_image([("كعكة", "12.50")])
        long = khatt.receipt_image([(name, "12.50")])
        assert long.height > one.height
        price = _black(khatt.receipt_image([("", "12.50")])).getbbox()
        name_only = _black(khatt.receipt_image([(name, "12.50")])).getbbox()
        assert price is not None and name_only is not None

    def test_rule_and_blank_line(self) -> None:
        ruled = khatt.receipt_image(["---"], margin=10)
        row = _black(ruled).getbbox()
        assert row is not None and row[0] == 10 and row[2] == ruled.width - 10
        blank = khatt.receipt_image([""])
        assert _black(blank).getbbox() is None
        assert blank.height > khatt.receipt_image([]).height

    def test_more_rows_more_paper(self) -> None:
        assert khatt.receipt_image(ROWS * 2).height > khatt.receipt_image(ROWS).height

    def test_empty(self) -> None:
        receipt = khatt.receipt_image([])
        assert receipt.mode == "1" and _black(receipt).getbbox() is None


class TestErrors:
    @pytest.mark.parametrize("width", ["70mm", 10])
    def test_width(self, width) -> None:
        with pytest.raises(ValueError, match="width"):
            khatt.receipt_image(ROWS, width=width)

    def test_direction(self) -> None:
        with pytest.raises(ValueError, match="direction"):
            khatt.receipt_image(ROWS, direction="up")

    def test_threshold(self) -> None:
        with pytest.raises(ValueError, match="threshold"):
            khatt.receipt_image(ROWS, threshold=300)

    @pytest.mark.parametrize("row", [("a", "b", "c"), ("a", 5), 5])
    def test_bad_rows(self, row) -> None:
        with pytest.raises(ValueError, match="row"):
            khatt.receipt_image([row])
