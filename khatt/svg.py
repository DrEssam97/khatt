"""Shaped text as SVG: real glyph outlines, for designers, the web and cutters.

The text is shaped and laid out exactly as for images, and each glyph's
outline comes straight from the font through HarfBuzz, so the SVG matches what
:func:`khatt.draw_text` draws, joins and tashkeel included, at any zoom.

    >>> svg = khatt.render_svg("خط جميل", font="lalezar")
    >>> Path("khatt.svg").write_text(svg, encoding="utf-8")
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from xml.sax.saxutils import escape

from khatt.color import Fill, rgba
from khatt.draw import _check_layout, _check_stroke, _is_number, _pixels
from khatt.fonts import Font, font_path, font_paths
from khatt.layout import _checked_pitch, _shape_lines, line_pitch
from khatt.shaping import ShapedGlyph, _load_font, units_per_em

Point = tuple[float, float]


class _Pen:
    """Collects one glyph's outline as SVG path data, in pixels, y down."""

    def __init__(self, x: float, y: float, scale: float) -> None:
        self.x, self.y, self.scale = x, y, scale
        self.parts: list[str] = []
        self.points: list[Point] = []

    def _at(self, point: Point) -> str:
        x, y = self.x + point[0] * self.scale, self.y - point[1] * self.scale
        self.points.append((x, y))
        return f"{x:.2f} {y:.2f}"

    def moveTo(self, point: Point) -> None:
        self.parts.append(f"M{self._at(point)}")

    def lineTo(self, point: Point) -> None:
        self.parts.append(f"L{self._at(point)}")

    def curveTo(self, *points: Point) -> None:
        self.parts.append("C" + " ".join(self._at(p) for p in points))

    def qCurveTo(self, *points: Point | None) -> None:
        # Off-curve points in a row imply an on-curve point halfway between them.
        *offs, end = points
        controls = [p for p in offs if p is not None]
        if end is None:  # a contour of off-curve points only
            end = _middle(controls[-1], controls[0])
        for index, control in enumerate(controls):
            last = index == len(controls) - 1
            target = end if last else _middle(control, controls[index + 1])
            self.parts.append(f"Q{self._at(control)} {self._at(target)}")

    def closePath(self) -> None:
        self.parts.append("Z")

    def endPath(self) -> None:
        pass


def _middle(a: Point, b: Point) -> Point:
    return (a[0] + b[0]) / 2, (a[1] + b[1]) / 2


def _outlines(
    line: Sequence[ShapedGlyph], path: str, size_px: int, y: float
) -> list[tuple[str, list[Point]]]:
    """Each inked glyph of ``line``: its path data and its points, pen starting at x = 0."""
    glyphs = []
    pen_x = 0.0
    for glyph in line:
        source = glyph.font or path
        scale = size_px / units_per_em(source)
        pen = _Pen(pen_x + glyph.x_offset * scale, y - glyph.y_offset * scale, scale)
        _load_font(source).draw_glyph_with_pen(glyph.gid, pen)
        if pen.points:
            glyphs.append(("".join(pen.parts), pen.points))
        pen_x += glyph.x_advance * scale
    return glyphs


def _colour(fill: Fill) -> tuple[str, str]:
    """``fill`` as an SVG colour, and an opacity attribute when it is translucent."""
    red, green, blue, alpha = rgba(fill)
    opacity = f' fill-opacity="{alpha / 255:.3f}"' if alpha < 255 else ""
    return f"#{red:02x}{green:02x}{blue:02x}", opacity


