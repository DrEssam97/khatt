"""Environment check for Arabic text rendering (``khatt --doctor``).

The popular recipe for Arabic in Pillow and matplotlib, ``arabic_reshaper``
plus python-bidi's ``get_display``, shapes and reorders text up front because
those libraries used not to. Where they now shape Arabic themselves (Pillow
built with Raqm, matplotlib 3.11+), pre-shaped text is shaped a second time
and comes out corrupted. khatt shapes text itself and never hands it to
another shaper, so its output is the same either way.
"""

from __future__ import annotations

import importlib.util
import os
import platform
import re
from importlib import metadata
from pathlib import Path
from typing import TypedDict

MATPLOTLIB_NATIVE_SHAPING = (3, 11)
"""The first matplotlib version that shapes Arabic natively."""

_SKIPPED_FOLDERS = frozenset(
    {
        ".git",
        ".hg",
        ".venv",
        "venv",
        "env",
        ".env",
        "node_modules",
        "__pycache__",
        "site-packages",
        "build",
        "dist",
        ".tox",
        ".nox",
        ".mypy_cache",
        ".ruff_cache",
    }
)
_IMPORTS_RESHAPER = re.compile(r"^\s*(?:from|import)\s+arabic_reshaper\b", re.MULTILINE)
_IMPORTS_BIDI = re.compile(r"^\s*(?:from|import)\s+bidi\b", re.MULTILINE)
_RESHAPER_CALL = re.compile(
    r"\b(?:arabic_reshaper\.reshape|ArabicReshaper|\w*reshaper\.reshape)\s*\("
)
_BARE_RESHAPE = re.compile(r"(?<![\w.])reshape\s*\(")
_GET_DISPLAY = re.compile(r"\bget_display\s*\(")


class DoctorReport(TypedDict):
    khatt: str
    python: str
    pillow: str
    pillow_raqm: bool
    """Pillow's text layout (``ImageDraw.text``) shapes Arabic via Raqm."""
    matplotlib: str | None
    """The installed matplotlib version, or ``None``."""
    matplotlib_shapes_arabic: bool
    arabic_reshaper: bool
    """``arabic_reshaper`` is importable."""
    reshaping: list[str]
    """Where the scanned project pre-shapes Arabic: ``file:line: code``."""
    warnings: list[str]


def _version(distribution: str) -> str | None:
    try:
        return metadata.version(distribution)
    except metadata.PackageNotFoundError:
        return None


def _at_least(version: str, minimum: tuple[int, int]) -> bool:
    numbers = tuple(int(part) for part in re.findall(r"\d+", version)[:2])
    return numbers >= minimum


def _python_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root] if root.suffix == ".py" else []
    found: list[Path] = []
    for folder, subfolders, files in os.walk(root):
        subfolders[:] = sorted(name for name in subfolders if name not in _SKIPPED_FOLDERS)
        found.extend(Path(folder) / name for name in sorted(files) if name.endswith(".py"))
    return found


def find_reshaping(path: str | os.PathLike[str], *, limit: int = 200) -> list[str]:
    """Where a project pre-shapes Arabic text for another library.

    Looks through the Python files under ``path`` (skipping virtual
    environments, ``site-packages`` and build folders) for calls to
    arabic_reshaper and to python-bidi's ``get_display``: the old recipe
    that now makes Pillow with Raqm and matplotlib 3.11+ shape text twice.
    A bare ``reshape(...)`` or ``get_display(...)`` counts only in a file
    that imports arabic_reshaper or bidi.

    Returns:
        Up to ``limit`` places, each ``"file:line: code"``.
    """
    root = Path(path)
    if not root.exists():
        raise FileNotFoundError(f"no such file or folder: {root}")
    places: list[str] = []
    for file in _python_files(root):
        try:
            source = file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        reshaper = bool(_IMPORTS_RESHAPER.search(source))
        bidi = bool(_IMPORTS_BIDI.search(source))
        if not (reshaper or bidi or "arabic_reshaper" in source):
            continue
        for number, line in enumerate(source.splitlines(), start=1):
            code = line.split("#", 1)[0]
            if (
                _RESHAPER_CALL.search(code)
                or (reshaper and _BARE_RESHAPE.search(code))
                or (bidi and _GET_DISPLAY.search(code))
            ):
                name = file.relative_to(root).as_posix() if root.is_dir() else file.name
                places.append(f"{name}:{number}: {line.strip()}")
                if len(places) >= limit:
                    return places
    return places


