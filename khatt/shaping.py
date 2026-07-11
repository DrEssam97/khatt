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
from dataclasses import dataclass
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


@dataclass(frozen=True)
class ShapedGlyph:
    """One positioned glyph, in visual order. Distances are in font units."""

    gid: int
    cluster: int
    x_advance: int
    y_advance: int
    x_offset: int
    y_offset: int


def strip_tashkeel(text: str) -> str:
    """Remove Arabic diacritical marks (harakat, tanween, shadda, sukun…)."""
    return "".join(ch for ch in text if ch not in _TASHKEEL)


@lru_cache(maxsize=8)
def _load_font(path: str) -> hb.Font:
    blob = hb.Blob.from_file_path(path)
    face = hb.Face(blob)
    return hb.Font(face)


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


def _visual_segments(text: str) -> list[tuple[str, str]]:
    """Split text into ``(logical_segment, direction)`` pairs in visual order."""
    visual = get_display(text)
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


def _shape_segment(font: hb.Font, segment: str, direction: str) -> list[ShapedGlyph]:
    buf = hb.Buffer()
    buf.add_str(segment)
    buf.guess_segment_properties()
    buf.direction = direction
    if direction == "rtl":
        buf.script = "Arab"
        buf.language = "ar"
    hb.shape(font, buf, None)

    glyphs: list[ShapedGlyph] = []
    for info, pos in zip(buf.glyph_infos, buf.glyph_positions, strict=True):
        if info.codepoint == 0:  # .notdef — the font has no glyph for this
            offender = segment[info.cluster] if info.cluster < len(segment) else "?"
            warnings.warn(
                f"character {offender!r} (U+{ord(offender):04X}) is not supported "
                "by the selected font and was skipped",
                UnsupportedCharacterWarning,
                stacklevel=3,
            )
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
    return glyphs


def shape(text: str, font_path: str | Path, *, keep_tashkeel: bool = False) -> list[ShapedGlyph]:
    """Shape ``text`` with the font at ``font_path``.

    Returns glyphs in visual order (left to right) with positions in font
    units. Arabic contextual forms, mandatory ligatures and mixed-direction
    text are handled; characters missing from the font are skipped with an
    :class:`UnsupportedCharacterWarning`.

    ``keep_tashkeel`` keeps Arabic diacritics; by default they are stripped,
    because diacritics are illegible at character-grid resolution.
    """
    if not keep_tashkeel:
        text = strip_tashkeel(text)
    if not text:
        return []

    font = _load_font(str(font_path))
    glyphs: list[ShapedGlyph] = []
    for segment, direction in _visual_segments(text):
        glyphs.extend(_shape_segment(font, segment, direction))
    return glyphs


def units_per_em(font_path: str | Path) -> int:
    """Units-per-em of the font; ShapedGlyph distances are in these units."""
    upem: int = _load_font(str(font_path)).face.upem
    return upem
