# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- Python 3.14 is tested and listed as supported. CI also runs the whole suite with
  Pillow's Raqm turned on, to prove khatt draws the same with or without it.

## [0.7.0] - 2026-11-11

### Added

- Zakhrafa: `khatt.zakhrafa("محمد", "royal")` decorates text to copy and paste, in 10
  styles (`khatt.list_zakhrafa()`). Decorations only go where letters join, never inside
  lam-alef, so words stay joined and tashkeel stays with its letter. In the CLI:
  `khatt "محمد" --zakhrafa all`.
- SVG: `khatt.render_svg(text)` draws text as vector glyph outlines, shaped and laid out
  exactly as for images, with `draw_text`'s options plus `padding` and `background`. In
  the CLI, an `.svg` output: `khatt "خط" -o khatt.svg`.

## [0.6.0] - 2026-11-09

### Added

- Text on curves: `khatt.word_art(text, curve="arc")`, with the presets `arc`, `smile`,
  `ring` and `wave` (`khatt.list_curves()`), or `khatt.Arc` and `khatt.Wave` for your
  own. The whole line bends as one sheet, so Arabic letters stay joined and marks stay in
  place, and effects are drawn on the bent text. In the CLI: `--curve` and `--list-curves`.
- Calligrams: `khatt.calligram(text, shape="heart")` flows text inside a shape, line by
  line, without cutting a letter at the edge. The presets are `arch`, `circle`,
  `crescent`, `diamond` and `heart` (`khatt.list_shapes()`), and any image works as a shape.
  The text repeats until the shape is full, or fits in once with `repeat=False`, and Arabic
  lines are stretched to their full width with kashida. Effects work too. In the CLI:
  `--shape`, `--repeat/--no-repeat` and `--list-shapes`.

## [0.5.0] - 2026-11-07

### Added

- Word art: `khatt.word_art()` draws text as a finished image, and `draw_text` and
  `overlay` take `effect=`. Presets are `3d`, `fire`, `gold`, `ice`, `neon`, `retro`,
  `silver` and `sticker` (`khatt.list_effects()`), and `khatt.Effect` builds your own
  from `Gradient`, `Shadow`, `Glow`, `Extrude`, an outline and a bevel. Effects work on
  the finished text, so letters stay joined and marks stay in place. In the CLI:
  `khatt "خط" --effect gold -o gold.png`, with `--size-px` and `--list-effects`.
- Four more bundled fonts: `aref-ruqaa`, `lalezar`, `rakkas` and `reem-kufi`. Style names
  work as fonts too: `naskh`, `ruqaa`, `kufi`, `display` and `modern`.
- `khatt-fonts`, a new package with 22 more open Arabic fonts in Kufi, Naskh, Nastaliq,
  display, handwriting and modern styles. Install it and khatt finds it on its own.

## [0.4.2] - 2026-11-05

### Fixed

- Sizes can be NumPy numbers or floats, as they often are when worked out from
  an image. `size_px` in `draw_text` and `text_bbox`, `max_size_px`,
  `min_size_px` and `padding` in `overlay`, and `size` in `caption_image`
  raised `ctypes.ArgumentError` from FreeType unless that size had been drawn
  before, so the same call could work or fail depending on what came first.
  `overlay` could also hang on a fractional `max_size_px`, or on a size in a
  small NumPy type such as `uint8`. Sizes now round to whole pixels, and NaN or
  infinity raises `ValueError`.

## [0.4.1] - 2026-11-03

### Fixed

- Brackets in right-to-left text now face the right way. `(مرحبا)` was drawn
  as `)مرحبا(`, and `سيارة (أجرة)` with its closing bracket reversed, because
  a bracket at the start or end of an Arabic or Hebrew line was laid out left
  to right. It now takes the line's direction and is mirrored. Brackets in
  left-to-right lines are unchanged.

### Removed

