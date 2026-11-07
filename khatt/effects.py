"""Word art: gradients, glows, shadows, depth and bevels on shaped text.

Every effect works on the finished coverage mask of the text, never on single
letters, so letters stay joined and marks stay in place whatever the effect
does. Lengths are fractions of the font size, so an effect looks the same at
any size.

    >>> khatt.word_art("خط جميل", effect="gold")
    >>> khatt.draw_text(image, (40, 40), "خط", effect=khatt.Effect(fill="white",
    ...     shadow=khatt.Shadow()))
"""

from __future__ import annotations

import math
import numbers
from collections.abc import Sequence
from dataclasses import dataclass

from PIL import Image, ImageChops, ImageFilter

from khatt.color import Fill, rgba
from khatt.raster import Block

_LIGHT = 2.4
"""How strongly a bevel's slopes catch the light."""


def _check_length(name: str, value: float) -> None:
    if not (isinstance(value, numbers.Real) and math.isfinite(value) and value >= 0):
        raise ValueError(f"{name} must be a non-negative number, got {value!r}")


def _check_offset(name: str, value: tuple[float, float]) -> None:
    if not (
        isinstance(value, (tuple, list))
        and len(value) == 2
        and all(isinstance(v, numbers.Real) and math.isfinite(v) for v in value)
    ):
        raise ValueError(f"{name} must be an (x, y) pair of numbers, got {value!r}")


@dataclass(frozen=True)
class Gradient:
    """A fill that blends through ``colors``, spaced evenly across the text.

    Args:
        colors: Two or more colours, as anywhere khatt takes a ``fill``.
        angle: The direction of the blend in degrees, clockwise: 0 runs left
            to right, 90 (the default) top to bottom.
    """

    colors: Sequence[Fill]
    angle: float = 90

    def __post_init__(self) -> None:
        if isinstance(self.colors, str) or len(self.colors) < 2:
            raise ValueError(f"a gradient needs at least two colours, got {self.colors!r}")
        object.__setattr__(self, "colors", tuple(self.colors))
        for color in self.colors:
            rgba(color)
        if not (isinstance(self.angle, numbers.Real) and math.isfinite(self.angle)):
            raise ValueError(f"angle must be a number of degrees, got {self.angle!r}")


Paint = Fill | Gradient
"""A plain colour or a :class:`Gradient`."""


def _check_paint(paint: Paint) -> None:
    if not isinstance(paint, Gradient):
        rgba(paint)


@dataclass(frozen=True)
class Shadow:
    """A shadow behind the text.

    Args:
        offset: How far it falls, ``(right, down)``, in font sizes.
        blur: How soft it is, in font sizes; 0 is a hard edge.
        color: Its colour, usually translucent.
    """

    offset: tuple[float, float] = (0.04, 0.05)
    blur: float = 0.04
    color: Fill = "#00000099"

    def __post_init__(self) -> None:
        _check_offset("offset", self.offset)
        _check_length("blur", self.blur)
        rgba(self.color)


@dataclass(frozen=True)
class Glow:
    """Light around the text. Stack several for a bright core and a wide halo.

    Args:
        radius: How far it reaches, in font sizes.
        color: Its colour.
        strength: How bright it is; 1 is a plain blur of the text.
        offset: How far it shifts, ``(right, down)``, in font sizes.
    """

    radius: float = 0.1
    color: Fill = "white"
    strength: float = 1.5
    offset: tuple[float, float] = (0, 0)

    def __post_init__(self) -> None:
        _check_length("radius", self.radius)
        _check_length("strength", self.strength)
        _check_offset("offset", self.offset)
        rgba(self.color)


@dataclass(frozen=True)
class Extrude:
    """Solid depth behind the text, as if it were cut from a block.

    Args:
        depth: How deep it is, in font sizes.
        angle: The direction it runs in degrees, clockwise from right; the
            default, 45, runs down and to the right.
        color: The colour next to the text.
        end_color: The colour at the far end; default: ``color`` all the way.
    """

    depth: float = 0.1
    angle: float = 45
    color: Fill = "#333333"
    end_color: Fill | None = None

    def __post_init__(self) -> None:
        _check_length("depth", self.depth)
        if not (isinstance(self.angle, numbers.Real) and math.isfinite(self.angle)):
            raise ValueError(f"angle must be a number of degrees, got {self.angle!r}")
        rgba(self.color)
        if self.end_color is not None:
            rgba(self.end_color)


