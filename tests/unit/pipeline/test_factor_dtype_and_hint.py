"""Spec 3.3: `@nx.factor`'s `dtype` takes `"float64"` only, any other value E16 when the term is
built (#638); the `.function` call E16 shows for a call with an array writes a bound NaN or
infinity as Python a user can paste (#624)."""

from __future__ import annotations

import ast
import math
import re
from typing import Any

import numpy as np
import pytest

import nexusbt as nx
from nexusbt.contracts import ConfigError
from nexusbt.pipeline import BoundColumn, graph_hash

CLOSE = BoundColumn.of("Price", "close")

#: The graph hash of `_ratio` built with `dtype="float64"` or with no `dtype`, on `main` at
#: 1d8495f, before #638: refusing other values changes neither.
PINNED = "6f2c0c4fa09cc3979badb52536e7a0d065d6ca7b278659b103aae49423c3cda5"


def _ratio(close: Any, *, n: Any = 1.0) -> Any:
    return close[-1] / close[0]


@pytest.mark.parametrize("dtype", ["float32", "int64", "bogus"])
def test_a_dtype_other_than_float64_is_refused_at_build(dtype: Any) -> None:
    """#638 AC 1: E16 when the term is built, naming the argument, the value and `"float64"`."""
    with pytest.raises(ConfigError) as caught:
        nx.factor(window=2, inputs=[CLOSE], dtype=dtype)(_ratio)
    error = caught.value
    assert error.code == "E16"
    assert f"dtype={dtype!r}" in error.parts["what"], error.parts["what"]
    assert error.parts["fix"] == "dtype= one of 'float64'", error.parts["fix"]


def test_float64_and_no_dtype_keep_their_graph_hash() -> None:
    """#638 AC 2: `dtype="float64"` and no `dtype` give the hash they gave before #638."""
    declared = nx.factor(window=2, inputs=[CLOSE], dtype="float64")(_ratio)
    assert graph_hash(declared) == graph_hash(nx.factor(window=2, inputs=[CLOSE])(_ratio))
    assert graph_hash(declared) == PINNED


def _shown(bound: Any) -> Any:
    """The value of `n` in the `.function` call the E16 of `_ratio(n=bound)(array)` shows,
    evaluated as a user pasting it would."""
    term = nx.factor(window=2, inputs=[CLOSE])(_ratio)(n=bound)
    with pytest.raises(ConfigError) as caught:
        term(np.ones((2, 3)))
    call = re.fullmatch(r"(.*) on the arrays, one for each input", caught.value.parts["fix"])
    assert call is not None, caught.value.parts["fix"]
    parsed = ast.parse(call[1], mode="eval").body
    assert isinstance(parsed, ast.Call)
    (keyword,) = parsed.keywords
    return eval(ast.unparse(keyword.value), {"float": float})  # noqa: S307 - the pasted text


@pytest.mark.parametrize("bound", [math.nan, math.inf, -math.inf])
def test_a_bound_nan_or_infinity_is_shown_as_python(bound: float) -> None:
    """#624 AC 1: the shown call, pasted, gives `n` its NaN, `inf` or `-inf`."""
    got = _shown(bound)
    assert math.isnan(got) if math.isnan(bound) else got == bound


def test_one_inside_a_bound_tuple_is_shown_as_python() -> None:
    """#624 AC 1: the same for one inside a bound tuple, the other values as before."""
    got = _shown((1.0, math.nan, -math.inf))
    assert got[0] == 1.0
    assert math.isnan(got[1])
    assert got[2] == -math.inf


def test_a_bound_frozensets_items_are_shown_in_one_order() -> None:
    """#814's uncovered line: a frozenset's items are shown sorted by their text, so the hint
    reads the same in every run (a set of strings is met in another order in each process);
    the order is only the message's, never a computed value or a graph hash. Pasted, it gives
    the set back, a NaN in it too."""
    term = nx.factor(window=2, inputs=[CLOSE])(_ratio)(n=frozenset("fbdace"))
    with pytest.raises(ConfigError) as caught:
        term(np.ones((2, 3)))
    assert "n=frozenset({'a', 'b', 'c', 'd', 'e', 'f'})" in caught.value.parts["fix"]
    got = _shown(frozenset({2.0, math.nan, -math.inf}))
    assert {x for x in got if not math.isnan(x)} == {2.0, -math.inf}
    assert sum(math.isnan(x) for x in got) == 1
