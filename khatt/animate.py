"""Animated text art that keeps Arabic joined.

Effects that split a word into letters (most typing effects, After Effects, Lottie)
break Arabic apart. Here every frame is shaped as a whole, so letters join as they would
on the page:

* ``type``: the text appears a letter at a time. Each letter first takes the form it has
  at the end of a word, then joins the next one as it arrives.
* ``wipe``: the finished text is uncovered from the right, where Arabic starts.
* ``kashida``: the words stretch with tatweel (``ـ``) where their letters join, and
  settle back.
* ``shimmer``: the palette's colours flow through the text (needs a palette).

All frames share one grid, with the line's start fixed (the right edge for Arabic), so
nothing jumps. :class:`Animation` plays them in a terminal or saves them as GIF, APNG,
WebP or an asciinema ``.cast`` recording.
"""

from __future__ import annotations

import json
import sys
import time
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import TextIO

from PIL import Image

from khatt.art_image import _paint_ink, _rgb, art_to_image
from khatt.fonts import Font, font_path, font_paths
from khatt.frames import frame_art
from khatt.kashida import MOST_KASHIDA, kashida_points, stretch
from khatt.layout import DEFAULT_SIZE
from khatt.mapper import get_style, map_image
from khatt.palette import RGB, Palette, _at, _code, cell_colors, palette_colors
from khatt.raster import CELL_ASPECT, RENDER_PPEM, _blend_max, _place, to_grid
from khatt.shaping import base_direction, shape, strip_tashkeel, units_per_em

EFFECTS = ("type", "wipe", "kashida", "shimmer")
"""The animation effects, see the module docstring."""

_HOLD = 1.5
"""Seconds the finished text stays on screen before the animation ends or loops."""


@dataclass
class Animation:
    """Frames of text art, every one the same size, and how long each is shown.

    ``colors`` holds each frame's cell colours when the animation is coloured (see
    :func:`khatt.palette.cell_colors`), so a palette's gradient stays in place while
    the text changes.
    """

    frames: list[str]
    durations: list[float]
    """Seconds per frame."""
    colors: list[list[list[RGB | None]]] | None = field(default=None, repr=False)

    def ansi(self, index: int, mode: str = "truecolor") -> str:
        """Frame ``index`` with terminal colour codes (plain when uncoloured)."""
        frame = self.frames[index]
        if self.colors is None:
            return frame
        lines = []
        for line, line_colors in zip(frame.split("\n"), self.colors[index], strict=True):
            parts, current = [], ""
            for char, color in zip(line, line_colors, strict=True):
                code = "" if color is None else _code(color, mode)
                if code and code != current:
                    parts.append(code)
                    current = code
                parts.append(char)
            lines.append("".join(parts) + ("\033[0m" if current else ""))
        return "\n".join(lines)

    def play(
        self,
        stream: TextIO | None = None,
        *,
        loops: int = 1,
        mode: str | None = "truecolor",
    ) -> None:
        """Play the animation in a terminal, redrawing each frame in place.

        Args:
            stream: Where to write (default: standard output).
            loops: How many times to play it; ``0`` repeats until interrupted.
            mode: ``"truecolor"``, ``"256"``, or ``None`` for no colour codes.
        """
        out = sys.stdout if stream is None else stream
        height = len(self.frames[0].split("\n"))
        out.write("\033[?25l")  # hide the cursor
        try:
            played = 0
            first = True
            while loops == 0 or played < loops:
                for index, duration in enumerate(self.durations):
                    if not first:
                        out.write(f"\033[{height - 1}A\r" if height > 1 else "\r")
                    first = False
                    shown = self.frames[index] if mode is None else self.ansi(index, mode)
                    out.write("\033[K" + shown.replace("\n", "\n\033[K"))
                    out.flush()
                    time.sleep(duration)
                played += 1
        finally:
            out.write("\n\033[?25h")  # show the cursor again
            out.flush()

    def images(
        self,
        *,
        fg: str | tuple[int, int, int] = "black",
        bg: str | tuple[int, int, int] = "white",
        cell_width: int = 12,
    ) -> list[Image.Image]:
        """Every frame drawn with :func:`khatt.art_to_image`, all the same size."""
        images = []
        for index, frame in enumerate(self.frames):
            colors = None if self.colors is None else self.colors[index]
            image = _frame_image(frame, colors, fg, bg, cell_width)
            images.append(image)
        return images

    def save(
        self,
        target: str | Path,
        *,
        fg: str | tuple[int, int, int] = "black",
        bg: str | tuple[int, int, int] = "white",
        cell_width: int = 12,
        loops: int = 0,
    ) -> None:
        """Save as ``.gif``, ``.png`` (APNG), ``.webp`` or ``.cast`` (asciinema).

        Args:
            target: The file; its extension picks the format.
            fg, bg, cell_width: Colours and cell size of image formats (see
                :func:`khatt.art_to_image`); a palette's colours win over ``fg``.
            loops: How many times image formats play; ``0`` (the default) loops
                forever.
        """
        path = Path(target)
        suffix = path.suffix.lower()
        if suffix == ".cast":
            path.write_text(self.cast(), encoding="utf-8")
            return
        if suffix not in (".gif", ".png", ".apng", ".webp"):
            raise ValueError(
                f"unknown animation format {suffix!r}; use .gif, .png (APNG), .webp or .cast"
            )
        images = self.images(fg=fg, bg=bg, cell_width=cell_width)
        durations = [round(seconds * 1000) for seconds in self.durations]
        options: dict[str, object] = {"save_all": True, "duration": durations, "loop": loops}
        if suffix == ".gif":
            options["disposal"] = 2
        if suffix == ".apng":
            options["format"] = "PNG"
        images[0].save(path, append_images=images[1:], **options)  # type: ignore[arg-type]

    def cast(self, mode: str = "truecolor") -> str:
        """The animation as an asciinema v2 recording (play it with ``asciinema play``)."""
        lines = self.frames[0].split("\n")
        header = {
            "version": 2,
            "width": max(len(line) for line in lines),
            "height": len(lines),
            "title": "khatt",
        }
        events = [json.dumps(header, ensure_ascii=False)]
        clock = 0.0
        for index, duration in enumerate(self.durations):
            shown = self.ansi(index, mode).replace("\n", "\r\n")
            events.append(json.dumps([round(clock, 3), "o", "\033[H\033[2J" + shown]))
            clock += duration
        events.append(json.dumps([round(clock, 3), "o", "\r\n"]))
        return "\n".join(events) + "\n"


