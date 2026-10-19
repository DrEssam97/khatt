"""Bundled open-license Arabic fonts, and resolution of user font files.

Font binaries live in this package directory; their SIL Open Font License
texts are preserved under ``LICENSES/``. The MIT license of the khatt code
does not apply to these files.

Wherever khatt takes a ``font``, it accepts a bundled font name or the path
to a TrueType/OpenType font file of your own.
"""

from __future__ import annotations

import io
import os
from functools import lru_cache
from pathlib import Path

import freetype
import uharfbuzz as hb

_FONT_DIR = Path(__file__).resolve().parent

# Cairo, Noto Naskh Arabic and Rubik are variable-font builds used at their
# default (Regular) instances; Amiri is a static build.
_REGISTRY: dict[str, str] = {
    "amiri": "Amiri-Regular.ttf",
    "cairo": "Cairo-Regular.ttf",
    "noto-naskh": "NotoNaskhArabic-Regular.ttf",
    "rubik": "Rubik-Regular.ttf",
}

Font = str | os.PathLike[str]
"""A bundled font name (see :func:`available_fonts`) or a font file path."""


@lru_cache(maxsize=32)
def _check_font_file(path: str) -> None:
    """Raise ``ValueError`` unless both FreeType and HarfBuzz can use the font."""
    data = Path(path).read_bytes()
    try:
        face = freetype.Face(io.BytesIO(data))
    except freetype.FT_Exception as exc:
        raise ValueError(f"cannot load font file {path}: not a TrueType or OpenType font") from exc
    if not face.is_scalable:
        raise ValueError(f"cannot use font file {path}: bitmap-only fonts are not supported")
    # HarfBuzz reads only plain sfnt data: web fonts (WOFF, WOFF2) load in
    # FreeType but would shape to nothing.
    if hb.Face(data).glyph_count == 0:
        raise ValueError(
            f"cannot shape text with font file {path}; if it is a web font "
            "(.woff/.woff2), use the .ttf or .otf version"
        )


def font_path(font: Font) -> Path:
    """Resolve a bundled font name or a font file path to a font file.

    Bundled names are case-insensitive and win over a file of the same name.
    Anything else is taken as the path to a TrueType or OpenType font
    (``.ttf``, ``.otf``, or the first font of a ``.ttc`` collection).

    Raises:
        KeyError: ``font`` is neither a bundled font name nor an existing file.
        ValueError: the file is not a font khatt can shape and render.
    """
    if isinstance(font, str):
        key = font.strip().lower()
        if key in _REGISTRY:
            return _FONT_DIR / _REGISTRY[key]
    path = Path(font).expanduser()
    if not path.is_file():
        available = ", ".join(sorted(_REGISTRY))
        raise KeyError(
            f"unknown font {os.fspath(font)!r}; available fonts: {available}, "
            "or the path to a .ttf/.otf file"
        )
    path = path.resolve()
    _check_font_file(str(path))
    return path


def available_fonts() -> list[str]:
    """Return the sorted names of all bundled fonts."""
    return sorted(_REGISTRY)
