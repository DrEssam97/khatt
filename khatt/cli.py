"""The ``khatt`` command-line interface."""

from __future__ import annotations

import shutil
import sys
import warnings
from enum import Enum
from pathlib import Path

import typer
from PIL import ImageColor, ImageOps

import khatt
from khatt.art_image import paint
from khatt.doctor import format_report
from khatt.fonts import available_fonts

app = typer.Typer(add_completion=False)


class PngContent(str, Enum):
    """What a ``.png`` ``--output`` contains."""

    art = "art"
    text = "text"


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


def _color(value: str) -> str:
    """Validate a ``--fg``/``--bg`` colour (a Pillow colour name or ``#rrggbb``)."""
    try:
        ImageColor.getrgb(value)
    except ValueError as exc:
        raise typer.BadParameter(f"unknown colour {value!r}") from exc
    return value


def _save_png(
    art: str,
    text: str,
    *,
    content: PngContent,
    font: str,
    keep_tashkeel: bool,
    fg: str,
    bg: str | None,
    target: Path,
) -> None:
    """Save the text art drawn as an image, or the plain high-resolution text."""
    if content is PngContent.art:
        image = khatt.art_to_image(art, fg=fg, bg=bg)
    else:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # already reported while rendering the art
            plain = khatt.render_image(text, font=font, keep_tashkeel=keep_tashkeel)
        image = None if plain is None else paint(ImageOps.invert(plain), fg, bg)
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
        help="Keep or strip Arabic diacritics. Default: stripped in the art "
        "(illegible at character-grid resolution), kept in '--png text' images.",
        show_default=False,
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Write to a file: .png saves an image (see --png), "
        "any other extension saves the text art.",
    ),
    png: PngContent = typer.Option(
        PngContent.art,
        "--png",
        help="What a .png --output contains: 'art' draws the text art itself "
        "(in the chosen --style), 'text' the plain high-resolution text.",
    ),
    fg: str = typer.Option("black", "--fg", help="Ink colour of .png output (name or #rrggbb)."),
    bg: str = typer.Option(
        "white", "--bg", help="Background colour of .png output, or 'none' for transparent."
    ),
    list_fonts: bool = typer.Option(False, "--list-fonts", help="List bundled fonts and exit."),
    list_styles: bool = typer.Option(False, "--list-styles", help="List styles and exit."),
    doctor: bool = typer.Option(
        False,
        "--doctor",
        help="Check which Arabic shaping engines are installed (and double-shaping risks), "
        "then exit.",
    ),
) -> None:
    """Render Arabic text as ASCII/Unicode-block art."""
    _configure_utf8_output()

    if doctor:
        for line in format_report(khatt.doctor()):
            if line.startswith("warning:"):
                typer.secho(line, fg=typer.colors.YELLOW)
            else:
                typer.echo(line)
        raise typer.Exit()
    if list_fonts:
        for name in available_fonts():
            typer.echo(name)
        raise typer.Exit()
    if list_styles:
        for name in khatt.list_styles():
            typer.echo(name)
        raise typer.Exit()

    ink = _color(fg)
    background = None if bg.strip().lower() in ("none", "transparent") else _color(bg)
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
        _save_png(
            art,
            text,
            content=png,
            font=font,
            keep_tashkeel=keep_tashkeel is not False,
            fg=ink,
            bg=background,
            target=output,
        )
        typer.secho(f"wrote {output}", err=True)
    else:
        output.write_text(art + "\n", encoding="utf-8")
        typer.secho(f"wrote {output}", err=True)