@dataclass(frozen=True)
class Effect:
    """How to paint text. Back to front: glows, shadow, depth, outline, fill, bevel.

    Args:
        fill: The colour of the letters, or a :class:`Gradient`.
        outline: Outline width, in font sizes.
        outline_fill: The colour of the outline, or a :class:`Gradient`.
        bevel: How wide the rounded edge of the letters is, in font sizes.
            It catches light from the top left.
        shadow: A :class:`Shadow`.
        glows: One :class:`Glow` or several, widest first.
        extrude: :class:`Extrude` depth.
    """

    fill: Paint = "black"
    outline: float = 0
    outline_fill: Paint = "black"
    bevel: float = 0
    shadow: Shadow | None = None
    glows: Glow | Sequence[Glow] = ()
    extrude: Extrude | None = None

    def __post_init__(self) -> None:
        _check_paint(self.fill)
        _check_paint(self.outline_fill)
        _check_length("outline", self.outline)
        _check_length("bevel", self.bevel)
        glows = (self.glows,) if isinstance(self.glows, Glow) else tuple(self.glows)
        object.__setattr__(self, "glows", glows)
        if not all(isinstance(glow, Glow) for glow in glows):
            raise ValueError(f"glows must be Glow objects, got {self.glows!r}")
        if self.shadow is not None and not isinstance(self.shadow, Shadow):
            raise ValueError(f"shadow must be a Shadow, got {self.shadow!r}")
        if self.extrude is not None and not isinstance(self.extrude, Extrude):
            raise ValueError(f"extrude must be an Extrude, got {self.extrude!r}")


_PRESETS: dict[str, Effect] = {
    "3d": Effect(
        fill="#ff4438",
        extrude=Extrude(depth=0.13, angle=60, color="#b3160d", end_color="#3d0602"),
        shadow=Shadow(offset=(0.08, 0.12), blur=0.05, color="#00000066"),
    ),
    "fire": Effect(
        fill=Gradient(("#8c1000", "#e8341c", "#ff8a00", "#ffd23f", "#fff7c2")),
        glows=(
            Glow(radius=0.2, color="#ff3d00", strength=1.5, offset=(0, -0.06)),
            Glow(radius=0.07, color="#ffb300", strength=1.8, offset=(0, -0.02)),
        ),
    ),
    "gold": Effect(
        fill=Gradient(("#8a5a14", "#e6b93c", "#fff3b0", "#f2c94c", "#9c6a16")),
        outline=0.012,
        outline_fill="#5c3a0a",
        bevel=0.035,
        shadow=Shadow(offset=(0.02, 0.03), blur=0.03, color="#00000080"),
    ),
    "ice": Effect(
        fill=Gradient(("#ffffff", "#bfefff", "#5cc8f2")),
        outline=0.012,
        outline_fill="#1f78b4",
        bevel=0.03,
        glows=Glow(radius=0.1, color="#9be7ff", strength=1.2),
    ),
    "neon": Effect(
        fill="#f2ffff",
        glows=(
            Glow(radius=0.18, color="#00e5ff", strength=1.6),
            Glow(radius=0.07, color="#00e5ff", strength=2.2),
            Glow(radius=0.02, color="#b8fbff", strength=1.5),
        ),
    ),
    "retro": Effect(
        fill=Gradient(("#ffe14d", "#ff7a3c", "#ff2975")),
        outline=0.015,
        outline_fill="#1a1147",
        extrude=Extrude(depth=0.09, color="#1a1147"),
    ),
    "silver": Effect(
        fill=Gradient(("#5b6470", "#dfe6ee", "#ffffff", "#aab4c0", "#4a525c")),
        outline=0.01,
        outline_fill="#2b3138",
        bevel=0.035,
        shadow=Shadow(offset=(0.02, 0.03), blur=0.03, color="#00000080"),
    ),
    "sticker": Effect(
        fill="#ff3d71",
        outline=0.07,
        outline_fill="white",
        shadow=Shadow(offset=(0.02, 0.04), blur=0.04, color="#00000066"),
    ),
}


