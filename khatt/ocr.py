"""Synthetic training data for Arabic OCR: line images whose labels are exact.

Generators that pre-shape Arabic with arabic_reshaper and ``get_display`` store one
string and draw another, and on a Pillow with Raqm the picture even comes out
backwards. khatt draws the label itself, so the text that goes with each image is
exactly the text in it, in logical (typed) order, with every word's box::

    import khatt

    for line in khatt.ocr_lines(["مرحبا بالعالم", "السعر 25 ريالا"], fonts=["amiri", "cairo"]):
        line.image.save(...)  # line.text is the label, line.words the word boxes

:func:`write_ocr_dataset` saves a folder that Hugging Face ``datasets`` loads as an
``imagefolder`` (``metadata.jsonl``) and that PaddleOCR-style tools read
(``labels.txt``: image path, a tab, the label).
"""

from __future__ import annotations

import json
import math
import random
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageFilter

from khatt.color import Fill, rgba
from khatt.digits import with_digits
from khatt.draw import _pixels, draw_text, text_bbox
from khatt.fonts import Font, font_path
from khatt.geometry import word_boxes
from khatt.layout import _ascender_px, _descender_px
from khatt.raster import Box
from khatt.shaping import strip_tashkeel


@dataclass(frozen=True)
class OcrWord:
    """One word of an :class:`OcrLine` and where it is in the image."""

    text: str
    """The word, as in the label."""
    start: int
    end: int
    """Where it is in the label: ``label[start:end]``."""
    box: Box
    """``(left, top, right, bottom)`` in pixels, ``right`` and ``bottom`` exclusive.
    After a rotation, the smallest upright box around the turned word."""


@dataclass(frozen=True)
class OcrLine:
    """A line image and its label."""

    image: Image.Image
    text: str
    """The label: exactly the text drawn, in logical (typed) order."""
    words: tuple[OcrWord, ...]
    """Each word with ink, in reading order."""
    font: str
    """The font it was drawn in, as given in ``fonts``."""
    size_px: int


def _choices(value: Any) -> list[Any]:
    """One colour as a list of one, or the colours given to pick from."""
    if isinstance(value, str) or _is_colour(value):
        return [value]
    return list(value)


def _is_colour(value: object) -> bool:
    """Whether ``value`` is one colour tuple such as ``(0, 0, 0)``, not a list of them."""
    return (
        isinstance(value, tuple)
        and len(value) in (3, 4)
        and all(isinstance(part, int) for part in value)
    )


def _turned(box: Box, angle: float, centre: tuple[float, float], shift: tuple[float, float]) -> Box:
    """The upright box around ``box`` turned ``angle`` degrees about ``centre``, then moved.

    Turns counter-clockwise, as ``Image.rotate`` does.
    """
    radians = math.radians(angle)
    cos, sin = math.cos(radians), math.sin(radians)
    xs, ys = [], []
    for x, y in ((box[0], box[1]), (box[2], box[1]), (box[0], box[3]), (box[2], box[3])):
        dx, dy = x - centre[0], y - centre[1]
        # y points down in an image, so turning counter-clockwise is this way round.
        xs.append(centre[0] + dx * cos + dy * sin + shift[0])
        ys.append(centre[1] - dx * sin + dy * cos + shift[1])
    # Rounded first, so that cos(90°) = 6e-17 doesn't push a side out by a pixel.
    xs, ys = [round(x, 6) for x in xs], [round(y, 6) for y in ys]
    return (math.floor(min(xs)), math.floor(min(ys)), math.ceil(max(xs)), math.ceil(max(ys)))


def _grain(size: tuple[int, int], deviation: float, rng: random.Random) -> Image.Image:
    """Grey noise around 128 with this standard deviation, from ``rng`` so a seed repeats it.

    Pillow's ``effect_noise`` has its own random numbers, which no seed reaches.
    """
    spread = deviation * math.sqrt(3) / 127.5  # even noise this wide has that deviation
    table = [min(255, max(0, round(128 + (value - 127.5) * spread))) for value in range(256)]
    return Image.frombytes("L", size, rng.randbytes(size[0] * size[1])).point(table)


