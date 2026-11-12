"""The ``khatt`` command-line interface."""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import warnings
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from PIL import Image, ImageColor, ImageOps

import khatt
from khatt.art_image import paint
from khatt.doctor import format_report
from khatt.draw import WORD_ART_FONT
from khatt.fonts import available_fonts

_COLOURS = {"red": "31", "yellow": "33"}


def _enable_ansi(stream: TextIO) -> bool:
    """Turn on colour codes in a Windows console; other terminals have them on."""
    if sys.platform != "win32":
        return True
    try:
        import ctypes
        import msvcrt

        kernel32 = ctypes.windll.kernel32
        handle = msvcrt.get_osfhandle(stream.fileno())
        mode = ctypes.c_uint32()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        return bool(kernel32.SetConsoleMode(handle, mode.value | 0x0004))
    except (AttributeError, OSError, ValueError):
        return False


def _say(message: str, *, err: bool = False, colour: str | None = None) -> None:
    """Print a line to stdout, or stderr, in colour when that is a terminal."""
    stream = sys.stderr if err else sys.stdout
    if (
        colour is not None
        and "NO_COLOR" not in os.environ
        and stream.isatty()
        and _enable_ansi(stream)
    ):
        message = f"\033[{_COLOURS[colour]}m{message}\033[0m"
    print(message, file=stream)


def _fail(message: str, code: int) -> SystemExit:
    """Report an error in red; the caller raises the exit this returns."""
    _say(f"error: {message}", err=True, colour="red")
    return SystemExit(code)


def _warn(caught: list[warnings.WarningMessage]) -> None:
    for warning in caught:
        _say(f"warning: {warning.message}", err=True, colour="yellow")


def _whole(value: str) -> int:
    """A whole number of 1 or more, for ``--width``, ``--size`` and ``--size-px``."""
    try:
        number = int(value)
    except ValueError:
        number = 0
    if number < 1:
        raise argparse.ArgumentTypeError(f"{value!r} is not a whole number of 1 or more")
    return number


def _fraction(value: str) -> float:
    """A number from 0 to 1, for ``--threshold``."""
    try:
        number = float(value)
    except ValueError:
        number = -1.0
    if not 0.0 <= number <= 1.0:
        raise argparse.ArgumentTypeError(f"{value!r} is not a number from 0 to 1")
    return number


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


def _color(parser: argparse.ArgumentParser, option: str, value: str) -> str:
    """Validate a ``--fg``/``--bg`` colour (a Pillow colour name or ``#rrggbb``)."""
    try:
        ImageColor.getrgb(value)
    except ValueError:
        parser.error(f"argument {option}: unknown colour {value!r}")
    return value


def _save_png(
    art: str,
    text: str,
    *,
    content: str,
    font: str,
    keep_tashkeel: bool,
    fg: str,
    bg: str | None,
    target: Path,
) -> None:
    """Save the text art drawn as an image, or the plain high-resolution text."""
    if content == "art":
        image = khatt.art_to_image(art, fg=fg, bg=bg)
    else:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # already reported while rendering the art
            plain = khatt.render_image(text, font=font, keep_tashkeel=keep_tashkeel)
        image = None if plain is None else paint(ImageOps.invert(plain), fg, bg)
    if image is None:  # unreachable normally: empty art exits earlier
        raise SystemExit(1)
    image.save(target)


def _save_calligram(
    text: str,
    *,
    shape: str,
    effect: str | None,
    font: str,
    size_px: int | None,
    repeat: bool,
    fill: str,
    keep_tashkeel: bool,
    background: str | None,
    target: Path | None,
) -> None:
    """Save ``text`` flowing inside ``shape``: a preset name or an image file."""
    if target is None or target.suffix.lower() != ".png":
        raise _fail("--shape draws an image; pass --output with a .png name", 2)
    outline: str | Image.Image = shape
    if Path(shape).expanduser().is_file():
        try:
            outline = Image.open(Path(shape).expanduser())
            outline.load()
        except OSError as exc:
            raise _fail(f"cannot read the shape image {shape}", 2) from exc
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            image = khatt.calligram(
                text,
                outline,
                font=font,
                size_px=size_px,
                repeat=repeat,
                fill=fill,
                effect=effect,
                keep_tashkeel=keep_tashkeel,
                background=background,
            )
        except (KeyError, ValueError) as exc:  # unknown name, unusable shape image
            raise _fail(str(exc.args[0]), 2) from exc
    _warn(caught)
    if image is None:
        raise _fail("no renderable characters in input", 1)
    image.save(target)
    _say(f"wrote {target}", err=True)


