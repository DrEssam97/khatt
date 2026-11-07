"""Colour values, shared by everything that paints."""

from __future__ import annotations

from PIL import ImageColor

Fill = str | tuple[int, int, int] | tuple[int, int, int, int]
"""A colour name or ``#rrggbb[aa]`` string, or an RGB / RGBA tuple."""


def rgba(fill: Fill) -> tuple[int, int, int, int]:
    """``fill`` as an RGBA tuple of 0-255; ``ValueError`` if it isn't a colour."""
    if isinstance(fill, str):
        color = ImageColor.getcolor(fill, "RGBA")  # raises ValueError if unknown
    elif isinstance(fill, (tuple, list)) and len(fill) in (3, 4):
        color = (*fill, 255)[:4]
    else:
        color = ()
    if not (
        isinstance(color, tuple)
        and len(color) == 4
        and all(isinstance(c, int) and 0 <= c <= 255 for c in color)
    ):
        raise ValueError(f"fill must be a colour string or an RGB(A) tuple of 0-255, got {fill!r}")
    red, green, blue, alpha = color
    return red, green, blue, alpha
