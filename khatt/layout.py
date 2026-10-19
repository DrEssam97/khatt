"""Line layout: paragraphs, word-wrap and FIGlet-style sizing.

Text is split into paragraphs on line breaks before shaping. Each paragraph is
aligned by its own direction (right-to-left paragraphs right-align) and, when
it is too wide, wrapped at spaces. In text art every line is cropped to its
own ink and lines are separated by one blank line; images keep evenly spaced
baselines instead.

Sizing has two modes:

* **size** (default): the font size is fixed at ``size`` character rows per
  em, so letters come out the same size however long the text is, and lines
  wider than ``width`` columns wrap. If a single word is wider than ``width``
  on its own, the whole render shrinks just enough for it to fit.
* **fit** (``size=None``): nothing wraps; the widest line is scaled to fill
  exactly ``width`` columns.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PIL import Image

from khatt.raster import CELL_ASPECT, RENDER_PPEM, compose, compose_lines, measure, to_grid
from khatt.shaping import ShapedGlyph, base_direction, shape

DEFAULT_SIZE = 10
"""Default font size, in character rows per em."""

IMAGE_LINE_GAP = RENDER_PPEM // 4
"""Gap between lines in :func:`render_ink` output, in render pixels."""


def paragraphs(text: str) -> list[str]:
    """Split text on line breaks (``\\n``, ``\\r\\n``, ``\\r`` …); tabs become spaces."""
    return text.replace("\t", " ").splitlines()


def wrap(paragraph: str, fits: Callable[[str], bool]) -> list[str]:
    """Greedily break a paragraph at spaces into lines for which ``fits`` holds.

    A paragraph that fits is returned unchanged; otherwise words are rejoined
    with single spaces. A word that does not fit on its own still gets its
    own line.
    """
    if fits(paragraph):
        return [paragraph]
    words = paragraph.split()
    if not words:
        return [paragraph]
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if fits(candidate):
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


class _Lines:
    """Shaped, aligned lines ready for :func:`khatt.raster.compose`."""

    def __init__(self) -> None:
        self.glyphs: list[list[ShapedGlyph]] = []
        self.align: list[str] = []

    def add(self, glyphs: list[ShapedGlyph], direction: str) -> None:
        self.glyphs.append(glyphs)
        self.align.append("right" if direction == "rtl" else "left")


def _ink_width(text: str, path: Path, direction: str, keep_tashkeel: bool) -> int:
    glyphs = shape(text, path, keep_tashkeel=keep_tashkeel, direction=direction, warn=False)
    box = measure(glyphs, path)
    return 0 if box is None else box[2] - box[0]


def _shape_lines(
    text: str, path: Path, keep_tashkeel: bool, max_width: float | None = None
) -> _Lines:
    """Shape every paragraph, wrapping it to ``max_width`` render pixels if given."""
    lines = _Lines()
    for paragraph in paragraphs(text):
        direction = base_direction(paragraph)
        pieces = [paragraph]
        if max_width is not None:

            def fits(candidate: str, direction: str = direction, limit: float = max_width) -> bool:
                return _ink_width(candidate, path, direction, keep_tashkeel) <= limit

            pieces = wrap(paragraph, fits)
        for piece in pieces:
            lines.add(
                shape(piece, path, keep_tashkeel=keep_tashkeel, direction=direction), direction
            )
    return lines


def _longest_word(text: str, path: Path, keep_tashkeel: bool) -> int:
    widths = [
        _ink_width(word, path, base_direction(paragraph), keep_tashkeel)
        for paragraph in paragraphs(text)
        for word in paragraph.split()
    ]
    return max(widths, default=0)


def _trim_blank(bands: list[Image.Image]) -> list[Image.Image]:
    """Drop ink-less bands (empty input lines) from both ends."""
    inked = [i for i, band in enumerate(bands) if band.getbbox() is not None]
    return bands[inked[0] : inked[-1] + 1] if inked else []


def render_grids(
    text: str,
    path: Path,
    cell: tuple[int, int],
    *,
    width: int | None,
    size: int | None,
    keep_tashkeel: bool,
) -> list[Image.Image]:
    """Lay out ``text`` and downsample it to character grid images, one per line.

    Each grid has one pixel per ramp character (``cell`` pixels per character
    for dot styles). Grids share one width and scale, but each is cropped to
    its own line's ink vertically. An empty list means there is nothing to
    draw.
    """
    if size is None:
        if width is None:
            raise ValueError("fit mode (size=None) needs a width")
        lines = _shape_lines(text, path, keep_tashkeel)
        bands = compose_lines(lines.glyphs, path, align=lines.align, tight=True)
        if bands is None:
            return []
        return [to_grid(band, width, cell=cell) for band in _trim_blank(bands)]

    row_px = RENDER_PPEM / size
    col_px = row_px * CELL_ASPECT
    max_width = None
    if width is not None:
        longest = _longest_word(text, path, keep_tashkeel)
        if longest > width * col_px:
            col_px = longest / width
            row_px = col_px / CELL_ASPECT
        max_width = width * col_px
    lines = _shape_lines(text, path, keep_tashkeel, max_width)
    bands = compose_lines(lines.glyphs, path, align=lines.align, tight=True)
    if bands is None:
        return []
    columns = max(1, round(bands[0].size[0] / col_px))
    if width is not None:
        columns = min(columns, width)
    return [
        to_grid(band, columns, cell=cell, rows=max(1, round(band.size[1] / row_px)))
        for band in _trim_blank(bands)
    ]


def render_ink(text: str, path: Path, *, keep_tashkeel: bool) -> Image.Image | None:
    """Render ``text`` at full resolution (no wrapping), white ink on black."""
    lines = _shape_lines(text, path, keep_tashkeel)
    return compose(lines.glyphs, path, align=lines.align, line_gap=IMAGE_LINE_GAP)
