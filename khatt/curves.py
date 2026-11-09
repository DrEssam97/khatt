"""Bend finished text along a curve, with its letters still joined.

Placing letters one by one along a curve is what breaks Arabic: rotated
neighbours stop meeting, and the joins open up. So khatt bends the whole shaped
line instead, as one continuous sheet. Every join and mark moves with the line,
and the letters themselves change shape only as much as the curve asks.

    >>> khatt.word_art("خط جميل", effect="gold", curve="arc")
    >>> khatt.word_art("خط جميل", curve=khatt.Arc(angle=200))
"""

from __future__ import annotations

import math
import numbers
from collections.abc import Callable
from dataclasses import dataclass

from PIL import Image

from khatt.raster import Block

MAX_ARC = 350
"""A full circle would leave the two ends of the text touching."""

_TIGHTEST = 0.2
"""The hole a curve leaves inside the text, in text heights."""

_PAD = 3
"""Empty pixels around the flat text, so that resampling sees clean edges."""

_Source = Callable[[float, float], tuple[float, float]]
"""Where on the flat text a point of the bent text comes from."""


def _is_number(value: object) -> bool:
    return isinstance(value, numbers.Real) and math.isfinite(value)


@dataclass(frozen=True)
class Arc:
    """Text along part of a circle.

    The letters stay upright to the reader, and the text keeps its length along
    the middle of the line.

    Args:
        angle: How much of the circle the text covers, in degrees, up to 350.
            Positive arches upwards; negative dips downwards, along the
            bottom of the circle.
    """

    angle: float = 120

    def __post_init__(self) -> None:
        if not (_is_number(self.angle) and 0 < abs(self.angle) <= MAX_ARC):
            raise ValueError(
                f"angle must be a number of degrees from -{MAX_ARC} to {MAX_ARC}, "
                f"and not 0, got {self.angle!r}"
            )


@dataclass(frozen=True)
class Wave:
    """Text that rises and falls along its length.

    Args:
        height: How far it rises and falls, in font sizes.
        waves: How many full waves fit along the text.
    """

    height: float = 0.3
    waves: float = 1

    def __post_init__(self) -> None:
        if not (_is_number(self.height) and self.height >= 0):
            raise ValueError(f"height must be a non-negative number, got {self.height!r}")
        if not (_is_number(self.waves) and self.waves > 0):
            raise ValueError(f"waves must be a positive number, got {self.waves!r}")


Curve = Arc | Wave
"""An :class:`Arc` or a :class:`Wave`."""

_PRESETS: dict[str, Curve] = {
    "arc": Arc(120),
    "ring": Arc(330),
    "smile": Arc(-120),
    "wave": Wave(),
}


def available_curves() -> list[str]:
    """Return the sorted names of all preset curves."""
    return sorted(_PRESETS)


def get_curve(curve: str | Curve) -> Curve:
    """Resolve a preset name to its curve; an :class:`Arc` or :class:`Wave` passes through.

    Raises:
        KeyError: ``curve`` is not a preset name.
        ValueError: ``curve`` is neither a name nor a curve.
    """
    if isinstance(curve, (Arc, Wave)):
        return curve
    if not isinstance(curve, str):
        raise ValueError(f"curve must be a preset name, an Arc or a Wave, got {curve!r}")
    try:
        return _PRESETS[curve.strip().lower()]
    except KeyError:
        available = ", ".join(available_curves())
        raise KeyError(f"unknown curve {curve!r}; available curves: {available}") from None


