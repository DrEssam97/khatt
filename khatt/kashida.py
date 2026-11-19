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


_SEEN_LIKE = frozenset("سشصض")
"""Letters whose long joining stroke takes a kashida best of all."""


def justify_point(word: str) -> int | None:
    """The one place a justified line stretches ``word``, or ``None`` to leave it be.

    After a seen, sheen, sad or dad if the word has one, else before its last joined
    letter, as in printed Naskh. Short words (one or two letters) and the name of God,
    whose ligature a tatweel would break, are left alone.
    """
    letters = [ch for ch in word if _is_letter(ch)]
    if len(letters) < 3 or "لله" in "".join(letters):
        return None
    points = kashida_points(word)
    if not points:
        return None
    for point in points:
        before = point - 1
        while before > 0 and unicodedata.combining(word[before]):
            before -= 1
        if word[before] in _SEEN_LIKE:
            return point
    return points[-1]


def justify(line: str, count: int) -> str:
    """``line`` with up to ``count`` tatweels, at one :func:`justify_point` per word.

    The tatweels are shared out evenly; no word gets more than :data:`MOST_KASHIDA`,
    so fewer are added when the line has too few words to take them.
    """
    words = line.split(" ")
    spots = [
        (n, point) for n, word in enumerate(words) if (point := justify_point(word)) is not None
    ]
    if not spots or count <= 0:
        return line
    count = min(count, len(spots) * MOST_KASHIDA)
    extra = [count // len(spots)] * len(spots)
    # The rest go to every few words across the line, not all at its start.
    rest = count % len(spots)
    for n in range(rest):
        extra[n * len(spots) // rest] += 1
    for (n, point), add in zip(spots, extra, strict=True):
        words[n] = words[n][:point] + TATWEEL * add + words[n][point:]
    return " ".join(words)


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
