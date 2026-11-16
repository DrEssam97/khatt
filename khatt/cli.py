"""The ``khatt`` command-line interface."""

from __future__ import annotations

import argparse
import contextlib
import os
import shutil
import sys
import warnings
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from PIL import Image, ImageColor, ImageOps

import khatt
from khatt.animate import EFFECTS as ANIMATIONS
from khatt.animate import animate
from khatt.art_image import paint
from khatt.doctor import format_report
from khatt.draw import WORD_ART_FONT
from khatt.fetch import fetch, fetch_image
from khatt.fonts import available_fonts
from khatt.palette import DIRECTIONS, Palette, palette_colors
from khatt.terminal import TERMINAL_MODES, terminal_shapes_arabic

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


def _color_mode(choice: str, stream: TextIO) -> str | None:
    """Terminal colour codes to print with: ``"truecolor"``, ``"256"`` or ``None``.

    ``auto`` colours only a terminal, and never with ``NO_COLOR`` set. 24-bit colour is
    used where the terminal says it has it (``COLORTERM``, Windows Terminal), else the
    256 colours every colour terminal has.
    """
    if choice == "never":
        return None
    if choice == "auto" and ("NO_COLOR" in os.environ or not stream.isatty()):
        return None
    if not _enable_ansi(stream) and choice == "auto":
        return None
    deep = os.environ.get("COLORTERM", "").lower() in ("truecolor", "24bit")
    return "truecolor" if deep or "WT_SESSION" in os.environ else "256"


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
    palette: Palette | None = None,
    direction: str = "rtl",
    bands: bool = False,
) -> None:
    """Save the text art drawn as an image, or the plain high-resolution text."""
    if content == "art":
        image = khatt.art_to_image(
            art, fg=fg, bg=bg, palette=palette, direction=direction, bands=bands
        )
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


def _show_fetch(
    text: str | None,
    *,
    font: str | None,
    style: str | None,
    palette: str | None,
    gradient: str,
    bands: bool,
    width: int | None,
    color: str,
    rtl_terminal: str,
    arabic_digits: bool,
    private: bool,
    bg: str | None,
    output: Path | None,
) -> None:
    """Print the system-information card, or save it: as an image, ``.txt`` or ``.ans``."""
    options = {
        "font": "lalezar" if font is None else font,
        "style": "quadrants" if style is None else style,
        "palette": "gold" if palette is None else palette,
        "direction": gradient,
        "bands": bands,
        "arabic_digits": arabic_digits,
        "private": private,
    }
    shaped = rtl_terminal == "yes" or (rtl_terminal == "auto" and terminal_shapes_arabic())
    suffix = "" if output is None else output.suffix.lower()
    try:
        if output is None:
            mode = _color_mode(color, sys.stdout)
            columns = _terminal_width() if width is None else width
            card = fetch(
                text,
                color_mode=mode,
                shaped_by_terminal=shaped,
                width=columns,
                **options,  # type: ignore[arg-type]
            )
            _say(card)
        elif suffix in (".txt", ".ans"):
            # A .txt file is read in an editor, which lays Arabic out itself; an .ans file
            # is printed to a terminal with cat.
            card = fetch(
                text,
                color_mode="truecolor" if suffix == ".ans" else None,
                shaped_by_terminal=shaped if suffix == ".ans" else True,
                **options,  # type: ignore[arg-type]
            )
            output.write_text(card + "\n", encoding="utf-8")
            _say(f"wrote {output}", err=True)
        else:
            backdrop = "#1e1e2e" if bg is None else bg
            background = None if backdrop.strip().lower() in ("none", "transparent") else backdrop
            image = fetch_image(text, bg=background, **options)  # type: ignore[arg-type]
            image.save(output)
            _say(f"wrote {output}", err=True)
    except (KeyError, ValueError) as exc:  # unknown font, style, colour or image type
        raise _fail(str(exc.args[0]), 2) from exc


def _positive(value: str) -> float:
    """A number above 0, for ``--fps``."""
    try:
        number = float(value)
    except ValueError:
        number = 0.0
    if number <= 0:
        raise argparse.ArgumentTypeError(f"{value!r} is not a number above 0")
    return number


