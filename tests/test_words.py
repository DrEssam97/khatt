"""Word timings: reading recogniser results, grouping lines, caption steps."""

from __future__ import annotations

from collections import namedtuple
from itertools import pairwise
from types import SimpleNamespace

import pytest

import khatt
from khatt import CaptionStep, Word

SENTENCE = ["كل", "كلمة", "تضيء", "في", "وقتها"]


def _timed(texts=SENTENCE, start: float = 0.0, length: float = 0.4, gap: float = 0.1):
    words, at = [], start
    for text in texts:
        words.append(Word(text, at, at + length))
        at += length + gap
    return words


class TestWordsFromWhisper:
    def test_openai_whisper(self) -> None:
        result = {
            "text": " كل كلمة",
            "segments": [
                {
                    "words": [
                        {"word": " كل", "start": 0.0, "end": 0.3, "probability": 0.9},
                        {"word": " كلمة", "start": 0.3, "end": 0.8, "probability": 0.8},
                    ]
                },
                {"words": [{"word": " تضيء", "start": 1.0, "end": 1.4, "probability": 0.9}]},
            ],
        }
        assert khatt.words_from_whisper(result) == [
            Word("كل", 0.0, 0.3),
            Word("كلمة", 0.3, 0.8),
            Word("تضيء", 1.0, 1.4),
        ]

    def test_faster_whisper(self) -> None:
        FasterWord = namedtuple("FasterWord", "start end word probability")
        segments = iter(
            [SimpleNamespace(words=[FasterWord(0.0, 0.5, " مرحبا", 0.9)], text=" مرحبا")]
        )
        info = SimpleNamespace(language="ar")
        assert khatt.words_from_whisper((segments, info)) == [Word("مرحبا", 0.0, 0.5)]

    def test_faster_whisper_segments_only(self) -> None:
        segments = [SimpleNamespace(words=[SimpleNamespace(word="أهلا", start=1, end=2)])]
        assert khatt.words_from_whisper(segments) == [Word("أهلا", 1.0, 2.0)]

    def test_stable_ts(self) -> None:
        result = SimpleNamespace(
            segments=[SimpleNamespace(words=[SimpleNamespace(word=" سلام", start=0.2, end=0.6)])]
        )
        assert khatt.words_from_whisper(result) == [Word("سلام", 0.2, 0.6)]

    def test_whisperx_fills_missing_times(self) -> None:
        result = {
            "segments": [
                {
                    "words": [
                        {"word": "عندي", "start": 0.0, "end": 0.4, "score": 0.9},
                        {"word": "3"},  # whisperX can't align numbers
                        {"word": "كتب", "start": 0.9, "end": 1.3, "score": 0.9},
                    ]
                }
            ],
            "word_segments": [],
        }
        assert khatt.words_from_whisper(result) == [
            Word("عندي", 0.0, 0.4),
            Word("3", 0.4, 0.9),
            Word("كتب", 0.9, 1.3),
        ]

    def test_whisperx_word_segments(self) -> None:
        result = {"word_segments": [{"word": "نعم", "start": 0.1, "end": 0.3}]}
        assert khatt.words_from_whisper(result) == [Word("نعم", 0.1, 0.3)]

    def test_missing_end_and_last_word(self) -> None:
        result = {"segments": [{"words": [{"word": "أخيرا", "start": 2.0}]}]}
        assert khatt.words_from_whisper(result) == [Word("أخيرا", 2.0, 2.0)]

    def test_skips_empty_words(self) -> None:
        result = {"segments": [{"words": [{"word": " ", "start": 0, "end": 1}]}]}
        assert khatt.words_from_whisper(result) == []

    def test_no_word_timestamps(self) -> None:
        with pytest.raises(ValueError, match="word_timestamps=True"):
            khatt.words_from_whisper({"segments": [{"text": "كل", "start": 0, "end": 1}]})

    @pytest.mark.parametrize("result", [{"text": "كل"}, "كل", 5])
    def test_not_a_result(self, result: object) -> None:
        with pytest.raises(ValueError):
            khatt.words_from_whisper(result)


