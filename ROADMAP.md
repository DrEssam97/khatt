# Roadmap

> Local planning document — git ignores changes to this file (`skip-worktree`), so the
> public ROADMAP.md is unchanged. Publish with
> `git update-index --no-skip-worktree ROADMAP.md`. Research date: October 2026.

## Positioning

> **Khatt: correct Arabic and Arabizi text for Python — the same output everywhere,
> whether or not the environment shapes Arabic natively. It never double-shapes, and it
> does what nothing else does: fit text to a box, captions, word-timed animation,
> per-word styling, font fallback and emoji — to images, video and the terminal.**

## What the research changed

- **Basic shaping is spreading, so "Pillow breaks Arabic" is a shrinking pitch.**
  matplotlib 3.11 (June 2026) shapes Arabic natively with libraqm. Pillow PR #9926
  (open) would make Raqm actually load in the Windows wheels.
- **The old workaround now corrupts text.** Where native shaping exists, the
  `arabic-reshaper` + `python-bidi` recipe shapes twice and reverses or garbles the
  output (matplotlib's own release notes warn about it; wordcloud #723 is still open).
  Khatt's job: correct output with or without native shaping.
- **Demand is real but smaller than raw downloads suggest.** ~3.6M of
  arabic-reshaper's ~4.8M monthly downloads come in through xhtml2pdf.
- **Where the unmet demand is:** fitting text into images (automation, banners,
  certificates), video captions, word-timed animation (Quran recitation videos), mixed
  scripts with emoji, cut files, OCR training data, HTTP/AI-agent access.
- **Stars come from a visual demo told as a technical story, not from usage.**
  arabic-reshaper has 449★ despite millions of downloads; TerminalTextEffects gained
  ~2,000★ in 9 days from one HN post linking to its GIFs.

## Released

- **v0.1.0** (2026-07-11): HarfBuzz → FreeType → density mapping (`blocks` / `ascii` /
  `braille`), four OFL fonts, Python API, CLI, Gradio app.
- **v0.2.0** (2026-10-19, PyPI + GitHub Release): multi-line input, FIGlet-style sizing
  with word-wrap (`--fit` keeps the old mode), ~20× faster rendering, Gradio temp-file
  leak fixed, `render_image()` (keeps tashkeel by default), **art saved as images**
  (`art_to_image`, `-o art.png`, `--fg`/`--bg`, `--png text`), snapshot tests for every
  font × style, LICENSE/NOTICE split (GitHub now detects MIT).

## On `main`, unreleased (→ v0.3.0)

- [x] `draw_text()` / `overlay(fit=...)` / `khatt --doctor` / custom `.ttf`/`.otf` fonts (#6).
- [x] Variable fonts render at Regular weight; Rubik was Light (#7).
- [x] Dev group requires twine 7 so local `twine check` works (#5).
- [ ] Reconcile CONTRIBUTING.md's "Scope" section with this roadmap when it's published.

## Next release (v0.3.0): general features that MoneyPrinterTurbo will also need

These are khatt features in their own right. MoneyPrinterTurbo is one consumer, never the
reason for MPT-specific code in khatt.

1. [x] **Wider dependency compatibility** (PR #8, open): lower the minimums (Pillow `>=12.3` and typer
       `>=0.26.8` before; now Pillow `>=10.1`, typer `>=0.15.4`) to what khatt actually needs, so it installs next to projects
       pinned to Pillow 10/11 (moviepy 2.2.1 → Pillow 11.3.0). CI jobs for the minimum
       versions and for MoneyPrinterTurbo's pins (Pillow 11.3.0, typer 0.26.5).
2. [x] **Outlines** (PR #9, open): `stroke_width=` / `stroke_fill=` on `draw_text` / `overlay`, same
       meaning as Pillow's.
3. [ ] **Measuring**: `khatt.text_bbox(text, font=, size_px=, stroke_width=)`, like
       Pillow's `textbbox`.
4. [ ] **Line spacing in pixels** (`spacing=`), alongside the `line_spacing` multiplier.
5. [ ] **Glyph coverage**: `khatt.font_covers(font, text)` → missing characters.
6. [ ] **`khatt.video.text_clip()`**: a moviepy-compatible Arabic caption clip (same
       options as moviepy's `TextClip`) behind an optional `khatt[video]` extra.
       Roadmap Phase 2's "moviepy captions", first slice.
7. [ ] Regression tests: the `بِتَ` mark-placement case against HarfBuzz's reference,
       vocalized Quran text, Persian/Urdu letters, identical output with and without
       Pillow's Raqm.

## Phase 1 — An image API that works everywhere

Ranked by value for effort.

1. [x] **`khatt.draw_text()` and `khatt.overlay(img, text, box, fit="shrink")`** (on main) —
       draw onto existing images with right-to-left wrapping and alignment, never
       double-shaping. Plus `khatt doctor`, which reports whether the environment
       shapes natively and warns about the reshaper recipe. *(S–M, high — automation,
       banners, certificates; n8n says Arabic in its Edit Image node is "not possible".)*
2. [ ] **Styled spans** — colour, weight or font per word or letter via HarfBuzz
       clusters, keeping diacritics. Needed for karaoke highlighting, tajweed colouring
       (Quran.com returns tajweed markup) and marketing emphasis. *(M, high.)*
3. [ ] **Font fallback chain + emoji** — Arabic font → Latin font → emoji, so mixed
       text never drops characters. *(M, high — Pillow #4808 open since 2020.)*
4. [ ] **Full `render_image()` options** — size in pixels, colours, transparent
       background, padding, alignment, line spacing, DPI; custom and system fonts
       (`font="path.ttf"`); variable-font weights.
5. [ ] Bundle **Amiri Quran** (OFL) for Quran text; accept user-supplied fonts. Do not
       bundle the KFGQPC Uthmani fonts (proprietary licence).

## Phase 2 — Motion and video

**Animation scope:** animate masks and colour over intact shaped text — never split
letters apart (that is what breaks joining in After Effects and Lottie).

1. [ ] **Word-timed animation export** — word highlight (karaoke) from timings (JSON,
       SRT, Whisper, Quran.com `segments`, Tarteel QUL), right-to-left wipe, word-by-word
       fade. Output MP4/WebM, GIF, APNG/WebP, or a moviepy clip. *(M, high — paid apps
       and freelance jobs exist for Quran word-highlight videos; no open-source
       generator found. Also the main star hook.)*
2. [ ] **moviepy captions** — an RGBA clip; SRT/ASS/Whisper in, burned-in captions
       out. *(M, high — moviepy has 4.2M downloads/month and long-open Arabic issues.)*
3. [ ] Contribute a khatt-based fix to **MoneyPrinterTurbo**: see the dedicated track
       below.
4. [ ] Terminal reveal effects only as marketing: first try piping khatt's output
       through `tte` for the README GIF; build native effects only if that fails.

## Track: MoneyPrinterTurbo Arabic subtitles (researched 2026-10-20)

**Principles:** khatt features stay general (see "Next release"); the MPT-specific
adapter lives in *their* repo. We go straight to our own PR when it's ready and don't
comment on other contributors' PRs. In our PR description, list related work neutrally
("Related: #1659, #1210, #1567") and say only what's different.

**Facts:** 133k★, one maintainer (harry0703) who merges outside PRs almost daily and
reviews deeply (runs the suite, renders real videos, compares with `hb-view`).
Subtitles: `app/services/video.py` → `wrap_text` (Pillow `getbbox`), `create_text_clip`
(three `TextClip` branches: plain, rectangle background, rounded background;
stroke colour/width, `interline`, centre alignment, margins) and `make_textclip`.
Code comments are in Simplified Chinese. CI: `uv sync --frozen`, compileall, ruff,
pytest + coverage on Python 3.11 / 3.13. Exact pins (`==`); Pillow 11.3.0 via moviepy 2.2.1.

**Why earlier Arabic PRs stalled:** #1659 (inline HarfBuzz/FreeType, +3k lines): marks
still misplaced in real renders (`بِتَ` +38px), awaiting re-review. #1210 (system Raqm):
needs FriBiDi on Windows / library paths on macOS, changed geometry for all languages,
died in rebase churn. #1567 (reshaper): dependencies not in `pyproject.toml`/`uv.lock`,
author went silent. #1523: reshaped forms rendered as boxes; scope creep. #1203: unwanted
README/translation maintenance.

**The maintainer's bar:** marks correct in the actual render (checked against
HarfBuzz) · works after a clean `uv sync --frozen` · with and without Raqm, no
double-shaping · Windows/macOS/Linux without system libraries · English/Chinese frames
pixel-identical · per-job (not per-process) warnings · small scope, rebased, ruff/tests
green · real multi-line vocalized video rendered · comments in Simplified Chinese.
khatt already passes his `بِتَ` test (0px growth vs Pillow's +44px).

- [ ] **A. khatt prerequisites**: the "Next release" list, then release v0.3.0.
- [ ] **B. Prototype in a fork**: baseline their gate; add `khatt[video]==0.3.x` to
      `pyproject.toml` + `requirements.txt` + `uv.lock`; route Arabic-script text only
      (Arabic, Persian, Urdu) through `khatt.video.text_clip` in `wrap_text`,
      `create_text_clip` (all three branches) and `make_textclip`; everything else keeps
      `TextClip`. If the chosen font lacks Arabic glyphs, fall back to khatt's bundled OFL
      font with a once-per-job warning. No UI strings, translations, README or system
      libraries.
- [ ] **C. Test to his bar**: unit tests (detection, wrap widths, clip geometry vs
      `TextClip`, branches, stroke, non-Arabic still `TextClip`); rendered regressions
      (`بِتَ` placement, joining, RTL order, multi-line vocalized, mixed Arabic/English/
      digits, پ چ گ ے ٹ); Raqm on/off parity; English/Chinese frames pixel-identical
      main vs branch; full H.264/AAC videos through `generate_video` for every subtitle
      style/position/stroke/animation; Windows + Linux (their Dockerfile) + macOS (fork CI);
      their full gate on 3.11 and 3.13.
- [ ] **D. Pre-submit check**: look at #1659/#1210/#1567's state. If #1659 has merged,
      re-pitch (Persian/Urdu/Hindi #1517, stroke quality) instead of replacing his new code.
- [ ] **E. Submit**: `fix(subtitle): shape Arabic-script subtitles with HarfBuzz via khatt`;
      a checklist mapping each earlier review point to evidence, before/after frames,
      test commands and results, platforms, dependency facts (MIT, wheels, no system
      libraries); disclose that you maintain khatt and that the code is AI-assisted.
      Rebase within hours when `main` moves, answer reviews within a day, never swallow
      import errors. After merge: "Used by MoneyPrinterTurbo" in the README.

## Phase 3 — Integrations and outputs

- [ ] **SVG with merged outlines** (single cut paths, e.g. via skia-pathops) for
      Cricut/laser makers and designers; also a route around Lottie's lack of Arabic.
      *(M, medium.)*
- [ ] **Synthetic OCR data generator** — logical-order labels, glyph/word boxes, scan
      degradations, export to Hugging Face datasets. *(M, medium-high; ML audience.)*
- [ ] **Docker image + HTTP API** (FastAPI) for no-code tools and JS developers making
      OG images. *(S–M, medium.)*
- [ ] **MCP server** with a `render_arabic` tool for AI agents (exact text such as
      verses, names and prices needs deterministic rendering). *(S, medium; thin
      demand evidence, good visibility.)*
- [ ] **wordcloud adapter** (#723 open since 2023). *(S–M, medium.)*
- [ ] **Batch templates** — CSV → certificates, product cards, social-media size
      presets. *(S once Phase 1 item 1 exists.)*
- [ ] OpenCV and ComfyUI helpers. *(S each, low–medium.)*

## Phase 4 — Arabizi

Rendering Arabizi as-is already works (every bundled font covers Latin).

- [ ] Arabizi detection (Latin letters plus digits such as 2/3/5/7/9 used as letters).
- [ ] Optional `khatt[arabizi]` extra that **wraps existing tools** (arabizi-kit, MIT;
      darija-tools for Moroccan) with a `dialect=` option and user dictionary overrides.
- [ ] "Show both" mode: the Arabizi and its Arabic rendering together.
- [ ] Opt-in only, never silent — Arabizi has no standard spelling, so conversion is
      inherently ambiguous.

## Terminal (low priority)

- [ ] ANSI colour and gradients; `halfblocks` style (`▀▄`); `--align`.
- [ ] `khatt --version` and `python -m khatt`.
- [ ] Rich renderable only as a cheap extra (no Arabic demand found in Rich's issues).

## Launch plan

**Weeks 0–2 — assets**

- [x] License fix (done in v0.2.0; GitHub detects MIT).
- [ ] Hero GIF recorded with VHS (keep the `.tape` file in the repo): `uvx khatt
      "مرحبا"` plus a before/after against broken Pillow output.
- [ ] Live Hugging Face Space, linked in the repo's homepage field (empty today).
- [ ] `uvx khatt "مرحبا"` one-liner and live-demo link at the top of the README.
- [ ] Gallery page on GitHub Pages: every font × style (the link to share on HN).
- [ ] Blog post: "Why Arabic breaks in terminals and FIGlet, and how HarfBuzz fixes it."
- [ ] Social preview image (1280×640); add topics `terminal-art`, `braille`,
      `text-rendering`, `pillow`.
- [ ] Arabic README section or `README.ar.md`; issue/PR templates and a code of
      conduct; 5–10 labelled good-first-issues (fonts, effects, Arabizi mappings).
- [x] Release v0.2.0 with one visible new feature (art as images).

**Week 3 — one channel per day; stay to answer comments**

- [ ] **Show HN** — must be tryable without signup; write the text yourself; never ask
      for upvotes. Submit the blog post 1–2 weeks later as a normal story.
- [ ] **r/Python** — only in the monthly showcase / daily thread (standalone showcase
      posts are banned); sections: What My Project Does / Target Audience / Comparison.
- [ ] **r/commandline** — list alternatives (figlet, toilet, araste); **disclose
      AI-assisted code**; no AI-written post text.
- [ ] **r/arabs** — message the moderators first; Arabic is welcome.
- [ ] Newsletters and directories: Python Bytes (contact@pythonbytes.fm), PyCoder's
      Weekly, Console.dev (beta section), Terminal Trove.
- [ ] Arabic channels: Hsoub I/O programming community; posts tagging the Amiri and
      Cairo font authors (unverified reach).

**Awesome lists**

- [ ] Now (no star minimum): awesome-arabic, awesome-cli-apps-in-a-csv,
      awesome-typography (show you use it, explain why it's better, disclose you
      maintain it), awesome-rtl.
- [ ] At 20★: awesome-cli-apps (Data Manipulation › Text; one PR "Add khatt").
- [ ] At 50★: awesome-shell.
- [ ] Skip awesome-python until the project is production-stable with real downloads.

**After launch:** re-announce only substantial releases, each with a write-up; release
regularly.

## Quality bar — every phase

- [ ] Docs site in English and Arabic: API reference plus a cookbook.
- [ ] API stability policy: semantic versioning; deprecation warnings for at least one
      minor release before removal.
- [ ] Image snapshot tests with a small pixel tolerance, alongside the text goldens.
- [ ] Property-based tests (Hypothesis): no Unicode input ever crashes rendering.
- [ ] Tests that khatt's output is identical with and without native Raqm shaping.
- [ ] Rendering benchmarks tracked in CI.
- [ ] Python 3.14 in the CI matrix; decide on Python 3.10 (end of life October 2026).
- [ ] Release workflow gated on the test suite; wheel-install smoke test in CI.

## Not planned (and why)

- **matplotlib integration** — 3.11 shapes Arabic natively; a docs note is enough.
- **Streamlit, plotly, manim, PDF engines** — browsers, Pango, WeasyPrint, fpdf2 and
  ReportLab already handle Arabic.
- **JS/WASM port** — browsers shape Arabic natively; harfbuzzjs exists.
- **Our own Arabizi model** — wrap existing tools instead.
- **True stroke-by-stroke handwriting animation** — fonts store outlines, not stroke
  order; Tegaki already fakes it and the order isn't correct for teaching.
- **Generic kinetic typography or a terminal effects library** — no demand found.
- **Engine B (hand-drawn FIGlet-style fonts)**, **image-to-ASCII**, **LED/Arduino
  exporters**, **Product Hunt launch**.
- **Bundling many fonts** — keeps the wheel small; prefer custom/system fonts.

## References

- Ecosystem: [matplotlib 3.11 — complex text layout](https://matplotlib.org/stable/release/prev_whats_new/whats_new_3.11.0) ·
  [Pillow #9926](https://github.com/python-pillow/Pillow/pull/9926) ·
  [Pillow #4808](https://github.com/python-pillow/Pillow/issues/4808) ·
  [wordcloud #723](https://github.com/amueller/word_cloud/issues/723)
- Demand: [MoneyPrinterTurbo #1567](https://github.com/harry0703/MoneyPrinterTurbo/pull/1567) ·
  [n8n Arabic in Edit Image](https://community.n8n.io/t/edit-image-node-arabic-text/60798) ·
  [Quran.com API](https://api-docs.quran.com/docs/content_apis_versioned/chapter-reciter-audio-file/) ·
  [Tarteel QUL](https://qul.tarteel.ai/) ·
  [Quran Captions app](https://apps.apple.com/us/app/quran-captions/id6761422097) ·
  [Freelancer Quran video job](https://www.freelancer.ca/projects/motion-graphics/youtube-qur-video-modernization) ·
  [Tegaki](https://github.com/KurtGokhan/tegaki) ·
  [TRDG Arabic issues](https://github.com/Belval/TextRecognitionDataGenerator/issues?q=arabic)
- Growth: [TTE on HN (1,830 pts)](https://news.ycombinator.com/item?id=40503202) ·
  [Arabic typography on HN (287 pts)](https://news.ycombinator.com/item?id=48516710) ·
  [Will McGugan on the first 1k stars](https://web.archive.org/web/20240625144953/https://www.willmcgugan.com/blog/tech/post/promoting-your-open-source-project-or-how-to-get-your-first-1k-github-stars/) ·
  [HN launch study](https://arxiv.org/abs/2511.04453v1) ·
  [Show HN rules](https://news.ycombinator.com/showhn.html) ·
  [r/commandline rules (archived)](https://web.archive.org/web/20260811152913/https://old.reddit.com/r/commandline/about/rules)
- Awesome lists: [awesome-arabic](https://github.com/01walid/awesome-arabic) ·
  [awesome-cli-apps](https://github.com/agarrharr/awesome-cli-apps) ·
  [awesome-cli-apps-in-a-csv](https://github.com/toolleeo/awesome-cli-apps-in-a-csv) ·
  [awesome-typography](https://github.com/Jolg42/awesome-typography) ·
  [awesome-shell](https://github.com/alebcay/awesome-shell)
- Arabizi: [arabizi-kit](https://huggingface.co/rabeeeehh/arabizi-kit-model) ·
  [darija-tools](https://pypi.org/project/darija-tools/)
- Download counts: pypistats.org (October 2026).