def available_effects() -> list[str]:
    """Return the sorted names of all preset effects."""
    return sorted(_PRESETS)


def get_effect(effect: str | Effect) -> Effect:
    """Resolve a preset name to its :class:`Effect`; an ``Effect`` passes through.

    Presets are plain ``Effect`` objects, so ``dataclasses.replace`` makes
    variations: ``replace(khatt.get_effect("3d"), fill="#2563eb")``.

    Raises:
        KeyError: ``effect`` is not a preset name.
        ValueError: ``effect`` is neither a name nor an ``Effect``.
    """
    if isinstance(effect, Effect):
        return effect
    if not isinstance(effect, str):
        raise ValueError(f"effect must be a preset name or an Effect, got {effect!r}")
    try:
        return _PRESETS[effect.strip().lower()]
    except KeyError:
        available = ", ".join(available_effects())
        raise KeyError(f"unknown effect {effect!r}; available effects: {available}") from None


def _ramp(size: tuple[int, int], angle: float) -> Image.Image:
    """A grey ramp over ``size``, black where the gradient starts, white where it ends."""
    width, height = size
    across, down = math.cos(math.radians(angle)), math.sin(math.radians(angle))
    span = abs(across) * width + abs(down) * height
    base = Image.linear_gradient("L")  # black at the top, white at the bottom
    ramp = Image.new("L", size, 0)
    for share, axis in (
        (across * width / span, base.transpose(Image.Transpose.ROTATE_90).resize(size)),
        (down * height / span, base.resize(size)),
    ):
        table = [round((v if share > 0 else 255 - v) * abs(share)) for v in range(256)]
        ramp = ImageChops.add(ramp, axis.point(table))
    return ramp


def _gradient_image(gradient: Gradient, size: tuple[int, int]) -> Image.Image:
    """``gradient`` drawn over ``size``, in mode ``"RGBA"``."""
    stops = [rgba(color) for color in gradient.colors]
    last = len(stops) - 1
    ramp = _ramp(size, gradient.angle)
    channels = []
    for channel in range(4):
        table = []
        for value in range(256):
            position = value / 255 * last
            index = min(int(position), last - 1)
            mix = position - index
            start, end = stops[index][channel], stops[index + 1][channel]
            table.append(round(start + (end - start) * mix))
        channels.append(ramp.point(table))
    return Image.merge("RGBA", channels)


