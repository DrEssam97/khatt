# Contributing to Khatt

Thanks for helping! This is a small project with strict hygiene — the rules below keep
it that way.

## Setup

```bash
git clone https://github.com/DrEssam97/khatt.git && cd khatt
uv sync --all-extras       # runtime + dev + gradio
uv run pre-commit install
```

Python 3.10–3.13 are supported; local development is pinned to 3.13 via
`.python-version`. Everything runs through [uv](https://docs.astral.sh/uv/) — there is
no `requirements-dev.txt` and no manual venv management.

## Workflow

- **Never commit to `main`.** Branch per change: `feat/…`, `fix/…`, `test/…`,
  `docs/…`, `ci/…`, `chore/…`.
- **Conventional Commits** for every message: `feat: …`, `fix: …`, `test: …`, etc.
- Before every merge/push, the full gate must be green:

  ```bash
  uv run ruff check .
  uv run ruff format --check .
  uv run mypy khatt
  uv run pytest
  ```

- Coverage must stay ≥ 85% (enforced by pytest's `--cov-fail-under`).

## Tests

Write tests **with** the feature, not after. Shaping assertions are glyph-ID
relational (the bundled font builds have no `post` name table) — see
`tests/test_shaping.py` for the pattern.

If you intentionally change rendering output, regenerate the golden snapshots and
commit the resulting diff — reviewers judge the art change from it:

```bash
uv run pytest --update-golden
```

## Fonts

Bundled fonts must be OFL-licensed, with the complete license text added under
`khatt/fonts/LICENSES/` (that directory is excluded from whitespace-normalization
hooks — license texts stay verbatim). Register new fonts in
`khatt/fonts/__init__.py`.

## Scope

v0.1.x is Engine A (rasterize-then-map) only. Hand-drawn FIGlet-style connected
Arabic fonts (Engine B), ANSI color, animation, and image-to-ASCII are out of scope —
see [ROADMAP.md](ROADMAP.md) before proposing features.
