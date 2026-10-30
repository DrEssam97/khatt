"""Arabic text shaping via HarfBuzz.

Pipeline: ``python-bidi`` computes the visual (display) order of the whole
string, the visual string is split into directional segments, RTL segments are
un-reversed back to logical order, and each segment is shaped by HarfBuzz with
the appropriate direction. The resulting glyphs are returned in visual order,
left to right, with positions in font units (scaled to units-per-em).

Bidi handling relies on python-bidi's implementation of the Unicode
Bidirectional Algorithm for reordering; the segment classification here only
distinguishes right-to-left letters from everything else, so explicit bidi
control characters (LRE/RLE/…) are not given special treatment.
"""

from __future__ import annotations

import unicodedata
import warnings
from collections.abc import Sequence
from dataclasses import dataclass, replace
from functools import lru_cache
from pathlib import Path

import uharfbuzz as hb
from bidi import get_display


class UnsupportedCharacterWarning(UserWarning):
    """A character has no glyph in the requested font and was skipped."""


# Arabic diacritical marks (tashkeel). Tatweel (U+0640) is deliberately not
# included: it is an elongation character, not a diacritic.
_TASHKEEL = frozenset(
    chr(cp)
    for start, end in (
        (0x0610, 0x061A),
        (0x064B, 0x065F),
        (0x0670, 0x0670),
        (0x06D6, 0x06DC),
        (0x06DF, 0x06E4),
        (0x06E7, 0x06E8),
        (0x06EA, 0x06ED),
    )
    for cp in range(start, end + 1)
)

_RTL_BIDI_CLASSES = frozenset({"AL", "R"})
# Strong LTR and the digit classes: these must keep left-to-right order.
_LTR_BIDI_CLASSES = frozenset({"L", "EN", "AN"})

_BIDI_BASE_DIR = {"ltr": "L", "rtl": "R"}

REGULAR_WEIGHT = 400
"""Weight variable fonts render at (clamped to the font's range). A variable
font's default instance isn't always Regular: Rubik's is Light (300)."""


@dataclass(frozen=True)
class ShapedGlyph:
    """One positioned glyph, in visual order. Distances are in font units."""

    gid: int
    cluster: int
    x_advance: int
    y_advance: int
    x_offset: int
    y_offset: int
    font: str | None = None
    """The fallback font file the glyph comes from, or ``None`` for the line's
    own font. The glyph's distances are in that font's units."""


def strip_tashkeel(text: str) -> str:
    """Remove Arabic diacritical marks (harakat, tanween, shadda, sukun…)."""
    return "".join(ch for ch in text if ch not in _TASHKEEL)


def base_direction(text: str) -> str:
    """Paragraph direction, ``"rtl"`` or ``"ltr"``, from the first strong character.

    Text with no strong character (digits, punctuation, empty) is ``"ltr"``.
    """
    for ch in text:
        bc = unicodedata.bidirectional(ch)
        if bc in _RTL_BIDI_CLASSES:
            return "rtl"
        if bc == "L":
            return "ltr"
    return "ltr"


@lru_cache(maxsize=8)
def _load_font(path: str) -> hb.Font:
    blob = hb.Blob.from_file_path(path)
    face = hb.Face(blob)
    font = hb.Font(face)
    settings = _regular_variations(face)
    if settings:
        font.set_variations(settings)
    return font


def _regular_variations(face: hb.Face) -> dict[str, float]:
    for axis in face.axis_infos:
        if axis.tag == "wght":
            return {"wght": min(max(REGULAR_WEIGHT, axis.min_value), axis.max_value)}
    return {}


def variations(font_path: str | Path) -> dict[str, float]:
    """Variation-axis settings the font is rendered with; empty for static fonts.

    Shaping (HarfBuzz) and rasterization (FreeType) must use the same
    instance, or glyph advances and outlines would disagree.
    """
    return _regular_variations(_load_font(str(font_path)).face)


