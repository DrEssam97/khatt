"""Zakhrafa (زخرفة): decorated Arabic text to copy and paste, for names and bios.

The decorations only go where letters join, and never inside lam-alef, so the
words stay joined and readable. Tashkeel stays with its letter.

    >>> khatt.zakhrafa("محمد", "royal")
    '꧁༺ مـ͜͡ـحـ͜͡ـمـ͜͡ـد ༻꧂'

Decorated text is harder for screen readers and search to understand, so keep
it for display names and the like, not for text people need to find or read
aloud.
"""

from __future__ import annotations

from dataclasses import dataclass

from khatt.kashida import TATWEEL, kashida_points

_BREVES = "͜͡"
"""A double breve below and a double inverted breve above, spanning to the next tatweel."""

_STOP_DOT = "۪ٜ"
"""An empty centre low stop and a dot below, small Arabic marks."""


@dataclass(frozen=True)
class _Style:
    join: str = ""
    """What goes between two letters that join."""
    frame: tuple[str, str] = ("", "")
    """What goes before and after the text."""


_STYLES: dict[str, _Style] = {
    "brackets": _Style(frame=("『", "』")),
    "crown": _Style(TATWEEL, ("♚ ", " ♚")),
    "dots": _Style(f"{TATWEEL}{_STOP_DOT}{TATWEEL}"),
    "flowers": _Style(TATWEEL, ("✿ ", " ✿")),
    "hearts": _Style(TATWEEL, ("♡ ", " ♡")),
    "long": _Style(TATWEEL * 3),
    "royal": _Style(f"{TATWEEL}{_BREVES}{TATWEEL}", ("꧁༺ ", " ༻꧂")),
    "stars": _Style(TATWEEL, ("★彡 ", " 彡★")),
    "tatweel": _Style(TATWEEL),
    "waves": _Style(f"{TATWEEL}{_BREVES}{TATWEEL}"),
}


def available_zakhrafa() -> list[str]:
    """Return the sorted names of the zakhrafa styles."""
    return sorted(_STYLES)


def _decorate(word: str, join: str) -> str:
    if not join:
        return word
    pieces, last = [], 0
    for point in kashida_points(word):
        pieces += [word[last:point], join]
        last = point
    return "".join(pieces) + word[last:]


def zakhrafa(text: str, style: str = "tatweel") -> str:
    """Decorate ``text`` in a zakhrafa style, as plain text to copy and paste.

    Arabic words are stretched or ornamented only where their letters join,
    so they stay joined. Other scripts are left as they are; a style's frame
    still goes around the whole text.

    Args:
        text: The text, as typed.
        style: A style name (see :func:`khatt.list_zakhrafa`).

    Returns:
        The decorated text. Empty or blank text comes back unchanged.

    Raises:
        KeyError: ``style`` is not a style name.
        ValueError: ``text`` or ``style`` is not a string.
    """
    if not isinstance(text, str):
        raise ValueError(f"text must be a string, got {text!r}")
    if not isinstance(style, str):
        raise ValueError(f"style must be a style name, got {style!r}")
    try:
        spec = _STYLES[style.strip().lower()]
    except KeyError:
        available = ", ".join(available_zakhrafa())
        raise KeyError(f"unknown zakhrafa style {style!r}; available styles: {available}") from None
    if not text.strip():
        return text
    lines = [
        " ".join(_decorate(word, spec.join) for word in line.split(" "))
        for line in text.split("\n")
    ]
    before, after = spec.frame
    return before + "\n".join(lines) + after
