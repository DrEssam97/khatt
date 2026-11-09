"""Calligrams: text that flows inside a shape, a heart, a circle or your own.

Lines follow the shape's outline from top to bottom, each one as wide as the
shape is at that height, and never cut a letter at the edge. Arabic lines are
stretched to fill their width with kashida (tatweel, ``ـ``), the way a
calligrapher would, rather than with wider gaps between words.

    >>> khatt.calligram("خط جميل بالعربية", shape="heart")
"""

from __future__ import annotations

import math
import unicodedata
import warnings
from collections.abc import Sequence
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageOps

from khatt.color import Fill, rgba
from khatt.draw import TextOverflowWarning, _pixels, _place_text
from khatt.effects import Effect, compose, get_effect
from khatt.fonts import Font, font_path, font_paths
from khatt.layout import _ink_width, largest_size
from khatt.raster import Block, size_metrics
from khatt.shaping import base_direction

TATWEEL = "ـ"
_RLM = "‏"
"""Keeps a line of right-to-left text right-to-left when it starts with a Latin word."""

_MOST_KASHIDA = 3
"""Tatweels at any one point of a word; more looks drawn out rather than written."""

_MOST_STRETCH = 0.3
"""How much kashida may widen a line; a line that needs more is centred instead."""

_NARROWEST = 1.6
"""The narrowest piece of a shape a line goes in, in font sizes."""

_INSET = 0.12
"""Room left between the text and the shape's edge, in font sizes."""

# Letters that never join the letter after them, so no kashida can follow them.
_NO_JOIN_AFTER = frozenset("ءآأؤإاةدذرزوٱژڈڑۀےۓ")
_ALEFS = frozenset("آأإاٱ")


def _is_letter(ch: str) -> bool:
    return unicodedata.bidirectional(ch) == "AL" and unicodedata.category(ch) == "Lo"


def kashida_points(word: str) -> list[int]:
    """Where a tatweel can go in ``word``: positions to insert it before.

    Only between two letters that join, after the first one's marks, and
    never inside lam-alef, which a tatweel would break apart.
    """
    points = []
    for index, ch in enumerate(word):
        if not _is_letter(ch) or ch in _NO_JOIN_AFTER:
            continue
        after = index + 1
        while after < len(word) and unicodedata.combining(word[after]):
            after += 1
        if after == len(word) or not _is_letter(word[after]):
            continue
        if ch == "ل" and word[after] in _ALEFS:
            continue
        points.append(after)
    return points


