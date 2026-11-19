"""Arabic-Indic digits (٠١٢٣٤٥٦٧٨٩) for numbers in drawn text."""

from __future__ import annotations

import re

DIGITS = ("arabic-indic",)
"""The values ``digits=`` takes, besides ``None`` (digits as typed)."""

_ARABIC_INDIC = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")
_SEPARATORS = {".": "٫", ",": "٬", "%": "٪"}
_IN_NUMBER = re.compile(r"(?<=[0-9])[.,](?=[0-9])|(?<=[0-9])%")


def arabic_digits(text: str) -> str:
    """``text`` with its digits written as Arabic-Indic digits (٠١٢٣٤٥٦٧٨٩).

    Inside a number, ``.`` becomes the Arabic decimal separator ``٫`` and ``,`` the
    thousands separator ``٬``, and a ``%`` right after a digit becomes ``٪``: so
    ``"1,250.5 ريال 15%"`` becomes ``"١٬٢٥٠٫٥ ريال ١٥٪"``. Each character is replaced by
    one character, so positions in the text (such as ``spans``) stay the same.

    >>> arabic_digits("السعر 150 ريال")
    'السعر ١٥٠ ريال'
    """
    return _IN_NUMBER.sub(lambda match: _SEPARATORS[match.group()], text).translate(_ARABIC_INDIC)


def with_digits(text: str, digits: str | None) -> str:
    """``text`` with the digits ``digits=`` asks for."""
    if digits is None:
        return text
    if digits == "arabic-indic":
        return arabic_digits(text)
    raise ValueError(f'digits must be None or "arabic-indic", got {digits!r}')
