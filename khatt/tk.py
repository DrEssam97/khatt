"""Arabic text for Tkinter labels, buttons and canvases.

Tk draws Arabic as separate letters, left to right, on Windows and Linux, and the
old fix (arabic_reshaper and ``get_display`` before giving Tk the string) draws it
backwards on macOS, where Tk shapes Arabic itself. :func:`tk_image` draws the text
with khatt instead and gives Tk a picture of it, which looks the same everywhere::

    import tkinter as tk
    import khatt

    root = tk.Tk()
    greeting = khatt.tk_image("مرحبا بكم", size_px=32)
    tk.Label(root, image=greeting).pack()
    root.mainloop()

``Entry`` and ``Text`` widgets are not covered: what is typed into them is still
drawn by Tk.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from khatt.caption import caption_image
from khatt.color import Fill
from khatt.fonts import Font


def tk_image(
    text: str,
    *,
    font: Font = "amiri",
    size_px: int = 24,
    fill: Fill = "black",
    background: Fill | None = None,
    max_width: int | None = None,
    align: str | None = None,
    padding: int = 0,
    stroke_width: float = 0,
    stroke_fill: Fill | None = None,
    keep_tashkeel: bool = True,
    digits: str | None = None,
    fallback_fonts: Font | Sequence[Font] = (),
    master: Any = None,
) -> Any:
    """``text`` drawn by khatt, as a Tkinter ``PhotoImage``.

    Pass it as the ``image`` of a ``Label`` or ``Button``, or to
    ``Canvas.create_image``. Keep a reference to it (for example as an attribute of
    the widget): Tk shows nothing once Python has dropped the image. Every image has
    the height of a line of the font, so labels and buttons in a row line up. A Tk
    window (``tk.Tk()``) must exist first, as for any ``PhotoImage``.

    For CustomTkinter, pass :func:`khatt.caption_image` (the same picture, as a
    Pillow image) to ``customtkinter.CTkImage``.

    Args:
        text: The text, as typed. Line breaks start new lines.
        font: A bundled font name (see :func:`khatt.list_fonts`) or the path to a
            .ttf/.otf font file.
        size_px: Font size in pixels per em.
        fill: Text colour: a name, ``#rrggbb[aa]``, or an RGB(A) tuple.
        background: A colour behind the text; default: transparent, so the
            widget's own background shows through.
        max_width: Wrap lines at spaces to this many pixels; the image is then
            this wide.
        align: ``"left"``, ``"right"`` or ``"center"`` alignment of lines;
            ``None`` aligns right-to-left paragraphs right and left-to-right ones
            left.
        padding: Empty pixels around the text.
        stroke_width: Width in pixels of an outline around the text.
        stroke_fill: Outline colour; default: ``fill``.
        keep_tashkeel: Keep Arabic diacritics (``False`` strips them).
        digits: ``"arabic-indic"`` writes the digits 0 to 9 as ٠ to ٩ (see
            :func:`khatt.arabic_digits`); default: as typed.
        fallback_fonts: Fonts for characters ``font`` has no glyph for.
        master: The Tk widget the image belongs to; default: the first ``Tk()``.

    Returns:
        A ``PIL.ImageTk.PhotoImage``.

    Raises:
        ImportError: Python was built without Tkinter.
    """
    try:
        from PIL import ImageTk
    except ImportError as exc:  # pragma: no cover - Pillow imports tkinter here
        raise ImportError("tk_image needs Tkinter, which this Python lacks") from exc
    image = caption_image(
        text,
        font=font,
        font_size=size_px,
        size=(max_width, None),
        margin=(padding, padding),
        color=fill,
        bg_color=background,
        stroke_color=stroke_fill,
        stroke_width=stroke_width,
        method="label" if max_width is None else "caption",
        text_align=align,
        keep_tashkeel=keep_tashkeel,
        digits=digits,
        fallback_fonts=fallback_fonts,
    )
    return ImageTk.PhotoImage(image, master=master)