def _frame_image(
    frame: str,
    colors: list[list[RGB | None]] | None,
    fg: str | tuple[int, int, int],
    bg: str | tuple[int, int, int],
    cell_width: int,
) -> Image.Image:
    """One frame as an image the size of the whole grid, blank frames included."""
    lines = frame.split("\n")
    cell_height = round(cell_width / CELL_ASPECT)
    size = (
        max(len(line) for line in lines) * cell_width + 2 * cell_width,
        len(lines) * cell_height + 2 * cell_width,
    )
    if colors is None:
        image = art_to_image(frame, fg=fg, bg=bg, cell_width=cell_width)
        return Image.new("RGB", size, _rgb(bg)) if image is None else image
    mask_image = art_to_image(frame, fg="white", bg="black", cell_width=cell_width)
    if mask_image is None:
        return Image.new("RGB", size, _rgb(bg))
    ink = Image.new("RGB", size, _rgb(fg))
    for row, line_colors in enumerate(colors):
        for col, color in enumerate(line_colors):
            if color is not None:
                x0, y0 = cell_width + col * cell_width, cell_width + row * cell_height
                ink.paste(color, (x0, y0, x0 + cell_width, y0 + cell_height))
    return _paint_ink(mask_image.convert("L"), ink, bg)


def _clusters(text: str) -> list[int]:
    """Where each typed step ends: after a letter and the marks on it."""
    ends: list[int] = []
    for index, char in enumerate(text):
        if unicodedata.combining(char) and ends:
            ends[-1] = index + 1
        else:
            ends.append(index + 1)
    return ends


def _grids(
    texts: Sequence[str],
    path: Path,
    style: str,
    size: int,
    keep_tashkeel: bool,
    fallbacks: Sequence[Path],
    threshold: float | None,
    fill: str | None = None,
) -> list[str]:
    """Each text as text art on one shared grid, with the line's start fixed in place."""
    direction = base_direction(texts[-1])
    placed_frames = []
    for text in texts:
        glyphs = (
            shape(
                text,
                path,
                keep_tashkeel=keep_tashkeel,
                direction=direction,
                warn=False,
                fallback_fonts=fallbacks,
            )
            if text
            else []
        )
        advance = sum(
            glyph.x_advance * RENDER_PPEM / units_per_em(glyph.font or str(path))
            for glyph in glyphs
        )
        placed_frames.append((_place(glyphs, str(path)), advance))
    widest = max(advance for _, advance in placed_frames)
    shifted = []
    for placed, advance in placed_frames:
        shift = round(widest - advance) if direction == "rtl" else 0
        shifted.append([(item, item.x + shift, item.y) for item in placed])
    boxes = [
        (x, y, x + item.image.size[0], y + item.image.size[1])
        for frame in shifted
        for item, x, y in frame
    ]
    if not boxes:
        raise ValueError("no renderable characters in the text")
    left = min(box[0] for box in boxes)
    top = min(box[1] for box in boxes)
    right = max(box[2] for box in boxes)
    bottom = max(box[3] for box in boxes)
    resolved = get_style(style)
    row_px = RENDER_PPEM / size
    columns = max(1, round((right - left) / (row_px * CELL_ASPECT)))
    rows = max(1, round((bottom - top) / row_px))
    frames = []
    for frame in shifted:
        canvas = Image.new("L", (right - left, bottom - top), 0)
        for item, x, y in frame:
            _blend_max(canvas, item.image, x - left, y - top)
        grid = to_grid(canvas, columns, cell=resolved.cell, rows=rows)
        art = map_image(grid, resolved.name, threshold, fill or texts[-1])
        lines = art.split("\n") + [""] * rows
        frames.append("\n".join(line.ljust(columns) for line in lines[:rows]))
    return frames


