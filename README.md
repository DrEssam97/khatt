# خَطّ — Khatt

Render Arabic text as ASCII/Unicode-block art — the Arabic FIGlet that FIGlet can't be.

> **Status:** under construction (v0.1.0 in progress). See [PLAN.md](PLAN.md) and
> [ROADMAP.md](ROADMAP.md).

FIGlet's per-character glyph model cannot handle Arabic: contextual shaping
(isolated/initial/medial/final positional forms), mandatory ligatures like لا, cursive
joining, and right-to-left layout all break it. Khatt uses a **rasterize-then-map**
pipeline instead: shape the text with HarfBuzz, render it with a real Arabic font, then
map pixel density onto character ramps (`blocks`, `ascii`, `braille`).

A full README with demo output, install instructions, and quickstarts lands with the
v0.1.0 release.

## License

MIT for the code. Bundled fonts are under the SIL Open Font License 1.1 — see
`khatt/fonts/LICENSES/`.