def _classify(visual: str) -> list[str]:
    """Tag each character of the visual string as ``rtl``, ``ltr`` or ``neutral``.

    Combining marks (NSM) and neutrals are resolved afterwards: marks join the
    directional segment of their neighbours, neutral runs flanked by RTL on
    both sides join the RTL segment, everything else defaults to LTR.
    """
    kinds: list[str] = []
    for ch in visual:
        bc = unicodedata.bidirectional(ch)
        if bc in _RTL_BIDI_CLASSES:
            kinds.append("rtl")
        elif bc == "NSM":
            kinds.append("mark")
        elif bc in _LTR_BIDI_CLASSES:
            kinds.append("ltr")
        else:
            kinds.append("neutral")

    resolved: list[str] = []
    n = len(kinds)
    for i, kind in enumerate(kinds):
        if kind in ("mark", "neutral"):
            prev = resolved[i - 1] if i > 0 else None
            nxt = next((k for k in kinds[i + 1 : n] if k not in ("mark", "neutral")), None)
            if kind == "mark":
                resolved.append("rtl" if "rtl" in (prev, nxt) else "ltr")
            else:
                resolved.append("rtl" if prev == "rtl" and nxt == "rtl" else "ltr")
        else:
            resolved.append(kind)
    return resolved


def _visual_segments(text: str, direction: str | None = None) -> list[tuple[str, str]]:
    """Split text into ``(logical_segment, direction)`` pairs in visual order."""
    base_dir = _BIDI_BASE_DIR[direction] if direction is not None else None
    visual = get_display(text, base_dir=base_dir)
    kinds = _classify(visual)

    segments: list[tuple[str, str]] = []
    start = 0
    for i in range(1, len(visual) + 1):
        if i == len(visual) or kinds[i] != kinds[start]:
            chunk = visual[start:i]
            if kinds[start] == "rtl":
                # RTL segments arrive reversed in the visual string; restore
                # logical order for HarfBuzz, which expects logical input.
                segments.append((chunk[::-1], "rtl"))
            else:
                segments.append((chunk, "ltr"))
            start = i
    return segments


def _shape_segment(
    font: hb.Font, segment: str, direction: str
) -> tuple[list[ShapedGlyph], list[str]]:
    """Shape one directional segment: its glyphs, and the characters with no glyph."""
    buf = hb.Buffer()
    buf.add_str(segment)
    buf.guess_segment_properties()
    buf.direction = direction
    if direction == "rtl":
        buf.script = "Arab"
        buf.language = "ar"
    # Keep each character its own cluster (by default a mark joins its base
    # letter's), so a missing diacritic is reported as itself.
    buf.cluster_level = hb.BufferClusterLevel.MONOTONE_CHARACTERS
    hb.shape(font, buf, None)

    glyphs: list[ShapedGlyph] = []
    missing: list[str] = []
    for info, pos in zip(buf.glyph_infos, buf.glyph_positions, strict=True):
        if info.codepoint == 0:  # .notdef — the font has no glyph for this
            missing.append(segment[info.cluster])
            continue
        glyphs.append(
            ShapedGlyph(
                gid=info.codepoint,
                cluster=info.cluster,
                x_advance=pos.x_advance,
                y_advance=pos.y_advance,
                x_offset=pos.x_offset,
                y_offset=pos.y_offset,
            )
        )
    return glyphs, missing


def _font_runs(segment: str, fonts: Sequence[hb.Font]) -> list[tuple[int, int, int]]:
    """Split a segment into ``(start, end, font index)`` runs, in logical order.

    A letter or digit takes the first font that has a glyph for it. Other
    characters stay in the previous character's font: marks and format
    characters (ZWJ, variation selectors) always, so they are shaped with
    their base; spaces, punctuation and symbols when that font has them.
    Characters no font has stay in the first font, which reports them.
    """
    choices: list[int] = []
    for ch in segment:
        category = unicodedata.category(ch)[0]
        has = [font.get_nominal_glyph(ord(ch)) is not None for font in fonts]
        previous = choices[-1] if choices else None
        if previous is not None and (category in "MC" or (category not in "LN" and has[previous])):
            choices.append(previous)
        else:
            choices.append(has.index(True) if any(has) else 0)
    runs: list[tuple[int, int, int]] = []
    start = 0
    for i in range(1, len(segment) + 1):
        if i == len(segment) or choices[i] != choices[start]:
            runs.append((start, i, choices[start]))
            start = i
    return runs


