"""Gradio app for khatt (خَطّ) — Arabic text as ASCII/Unicode-block art.

Single file by design: push this repository to a Hugging Face Space with the
Gradio SDK and it deploys unchanged (see README, "Deploy to a Space").
"""

from __future__ import annotations

import tempfile
import warnings

import gradio as gr
from PIL import ImageOps

import khatt
from khatt.fonts import font_path
from khatt.raster import rasterize
from khatt.shaping import shape

CSS = """
#khatt-output textarea {
    font-family: ui-monospace, "Cascadia Mono", Consolas, Menlo, monospace;
    white-space: pre;
    overflow-x: auto;
    direction: ltr;
    line-height: 1.1;
}
"""


def render_art(
    text: str, font: str, style: str, width: float, threshold: float
) -> tuple[str, str | None]:
    """Render the art and a downloadable PNG of the shaped text."""
    if not text.strip():
        return "", None

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # unsupported chars degrade silently in the UI
        art = khatt.render(
            text,
            font=font,
            style=style,
            width=int(width),
            threshold=threshold or None,  # slider at 0 means "off"
        )

    png_path: str | None = None
    path = font_path(font)
    image = rasterize(shape(text, path), path)
    if image is not None:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as handle:
            png_path = handle.name
        ImageOps.invert(image).save(png_path)

    return art, png_path


with gr.Blocks(title="خط — Khatt") as demo:
    gr.Markdown(
        "# خط — Khatt\n"
        "Render Arabic text as ASCII/Unicode-block art — with real shaping: "
        "positional forms, ligatures and right-to-left layout.\n\n"
        "اكتب نصًا عربيًا وشاهده يتحول إلى فن حروف."
    )
    with gr.Row():
        with gr.Column(scale=1):
            text_in = gr.Textbox(label="النص / Text", value="مرحبا", rtl=True, lines=2)
            font_in = gr.Dropdown(khatt.list_fonts(), value="amiri", label="Font")
            style_in = gr.Dropdown(khatt.list_styles(), value="blocks", label="Style")
            width_in = gr.Slider(20, 200, value=80, step=2, label="Width (columns)")
            threshold_in = gr.Slider(0.0, 0.95, value=0.0, step=0.05, label="Threshold (0 = off)")
        with gr.Column(scale=2):
            art_out = gr.Textbox(
                label="Art",
                lines=22,
                elem_id="khatt-output",
                buttons=["copy"],
                interactive=False,
            )
            png_out = gr.File(label="PNG of the rendered text")

    controls = [text_in, font_in, style_in, width_in, threshold_in]
    outputs = [art_out, png_out]
    for control in controls:
        control.change(render_art, controls, outputs)
    demo.load(render_art, controls, outputs)


if __name__ == "__main__":
    demo.launch(css=CSS)
