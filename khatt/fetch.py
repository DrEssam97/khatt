"""``khatt --fetch``: a system-information card in Arabic, like neofetch.

An Arabic logo drawn as text art sits on the right, where Arabic starts, and the facts
about the machine sit to its left under Arabic labels. :func:`fetch` returns the card
for a terminal; :func:`fetch_image` draws it as an image, with real Arabic shaping.
"""

from __future__ import annotations

import ctypes
import datetime
import getpass
import os
import platform
import socket
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from khatt.art_image import art_to_image
from khatt.color import rgba
from khatt.draw import draw_text, text_bbox
from khatt.fonts import Font
from khatt.palette import RGB, Palette, _code, color_art, palette_colors
from khatt.terminal import for_terminal

ARABIC_DIGITS = str.maketrans("0123456789.", "٠١٢٣٤٥٦٧٨٩٫")
"""Western digits to Eastern Arabic ones, with the Arabic decimal point."""

_MONTHS = (
    "يناير",
    "فبراير",
    "مارس",
    "أبريل",
    "مايو",
    "يونيو",
    "يوليو",
    "أغسطس",
    "سبتمبر",
    "أكتوبر",
    "نوفمبر",
    "ديسمبر",
)
_WEEKDAYS = ("الإثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد")

_LOGOS = {
    "windows": "ويندوز",
    "darwin": "ماك",
    "ubuntu": "أوبونتو",
    "debian": "ديبيان",
    "fedora": "فيدورا",
    "arch": "آرتش",
    "manjaro": "مانجارو",
    "linuxmint": "مينت",
    "pop": "بوب",
    "kali": "كالي",
    "alpine": "ألباين",
    "opensuse": "سوزي",
    "centos": "سنت",
    "rhel": "ريدهات",
    "nixos": "نكس",
    "gentoo": "جنتو",
}
_LINUX_LOGO = "لينكس"

_UNITS = {
    # singular (1), dual (2), plural (3 to 10), singular after 11 and more
    "day": ("يوم", "يومان", "أيام", "يومًا"),
    "hour": ("ساعة", "ساعتان", "ساعات", "ساعة"),
    "minute": ("دقيقة", "دقيقتان", "دقائق", "دقيقة"),
}


@dataclass(frozen=True)
class Fact:
    """One line of the card: an Arabic label and its value."""

    label: str
    value: str
    numeric: bool = False
    """Whether the value is a count or a date, written in Arabic digits on request."""


def counted(number: int, unit: str) -> str:
    """``number`` of ``unit`` in Arabic grammar: يوم, يومان, 3 أيام, 11 يومًا."""
    singular, dual, plural, many = _UNITS[unit]
    if number == 1:
        return singular
    if number == 2:
        return dual
    if 3 <= number % 100 <= 10:
        return f"{number} {plural}"
    return f"{number} {many if number % 100 >= 11 else singular}"


