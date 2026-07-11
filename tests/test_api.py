"""Tests for the public khatt API."""

import khatt


def test_version() -> None:
    assert khatt.__version__ == "0.1.0"
