"""Bundled open-license Arabic fonts, and resolution of user font files.

Font binaries live in this package directory; their SIL Open Font License
texts are preserved under ``LICENSES/``. The MIT license of the khatt code
does not apply to these files.

Wherever khatt takes a ``font``, it accepts a bundled font name or the path
to a TrueType/OpenType font file of your own. The optional ``khatt-fonts``
package adds more names, and calligraphy style names such as ``"kufi"``.
"""

from __future__ import annotations

import io
import os
from collections.abc import Sequence
from functools import lru_cache
from pathlib import Path

import freetype
import uharfbuzz as hb

_FONT_DIR = Path(__file__).resolve().parent

# Cairo, Noto Naskh Arabic and Rubik are variable-font builds, rendered at
# their Regular weight (khatt.shaping.REGULAR_WEIGHT) rather than their
# default instance, which for Rubik is Light; Amiri is a static build.
_REGISTRY: dict[str, str] = {
    "amiri": "Amiri-Regular.ttf",
    "cairo": "Cairo-Regular.ttf",
    "noto-naskh": "NotoNaskhArabic-Regular.ttf",
    "rubik": "Rubik-Regular.ttf",
}

Font = str | os.PathLike[str]
"""A bundled font name (see :func:`available_fonts`) or a font file path."""


def _pack() -> tuple[dict[str, Path], dict[str, list[str]]]:
    """The ``khatt-fonts`` package, if installed: fonts by name, and names by style."""
    try:
        import khatt_fonts
    except ImportError:
        return {}, {}
    return khatt_fonts.fonts(), khatt_fonts.styles()


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
    """Resolve a font name or a font file path to a font file.

    Names are case-insensitive and win over a file of the same name. With the
    ``khatt-fonts`` package installed, its fonts have names too, and a style
    name such as ``"kufi"`` means the first font of that style.
    Anything else is taken as the path to a TrueType or OpenType font
    (``.ttf``, ``.otf``, or the first font of a ``.ttc`` collection).

    Raises:
        KeyError: ``font`` is neither a font name nor an existing file.
        ValueError: the file is not a font khatt can shape and render.
    """
    if isinstance(font, str):
        key = font.strip().lower()
        if key in _REGISTRY:
            return _FONT_DIR / _REGISTRY[key]
        fonts, styles = _pack()
        key = styles[key][0] if key in styles else key
        if key in fonts:
            return fonts[key]
    path = Path(font).expanduser()
    if not path.is_file():
        available = ", ".join(available_fonts())
        more = "" if _pack()[0] else "; `pip install khatt-fonts` adds 26 more"
        raise KeyError(
            f"unknown font {os.fspath(font)!r}; available fonts: {available}, "
            f"or the path to a .ttf/.otf file{more}"
        )
    path = path.resolve()
    _check_font_file(str(path))
    return path


def font_paths(fonts: Font | Sequence[Font]) -> tuple[Path, ...]:
    """Resolve fallback fonts with :func:`font_path`; a single font is a list of one."""
    if isinstance(fonts, (str, os.PathLike)):
        fonts = [fonts]
    return tuple(font_path(font) for font in fonts)


def available_fonts() -> list[str]:
    """Return the sorted names of all fonts: bundled, and from ``khatt-fonts`` if installed."""
    return sorted({*_REGISTRY, *_pack()[0]})
