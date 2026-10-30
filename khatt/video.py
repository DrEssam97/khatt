"""Captions for moviepy that shape Arabic: a drop-in for ``moviepy.TextClip``.

    from khatt.video import TextClip  # instead of: from moviepy import TextClip

moviepy's ``TextClip`` draws with Pillow, which shapes Arabic only when it
has Raqm (most Windows installs don't), and with Pillow 11 or later it cuts
off the bottom of label clips. :class:`TextClip` takes the same arguments
and draws through khatt (see :func:`khatt.caption.caption_image`).

Needs moviepy: ``pip install "khatt[video]"``.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from pathlib import Path

try:
    import numpy as np
    from moviepy import ImageClip
except ImportError as error:
    raise ImportError('khatt.video needs moviepy: pip install "khatt[video]"') from error

from khatt.caption import caption_image
from khatt.draw import Fill
from khatt.fonts import Font

__all__ = ["TextClip"]


class TextClip(ImageClip):
    """A text clip drawn by khatt, with moviepy's ``TextClip`` arguments.

    The arguments are moviepy 2.2's, in the same order and with the same
    meaning (see :func:`khatt.caption.caption_image`), except:

    * ``font`` is a bundled font name or a font file path, and ``None``
      means ``"amiri"`` instead of Pillow's bitmap font;
    * ``text_align`` defaults to ``None``: right-to-left paragraphs align
      right and left-to-right ones left;
    * ``filename`` is read as UTF-8 whatever the system locale;
    * ``keep_tashkeel`` (keyword only) can strip Arabic diacritics;
    * ``fallback_fonts`` (keyword only) are fonts for characters ``font``
      has no glyph for (see :func:`khatt.caption.caption_image`).

    Like moviepy's, it sets ``text``, ``color`` and ``stroke_color``.
    """

    def __init__(
        self,
        font: Font | None = None,
        text: str | None = None,
        filename: str | os.PathLike[str] | None = None,
        font_size: int | None = None,
        size: tuple[int | None, int | None] = (None, None),
        margin: Sequence[int | None] = (None, None),
        color: Fill = "black",
        bg_color: Fill | None = None,
        stroke_color: Fill | None = None,
        stroke_width: float = 0,
        method: str = "label",
        text_align: str | None = None,
        horizontal_align: str = "center",
        vertical_align: str = "center",
        interline: float = 4,
        transparent: bool = True,
        duration: float | None = None,
        *,
        keep_tashkeel: bool = True,
        fallback_fonts: Font | Sequence[Font] = (),
    ) -> None:
        if filename is not None:
            text = Path(filename).read_text(encoding="utf-8").rstrip()
        if text is None:
            raise ValueError("No text nor filename provided")
        image = caption_image(
            text,
            font=font,
            font_size=font_size,
            size=size,
            margin=margin,
            color=color,
            bg_color=bg_color,
            stroke_color=stroke_color,
            stroke_width=stroke_width,
            method=method,
            text_align=text_align,
            horizontal_align=horizontal_align,
            vertical_align=vertical_align,
            interline=interline,
            transparent=transparent,
            keep_tashkeel=keep_tashkeel,
            fallback_fonts=fallback_fonts,
        )
        # A writeable copy, as moviepy's: effects may edit frames in place.
        super().__init__(np.array(image), transparent=transparent, duration=duration)
        self.text = text
        self.color = color
        self.stroke_color = stroke_color