def _union(frames: Sequence[str]) -> str:
    """A full block wherever any frame has ink."""
    grids = [frame.split("\n") for frame in frames]
    return "\n".join(
        "".join(
            "█" if any(grid[row][col] not in " ⠀" for grid in grids) else " "
            for col in range(len(grids[0][row]))
        )
        for row in range(len(grids[0]))
    )


def _wipe(art: str, steps: int, direction: str) -> list[str]:
    lines = art.split("\n")
    columns = max(len(line) for line in lines)
    frames = []
    for step in range(steps + 1):
        shown = round(columns * step / steps)
        if direction == "rtl":
            frames.append(
                "\n".join(" " * (columns - shown) + line[columns - shown :] for line in lines)
            )
        else:
            frames.append("\n".join(line[:shown].ljust(columns) for line in lines))
    return frames


def _shifted_palette(colors: Sequence[RGB], phase: float, count: int = 8) -> list[RGB]:
    """``count`` colours sampled from the palette as a loop, starting at ``phase``."""
    ring = [*colors, colors[0]]
    return [_at(ring, (phase + step / count) % 1, False) for step in range(count + 1)]


def animate(
    text: str,
    effect: str = "type",
    *,
    font: Font = "amiri",
    style: str = "blocks",
    size: int = DEFAULT_SIZE,
    palette: Palette | None = None,
    direction: str = "rtl",
    bands: bool = False,
    fps: float = 12,
    hold: float = _HOLD,
    threshold: float | None = None,
    keep_tashkeel: bool = False,
    fallback_fonts: Font | Sequence[Font] = (),
    fill: str | None = None,
    frame: str | None = None,
) -> Animation:
    """Animate one line of text as text art, keeping its letters joined.

    Args:
        text: One line; line breaks become spaces.
        effect: ``"type"``, ``"wipe"``, ``"kashida"`` or ``"shimmer"`` (see the
            module docstring). ``shimmer`` needs a ``palette``.
        font, style, size, threshold, keep_tashkeel, fallback_fonts: As for
            :func:`khatt.render`.
        palette, direction, bands: Colour the frames (see :func:`khatt.color_art`).
        fill: For the ``letters`` style, the text whose letters ink the art (default:
            ``text``).
        frame: Put every frame inside this frame style (see :func:`khatt.frame_art`).
        fps: Frames per second.
        hold: Seconds the finished text stays on screen at the end.

    Returns:
        The :class:`Animation`: play it in a terminal or save it.
    """
    if effect not in EFFECTS:
        raise ValueError(f"effect must be one of {', '.join(EFFECTS)}, got {effect!r}")
    if effect == "shimmer" and palette is None:
        raise ValueError("the shimmer effect needs a palette")
    if fps <= 0:
        raise ValueError(f"fps must be positive, got {fps}")
    if size < 1:
        raise ValueError(f"size must be at least 1, got {size}")
    line = " ".join(text.split())
    if not keep_tashkeel:
        line = strip_tashkeel(line)
    path = font_path(font)
    fallbacks = font_paths(fallback_fonts)
    reading = base_direction(line)

    def grids(texts: Sequence[str]) -> list[str]:
        return _grids(texts, path, style, size, keep_tashkeel, fallbacks, threshold, fill)

    if effect == "type":
        frames = grids(["", *(line[:end] for end in _clusters(line))])
    elif effect == "kashida":
        most = min(12, len([p for w in line.split(" ") for p in kashida_points(w)]) * MOST_KASHIDA)
        if most == 0:
            raise ValueError("the text has no place for kashida (letters that join)")
        counts = [*range(most + 1), *range(most - 1, -1, -1)]
        frames = grids([stretch(line, count) for count in counts])
    else:
        final = grids([line])[0]
        frames = _wipe(final, max(8, round(fps)), reading) if effect == "wipe" else [final]
        if effect == "shimmer":
            frames = frames * max(8, round(fps * 2))
    if frame is not None:
        frames = [frame_art(art, frame) for art in frames]
    step = 1 / fps
    durations = [step] * len(frames)
    if effect != "shimmer":
        durations[-1] = hold
    colors = None
    if palette is not None:
        base = palette_colors(palette)
        # The gradient spans every cell any frame inks, so it stays put as the text moves.
        union = _union(frames)
        colors = []
        for index, frame in enumerate(frames):
            ring = _shifted_palette(base, index / len(frames)) if effect == "shimmer" else base
            spread = cell_colors(union, ring, direction=direction, bands=bands)
            colors.append(
                [
                    [None if char in " ⠀" else spread[r][c] for c, char in enumerate(row)]
                    for r, row in enumerate(frame.split("\n"))
                ]
            )
    return Animation(frames, durations, colors)
