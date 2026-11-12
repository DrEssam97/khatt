"""put_text: shaped Arabic on NumPy arrays, OpenCV style."""

from __future__ import annotations

import pytest
from PIL import Image

import khatt

np = pytest.importorskip("numpy")

TEXT = "مرحبا بالعالم"


def _ink(array) -> tuple[int, int, int, int] | None:
    """Box of the pixels that changed from the blank background."""
    changed = np.any(array != 0, axis=-1) if array.ndim == 3 else array != 0
    ys, xs = np.nonzero(changed)
    if len(xs) == 0:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def test_bgr_colour_by_default() -> None:
    frame = np.zeros((100, 400, 3), np.uint8)
    result = khatt.put_text(frame, TEXT, (10, 70), size_px=40, color=(255, 0, 0))  # blue
    assert result is frame
    _, xs = np.nonzero(frame[..., 0] == 255)
    assert len(xs) > 100
    assert frame[..., 2].max() == 0  # no red anywhere


def test_rgb_order() -> None:
    frame = np.zeros((100, 400, 3), np.uint8)
    khatt.put_text(frame, TEXT, (10, 70), size_px=40, color=(255, 0, 0), channels="rgb")  # red
    assert frame[..., 0].max() == 255 and frame[..., 2].max() == 0


def test_same_pixels_as_draw_text() -> None:
    frame = np.zeros((100, 400, 3), np.uint8)
    khatt.put_text(frame, TEXT, (10, 70), size_px=40, color=(0, 200, 255), channels="rgb")
    image = Image.new("RGB", (400, 100), "black")
    khatt.draw_text(image, (10, 70), TEXT, size_px=40, fill=(0, 200, 255), anchor="ls")
    assert np.array_equal(frame, np.asarray(image))


def test_origin_is_the_baseline() -> None:
    frame = np.zeros((120, 400, 3), np.uint8)
    khatt.put_text(frame, "خط", (10, 80), size_px=60)
    box = _ink(frame)
    assert box is not None
    assert box[1] < 80 and box[0] >= 9


def test_grayscale_and_alpha() -> None:
    gray = np.zeros((100, 400), np.uint8)
    khatt.put_text(gray, TEXT, (10, 70), size_px=40, color=200)
    assert gray.max() == 200
    rgba = np.zeros((100, 400, 4), np.uint8)
    khatt.put_text(rgba, TEXT, (10, 70), size_px=40, color=(0, 0, 255, 255))
    assert rgba[..., 3].max() == 255 and rgba[..., 2].max() == 255


def test_only_the_region_under_the_text_changes() -> None:
    frame = np.full((200, 600, 3), 7, np.uint8)
    khatt.put_text(frame, TEXT, (300, 120), size_px=30)
    left, top, right, bottom = khatt.text_bbox(TEXT, xy=(300, 120), size_px=30, anchor="ls")
    outside = frame.copy()
    outside[top:bottom, left:right] = 7
    assert (outside == 7).all()


def test_text_off_the_image() -> None:
    frame = np.zeros((50, 50, 3), np.uint8)
    khatt.put_text(frame, TEXT, (500, 500), size_px=30)
    assert not frame.any()
    khatt.put_text(frame, TEXT, (-60, 40), size_px=30)  # partly off: clipped, no error
    assert frame.any()


def test_outline() -> None:
    frame = np.zeros((100, 400, 3), np.uint8)
    khatt.put_text(
        frame,
        TEXT,
        (20, 70),
        size_px=40,
        color=(255, 255, 255),
        stroke_width=3,
        stroke_color=(0, 0, 255),
    )
    assert (frame[..., 2] == 255).any() and (frame.sum(axis=-1) == 765).any()


@pytest.mark.parametrize(
    ("image", "message"),
    [
        (np.zeros((10, 10, 3), np.float32), "uint8"),
        (np.zeros((10, 10, 2), np.uint8), "shape"),
        ([[0]], "uint8"),
    ],
)
def test_bad_images(image, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        khatt.put_text(image, TEXT, (0, 0))


def test_bad_colours_and_channels() -> None:
    with pytest.raises(ValueError, match="channels"):
        khatt.put_text(np.zeros((10, 10, 3), np.uint8), TEXT, (0, 0), channels="hsv")
    with pytest.raises(ValueError, match="one colour value"):
        khatt.put_text(np.zeros((50, 200), np.uint8), TEXT, (0, 40), color=(1, 2, 3))
    with pytest.raises(ValueError, match="3 or 4 values"):
        khatt.put_text(np.zeros((50, 200, 3), np.uint8), TEXT, (0, 40), color=(1, 2))
