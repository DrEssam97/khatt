"""khatt.video.TextClip: a drop-in for moviepy's TextClip (needs the video extra)."""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

moviepy = pytest.importorskip("moviepy")
np = pytest.importorskip("numpy")

import khatt  # noqa: E402
from khatt.video import TextClip  # noqa: E402

TEXT = "بِسْمِ اللَّهِ\nKhatt 2026"


def test_is_an_image_clip_of_the_caption_image() -> None:
    clip = TextClip(text=TEXT, font_size=40, color="white", stroke_color="black", stroke_width=2)
    image = khatt.caption_image(
        TEXT, font_size=40, color="white", stroke_color="black", stroke_width=2
    )
    assert isinstance(clip, moviepy.ImageClip)
    assert tuple(clip.size) == image.size
    rgba = np.asarray(image)
    assert np.array_equal(clip.get_frame(0), rgba[:, :, :3])
    assert np.allclose(clip.mask.get_frame(0), rgba[:, :, 3] / 255)


def test_takes_moviepys_arguments_in_moviepys_order() -> None:
    theirs = inspect.signature(moviepy.TextClip.__init__).parameters
    ours = inspect.signature(TextClip.__init__).parameters
    assert list(ours)[: len(theirs)] == list(theirs)
    changed = {"font", "text_align"}  # documented: "amiri", and by direction
    for name, parameter in theirs.items():
        if name not in changed:
            assert ours[name].default == parameter.default, name


def test_positional_font_and_text_like_moviepy() -> None:
    clip = TextClip("amiri", "مرحبا", None, 40)
    assert clip.text == "مرحبا"


def test_frames_are_writeable_like_moviepys() -> None:
    # Effects may edit a frame in place.
    clip = TextClip(text="مرحبا", font_size=40)
    assert clip.get_frame(0).flags.writeable
    edited = clip.image_transform(lambda frame: (frame.__setitem__((0, 0), 0), frame)[1])
    assert tuple(edited.get_frame(0)[0, 0]) == (0, 0, 0)


def test_attributes_and_duration() -> None:
    clip = TextClip(text="مرحبا", font_size=40, color="white", stroke_color="red", duration=2.5)
    assert (clip.text, clip.color, clip.stroke_color) == ("مرحبا", "white", "red")
    assert clip.duration == 2.5


def test_opaque_clip_has_no_mask() -> None:
    clip = TextClip(text="مرحبا", font_size=40, bg_color="navy", transparent=False)
    assert clip.mask is None
    assert tuple(clip.get_frame(0)[0, 0]) == (0, 0, 128)


def test_reads_the_text_file_as_utf8(tmp_path: Path) -> None:
    source = tmp_path / "caption.txt"
    source.write_bytes("مرحبا بالعالم\n".encode())
    clip = TextClip(filename=source, font_size=40)
    assert clip.text == "مرحبا بالعالم"


def test_needs_text() -> None:
    with pytest.raises(ValueError, match="text"):
        TextClip(font_size=40)


def test_passes_fallback_fonts_to_the_caption_image() -> None:
    text = "مرحبا Жук"
    clip = TextClip(text=text, font="amiri", font_size=40, fallback_fonts=["rubik"])
    image = khatt.caption_image(text, font="amiri", font_size=40, fallback_fonts=["rubik"])
    assert np.array_equal(clip.get_frame(0), np.asarray(image)[:, :, :3])


def test_composites_into_a_video() -> None:
    background = moviepy.ColorClip((640, 360), color=(30, 30, 30), duration=1)
    caption = (
        TextClip(text=TEXT, font_size=36, color="white", stroke_color="black", stroke_width=2)
        .with_duration(1)
        .with_position(("center", "bottom"))
    )
    frame = moviepy.CompositeVideoClip([background, caption]).get_frame(0.5)
    assert frame.shape == (360, 640, 3)
    assert (frame == 255).all(axis=2).any()  # white text was composited