def ocr_lines(
    texts: Iterable[str],
    *,
    fonts: Sequence[Font] = ("amiri",),
    size_px: int | tuple[int, int] = 40,
    fill: Fill | Sequence[Fill] = "black",
    background: Fill | Sequence[Fill] = "white",
    padding: int = 8,
    rotate: float = 0,
    blur: float = 0,
    noise: float = 0,
    keep_tashkeel: bool = True,
    digits: str | None = None,
    fallback_fonts: Font | Sequence[Font] = (),
    seed: int | None = None,
) -> Iterator[OcrLine]:
    """Draw each text as a line image for training OCR, with its exact label and word boxes.

    Every line gets a font from ``fonts``, a size, colours and degradations picked at
    random (``seed`` makes the same picks every run). The label is the text as drawn,
    in logical order: with ``keep_tashkeel=False`` it has no diacritics either, and
    with ``digits`` its digits are the drawn ones.

    Args:
        texts: One line each; blank ones are skipped. A text may end with a line
            break (as lines read from a file do), but not contain one.
        fonts: Bundled font names or font files to pick from.
        size_px: Font size in pixels per em, or ``(smallest, largest)`` to pick from.
        fill: Text colour, or a list of colours to pick from.
        background: Background colour, or a list of colours to pick from.
        padding: Pixels of background around the line (its ink and the font's
            ascender and descender).
        rotate: Turn each image by up to this many degrees either way.
        blur: Gaussian blur of up to this radius, in pixels.
        noise: Grey noise of up to this standard deviation, in levels of 255.
        keep_tashkeel: Keep Arabic diacritics.
        digits: ``"arabic-indic"`` draws and labels digits as ٠ to ٩.
        fallback_fonts: Fonts for characters the picked font has no glyph for.
        seed: Seed for the random picks.

    Yields:
        One :class:`OcrLine` per text that has something to draw.

    Raises:
        ValueError: a text has a line break inside it, or an argument is out of range.
    """
    if not fonts:
        raise ValueError("fonts must name at least one font")
    paths = [font_path(font) for font in fonts]  # fail early on an unknown font
    for name, value in (("rotate", rotate), ("blur", blur), ("noise", noise)):
        if not (isinstance(value, int | float) and value >= 0):
            raise ValueError(f"{name} must be a number of at least 0, got {value!r}")
    pad = _pixels("padding", padding)
    sizes = size_px if isinstance(size_px, tuple) else (size_px, size_px)
    if not (len(sizes) == 2 and 1 <= sizes[0] <= sizes[1]):
        raise ValueError(f"size_px must be at least 1, or a (smallest, largest) pair: {size_px!r}")
    fills, backgrounds = _choices(fill), _choices(background)
    rng = random.Random(seed)

    for text in texts:
        label = text.rstrip("\r\n")
        if "\n" in label or "\r" in label:
            raise ValueError(f"each text is one line; this one has a line break: {text!r}")
        label = with_digits(label, digits)
        if not keep_tashkeel:
            label = strip_tashkeel(label)
        if not label.strip():
            continue
        choice = rng.randrange(len(fonts))
        font, path = fonts[choice], paths[choice]
        size = rng.randint(sizes[0], sizes[1])
        ink, paper = rgba(rng.choice(fills)), rgba(rng.choice(backgrounds))

        # Measured from the start of the baseline; the image holds the font's whole height.
        left, top, right, bottom = text_bbox(
            label, font=font, size_px=size, anchor="ls", fallback_fonts=fallback_fonts
        )
        if right <= left:
            continue
        top = min(top, -_ascender_px(path, size))
        bottom = max(bottom, _descender_px(path, size))
        image = Image.new("RGB", (right - left + 2 * pad, bottom - top + 2 * pad), paper[:3])
        xy = (pad - left, pad - top)
        draw_text(
            image,
            xy,
            label,
            font=font,
            size_px=size,
            anchor="ls",
            fill=ink,
            fallback_fonts=fallback_fonts,
        )
        boxes = word_boxes(
            label, xy=xy, font=font, size_px=size, anchor="ls", fallback_fonts=fallback_fonts
        )
        words = [OcrWord(word.text, word.start, word.end, word.box) for word in boxes]

        angle = rng.uniform(-rotate, rotate) if rotate else 0.0
        if angle:
            centre = (image.width / 2, image.height / 2)
            turned = image.rotate(
                angle, resample=Image.Resampling.BICUBIC, expand=True, fillcolor=paper[:3]
            )
            shift = ((turned.width - image.width) / 2, (turned.height - image.height) / 2)
            words = [
                OcrWord(word.text, word.start, word.end, _turned(word.box, angle, centre, shift))
                for word in words
            ]
            image = turned
        radius = rng.uniform(0, blur) if blur else 0.0
        if radius:
            image = image.filter(ImageFilter.GaussianBlur(radius))
        sigma = rng.uniform(0, noise) if noise else 0.0
        if sigma:
            grain = _grain(image.size, sigma, rng).convert("RGB")
            image = ImageChops.add(image, grain, scale=1.0, offset=-128)
        yield OcrLine(image, label, tuple(words), str(font), size)


def write_ocr_dataset(texts: Iterable[str], folder: str | Path, **options: Any) -> int:
    """Draw ``texts`` with :func:`ocr_lines` and save them as a dataset in ``folder``.

    Writes ``images/000001.png`` and so on; ``metadata.jsonl``, one JSON object per
    image (``file_name``, ``text``, ``font``, ``size_px``, and ``words`` with each word's
    ``text`` and ``box``), which Hugging Face ``datasets`` loads with
    ``load_dataset("imagefolder", data_dir=folder)``; and ``labels.txt``, each image's
    path, a tab and its label, as PaddleOCR's recognition training reads it.

    Args:
        texts: One line each, as in :func:`ocr_lines`.
        folder: Where to write; created if missing.
        **options: :func:`ocr_lines`'s keyword arguments.

    Returns:
        How many images were written.
    """
    root = Path(folder)
    (root / "images").mkdir(parents=True, exist_ok=True)
    count = 0
    with (
        (root / "metadata.jsonl").open("w", encoding="utf-8", newline="\n") as metadata,
        (root / "labels.txt").open("w", encoding="utf-8", newline="\n") as labels,
    ):
        for count, line in enumerate(ocr_lines(texts, **options), start=1):
            name = f"images/{count:06d}.png"
            line.image.save(root / name)
            record = {
                "file_name": name,
                "text": line.text,
                "font": line.font,
                "size_px": line.size_px,
                "words": [{"text": word.text, "box": list(word.box)} for word in line.words],
            }
            metadata.write(json.dumps(record, ensure_ascii=False) + "\n")
            labels.write(f"{name}\t{line.text}\n")
    return count
