"""The ``khatt`` command-line interface."""

from __future__ import annotations

import shutil
import sys
import warnings
from pathlib import Path

import typer

import khatt
from khatt.fonts import available_fonts

app = typer.Typer(add_completion=False)


def _configure_utf8_output() -> None:
    """Force UTF-8 on stdout/stderr; Windows consoles often default to a
    legacy code page that cannot encode Arabic or block characters."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")


def _terminal_width() -> int:
    """Columns of the attached terminal (honours ``COLUMNS``), else 80."""
    columns = shutil.get_terminal_size(fallback=(80, 24)).columns
    return columns if columns > 0 else 80


def _save_png(text: str, font: str, keep_tashkeel: bool, target: Path) -> None:
    """PNG output saves the high-resolution rendered text (black on white),
    not the character art — image viewers can't display text art anyway."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # already reported while rendering the art
        image = khatt.render_image(text, font=font, keep_tashkeel=keep_tashkeel)
    if image is None:  # unreachable normally: empty art exits earlier
        raise typer.Exit(code=1)
    image.save(target)


@app.command()
def main(
    text: str | None = typer.Argument(
        None,
        help="Text to render. Omit (or pass '-') to read from stdin.",
        show_default=False,
    ),
    font: str = typer.Option("amiri", "--font", "-f", help="Bundled font name."),
    style: str = typer.Option("blocks", "--style", "-s", help="Output style."),
    width: int | None = typer.Option(
        None,
        "--width",
        "-w",
        min=1,
        help="Maximum output width in columns (default: the terminal width); "
        "longer lines wrap at spaces.",
        show_default=False,
    ),
    size: int = typer.Option(
        khatt.DEFAULT_SIZE, "--size", min=1, help="Font size in character rows per em."
    ),
    fit: bool = typer.Option(
        False,
        "--fit",
        help="Scale the text to fill the width exactly instead of wrapping (ignores --size).",
    ),
    threshold: float | None = typer.Option(
        None,
        "--threshold",
        "-t",
        min=0.0,
        max=1.0,
        help="Coverage cutoff in [0, 1]; below it cells render blank.",
    ),
    keep_tashkeel: bool | None = typer.Option(
        None,
        "--keep-tashkeel/--strip-tashkeel",
        help="Keep or strip Arabic diacritics. Default: stripped in text art "
        "(illegible at character-grid resolution), kept in .png output.",
        show_default=False,
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Write to a file: .png saves the rendered text as an image, "
        "any other extension saves the text art.",
    ),
    list_fonts: bool = typer.Option(False, "--list-fonts", help="List bundled fonts and exit."),
    list_styles: bool = typer.Option(False, "--list-styles", help="List styles and exit."),
) -> None:
    """Render Arabic text as ASCII/Unicode-block art."""
    _configure_utf8_output()

    if list_fonts:
        for name in available_fonts():
            typer.echo(name)
        raise typer.Exit()
    if list_styles:
        for name in khatt.list_styles():
            typer.echo(name)
        raise typer.Exit()

    if text is None or text == "-":
        text = sys.stdin.read()
    text = text.rstrip("\n")

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            art = khatt.render(
                text,
                font=font,
                style=style,
                width=width if width is not None else _terminal_width(),
                threshold=threshold,
                size=None if fit else size,
                keep_tashkeel=bool(keep_tashkeel),
            )
        except KeyError as exc:
            typer.secho(f"error: {exc.args[0]}", err=True, fg=typer.colors.RED)
            raise typer.Exit(code=2) from exc
    for warning in caught:
        typer.secho(f"warning: {warning.message}", err=True, fg=typer.colors.YELLOW)

    if not art and text.strip():
        typer.secho("error: no renderable characters in input", err=True, fg=typer.colors.RED)
        raise typer.Exit(code=1)

    if output is None:
        typer.echo(art)
    elif output.suffix.lower() == ".png":
        _save_png(text, font, keep_tashkeel is not False, output)
        typer.secho(f"wrote {output}", err=True)
    else:
        output.write_text(art + "\n", encoding="utf-8")
        typer.secho(f"wrote {output}", err=True)
