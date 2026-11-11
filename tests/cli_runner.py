"""Run the ``khatt`` command in the test process and capture what it prints."""

from __future__ import annotations

import io
import os
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass


@dataclass
class Result:
    exit_code: int
    output: str  # stdout and stderr together, in the order they were written


def invoke(
    main: Callable[[Sequence[str]], None],
    args: Sequence[str],
    input: str = "",
    env: Mapping[str, str] | None = None,
) -> Result:
    """Call ``main(args)`` with ``input`` on stdin and ``env`` added to the environment."""
    buffer = io.BytesIO()
    stream = io.TextIOWrapper(buffer, encoding="utf-8", newline="\n", write_through=True)
    saved = sys.stdin, sys.stdout, sys.stderr
    saved_env = dict(os.environ)
    sys.stdin = io.StringIO(input)
    sys.stdout = sys.stderr = stream
    os.environ.update(env or {})
    try:
        main(args)
        code = 0
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 1
    finally:
        sys.stdin, sys.stdout, sys.stderr = saved
        os.environ.clear()
        os.environ.update(saved_env)
    stream.flush()
    return Result(code, buffer.getvalue().decode("utf-8"))
