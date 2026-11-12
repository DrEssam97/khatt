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

For recitations, :func:`words_from_quran` pairs the Quran.com or Tarteel QUL
word timings with the verses' text.
"""

from __future__ import annotations

import math
import numbers
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

_HIGHLIGHTS = ("word", "spoken")
_SENTENCE_ENDS = (".", "!", "?", "؟", "۔", "…")
_END_OF_AYAH = "\u06dd"
"""Followed by the verse number, fonts such as Amiri draw the verse medallion."""
_ARABIC_DIGITS = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")


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
    return _fill_times(raw)


def _fill_times(raw: Sequence[tuple[str, float | None, float | None]]) -> list[Word]:
    """Words, with a missing start or end taken from the gap around the word."""
    timed: list[Word] = []
    for index, (text, start, end) in enumerate(raw):
        if start is None:
            start = timed[-1].end if timed else 0.0
        if end is None:
            later = (s for _, s, _ in raw[index + 1 :] if s is not None)
            end = max(start, next(later, start))
        timed.append(Word(text, start, max(start, end)))
    return timed


def _verse_key(key: Any) -> tuple[int, int] | None:
    """``"2:255"`` as ``(2, 255)``, or ``None`` if it isn't a verse key."""
    parts = str(key).split(":")
    if len(parts) == 2 and all(part.strip().isdigit() for part in parts):
        return int(parts[0]), int(parts[1])
    return None


def _verse_timings(timings: Any) -> list[tuple[tuple[int, int], Any]]:
    """``((surah, ayah), segments)`` for each verse, in order, from any supported format."""
    entries: Any = timings
    if isinstance(timings, Mapping):
        if "audio_files" in timings:  # Quran.com QDC: a list of files
            files = timings["audio_files"] or [{}]
            entries = _field(files[0], "verse_timings", "timestamps")
        elif "audio_file" in timings:  # Quran.com API v4
            entries = _field(timings["audio_file"], "timestamps", "verse_timings")
        elif _field(timings, "timestamps", "verse_timings") is not None:
            entries = _field(timings, "timestamps", "verse_timings")
        elif "segments" in timings:  # QUL, one ayah
            entries = [timings]
        else:  # QUL, surah by surah: {"1:1": {"segments": ...}}
            entries = [{"verse_key": key, **value} for key, value in timings.items()]
    if entries is None or isinstance(entries, (str, bytes)) or not isinstance(entries, Iterable):
        raise ValueError("expected Quran.com or QUL word timings with 'segments'")
    verses = []
    for entry in entries:
        key = _verse_key(_field(entry, "verse_key"))
        if key is None and _field(entry, "surah") is not None:
            key = _verse_key(f"{_field(entry, 'surah')}:{_field(entry, 'ayah')}")
        segments = _field(entry, "segments")
        if key is None or segments is None:
            raise ValueError(f"a verse timing needs a verse key and segments, got {entry!r}")
        verses.append((key, segments))
    return sorted(verses, key=lambda verse: verse[0])


def _tokens(verse: str) -> list[str]:
    """A verse's words in order; marks standing alone (pause signs) join the word before."""
    tokens: list[str] = []
    for token in verse.split():
        if tokens and not any(ch.isalpha() for ch in token):
            tokens[-1] = f"{tokens[-1]} {token}"
        else:
            tokens.append(token)
    return tokens


def _verse_words(text: Any) -> dict[tuple[int, int], list[str]]:
    """Each verse's words by position, from any supported text format."""
    if isinstance(text, Mapping) and "verses" in text:  # Quran.com verses response
        text = text["verses"]
    words: dict[tuple[int, int], list[str]] = {}
    if isinstance(text, Mapping):
        for key, value in text.items():
            verse = _verse_key(key)
            if verse is None:
                raise ValueError(f"expected verse keys such as '1:1', got {key!r}")
            words[verse] = _tokens(value) if isinstance(value, str) else [str(w) for w in value]
        return words
    for entry in text:
        verse = _verse_key(_field(entry, "verse_key"))
        if verse is None:
            raise ValueError(f"a verse needs a verse_key, got {entry!r}")
        listed = _field(entry, "words")
        if listed is None:
            words[verse] = _tokens(str(_field(entry, "text_uthmani", "text") or ""))
            continue
        ordered = sorted(
            (w for w in listed if _field(w, "char_type_name") in (None, "word")),
            key=lambda w: _field(w, "position") or 0,
        )
        words[verse] = [str(_field(w, "text_uthmani", "text") or "").strip() for w in ordered]
    return words


