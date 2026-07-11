"""Map grayscale coverage grids to text-art characters.

Input images use ink-coverage convention: pixel value 0 is empty background,
255 is fully inked. Higher coverage maps to a denser character, monotonically.

``threshold`` (in [0, 1]) forces coverage below it to blank and rescales the
remaining range across the ramp; for ``braille`` it is the per-dot on/off
cutoff (default 0.5).
"""

from __future__ import annotations

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
    """Blank-to-dense character ramp; ``None`` means braille dot mapping."""
    description: str


STYLES: dict[str, Style] = {
    "blocks": Style("blocks", (1, 1), " ░▒▓█", "Unicode shade blocks"),
    "ascii": Style("ascii", (1, 1), " .:-=+*#%@", "classic ASCII density ramp"),
    "braille": Style("braille", (2, 4), None, "braille patterns, 2x4 dots per cell"),
}

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


def map_image(image: Image.Image, style: str, threshold: float | None = None) -> str:
    """Map a grayscale grid image to lines of text-art characters.

    The image size must be an exact multiple of the style's cell size; use
    :func:`khatt.raster.to_grid` with the style's ``cell`` to produce it.
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
    lines: list[str] = []
    for row in range(height // dy):
        chars: list[str] = []
        for col in range(width // dx):
            if resolved.ramp is not None:
                chars.append(_ramp_char(resolved.ramp, coverage_at(col, row), threshold))
            else:
                code = 0x2800
                for (dot_x, dot_y), bit in _BRAILLE_BITS.items():
                    if coverage_at(col * dx + dot_x, row * dy + dot_y) >= dot_cutoff:
                        code |= bit
                chars.append(chr(code))
        lines.append("".join(chars).rstrip(_BLANKS))
    return "\n".join(lines)
