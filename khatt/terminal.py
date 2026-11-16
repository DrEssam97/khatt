"""Arabic for terminals that can't lay it out.

Most terminals draw one character per cell, left to right, as stored: Arabic comes out
with its letters apart and backwards. A few (Konsole, mlterm, GNOME Terminal and other
VTE terminals, macOS Terminal) join and order Arabic themselves. :func:`for_terminal`
gives the first kind the text already joined, in Unicode's presentation forms, and in
display order, and gives the second kind the text as typed.

This is only for text printed to a terminal. Images and SVG are shaped by HarfBuzz, never
with presentation forms.
"""

from __future__ import annotations

import os
import unicodedata
from collections.abc import Mapping
from functools import lru_cache

from bidi import get_display

from khatt.shaping import _BIDI_BASE_DIR, _LEVEL, _LEVELS, _logical_order, strip_tashkeel

_FORM_TAGS = {
    "<isolated>": "isolated",
    "<final>": "final",
    "<initial>": "initial",
    "<medial>": "medial",
}
_LAM = "ل"
_ALEFS = frozenset("آأإا")
"""Alef with madda, hamza above, hamza below, and plain: the four that join lam into لا."""
_TATWEEL = "ـ"
_ZWJ = "‍"
_JOIN_CAUSING = frozenset({_TATWEEL, _ZWJ})

_PAIRS = "()[]{}<>«»‹›⁅⁆⁽⁾₍₎"
_MIRRORS = {
    **dict(zip(_PAIRS[::2], _PAIRS[1::2], strict=True)),
    **dict(zip(_PAIRS[1::2], _PAIRS[::2], strict=True)),
}
"""Brackets and their mirror images."""

TERMINAL_MODES = ("auto", "yes", "no")
"""Whether the terminal joins and orders Arabic itself: ``auto`` (guess), ``yes``, ``no``."""


@lru_cache(maxsize=1)
def _tables() -> tuple[dict[str, dict[str, str]], dict[tuple[str, str], str]]:
    """Presentation forms per letter, and lam-alef ligatures per ``(alef, form)``."""
    forms: dict[str, dict[str, str]] = {}
    ligatures: dict[tuple[str, str], str] = {}
    for low, high in ((0xFE70, 0xFEFC), (0xFB50, 0xFDFF)):  # Forms-B first, like shapers
        for code in range(low, high + 1):
            tag, *parts = unicodedata.decomposition(chr(code)).split() or [""]
            if tag not in _FORM_TAGS:
                continue
            letters = [chr(int(part, 16)) for part in parts]
            form = _FORM_TAGS[tag]
            if len(letters) == 1:
                forms.setdefault(letters[0], {}).setdefault(form, chr(code))
            elif letters[:1] == [_LAM] and letters[1:] and letters[1] in _ALEFS:
                ligatures.setdefault((letters[1], form), chr(code))
    return forms, ligatures


def _joining(char: str) -> str:
    """Joining type: ``D`` (both sides), ``R`` (right only), ``C``, ``T`` or ``U``."""
    if char in _JOIN_CAUSING:
        return "C"
    if unicodedata.category(char) == "Mn":
        return "T"
    letter_forms = _tables()[0].get(char)
    if not letter_forms:
        return "U"
    return "D" if "initial" in letter_forms or "medial" in letter_forms else "R"