def words_from_quran(timings: Any, text: Any, *, verse_numbers: bool = True) -> list[Word]:
    """The timed words of a Quran recitation, from its word timings and the verses' text.

    Timings give each word of a verse as ``[position, start_ms, end_ms]``.
    This reads the Quran.com API (``chapter_recitations/{reciter}/{chapter}``
    with ``segments=true``, or the QDC ``audio_files`` with ``verse_timings``)
    and Tarteel QUL files (surah by surah, keyed ``"1:1"``, or ayah by ayah
    with ``surah`` and ``ayah``).

    The text comes from you, so it is always the edition you chose: a
    mapping of verse keys to verse text (``{"1:1": "بِسْمِ ٱللَّهِ ..."}``)
    or to its words, or Quran.com's ``verses`` response with ``words``. A
    pause sign standing alone, such as ``ۛ``, stays with the word before it,
    as in Quran.com's word lists. Use the text edition the timings were made
    for, so the word positions match.

    Args:
        timings: Word timings, in one of the formats above.
        text: The verses, in one of the formats above.
        verse_numbers: End each verse with its number in an end-of-ayah
            sign (``۝`` and the number), which fonts such as Amiri draw as
            the verse medallion. It is lit after the verse's last word.

    Returns:
        The words in order, in seconds. A word with no timing (entries such
        as ``[2]`` are skipped) gets the gap around it.

    Raises:
        ValueError: if a verse's text is missing, or its timings point past
            its last word.
    """
    verses = _verse_words(text)
    raw: list[tuple[str, float | None, float | None]] = []
    for (surah, ayah), segments in _verse_timings(timings):
        tokens = verses.get((surah, ayah))
        if tokens is None:
            raise ValueError(f"no text for verse {surah}:{ayah}")
        times: dict[int, tuple[float, float]] = {}
        for segment in segments:
            numbers_only = [_seconds(value) for value in list(segment)[:3]]
            if len(numbers_only) < 3 or None in numbers_only:
                continue  # a placeholder such as [2], with no times
            position, start_ms, end_ms = (value or 0.0 for value in numbers_only)
            if position > len(tokens):
                raise ValueError(
                    f"verse {surah}:{ayah} has {len(tokens)} words, but its timings go to "
                    f"word {int(position)}: use the text edition the timings were made for"
                )
            times.setdefault(int(position), (start_ms / 1000, end_ms / 1000))
        for position, token in enumerate(tokens, start=1):
            start, end = times.get(position, (None, None))
            raw.append((token, start, end))
        if verse_numbers:
            raw.append((f"{_END_OF_AYAH}{str(ayah).translate(_ARABIC_DIGITS)}", None, None))
    words = _fill_times(raw)
    if verse_numbers:
        # A verse number takes no time of its own: it starts as its verse ends.
        words = [
            Word(word.text, word.start, word.start) if word.text.startswith(_END_OF_AYAH) else word
            for word in words
        ]
    return words


def group_words(
    words: Sequence[Word], *, max_chars: int = 42, max_gap: float = 1.0
) -> list[list[Word]]:
    """Split timed words into caption lines.

    A new line starts when the next word would make the line longer than
    ``max_chars`` characters, after a pause of more than ``max_gap``
    seconds, or after a word that ends a sentence or a verse (its number
    from :func:`words_from_quran`). A word longer than ``max_chars`` still
    gets a line of its own.
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
            or line[-1].text.startswith(_END_OF_AYAH)
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
