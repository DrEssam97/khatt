# Roadmap

## v0.1.0 — Engine A (rasterize-then-map)

The current milestone. HarfBuzz shaping → FreeType rasterization → density mapping to
`blocks` / `ascii` / `braille` ramps, with a Python API, a `khatt` CLI, and a Gradio app.
See [PLAN.md](PLAN.md) for the full breakdown.

## Explicitly out of scope for v0.1.0

Recorded here so they don't creep in early:

- **Engine B — hand-crafted connected FIGlet-style Arabic fonts.** Designed glyph-art
  letterforms with explicit joining rules, rather than rasterized real fonts. The
  long-term differentiator, but a font-design project of its own.
- **Color / ANSI output.** Escape-code coloring of the rendered art.
- **Animation.** Scrolling marquees, reveal effects.
- **Image-to-ASCII.** General bitmap input; Khatt v0.1.0 renders text only.