def uptime_text(seconds: float) -> str:
    """How long the machine has been on, such as ``3 أيام و4 ساعات و12 دقيقة``."""
    minutes = int(seconds // 60)
    days, minutes = divmod(minutes, 24 * 60)
    hours, minutes = divmod(minutes, 60)
    parts = [
        counted(value, unit)
        for value, unit in ((days, "day"), (hours, "hour"), (minutes, "minute"))
        if value
    ]
    return " و".join(parts) or "أقل من دقيقة"


def date_text(day: datetime.date) -> str:
    """A date in Arabic, such as ``الأحد 16 نوفمبر 2026``."""
    return f"{_WEEKDAYS[day.weekday()]} {day.day} {_MONTHS[day.month - 1]} {day.year}"


def _gib(size: float) -> str:
    return f"{size / 2**30:.1f}"


def _run(command: Sequence[str]) -> str:
    """Output of a short command, or ``""`` if it can't run."""
    try:
        done = subprocess.run(command, capture_output=True, text=True, timeout=2, check=False)
    except (OSError, subprocess.SubprocessError):
        return ""
    return done.stdout.strip()


def _os_release(path: Path = Path("/etc/os-release")) -> dict[str, str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return {}
    pairs = (line.split("=", 1) for line in lines if "=" in line)
    return {key: value.strip().strip('"') for key, value in pairs}


def _windows_memory() -> tuple[float, float] | None:
    if sys.platform != "win32":
        return None

    class MemoryStatus(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    status = MemoryStatus()
    status.dwLength = ctypes.sizeof(MemoryStatus)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return None
    return status.ullTotalPhys - status.ullAvailPhys, status.ullTotalPhys


def _memory() -> tuple[float, float] | None:
    """Used and total memory in bytes (used is ``0`` where it can't be known)."""
    if sys.platform == "win32":
        return _windows_memory()
    if sys.platform == "darwin":
        total = _run(["sysctl", "-n", "hw.memsize"])
        return (0, int(total)) if total.isdigit() else None
    try:
        info = Path("/proc/meminfo").read_text(encoding="utf-8")
    except OSError:
        return None
    values = {
        line.split(":")[0]: int(line.split()[1]) * 1024
        for line in info.splitlines()
        if len(line.split()) >= 2 and line.split()[1].isdigit()
    }
    if "MemTotal" not in values:
        return None
    total = values["MemTotal"]
    return total - values.get("MemAvailable", total), total


def _uptime() -> float | None:
    if sys.platform == "win32":
        tick = ctypes.windll.kernel32.GetTickCount64
        tick.restype = ctypes.c_ulonglong
        return float(tick()) / 1000
    if sys.platform == "darwin":
        boot = _run(["sysctl", "-n", "kern.boottime"])  # { sec = 1763000000, usec = 0 } ...
        seconds = boot.split("sec = ")[1].split(",")[0] if "sec = " in boot else ""
        return datetime.datetime.now().timestamp() - int(seconds) if seconds.isdigit() else None
    try:
        return float(Path("/proc/uptime").read_text(encoding="utf-8").split()[0])
    except (OSError, ValueError, IndexError):
        return None


def _cpu() -> str:
    if sys.platform == "win32":
        try:
            import winreg

            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0"
            )
            name, _ = winreg.QueryValueEx(key, "ProcessorNameString")
            return " ".join(str(name).split())
        except OSError:
            return platform.processor()
    if sys.platform == "darwin":
        return _run(["sysctl", "-n", "machdep.cpu.brand_string"]) or platform.machine()
    try:
        for line in Path("/proc/cpuinfo").read_text(encoding="utf-8").splitlines():
            if line.startswith(("model name", "Hardware", "Model")):
                return " ".join(line.split(":", 1)[1].split())
    except OSError:
        pass
    return platform.processor() or platform.machine()


def _system_name(release: Mapping[str, str]) -> str:
    if sys.platform == "win32":
        return f"Windows {platform.release()}"
    if sys.platform == "darwin":
        return f"macOS {platform.mac_ver()[0]}"
    return release.get("PRETTY_NAME") or f"{platform.system()} {platform.release()}"


def _terminal(environ: Mapping[str, str]) -> str:
    if "WT_SESSION" in environ:
        return "Windows Terminal"
    if "KONSOLE_VERSION" in environ:
        return "Konsole"
    program = environ.get("TERM_PROGRAM", "")
    if program:
        return {"Apple_Terminal": "Terminal", "vscode": "VS Code"}.get(program, program)
    return environ.get("TERM", "")


def logo_text(release: Mapping[str, str] | None = None) -> str:
    """The default logo: the name of the operating system in Arabic letters."""
    if sys.platform == "win32":
        return _LOGOS["windows"]
    if sys.platform == "darwin":
        return _LOGOS["darwin"]
    found = _os_release() if release is None else release
    for key in (found.get("ID", ""), *found.get("ID_LIKE", "").split()):
        for name, logo in _LOGOS.items():
            if key.startswith(name):
                return logo
    return _LINUX_LOGO


def system_facts(
    *,
    environ: Mapping[str, str] | None = None,
    today: datetime.date | None = None,
    hijri: Callable[[datetime.date], str | None] | None = None,
) -> list[Fact]:
    """What the card shows about this machine, each under its Arabic label.

    Facts that can't be found on this system are left out.
    """
    from khatt import __version__

    env = os.environ if environ is None else environ
    release = _os_release() if sys.platform.startswith("linux") else {}
    facts = [Fact("النظام", _system_name(release))]
    if sys.platform != "win32":
        facts.append(Fact("النواة", platform.release()))
    cpu = _cpu()
    if cpu:
        cores = os.cpu_count()
        facts.append(Fact("المعالج", f"{cpu} ({cores})" if cores else cpu))
    memory = _memory()
    if memory is not None:
        used, total = memory
        amount = f"{_gib(used)} / {_gib(total)}" if used else _gib(total)
        facts.append(Fact("الذاكرة", f"{amount} جيجابايت", numeric=True))
    uptime = _uptime()
    if uptime is not None:
        facts.append(Fact("مدة التشغيل", uptime_text(uptime), numeric=True))
    shell = Path(env.get("SHELL", "")).stem
    if shell:
        facts.append(Fact("الصدفة", shell))
    terminal = _terminal(env)
    if terminal:
        facts.append(Fact("الطرفية", terminal))
    facts.append(Fact("بايثون", platform.python_version()))
    facts.append(Fact("خط", __version__))
    day = datetime.date.today() if today is None else today
    facts.append(Fact("التاريخ", date_text(day), numeric=True))
    hijri_date = (hijri or _hijri)(day)
    if hijri_date:
        facts.append(Fact("الهجري", hijri_date, numeric=True))
    return facts


def _hijri(day: datetime.date) -> str | None:
    """The Hijri (Umm al-Qura) date, when the optional ``hijridate`` package is installed."""
    try:
        from hijridate import Gregorian
    except ImportError:
        return None
    try:
        date = Gregorian(day.year, day.month, day.day).to_hijri()
    except (OverflowError, ValueError):
        return None
    return f"{date.day} {date.month_name('ar')} {date.year} هـ"


def _accent(palette: Palette) -> RGB:
    """The colour of the labels: the palette's second colour, or its only one."""
    colors = palette_colors(palette)
    return colors[min(1, len(colors) - 1)]


def _header(private: bool) -> str | None:
    if private:
        return None
    try:
        user = getpass.getuser()
    except (KeyError, OSError):
        user = ""
    host = socket.gethostname().split(".")[0]
    return f"{user}@{host}" if user else host


@dataclass
class _Card:
    logo: str
    rows: list[tuple[str, str]]
    """``(label, value)``; a row with an empty label is the header or the rule."""
    title: str
    """The logo's text."""


def _card(
    text: str | None,
    *,
    font: Font,
    style: str,
    width: int,
    facts: Sequence[Fact] | None,
    arabic_digits: bool,
    private: bool,
) -> _Card:
    rows: list[tuple[str, str]] = []
    header = _header(private)
    if header:
        rows += [("", header), ("", "─" * len(header))]
    for fact in system_facts() if facts is None else facts:
        value = (
            fact.value.translate(ARABIC_DIGITS) if arabic_digits and fact.numeric else fact.value
        )
        rows.append((fact.label, value))
    title = text or logo_text()
    return _Card(_logo(title, font, style, width, len(rows) + 2), rows, title)


def _logo(text: str, font: Font, style: str, width: int, rows: int) -> str:
    """The logo as text art at the largest size that fits ``width`` columns and ``rows``."""
    from khatt import render

    art = ""
    for size in range(max(rows, 4), 2, -1):
        art = render(text, font=font, style=style, width=None, size=size)
        lines = art.split("\n")
        if max(map(len, lines)) <= width and len(lines) <= rows:
            break
    return art


def fetch(
    text: str | None = None,
    *,
    font: Font = "lalezar",
    style: str = "quadrants",
    palette: Palette = "gold",
    direction: str = "rtl",
    bands: bool = False,
    logo_width: int = 56,
    width: int | None = None,
    color_mode: str | None = "truecolor",
    shaped_by_terminal: bool = False,
    arabic_digits: bool = False,
    private: bool = False,
    facts: Sequence[Fact] | None = None,
) -> str:
    """A system-information card for the terminal, in Arabic.

    Args:
        text: The logo; by default the name of the operating system in Arabic letters
            (ويندوز, أوبونتو, ماك...).
        font, style: The logo's font and text-art style (see :func:`khatt.render`).
        palette, direction, bands: The logo's colours (see :func:`khatt.color_art`).
            The labels take the palette's second colour, which reads well on dark
            and light backgrounds in every bundled palette.
        logo_width: The most terminal columns the logo may take; it is drawn as large as
            fits that and the height of the facts.
        width: The most columns the whole card may take, such as the terminal's width;
            the logo shrinks to make room for the facts.
        color_mode: ``"truecolor"``, ``"256"``, or ``None`` for no colour codes.
        shaped_by_terminal: Whether the terminal joins and orders Arabic itself; if not,
            the labels are given to it joined and in display order (see
            :func:`khatt.terminal.for_terminal`).
        arabic_digits: Write counts and dates in Eastern Arabic digits (٠١٢٣).
        private: Leave out the ``user@host`` line, for screenshots.
        facts: The lines to show, instead of this machine's (see :func:`system_facts`).

    Returns:
        The card, ``\\n``-separated: the logo on the right, the facts to its left.
    """
    card = _card(
        text,
        font=font,
        style=style,
        width=logo_width,
        facts=facts,
        arabic_digits=arabic_digits,
        private=private,
    )
    accent = _accent(palette)

    def paint(segment: str) -> str:
        return segment if color_mode is None else f"{_code(accent, color_mode)}{segment}\033[0m"

    def shown(segment: str, direction: str | None = None) -> str:
        return for_terminal(segment, shaped_by_terminal=shaped_by_terminal, direction=direction)

    label_width = max(
        (len(shown(label + ":", "rtl")) for label, _ in card.rows if label), default=0
    )
    value_width = max(len(shown(value)) for _, value in card.rows)
    if width is not None and width - (value_width + 1 + label_width) - 3 < logo_width:
        room = max(8, width - (value_width + 1 + label_width) - 3)
        card.logo = _logo(card.title, font, style, room, len(card.rows) + 2)
    info: list[str] = []
    for label, value in card.rows:
        if not label:
            text_shown = shown(value)
            pad = " " * (value_width + 1 + label_width - len(text_shown))
            info.append(pad + paint(text_shown))
            continue
        tag = shown(label + ":", "rtl")
        value_shown = shown(value)
        info.append(
            " " * (value_width - len(value_shown))
            + value_shown
            + " "
            + " " * (label_width - len(tag))
            + paint(tag)
        )
    info.append("")
    swatches = "".join(
        f"{_code(color, color_mode)}███\033[0m" if color_mode else "███"
        for color in palette_colors(palette)
    )
    swatch_width = 3 * len(palette_colors(palette))
    info.append(" " * (value_width + 1 + label_width - swatch_width) + swatches)

    logo_lines = card.logo.split("\n")
    if color_mode is not None:
        coloured = color_art(card.logo, palette, direction=direction, bands=bands, mode=color_mode)
        logo_shown = coloured.split("\n")
    else:
        logo_shown = logo_lines
    logo_columns = max(len(line) for line in logo_lines)
    height = max(len(info), len(logo_lines))
    info_top = (height - len(info)) // 2
    logo_top = (height - len(logo_lines)) // 2
    info_width = value_width + 1 + label_width
    out = []
    for row in range(height):
        left = info[row - info_top] if 0 <= row - info_top < len(info) else ""
        left_plain_width = (
            info_width if 0 <= row - info_top < len(info) and info[row - info_top] else 0
        )
        right_index = row - logo_top
        if 0 <= right_index < len(logo_lines):
            right = logo_shown[right_index] + " " * (logo_columns - len(logo_lines[right_index]))
        else:
            right = ""
        out.append((left + " " * (info_width - left_plain_width) + "   " + right).rstrip())
    return "\n".join(out)


def fetch_image(
    text: str | None = None,
    *,
    font: Font = "lalezar",
    style: str = "quadrants",
    palette: Palette = "gold",
    direction: str = "rtl",
    bands: bool = False,
    logo_width: int = 56,
    arabic_digits: bool = False,
    private: bool = False,
    facts: Sequence[Fact] | None = None,
    text_font: Font = "cairo",
    size_px: int = 26,
    fg: str = "#cdd6f4",
    bg: str | None = "#1e1e2e",
    cell_width: int = 10,
) -> Image.Image:
    """The card of :func:`fetch` drawn as an image, with HarfBuzz shaping the Arabic.

    The extra arguments: ``text_font`` and ``size_px`` for the labels and values, ``fg``
    for the values, ``bg`` for the background (``None`` for transparent), and
    ``cell_width`` for the logo's character cells.
    """
    card = _card(
        text,
        font=font,
        style=style,
        width=logo_width,
        facts=facts,
        arabic_digits=arabic_digits,
        private=private,
    )
    accent = _accent(palette)
    logo = art_to_image(
        card.logo,
        bg=None,
        cell_width=cell_width,
        padding=0,
        palette=palette,
        direction=direction,
        bands=bands,
    )
    if logo is None:
        raise ValueError("the logo has nothing to draw")
    options = {"font": text_font, "size_px": size_px}
    line_height = round(size_px * 1.6)

    def width_of(segment: str) -> int:
        left, _, right, _ = text_bbox(segment, **options)  # type: ignore[arg-type]
        return right - left

    facts_shown = [(label, value) for label, value in card.rows if label]
    label_width = max((width_of(label + ":") for label, _ in facts_shown), default=0)
    value_width = max((width_of(value) for _, value in facts_shown), default=0)
    headers = [value for label, value in card.rows if not label and set(value) != {"─"}]
    gap, margin = size_px // 2, size_px * 2
    info_width = max(value_width + gap + label_width, *map(width_of, headers or [""]))
    swatch = size_px
    info_height = line_height * len(card.rows) + line_height + swatch
    height = max(info_height, logo.height) + 2 * margin
    width = margin + info_width + margin + logo.width + margin
    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0) if bg is None else rgba(bg))
    canvas.alpha_composite(logo, (width - margin - logo.width, (height - logo.height) // 2))
    top = (height - info_height) // 2
    right = margin + info_width
    for index, (label, value) in enumerate(card.rows):
        y = top + index * line_height
        if not label and set(value) == {"─"}:  # the rule under user@host
            rule_y = y + line_height // 3
            canvas.paste(accent, (right - width_of(card.rows[0][1]), rule_y, right, rule_y + 2))
            continue
        if not label:
            draw_text(canvas, (right, y), value, fill=accent, anchor="ra", **options)  # type: ignore[arg-type]
            continue
        draw_text(canvas, (right, y), label + ":", fill=accent, anchor="ra", **options)  # type: ignore[arg-type]
        draw_text(canvas, (right - label_width - gap, y), value, fill=fg, anchor="ra", **options)  # type: ignore[arg-type]
    y = top + len(card.rows) * line_height + line_height // 2
    colors = palette_colors(palette)
    for index, color in enumerate(colors):
        x = right - (len(colors) - index) * swatch * 2
        canvas.paste(color, (x, y, x + swatch * 2, y + swatch))
    return canvas if bg is None else canvas.convert("RGB")