def join_letters(text: str) -> str:
    """Replace Arabic letters with the presentation form for their place in the word.

    Lam followed by alef becomes the lam-alef ligature, as every Arabic font draws it.
    Letters without presentation forms, and every other character, stay as they are.
    """
    forms, ligatures = _tables()
    types = [_joining(char) for char in text]
    out: list[str] = []
    index = 0
    while index < len(text):
        char = text[index]
        kind = types[index]
        if kind not in ("D", "R"):
            out.append(char)
            index += 1
            continue
        before = next((types[i] for i in range(index - 1, -1, -1) if types[i] != "T"), "U")
        after_index = next((i for i in range(index + 1, len(text)) if types[i] != "T"), None)
        after = "U" if after_index is None else types[after_index]
        joins_before = before in ("D", "C")
        if char == _LAM and after_index is not None:
            ligature = ligatures.get((text[after_index], "final" if joins_before else "isolated"))
            if ligature is not None:
                out.append(ligature)
                out.extend(text[index + 1 : after_index])  # marks on the lam
                index = after_index + 1
                continue
        joins_after = kind == "D" and after in ("D", "R", "C")
        form = {
            (True, True): "medial",
            (True, False): "final",
            (False, True): "initial",
            (False, False): "isolated",
        }[(joins_before, joins_after)]
        letter_forms = forms[char]
        out.append(letter_forms.get(form) or letter_forms.get("isolated", char))
        index += 1
    return "".join(out)


def keep_in_cells(art: str) -> str:
    """Text art whose Arabic letters stay in their cells in any terminal or editor.

    Terminals and editors that lay Arabic out themselves would reverse a run of
    Arabic letters, such as the ink of the ``letters`` style. Each line holding one
    is wrapped in a left-to-right override (U+202D ... U+202C), which they honour
    and which takes no space.
    """
    return "\n".join(
        f"\u202d{line}\u202c"
        if any(unicodedata.bidirectional(char) in ("R", "AL") for char in line)
        else line
        for line in art.split("\n")
    )


def terminal_shapes_arabic(environ: Mapping[str, str] | None = None) -> bool:
    """Guess from the environment whether the terminal joins and orders Arabic itself.

    True for Konsole, mlterm, VTE terminals (GNOME Terminal, Tilix, Terminator) from
    VTE 0.58, and macOS Terminal. Everything else is taken to draw characters as stored.
    """
    env = os.environ if environ is None else environ
    if "KONSOLE_VERSION" in env or "MLTERM" in env:
        return True
    if env.get("TERM_PROGRAM") == "Apple_Terminal":
        return True
    vte = env.get("VTE_VERSION", "")
    return vte.isdigit() and int(vte) >= 5800


def for_terminal(text: str, *, shaped_by_terminal: bool, direction: str | None = None) -> str:
    """``text`` as a terminal should be given it.

    Args:
        text: One line, as typed.
        shaped_by_terminal: Whether the terminal joins and orders Arabic itself (see
            :func:`terminal_shapes_arabic`). Then the text is returned as typed.
        direction: ``"rtl"`` or ``"ltr"`` for the line, or ``None`` to take it from the
            first letter with a direction.

    Returns:
        For a terminal that doesn't lay Arabic out: the line with its Arabic letters
        joined and everything in display order, tashkeel left out (terminals draw it
        apart from its letter). Otherwise ``text`` unchanged.
    """
    if shaped_by_terminal or not any(_joining(char) in ("D", "R") for char in text):
        return text
    joined = join_letters(strip_tashkeel(text))
    order = _logical_order(joined, direction)
    levels = _levels(joined, direction)
    if order is None or levels is None:  # not expected; show it unmirrored
        return str(get_display(joined, base_dir=_BIDI_BASE_DIR.get(direction or "")))
    # A bracket at an odd (right-to-left) level faces the other way once its run is reversed.
    return "".join(
        _MIRRORS.get(joined[index], joined[index]) if levels[index] % 2 else joined[index]
        for index in order
    )


def _levels(text: str, direction: str | None) -> list[int] | None:
    """The bidi embedding level of each character of ``text``, from python-bidi."""
    info = get_display(text, base_dir=_BIDI_BASE_DIR.get(direction or ""), debug=True)
    found = _LEVELS.search(info) if isinstance(info, str) else None
    if found is None:
        return None
    by_byte = [int(level) for level in _LEVEL.findall(found.group(1))]
    if len(by_byte) != len(text.encode("utf-8")):
        return None
    levels, offset = [], 0
    for char in text:
        levels.append(by_byte[offset])
        offset += len(char.encode("utf-8"))
    return levels
