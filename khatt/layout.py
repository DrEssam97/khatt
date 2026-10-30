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

Text drawn onto images (:func:`layout_block`) is laid out at a size in pixels
per em, wraps to a width in pixels, and keeps its baselines evenly spaced
(:func:`line_pitch`).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from khatt.raster import (
    CELL_ASPECT,
    RENDER_PPEM,
    Block,
    Box,
    compose,
    compose_block,
    compose_lines,
    estimate,
    measure,
    size_metrics,
    to_grid,
)
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


def _ink_width(
    text: str,
    path: Path,
    direction: str,
    keep_tashkeel: bool,
    ppem: int | None = None,
    fallbacks: Sequence[Path] = (),
) -> int:
    """Ink width in render pixels, or estimated at ``ppem`` for drawing on images."""
    glyphs = shape(
        text,
        path,
        keep_tashkeel=keep_tashkeel,
        direction=direction,
        warn=False,
        fallback_fonts=fallbacks,
    )
    box = measure(glyphs, path) if ppem is None else estimate(glyphs, path, ppem=ppem)
    return 0 if box is None else box[2] - box[0]


def _shape_lines(
    text: str,
    path: Path,
    keep_tashkeel: bool,
    max_width: float | None = None,
    ppem: int | None = None,
    warn: bool = True,
    fallbacks: Sequence[Path] = (),
) -> _Lines:
    """Shape every paragraph, wrapping it to ``max_width`` pixels if given.

    Widths are measured in render pixels, or at ``ppem`` when given.
    ``warn=False`` skips unsupported characters silently. ``fallbacks`` are
    fonts for characters ``path`` has no glyph for.
    """
    lines = _Lines()
    for paragraph in paragraphs(text):
        direction = base_direction(paragraph)
        pieces = [paragraph]
        if max_width is not None:

            def fits(candidate: str, direction: str = direction, limit: float = max_width) -> bool:
                width = _ink_width(candidate, path, direction, keep_tashkeel, ppem, fallbacks)
                return width <= limit

            pieces = wrap(paragraph, fits)
        for piece in pieces:
            lines.add(
                shape(
                    piece,
                    path,
                    keep_tashkeel=keep_tashkeel,
                    direction=direction,
                    warn=warn,
                    fallback_fonts=fallbacks,
                ),
                direction,
            )
    return lines


