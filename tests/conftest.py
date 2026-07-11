"""Shared fixtures, including the golden-file snapshot harness."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

GOLDEN_DIR = Path(__file__).parent / "golden"

GoldenCheck = Callable[[str, str], None]


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--update-golden",
        action="store_true",
        default=False,
        help="regenerate golden snapshot files instead of comparing against them",
    )


@pytest.fixture
def golden(request: pytest.FixtureRequest) -> GoldenCheck:
    """Compare ``content`` against ``tests/golden/<name>``.

    Run ``pytest --update-golden`` to (re)generate the snapshots after an
    intentional rendering change, then commit the diff.
    """
    update: bool = request.config.getoption("--update-golden")

    def check(name: str, content: str) -> None:
        path = GOLDEN_DIR / name
        if update:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8", newline="\n")
            return
        if not path.exists():
            pytest.fail(f"golden file {name} is missing; run: pytest --update-golden")
        expected = path.read_text(encoding="utf-8")
        assert content == expected, (
            f"output differs from golden snapshot {name}; "
            "if the change is intentional, run: pytest --update-golden"
        )

    return check
