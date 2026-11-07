"""Open Arabic fonts for khatt, grouped by calligraphy style.

Installing this package is all it takes: khatt finds it on its own.

    >>> khatt.word_art("خط جميل", effect="gold", font="jomhuria")
    >>> khatt.draw_text(image, (40, 40), "خط", font="nastaliq")

Every font is unmodified and keeps its own SIL Open Font License, in
``licenses/``. The MIT license of this package's code does not apply to them.
"""

from __future__ import annotations

from pathlib import Path

__version__ = "1.0.0"

_FONT_DIR = Path(__file__).resolve().parent / "fonts"

# khatt bundles a font for most styles. For the others, the first font here
# is what the style's own name draws with.
_STYLES: dict[str, dict[str, str]] = {
    "kufi": {
        "reem-kufi-fun": "ReemKufiFun[wght].ttf",
        "noto-kufi": "NotoKufiArabic[wght].ttf",
        "kufam": "Kufam[wght].ttf",
        "qahiri": "Qahiri-Regular.ttf",
    },
    "naskh": {
        "scheherazade": "ScheherazadeNew-Regular.ttf",
        "lateef": "Lateef-Regular.ttf",
        "markazi": "MarkaziText[wght].ttf",
        "amiri-quran": "AmiriQuran-Regular.ttf",
    },
    "nastaliq": {
        "gulzar": "Gulzar-Regular.ttf",
    },
    "display": {
        "jomhuria": "Jomhuria-Regular.ttf",
        "lemonada": "Lemonada[wght].ttf",
        "marhey": "Marhey[wght].ttf",
        "blaka": "Blaka-Regular.ttf",
        "blaka-hollow": "BlakaHollow-Regular.ttf",
        "katibeh": "Katibeh-Regular.ttf",
        "mirza": "Mirza-Regular.ttf",
        "el-messiri": "ElMessiri[wght].ttf",
        "changa": "Changa[wght].ttf",
    },
    "handwriting": {
        "playpen": "PlaypenSansArabic[wght].ttf",
    },
    "modern": {
        "tajawal": "Tajawal-Regular.ttf",
        "almarai": "Almarai-Regular.ttf",
        "alexandria": "Alexandria[wght].ttf",
    },
}


def fonts() -> dict[str, Path]:
    """Every font in the package: its name, and the path to its file."""
    return {name: _FONT_DIR / file for group in _STYLES.values() for name, file in group.items()}


def styles() -> dict[str, list[str]]:
    """The calligraphy styles, and the names of the fonts in each."""
    return {style: list(group) for style, group in _STYLES.items()}