def _longest_word(
    text: str, path: Path, keep_tashkeel: bool, fallbacks: Sequence[Path] = ()
) -> int:
    widths = [
        _ink_width(word, path, base_direction(paragraph), keep_tashkeel, None, fallbacks)
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
    fallbacks: Sequence[Path] = (),
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
        lines = _shape_lines(text, path, keep_tashkeel, fallbacks=fallbacks)
        bands = compose_lines(lines.glyphs, path, align=lines.align, tight=True)
        if bands is None:
            return []
        return [to_grid(band, width, cell=cell) for band in _trim_blank(bands)]

    row_px = RENDER_PPEM / size
    col_px = row_px * CELL_ASPECT
    max_width = None
    if width is not None:
        longest = _longest_word(text, path, keep_tashkeel, fallbacks)
        if longest > width * col_px:
            col_px = longest / width
            row_px = col_px / CELL_ASPECT
        max_width = width * col_px
    lines = _shape_lines(text, path, keep_tashkeel, max_width, fallbacks=fallbacks)
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


def render_ink(
    text: str, path: Path, *, keep_tashkeel: bool, fallbacks: Sequence[Path] = ()
) -> Image.Image | None:
    """Render ``text`` at full resolution (no wrapping), white ink on black."""
    lines = _shape_lines(text, path, keep_tashkeel, fallbacks=fallbacks)
    return compose(lines.glyphs, path, align=lines.align, line_gap=IMAGE_LINE_GAP)


@dataclass(frozen=True)
class TextBlock:
    """Text laid out by :func:`layout_block`.

    Positions are in pixels relative to the first line's baseline (y down)
    and the left edge of the layout width, like ``block``'s.
    """

    block: Block
    ascender: int
    """y of the first line's ascender line (negative: above the baseline)."""
    descender: int
    """y of the last line's descender line."""
    align: tuple[str, ...]
    """Alignment of each line."""


def _ascender_px(path: Path, size_px: int) -> int:
    """The font's ascender at ``size_px``, in whole pixels above the baseline."""
    return size_metrics(str(path), size_px)[0]


def _descender_px(path: Path, size_px: int) -> int:
    """The font's descender at ``size_px``, in whole pixels below the baseline."""
    return size_metrics(str(path), size_px)[1]


def line_pitch(
    path: Path,
    *,
    size_px: int,
    line_spacing: float,
    spacing: float | None = None,
    stroke_width: float = 0,
) -> float:
    """Distance between baselines, in pixels.

    ``line_spacing`` times ``size_px``, or with ``spacing`` (pixels) Pillow's
    rule: the font's ascender (:func:`_ascender_px`) plus twice
    ``stroke_width`` plus ``spacing``. So each line's ascender line sits
    ``spacing`` pixels below the previous baseline, plus room for both
    lines' outlines. A very negative ``spacing`` can make it zero or less.
    """
    if spacing is None:
        return line_spacing * size_px
    return _ascender_px(path, size_px) + 2 * stroke_width + spacing


def _checked_pitch(pitch: float, line_count: int, size_px: int, spacing: float | None) -> float:
    """``pitch``, or ``ValueError`` if it would stack lines upwards.

    A single line has no pitch to check: spacing doesn't apply to it.
    """
    if line_count > 1 and pitch <= 0:
        unspaced = pitch - (spacing or 0)
        raise ValueError(
            f"spacing must be more than {-unspaced:g} at {size_px}px, "
            f"or each line would not start below the one before; got {spacing}"
        )
    return pitch


def estimate_block(
    text: str,
    path: Path,
    *,
    size_px: int,
    max_width: int | None,
    line_spacing: float,
    keep_tashkeel: bool,
    spacing: float | None = None,
    stroke_width: float = 0,
    fallbacks: Sequence[Path] = (),
) -> tuple[Box, int] | None:
    """Ink box of :func:`layout_block`'s text, and its line count, without rendering.

    The box is relative to the first baseline and the layout's left edge,
    estimated from glyph outline boxes: never smaller than the drawn ink,
    which excludes the outline (``stroke_width`` only spaces the lines, see
    :func:`line_pitch`). Unsupported characters are skipped silently, so a
    search over sizes doesn't repeat their warnings. ``None`` means there
    is nothing to draw.
    """
    lines = _shape_lines(
        text, path, keep_tashkeel, max_width, ppem=size_px, warn=False, fallbacks=fallbacks
    )
    pitch = line_pitch(
        path,
        size_px=size_px,
        line_spacing=line_spacing,
        spacing=spacing,
        stroke_width=stroke_width,
    )
    pitch = _checked_pitch(pitch, len(lines.glyphs), size_px, spacing)
    boxes = [
        (box, round(index * pitch))
        for index, glyphs in enumerate(lines.glyphs)
        if (box := estimate(glyphs, path, ppem=size_px)) is not None
    ]
    if not boxes:
        return None
    ink = (
        0,
        min(box[1] + dy for box, dy in boxes),
        max(box[2] - box[0] for box, _ in boxes),
        max(box[3] + dy for box, dy in boxes),
    )
    return ink, len(lines.glyphs)


def measure_block(
    text: str,
    path: Path,
    *,
    size_px: int,
    max_width: int | None,
    line_spacing: float,
    keep_tashkeel: bool,
    spacing: float | None = None,
    stroke_width: float = 0,
    fallbacks: Sequence[Path] = (),
) -> tuple[int, int] | None:
    """Ink ``(width, height)`` of :func:`layout_block`'s output, without rendering.

    See :func:`estimate_block`. ``None`` means there is nothing to draw.
    """
    estimated = estimate_block(
        text,
        path,
        size_px=size_px,
        max_width=max_width,
        line_spacing=line_spacing,
        keep_tashkeel=keep_tashkeel,
        spacing=spacing,
        stroke_width=stroke_width,
        fallbacks=fallbacks,
    )
    if estimated is None:
        return None
    (left, top, right, bottom), _ = estimated
    return right - left, bottom - top


def smallest_spaced_size(
    path: Path,
    sizes: tuple[int, int],
    *,
    line_spacing: float,
    spacing: float | None,
    stroke_width: float,
) -> int:
    """The smallest size in ``sizes`` at which lines still stack downwards.

    A negative ``spacing`` stacks lines upwards below some size, which
    :func:`layout_block` refuses; size searches start above it. Returns the
    largest size if none qualifies.
    """
    low, high = sizes
    while (
        low < high
        and line_pitch(
            path,
            size_px=low,
            line_spacing=line_spacing,
            spacing=spacing,
            stroke_width=stroke_width,
        )
        <= 0
    ):
        low += 1
    return low


def largest_size(fits: Callable[[int], bool], sizes: tuple[int, int]) -> int:
    """Binary-search the largest size in ``sizes`` for which ``fits`` holds.

    Returns the smallest size when none fits.
    """
    low, high = sizes
    if not fits(low):
        return low
    while low < high:
        middle = (low + high + 1) // 2
        if fits(middle):
            low = middle
        else:
            high = middle - 1
    return low


def layout_block(
    text: str,
    path: Path,
    *,
    size_px: int,
    max_width: int | None = None,
    align: str | None = None,
    line_spacing: float,
    keep_tashkeel: bool,
    width: int | None = None,
    stroke_width: float = 0,
    spacing: float | None = None,
    fallbacks: Sequence[Path] = (),
) -> TextBlock | None:
    """Lay out and draw ``text`` at ``size_px`` pixels per em for an image.

    Paragraphs wrap at spaces to ``max_width`` pixels when given; baselines
    are :func:`line_pitch` pixels apart (``line_spacing * size_px``, or by
    ``spacing``). Lines are aligned by ``align`` (``"left"``, ``"right"`` or
    ``"center"``; ``None``: by each paragraph's direction) within ``width``
    pixels or the widest line. ``stroke_width`` (pixels) also draws an
    outline stroke around the text (see :func:`khatt.raster.compose_block`).
    Characters ``path`` has no glyph for are drawn from the first of
    ``fallbacks`` that has one; line spacing still follows ``path``.

    Returns ``None`` when there is nothing to draw.
    """
    lines = _shape_lines(text, path, keep_tashkeel, max_width, ppem=size_px, fallbacks=fallbacks)
    alignments = lines.align if align is None else [align] * len(lines.align)
    pitch = line_pitch(
        path,
        size_px=size_px,
        line_spacing=line_spacing,
        spacing=spacing,
        stroke_width=stroke_width,
    )
    pitch = _checked_pitch(pitch, len(lines.glyphs), size_px, spacing)
    block = compose_block(
        lines.glyphs,
        path,
        ppem=size_px,
        pitch=pitch,
        align=alignments,
        width=width,
        stroke=round(stroke_width * 64),
    )
    if block is None:
        return None
    return TextBlock(
        block,
        ascender=-_ascender_px(path, size_px),
        descender=round((len(lines.glyphs) - 1) * pitch) + _descender_px(path, size_px),
        align=tuple(alignments),
    )