def _count(value: str) -> int:
    """A whole number of 0 or more, for ``--loop``."""
    try:
        number = int(value)
    except ValueError:
        number = -1
    if number < 0:
        raise argparse.ArgumentTypeError(f"{value!r} is not a whole number of 0 or more")
    return number


def _show_animation(
    text: str,
    effect: str,
    *,
    font: str | None,
    style: str | None,
    size: int,
    threshold: float | None,
    keep_tashkeel: bool,
    palette: str | None,
    gradient: str,
    bands: bool,
    fps: float,
    loops: int,
    color: str,
    fg: str,
    bg: str,
    output: Path | None,
) -> None:
    """Play the animation in the terminal, or save it as GIF, APNG, WebP or .cast."""
    try:
        animation = animate(
            text,
            effect,
            font="amiri" if font is None else font,
            style="blocks" if style is None else style,
            size=size,
            palette=palette,
            direction=gradient,
            bands=bands,
            fps=fps,
            threshold=threshold,
            keep_tashkeel=keep_tashkeel,
        )
        if output is not None:
            animation.save(output, fg=fg, bg=bg, loops=0)
            _say(f"wrote {output}", err=True)
            return
    except (KeyError, ValueError) as exc:  # unknown font, style or format; nothing to draw
        raise _fail(str(exc.args[0]), 2) from exc
    mode = _color_mode(color, sys.stdout)
    if not sys.stdout.isatty():
        # Not a terminal: no redrawing, just the finished text.
        last = len(animation.frames) - 1
        _say(animation.frames[last] if mode is None else animation.ansi(last, mode))
        return
    with contextlib.suppress(KeyboardInterrupt):  # Ctrl+C ends a looping animation
        animation.play(loops=loops, mode=mode)


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
    parser.add_argument(
        "-s", "--style", help="Output style. Default: blocks, or quadrants with --fetch."
    )
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
        help="Write to a file: .png saves an image (see --png), .svg vector outlines (see "
        "--svg), .html the art as coloured HTML text, .ans the art with terminal colour "
        "codes, any other extension the text art.",
    )
    parser.add_argument(
        "--png",
        choices=("art", "text"),
        default="art",
        help="What a .png --output contains: 'art' draws the text art itself "
        "(in the chosen --style), 'text' the plain high-resolution text. Default: art.",
    )
    parser.add_argument(
        "-p",
        "--palette",
        help="Colour the art: a palette (see --list-palettes) or colours separated by commas, "
        "such as '#ce1126,white,black'. Applies to the terminal and to .png, .svg, .html "
        "and .ans output.",
    )
    parser.add_argument(
        "--gradient",
        choices=DIRECTIONS,
        default="rtl",
        help="Where the palette starts: rtl (the right edge, where Arabic starts), ltr, down "
        "or up. Default: rtl.",
    )
    parser.add_argument(
        "--bands",
        action="store_true",
        help="Solid bands of each palette colour, like a flag, instead of a blend.",
    )
    parser.add_argument(
        "--color",
        choices=("auto", "always", "never"),
        default="auto",
        help="Colour codes in terminal output: auto (only in a terminal, not with NO_COLOR), "
        "always or never. Default: auto.",
    )
    parser.add_argument(
        "--svg",
        choices=("text", "art"),
        default="text",
        help="What a .svg --output contains: 'text' the text as vector outlines, 'art' the "
        "text art drawn as vector shapes. Default: text.",
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
    for name in ("curves", "effects", "fonts", "palettes", "shapes", "styles"):
        parser.add_argument(f"--list-{name}", action="store_true", help=f"List {name} and exit.")
    parser.add_argument(
        "-a",
        "--animate",
        choices=ANIMATIONS,
        help="Animate the art, keeping Arabic letters joined: type (a letter at a time), "
        "wipe (uncovered from the right), kashida (the words stretch and settle) or shimmer "
        "(the palette flows through, needs --palette). Plays in the terminal, or saves "
        "with --output as .gif, .png (APNG), .webp or .cast (asciinema).",
    )
    parser.add_argument(
        "--fps", type=_positive, default=12.0, help="Frames per second of --animate. Default: 12."
    )
    parser.add_argument(
        "--loop",
        type=_count,
        default=1,
        help="How many times --animate plays in the terminal; 0 repeats until Ctrl+C. "
        "Saved animations always loop. Default: 1.",
    )
    parser.add_argument(
        "--fetch",
        action="store_true",
        help="Show this machine's details in Arabic beside a logo, like neofetch. The text, if "
        "any, is the logo (default: the system's name, such as ويندوز). Save it with "
        "--output as an image (.png, .webp, .jpg), .txt or .ans.",
    )
    parser.add_argument(
        "--rtl-terminal",
        choices=TERMINAL_MODES,
        default="auto",
        help="With --fetch: whether the terminal joins and orders Arabic itself (Konsole, "
        "GNOME Terminal, mlterm, macOS Terminal do). If not, khatt gives it the letters "
        "already joined. Default: auto, which guesses.",
    )
    parser.add_argument(
        "--arabic-digits",
        action="store_true",
        help="With --fetch: write counts and dates in Eastern Arabic digits (٠١٢٣).",
    )
    parser.add_argument(
        "--private",
        action="store_true",
        help="With --fetch: leave out the user@host line, for screenshots.",
    )
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
    style: str | None = options.style
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
    palette: str | None = options.palette
    gradient: str = options.gradient
    bands: bool = options.bands
    svg_content: str = options.svg
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

    if options.list_palettes:
        for name in khatt.list_palettes():
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
    if palette is not None:
        try:
            palette_colors(palette)
        except (KeyError, ValueError) as exc:
            raise _fail(str(exc.args[0]), 2) from exc
    if options.animate is not None:
        if text is None or text == "-":
            text = sys.stdin.read()
        _show_animation(
            text.rstrip("\n"),
            options.animate,
            font=font,
            style=style,
            size=size,
            threshold=threshold,
            keep_tashkeel=bool(keep_tashkeel),
            palette=palette,
            gradient=gradient,
            bands=bands,
            fps=options.fps,
            loops=options.loop,
            color=options.color,
            fg=ink,
            bg="white" if background is None else background,
            output=output,
        )
        return
    if options.fetch:
        _show_fetch(
            None if text in (None, "-") else text,
            font=font,
            style=style,
            palette=palette,
            gradient=gradient,
            bands=bands,
            width=width,
            color=options.color,
            rtl_terminal=options.rtl_terminal,
            arabic_digits=options.arabic_digits,
            private=options.private,
            bg=bg,
            output=output,
        )
        return
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
    style = "blocks" if style is None else style

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

    suffix = "" if output is None else output.suffix.lower()
    if output is None:
        mode = None if palette is None else _color_mode(options.color, sys.stdout)
        if palette is None or mode is None:
            _say(art)
        else:
            _say(khatt.color_art(art, palette, direction=gradient, bands=bands, mode=mode))
    elif suffix == ".svg" and svg_content == "art":
        art_svg = khatt.art_to_svg(
            art, fg=ink, bg=background, palette=palette, direction=gradient, bands=bands
        )
        if art_svg is None:  # unreachable normally: empty art exits earlier
            raise SystemExit(1)
        output.write_text(art_svg, encoding="utf-8")
        _say(f"wrote {output}", err=True)
    elif suffix == ".html":
        output.write_text(
            khatt.art_to_html(
                art, fg=ink, bg=background, palette=palette, direction=gradient, bands=bands
            ),
            encoding="utf-8",
        )
        _say(f"wrote {output}", err=True)
    elif suffix == ".ans":
        coloured = (
            art
            if palette is None
            else khatt.color_art(art, palette, direction=gradient, bands=bands)
        )
        output.write_text(coloured + "\n", encoding="utf-8")
        _say(f"wrote {output}", err=True)
    elif suffix == ".svg":
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
            palette=palette,
            direction=gradient,
            bands=bands,
        )
        _say(f"wrote {output}", err=True)
    else:
        output.write_text(art + "\n", encoding="utf-8")
        _say(f"wrote {output}", err=True)
