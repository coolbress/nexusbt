"""Spec 3.3 `nx.ops` through the reference executor: `rolling` over a term's values, each fixed
at its row (5.1.2), and the explicit fills `where` and `coalesce` (5.4.1, INV-12)."""

from __future__ import annotations

import math

import numpy as np
import pytest

import nexusbt as nx
from nexusbt import ops
from nexusbt.compute._executor import execute
from nexusbt.contracts import SchemaRegistry
from nexusbt.data._block import MarketBlock
from nexusbt.pipeline import Factor, Price, bind, graph_hash

pytestmark = pytest.mark.unit

NAN = math.nan
#: `.latest` of a column with degree 0 (3.4), so a window over it is not refused.
VALUE, CLOSE = Price.value_traded.latest, Price.close.latest


def run(term: Factor, **columns: list[float]) -> list[float]:
    """`term` at every row of one instrument whose columns are `columns`, each cell on time."""
    n = len(next(iter(columns.values())))
    dates = np.datetime64("2020-01-01") + np.arange(n).astype("timedelta64[D]")
    ready = (dates + np.timedelta64(16, "h")).astype("datetime64[us]")
    values = {k: np.array(v, dtype=np.float64)[:, None] for k, v in columns.items()}
    exists, status = np.ones((n, 1), bool), np.zeros((n, 1), np.int8)
    block = MarketBlock("XX", dates, 0, ("A",), values, exists, status, ready[:, None])
    found = execute([term], range(n), [(0, n - 1)], lambda a, b: block, ready)
    cells: list[float] = found[graph_hash(term)]["value"].to_pylist()
    return cells


def same(found: list[float], expected: list[float]) -> None:
    assert found == pytest.approx(expected, abs=1e-12, nan_ok=True)


def test_ops_is_on_nx() -> None:
    """3.1's Terms row: `nx.ops` after `import nexusbt as nx`."""
    assert nx.ops is ops


def test_rolling_min_periods() -> None:
    """A row's value needs `min_periods` finite cells in the window (default: the window); NaN
    cells are left out; the window looks backward only, NaN until it fits on the axis."""
    x = [1, NAN, 3, 4, NAN, NAN, 8]
    same(run(ops.rolling(VALUE, 3).mean(), value_traded=x),
         [NAN, NAN, NAN, NAN, NAN, NAN, NAN])  # fmt: skip
    same(run(ops.rolling(VALUE, 3, min_periods=2).mean(), value_traded=x),
         [NAN, NAN, 2.0, 3.5, 3.5, NAN, NAN])  # fmt: skip
    same(run(ops.rolling(VALUE, 3, min_periods=1).sum(), value_traded=x),
         [NAN, NAN, 4.0, 7.0, 7.0, 4.0, 8.0])  # fmt: skip


def test_rolling_operations() -> None:
    """`mean`, `sum`, `std` (ddof 1), `min`, `max`, `median` of the finite cells."""
    x = [4.0, 1.0, 3.0, 2.0]
    found = {how: run(getattr(ops.rolling(VALUE, 4), how)(), value_traded=x)[-1]
             for how in ("mean", "sum", "std", "min", "max", "median")}  # fmt: skip
    assert found == pytest.approx(
        {"mean": 2.5, "sum": 10.0, "std": math.sqrt(5 / 3), "min": 1.0, "max": 4.0, "median": 2.5}
    )
    assert run(ops.rolling(VALUE, 3).median(), value_traded=[5, 1, 3])[-1] == 3.0


def test_rolling_arguments() -> None:
    """`x` is a Factor; `window` and `min_periods` whole numbers, `1 <= min_periods <= window`,
    so a float window cannot slip past #499's check (which reads an int window)."""
    with pytest.raises(TypeError, match="a Factor"):
        ops.rolling(Price.close, 3)
    for window, least in ((3.0, None), (True, None), (3, 2.0)):
        with pytest.raises(TypeError, match="whole numbers"):
            ops.rolling(VALUE, window, min_periods=least)  # type: ignore[arg-type]
    for window, least in ((0, None), (3, 4), (3, 0)):
        with pytest.raises(ValueError, match="min_periods <= window"):
            ops.rolling(VALUE, window, min_periods=least)


def test_rolling_over_a_price_level_is_refused() -> None:
    """#243 Decisions 2026-11-18: `rolling` reads a term's values, so a price level is E17 and
    a degree-0 term passes."""
    registry = SchemaRegistry(columns={}, labels={})
    with pytest.raises(nx.TermDomainError) as caught:
        bind(ops.rolling(CLOSE, 3).mean(), registry)
    assert caught.value.code == "E17"
    bind(ops.rolling(CLOSE / Price.open.latest, 3).mean(), registry)


def test_coalesce_explicit_fill() -> None:
    """INV-12: `coalesce` takes, cell by cell, the first of its terms that is not NaN, and
    fills nothing it is not given: with one term, a NaN stays NaN."""
    a, b = VALUE, Price.market_cap.latest
    columns = {"value_traded": [1, NAN, NAN], "market_cap": [10, 20, NAN]}
    same(run(ops.coalesce(a, b), **columns), [1.0, 20.0, NAN])
    same(run(ops.coalesce(a, b, 0.0), **columns), [1.0, 20.0, 0.0])
    same(run(ops.coalesce(a), **columns), [1.0, NAN, NAN])
    with pytest.raises(TypeError, match="at least one"):
        ops.coalesce()


def test_where_explicit_fill() -> None:
    """`where(cond, a, b)`: a where cond is true, b where false, NaN where it is unknown."""
    cond = VALUE > 2
    found = run(ops.where(cond, VALUE, -1.0), value_traded=[1, 3, NAN])
    same(found, [-1.0, 3.0, NAN])