def _save_word_art(
    text: str,
    *,
    effect: str,
    curve: str | None,
    font: str,
    size_px: int,
    keep_tashkeel: bool,
    background: str | None,
    target: Path | None,
) -> None:
    """Save ``text`` as word art; a preset and a ``.png`` target are required."""
    if target is None or target.suffix.lower() != ".png":
        raise _fail("--effect and --curve draw an image; pass --output with a .png name", 2)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            image = khatt.word_art(
                text,
                effect=effect,
                curve=curve,
                font=font,
                size_px=size_px,
                keep_tashkeel=keep_tashkeel,
                background=background,
            )
        except (KeyError, ValueError) as exc:  # unknown name, bad size, text too short to bend
            raise _fail(str(exc.args[0]), 2) from exc
    _warn(caught)
    if image is None:
        raise _fail("no renderable characters in input", 1)
    image.save(target)
    _say(f"wrote {target}", err=True)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="khatt", description="Render Arabic text as ASCII/Unicode-block art."
    )
    parser.add_argument(
        "text", nargs="?", help="Text to render. Omit (or pass '-') to read from stdin."
    )
    parser.add_argument(
        "-f",
        "--font",
        help="Font name (see --list-fonts), style name, or the path to a .ttf/.otf file. "
        f"Default: amiri, or {WORD_ART_FONT} with --effect.",
    )
    parser.add_argument("-s", "--style", default="blocks", help="Output style.")
    parser.add_argument(
        "-w",
        "--width",
        type=_whole,
        help="Maximum output width in columns (default: the terminal width); "
        "longer lines wrap at spaces.",
    )
    parser.add_argument(
        "--size",
        type=_whole,
        default=khatt.DEFAULT_SIZE,
        help=f"Font size in character rows per em. Default: {khatt.DEFAULT_SIZE}.",
    )
    parser.add_argument(
        "--fit",
        action="store_true",
        help="Scale the text to fill the width exactly instead of wrapping (ignores --size).",
    )
    parser.add_argument(
        "-t",
        "--threshold",
        type=_fraction,
        help="Coverage cutoff in [0, 1]; below it cells render blank.",
    )
    parser.add_argument(
        "--keep-tashkeel",
        action="store_true",
        help="Keep Arabic diacritics. Default: stripped in the art "
        "(illegible at character-grid resolution), kept in '--png text' images.",
    )
    parser.add_argument(
        "--strip-tashkeel",
        dest="keep_tashkeel",
        action="store_false",
        help="Strip Arabic diacritics, also from '--png text' images.",
    )
    parser.set_defaults(keep_tashkeel=None)
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Write to a file: .png saves an image (see --png), .svg the text as vector "
        "outlines, any other extension saves the text art.",
    )
    parser.add_argument(
        "--png",
        choices=("art", "text"),
        default="art",
        help="What a .png --output contains: 'art' draws the text art itself "
        "(in the chosen --style), 'text' the plain high-resolution text. Default: art.",
    )
    parser.add_argument(
        "--fg", default="black", help="Ink colour of .png output (name or #rrggbb)."
    )
    parser.add_argument(
        "--bg",
        help="Background colour of .png output, or 'none' for transparent. "
        "Default: white, or transparent with --effect.",
    )
    parser.add_argument(
        "-e",
        "--effect",
        help="Draw word art with this effect instead of text art; needs a .png --output.",
    )
    parser.add_argument(
        "--curve",
        help="Bend word art along this curve, with the gold effect unless --effect says "
        "otherwise; needs a .png --output.",
    )
    parser.add_argument(
        "--shape",
        help="Flow the text inside a shape: a preset (see --list-shapes) or an image file whose "
        "dark or opaque pixels are the inside. Needs a .png --output.",
    )
    parser.add_argument(
        "--repeat",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="With --shape: repeat the text until the shape is full, or fit it in once.",
    )
    parser.add_argument(
        "--size-px",
        type=_whole,
        help="Font size of word art (default 160) or of --shape text (default: to suit the "
        "shape), in pixels.",
    )
    parser.add_argument(
        "-z",
        "--zakhrafa",
        help="Print the text decorated in this zakhrafa style, to copy and paste, or 'all' "
        "for every style.",
    )
    for name in ("curves", "effects", "fonts", "shapes", "styles"):
        parser.add_argument(f"--list-{name}", action="store_true", help=f"List {name} and exit.")
    parser.add_argument(
        "--doctor",
        action="store_true",
        help="Check which Arabic shaping engines are installed (and double-shaping risks), "
        "then exit. With a folder or .py file as the text, also list where it pre-shapes "
        "Arabic with arabic_reshaper or get_display.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    """Run the ``khatt`` command with ``argv`` (default: the command line)."""
    parser = _parser()
    options = parser.parse_args(argv)
    text: str | None = options.text
    font: str | None = options.font
    style: str = options.style
    width: int | None = options.width
    size: int = options.size
    fit: bool = options.fit
    threshold: float | None = options.threshold
    keep_tashkeel: bool | None = options.keep_tashkeel
    output: Path | None = options.output
    png: str = options.png
    fg: str = options.fg
    bg: str | None = options.bg
    effect: str | None = options.effect
    curve: str | None = options.curve
    shape: str | None = options.shape
    repeat: bool = options.repeat
    size_px: int | None = options.size_px
    zakhrafa: str | None = options.zakhrafa
    _configure_utf8_output()

    if options.doctor:
        # Text that names a folder or file is scanned; any other text is ignored.
        target = text if text and text != "-" else None
        looks_like_a_path = target is not None and (
            "/" in target or "\\" in target or target.endswith(".py")
        )
        if target is not None and not Path(target).exists() and not looks_like_a_path:
            target = None
        try:
            report = khatt.doctor(target)
        except FileNotFoundError as exc:
            raise _fail(str(exc), 2) from exc
        for line in format_report(report):
            _say(line, colour="yellow" if line.startswith("warning:") else None)
        return
    if options.list_fonts:
        for name in available_fonts():
            _say(name)
        return
    if options.list_styles:
        for name in khatt.list_styles():
            _say(name)
        return

    if options.list_effects:
        for name in khatt.list_effects():
            _say(name)
        return
    if options.list_curves:
        for name in khatt.list_curves():
            _say(name)
        return
    if options.list_shapes:
        for name in khatt.list_shapes():
            _say(name)
        return
    if zakhrafa is not None:
        if text is None or text == "-":
            text = sys.stdin.read()
        text = text.rstrip("\n")
        name = zakhrafa.strip().lower()
        try:
            if name == "all":
                width = max(len(style) for style in khatt.list_zakhrafa())
                for style in khatt.list_zakhrafa():
                    _say(f"{style:<{width}}  {khatt.zakhrafa(text, style)}")
            else:
                _say(khatt.zakhrafa(text, name))
        except KeyError as exc:
            raise _fail(str(exc.args[0]), 2) from exc
        return
    if shape is not None and curve is not None:
        raise _fail("pass --shape or --curve, not both", 2)

    word_art = effect is not None or curve is not None or shape is not None
    ink = _color(parser, "--fg", fg)
    backdrop = bg if bg is not None else ("none" if word_art else "white")
    background = (
        None
        if backdrop.strip().lower() in ("none", "transparent")
        else _color(parser, "--bg", backdrop)
    )
    if text is None or text == "-":
        text = sys.stdin.read()
    text = text.rstrip("\n")

    if shape is not None:
        _save_calligram(
            text,
            shape=shape,
            effect=effect,
            font="amiri" if font is None else font,
            size_px=size_px,
            repeat=repeat,
            fill=ink,
            keep_tashkeel=keep_tashkeel is not False,
            background=background,
            target=output,
        )
        return
    if word_art:
        _save_word_art(
            text,
            effect="gold" if effect is None else effect,
            curve=curve,
            font=WORD_ART_FONT if font is None else font,
            size_px=160 if size_px is None else size_px,
            keep_tashkeel=keep_tashkeel is not False,
            background=background,
            target=output,
        )
        return
    font = "amiri" if font is None else font

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
        except (KeyError, ValueError) as exc:  # unknown font, unusable font file
            raise _fail(str(exc.args[0]), 2) from exc
    _warn(caught)

    if not art and text.strip():
        raise _fail("no renderable characters in input", 1)

    if output is None:
        _say(art)
    elif output.suffix.lower() == ".svg":
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # already reported while rendering the art
            svg = khatt.render_svg(
                text,
                font=font,
                size_px=160 if size_px is None else size_px,
                fill=ink,
                keep_tashkeel=keep_tashkeel is not False,
                background=None if bg is None else background,
            )
        if svg is None:  # unreachable normally: empty art exits earlier
            raise SystemExit(1)
        output.write_text(svg, encoding="utf-8")
        _say(f"wrote {output}", err=True)
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
        _say(f"wrote {output}", err=True)
    else:
        output.write_text(art + "\n", encoding="utf-8")
        _say(f"wrote {output}", err=True)
