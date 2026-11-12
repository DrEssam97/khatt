"""Draw shaped Arabic onto NumPy image arrays, such as OpenCV frames.

OpenCV's ``cv2.putText`` draws with Hershey stroke fonts that have no Arabic
letters at all. :func:`put_text` takes the same order of arguments (array,
text, origin) and BGR colours by default, and draws through khatt::

    import cv2
    import khatt

    frame = cv2.imread("frame.png")
    khatt.put_text(frame, "مرحبا", (40, 80), size_px=48, color=(0, 255, 255))
    cv2.imwrite("out.png", frame)

NumPy is not a dependency of khatt; this module only needs it when called.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from PIL import Image

from khatt.draw import draw_text, text_bbox
from khatt.fonts import Font

_ORDERS = ("bgr", "rgb")


def _fill(color: Any, channels: int, order: str) -> Any:
    """``color``, given in the array's channel order, as an RGB(A) tuple for Pillow."""
    values = (color,) if isinstance(color, int) else tuple(int(v) for v in color)
    if channels == 1:
        if len(values) != 1:
            raise ValueError(f"a one-channel image takes one colour value, got {color!r}")
        return (values[0],) * 3
    if len(values) not in (3, 4):
        raise ValueError(f"color must have 3 or 4 values in {order} order, got {color!r}")
    rgb = values[:3][::-1] if order == "bgr" else values[:3]
    return (*rgb, *values[3:])


def put_text(
    image: Any,
    text: str,
    org: tuple[float, float],
    *,
    font: Font = "amiri",
    size_px: int = 32,
    color: Any = (255, 255, 255),
    channels: str = "bgr",
    anchor: str = "ls",
    align: str | None = None,
    max_width: int | None = None,
    line_spacing: float | None = None,
    stroke_width: float = 0,
    stroke_color: Any = None,
    keep_tashkeel: bool = True,
    fallback_fonts: Font | Sequence[Font] = (),
) -> Any:
    """Draw shaped text onto a NumPy image (in place) and return it.

    The arguments follow ``cv2.putText(img, text, org, ...)``: by default
    ``org`` is the left end of the text's baseline and colours are in BGR
    order. Only the part of the image under the text is touched.

    Args:
        image: A ``uint8`` array: ``(height, width)`` grayscale, or
            ``(height, width, 3)`` or ``(height, width, 4)`` colour.
        text: The text, as typed; line breaks start new lines.
        org: Where the ``anchor`` point of the text goes, as ``(x, y)``.
        font: A bundled font name (see :func:`khatt.list_fonts`) or a font
            file path.
        size_px: Font size in pixels per em.
        color: Text colour in the image's channel order: one value for
            grayscale, three for colour, four to set alpha too.
        channels: ``"bgr"`` (OpenCV, the default) or ``"rgb"`` (Pillow,
            Matplotlib and most other libraries); a fourth channel is alpha.
        anchor: As in :func:`khatt.draw_text`; the default ``"ls"`` (left
            end of the baseline) is OpenCV's ``org``.
        align: Alignment of the lines of a multi-line text, as in
            :func:`khatt.draw_text`.
        max_width: Wrap lines at spaces to this many pixels.
        line_spacing: Distance between baselines, in multiples of the size.
        stroke_width: Width in pixels of an outline around the text.
        stroke_color: Outline colour, in the same order as ``color``;
            default: ``color``.
        keep_tashkeel: Keep Arabic diacritics (``False`` strips them).
        fallback_fonts: Fonts for characters ``font`` has no glyph for.

    Returns:
        ``image``, drawn on.

    Raises:
        ValueError: if ``image`` is not a ``uint8`` array of a supported shape.
    """
    import numpy as np

    if not isinstance(image, np.ndarray) or image.dtype != np.uint8:
        raise ValueError("put_text draws on a uint8 NumPy array")
    if channels not in _ORDERS:
        raise ValueError(f"channels must be 'bgr' or 'rgb', got {channels!r}")
    if image.ndim == 2:
        count = 1
    elif image.ndim == 3 and image.shape[2] in (3, 4):
        count = image.shape[2]
    else:
        raise ValueError(f"expected a (height, width[, 3 or 4]) array, got shape {image.shape}")
    fill = _fill(color, count, channels)
    outline = None if stroke_color is None else _fill(stroke_color, count, channels)
    options: dict[str, Any] = {
        "font": font,
        "size_px": size_px,
        "anchor": anchor,
        "align": align,
        "max_width": max_width,
        "line_spacing": line_spacing,
        "keep_tashkeel": keep_tashkeel,
        "stroke_width": stroke_width,
        "fallback_fonts": fallback_fonts,
    }
    left, top, right, bottom = text_bbox(text, xy=org, **options)
    height, width = image.shape[:2]
    x0, y0 = max(left, 0), max(top, 0)
    x1, y1 = min(right, width), min(bottom, height)
    if x0 >= x1 or y0 >= y1:
        return image  # nothing to draw, or all of it off the image
    region = image[y0:y1, x0:x1]
    if count == 1:
        canvas = Image.fromarray(np.stack([region] * 3, axis=-1), "RGB")
    else:
        rgb = region[..., 2::-1] if channels == "bgr" else region[..., :3]
        pixels = np.dstack([rgb, region[..., 3]]) if count == 4 else rgb
        canvas = Image.fromarray(np.ascontiguousarray(pixels), "RGBA" if count == 4 else "RGB")
    draw_text(
        canvas,
        (org[0] - x0, org[1] - y0),
        text,
        fill=fill,
        stroke_fill=outline,
        **options,
    )
    drawn = np.asarray(canvas)
    if count == 1:
        region[...] = np.asarray(canvas.convert("L"))
    else:
        region[..., :3] = drawn[..., 2::-1] if channels == "bgr" else drawn[..., :3]
        if count == 4:
            region[..., 3] = drawn[..., 3]
    return image