class TestWordCaptions:
    GOLD = (255, 200, 0)
    WORDS = tuple(
        khatt.Word(text, n * 0.5, n * 0.5 + 0.4) for n, text in enumerate(["كل", "كلمة", "تضيء"])
    )

    def _lit(self, frame) -> tuple[float, float] | None:
        """Mean x and y of the highlighted pixels in a frame."""
        ys, xs = np.nonzero(np.all(frame == self.GOLD, axis=-1))
        return None if len(xs) == 0 else (xs.mean(), ys.mean())

    def test_each_word_lights_up_in_turn(self) -> None:
        from khatt.video import word_captions

        clip = word_captions(self.WORDS, (640, 360), highlight_color=self.GOLD)
        assert tuple(clip.size) == (640, 360)
        assert clip.duration == pytest.approx(self.WORDS[-1].end + 0.5)
        lit = [self._lit(clip.get_frame(word.start + 0.2)) for word in self.WORDS]
        assert all(spot is not None for spot in lit)
        xs = [spot[0] for spot in lit]
        assert xs[0] > xs[1] > xs[2]  # right to left
        assert all(spot[1] > 360 * 0.6 for spot in lit)  # near the bottom
        assert clip.mask.get_frame(0.2).max() > 0.99

    def test_spoken_keeps_earlier_words(self) -> None:
        from khatt.video import word_captions

        clip = word_captions(self.WORDS, (640, 360), highlight_color=self.GOLD, highlight="spoken")
        first = np.all(clip.get_frame(0.2) == self.GOLD, axis=-1).sum()
        last = np.all(clip.get_frame(1.2) == self.GOLD, axis=-1).sum()
        assert last > first * 2

    def test_options(self) -> None:
        from khatt.video import word_captions

        clip = word_captions(
            self.WORDS,
            (320, 180),
            font="cairo",
            font_size=20,
            stroke_color=None,
            bg_color="black",
            bottom=0.0,
        )
        assert clip.get_frame(0.2).any()

    def test_no_words(self) -> None:
        from khatt.video import word_captions

        with pytest.raises(ValueError, match="no words"):
            word_captions([], (640, 360))


QURAN_VERSES = {"1:1": "كلمة أولى ثانية", "1:2": "قول هنا ۛ ثم ذاك"}
QURAN_TIMINGS = {
    "1:1": {"segments": [[1, 0, 400], [2, 400, 900], [3, 900, 1500]]},
    "1:2": {"segments": [[1, 1700, 2000], [2, 2000, 2600], [3, 2600, 3000], [4, 3000, 3500]]},
}


class TestQuranCaptions:
    GOLD = (255, 200, 0)

    def test_one_verse_at_a_time(self) -> None:
        from khatt.video import quran_captions

        words = khatt.words_from_quran(QURAN_TIMINGS, QURAN_VERSES)
        clip = quran_captions(words, (640, 360), highlight_color=self.GOLD)
        assert tuple(clip.size) == (640, 360)
        assert clip.duration == pytest.approx(3.5 + 1.5)
        for t in (0.2, 1.2, 2.2):
            assert np.all(clip.get_frame(t) == self.GOLD, axis=-1).any(), t
        # The first verse stays up, its medallion lit, until the second starts.
        assert np.all(clip.get_frame(1.6) == self.GOLD, axis=-1).any()

    def test_wraps_long_verses_with_room_for_marks(self) -> None:
        from khatt.video import quran_captions, word_captions

        verse = " ".join(["كَلِمَةٌ"] * 12)
        words = khatt.words_from_quran(
            {"1:1": {"segments": [[n + 1, n * 300, n * 300 + 250] for n in range(12)]}},
            {"1:1": verse},
            verse_numbers=False,
        )
        quran = quran_captions(words, (480, 600), font_size=40, max_chars=200)
        plain = word_captions(words, (480, 600), font_size=40, max_chars=200)
        ink = [np.nonzero(clip.mask.get_frame(0.1).max(axis=1))[0] for clip in (quran, plain)]
        assert ink[0][-1] - ink[0][0] > ink[1][-1] - ink[1][0]  # wider line spacing
