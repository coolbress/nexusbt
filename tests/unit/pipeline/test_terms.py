"""Spec 3.3, 5.3.9, 6.5 (6): term value objects, operators, the graph hash, captured constants."""

from __future__ import annotations

from typing import Any

import pytest

import nexusbt as nx
from nexusbt.factors import Returns
from nexusbt.pipeline import Classifier, Factor, Filter, graph_hash

THRESHOLD = 10


def test_operator_result_types() -> None:
    x, y = Returns(21), Returns(63)
    for f in (x + y, -x, x.rank(), x.zscore(), x.demean(), x.winsorize(0.01, 0.99),
              x.pct_rank(na="bottom"), x.fillna(0.0), x.clip(lower=0.0), x.shift(1), x.to("USD"),
              (x > 0).if_else(x, y), (x > 0).as_factor()):  # fmt: skip
        assert type(f) is Factor
    for p in (x < y, x.top(10), x.bottom(10), x.percentile_between(10, 90), x.notnan(),
              (x > 0) & (y > 0), (x > 0) | (y > 0), ~(x > 0), (x > 0).all(5), (x > 0).any(5),
              (x > 0).fillna(False)):  # fmt: skip
        assert type(p) is Filter
    for c in (x.quantiles(5), x.quartiles(), x.quintiles(), x.deciles()):
        assert type(c) is Classifier
        for p in (c.eq(1), c.element_of([1, 2]), c.isnull(), c.notnull(), c.startswith("A")):
            assert type(p) is Filter
    assert x.quartiles() == x.quantiles(4)
    assert x.zscore(x > 0) == x.zscore(mask=x > 0)  # the 3.3 keywords also by position
    c = x.quartiles()
    assert c.element_of({"B", "A"}) == c.element_of(frozenset({"A", "B"}))
    not_a_bool: Any = 1
    with pytest.raises(TypeError):
        (x > 0).fillna(not_a_bool)
    not_a_term: Any = 1
    with pytest.raises(TypeError):
        Returns(21, inputs=[not_a_term])
    assert x.rank(mask=x > 0) != x.rank()
    assert "  mask=Filter gt" in str(nx.describe(x.rank(mask=x > 0)))
    with pytest.raises(nx.CapabilityError):
        x.downsample("monthly")
    not_a_filter: Any = x
    with pytest.raises(TypeError):
        (x > 0) & not_a_filter


def _above(close: Any) -> Any:
    return close[-1] > THRESHOLD


def test_captured_scalar_changes_hash(monkeypatch: pytest.MonkeyPatch) -> None:
    def build() -> Factor:
        return nx.factor(window=5, inputs=[Returns(1)])(_above)

    at_10 = graph_hash(build())
    assert at_10 == graph_hash(build())
    assert "Factor user THRESHOLD=10 window=5" in str(nx.describe(build()))
    monkeypatch.setitem(globals(), "THRESHOLD", 20)
    assert graph_hash(build()) != at_10
    limit = (1, 2.5)
    closure = nx.factor(window=5, inputs=[Returns(1)])(lambda c: c[-1] > limit[0])
    assert ("limit", (1, 2.5)) in dict(closure.params)["captured"]
    names = frozenset({"A", "B"})
    deco = nx.factor(window=5, inputs=[Returns(1)])
    sets = deco(lambda c: c in names)
    assert ("names", names) in dict(sets.params)["captured"]
    assert graph_hash(deco(lambda c: c[-1] > 1)) != graph_hash(deco(lambda c: c[-1] > 2))
    make = lambda c: lambda d: d * 3  # noqa: E731 - a lambda whose body is a lambda
    assert graph_hash(deco(make)) != graph_hash(deco(make(0)))  # each picks its own node
    table = [1, 2]  # not constant-like: left to T1.12's E24
    assert dict(deco(lambda c: c > table[0]).params)["captured"] == ()
    not_a_function: Any = len
    with pytest.raises(TypeError):
        deco(not_a_function)
    with pytest.raises(TypeError, match="has no value yet"):
        deco(lambda c: c > later)
    later = 1
    with pytest.raises(TypeError, match="cannot read the source"):
        deco(eval("lambda c: c"))  # noqa: S307 - a function without a source file
    with pytest.raises(TypeError):
        Returns(21).quartiles().element_of("AB")
    inner = deco(_reads_through_inner)
    monkeypatch.setitem(globals(), "THRESHOLD", 40)
    assert graph_hash(deco(_reads_through_inner)) != graph_hash(inner)  # an inner function's read
    with_default = deco(_above_default)
    defaults: Any = _above_default.__kwdefaults__
    monkeypatch.setitem(defaults, "n", 30)  # as if the file now said `THRESHOLD = 30`
    assert graph_hash(deco(_above_default)) != graph_hash(with_default)  # `n=THRESHOLD` too


def _reads_through_inner(close: Any) -> Any:
    def above(x: Any) -> Any:
        return x > THRESHOLD

    return above(close[-1])


def _above_default(close: Any, *, n: int = THRESHOLD) -> Any:
    return close[-1] > n


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