class TestGroupWords:
    def test_one_line(self) -> None:
        assert khatt.group_words(_timed()) == [_timed()]

    def test_max_chars(self) -> None:
        lines = khatt.group_words(_timed(), max_chars=10)
        assert [" ".join(w.text for w in line) for line in lines] == ["كل كلمة", "تضيء في", "وقتها"]
        assert all(len(" ".join(w.text for w in line)) <= 10 for line in lines)

    def test_long_word_alone(self) -> None:
        assert len(khatt.group_words([Word("استراتيجياتهم", 0, 1)], max_chars=4)) == 1

    def test_pause(self) -> None:
        words = [Word("قبل", 0, 0.5), Word("بعد", 2.0, 2.5)]
        assert len(khatt.group_words(words, max_gap=1.0)) == 2
        assert len(khatt.group_words(words, max_gap=2.0)) == 1

    @pytest.mark.parametrize("end", [".", "؟", "!", "?", "…"])
    def test_sentence_end(self, end: str) -> None:
        words = [Word(f"انتهى{end}", 0, 0.4), Word("ثم", 0.5, 0.9)]
        assert len(khatt.group_words(words)) == 2

    def test_bad_arguments(self) -> None:
        with pytest.raises(ValueError, match="max_chars"):
            khatt.group_words(_timed(), max_chars=0)
        with pytest.raises(ValueError, match="max_gap"):
            khatt.group_words(_timed(), max_gap=-1)


class TestCaptionSteps:
    def test_each_word_in_turn(self) -> None:
        words = _timed()
        steps = khatt.caption_steps(words)
        text = " ".join(SENTENCE)
        assert [step.text for step in steps] == [text] * 5
        assert [text[slice(*step.spans[0])] for step in steps] == SENTENCE
        assert steps[0].start == words[0].start
        # Each word stays lit until the next one starts; the line holds after the last.
        for step, word, after in zip(steps, words, [*words[1:], None], strict=True):
            assert step.start == pytest.approx(word.start)
            assert step.end == pytest.approx(after.start if after else word.end + 0.5)

    def test_spoken(self) -> None:
        steps = khatt.caption_steps(_timed(), highlight="spoken")
        text = " ".join(SENTENCE)
        assert [text[slice(*step.spans[0])] for step in steps] == [
            " ".join(SENTENCE[: n + 1]) for n in range(5)
        ]

    def test_next_line_cuts_the_hold(self) -> None:
        words = [Word("أول.", 0, 0.4), Word("ثان", 0.6, 1.0)]
        steps = khatt.caption_steps(words, hold=2.0)
        assert steps[0] == CaptionStep(0, 0.6, "أول.", ((0, 4),))
        assert steps[1].start == 0.6 and steps[1].end == pytest.approx(3.0)

    def test_no_overlaps(self) -> None:
        words = [Word("أ", 0, 1.0), Word("ب.", 0.5, 0.8), Word("ج", 0.2, 0.9)]
        steps = khatt.caption_steps(words)
        for before, after in pairwise(steps):
            assert before.end <= after.start
        assert all(step.end > step.start for step in steps)

    def test_no_words(self) -> None:
        assert khatt.caption_steps([]) == []

    def test_bad_arguments(self) -> None:
        with pytest.raises(ValueError, match="highlight"):
            khatt.caption_steps(_timed(), highlight="karaoke")
        with pytest.raises(ValueError, match="hold"):
            khatt.caption_steps(_timed(), hold=-1)

    def test_drawn_with_spans(self) -> None:
        step = khatt.caption_steps(_timed())[2]
        image = khatt.caption_image(
            step.text, font_size=48, color="white", spans=[(*step.spans[0], (255, 200, 0))]
        )
        data = image.tobytes()
        pixels = {tuple(data[i : i + 4]) for i in range(0, len(data), 4)}
        assert (255, 200, 0, 255) in pixels


# Synthetic verses (not Quran text) shaped like the real data: words, a pause
# sign standing alone, and timings in the Quran.com and QUL formats.
VERSES = {"1:1": "كلمة أولى ثانية", "1:2": "قول هنا ۛ ثم ذاك"}
SEGMENTS = {
    "1:1": [[1, 0, 400], [2, 400, 900], [3, 900, 1500]],
    "1:2": [[1, 1700, 2000], [2, 2000, 2600], [3, 2600, 3000], [4, 3000, 3500]],
}
EXPECTED = [
    Word("كلمة", 0.0, 0.4),
    Word("أولى", 0.4, 0.9),
    Word("ثانية", 0.9, 1.5),
    Word("۝١", 1.5, 1.5),
    Word("قول", 1.7, 2.0),
    Word("هنا ۛ", 2.0, 2.6),
    Word("ثم", 2.6, 3.0),
    Word("ذاك", 3.0, 3.5),
    Word("۝٢", 3.5, 3.5),
]