def doctor(path: str | os.PathLike[str] | None = None) -> DoctorReport:
    """Report which Arabic shaping engines are installed, and double-shaping risks.

    Args:
        path: A project folder or Python file to look through as well, for
            code that pre-shapes Arabic (see :func:`find_reshaping`).

    Returns:
        A dict with the khatt, Python and Pillow versions; ``pillow_raqm``
        (whether ``ImageDraw.text`` shapes Arabic); the matplotlib version
        (``None`` if not installed) and whether it shapes Arabic natively;
        whether ``arabic_reshaper`` is importable; ``reshaping``, the places
        in ``path`` that pre-shape Arabic; and ``warnings``, a list of
        human-readable problems.
    """
    import PIL
    from PIL import features

    from khatt import __version__

    raqm = bool(features.check("raqm"))
    matplotlib = _version("matplotlib")
    matplotlib_shapes = matplotlib is not None and _at_least(matplotlib, MATPLOTLIB_NATIVE_SHAPING)
    reshaper = importlib.util.find_spec("arabic_reshaper") is not None

    native = []
    if raqm:
        native.append("Pillow (Raqm)")
    if matplotlib_shapes:
        native.append(f"matplotlib {matplotlib}")
    problems = []
    if reshaper and native:
        problems.append(
            f"arabic_reshaper is installed, and {' and '.join(native)} already "
            "shape Arabic: text passed through arabic_reshaper (and bidi's "
            "get_display) first is shaped twice and comes out corrupted. Give them "
            "the plain text, or draw it with khatt.draw_text."
        )
    elif reshaper:
        problems.append(
            "arabic_reshaper is installed. Nothing here shapes Arabic natively yet, "
            "but reshaped text comes out corrupted (shaped twice) as soon as Pillow "
            "gains Raqm or matplotlib is upgraded to 3.11+. khatt.draw_text gives "
            "the same correct output in both cases."
        )
    reshaping = [] if path is None else find_reshaping(path)
    if reshaping:
        problems.append(
            f"{len(reshaping)} place(s) in {path} pre-shape Arabic (listed above). Pass the "
            "text as typed to Pillow with Raqm, matplotlib 3.11+ or khatt.draw_text; for "
            "strings that were already reshaped, khatt.unreshape(text) turns them back."
        )
    return DoctorReport(
        khatt=__version__,
        python=platform.python_version(),
        pillow=PIL.__version__,
        pillow_raqm=raqm,
        matplotlib=matplotlib,
        matplotlib_shapes_arabic=matplotlib_shapes,
        arabic_reshaper=reshaper,
        reshaping=reshaping,
        warnings=problems,
    )


def format_report(report: DoctorReport) -> list[str]:
    """The report as lines of text, warnings last (prefixed ``warning:``)."""
    pillow = (
        "built with Raqm, so ImageDraw.text shapes Arabic"
        if report["pillow_raqm"]
        else "no Raqm, so ImageDraw.text cannot shape Arabic"
    )
    if report["matplotlib"] is None:
        matplotlib = "not installed"
    elif report["matplotlib_shapes_arabic"]:
        matplotlib = f"{report['matplotlib']} (shapes Arabic natively)"
    else:
        matplotlib = f"{report['matplotlib']} (does not shape Arabic; 3.11+ does)"
    lines = [
        f"khatt {report['khatt']} (Python {report['python']})",
        f"Pillow {report['pillow']}: {pillow}",
        f"matplotlib: {matplotlib}",
        f"arabic_reshaper: {'installed' if report['arabic_reshaper'] else 'not installed'}",
        "khatt shapes text itself: its output is the same in every case above.",
    ]
    if report.get("reshaping"):
        lines.append("pre-shaping Arabic:")
        lines.extend(f"  {place}" for place in report["reshaping"])
    lines.extend(f"warning: {problem}" for problem in report["warnings"])
    return lines
