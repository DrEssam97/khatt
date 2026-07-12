# PLAN — Khatt (خَطّ) v0.1.0

> Approved implementation plan for v0.1.0. Decisions settled during planning:
> **rasterization = uharfbuzz + freetype-py** (freetype-py approved as the one dependency
> beyond the original spec), and **local-only git for now** (full GitHub Flow discipline
> kept locally; remote/PRs activate when a GitHub remote is connected).

## Context

Arabic has no FIGlet equivalent: FIGlet's per-character glyph model can't express contextual shaping (isolated/initial/medial/final forms), mandatory ligatures (لا), cursive joining, or RTL. Khatt sidesteps FIGlet entirely with a **rasterize-then-map** pipeline: shape the text properly with a real shaping engine, render it to a bitmap with a real Arabic font, then map pixel density onto character ramps. Deliverables for v0.1.0: a Python library (`khatt.render`), a `khatt` CLI, and a single-file Gradio app deployable to a Hugging Face Space.

## Architecture

```
text ──► shaping.py ──► raster.py ──► mapper.py ──► str
        (HarfBuzz:      (FreeType     (density →
         bidi runs,      glyph        ramp chars:
         positional      bitmaps →    blocks/ascii/
         forms,          hi-res PIL   braille)
         ligatures)      grayscale →
                         downsample
                         to grid)
```