def stretch(line: str, count: int) -> str:
    """``line`` with ``count`` tatweels spread evenly over its words.

    Fewer are added when the words have too few places for them.
    """
    words = line.split(" ")
    spots = [(n, point) for n, word in enumerate(words) for point in kashida_points(word)]
    if not spots or count <= 0:
        return line
    count = min(count, len(spots) * _MOST_KASHIDA)
    extra = {spot: count // len(spots) for spot in spots}
    # The rest go to every few spots across the line, not all at its start.
    rest = count % len(spots)
    for n in range(rest):
        extra[spots[n * len(spots) // rest]] += 1
    stretched = []
    for n, word in enumerate(words):
        pieces, last = [], 0
        for point in kashida_points(word):
            pieces += [word[last:point], TATWEEL * extra[(n, point)]]
            last = point
        stretched.append("".join(pieces) + word[last:])
    return " ".join(stretched)


def _heart(size: int) -> list[tuple[float, float]]:
    points = []
    for step in range(240):
        t = 2 * math.pi * step / 240
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        points.append((size / 2 + x * size / 34, size * 0.43 - y * size / 34))
    return points


def _arch(size: int) -> list[tuple[float, float]]:
    """A pointed arch over a doorway, as in a mihrab: two arcs meeting at the top."""
    radius, spring = size * 0.75, size * 0.71
    apex = math.acos((0.5 - 0.75) / 0.75)
    steps = 60
    left = [
        (
            radius + radius * math.cos(math.pi - (math.pi - apex) * n / steps),
            spring - radius * math.sin(math.pi - (math.pi - apex) * n / steps),
        )
        for n in range(steps + 1)
    ]
    right = [(size - x, y) for x, y in reversed(left)]
    return [(0, size * 1.46), *left, *right, (size, size * 1.46)]


def _draw_shape(name: str, size: int) -> Image.Image:
    big = size * 2
    mask = Image.new("L", (big, round(big * 1.5)), 0)
    draw = ImageDraw.Draw(mask)
    if name == "circle":
        draw.ellipse((0, 0, big - 1, big - 1), fill=255)
    elif name == "heart":
        draw.polygon(_heart(big), fill=255)
    elif name == "arch":
        draw.polygon(_arch(big), fill=255)
    elif name == "diamond":
        draw.polygon([(big / 2, 0), (big - 1, big / 2), (big / 2, big - 1), (0, big / 2)], fill=255)
    elif name == "crescent":
        draw.ellipse((0, 0, big - 1, big - 1), fill=255)
        cut = big * 0.4
        middle = (big * 0.8, big * 0.45)
        draw.ellipse((middle[0] - cut, middle[1] - cut, middle[0] + cut, middle[1] + cut), fill=0)
    mask = mask.reduce(2)
    return mask.crop(mask.getbbox())


_SHAPES = ("arch", "circle", "crescent", "diamond", "heart")


def available_shapes() -> list[str]:
    """Return the sorted names of the preset shapes for :func:`calligram`."""
    return sorted(_SHAPES)


def _shape_mask(shape: str | Image.Image, width: int) -> Image.Image:
    """The inside of ``shape`` at ``width`` pixels wide, white on black."""
    if isinstance(shape, Image.Image):
        lowest = shape.getchannel("A").getextrema()[0] if "A" in shape.getbands() else 255
        if isinstance(lowest, (int, float)) and lowest < 255:
            inside = shape.getchannel("A")
        else:
            inside = ImageOps.invert(shape.convert("L"))  # dark marks the inside
        box = inside.point(lambda v: 255 if v >= 128 else 0).getbbox()
        if box is None:
            raise ValueError("the shape image has no inside: use dark or opaque pixels for it")
        inside = inside.crop(box)
        height = max(1, round(inside.height * width / inside.width))
        return inside.resize((width, height), Image.Resampling.LANCZOS)
    if not isinstance(shape, str):
        raise ValueError(f"shape must be a preset name or a Pillow image, got {shape!r}")
    name = shape.strip().lower()
    if name not in _SHAPES:
        raise KeyError(f"unknown shape {shape!r}; available shapes: {', '.join(_SHAPES)}")
    mask = _draw_shape(name, width)
    return mask.resize((width, round(mask.height * width / mask.width)), Image.Resampling.LANCZOS)


def _segments(
    mask: Image.Image, top: int, bottom: int, narrowest: int, inset: int
) -> list[tuple[int, int]]:
    """The stretches of ``mask`` that are inside the shape from ``top`` to ``bottom``."""
    if top < 0 or bottom > mask.height:
        return []
    band = mask.crop((0, top, mask.width, bottom)).resize((mask.width, 1), Image.Resampling.BOX)
    inside = [v >= 250 for v in band.tobytes()]
    runs, start = [], None
    for x, here in enumerate([*inside, False]):
        if here and start is None:
            start = x
        elif not here and start is not None:
            if x - start - 2 * inset >= narrowest:
                runs.append((start + inset, x - inset))
            start = None
    return runs


def _repeat_size(mask: Image.Image) -> int:
    """A size that puts several words on a typical line, and twenty lines down the shape."""
    rows = mask.resize((1, mask.height), Image.Resampling.BOX).tobytes()
    widths = [v * mask.width / 255 for v in rows if v]
    typical = sum(widths) / len(widths) if widths else mask.width
    return max(8, round(min(mask.height / 20, typical / 9)))


class _Measure:
    """Line widths at one size, added up from cached word widths."""

    def __init__(
        self, path: Path, direction: str, size: int, keep_tashkeel: bool, fallbacks: Sequence[Path]
    ):
        self.path, self.direction, self.size = path, direction, size
        self.keep_tashkeel, self.fallbacks = keep_tashkeel, fallbacks
        self.words: dict[str, int] = {}
        self.space = (
            self.exact("ا ا") - 2 * self.exact("ا")
            if direction == "rtl"
            else (self.exact("i i") - 2 * self.exact("i"))
        )
        self.tatweel = self.exact("بـب") - self.exact("بب")

    def exact(self, text: str) -> int:
        return _ink_width(
            text, self.path, self.direction, self.keep_tashkeel, self.size, self.fallbacks
        )

    def word(self, word: str) -> int:
        if word not in self.words:
            self.words[word] = self.exact(word)
        return self.words[word]

    def line(self, words: Sequence[str]) -> int:
        return sum(self.word(w) for w in words) + self.space * (len(words) - 1)


def _flow(
    words: list[str],
    mask: Image.Image,
    measure: _Measure,
    *,
    pitch: float,
    ascent: int,
    descent: int,
    repeat: bool,
) -> tuple[list[tuple[list[str], tuple[int, int], int]], int]:
    """Fill ``mask`` with lines of ``words``.

    Returns:
        Each line's words, its stretch of the shape and its baseline, and how
        many words were placed.
    """
    size = measure.size
    narrowest, inset = round(_NARROWEST * size), round(_INSET * size)
    lines: list[tuple[list[str], tuple[int, int], int]] = []
    placed = 0
    baseline = ascent
    while baseline + descent <= mask.height and (repeat or placed < len(words)):
        segments = _segments(mask, baseline - ascent, baseline + descent, narrowest, inset)
        if measure.direction == "rtl":
            segments.reverse()
        for left, right in segments:
            taken: list[str] = []
            while repeat or placed + len(taken) < len(words):
                candidate = [*taken, words[(placed + len(taken)) % len(words)]]
                if measure.line(candidate) > right - left:
                    break
                taken = candidate
            if not taken:
                continue
            while len(taken) > 1 and measure.exact(" ".join(taken)) > right - left:
                taken.pop()
            lines.append((taken, (left, right), baseline))
            placed += len(taken)
            if not repeat and placed >= len(words):
                break
        baseline += round(pitch) if segments else max(1, round(pitch / 4))
    return lines, placed


def _draw_lines(
    lines: list[tuple[list[str], tuple[int, int], int]],
    size: tuple[int, int],
    measure: _Measure,
    *,
    justify: bool,
    last_is_end: bool,
    font: Font,
    keep_tashkeel: bool,
    stroke_width: float,
    fallback_fonts: Font | Sequence[Font],
) -> tuple[Image.Image, Image.Image | None]:
    """Draw each line centred in its stretch of the shape, stretched with kashida if it may be.

    Returns:
        The text's coverage, and its outline's when ``stroke_width`` is set,
        both as big as the shape.
    """
    text_mask = Image.new("L", size, 0)
    stroke_mask = Image.new("L", size, 0) if stroke_width else None
    for number, (taken, (left, right), baseline) in enumerate(lines):
        line = " ".join(taken)
        last = last_is_end and number == len(lines) - 1
        natural = measure.exact(line)
        room = right - left - natural
        if justify and not last and measure.tatweel > 0 and room <= _MOST_STRETCH * natural:
            line = stretch(line, room // measure.tatweel)
            while measure.exact(line) > right - left and TATWEEL in line:
                line = line[::-1].replace(TATWEEL, "", 1)[::-1]
        if measure.direction == "rtl" and base_direction(line) == "ltr":
            line = _RLM + line
        placed = _place_text(
            ((left + right) / 2, baseline),
            line,
            font=font,
            size_px=measure.size,
            align=None,
            anchor="ms",
            max_width=None,
            line_spacing=None,
            spacing=None,
            keep_tashkeel=keep_tashkeel,
            stroke_width=stroke_width,
            fallback_fonts=fallback_fonts,
        )
        if placed is None:
            continue
        block, (x, y) = placed
        region = (x, y, x + block.mask.width, y + block.mask.height)
        text_mask.paste(ImageChops.lighter(text_mask.crop(region), block.mask), (x, y))
        if stroke_mask is not None and block.stroke is not None:
            outline, stroke_left, stroke_top = block.stroke
            sx, sy = x + stroke_left - block.left, y + stroke_top - block.top
            region = (sx, sy, sx + outline.width, sy + outline.height)
            stroke_mask.paste(ImageChops.lighter(stroke_mask.crop(region), outline), (sx, sy))
    return text_mask, stroke_mask


def calligram(
    text: str,
    shape: str | Image.Image = "heart",
    *,
    width: int = 800,
    font: Font = "amiri",
    size_px: int | None = None,
    repeat: bool = True,
    fill: Fill = "black",
    effect: str | Effect | None = None,
    line_spacing: float = 1.15,
    justify: bool = True,
    keep_tashkeel: bool = True,
    padding: int = 0,
    background: Fill | None = None,
    fallback_fonts: Font | Sequence[Font] = (),
) -> Image.Image | None:
    """Draw ``text`` flowing inside a shape.

    Lines run from the top of the shape to the bottom, each as wide as the
    shape at that height. Line breaks in ``text`` are treated as spaces.

    Args:
        text: The text, as typed.
        shape: A preset name (see :func:`khatt.list_shapes`) or a Pillow
            image of your own: its opaque pixels, or its dark ones if it has
            no transparency, are the inside.
        width: The width of the shape in pixels; the height follows it.
        font: A font name (see :func:`khatt.list_fonts`), a style name or the
            path to a .ttf/.otf file.
        size_px: The font size in pixels. By default small enough for
            several words a line, so the shape shows, or without ``repeat``,
            the largest size at which all of the text fits.
        repeat: Start the text again whenever it ends, until the shape is
            full: the default, because the shape shows best when it's full.
            ``False`` fits the text in once, as big as it goes; short text
            then gives few lines, and the shape is harder to see.
        fill: The colour of the text, when there is no ``effect``.
        effect: A preset name (see :func:`khatt.list_effects`) or a
            :class:`khatt.Effect`, drawn over the whole calligram.
        line_spacing: Distance between baselines, in multiples of ``size_px``.
        justify: Stretch Arabic lines to the full width with kashida. A
            line that would need to grow by more than 30% is centred instead,
            and so is the last line without ``repeat``, and lines of other
            scripts.
        keep_tashkeel: Keep Arabic diacritics (``False`` strips them).
        padding: Empty pixels around the calligram.
        background: A colour behind it; default: transparent.
        fallback_fonts: Fonts for characters ``font`` has no glyph for.

    Returns:
        An RGBA image as big as what was drawn, or ``None`` when ``text`` has
        nothing to draw. Text that doesn't fit at 8 px, the smallest size
        tried, raises a :class:`khatt.TextOverflowWarning`, and what fits is
        drawn.
    """
    style = Effect(fill=fill) if effect is None else get_effect(effect)
    width = _pixels("width", width)
    if width < 16:
        raise ValueError(f"width must be at least 16 pixels, got {width}")
    if padding < 0:
        raise ValueError(f"padding must not be negative, got {padding}")
    if not (
        isinstance(line_spacing, (int, float)) and math.isfinite(line_spacing) and line_spacing > 0
    ):
        raise ValueError(f"line_spacing must be a positive number, got {line_spacing!r}")
    mask = _shape_mask(shape, width)
    words = text.split()
    if not words:
        return None
    path, fallbacks = font_path(font), font_paths(fallback_fonts)
    direction = base_direction(text)

    def fit(size: int) -> tuple[list[tuple[list[str], tuple[int, int], int]], int, _Measure]:
        ascent, descent = size_metrics(str(path), size)
        measure = _Measure(path, direction, size, keep_tashkeel, fallbacks)
        lines, placed = _flow(
            words,
            mask,
            measure,
            pitch=line_spacing * size,
            ascent=ascent,
            descent=descent,
            repeat=repeat,
        )
        return lines, placed, measure

    if size_px is not None:
        size = _pixels("size_px", size_px)
        if size < 1:
            raise ValueError(f"size_px must be at least 1, got {size}")
    elif repeat:
        size = _repeat_size(mask)
    else:
        size = largest_size(lambda s: fit(s)[1] >= len(words), (8, max(8, mask.height // 3)))
    lines, placed, measure = fit(size)
    if not repeat and placed < len(words):
        warnings.warn(
            f"the text does not fit in the shape at {size}px; {len(words) - placed} words "
            "are left out",
            TextOverflowWarning,
            stacklevel=2,
        )
    if not lines:
        return None

    stroke_width = style.outline * size
    text_mask, stroke_mask = _draw_lines(
        lines,
        mask.size,
        measure,
        justify=justify,
        last_is_end=not repeat,
        font=font,
        keep_tashkeel=keep_tashkeel,
        stroke_width=stroke_width,
        fallback_fonts=fallback_fonts,
    )
    drawn = Block(
        mask=text_mask,
        left=0,
        top=0,
        width=mask.width,
        stroke=None if stroke_mask is None else (stroke_mask, 0, 0),
    )
    layer = compose(drawn, style, size)[0]
    box = layer.getbbox()
    if box is None:
        return None
    art = layer.crop(box)
    padding = _pixels("padding", padding)
    backdrop = (0, 0, 0, 0) if background is None else rgba(background)
    image = Image.new("RGBA", (art.width + 2 * padding, art.height + 2 * padding), backdrop)
    image.alpha_composite(art, (padding, padding))
    return image