- The Gradio demo app (`app.py`), its `app` extra and its deployment files
  (`Dockerfile`, `render.yaml`, `requirements.txt`). khatt is a library and a
  CLI; `uvx khatt "مرحبا"` is the quickest way to try it.

## [0.4.0] - 2026-10-30

### Added

- Fallback fonts: `fallback_fonts=[...]` on `render`, `render_image`,
  `draw_text`, `text_bbox`, `overlay`, `caption_image`,
  `khatt.video.TextClip` and `missing_characters`. A character the font has
  no glyph for is drawn from the first fallback that has one, instead of
  being skipped, so Arabic mixed with Chinese, Hebrew or Cyrillic keeps
  every script. Marks stay in their base letter's font, spaces and
  punctuation in the font of the text before them, and line spacing and
  anchors follow `font`. Text the font covers draws exactly as before.

## [0.3.0] - 2026-10-20

### Added

- `khatt.draw_text(image, xy, text, ...)`: draws correctly shaped text onto
  an existing RGB or RGBA Pillow image, a drop-in for `ImageDraw.text` with
  Pillow-style anchors, `max_width` word-wrap, `line_spacing`, auto or
  explicit `align`, and alpha-aware fills. It never uses Pillow's text
  layout, so its output is identical with or without Raqm and text is never
  shaped twice. Glyphs are rendered at the target size with quarter-pixel
  positioning.
- `khatt.overlay(image, text, box, fit=...)`: places text inside a box.
  `fit="shrink"` picks the largest size that fits with wrapping (a binary
  search measured from glyph outlines, without rendering), `"wrap"` wraps at
  a fixed size and `"none"` draws as is; plus `align`, `valign` and
  `padding`. Nothing is drawn outside the box: text that doesn't fit is
  clipped with a `khatt.TextOverflowWarning`.
