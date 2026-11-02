"""Spec 6.6 "User function exceptions" and 8.4b: the original exception is raised as it is,
with one `layer  your code — …` note and one `fix` note (R-42, R4F-22)."""

from __future__ import annotations

import functools
import math
from collections.abc import Callable

import pytest

from nexusbt.contracts import _note_user_exception


def engine_calls(function: Callable[[], object]) -> object:
    """What an engine call site does: note the user's exception, then re-raise it as it is."""
    try:
        return function()
    except Exception as error:
        _note_user_exception(error, function, instrument_id="A1", date="2020-03-02")
        raise


def my_score() -> object:
    return {"A2": 1.0}["A1"]


def test_original_class_and_traceback_kept() -> None:
    with pytest.raises(KeyError) as caught:
        engine_calls(my_score)
    assert type(caught.value) is KeyError
    assert caught.value.args == ("A1",)
    assert caught.traceback[-1].name == "my_score"  # the user's frame is still the last one
    line = my_score.__code__.co_firstlineno + 1
    layer, fix = caught.value.__notes__
    assert layer == f"  layer  your code — test_user_exception_note.py:{line} in my_score"
    assert fix.startswith("  fix    ")
    assert "nx.describe" in fix


def decorated(f: Callable[[], object]) -> Callable[[], object]:
    @functools.wraps(f)
    def wrapper() -> object:
        return f()

    return wrapper


@pytest.mark.parametrize("function", [decorated(my_score), functools.partial(my_score)])
def test_a_wrapped_function_keeps_the_original(function: Callable[[], object]) -> None:
    with pytest.raises(KeyError) as caught:  # the user's exception, never one of the helper's
        engine_calls(function)
    line = my_score.__code__.co_firstlineno + 1
    assert f"test_user_exception_note.py:{line} in my_score" in caught.value.__notes__[0]


def shape() -> object:
    raise ValueError("operands could not be broadcast together with shapes (3,) (4,)")


def none() -> object:
    raise TypeError("unsupported operand type(s) for +: 'NoneType' and 'float'")


@pytest.mark.parametrize(
    ("function", "fix"),
    [
        (lambda: [1.0][5], "window="),
        (shape, "(n_alive,)"),
        (none, "missing value"),
        (lambda: 1 / 0, "np.where"),
        (lambda: int("x"), "check <lambda> at test_user_exception_note.py:"),
        (lambda: math.exp(1000), "check <lambda>"),  # OverflowError: not in the 6.6 table
    ],
)
def test_fix_line_from_hints(function: Callable[[], object], fix: str) -> None:
    with pytest.raises((LookupError, ValueError, TypeError, ArithmeticError)) as caught:
        engine_calls(function)
    assert fix in caught.value.__notes__[1]
    if fix.startswith("check"):  # the general sentence, for an exception the table lacks
        assert caught.value.__notes__[1].endswith("nx.explain(strategy, 'A1', '2020-03-02')")
