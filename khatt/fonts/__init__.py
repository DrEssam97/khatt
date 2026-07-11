"""Bundled open-license Arabic fonts.

Font binaries live in this package directory; their SIL Open Font License
texts are preserved under ``LICENSES/``. The MIT license of the khatt code
does not apply to these files.
"""

from __future__ import annotations

from pathlib import Path

_FONT_DIR = Path(__file__).resolve().parent

# Cairo, Noto Naskh Arabic and Rubik are variable-font builds used at their
# default (Regular) instances; Amiri is a static build.
_REGISTRY: dict[str, str] = {
    "amiri": "Amiri-Regular.ttf",
    "cairo": "Cairo-Regular.ttf",
    "noto-naskh": "NotoNaskhArabic-Regular.ttf",
    "rubik": "Rubik-Regular.ttf",
}


def font_path(name: str) -> Path:
    """Return the path to a bundled font by registry name (case-insensitive)."""
    key = name.strip().lower()
    if key not in _REGISTRY:
        available = ", ".join(sorted(_REGISTRY))
        raise KeyError(f"unknown font {name!r}; available fonts: {available}")
    return _FONT_DIR / _REGISTRY[key]


def available_fonts() -> list[str]:
    """Return the sorted names of all bundled fonts."""
    return sorted(_REGISTRY)