- Your own fonts: every `font` parameter (`render`, `render_image`,
  `draw_text`, `overlay`, the CLI's `--font`) also accepts the path to a
  `.ttf`/`.otf` file, as a string or `pathlib.Path`, including non-ASCII
  paths on Windows. Bundled names still win over a file of the same name. A
  missing file raises `KeyError` like an unknown name; a file khatt can't
  shape and render (not a font, bitmap-only, or a WOFF/WOFF2 web font that
  FreeType reads but HarfBuzz can't) raises a `ValueError` saying why.
- Outlined text: `stroke_width=` and `stroke_fill=` on `draw_text` and
  `overlay`, with the same meaning as Pillow's. The outline is FreeType's own
  stroke (round corners), filled like Pillow's, and grows outward around the
  text without moving it; `stroke_fill` defaults to `fill`, and an outline in
  the text's own colour is painted in one coat, so translucent text stays
  even. `overlay` fits the outline inside the padding too. Arabic joins stay
  continuous because the text is painted over its outline.
- `khatt.text_bbox(text, xy=..., ...)`: measures text without drawing it, like
  Pillow's `textbbox`, with `draw_text`'s arguments. The box is exact: every
  pixel `draw_text` would paint, outline included. Empty text gives an empty
  box at `xy`.
- `spacing=` on `draw_text`, `overlay` and `text_bbox`: pixels between lines,
  with the same meaning as Pillow's `multiline_text` spacing (each line's
  ascender line sits `spacing` pixels below the previous baseline, plus twice
  the stroke width), so lines land within a pixel per line of where Pillow
  puts them. Like Pillow's, it doesn't apply to a single line. It replaces
  `line_spacing`, whose default is still 1.2; passing both raises a
  `ValueError`. The `a` anchor uses the same ascender, rounded up to whole
  pixels as in Pillow.
- `khatt.missing_characters(text, font)`: the characters a font has no glyph
  for, each once, in the order typed. These are exactly the ones drawing
  skips with an `UnsupportedCharacterWarning`, so you can check first and
  fall back to another font. Invisible characters (ZWJ, ZWNJ, bidi marks)
  and line breaks don't count; `keep_tashkeel=False` leaves out diacritics,
  as drawing with it (or `render`) does.
- `khatt.video.TextClip` (new `khatt[video]` extra): a drop-in for moviepy's
  `TextClip` that shapes text with khatt. It takes moviepy 2.2's arguments in
  the same order, including `method="caption"` wrapping and the automatic
  font size; `font` defaults to Amiri and `text_align` to each paragraph's
  direction; fractional font sizes round to whole pixels. Clips follow
  moviepy's documented height formula and grow only when stacked diacritics
  reach beyond it, so nothing is cut off (text too wide for a fixed size and
  font size warns with `TextOverflowWarning`); moviepy's own `TextClip`
  crops the bottom of label clips with Pillow 11 and later. The automatic
  font size is found without rendering, like `overlay`'s.
- `khatt.caption_image(text, ...)`: the same caption as a Pillow image,
  without moviepy.
- Regression tests against HarfBuzz itself: every glyph of `بِتَ` (the
  kasra/fatha case from moviepy and MoneyPrinterTurbo reviews) lands where
  HarfBuzz's positions and glyph extents put it, within a pixel, in all four
  fonts; the whole vocalized Al-Fatiha and Persian and Urdu text match
  HarfBuzz's ink boxes; Persian and Urdu letters take their joined forms; and
  each font's coverage of Quranic marks and Urdu letters is pinned down.
- `khatt --doctor` / `khatt.doctor()`: reports the Pillow version and
  whether it has Raqm, the matplotlib version (3.11+ shapes Arabic
  natively), and whether `arabic_reshaper` is importable, with a warning
  that combining it with native shaping corrupts text (double-shaping).

### Changed

- khatt now installs alongside older Pillow and typer: the minimums drop from
  Pillow 12.3 and typer 0.26.8 to **Pillow 10.1** and **typer 0.15.4**, the
  oldest versions the full test suite passes with. Projects pinned to Pillow
  10/11 (for example through moviepy 2.2.1) can now depend on khatt. CI tests
  the minimums and MoneyPrinterTurbo's pins (Pillow 11.3.0, typer 0.26.5) on
  every change.
- Vertical metrics (the `a`, `d` and `m` anchors, and `spacing`) come from
  FreeType's scaled metrics, exactly what Pillow's `getmetrics` reports, for
  any font; the `d` and `m` anchors can move by a pixel.
- Development: moviepy holds Pillow below 12, so the lockfile resolves the
  `video` extra separately. `uv sync` keeps the newest Pillow; use
  `uv sync --extra video --no-group latest-pillow` for the video extra.

### Fixed

- When a font had no glyph for a diacritic, `UnsupportedCharacterWarning`
  named the letter it sat on instead of the diacritic itself.
- `overlay(fit="shrink")` repeated each `UnsupportedCharacterWarning` once
  per size it tried; it now warns once.
- Rubik rendered at its Light weight: a variable font's default instance
  isn't always Regular, and Rubik's is Light (300). Variable fonts now render
  at their Regular weight (400) in both shaping and rasterization, so Rubik
  output is heavier and easier to read. Cairo and Noto Naskh Arabic already
  defaulted to Regular and are unchanged.

## [0.2.0] - 2026-10-19

### Changed

- **Breaking: default sizing.** Text now renders at a fixed font size
  (`size`, in character rows per em, default 10) and wraps at spaces to fit
  `width`, like FIGlet. Before, `width` always stretched the whole text to
  fill it, so a short word came out huge and a sentence came out unreadably
  flat. Pass `size=None` (CLI: `--fit`) for the old behaviour; for single-line
  text its output is byte-identical to 0.1.0.
- **Breaking: PNG output.** The CLI's `--output x.png` now saves the art
  itself as an image, in the chosen `--style`, with `--fg` / `--bg` colours
  (`--bg none` for transparent). `--png text` saves the plain high-resolution
  text instead, which was the only option in 0.1.0.
- The CLI's `--width` now defaults to the terminal width instead of 80.
- `--keep-tashkeel` is now a `--keep-tashkeel/--strip-tashkeel` pair: with
  neither, the art strips diacritics and `--png text` images keep them.
- Rendering is ~20× faster: rasterized glyphs are cached per font and glyph,
  and FreeType bitmaps are copied directly instead of pixel by pixel
  (2000 characters: 5.7 s → 0.25 s).
- `LICENSE` is now the plain MIT text, so GitHub and other tools detect the
  license; the note about the bundled OFL fonts moved to a new `NOTICE` file,
  which ships in the wheel and sdist.

### Added

- Multi-line input: line breaks start new art lines, separated by a blank
  line; right-to-left paragraphs are right-aligned.
- `khatt.art_to_image(art, fg=, bg=, cell_width=, padding=)`: draws text art
  as an image. Braille dots and shade blocks are drawn as shapes (crisp at
  any size), ascii characters in a bold sans font; `bg=None` gives a
  transparent background.
- `khatt.render_image(text, font, keep_tashkeel=True)`: the shaped text as a
  high-resolution Pillow image (black on white), with the same multi-line
  layout. `--png text` and the Gradio app use it. Unlike text art, these
  images keep Arabic diacritics by default; `--strip-tashkeel` (API:
  `keep_tashkeel=False`) removes them.
- `--size` and `--fit` CLI options; `khatt.DEFAULT_SIZE`.
- Gradio app: size slider, "Fill width" checkbox, and a download of the art
  as an image.

### Fixed

- A line break in the input was reported as an unsupported character and
  the lines were merged into one.
- The Gradio app left a temporary PNG behind on every keystroke; images are
  now served from Gradio's cache, which is pruned hourly.
- Rendering from several threads at once (as the Gradio app does) could
  race on the shared FreeType face.

## [0.1.0] - 2026-07-11

### Added

- **Engine A, the rasterize-then-map rendering pipeline**: HarfBuzz shaping
  (`uharfbuzz` + `python-bidi`) → FreeType rasterization (`freetype-py`) →
  density mapping to character ramps.
- Correct Arabic shaping: positional forms, the mandatory لا ligature, mixed
  Arabic/Latin/digit visual ordering, and a `keep_tashkeel` flag (diacritics
  are stripped by default).
- Three output styles: `blocks` (░▒▓█), `ascii` (density ramp), `braille`
  (2×4 dot patterns), all with an optional coverage `threshold`.
- Four bundled OFL fonts: Amiri (default), Cairo, Noto Naskh Arabic, Rubik,
  with license texts preserved under `khatt/fonts/LICENSES/`.
- Public API: `khatt.render(text, font, style, width, threshold,
  keep_tashkeel)`, `khatt.list_fonts()`, `khatt.list_styles()`.
- `khatt` CLI (typer): `--font/--style/--width/--threshold/--keep-tashkeel`,
  `--list-fonts`, `--list-styles`, `--output` (text art or PNG of the
  rendered text), stdin input, UTF-8 output on Windows consoles.
- Single-file Gradio app (`app.py`) with live preview, deployable unchanged
  to a Hugging Face Space (`[app]` extra).
- Golden-file snapshot tests with a `pytest --update-golden` refresh flow;
  83-test suite at ≥85% enforced coverage on a 3.10 to 3.13 × Ubuntu/Windows
  CI matrix.

[Unreleased]: https://github.com/DrEssam97/khatt/compare/v0.7.0...HEAD
[0.7.0]: https://github.com/DrEssam97/khatt/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/DrEssam97/khatt/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/DrEssam97/khatt/compare/v0.4.2...v0.5.0
[0.4.2]: https://github.com/DrEssam97/khatt/compare/v0.4.1...v0.4.2
[0.4.1]: https://github.com/DrEssam97/khatt/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/DrEssam97/khatt/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/DrEssam97/khatt/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/DrEssam97/khatt/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/DrEssam97/khatt/releases/tag/v0.1.0