1. **`khatt/shaping.py`** — `python-bidi` splits mixed-direction text into visual-order runs; each run is shaped with `uharfbuzz` (Arabic runs RTL + `language="ar"`, Latin/digit runs LTR). Output: `list[ShapedGlyph]` — dataclass with `gid`, `glyph_name`, `cluster`, `x_advance/y_advance`, `x_offset/y_offset`. Glyph names (e.g. Amiri's `uni0645.init`) are what the shaping tests assert against. A documented `tashkeel` flag controls whether diacritics are kept or stripped before shaping (proposed default: **strip**, because tashkeel is illegible at character-grid resolution; `--keep-tashkeel` to override — see Open Questions).
2. **`khatt/raster.py`** — `freetype-py` renders each shaped glyph's bitmap at the HarfBuzz-computed pen positions onto a high-resolution Pillow grayscale canvas (hinting disabled, fixed integer ppem → deterministic). The canvas is auto-cropped to ink extents then downsampled with LANCZOS to the target grid: `(width, rows)` cells for blocks/ascii, `(width*2, rows*4)` dots for braille. Rows derive from the ink aspect ratio corrected by a terminal cell aspect of ~0.5 (cells are twice as tall as wide). Determinism note: `freetype-py` wheels bundle their own libfreetype and `uv.lock` pins the version, so output is byte-identical across Ubuntu/Windows — this is what makes golden tests viable on both CI runners.
3. **`khatt/mapper.py`** — named styles registry: `blocks` (` ░▒▓█`), `ascii` (` .:-=+*#%@`), `braille` (U+2800 + 8-dot bitmask per 2×4 pixel block). `threshold: float | None` in [0,1]: pixels below it are forced blank; ramp mapping over the remaining range (documented, monotonic: darker → denser).
4. **`khatt/fonts/`** — bundled OFL fonts + registry (`khatt/fonts/__init__.py` maps name → path): **Amiri** (default, naskh, rich ligatures), **Cairo** (geometric kufi-ish, bold weights rasterize well at low res), **Noto Naskh Arabic**, **Rubik** (Arabic + Latin coverage for mixed text). Full OFL texts preserved in `khatt/fonts/LICENSES/`.
5. **`khatt/__init__.py`** — public API exactly as specced: `render(text, font="amiri", style="blocks", width=80, threshold=None) -> str`, plus `list_fonts()`, `list_styles()`, `__version__`. Ships `py.typed`.
6. **`khatt/cli.py`** — `typer` app, entry point `khatt` via `[project.scripts]`. Flags: `--font/-f`, `--style/-s`, `--width/-w`, `--threshold/-t`, `--list-fonts`, `--list-styles`, `--output FILE` (`.txt` writes text; `.png` renders the text art string to an image via Pillow), reads stdin when no arg or arg is `-`. Windows UTF-8: `sys.stdout.reconfigure(encoding="utf-8")` (+ same for stderr) before any output.
7. **`app.py`** (repo root, single file, HF Spaces convention) — Gradio Blocks: RTL textbox (`rtl=True`), font/style dropdowns, width + threshold sliders, live monospace preview (`gr.Code`/styled `gr.Textbox`), copy button, PNG download (`gr.File`). README gets a "Deploy to HF Spaces" section (one command via `huggingface_hub`/`gradio deploy`).

**Out of scope (recorded in `ROADMAP.md`, not implemented):** Engine B (hand-crafted connected FIGlet-style fonts), ANSI color, animation, image-to-ASCII.

## File tree

```
Khatt/
├── pyproject.toml            # all metadata + ruff/mypy/pytest/coverage config
├── uv.lock                   # committed
├── LICENSE                   # MIT (code only)
├── README.md                 # demo media, install, quickstart, FIGlet comparison, Spaces deploy
├── CHANGELOG.md              # Keep a Changelog
├── CONTRIBUTING.md
├── ROADMAP.md                # out-of-scope items above
├── PLAN.md                   # this document
├── app.py                    # single-file Gradio app
├── .gitignore
├── .pre-commit-config.yaml   # ruff, ruff-format, trailing-whitespace, end-of-file-fixer, uv lock --check
├── .github/workflows/ci.yml  # runs on push to GitHub (later); + release.yml in PR 6 (disabled)
├── khatt/
│   ├── __init__.py           # render(), list_fonts(), list_styles(), __version__
│   ├── py.typed
│   ├── shaping.py
│   ├── raster.py
│   ├── mapper.py
│   ├── cli.py
│   └── fonts/
│       ├── __init__.py       # font registry
│       ├── Amiri-Regular.ttf, Cairo-Bold.ttf, NotoNaskhArabic-Regular.ttf, Rubik-Bold.ttf
│       └── LICENSES/         # OFL texts per family
└── tests/
    ├── conftest.py           # --update-golden pytest option, shared fixtures
    ├── test_shaping.py
    ├── test_raster.py
    ├── test_mapper.py
    ├── test_api.py
    ├── test_cli.py
    ├── test_edge_cases.py
    └── golden/               # word × style × font snapshots (*.txt)
```

Note: spec calls for flat `khatt/` package paths, so the build config uses flat layout rather than `uv init --package`'s default `src/` layout.

## Dependencies

| Package | Why | Group |
|---|---|---|
| `uharfbuzz` | Real shaping engine: positional forms, mandatory ligatures, kerning — the reason Khatt can exist. Wheels on all target platforms/versions. | runtime |
| `freetype-py` | Rasterizes glyphs **by glyph ID** at HarfBuzz positions (Pillow can't). Bundles libfreetype → deterministic cross-platform output. *(The one dep beyond your list — approved.)* | runtime |
| `python-bidi` | UBA run ordering for mixed Arabic/Latin/digit strings. | runtime |
| `Pillow` | Canvas compositing, downsampling, PNG output. | runtime |
| `typer` | CLI. | runtime |
| `gradio` | App only — optional extra `khatt[app]`, not a base install requirement. | extra |
| `pytest`, `pytest-cov` | Test suite + coverage gate (`--cov-fail-under=85`). | dev |
| `ruff`, `mypy`, `pre-commit` | Lint/format, type-check, hooks. | dev |
| `twine` | `twine check dist/*` packaging validation in PR 6. | dev |

Not used: `arabic-reshaper` — unnecessary given uharfbuzz works; noted in README as the inferior fallback approach.

Python 3.10–3.13. Everything through `uv` (`uv add`, `uv run`, `uv build`); `uv.lock` committed.

## Git workflow (local-mode adaptation)

`git init` with `main`; **never commit to main directly**. Each phase = one branch (`chore/scaffold`, `feat/shaping`, …), Conventional Commits throughout. Since there's no remote yet: each phase merges to main locally with `--no-ff` and a PR-style merge commit body (what changed / how tested / tradeoffs) — preserving reviewable history so branches can be pushed and retro-PR'd when you connect GitHub. The "before every push" gate becomes **before every merge to main**: `uv run ruff check .` + `uv run ruff format --check .` + `uv run mypy khatt` + `uv run pytest` — never merge red. CI workflow files are committed from PR 1 and will run on first GitHub push.

## Milestones → branches

1. **`chore/scaffold`** — uv project (flat layout), full `pyproject.toml` (metadata, scripts, ruff/mypy/pytest/coverage config), `.pre-commit-config.yaml`, `ci.yml` (matrix: py 3.10–3.13 × ubuntu/windows; ruff → mypy → pytest+coverage), MIT LICENSE, empty package skeleton + placeholder test, PLAN.md, ROADMAP.md. Gate green on empty suite.
2. **`feat/shaping`** — tests first: lam-alef ligature (glyph count + name), «محمد» positional forms (`.init/.medi/.fina` glyph-name assertions), mixed-direction visual order, tashkeel flag behavior. Then `shaping.py` until green.
3. **`feat/raster-mapper`** — download/bundle 4 fonts + OFL licenses; `raster.py` (deterministic output, grid-dimension tests, all-fonts-load test); `mapper.py` (ramp-membership, monotonicity, threshold tests); golden harness (`--update-golden` in conftest) + goldens for «مرحبا» «خط» «القاهرة» × 3 styles × Amiri.
4. **`feat/api-cli`** — `render()` + `cli.py`, `typer.testing.CliRunner` tests (flags, stdin, txt/png output, non-Arabic warning path), edge-case suite (empty, single letter, long-vs-width, tashkeel-only, emoji → graceful warning), coverage gate ≥85% enforced.
5. **`feat/gradio-app`** — `app.py` + `[app]` extra + README Spaces-deploy section. Manual verification: `uv run --extra app python app.py`.
6. **`docs/release-0.1`** — README (Arabic demo media at top, install, API/CLI/Gradio quickstarts, FIGlet comparison), CHANGELOG, CONTRIBUTING, `uv build` + `twine check dist/*`, clean-venv wheel install smoke test (`khatt "مرحبا"`), tag `v0.1.0`. `release.yml` (PyPI trusted publishing) committed **but not enabled** — needs your go-ahead + a GitHub remote anyway.

## Test strategy

- **Shaping (critical):** glyph-name-based assertions via HarfBuzz — ligature presence, positional-form suffixes, run order for mixed-direction input, tashkeel flag. No pixels involved → fast and unambiguous.
- **Raster:** byte-identical output for pinned inputs (determinism guaranteed by bundled fonts + wheel-bundled libfreetype + `uv.lock`); exact grid dimensions per requested width; every bundled font loads and renders non-empty ink.
- **Mapper:** output charset ⊆ declared ramp per style; synthetic gradient input → monotonic density; threshold semantics.
- **Golden files:** committed snapshots under `tests/golden/`, diffed on every run; regenerate deliberately via `pytest --update-golden`. If a platform-specific diff ever appears despite the determinism design, fallback is documented in conftest: per-platform goldens for the offending case.
- **CLI:** `CliRunner` — every flag, stdin, file outputs, error paths.
- **Edge cases:** empty string, single letter, long string vs width, tashkeel-only string, emoji/unsupported chars → warning + graceful degradation, never a crash.
- **Coverage:** `pytest-cov`, `--cov=khatt --cov-fail-under=85` in config and CI.
