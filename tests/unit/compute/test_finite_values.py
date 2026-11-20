"""Spec 5.4.1 (decision 2026-11-18, #536): a Factor's value is a finite number or NaN, at every
term. Where a term's result would be ±inf, that term's value in that cell is NaN, so no reader,
comparison or `isfinite()` meets an `inf`. The counts of 5.4.1 are not kept here (#249)."""

from __future__ import annotations

from typing import Any

import numpy as np
import pyarrow as pa
import pytest

import nexusbt as nx
from nexusbt.compute._executor import execute
from nexusbt.data._block import MarketBlock
from nexusbt.pipeline import BoundColumn, Term, factor, graph_hash
from nexusbt.pipeline.factors import SMA, AnnualizedVolatility, DailyReturns

pytestmark = pytest.mark.unit

N = np.nan
U = None  # an unknown Filter cell in a table
CLOSE, OPEN = BoundColumn.of("Price", "close"), BoundColumn.of("Price", "open")


def block(**columns: list[list[float]]) -> MarketBlock:
    """Rows of a whole axis, one column a list of rows; every instrument listed, every bar seen."""
    values = {name: np.array(rows, dtype=np.float64) for name, rows in columns.items()}
    shape = next(iter(values.values())).shape
    dates = np.datetime64("2020-01-01") + np.arange(shape[0]).astype("timedelta64[D]")
    ready = (dates + np.timedelta64(16, "h")).astype("datetime64[us]")
    ids = tuple(f"I{i}" for i in range(shape[1]))
    seen = np.broadcast_to(ready[:, None], shape).copy()
    status = np.zeros(shape, np.int8)
    return MarketBlock("XX", dates, 0, ids, values, np.ones(shape, bool), status, seen)


def values(
    terms: list[Term], whole: MarketBlock, functions: dict[str, Any] | None = None
) -> list[list[Any]]:
    """Each term's cells at the last row, in instrument order."""
    last = len(whole.dates) - 1
    ready = (whole.dates + np.timedelta64(16, "h")).astype("datetime64[us]")
    found = execute(terms, [last], [(0, last)], lambda a, b: whole, ready, functions)
    tables: list[pa.Table] = [found[graph_hash(t)] for t in terms]
    return [t["value"].to_pylist() for t in tables]


def nan(cells: list[Any]) -> bool:
    return all(isinstance(c, float) and np.isnan(c) for c in cells)


#: Each cell would be ±inf (or NaN) under IEEE: a division by 0, `0/0`, `log(0)`, and overflows.
CASES = {
    "x / 0": (CLOSE.latest / OPEN.latest, {"close": [[1.0, -1.0, 0.0]], "open": [[0.0] * 3]}),
    "log(0)": (CLOSE.latest.log(), {"close": [[0.0, 0.0, 0.0]]}),
    "exp overflow": (CLOSE.latest.exp(), {"close": [[1000.0, 800.0, 710.0]]}),
    "** overflow": (CLOSE.latest**1000.0, {"close": [[10.0, -10.0, 1e10]]}),
}


@pytest.mark.parametrize("name", list(CASES))
def test_a_term_whose_result_would_be_inf_is_nan_at_that_term(name: str) -> None:
    """The producing term's own value is NaN, and a term reading it sees NaN."""
    term, columns = CASES[name]
    own, negated = values([term, -term], block(**columns))
    assert nan(own), own
    assert nan(negated), negated


def _infinite(w: Any) -> Any:
    return np.where(w[-1] > 0, np.inf, -np.inf)


def test_a_user_function_returning_inf_is_nan_at_its_term() -> None:
    user = factor(1, [CLOSE])(_infinite)
    (found,) = values([user], block(close=[[1.0, -1.0, 2.0]]), {graph_hash(user): _infinite})
    assert nan(found), found


def test_a_comparison_with_a_division_by_zero_is_unknown_and_isfinite_is_false_and_known() -> None:
    """`(x / 0) > 1` is unknown, not true; `(x / 0).isfinite()` is false, never unknown."""
    ratio = CLOSE.latest / OPEN.latest
    whole = block(close=[[1.0, -1.0, 4.0]], open=[[0.0, 0.0, 2.0]])
    above, finite = values([ratio > 1, ratio.isfinite()], whole)
    assert above == [U, U, True]
    assert finite == [False, False, True]


def test_a_built_in_factor_reading_an_inf_term_sees_nan() -> None:
    """`SMA` over a division by zero is the mean of the finite cells, as over a NaN cell (3.4)."""
    ratio = CLOSE.latest / OPEN.latest
    whole = block(close=[[1.0], [6.0]], open=[[0.0], [2.0]])
    with_nan = block(close=[[N], [6.0]], open=[[1.0], [2.0]])
    assert values([SMA(2, [ratio])], whole) == values([SMA(2, [ratio])], with_nan) == [[3.0]]


def test_annualized_volatility_leaves_out_a_return_over_a_zero_price() -> None:
    """#632 Decisions: 3.4's `nanstd(DailyReturns window, ddof=0)`, so a return over a zero
    price is `DailyReturns`' NaN and left out, as in `rolling(DailyReturns(), W).std()`. Closes
    1, 0, 2, 3, 5 give the returns -1, 2/0, 0.5, 2/3: three kept, so ddof 0 is ddof 1 times
    sqrt(2/3)."""
    whole = block(close=[[1.0], [0.0], [2.0], [3.0], [5.0]])
    vol = AnnualizedVolatility(4, annualization_factor=252, inputs=[CLOSE])
    std = nx.ops.rolling(DailyReturns(inputs=[CLOSE]), 4, 1).std()
    [[found]], [[sample]] = values([vol], whole), values([std], whole)
    assert found == pytest.approx(sample * np.sqrt(2 / 3) * np.sqrt(252), rel=1e-12)
