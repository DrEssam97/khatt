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
