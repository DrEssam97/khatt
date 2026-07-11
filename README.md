# خَطّ — Khatt

[![CI](https://github.com/DrEssam97/khatt/actions/workflows/ci.yml/badge.svg)](https://github.com/DrEssam97/khatt/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue.svg)](pyproject.toml)
[![Fonts: OFL](https://img.shields.io/badge/fonts-SIL%20OFL%201.1-lightgrey.svg)](khatt/fonts/LICENSES/)

**Render Arabic text as ASCII/Unicode-block art — the Arabic FIGlet that FIGlet can't be.**

```text
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣾⡄
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢺⣿⣿⣄
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⣿⣿⠟
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠈⣿⣿
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣿⣿
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢻⣿⡆⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣤⣄⡀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣾⣿⣿⣿⡗
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠈⠛⢿⣿⠟
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠘⣿⣇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠈
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣿⣿⠀⠀⠀⠀⠀⠀⠀⠀⣀⣠⣄⣀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣿⡏⠀⠀⠀⠀⣀⣤⣶⣿⣿⣿⣿⣿⣷⡄⠀⠀⠀⠀⣠⣶⣿⣿⣷⣶⣤⣄⣀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣿⠇⠀⣀⣴⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠀⠀⢠⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣶⣦⣤⣀⣀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣿⣤⣾⣿⠟⠋⠉⠀⠀⠀⠀⠙⢿⣿⣿⡟⠀⠀⠘⠉⠉⠉⠉⠉⠉⠙⠛⠿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣷⣶⣶⣶⣶⣶⡶
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣴⣿⠟⠋⠀⠀⠀⠀⠀⠀⣀⣠⣤⣶⣿⡿⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣀⣤⣽⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡿⠁
⣀⣀⣀⣀⡀⠀⣀⣀⣀⣴⣿⣿⣥⣤⣤⣤⣴⣶⣶⣿⣿⣿⣿⣿⣿⣋⣀⡀⠀⠀⣀⣀⣀⣀⣤⣤⣶⣾⣿⣿⣿⡿⠿⠛⠋⠉⠁⠀⠀⠀⠀⠀⠀⠈
⠈⢿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡿⠟⠋⠉
⠀⠀⠙⠿⢿⣿⣿⣿⣿⣿⣿⣿⣿⠿⠿⠿⠿⠿⠛⠛⠉⠛⠛⠻⠿⠿⠿⠿⠿⠿⠿⠿⠟⠛⠉⠁
```

*(that's «خط» — "khatt", meaning line/script/calligraphy — Amiri font, `braille` style)*

```text
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣿⡆⠀⠀⠀⢸⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣿⠀⠀⠀⠀⢸⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⡇
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣿⡇⠀⠀⠀⢸⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣿⠀⠀⠀⠀⢸⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⡇
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣿⡇⠀⠀⠀⢸⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣿⠀⠀⠀⠀⢸⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⡇
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣿⡇⠀⠀⠀⢸⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣿⠀⠀⠀⠀⢸⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⡇
⠀⠀⠀⠀⣀⣤⣤⡀⠀⠀⠀⠀⠀⠀⣿⡇⠀⠀⠀⢸⡇⠀⠀⠀⠀⣴⡶⠿⠿⠿⠿⣶⣄⠀⠀⠀⠀⣿⠀⠀⠀⠀⢸⡇⠀⠀⠀⠀⣶⡀⠀⠀⠀⠀⠀⠀⠀⠀⢸⡇⠀⠀⠀⠀⢀⣀⠀⠀⠀⠀⢠⣴⣶⣶⣦⣄⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣠⣤⣤⡀
⠀⠀⢠⡾⠋⠉⠉⢻⣆⠀⠀⠀⠀⠀⣿⡇⠀⠀⠀⢸⡇⠀⠀⠀⠀⠻⣦⡀⠀⠀⠀⣨⡟⠀⠀⠀⠀⣿⠀⠀⠀⠀⢸⡇⠀⠀⠀⠀⢹⡇⠀⠀⠀⠀⠀⠀⠀⠀⢸⡇⠀⠀⠀⠀⢸⣿⠀⠀⠀⠀⠛⠁⠀⠀⠀⠙⠻⠷⣶⣶⣶⠀⠀⠀⠀⠈⣿⡀⠀⠀⠀⠀⠀⣰⡿⠋⠉⠙⢿⣆
⠀⠀⣾⠃⠀⠀⠀⢸⣿⣄⠀⠀⠀⢀⣿⠀⠀⠀⠀⠸⣷⠀⠀⠀⠀⠀⠈⢻⣶⣴⡾⠋⠀⠀⠀⠀⢠⣿⠀⠀⠀⠀⢸⣧⠀⠀⠀⠀⣼⡇⠀⠀⠀⠀⠀⠀⠀⠀⠸⣷⠀⠀⠀⠀⣸⣿⡀⠀⠀⠀⠀⠀⠀⠀⢀⣀⣴⠾⠛⠁⠀⠀⠀⠀⠀⠀⢻⣧⠀⠀⠀⠀⣴⣿⣄⡀⠀⠀⢈⣿
⣴⡟⠛⠿⠷⠶⠾⠛⠀⠻⠿⠶⠾⠟⠃⠀⠀⠀⠀⠀⠙⠿⠶⠶⠶⠾⠿⠛⠋⠙⠻⠷⠶⠶⠶⠾⠟⠁⠀⠀⠀⠀⠀⠛⠿⠶⠶⠿⠟⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠙⠿⠶⠶⠾⠋⠈⠻⠷⠶⠶⠶⠶⠾⠿⠛⠋⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⡟⠿⠶⠶⠿⠋⠈⠙⠻⢷⣶⡾⠋
⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣾⠃
⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠈⠛⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠘⠟⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣀⣀⣤⡾⠋
⣿⠅⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠙⠛⠋⠉
```

*(«مرحبا بالعالم» — "Hello, world" — Rubik font, `braille` style)*

## Why FIGlet can't do this

FIGlet fonts map **one character to one fixed glyph**. Arabic doesn't work that way:

- Every letter has up to four **positional forms** (isolated / initial / medial / final).
- Some letter pairs form **mandatory ligatures** — ل + ا must become لا.
- The script is **cursive**: letters connect, and the connections carry the word's shape.
- Text runs **right-to-left**, and real text mixes RTL words with LTR numbers and names.

Khatt sidesteps glyph tables entirely with a **rasterize-then-map** pipeline:

```
text ──► HarfBuzz shaping ──► FreeType rasterization ──► density mapping ──► art
         (positional forms,    (real Arabic fonts,        (blocks / ascii /
          ligatures, bidi)      hi-res grayscale)          braille ramps)
```

The result is genuine calligraphic letterforms — from real fonts — approximated in
terminal characters.

## Install

```bash
pip install khatt        # or: uv add khatt
```

From source:

```bash
git clone https://github.com/DrEssam97/khatt.git && cd khatt
uv sync
```

## Quickstart

### Python API

```python
import khatt

print(khatt.render("مرحبا"))                          # blocks style, 80 columns
print(khatt.render("خط", style="braille", width=60))  # high effective resolution
print(khatt.render("القاهرة", font="cairo", style="ascii", threshold=0.4))

khatt.list_fonts()   # ['amiri', 'cairo', 'noto-naskh', 'rubik']
khatt.list_styles()  # ['ascii', 'blocks', 'braille']
```

### CLI

```bash
khatt "مرحبا"                          # render to the terminal
khatt "خط" --style braille --width 60
khatt "القاهرة" -f cairo -s ascii -t 0.4
echo "سلام" | khatt                    # stdin
khatt "خط" --output art.txt            # save the art
khatt "خط" --output khatt.png          # save the rendered text as an image
khatt --list-fonts
khatt --list-styles
```

Arabic diacritics (tashkeel) are stripped by default — they're illegible at
character-grid resolution. Pass `--keep-tashkeel` (API: `keep_tashkeel=True`) to
render them.

### Gradio app

```bash
uv sync --extra app
uv run python app.py
```

## Bundled fonts and styles

| Font | Family | Character |
|---|---|---|
| `amiri` (default) | Amiri | Classical naskh, rich calligraphic detail |
| `cairo` | Cairo | Geometric, modern, bold strokes |
| `noto-naskh` | Noto Naskh Arabic | Clean, highly legible naskh |
| `rubik` | Rubik | Strong Latin + Arabic pairing for mixed text |

All fonts are licensed under the SIL Open Font License 1.1, preserved verbatim in
[`khatt/fonts/LICENSES/`](khatt/fonts/LICENSES/).

| Style | Ramp | Notes |
|---|---|---|
| `blocks` | `░ ▒ ▓ █` | Default; reads well at any size |
| `ascii` | `. : - = + * # % @` | Pure ASCII, maximum compatibility |
| `braille` | `⠁ … ⣿` | 2×4 dots per cell — 8× the effective resolution |

## Deploy the app to a Hugging Face Space

`app.py` follows the Spaces convention (single file at the repo root), so the whole
repository deploys unchanged with one command:

```bash
uv run --extra app gradio deploy
```

This prompts for a Space name on first run (it uses your `huggingface-cli login`
credentials) and pushes the repo as a Gradio-SDK Space. Alternatively, create a Gradio
Space on huggingface.co and `git push` this repository to it — `app.py` is picked up
automatically and dependencies install via `requirements.txt` (which just points at
`pyproject.toml`).

## Development

```bash
uv sync --all-extras
uv run pre-commit install
```

The gate that must be green before every merge:

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy khatt && uv run pytest
```

Rendering changed intentionally? Regenerate the golden snapshots and commit the diff:

```bash
uv run pytest --update-golden
```

See [CONTRIBUTING.md](CONTRIBUTING.md), [PLAN.md](PLAN.md) and [ROADMAP.md](ROADMAP.md).

## License

MIT for the code — see [LICENSE](LICENSE). Bundled fonts are under the SIL Open Font
License 1.1 — see [`khatt/fonts/LICENSES/`](khatt/fonts/LICENSES/).
