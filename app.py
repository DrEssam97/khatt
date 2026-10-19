"""Gradio app for khatt (خَطّ) — Arabic text as ASCII/Unicode-block art.

Single file by design: push this repository to a Hugging Face Space with the
Gradio SDK and it deploys unchanged (see README, "Deploy to a Space").
"""

from __future__ import annotations

import warnings

import gradio as gr
from PIL import Image

import khatt

CSS = """
#khatt-output textarea {
    font-family: ui-monospace, "Cascadia Mono", Consolas, Menlo, monospace;
    white-space: pre;
    overflow-x: auto;
    direction: ltr;
    line-height: 1.1;
}
"""

# Gradio stores every returned image in its cache; prune files older than an
# hour, every hour, so a long-running Space doesn't fill its disk.
CACHE_PRUNING = (3600, 3600)


def render_art(
    text: str,
    font: str,
    style: str,
    width: float,
    size: float,
    fit: bool,
    threshold: float,
) -> tuple[str, Image.Image | None]:
    """Render the art and a PNG preview of the shaped text."""
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
            size=None if fit else int(size),
        )
        image = khatt.render_image(text, font=font)
    return art, image


with gr.Blocks(title="خط — Khatt", delete_cache=CACHE_PRUNING) as demo:
    gr.Markdown(
        "# خط — Khatt\n"
        "Render Arabic text as ASCII/Unicode-block art — with real shaping: "
        "positional forms, ligatures and right-to-left layout.\n\n"
        "اكتب نصًا عربيًا وشاهده يتحول إلى فن حروف."
    )
    with gr.Row():
        with gr.Column(scale=1):
            text_in = gr.Textbox(label="النص / Text", value="مرحبا", rtl=True, lines=3)
            font_in = gr.Dropdown(khatt.list_fonts(), value="amiri", label="Font")
            style_in = gr.Dropdown(khatt.list_styles(), value="blocks", label="Style")
            width_in = gr.Slider(20, 200, value=80, step=2, label="Max width (columns)")
            size_in = gr.Slider(4, 30, value=khatt.DEFAULT_SIZE, step=1, label="Size (rows per em)")
            fit_in = gr.Checkbox(
                label="Fill width",
                info="Scale the text to exactly the max width instead of wrapping.",
            )
            threshold_in = gr.Slider(0.0, 0.95, value=0.0, step=0.05, label="Threshold (0 = off)")
        with gr.Column(scale=2):
            art_out = gr.Textbox(
                label="Art",
                lines=22,
                elem_id="khatt-output",
                buttons=["copy"],
                interactive=False,
            )
            png_out = gr.Image(
                label="Rendered text (PNG)",
                type="pil",
                format="png",
                buttons=["download"],
                interactive=False,
            )

    controls = [text_in, font_in, style_in, width_in, size_in, fit_in, threshold_in]
    outputs = [art_out, png_out]
    for control in controls:
        control.change(render_art, controls, outputs, trigger_mode="always_last")
    demo.load(render_art, controls, outputs)


if __name__ == "__main__":
    demo.launch(css=CSS)
