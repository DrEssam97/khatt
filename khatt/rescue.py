"""Turn text pre-shaped by arabic_reshaper back into plain text.

The old recipe for Arabic in Pillow and matplotlib passed text through
``arabic_reshaper.reshape`` (letters swapped for their joined "presentation
forms") and python-bidi's ``get_display`` (reversed into display order),
because those libraries couldn't shape Arabic. Now that Pillow with Raqm and
matplotlib 3.11+ shape it themselves, such text is shaped twice and comes out
broken. :func:`unreshape` undoes both steps, giving the text as typed, which
khatt, Raqm or matplotlib can then shape once.

    import khatt

    plain = khatt.unreshape(old_text)  # the text before arabic_reshaper and get_display
    khatt.draw_text(image, (20, 20), plain)
"""

from __future__ import annotations

import unicodedata
from itertools import pairwise

from bidi import get_display

_PRESENTATION_FORMS = ((0xFB50, 0xFDFF), (0xFE70, 0xFEFC))
_TYPED_SYMBOLS = frozenset({0xFD3E, 0xFD3F, *range(0xFDF0, 0xFDFE)}) - {0xFDF2}
"""Symbols people type on purpose, such as ornate brackets and ﷺ, kept as they are.
arabic_reshaper writes ﷲ (U+FDF2) for الله, so that one goes back."""
_DIRECTIONS = {"rtl": "R", "ltr": "L"}


def _presentation_form(ch: str) -> bool:
    code = ord(ch)
    return code not in _TYPED_SYMBOLS and any(
        low <= code <= high for low, high in _PRESENTATION_FORMS
    )


class ReshapedTextWarning(UserWarning):
    """Text given to khatt was already shaped by arabic_reshaper (see :func:`unreshape`)."""


def is_reshaped(text: str) -> bool:
    """Whether ``text`` has Arabic presentation forms, as arabic_reshaper writes it.

    Text as typed never needs them: they are the joined shapes of letters,
    which a shaper picks itself. Symbols typed on purpose, such as ``ﷺ``
    and the ornate brackets ``﴿ ﴾``, don't count.
    """
    return any(_presentation_form(ch) for ch in text)


def _form(ch: str) -> str:
    name = unicodedata.name(ch, "")
    for form in ("INITIAL", "MEDIAL", "FINAL"):
        if f"{form} FORM" in name:
            return form
    return ""


def _in_display_order(line: str) -> bool:
    """Whether a reshaped line reads backwards, as ``get_display`` leaves it.

    In typed order a word's joined letters run initial, medial, final; in
    display order the other way round. A line whose shapes don't tell (short
    words, lam-alef) counts as display order, as the usual recipe was
    ``get_display(reshape(text))``.
    """
    score = 0
    for first, second in pairwise(line):
        a, b = _form(first), _form(second)
        if a in ("INITIAL", "MEDIAL") and b in ("MEDIAL", "FINAL"):
            score += 1
        elif a in ("MEDIAL", "FINAL") and b in ("INITIAL", "MEDIAL"):
            score -= 1
    return score <= 0


def _letters(line: str, backwards: bool) -> str:
    """The line with presentation forms turned back into letters (lam-alef into two)."""
    out = []
    for ch in line:
        if _presentation_form(ch):
            plain = unicodedata.normalize("NFKC", ch)
            out.append(plain[::-1] if backwards else plain)
        else:
            out.append(ch)
    return "".join(out)


def _typed_order(line: str, direction: str | None) -> str:
    """Undo ``get_display`` on one line: the typed line it came from.

    Several lines can give the same display; without ``direction``, the one
    read right to left wins unless the line has more Latin letters than
    Arabic.
    """
    if direction is not None:
        return get_display(line, base_dir=_DIRECTIONS[direction])
    arabic = sum(1 for ch in line if unicodedata.bidirectional(ch) in ("AL", "R"))
    latin = sum(1 for ch in line if unicodedata.bidirectional(ch) == "L")
    for base in ("R", "L") if arabic >= latin else ("L", "R"):
        typed = get_display(line, base_dir=base)
        if get_display(typed) == line:
            return typed
    return get_display(line)


def unreshape(text: str, *, display_order: bool | None = None, direction: str | None = None) -> str:
    """The text as typed, from arabic_reshaper's output (and ``get_display``'s).

    Presentation forms go back to plain letters (a lam-alef ligature to lam
    and alef, ``ﷲ`` to ``الله``), and lines that ``get_display`` reversed are
    put back in typed order. Symbols typed on purpose, such as ``ﷺ``, stay.
    Text without presentation forms comes back unchanged.

    Args:
        text: Text from ``arabic_reshaper.reshape``, maybe then
            ``get_display``; one line or several.
        display_order: Whether the text went through ``get_display``.
            ``None`` (default) tells from each line's letter shapes.
        direction: ``"rtl"`` or ``"ltr"``: the direction the lines were
            written in, for undoing ``get_display``. ``None`` (default)
            guesses: right to left, unless a line has more Latin letters than
            Arabic. A mostly Arabic line that starts with a Latin word looks
            the same in display order as one that ends with it; pass
            ``"ltr"`` for those.

    Returns:
        Plain text for :func:`khatt.draw_text`, or for Pillow with Raqm and
        matplotlib 3.11+, which shape it once.
    """
    if direction is not None and direction not in _DIRECTIONS:
        raise ValueError(f"direction must be 'rtl' or 'ltr', got {direction!r}")
    if not is_reshaped(text):
        return text
    lines = []
    for line in text.split("\n"):
        backwards = _in_display_order(line) if display_order is None else display_order
        letters = _letters(line, backwards)
        lines.append(_typed_order(letters, direction) if backwards and letters else letters)
    return "\n".join(lines)
