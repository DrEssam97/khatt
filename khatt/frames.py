"""Frames around text art, and the shapes that draw their lines in images.

A frame is drawn with box-drawing characters, so it stays text in a terminal. The
``lawha`` frame, after the framed panels of Arabic calligraphy, puts ``۞`` (the Arabic
sign that starts a rub el hizb) at its corners and in the middle of its top and bottom.
"""

from __future__ import annotations

FRAMES: dict[str, tuple[str, str, str, str, str, str]] = {
    "double": ("╔", "═", "╗", "║", "╚", "╝"),
    "heavy": ("┏", "━", "┓", "┃", "┗", "┛"),
    "lawha": ("۞", "═", "۞", "║", "۞", "۞"),
    "round": ("╭", "─", "╮", "│", "╰", "╯"),
    "single": ("┌", "─", "┐", "│", "└", "┘"),
}
"""Frame styles: top-left, horizontal, top-right, vertical, bottom-left, bottom-right."""

_ORNAMENT = "۞"
_BLANKS = " ⠀"

# Box-drawing characters as (weight, arms): arms are the sides of the cell the line
# reaches, l(eft), r(ight), u(p), d(own).
_BOX: dict[str, tuple[str, str]] = {
    "─": ("light", "lr"),
    "│": ("light", "ud"),
    "┌": ("light", "rd"),
    "┐": ("light", "ld"),
    "└": ("light", "ru"),
    "┘": ("light", "lu"),
    "╭": ("light", "rd"),
    "╮": ("light", "ld"),
    "╰": ("light", "ru"),
    "╯": ("light", "lu"),
    "━": ("heavy", "lr"),
    "┃": ("heavy", "ud"),
    "┏": ("heavy", "rd"),
    "┓": ("heavy", "ld"),
    "┗": ("heavy", "ru"),
    "┛": ("heavy", "lu"),
    "═": ("double", "lr"),
    "║": ("double", "ud"),
    "╔": ("double", "rd"),
    "╗": ("double", "ld"),
    "╚": ("double", "ru"),
    "╝": ("double", "lu"),
}
BOX_CHARACTERS = frozenset(_BOX)
"""The box-drawing characters that :func:`box_rects` draws."""


def available_frames() -> list[str]:
    """Return the sorted names of the frame styles."""
    return sorted(FRAMES)


def frame_art(art: str, style: str = "double", *, padding: int = 1) -> str:
    """``art`` inside a frame.

    Args:
        art: Text art, as returned by :func:`khatt.render`.
        style: A frame style (see :func:`available_frames`).
        padding: Blank rows above and below the art; twice as many blank columns on
            each side, since terminal cells are twice as tall as they are wide.

    Returns:
        The framed art, every line the same width.
    """
    key = style.strip().lower()
    if key not in FRAMES:
        raise KeyError(
            f"unknown frame {style!r}; available frames: {', '.join(available_frames())}"
        )
    if padding < 0:
        raise ValueError(f"padding must not be negative, got {padding}")
    top_left, horizontal, top_right, vertical, bottom_left, bottom_right = FRAMES[key]
    lines = art.split("\n")
    inner = max(len(line) for line in lines) + 4 * padding
    rule = [horizontal] * inner
    if key == "lawha" and inner >= 3:
        rule[inner // 2] = _ORNAMENT
    blank = vertical + " " * inner + vertical
    body = [
        vertical + " " * (2 * padding) + line.ljust(inner - 2 * padding) + vertical
        for line in lines
    ]
    return "\n".join(
        [
            top_left + "".join(rule) + top_right,
            *[blank] * padding,
            *body,
            *[blank] * padding,
            bottom_left + "".join(rule) + bottom_right,
        ]
    )


def box_rects(char: str, width: float, height: float) -> list[tuple[float, float, float, float]]:
    """The filled rectangles that draw a box-drawing character in a ``width`` x ``height`` cell.

    Coordinates are relative to the cell's top-left corner. Lines meet their
    neighbours' at the cell edges, so a frame comes out unbroken.
    """
    weight, arms = _BOX[char]
    cx, cy = width / 2, height / 2
    light = max(1.0, width * 0.12)
    if weight != "double":
        half = (light if weight == "light" else light * 2) / 2
        rects = []
        if "l" in arms:
            rects.append((0.0, cy - half, cx + half, cy + half))
        if "r" in arms:
            rects.append((cx - half, cy - half, width, cy + half))
        if "u" in arms:
            rects.append((cx - half, 0.0, cx + half, cy + half))
        if "d" in arms:
            rects.append((cx - half, cy - half, cx + half, height))
        return rects
    half = light / 2
    gap = max(light * 1.2, width * 0.16)
    if arms == "lr":
        return [
            (0.0, cy - gap - half, width, cy - gap + half),
            (0.0, cy + gap - half, width, cy + gap + half),
        ]
    if arms == "ud":
        return [
            (cx - gap - half, 0.0, cx - gap + half, height),
            (cx + gap - half, 0.0, cx + gap + half, height),
        ]
    # A corner: the outer pair of lines turns around the inner pair.
    h = 1 if "r" in arms else -1
    v = 1 if "d" in arms else -1
    rects = []
    for side in (-1, 1):  # -1: the outer lines, 1: the inner ones
        y = cy + side * v * gap
        x = cx + side * h * gap
        x_from = x - half if h > 0 else x + half
        rects.append(_span(x_from, width if h > 0 else 0.0, y - half, y + half))
        y_from = y - half if v > 0 else y + half
        rects.append(_span_vertical(x - half, x + half, y_from, height if v > 0 else 0.0))
    return rects


def _span(x0: float, x1: float, y0: float, y1: float) -> tuple[float, float, float, float]:
    return min(x0, x1), y0, max(x0, x1), y1


def _span_vertical(x0: float, x1: float, y0: float, y1: float) -> tuple[float, float, float, float]:
    return x0, min(y0, y1), x1, max(y0, y1)
