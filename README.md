# خَطّ — Khatt

[![PyPI](https://img.shields.io/pypi/v/khatt.svg)](https://pypi.org/project/khatt/)
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
                              -%+.
       :@.           =:       *+--  =@   *#                       =@
       -@.           +:        +=   =@   #%                       +@
   %+  -@.   =%   =**+***:     @#   =@   *%       -*****%+   -%.  +@
   @*  -@.   +@         +@.    %*   =@   *%      -@-    @*   -@.  +@
   @+  -@.   +@         .@-    %*   =@   *%      +@     @*   -@.  +@
   @+  -@.   +@         :@-    %#   =@   #%      :@-    @*   -@.  +@
   @*  :%****##**********%: +**%#***#%   +#       -*****%#**+*%   =%
  .@=        :-                                             :- -.
+*%+         -*                                             =+ *:
```

*(«ايه الأخبار» — "What's the news?" — Cairo font, `ascii` style)*

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

print(khatt.render("مرحبا"))                          # blocks style, size 10
print(khatt.render("خط", style="braille", size=16))   # bigger, high effective resolution
print(khatt.render("القاهرة", font="cairo", style="ascii", threshold=0.4))
print(khatt.render("السلام عليكم ورحمة الله", width=60))  # wraps at 60 columns
print(khatt.render("مرحبا\nKhatt 2026", font="rubik"))    # one art line per text line

art = khatt.render("مرحبا", style="braille")
khatt.art_to_image(art, fg="white", bg="#1e1e2e").save("art.png")  # the art as a picture

image = khatt.render_image("مرحبا\nKhatt 2026")  # the plain text: Pillow image, black on white
image.save("khatt.png")

khatt.list_fonts()   # ['amiri', 'cairo', 'noto-naskh', 'rubik']
khatt.list_styles()  # ['ascii', 'blocks', 'braille']
```

### CLI

```bash
khatt "مرحبا"                          # render to the terminal
khatt "خط" --style braille --size 16
khatt "القاهرة" -f cairo -s ascii -t 0.4
echo "سلام" | khatt                    # stdin
printf 'سطر أول\nسطر ثاني' | khatt     # multi-line input
khatt "خط" --output art.txt            # save the art
khatt "خط" -s braille -o art.png       # save the art as an image
khatt "خط" -s ascii -o art.png --fg "#e5e5e5" --bg "#1e1e2e"   # terminal colours
khatt "خط" -o logo.png --bg none       # transparent background
khatt "خط" -o khatt.png --png text     # the plain high-resolution text instead
khatt --list-fonts
khatt --list-styles
khatt --doctor                         # which Arabic shapers are installed
```

Arabic diacritics (tashkeel) are stripped from text art by default — they're
illegible at character-grid resolution. Pass `--keep-tashkeel` (API:
`render(..., keep_tashkeel=True)`) to render them. Plain-text images
(`--png text`, `render_image`) keep them by default, since they have the
resolution to show them: pass `--strip-tashkeel` (API:
`render_image(..., keep_tashkeel=False)`) to remove them.

In art images, braille dots and shade blocks are drawn as shapes, so they stay
crisp at any size; ascii characters are drawn in a bold sans font. Each
character gets a cell twice as tall as it is wide (12 × 24 px by default;
API: `cell_width=`), matching the terminal the art was sized for.

### Sizing and wrapping

Like FIGlet, letters have a fixed size and long text wraps:

- `size` (`--size`) is the font size in character rows per em (default 10). It
  gives the same on-screen height in every style; `braille` just packs 4× the
  dots into it.
- `width` (`--width`) is the maximum width. Lines wrap at spaces; a single
  word that can't fit on its own shrinks the whole render until it does. The
  CLI defaults to your terminal's width, the API to 80 columns; `width=None`
  turns wrapping off.
- Line breaks in the input start new lines. Right-to-left paragraphs are
  right-aligned, left-to-right ones left-aligned.
- `--fit` (API: `size=None`) is the 0.1.0 behaviour: scale each line to fill
  exactly `width` columns, without wrapping.

### Drawing on images

`khatt.draw_text` draws correctly shaped Arabic, mixed Arabic/Latin and Arabizi
onto an existing Pillow image. It's a drop-in for `ImageDraw.text`, and
`khatt.overlay` fits text into a box:

```python
from PIL import Image
import khatt

image = Image.open("certificate.png").convert("RGBA")

# Like ImageDraw.text: xy is where the anchor goes ("ra" = right edge, ascender line).
khatt.draw_text(image, (1100, 80), "شهادة تقدير", size_px=72, anchor="ra", fill="#1a3c6e")
khatt.draw_text(image, (1100, 200), "تُمنح هذه الشهادة إلى", size_px=36, anchor="ra",
                max_width=800)  # wraps at spaces

# The largest size at which the name fits the box, wrapped if it has to be.
khatt.overlay(image, "محمد عبد الله", (200, 260, 1100, 400), padding=12, fill="black")

image.save("certificate-filled.png")
```

- Pass text as typed. Don't run it through `arabic_reshaper` or `get_display` first.
- `draw_text`: `size_px` (pixels per em, like `ImageFont.truetype`), `fill`
  (colour name, `#rrggbb[aa]` or an RGB/RGBA tuple; alpha makes the text
  translucent), Pillow-style `anchor` (`l`/`m`/`r` + `a`/`t`/`m`/`s`/`b`/`d`),
  `max_width` in pixels to wrap, `line_spacing` (baseline distance in multiples of
  the size), `align` (`None`: right-to-left paragraphs right-aligned, left-to-right
  ones left-aligned), `keep_tashkeel` (diacritics are kept by default on images).
- `overlay(image, text, (left, top, right, bottom))`: `fit="shrink"` (default) uses
  the largest size between `max_size_px` and `min_size_px` at which the wrapped
  text fits; `"wrap"` wraps at `max_size_px`; `"none"` draws at `max_size_px` as
  is. Also `align`, `valign` (`top`/`middle`/`bottom`) and `padding`. It never
  draws outside the box: text that doesn't fit is clipped, with a
  `khatt.TextOverflowWarning`.
- RGB and RGBA images both work; on RGBA, a transparent background stays
  transparent around the text.

**Why not just `ImageDraw.text`?** Pillow shapes Arabic only when it's built with
Raqm, which most Windows installs aren't. The usual workaround,
`arabic_reshaper` plus `get_display`, pre-shapes the text, so wherever native
shaping *is* available (Pillow with Raqm, matplotlib 3.11+) the text gets shaped
twice and comes out corrupted. khatt never hands text to another shaper: it
shapes with HarfBuzz, rasterizes with FreeType and composites only the finished
pixels, so the output is identical everywhere.

`khatt --doctor` (API: `khatt.doctor()`) shows which shapers your environment
has and warns about that double-shaping trap:

```text
$ khatt --doctor
khatt 0.2.0 (Python 3.13.15)
Pillow 12.3.0: no Raqm, so ImageDraw.text cannot shape Arabic
matplotlib: not installed
arabic_reshaper: not installed
khatt shapes text itself: its output is the same in every case above.
```

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
