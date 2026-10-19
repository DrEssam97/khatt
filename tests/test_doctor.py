"""Tests for the environment check (khatt.doctor / khatt --doctor)."""

from __future__ import annotations

import importlib.util
from importlib import metadata
from typing import Protocol

import pytest
from PIL import features
from typer.testing import CliRunner

import khatt
from khatt.cli import app
from khatt.doctor import _at_least, format_report

runner = CliRunner()


class Environment(Protocol):
    def __call__(self, *, raqm: bool, matplotlib: str | None, reshaper: bool) -> None: ...


@pytest.fixture
def environment(monkeypatch: pytest.MonkeyPatch) -> Environment:
    """Fake which shaping engines are installed."""
    real_check = features.check
    real_version = metadata.version
    real_find_spec = importlib.util.find_spec

    def configure(*, raqm: bool, matplotlib: str | None, reshaper: bool) -> None:
        def check(name: str) -> bool | None:
            return raqm if name == "raqm" else real_check(name)

        def version(distribution: str) -> str:
            if distribution != "matplotlib":
                return real_version(distribution)
            if matplotlib is None:
                raise metadata.PackageNotFoundError(distribution)
            return matplotlib

        def find_spec(name: str, package: str | None = None) -> object:
            if name == "arabic_reshaper":
                return object() if reshaper else None
            return real_find_spec(name, package)

        monkeypatch.setattr(features, "check", check)
        monkeypatch.setattr(metadata, "version", version)
        monkeypatch.setattr(importlib.util, "find_spec", find_spec)

    return configure


def test_report_fields() -> None:
    report = khatt.doctor()
    assert report["khatt"] == khatt.__version__
    assert report["pillow"]
    assert report["python"]
    assert isinstance(report["pillow_raqm"], bool)
    assert isinstance(report["arabic_reshaper"], bool)
    assert isinstance(report["warnings"], list)


def test_clean_environment(environment: Environment) -> None:
    environment(raqm=False, matplotlib=None, reshaper=False)
    report = khatt.doctor()
    assert report["pillow_raqm"] is False
    assert report["matplotlib"] is None
    assert report["matplotlib_shapes_arabic"] is False
    assert report["arabic_reshaper"] is False
    assert report["warnings"] == []


@pytest.mark.parametrize(
    ("raqm", "matplotlib", "names"),
    [
        (True, None, ["Pillow (Raqm)"]),
        (False, "3.11.0", ["matplotlib 3.11.0"]),
        (True, "3.12.1", ["Pillow (Raqm)", "matplotlib 3.12.1"]),
    ],
)
def test_reshaper_with_native_shaping_warns_of_double_shaping(
    environment: Environment,
    raqm: bool,
    matplotlib: str | None,
    names: list[str],
) -> None:
    environment(raqm=raqm, matplotlib=matplotlib, reshaper=True)
    (warning,) = khatt.doctor()["warnings"]
    assert "shaped twice" in warning
    for name in names:
        assert name in warning


def test_reshaper_alone_warns_about_the_future(environment: Environment) -> None:
    environment(raqm=False, matplotlib="3.10.3", reshaper=True)
    report = khatt.doctor()
    assert report["matplotlib_shapes_arabic"] is False
    (warning,) = report["warnings"]
    assert "as soon as" in warning


def test_native_shaping_without_reshaper_is_fine(environment: Environment) -> None:
    environment(raqm=True, matplotlib="3.11.0", reshaper=False)
    report = khatt.doctor()
    assert report["pillow_raqm"] is True
    assert report["matplotlib_shapes_arabic"] is True
    assert report["warnings"] == []


@pytest.mark.parametrize(
    ("version", "expected"),
    [
        ("3.11.0", True),
        ("3.11.0rc1", True),
        ("3.12", True),
        ("4.0.0", True),
        ("3.10.8", False),
        ("3.9", False),
        ("2.2.5", False),
    ],
)
def test_version_comparison(version: str, expected: bool) -> None:
    assert _at_least(version, (3, 11)) is expected


def test_format_report(environment: Environment) -> None:
    environment(raqm=True, matplotlib="3.11.0", reshaper=True)
    lines = format_report(khatt.doctor())
    text = "\n".join(lines)
    assert "built with Raqm" in text
    assert "3.11.0 (shapes Arabic natively)" in text
    assert "arabic_reshaper: installed" in text
    assert lines[-1].startswith("warning: ")

    environment(raqm=False, matplotlib="3.9.0", reshaper=False)
    text = "\n".join(format_report(khatt.doctor()))
    assert "no Raqm" in text
    assert "3.9.0 (does not shape Arabic" in text
    assert "arabic_reshaper: not installed" in text
    assert "warning" not in text

    environment(raqm=False, matplotlib=None, reshaper=False)
    assert "matplotlib: not installed" in format_report(khatt.doctor())


def test_cli_doctor_flag(environment: Environment) -> None:
    environment(raqm=False, matplotlib=None, reshaper=True)
    result = runner.invoke(app, ["--doctor"])
    assert result.exit_code == 0
    assert "Pillow" in result.output
    assert "warning: arabic_reshaper is installed" in result.output


def test_cli_doctor_flag_wins_over_text() -> None:
    result = runner.invoke(app, ["مرحبا", "--doctor"])
    assert result.exit_code == 0
    assert result.output.startswith("khatt ")
