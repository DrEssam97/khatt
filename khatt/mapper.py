"""Map grayscale coverage grids to text-art characters.

Input images use ink-coverage convention: pixel value 0 is empty background,
255 is fully inked. Higher coverage maps to a denser character, monotonically.

``threshold`` (in [0, 1]) forces coverage below it to blank and rescales the
remaining range across the ramp; for ``braille`` and the block mosaics
(``halfblocks``, ``quadrants``, ``sextants``) it is the on/off cutoff of each
dot or block (default 0.5).

The ``letters`` style inks with the letters of a text instead (see
:func:`fill_characters`): the word drawn out of its own letters, or out of a
phrase, read right to left along each row when the phrase is Arabic.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Callable
from dataclasses import dataclass

from PIL import Image

_BLANKS = " ⠀"  # characters trimmed from line ends


@dataclass(frozen=True)
class Style:
    """A named output style: a character ramp or a dot-matrix mapping."""

    name: str
    cell: tuple[int, int]
    """Pixels consumed per output character, (x, y)."""
    ramp: str | None
    """Blank-to-dense character ramp; ``None`` means a dot or block mosaic."""
    description: str
    mosaic: tuple[str, ...] | None = None
    """Block mosaic: the character for each set of inked sub-cells, indexed by a bit
    mask whose bit ``y * cell[0] + x`` is the sub-cell at column ``x``, row ``y``.
    ``None`` with no ramp means braille."""
    letters: bool = False
    """Ink with the characters of a text (see :func:`fill_characters`)."""


def _sextants() -> tuple[str, ...]:
    """The 64 sextant characters (2x3 blocks), from Unicode's Legacy Computing block.

    It leaves out the four patterns other blocks already draw: blank, full, and the
    left and right halves.
    """
    chars = []
    for mask in range(64):
        if mask == 0:
            chars.append(" ")
        elif mask == 63:
            chars.append("█")
        elif mask == 21:
            chars.append("▌")
        elif mask == 42:
            chars.append("▐")
        else:
            chars.append(chr(0x1FB00 + mask - 1 - (mask > 21) - (mask > 42)))
    return tuple(chars)


STYLES: dict[str, Style] = {
    "blocks": Style("blocks", (1, 1), " ░▒▓█", "Unicode shade blocks"),
    "ascii": Style("ascii", (1, 1), " .:-=+*#%@", "classic ASCII density ramp"),
    "braille": Style("braille", (2, 4), None, "braille patterns, 2x4 dots per cell"),
    "halfblocks": Style(
        "halfblocks", (1, 2), None, "half blocks, 2 per cell, top and bottom", (" ", "▀", "▄", "█")
    ),
    "quadrants": Style(
        "quadrants",
        (2, 2),
        None,
        "quadrant blocks, 2x2 per cell",
        tuple(" ▘▝▀▖▌▞▛▗▚▐▜▄▙▟█"),
    ),
    "sextants": Style(
        "sextants",
        (2, 3),
        None,
        "sextant blocks, 2x3 per cell (needs a font with Unicode 13 legacy computing symbols)",
        _sextants(),
    ),
    "letters": Style(
        "letters", (1, 1), None, "the text's own letters, or a phrase given as the fill", None, True
    ),
}

DEFAULT_FILL = "خط"
"""What the ``letters`` style inks with when no fill is given."""


def fill_characters(fill: str) -> tuple[list[str], bool]:
    """The characters that ink the ``letters`` style, and whether they run right to left.

    Arabic letters take their isolated form, a character of its own that terminals
    can't join to its neighbours or move. Spaces, tashkeel and other marks are left
    out; Latin letters and digits stay, so Arabizi works as a fill too.
    """
    from khatt.terminal import _tables

    forms = _tables()[0]
    chars = []
    rtl = None
    for char in fill:
        if char.isspace() or unicodedata.category(char) in ("Mn", "Me", "Cf"):
            continue
        if rtl is None and unicodedata.bidirectional(char) in ("R", "AL", "L"):
            rtl = unicodedata.bidirectional(char) != "L"
        chars.append(forms.get(char, {}).get("isolated", char))
    return chars, bool(rtl)


# Braille bit assignment per (dot column, dot row) within a 2x4 cell.
_BRAILLE_BITS = {
    (0, 0): 0x01,
    (0, 1): 0x02,
    (0, 2): 0x04,
    (0, 3): 0x40,
    (1, 0): 0x08,
    (1, 1): 0x10,
    (1, 2): 0x20,
    (1, 3): 0x80,
}


def available_styles() -> list[str]:
    """Return the sorted names of all output styles."""
    return sorted(STYLES)


def get_style(name: str) -> Style:
    """Look up a style by name (case-insensitive)."""
    key = name.strip().lower()
    if key not in STYLES:
        available = ", ".join(sorted(STYLES))
        raise KeyError(f"unknown style {name!r}; available styles: {available}")
    return STYLES[key]


def _ramp_char(ramp: str, coverage: float, threshold: float | None) -> str:
    if threshold is not None:
        if coverage < threshold or threshold >= 1.0:
            coverage = 0.0
        else:
            coverage = (coverage - threshold) / (1.0 - threshold)
    index = min(int(coverage * len(ramp)), len(ramp) - 1)
    return ramp[index]


def map_image(
    image: Image.Image, style: str, threshold: float | None = None, fill: str | None = None
) -> str:
    """Map a grayscale grid image to lines of text-art characters.

    The image size must be an exact multiple of the style's cell size; use
    :func:`khatt.raster.to_grid` with the style's ``cell`` to produce it.
    ``fill`` is what the ``letters`` style inks with (default: ``خط``).
    """
    resolved = get_style(style)
    if threshold is not None and not 0.0 <= threshold <= 1.0:
        raise ValueError(f"threshold must be within [0, 1], got {threshold}")

    dx, dy = resolved.cell
    width, height = image.size
    if width % dx or height % dy:
        raise ValueError(
            f"image size {width}x{height} is not a multiple of the "
            f"{resolved.name} cell size {dx}x{dy}"
        )

    gray = image if image.mode == "L" else image.convert("L")
    data = gray.tobytes()  # row-major coverage bytes

    def coverage_at(x: int, y: int) -> float:
        return data[y * width + x] / 255.0

    dot_cutoff = 0.5 if threshold is None else threshold
    if resolved.letters:
        return _letters(image.size, coverage_at, dot_cutoff, fill or DEFAULT_FILL)
    lines: list[str] = []
    for row in range(height // dy):
        chars: list[str] = []
        for col in range(width // dx):
            if resolved.ramp is not None:
                chars.append(_ramp_char(resolved.ramp, coverage_at(col, row), threshold))
            elif resolved.mosaic is not None:
                mask = 0
                for sub_y in range(dy):
                    for sub_x in range(dx):
                        if coverage_at(col * dx + sub_x, row * dy + sub_y) >= dot_cutoff:
                            mask |= 1 << (sub_y * dx + sub_x)
                chars.append(resolved.mosaic[mask])
            else:
                code = 0x2800
                for (dot_x, dot_y), bit in _BRAILLE_BITS.items():
                    if coverage_at(col * dx + dot_x, row * dy + dot_y) >= dot_cutoff:
                        code |= bit
                chars.append(chr(code))
        lines.append("".join(chars).rstrip(_BLANKS))
    return "\n".join(lines)


def _letters(
    size: tuple[int, int],
    coverage_at: Callable[[int, int], float],
    cutoff: float,
    fill: str,
) -> str:
    """Ink every covered cell with the next character of ``fill``, in its reading order."""
    chars, rtl = fill_characters(fill)
    if not chars:
        raise ValueError("the fill has no characters to draw with")
    width, height = size
    lines = []
    used = 0
    for row in range(height):
        cells = [" "] * width
        for col in range(width - 1, -1, -1) if rtl else range(width):
            if coverage_at(col, row) >= cutoff:
                cells[col] = chars[used % len(chars)]
                used += 1
        lines.append("".join(cells).rstrip(_BLANKS))
    return "\n".join(lines)