def _coat(layer: Image.Image, mask: Image.Image, paint: Paint) -> None:
    """Composite ``paint`` onto ``layer`` through ``mask``; a gradient spans the mask's ink."""
    box = mask.getbbox()
    if box is None:
        return
    if isinstance(paint, Gradient):
        coat = Image.new("RGBA", layer.size, (0, 0, 0, 0))
        coat.paste(_gradient_image(paint, (box[2] - box[0], box[3] - box[1])), box[:2])
        coat.putalpha(ImageChops.multiply(coat.getchannel("A"), mask))
    else:
        *rgb, opacity = rgba(paint)
        coat = Image.new("RGBA", layer.size, (*rgb, 0))
        coat.putalpha(mask.point([(v * opacity + 127) // 255 for v in range(256)]))
    layer.alpha_composite(coat)


def _blur(mask: Image.Image, radius: float) -> Image.Image:
    return mask.filter(ImageFilter.GaussianBlur(radius)) if radius > 0 else mask


def _gain(mask: Image.Image, strength: float) -> Image.Image:
    return mask.point([min(255, round(v * strength)) for v in range(256)])


def _shifted(mask: Image.Image, x: float, y: float) -> Image.Image:
    """``mask`` moved by whole pixels; the margin keeps it from wrapping around."""
    return ImageChops.offset(mask, round(x), round(y))


def _extrude_steps(extrude: Extrude, size_px: int) -> list[tuple[int, int]]:
    """Pixel offsets of the extrusion, far end first."""
    steps = max(1, round(extrude.depth * size_px)) if extrude.depth > 0 else 0
    across = math.cos(math.radians(extrude.angle))
    down = math.sin(math.radians(extrude.angle))
    return [(round(across * step), round(down * step)) for step in range(steps, 0, -1)]


def _bevel(layer: Image.Image, text: Image.Image, width: float) -> None:
    """Light the slopes of the letters from the top left, inside the letters only."""
    coverage = layer.getchannel("A")
    height = _blur(text, width)
    reach = max(1, round(width / 2))
    before, after = _shifted(height, reach, reach), _shifted(height, -reach, -reach)
    for slope, color in (
        (ImageChops.subtract(after, before), "white"),
        (ImageChops.subtract(before, after), "black"),
    ):
        _coat(layer, ImageChops.multiply(_gain(slope, _LIGHT), text), color)
    layer.putalpha(coverage)  # light changes the colour, never the edges of the letters


def margin(effect: Effect, size_px: int) -> int:
    """How many pixels ``effect`` can reach beyond the text and its outline."""
    reach = [0.0]
    for glow in effect.glows:  # type: ignore[union-attr]  # a tuple since __post_init__
        reach.append(3 * glow.radius + max(abs(v) for v in glow.offset))
    depth = effect.extrude.depth if effect.extrude is not None else 0
    if effect.shadow is not None:
        reach.append(3 * effect.shadow.blur + max(abs(v) for v in effect.shadow.offset) + depth)
    reach.append(depth)
    return math.ceil(max(reach) * size_px) + 2


def compose(block: Block, effect: Effect, size_px: int) -> tuple[Image.Image, int, int]:
    """Draw ``block`` with ``effect``.

    Returns:
        The drawing in mode ``"RGBA"``, and where its corner sits relative to
        the corner of ``block.mask``.
    """
    room = margin(effect, size_px) + math.ceil(effect.bevel * size_px)
    width, height = block.mask.size
    left, top, right, bottom = 0, 0, width, height
    stroke = None
    if block.stroke is not None:
        mask, stroke_left, stroke_top = block.stroke
        x, y = stroke_left - block.left, stroke_top - block.top
        stroke = mask, x, y
        left, top = min(left, x), min(top, y)
        right, bottom = max(right, x + mask.size[0]), max(bottom, y + mask.size[1])
    size = (right - left + 2 * room, bottom - top + 2 * room)
    x0, y0 = room - left, room - top

    text = Image.new("L", size, 0)
    text.paste(block.mask, (x0, y0))
    body = text
    if stroke is not None:
        outline = Image.new("L", size, 0)
        outline.paste(stroke[0], (x0 + stroke[1], y0 + stroke[2]))
        body = ImageChops.lighter(text, outline)

    steps = [] if effect.extrude is None else _extrude_steps(effect.extrude, size_px)
    solid = body
    for x, y in steps:
        solid = ImageChops.lighter(solid, _shifted(body, x, y))

    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    for glow in effect.glows:  # type: ignore[union-attr]  # a tuple since __post_init__
        moved = _shifted(solid, glow.offset[0] * size_px, glow.offset[1] * size_px)
        _coat(layer, _gain(_blur(moved, glow.radius * size_px), glow.strength), glow.color)
    if effect.shadow is not None:
        shadow = effect.shadow
        moved = _shifted(solid, shadow.offset[0] * size_px, shadow.offset[1] * size_px)
        _coat(layer, _blur(moved, shadow.blur * size_px), shadow.color)
    if effect.extrude is not None:
        near = rgba(effect.extrude.color)
        far = near if effect.extrude.end_color is None else rgba(effect.extrude.end_color)
        for index, (x, y) in enumerate(steps):
            mix = 1 - index / max(1, len(steps) - 1)  # 1 at the far end, 0 next to the text
            color = tuple(round(n + (f - n) * mix) for n, f in zip(near, far, strict=True))
            _coat(layer, _shifted(body, x, y), color)  # type: ignore[arg-type]
    if stroke is not None:
        _coat(layer, body, effect.outline_fill)
    _coat(layer, text, effect.fill)
    if effect.bevel > 0:
        _bevel(layer, text, effect.bevel * size_px)
    return layer, -x0, -y0
