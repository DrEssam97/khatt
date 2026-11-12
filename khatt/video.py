"""Captions for moviepy that shape Arabic: a drop-in for ``moviepy.TextClip``.

    from khatt.video import TextClip  # instead of: from moviepy import TextClip

:func:`word_captions` makes word-timed captions, each word lighting up as it
is said, from a speech recogniser's word timings; :func:`quran_captions` does
the same for a recitation, with verse numbers and room for the marks.

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
    from moviepy import CompositeVideoClip, ImageClip
except ImportError as error:
    raise ImportError('khatt.video needs moviepy: pip install "khatt[video]"') from error

from khatt.caption import caption_image
from khatt.color import Fill
from khatt.fonts import Font
from khatt.words import Word, caption_steps

__all__ = ["TextClip", "quran_captions", "word_captions"]


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


def word_captions(
    words: Sequence[Word],
    size: tuple[int, int],
    *,
    font: Font = "amiri",
    font_size: int | None = None,
    color: Fill = "white",
    highlight_color: Fill = "gold",
    stroke_color: Fill | None = "black",
    stroke_width: float | None = None,
    bg_color: Fill | None = None,
    highlight: str = "word",
    max_chars: int = 42,
    max_gap: float = 1.0,
    hold: float = 0.5,
    bottom: float = 0.08,
    interline: float = 4,
    keep_tashkeel: bool = True,
    fallback_fonts: Font | Sequence[Font] = (),
) -> CompositeVideoClip:
    """Word-timed captions for a video of ``size``: each word lights up as it is said.

    Lay the result over the video::

        words = khatt.words_from_whisper(result)
        captions = word_captions(words, video.size)
        CompositeVideoClip([video, captions]).write_videofile("out.mp4")

    Lines and timing come from :func:`khatt.caption_steps`. Every line is
    centred near the bottom and wrapped to 90% of the width; its highlighted
    words are drawn with ``spans``, so their letters stay joined to the
    rest.

    Args:
        words: Timed words, for example from :func:`khatt.words_from_whisper`.
        size: ``(width, height)`` of the video.
        font: A bundled font name or a font file path.
        font_size: Pixels per em; default: 6.5% of the height.
        color: Colour of the words not highlighted.
        highlight_color: Colour of the highlighted words.
        stroke_color: Outline colour, or ``None`` for none.
        stroke_width: Outline width in pixels; default: 1/16 of the font size.
        bg_color: A box behind each line, or ``None`` for none.
        highlight: ``"word"`` (only the word being said) or ``"spoken"``
            (the words of the line said so far).
        max_chars: Longest line, in characters.
        max_gap: A pause longer than this many seconds starts a new line.
        hold: Seconds a line stays up after its last word.
        bottom: Space below the captions, as a fraction of the height.
        interline: Pixels between the lines of a wrapped caption.
        keep_tashkeel: Keep Arabic diacritics (``False`` strips them).
        fallback_fonts: Fonts for characters ``font`` has no glyph for.

    Returns:
        A transparent clip of ``size``, as long as the captions.

    Raises:
        ValueError: if there are no words.
    """
    steps = caption_steps(
        words, max_chars=max_chars, max_gap=max_gap, hold=hold, highlight=highlight
    )
    if not steps:
        raise ValueError("no words to caption")
    width, height = size
    if font_size is None:
        font_size = max(8, round(height * 0.065))
    if stroke_color is None:
        stroke_width = 0
    elif stroke_width is None:
        stroke_width = max(1.0, font_size / 16)
    clips = []
    for step in steps:
        image = caption_image(
            step.text,
            font=font,
            font_size=font_size,
            size=(max(1, round(width * 0.9)), None),
            margin=(round(font_size * 0.3), round(font_size * 0.15)),
            color=color,
            bg_color=bg_color,
            stroke_color=stroke_color,
            stroke_width=stroke_width,
            method="caption",
            text_align="center",
            interline=interline,
            keep_tashkeel=keep_tashkeel,
            fallback_fonts=fallback_fonts,
            spans=[(start, end, highlight_color) for start, end in step.spans],
        )
        x = (width - image.width) // 2
        y = height - image.height - round(height * bottom)
        clip = ImageClip(np.array(image), transparent=True)
        clips.append(
            clip.with_start(step.start).with_duration(step.end - step.start).with_position((x, y))
        )
    return CompositeVideoClip(clips, size=size).with_duration(steps[-1].end)


def quran_captions(
    words: Sequence[Word],
    size: tuple[int, int],
    *,
    font: Font = "amiri",
    font_size: int | None = None,
    color: Fill = "white",
    highlight_color: Fill = "gold",
    stroke_color: Fill | None = "black",
    stroke_width: float | None = None,
    bg_color: Fill | None = None,
    highlight: str = "word",
    max_chars: int = 60,
    hold: float = 1.5,
    bottom: float = 0.08,
    fallback_fonts: Font | Sequence[Font] = (),
) -> CompositeVideoClip:
    """Word-timed captions for a Quran recitation over a video of ``size``.

    :func:`word_captions` set up for recitations: words from
    :func:`khatt.words_from_quran`, one verse at a time (a long verse is
    split at ``max_chars``), every mark kept, lines spaced for the marks
    above and below them, and each verse shown until the next one starts
    (at most ``hold`` seconds after it ends)::

        words = khatt.words_from_quran(timings, verses)
        captions = quran_captions(words, video.size)

    The text is drawn exactly as given. Amiri (the default) draws the
    Uthmani script and the verse medallions; Amiri Quran and Scheherazade
    New come with ``pip install khatt-fonts``, or pass any font file.

    The arguments are :func:`word_captions`'s; the line spacing follows the
    font size.
    """
    height = size[1]
    if font_size is None:
        font_size = max(8, round(height * 0.06))
    return word_captions(
        words,
        size,
        font=font,
        font_size=font_size,
        color=color,
        highlight_color=highlight_color,
        stroke_color=stroke_color,
        stroke_width=stroke_width,
        bg_color=bg_color,
        highlight=highlight,
        max_chars=max_chars,
        max_gap=float("inf"),
        hold=hold,
        bottom=bottom,
        interline=font_size,
        keep_tashkeel=True,
        fallback_fonts=fallback_fonts,
    )