class TestWordsFromQuran:
    @pytest.mark.parametrize(
        "timings",
        [
            # Quran.com API v4: chapter_recitations/{reciter}/{chapter}?segments=true
            {
                "audio_file": {
                    "timestamps": [
                        {"verse_key": key, "timestamp_from": 0, "segments": segments}
                        for key, segments in SEGMENTS.items()
                    ]
                }
            },
            # Quran.com QDC: audio_files with verse_timings
            {
                "audio_files": [
                    {
                        "verse_timings": [
                            {"verse_key": key, "segments": segments}
                            for key, segments in SEGMENTS.items()
                        ]
                    }
                ]
            },
            # QUL, surah by surah
            {key: {"segments": segments, "duration_ms": 1} for key, segments in SEGMENTS.items()},
            # QUL, ayah by ayah
            [
                {"surah": 1, "ayah": int(key[2]), "segments": segments}
                for key, segments in SEGMENTS.items()
            ],
        ],
    )
    def test_formats(self, timings: object) -> None:
        assert khatt.words_from_quran(timings, VERSES) == EXPECTED

    def test_one_qul_ayah(self) -> None:
        words = khatt.words_from_quran({"surah": 1, "ayah": 1, "segments": SEGMENTS["1:1"]}, VERSES)
        assert words == EXPECTED[:4]

    def test_quran_com_verses_with_words(self) -> None:
        verses = {
            "verses": [
                {
                    "verse_key": "1:2",
                    "words": [
                        {"position": 2, "char_type_name": "word", "text_uthmani": "هنا ۛ"},
                        {"position": 1, "char_type_name": "word", "text_uthmani": "قول"},
                        {"position": 3, "char_type_name": "word", "text_uthmani": "ثم"},
                        {"position": 4, "char_type_name": "word", "text_uthmani": "ذاك"},
                        {"position": 5, "char_type_name": "end", "text_uthmani": "٢"},
                    ],
                },
                {"verse_key": "1:1", "text_uthmani": VERSES["1:1"]},
            ]
        }
        assert (
            khatt.words_from_quran({"1:2": {"segments": SEGMENTS["1:2"]}}, verses) == EXPECTED[4:]
        )
        assert (
            khatt.words_from_quran({"1:1": {"segments": SEGMENTS["1:1"]}}, verses) == EXPECTED[:4]
        )

    def test_word_lists(self) -> None:
        words = {"1:1": ["كلمة", "أولى", "ثانية"]}
        timings = {"1:1": {"segments": SEGMENTS["1:1"]}}
        assert khatt.words_from_quran(timings, words) == EXPECTED[:4]

    def test_placeholders_and_repeats(self) -> None:
        # Quran.com sends entries such as [1] with no times; a repeated word keeps its first time.
        timings = {"1:1": {"segments": [[1, 0, 400], [1], [3, 900, 1500], [1, 2000, 2400], [2]]}}
        words = khatt.words_from_quran(timings, VERSES, verse_numbers=False)
        assert words == [Word("كلمة", 0.0, 0.4), Word("أولى", 0.4, 0.9), Word("ثانية", 0.9, 1.5)]

    def test_verses_in_order(self) -> None:
        timings = {"1:2": {"segments": SEGMENTS["1:2"]}, "1:1": {"segments": SEGMENTS["1:1"]}}
        assert khatt.words_from_quran(timings, VERSES) == EXPECTED

    def test_big_verse_numbers(self) -> None:
        words = khatt.words_from_quran({"2:255": {"segments": [[1, 0, 100]]}}, {"2:255": "كلمة"})
        assert words[-1].text == "۝٢٥٥"

    def test_lines_end_with_the_verse(self) -> None:
        lines = khatt.group_words(EXPECTED, max_chars=100, max_gap=10)
        assert [len(line) for line in lines] == [4, 5]

    def test_verse_number_lit_after_the_verse(self) -> None:
        steps = khatt.caption_steps(EXPECTED[:4], hold=0.5)
        text = steps[-1].text
        assert text[slice(*steps[-1].spans[0])] == "۝١"
        assert steps[-1].start == 1.5 and steps[-1].end == 2.0
        assert text[slice(*steps[-2].spans[0])] == "ثانية"

    def test_missing_text(self) -> None:
        with pytest.raises(ValueError, match="no text for verse 1:3"):
            khatt.words_from_quran({"1:3": {"segments": [[1, 0, 1]]}}, VERSES)

    def test_timings_past_the_last_word(self) -> None:
        with pytest.raises(ValueError, match="has 3 words, but its timings go to word 4"):
            khatt.words_from_quran({"1:1": {"segments": [[4, 0, 1]]}}, VERSES)

    @pytest.mark.parametrize(
        ("timings", "text", "message"),
        [
            ("not timings", VERSES, "Quran.com or QUL"),
            ({"audio_file": {}}, VERSES, "Quran.com or QUL"),
            ([{"segments": []}], VERSES, "verse key and segments"),
            ({"1:1": {"segments": []}}, {"one": "كلمة"}, "verse keys"),
            ({"1:1": {"segments": []}}, [{"text": "كلمة"}], "verse_key"),
        ],
    )
    def test_bad_input(self, timings: object, text: object, message: str) -> None:
        with pytest.raises(ValueError, match=message):
            khatt.words_from_quran(timings, text)
