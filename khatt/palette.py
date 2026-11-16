"""Colour for text art: palettes, gradients and terminal colour codes.

A palette is a list of colours. Spread over the art it makes a gradient, or solid bands
with ``bands=True``. Gradients follow Arabic reading direction by default: the first
colour is at the right edge, where an Arabic line starts.
"""

from __future__ import annotations

from collections.abc import Sequence

from khatt.color import Fill, rgba

RGB = tuple[int, int, int]

PALETTES: dict[str, tuple[str, ...]] = {
    "andalus": ("#0b6e4f", "#14a098", "#d4af37", "#b23a48"),
    "damask": ("#7a1035", "#c9184a", "#ff4d6d", "#ffb3c1"),
    "desert": ("#8b4513", "#d2691e", "#f4a460", "#ffe4b5"),
    "fajr": ("#3d348b", "#7678ed", "#f7b801", "#f18701"),
    "gold": ("#8a6212", "#d4a017", "#fff1a8", "#b8860b"),
    "nile": ("#0d47a1", "#1e88e5", "#26c6da", "#43a047"),
}
"""Named palettes, each listed in gradient order."""

DIRECTIONS = ("rtl", "ltr", "down", "up")
"""Where a gradient starts and runs: right to left, left to right, top down, bottom up."""

COLOR_MODES = ("truecolor", "256")
"""Terminal colour codes: 24-bit colour, or the 256-colour palette."""

_BLANKS = frozenset(" ⠀")

Palette = str | Sequence[Fill]
"""A palette name, colours separated by commas, or a list of colours."""


def available_palettes() -> list[str]:
    """Return the sorted names of the bundled palettes."""
    return sorted(PALETTES)


def palette_colors(palette: Palette) -> list[RGB]:
    """The colours of ``palette``, as RGB tuples.

    Args:
        palette: A palette name (see :func:`available_palettes`), colours separated by
            commas (``"#c00,white,black"``), a single colour, or a list of colours.

    Raises:
        KeyError: An unknown palette name.
        ValueError: A colour that isn't one, or an empty palette.
    """
    if isinstance(palette, str):
        name = palette.strip().lower()
        if name in PALETTES:
            fills: Sequence[Fill] = PALETTES[name]
        elif "," in palette:
            fills = [part.strip() for part in palette.split(",")]
        else:
            try:
                fills = [rgba(palette.strip())]
            except ValueError:
                available = ", ".join(available_palettes())
                raise KeyError(
                    f"unknown palette {palette!r}; available palettes: {available}, "
                    "or colours separated by commas"
                ) from None
    else:
        fills = list(palette)
    if not fills:
        raise ValueError("a palette needs at least one colour")
    return [rgba(fill)[:3] for fill in fills]


def _at(colors: Sequence[RGB], position: float, bands: bool) -> RGB:
    """The colour at ``position`` (0 to 1) along the palette."""
    if len(colors) == 1:
        return colors[0]
    if bands:
        return colors[min(int(position * len(colors)), len(colors) - 1)]
    scaled = position * (len(colors) - 1)
    index = min(int(scaled), len(colors) - 2)
    mix = scaled - index
    start, end = colors[index], colors[index + 1]
    red, green, blue = (round(a + (b - a) * mix) for a, b in zip(start, end, strict=True))
    return red, green, blue


def cell_colors(
    art: str, palette: Palette, *, direction: str = "rtl", bands: bool = False
) -> list[list[RGB | None]]:
    """The colour of every character of ``art``: ``None`` for blank cells.

    Args:
        art: Text art, as returned by :func:`khatt.render`.
        palette: See :func:`palette_colors`.
        direction: Where the gradient starts (see :data:`DIRECTIONS`); ``"rtl"``, the
            default, puts the first colour at the right edge.
        bands: Solid bands of each colour instead of a smooth blend.

    Returns:
        One list per line of ``art``, one entry per character.
    """
    if direction not in DIRECTIONS:
        raise ValueError(f"direction must be one of {', '.join(DIRECTIONS)}, got {direction!r}")
    colors = palette_colors(palette)
    lines = art.split("\n")
    inked = [
        (row, col)
        for row, line in enumerate(lines)
        for col, char in enumerate(line)
        if char not in _BLANKS
    ]
    if not inked:
        return [[None] * len(line) for line in lines]
    horizontal = direction in ("rtl", "ltr")
    first = min(col if horizontal else row for row, col in inked)
    last = max(col if horizontal else row for row, col in inked)
    span = max(1, last - first)

    def position(row: int, col: int) -> float:
        offset = (col if horizontal else row) - first
        return 1 - offset / span if direction in ("rtl", "up") else offset / span

    return [
        [
            None if char in _BLANKS else _at(colors, position(row, col), bands)
            for col, char in enumerate(line)
        ]
        for row, line in enumerate(lines)
    ]


def _xterm256(color: RGB) -> int:
    """The nearest of the 256 terminal colours (the 6x6x6 cube or the gray ramp)."""
    levels = (0, 95, 135, 175, 215, 255)

    def nearest_level(value: int) -> int:
        return min(range(6), key=lambda index: abs(levels[index] - value))

    cube = [nearest_level(value) for value in color]
    cube_color = tuple(levels[index] for index in cube)
    gray_index = min(23, max(0, round((sum(color) / 3 - 8) / 10)))
    gray = 8 + gray_index * 10

    def distance(other: Sequence[int]) -> int:
        return sum((a - b) ** 2 for a, b in zip(color, other, strict=True))

    if distance((gray, gray, gray)) < distance(cube_color):
        return 232 + gray_index
    return 16 + 36 * cube[0] + 6 * cube[1] + cube[2]


def _code(color: RGB, mode: str) -> str:
    if mode == "truecolor":
        return f"\033[38;2;{color[0]};{color[1]};{color[2]}m"
    return f"\033[38;5;{_xterm256(color)}m"


def color_art(
    art: str,
    palette: Palette,
    *,
    direction: str = "rtl",
    bands: bool = False,
    mode: str = "truecolor",
) -> str:
    """Colour text art with terminal colour codes, for printing in a terminal.

    Args:
        art: Text art, as returned by :func:`khatt.render`.
        palette: A palette name (see :func:`available_palettes`), colours separated by
            commas, or a list of colours.
        direction: Where the gradient starts (see :data:`DIRECTIONS`).
        bands: Solid bands of each colour instead of a smooth blend, like a flag.
        mode: ``"truecolor"`` (24-bit) or ``"256"`` for terminals with 256 colours.

    Returns:
        ``art`` with colour codes before each change of colour and a reset at the end
        of every coloured line. Blank cells get no colour.
    """
    if mode not in COLOR_MODES:
        raise ValueError(f"mode must be one of {', '.join(COLOR_MODES)}, got {mode!r}")
    colors = cell_colors(art, palette, direction=direction, bands=bands)
    out: list[str] = []
    for line, line_colors in zip(art.split("\n"), colors, strict=True):
        parts: list[str] = []
        current: str | None = None
        for char, color in zip(line, line_colors, strict=True):
            if color is not None:
                code = _code(color, mode)
                if code != current:
                    parts.append(code)
                    current = code
            parts.append(char)
        if current is not None:
            parts.append("\033[0m")
        out.append("".join(parts))
    return "\n".join(out)