def render_svg(
    text: str,
    *,
    font: Font = "amiri",
    size_px: int = 96,
    fill: Fill = "black",
    align: str | None = None,
    max_width: int | None = None,
    line_spacing: float | None = None,
    spacing: float | None = None,
    keep_tashkeel: bool = True,
    stroke_width: float = 0,
    stroke_fill: Fill | None = None,
    padding: int = 0,
    background: Fill | None = None,
    fallback_fonts: Font | Sequence[Font] = (),
) -> str | None:
    """Draw ``text`` as an SVG document of glyph outlines.

    Lines are laid out as by :func:`khatt.draw_text`: the same wrapping,
    alignment and line spacing, so the SVG matches the image. Each glyph is
    its own path, so where Arabic letters join, their outlines overlap; a
    cutting machine needs them welded (Cricut Design Space: Weld).

    Args:
        text: The text, as typed.
        font: A font name (see :func:`khatt.list_fonts`), a style name or the
            path to a .ttf/.otf file.
        size_px: Font size in pixels per em; the SVG's units are pixels.
        fill: Text colour: a name, ``#rrggbb[aa]``, or an RGB(A) tuple.
        align: ``"left"``, ``"right"`` or ``"center"`` alignment of lines;
            ``None`` aligns right-to-left paragraphs right.
        max_width: Wrap at spaces to this width in pixels.
        line_spacing: Distance between baselines, in multiples of ``size_px``.
        spacing: Pixels between lines, as Pillow's ``spacing``.
        keep_tashkeel: Keep Arabic diacritics (``False`` strips them).
        stroke_width: Width of an outline around the letters, in pixels.
        stroke_fill: Its colour; default: ``fill``.
        padding: Empty pixels around the text.
        background: A colour behind the text; default: transparent.
        fallback_fonts: Fonts for characters ``font`` has no glyph for.

    Returns:
        The SVG document, or ``None`` when ``text`` has nothing to draw.
    """
    _check_stroke(stroke_width)
    spacing_multiple = _check_layout(size_px, line_spacing, spacing, align)
    size = _pixels("size_px", size_px)
    if max_width is not None and max_width < 1:
        raise ValueError(f"max_width must be at least 1, got {max_width}")
    if not (_is_number(padding) and padding >= 0):
        raise ValueError(f"padding must not be negative, got {padding}")
    colour, opacity = _colour(fill)
    stroke_colour, stroke_opacity = _colour(fill if stroke_fill is None else stroke_fill)

    path = font_path(font)
    lines = _shape_lines(
        text,
        path,
        keep_tashkeel,
        max_width,
        ppem=size,
        warn=True,
        fallbacks=font_paths(fallback_fonts),
    )
    alignments = lines.align if align is None else [align] * len(lines.align)
    pitch = line_pitch(
        path,
        size_px=size,
        line_spacing=spacing_multiple,
        spacing=spacing,
        stroke_width=stroke_width,
    )
    pitch = _checked_pitch(pitch, len(lines.glyphs), size, spacing)

    placed = [
        _outlines(line, str(path), size, index * pitch) for index, line in enumerate(lines.glyphs)
    ]
    spans = [
        None
        if not glyphs
        else (min(x for _, ps in glyphs for x, _ in ps), max(x for _, ps in glyphs for x, _ in ps))
        for glyphs in placed
    ]
    widths = [right - left for span in spans if span is not None for left, right in [span]]
    if not widths:
        return None
    layout_width = max(widths)

    paths = []
    for glyphs, span, alignment in zip(placed, spans, alignments, strict=True):
        if span is None:
            continue
        slack = layout_width - (span[1] - span[0])
        shift = {"left": 0.0, "right": slack, "center": slack / 2}[alignment] - span[0]
        for data, points in glyphs:
            paths.append((data, [(x + shift, y) for x, y in points], shift))

    xs = [x for _, points, _ in paths for x, _ in points]
    ys = [y for _, points, _ in paths for _, y in points]
    room = padding + stroke_width
    left, top = min(xs) - room, min(ys) - room
    width, height = max(xs) + room - left, max(ys) + room - top

    def group(attributes: str) -> str:
        shapes = "".join(
            f'<path transform="translate({shift:.2f} 0)" d="{data}"/>' for data, _, shift in paths
        )
        return f"<g {attributes}>{shapes}</g>"

    body = []
    if background is not None:
        back, back_opacity = _colour(background)
        body.append(
            f'<rect x="{left:.2f}" y="{top:.2f}" width="{width:.2f}" height="{height:.2f}" '
            f'fill="{back}"{back_opacity}/>'
        )
    if stroke_width:
        # The outline goes under all of the text, as in images: it grows by
        # stroke_width beyond each letter, so the line is twice as wide.
        body.append(
            group(
                f'fill="{stroke_colour}"{stroke_opacity.replace("fill-", "")} '
                f'stroke="{stroke_colour}" stroke-width="{2 * stroke_width:g}" '
                'stroke-linejoin="round"'
            )
        )
    body.append(group(f'fill="{colour}"{opacity}'))
    title = escape(" ".join(text.split()))
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{math.ceil(width)}" height="{math.ceil(height)}" '
        f'viewBox="{left:.2f} {top:.2f} {width:.2f} {height:.2f}">'
        f"<title>{title}</title>{''.join(body)}</svg>\n"
    )