def _arc(curve: Arc, width: int, height: int) -> tuple[tuple[int, int], _Source]:
    """The size of ``curve``'s canvas, and how to look up a point on it."""
    radius = width / math.radians(abs(curve.angle))
    if radius - height / 2 < _TIGHTEST * height:
        raise ValueError(
            f"this text is too short for a {abs(curve.angle):g} degree arc: its letters "
            "would meet in the middle; use a smaller angle or longer text"
        )
    # Arching up, the circle's centre is below the text, and outwards is up.
    outwards = -1 if curve.angle > 0 else 1

    def bent(along: float, across: float) -> tuple[float, float]:
        turn = along / radius
        reach = radius + across
        return reach * math.sin(turn), outwards * reach * math.cos(turn)

    edge = [
        bent(width * step / 256 - width / 2, across)
        for step in range(257)
        for across in (-height / 2, height / 2)
    ]
    left, top = min(p[0] for p in edge), min(p[1] for p in edge)
    right, bottom = max(p[0] for p in edge), max(p[1] for p in edge)

    def source(x: float, y: float) -> tuple[float, float]:
        across, down = x + left, y + top
        reach = math.hypot(across, down)
        turn = math.atan2(across, outwards * down)
        return width / 2 + turn * radius, height / 2 + outwards * (reach - radius)

    return (math.ceil(right - left), math.ceil(bottom - top)), source


def _wave(curve: Wave, width: int, height: int, size_px: int) -> tuple[tuple[int, int], _Source]:
    """The size of ``curve``'s canvas, and how to look up a point on it."""
    rise = curve.height * size_px

    def source(x: float, y: float) -> tuple[float, float]:
        return x, y - rise - rise * math.sin(2 * math.pi * curve.waves * x / width)

    return (width, math.ceil(height + 2 * rise)), source


def _mesh(
    size: tuple[int, int], source: _Source, flat: tuple[int, int]
) -> list[tuple[tuple[int, int, int, int], tuple[float, ...]]]:
    """Cut the canvas into small cells, each paired with the part of the flat text it shows."""
    width, height = flat
    step = max(4, min(16, width // 32))
    mesh = []
    for y0 in range(0, size[1], step):
        y1 = min(y0 + step, size[1])
        for x0 in range(0, size[0], step):
            x1 = min(x0 + step, size[0])
            corners = [source(x0, y0), source(x0, y1), source(x1, y1), source(x1, y0)]
            xs, ys = [c[0] for c in corners], [c[1] for c in corners]
            if max(xs) - min(xs) > max(width / 2, 8 * step):  # where the circle's ends meet
                continue
            if max(xs) < 0 or min(xs) > width or max(ys) < 0 or min(ys) > height:
                continue
            mesh.append(((x0, y0, x1, y1), tuple(v for corner in corners for v in corner)))
    return mesh


def bend(block: Block, curve: Curve, size_px: int, reduce: int = 1) -> Block:
    """Bend ``block`` along ``curve``, and shrink it by ``reduce`` when done.

    Text laid out at ``reduce`` times its final size bends with sharper edges.

    Raises:
        ValueError: the text is too short for the curve.
    """
    left, top, right, bottom = 0, 0, *block.mask.size
    outline = None
    if block.stroke is not None:
        mask, stroke_left, stroke_top = block.stroke
        x, y = stroke_left - block.left, stroke_top - block.top
        outline = mask, x, y
        left, top = min(left, x), min(top, y)
        right, bottom = max(right, x + mask.size[0]), max(bottom, y + mask.size[1])
    flat = (right - left + 2 * _PAD, bottom - top + 2 * _PAD)
    origin = (_PAD - left, _PAD - top)

    if isinstance(curve, Arc):
        size, source = _arc(curve, *flat)
    else:
        size, source = _wave(curve, *flat, size_px)
    mesh = _mesh(size, source, flat)

    def bent(mask: Image.Image, xy: tuple[int, int]) -> Image.Image:
        sheet = Image.new("L", flat, 0)
        sheet.paste(mask, xy)
        result = sheet.transform(
            size, Image.Transform.MESH, mesh, resample=Image.Resampling.BICUBIC
        )
        return result.reduce(reduce) if reduce > 1 else result

    text = bent(block.mask, origin)
    stroke = None
    if outline is not None:
        stroke = bent(outline[0], (origin[0] + outline[1], origin[1] + outline[2])), 0, 0
    return Block(mask=text, left=0, top=0, width=text.size[0], stroke=stroke)
