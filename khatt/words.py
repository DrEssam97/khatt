"""Word timings for captions where each word lights up as it is spoken.

Speech recognisers give each word a start and end time. These helpers read
them, group the words into caption lines and work out what the caption shows
at every moment: the line, and which words in it are highlighted. Draw each
step with :func:`khatt.caption_image` (its ``spans`` keep the letters joined
across the highlight), or let :func:`khatt.video.word_captions` make the whole
moviepy clip.

    import khatt

    words = khatt.words_from_whisper(result)  # openai-whisper, faster-whisper, whisperX
    for step in khatt.caption_steps(words):
        print(step.start, step.end, step.text, step.spans)
"""

from __future__ import annotations

import math
import numbers
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

_HIGHLIGHTS = ("word", "spoken")
_SENTENCE_ENDS = (".", "!", "?", "؟", "۔", "…")


@dataclass(frozen=True)
class Word:
    """One spoken word and when it is said, in seconds."""

    text: str
    start: float
    end: float


@dataclass(frozen=True)
class CaptionStep:
    """What a word-timed caption shows from ``start`` to ``end`` (seconds).

    ``text`` is the caption line; ``spans`` are the ``(start, end)``
    character ranges of ``text`` to highlight, ready for the ``spans`` of
    :func:`khatt.caption_image` or :func:`khatt.draw_text` with a colour
    added.
    """

    start: float
    end: float
    text: str
    spans: tuple[tuple[int, int], ...]


def _field(item: Any, *names: str) -> Any:
    for name in names:
        value = item.get(name) if isinstance(item, Mapping) else getattr(item, name, None)
        if value is not None:
            return value
    return None


def _seconds(value: Any) -> float | None:
    if isinstance(value, numbers.Real) and not isinstance(value, bool) and math.isfinite(value):
        return float(value)
    return None


def _segments(result: Any) -> Iterable[Any]:
    """The segments of any of the supported recogniser results."""
    if isinstance(result, Mapping):
        if result.get("segments") is not None:
            return result["segments"]
        if result.get("word_segments") is not None:  # whisperX, words only
            return [{"words": result["word_segments"]}]
        raise ValueError("expected a transcription result with 'segments'")
    segments = getattr(result, "segments", None)
    if segments is not None:  # stable-ts
        return segments
    if isinstance(result, tuple) and len(result) == 2 and not isinstance(result[0], str):
        return result[0]  # faster-whisper: (segments, info)
    if isinstance(result, Iterable) and not isinstance(result, str):
        return result
    raise ValueError(f"can't read word timings from {type(result).__name__}")


def words_from_whisper(result: Any) -> list[Word]:
    """The timed words of a speech recogniser's result.

    Reads the results of openai-whisper and stable-ts (``transcribe``),
    faster-whisper (the ``(segments, info)`` pair, or just the segments) and
    whisperX (after ``align``), always with word timestamps turned on
    (``word_timestamps=True`` for whisper and faster-whisper). Words come
    back in order with spaces trimmed. A word with no timing of its own, as
    whisperX leaves numbers, gets the gap around it.

    Raises:
        ValueError: if the result has no word timings.
    """
    raw: list[tuple[str, float | None, float | None]] = []
    for segment in _segments(result):
        words = _field(segment, "words")
        if words is None:
            raise ValueError(
                "the result has no word timings: transcribe with word_timestamps=True "
                "(whisperX: run align first)"
            )
        for word in words:
            text = str(_field(word, "word", "text") or "").strip()
            if text:
                raw.append((text, _seconds(_field(word, "start")), _seconds(_field(word, "end"))))
    timed: list[Word] = []
    for index, (text, start, end) in enumerate(raw):
        if start is None:
            start = timed[-1].end if timed else 0.0
        if end is None:
            later = (s for _, s, _ in raw[index + 1 :] if s is not None)
            end = max(start, next(later, start))
        timed.append(Word(text, start, max(start, end)))
    return timed


def group_words(
    words: Sequence[Word], *, max_chars: int = 42, max_gap: float = 1.0
) -> list[list[Word]]:
    """Split timed words into caption lines.

    A new line starts when the next word would make the line longer than
    ``max_chars`` characters, after a pause of more than ``max_gap``
    seconds, or after a word that ends a sentence. A word longer than
    ``max_chars`` still gets a line of its own.
    """
    if max_chars < 1:
        raise ValueError(f"max_chars must be at least 1, got {max_chars}")
    if max_gap < 0:
        raise ValueError(f"max_gap can't be negative, got {max_gap}")
    lines: list[list[Word]] = []
    for word in words:
        line = lines[-1] if lines else None
        if (
            line is None
            or len(" ".join(w.text for w in line)) + 1 + len(word.text) > max_chars
            or word.start - line[-1].end > max_gap
            or line[-1].text.endswith(_SENTENCE_ENDS)
        ):
            lines.append([word])
        else:
            line.append(word)
    return lines


def caption_steps(
    words: Sequence[Word],
    *,
    max_chars: int = 42,
    max_gap: float = 1.0,
    hold: float = 0.5,
    highlight: str = "word",
) -> list[CaptionStep]:
    """What a word-timed caption shows, step by step.

    Words are grouped into lines by :func:`group_words`. A line shows from
    its first word's start until the next line starts, but at most ``hold``
    seconds after its last word ends. Within it, each word stays highlighted
    from its start until the next word's start.

    Args:
        words: Timed words, for example from :func:`words_from_whisper`.
        max_chars: Longest caption line, in characters.
        max_gap: A pause longer than this many seconds starts a new line.
        hold: Seconds a line stays up after its last word.
        highlight: ``"word"`` highlights only the word being said;
            ``"spoken"`` highlights every word of the line said so far.

    Returns:
        Steps in time order, without overlaps.
    """
    if highlight not in _HIGHLIGHTS:
        raise ValueError(f"highlight must be one of {', '.join(_HIGHLIGHTS)}, got {highlight!r}")
    if hold < 0:
        raise ValueError(f"hold can't be negative, got {hold}")
    lines = group_words(words, max_chars=max_chars, max_gap=max_gap)
    steps: list[CaptionStep] = []
    for number, line in enumerate(lines):
        text = " ".join(word.text for word in line)
        ranges, offset = [], 0
        for word in line:
            ranges.append((offset, offset + len(word.text)))
            offset += len(word.text) + 1
        line_end = line[-1].end + hold
        if number + 1 < len(lines):
            line_end = min(line_end, lines[number + 1][0].start)
        for index, word in enumerate(line):
            start = word.start if index else line[0].start
            end = line[index + 1].start if index + 1 < len(line) else line_end
            if steps:
                start = max(start, steps[-1].end)
            if end <= start:
                continue
            spans = (ranges[index],) if highlight == "word" else ((0, ranges[index][1]),)
            steps.append(CaptionStep(start, end, text, spans))
    return steps
