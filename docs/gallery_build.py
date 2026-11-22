"""Draw the gallery page's pictures and snippets with khatt, at docs build time.

Writes ``docs/_generated``: one Markdown fragment per section (included by
``gallery.md``) and its images. Nothing in it is committed, so the gallery always
shows the fonts, effects and styles of the khatt being documented.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from PIL import Image

import khatt

SAMPLE = "الخط العربي فنّ"
WORD = "خط عربي"
DARK = "#1c1b22"
PAPER = "#fbf7ee"
INK = "#2b2118"


def _save(image: Image.Image, path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.convert("RGB").save(path, optimize=True)
    return path.name


def _on(background: str, art: Image.Image, padding: int = 24) -> Image.Image:
    sheet = Image.new("RGBA", (art.width + 2 * padding, art.height + 2 * padding), background)
    sheet.alpha_composite(art.convert("RGBA"), (padding, padding))
    return sheet


def _fonts(out: Path) -> str:
    lines = []
    for font in khatt.list_fonts():
        image = Image.new("RGB", (720, 120), PAPER)
        khatt.draw_text(image, (700, 60), SAMPLE, font=font, size_px=56, fill=INK, anchor="rm")
        name = _save(image, out / "fonts" / f"{font}.png")
        lines += [
            f"### {font}",
            "",
            f"![{SAMPLE} in {font}](fonts/{name})",
            "",
            f'```python\nkhatt.draw_text(image, xy, text, font="{font}")\n```',
            "",
        ]
    return "\n".join(lines)


def _effects(out: Path) -> str:
    lines = []
    for effect in khatt.list_effects():
        art = khatt.word_art(WORD, effect=effect, size_px=110)
        if art is None:
            continue
        name = _save(_on(DARK, art), out / "effects" / f"{effect}.png")
        lines += [
            f"### {effect}",
            "",
            f"![{WORD} as {effect} word art](effects/{name})",
            "",
            f'```python\nkhatt.word_art("{WORD}", effect="{effect}")\n```',
            "",
        ]
    return "\n".join(lines)


def _curves(out: Path) -> str:
    lines = []
    for curve in khatt.list_curves():
        art = khatt.word_art("بسم الله الرحمن الرحيم", effect="gold", size_px=70, curve=curve)
        if art is None:
            continue
        name = _save(_on(DARK, art), out / "curves" / f"{curve}.png")
        lines += [
            f"### {curve}",
            "",
            f"![Gold text on a {curve}](curves/{name})",
            "",
            f'```python\nkhatt.word_art(text, curve="{curve}")\n```',
            "",
        ]
    return "\n".join(lines)


def _shapes(out: Path) -> str:
    text = "الخط العربي فن جميل يجمع بين الدقة والجمال"
    lines = []
    for shape in khatt.list_shapes():
        art = khatt.calligram(text, shape, width=360, fill=INK)
        if art is None:
            continue
        name = _save(_on(PAPER, art), out / "shapes" / f"{shape}.png")
        lines += [
            f"### {shape}",
            "",
            f"![A {shape} calligram](shapes/{name})",
            "",
            f'```python\nkhatt.calligram(text, "{shape}")\n```',
            "",
        ]
    return "\n".join(lines)


def _styles() -> str:
    lines = []
    for style in khatt.list_styles():
        art = khatt.render("خط", style=style, width=36)
        lines += [
            f"### {style}",
            "",
            f'`khatt "خط" --style {style} -w 36`',
            "",
            "```text",
            art.rstrip("\n"),
            "```",
            "",
        ]
    return "\n".join(lines)


def _palettes(out: Path) -> str:
    art = khatt.render("مرحبا", style="quadrants", width=64, size=None)
    lines = []
    for palette in khatt.list_palettes():
        image = khatt.art_to_image(art, palette=palette, bg=DARK, cell_width=10)
        if image is None:
            continue
        name = _save(image, out / "palettes" / f"{palette}.png")
        lines += [
            f"### {palette}",
            "",
            f"![مرحبا in the {palette} palette](palettes/{name})",
            "",
            f'`khatt "مرحبا" -s quadrants --fit -w 64 --palette {palette}`',
            "",
        ]
    return "\n".join(lines)


def _frames() -> str:
    art = khatt.render("خط", style="braille", width=24)
    lines = []
    for frame in khatt.list_frames():
        lines += [
            f"### {frame}",
            "",
            f'`khatt "خط" -s braille -w 24 --frame {frame}`',
            "",
            "```text",
            khatt.frame_art(art, frame).rstrip("\n"),
            "```",
            "",
        ]
    return "\n".join(lines)


def _zakhrafa() -> str:
    rows = ["| Style | محمد |", "|---|---|"]
    rows += [f"| `{style}` | {khatt.zakhrafa('محمد', style)} |" for style in khatt.list_zakhrafa()]
    return "\n".join(rows) + "\n"


def build(docs: Path) -> None:
    """Write every section of the gallery into ``docs/_generated``."""
    out = docs / "_generated"
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    sections = {
        "fonts": _fonts(out),
        "effects": _effects(out),
        "curves": _curves(out),
        "shapes": _shapes(out),
        "styles": _styles(),
        "palettes": _palettes(out),
        "frames": _frames(),
        "zakhrafa": _zakhrafa(),
    }
    for name, text in sections.items():
        (out / f"{name}.md").write_text(text, encoding="utf-8", newline="\n")
