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
import platform
import re
from importlib import metadata
from typing import TypedDict

MATPLOTLIB_NATIVE_SHAPING = (3, 11)
"""The first matplotlib version that shapes Arabic natively."""


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
    warnings: list[str]


def _version(distribution: str) -> str | None:
    try:
        return metadata.version(distribution)
    except metadata.PackageNotFoundError:
        return None


def _at_least(version: str, minimum: tuple[int, int]) -> bool:
    numbers = tuple(int(part) for part in re.findall(r"\d+", version)[:2])
    return numbers >= minimum


def doctor() -> DoctorReport:
    """Report which Arabic shaping engines are installed, and double-shaping risks.

    Returns:
        A dict with the khatt, Python and Pillow versions; ``pillow_raqm``
        (whether ``ImageDraw.text`` shapes Arabic); the matplotlib version
        (``None`` if not installed) and whether it shapes Arabic natively;
        whether ``arabic_reshaper`` is importable; and ``warnings``, a list
        of human-readable problems.
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
    return DoctorReport(
        khatt=__version__,
        python=platform.python_version(),
        pillow=PIL.__version__,
        pillow_raqm=raqm,
        matplotlib=matplotlib,
        matplotlib_shapes_arabic=matplotlib_shapes,
        arabic_reshaper=reshaper,
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
    lines.extend(f"warning: {problem}" for problem in report["warnings"])
    return lines
