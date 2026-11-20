"""Where an E24 warning points (3.7, 6.5 (6), 6.6 header): at the line of the user's code that
applied `@nx.factor`, whichever way the user function reaches the global it reads: directly,
through a project helper, or through a closure (#558)."""

from __future__ import annotations

import inspect
import warnings
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

import nexusbt as nx
from nexusbt.pipeline import BoundColumn

CLOSE = BoundColumn.of("Price", "close")
TABLE = [1.0, 2.0]  # not constant-like: E24


def _direct(close: Any) -> Any:
    return close[-1] * TABLE[0]


def _through_helper(close: Any) -> Any:
    return close[-1] * _scale()


def _scale() -> float:
    return TABLE[1]


def _closure() -> Callable[..., Any]:
    table = [3.0]

    def _inner(close: Any) -> Any:
        return close[-1] * table[0] * TABLE[0]

    return _inner


@pytest.mark.parametrize(
    "fn", [_direct, _through_helper, _closure()], ids=["direct", "helper", "closure"]
)
def test_e24_points_at_the_line_that_applies_factor(fn: Callable[..., Any]) -> None:
    with warnings.catch_warnings(record=True) as got:
        warnings.simplefilter("always")
        line = _line() + 1
        nx.factor(window=2, inputs=[CLOSE])(fn)
    said = [w for w in got if "[E24]" in str(w.message)]
    assert [(Path(w.filename).name, w.lineno) for w in said] == [(Path(__file__).name, line)]
    assert f"your code — {Path(__file__).name}:{line} in " in str(said[0].message)


def _line() -> int:
    """The line this is called from."""
    frame = inspect.currentframe()
    assert frame is not None
    assert frame.f_back is not None
    return frame.f_back.f_lineno
