"""khatt.tk_image: Arabic text as a Tkinter PhotoImage."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from PIL import ImageChops

import khatt

tkinter = pytest.importorskip("tkinter")
ImageTk = pytest.importorskip("PIL.ImageTk")


@pytest.fixture(scope="module")
def root() -> Iterator[Any]:
    try:
        window = tkinter.Tk()
    except tkinter.TclError as exc:  # no display, as on a headless Linux runner
        pytest.skip(f"Tk cannot open a window here: {exc}")
    window.withdraw()
    yield window
    window.destroy()


def test_is_the_caption_image(root: Any) -> None:
    image = khatt.tk_image("مرحبا بكم", size_px=32, master=root)
    assert isinstance(image, ImageTk.PhotoImage)
    expected = khatt.caption_image("مرحبا بكم", font_size=32)
    assert (image.width(), image.height()) == expected.size
    shown = ImageTk.getimage(image)
    assert ImageChops.difference(shown, expected).getbbox() is None


def test_buttons_in_a_row_line_up(root: Any) -> None:
    heights = {khatt.tk_image(text, master=root).height() for text in ("ب", "ألج", "حفظ", "Save")}
    assert len(heights) == 1


def test_options(root: Any) -> None:
    padded = khatt.tk_image("حفظ", padding=6, background="white", master=root)
    plain = khatt.tk_image("حفظ", master=root)
    assert padded.width() == plain.width() + 12
    assert ImageTk.getimage(padded).getpixel((0, 0)) == (255, 255, 255, 255)
    wrapped = khatt.tk_image("نص طويل يلتف على أكثر من سطر واحد", max_width=120, master=root)
    assert wrapped.width() == 120
    assert wrapped.height() > plain.height()
    digits = khatt.tk_image("2026", digits="arabic-indic", master=root)
    typed = khatt.tk_image("٢٠٢٦", master=root)
    assert (
        ImageChops.difference(ImageTk.getimage(digits), ImageTk.getimage(typed)).getbbox() is None
    )


def test_shows_in_a_label(root: Any) -> None:
    image = khatt.tk_image("مرحبا", master=root)
    label = tkinter.Label(root, image=image)
    label.pack()
    root.update_idletasks()
    assert label.winfo_reqwidth() >= image.width()
