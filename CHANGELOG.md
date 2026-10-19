# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- **Breaking — default sizing.** Text now renders at a fixed font size
  (`size`, in character rows per em, default 10) and wraps at spaces to fit
  `width`, like FIGlet. Before, `width` always stretched the whole text to
  fill it, so a short word came out huge and a sentence came out unreadably
  flat. Pass `size=None` (CLI: `--fit`) for the old behaviour; for single-line
  text its output is byte-identical to 0.1.0.
- The CLI's `--width` now defaults to the terminal width instead of 80.
- Rendering is ~20× faster: rasterized glyphs are cached per font and glyph,
  and FreeType bitmaps are copied directly instead of pixel by pixel
  (2000 characters: 5.7 s → 0.25 s).

### Added

- Multi-line input: line breaks start new art lines, separated by a blank
  line; right-to-left paragraphs are right-aligned.
- `khatt.render_image(text, font, keep_tashkeel=True)`: the shaped text as a
  high-resolution Pillow image (black on white), with the same multi-line
  layout. The CLI's `--output x.png` and the Gradio app use it. Unlike text
  art, images keep Arabic diacritics by default; `--strip-tashkeel` (API:
  `keep_tashkeel=False`) removes them.
- `--size` and `--fit` CLI options; `khatt.DEFAULT_SIZE`.
- Gradio app: size slider and "Fill width" checkbox.

### Fixed

- A line break in the input was reported as an unsupported character and
  the lines were merged into one.
- The Gradio app left a temporary PNG behind on every keystroke; images are
  now served from Gradio's cache, which is pruned hourly.
- Rendering from several threads at once (as the Gradio app does) could
  race on the shared FreeType face.

## [0.1.0] - 2026-07-11

### Added

- **Engine A — rasterize-then-map rendering pipeline**: HarfBuzz shaping
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
  83-test suite at ≥85% enforced coverage on a 3.10–3.13 × Ubuntu/Windows
  CI matrix.

[0.1.0]: https://github.com/DrEssam97/khatt/releases/tag/v0.1.0
