# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[0.1.0]: https://github.com/mohammedessam/khatt/releases/tag/v0.1.0
