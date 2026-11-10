"""Kashida: stretching Arabic words with tatweel (``ـ``) where letters join.

A tatweel can only go between two letters that join, and never inside
lam-alef, which it would break apart. Calligrams use it to fill a line, and
zakhrafa to decorate a name.
"""

from __future__ import annotations

import unicodedata

TATWEEL = "\u0640"

MOST_KASHIDA = 3
"""Tatweels at any one point of a word; more looks drawn out rather than written."""

# Letters that never join the letter after them, so no kashida can follow them.
_NO_JOIN_AFTER = frozenset("ءآأؤإاةدذرزوٱژڈڑۀےۓ")
_ALEFS = frozenset("آأإاٱ")


def _is_letter(ch: str) -> bool:
    return unicodedata.bidirectional(ch) == "AL" and unicodedata.category(ch) == "Lo"


def kashida_points(word: str) -> list[int]:
    """Where a tatweel can go in ``word``: positions to insert it before.

    Only between two letters that join, after the first one's marks, and
    never inside lam-alef, which a tatweel would break apart.
    """
    points = []
    for index, ch in enumerate(word):
        if not _is_letter(ch) or ch in _NO_JOIN_AFTER:
            continue
        after = index + 1
        while after < len(word) and unicodedata.combining(word[after]):
            after += 1
        if after == len(word) or not _is_letter(word[after]):
            continue
        if ch == "ل" and word[after] in _ALEFS:
            continue
        points.append(after)
    return points


def stretch(line: str, count: int) -> str:
    """``line`` with ``count`` tatweels spread evenly over its words.

    Fewer are added when the words have too few places for them.
    """
    words = line.split(" ")
    spots = [(n, point) for n, word in enumerate(words) for point in kashida_points(word)]
    if not spots or count <= 0:
        return line
    count = min(count, len(spots) * MOST_KASHIDA)
    extra = {spot: count // len(spots) for spot in spots}
    # The rest go to every few spots across the line, not all at its start.
    rest = count % len(spots)
    for n in range(rest):
        extra[spots[n * len(spots) // rest]] += 1
    stretched = []
    for n, word in enumerate(words):
        pieces, last = [], 0
        for point in kashida_points(word):
            pieces += [word[last:point], TATWEEL * extra[(n, point)]]
            last = point
        stretched.append("".join(pieces) + word[last:])
    return " ".join(stretched)