def _shape_line(
    text: str,
    font_path: str | Path,
    direction: str | None,
    fallback_fonts: Sequence[str | Path],
) -> tuple[list[ShapedGlyph], list[str]]:
    """Shape one line with fallbacks: its glyphs, and the characters no font has."""
    fonts = [_load_font(str(path)) for path in (font_path, *fallback_fonts)]
    paths = [None, *(str(path) for path in fallback_fonts)]
    glyphs: list[ShapedGlyph] = []
    missing: list[str] = []
    for segment, segment_direction in _visual_segments(text, direction):
        shaped, absent = _shape_segment(fonts[0], segment, segment_direction)
        runs = _font_runs(segment, fonts) if absent and len(fonts) > 1 else []
        if any(index for _, _, index in runs):
            # Shape each run with its own font; a segment the first font
            # covers stays one run, exactly as without fallbacks.
            pieces, absent = [], []
            for start, end, index in runs:
                run_glyphs, run_absent = _shape_segment(
                    fonts[index], segment[start:end], segment_direction
                )
                pieces.append(
                    [
                        replace(glyph, cluster=glyph.cluster + start, font=paths[index])
                        for glyph in run_glyphs
                    ]
                )
                absent.extend(run_absent)
            if segment_direction == "rtl":
                pieces.reverse()  # runs are in logical order; glyphs go out visually
            shaped = [glyph for piece in pieces for glyph in piece]
        glyphs.extend(shaped)
        missing.extend(absent)
    return glyphs, missing


def shape(
    text: str,
    font_path: str | Path,
    *,
    keep_tashkeel: bool = False,
    direction: str | None = None,
    warn: bool = True,
    fallback_fonts: Sequence[str | Path] = (),
) -> list[ShapedGlyph]:
    """Shape one line of ``text`` with the font at ``font_path``.

    Returns glyphs in visual order (left to right) with positions in font
    units. Arabic contextual forms, mandatory ligatures and mixed-direction
    text are handled; characters missing from the font are skipped with an
    :class:`UnsupportedCharacterWarning`.

    ``keep_tashkeel`` keeps Arabic diacritics; by default they are stripped,
    because diacritics are illegible at character-grid resolution.

    ``direction`` (``"rtl"`` or ``"ltr"``) sets the paragraph direction used
    for bidi reordering; by default it is detected from the line itself. Pass
    the paragraph's direction when shaping a wrapped line, so a line that
    happens to start with a Latin word keeps the paragraph's order.

    ``warn=False`` skips unsupported characters silently (used when shaping
    candidate lines just to measure them).

    ``fallback_fonts`` are font files tried in order for characters the font
    has no glyph for; their glyphs carry :attr:`ShapedGlyph.font`.
    """
    if direction is not None and direction not in _BIDI_BASE_DIR:
        raise ValueError(f"direction must be 'rtl' or 'ltr', got {direction!r}")
    if not keep_tashkeel:
        text = strip_tashkeel(text)
    if not text:
        return []

    glyphs, missing = _shape_line(text, font_path, direction, fallback_fonts)
    for offender in missing if warn else ():
        warnings.warn(
            f"character {offender!r} (U+{ord(offender):04X}) is not supported "
            "by the selected font and was skipped",
            UnsupportedCharacterWarning,
            stacklevel=2,
        )
    return glyphs


def missing_characters(
    text: str,
    font_path: str | Path,
    *,
    direction: str | None = None,
    fallback_fonts: Sequence[str | Path] = (),
) -> set[str]:
    """Characters of one line of ``text`` that shaping with the font leaves out.

    These are the characters :func:`shape` skips with an
    :class:`UnsupportedCharacterWarning` (given the same ``direction`` and
    ``fallback_fonts``). Characters the font can still show (composed or
    decomposed by HarfBuzz) and invisible ones such as ZWJ are not missing.
    """
    return set(_shape_line(text, font_path, direction, fallback_fonts)[1])


def units_per_em(font_path: str | Path) -> int:
    """Units-per-em of the font; ShapedGlyph distances are in these units."""
    upem: int = _load_font(str(font_path)).face.upem
    return upem


def vertical_metrics(font_path: str | Path) -> tuple[int, int]:
    """The font's ``(ascender, descender)`` in font units, y up (descender < 0)."""
    extents = _load_font(str(font_path)).get_font_extents("ltr")
    return extents.ascender, extents.descender
