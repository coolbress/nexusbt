"""Spec 3.3 and 5.3.9: term value objects, operators and the graph hash."""

from __future__ import annotations

from typing import Any

import pytest

import nexusbt as nx
from nexusbt.factors import Returns
from nexusbt.pipeline import graph_hash


def test_negative_shift_raises_E1() -> None:  # noqa: N802 - the ticket's test name
    x = Returns(21)
    assert graph_hash(x.shift(0)) == graph_hash(x)  # 3.3: `k = 0` is unchanged
    with pytest.raises(nx.LookAheadError) as caught:
        x.shift(-1)
    assert caught.value.code == "E1"
    assert "test_terms.py:" in str(caught.value)  # the user's line, 6.6 header
    not_an_int: Any = 1.5
    with pytest.raises(TypeError):
        x.shift(not_an_int)  # 3.3: `shift(k: int)`


def test_graph_hash_stable_and_order_sensitive() -> None:
    a, b = Returns(232).shift(21) + 1, Returns(232).shift(21) + 1
    assert a is not b
    assert graph_hash(a) == graph_hash(b)
    assert hash(a) == hash(b)
    assert graph_hash(Returns(21) - Returns(63)) != graph_hash(Returns(63) - Returns(21))
    assert graph_hash(Returns(21) - 1) != graph_hash(1 - Returns(21))
    assert graph_hash(Returns(21)) != graph_hash(Returns(22))
    masked = Returns(21, mask=Returns(5) > 0)
    assert graph_hash(masked) != graph_hash(Returns(21))
    text = str(nx.describe(a))
    assert graph_hash(a) in text
    assert [line.strip() for line in text.splitlines()[:5]] == [
        "Factor add",
        "Factor shift k=21",
        "Factor Returns window=232",
        "BoundColumn Price.close_tr",
        "Factor constant value=1.0",
    ]
    assert "  mask=Filter gt" in str(nx.describe(masked))


def test_elementwise_operators_name_their_node() -> None:
    x, y = Returns(21), Returns(63)
    built = {"add": x + y, "sub": x - y, "mul": x * 2, "div": x / y, "pow": x**2, "neg": -x,
             "abs": abs(x), "log": x.log(), "log1p": x.log1p(), "exp": x.exp(), "sqrt": x.sqrt(),
             "lt": x < y, "le": x <= 0, "gt": x > 0, "ge": x >= y, "eq": x == y, "ne": x != 0,
             "isnan": x.isnan(), "notnan": x.notnan(), "isfinite": x.isfinite(),
             "isnull": x.isnull(), "notnull": x.notnull()}  # fmt: skip
    assert {op: term.op for op, term in built.items()} == {op: op for op in built}
    assert (2 * x).inputs[1] is x  # a scalar on the left stays on the left
    assert Returns(21, inputs=[]).inputs == ()  # an empty list is not the default input
    close = Returns(21).inputs[0]
    assert isinstance(close, nx.BoundColumn)
    assert close.latest.op == "latest"
    assert x.notnan() == Returns(21).notnan()  # a Filter compares by its hash
    assert x.notnan() != y.notnan()
    not_a_number: Any = "1"
    with pytest.raises(TypeError):
        x + not_a_number
    not_a_window: Any = [21]
    with pytest.raises(TypeError):
        Returns(not_a_window)  # a list cannot be a parameter


def test_pipeline_object_columns_screen() -> None:
    mom = Returns(232).shift(21)
    screen = mom.notnan()
    pipe = nx.Pipeline({"mom": mom, "neg": -mom}, screen=screen)
    assert list(pipe.columns) == ["mom", "neg"]
    assert pipe.columns["mom"] is mom
    assert pipe.screen is screen
    assert nx.Pipeline({"mom": mom}).screen is None
    not_a_filter: Any = mom
    with pytest.raises(TypeError):
        nx.Pipeline({"mom": mom}, screen=not_a_filter)  # 3.5: `screen: Filter | None`
    not_a_term: Any = 1.0
    with pytest.raises(TypeError):
        nx.Pipeline({"mom": not_a_term})  # 3.5: `columns: Mapping[str, Term]`
