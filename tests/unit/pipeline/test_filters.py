"""Spec 3.3, 5.4.1 [V31-21, R3-13]: three-valued Filters through the reference executor.

A Filter's cell is true, false or unknown; the executor's table gives it as a boolean that is
null where the cell is unknown.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pyarrow as pa
import pytest

from nexusbt.compute import _kernels as k
from nexusbt.compute._executor import execute
from nexusbt.data._block import MarketBlock
from nexusbt.pipeline import BoundColumn, Term, graph_hash

pytestmark = pytest.mark.unit

N = np.nan
U = None  # an unknown cell in a table
CLOSE, OPEN = BoundColumn.of("Price", "close"), BoundColumn.of("Price", "open")
#: Nine instruments: each pair of (close > 0, open > 0) in true, false, unknown.
PAIRS = [(1.0, 1.0), (1.0, -1.0), (1.0, N), (-1.0, 1.0), (-1.0, -1.0), (-1.0, N),
         (N, 1.0), (N, -1.0), (N, N)]  # fmt: skip


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


def values(terms: list[Term], whole: MarketBlock) -> list[list[Any]]:
    """Each term's cells at the last row, in instrument order."""
    last = len(whole.dates) - 1
    ready = (whole.dates + np.timedelta64(16, "h")).astype("datetime64[us]")
    found = execute(terms, [last], [(0, last)], lambda a, b: whole, ready)
    tables: list[pa.Table] = [found[graph_hash(t)] for t in terms]
    return [t["value"].to_pylist() for t in tables]


def pairs() -> MarketBlock:
    return block(close=[[c for c, _ in PAIRS]], open=[[o for _, o in PAIRS]])


def test_kleene_and_or() -> None:
    """`&` and `|` are Kleene: false & unknown = false, true | unknown = true, the rest of the
    pairs with an unknown are unknown (5.4.1)."""
    a, b = CLOSE.latest > 0, OPEN.latest > 0
    both, either = values([a & b, a | b], pairs())
    assert both == [True, False, U, False, False, False, U, False, U]
    assert either == [True, True, True, True, False, U, True, U, U]


def test_not_keeps_unknown() -> None:
    """`~` inverts the value and keeps validity: a halted instrument, with no close, is unknown
    in `~(close > 10_000)`, not true as v3 (and zipline) made it (5.4.1)."""
    halted = block(close=[[12_000.0, 8_000.0, N]])
    above = CLOSE.latest > 10_000
    assert values([above, ~above, ~~above], halted) == [
        [True, False, U], [False, True, U], [True, False, U]]  # fmt: skip


def test_isnan_always_valid() -> None:
    """`isnan`, `notnan`, `isfinite`, `isnull` and `notnull` are never unknown, a missing
    input included; so `(close > 0) | close.isnan()` is known everywhere (5.4.1)."""
    x = CLOSE.latest
    found = values([x.isnan(), x.notnan(), x.isfinite(), x.isnull(), x.notnull(),
                    (x > 0) | x.isnan()], block(close=[[1.0, N, -1.0]]))  # fmt: skip
    assert found == [
        [False, True, False],
        [True, False, True],
        [True, False, True],
        [False, True, False],
        [True, False, True],
        [True, True, False],
    ]


def test_all_any_kleene() -> None:
    """`all(2)` is false when one session is false, else unknown when one is unknown; `any(2)` is
    true when one is true, else unknown when one is unknown (3.3, R3-13). The two sessions are
    the rows of `PAIRS`."""
    up = CLOSE.latest > 0
    two = block(close=[[a for a, _ in PAIRS], [b for _, b in PAIRS]])
    every, some = values([up.all(2), up.any(2)], two)
    assert every == [True, False, U, False, False, False, U, False, U]
    assert some == [True, True, True, True, False, U, True, U, U]


def test_edges_of_the_filter_terms() -> None:
    """A window that starts before the axis is unknown, as a user window is NaN there (the spec
    does not say; #535); a Filter term not built yet and a comparison code out of range are
    refused."""
    assert values([(CLOSE.latest > 0).all(3)], block(close=[[-1.0], [1.0]])) == [[U]]
    with pytest.raises(NotImplementedError, match="no `top` term"):
        values([CLOSE.latest.top(1)], block(close=[[1.0]]))
    with pytest.raises(ValueError, match="no comparison has code 6"):
        k.compare(6, np.zeros(1), np.zeros(1))


def test_as_factor_unknown_nan() -> None:
    """`as_factor()` gives 1.0, 0.0 and NaN for unknown; `if_else` is NaN where its condition is
    unknown; `fillna(bool)` is the only fill (3.3, R3-13, INV-12)."""
    up = CLOSE.latest > 10_000
    x = block(close=[[12_000.0, 8_000.0, N]], open=[[1.0, 2.0, 3.0]])
    picked = up.if_else(OPEN.latest, -OPEN.latest)
    factor, chosen, yes, no = values([up.as_factor(), picked, up.fillna(True), up.fillna(False)], x)
    assert np.array_equal(factor, [1.0, 0.0, N], equal_nan=True)
    assert np.array_equal(chosen, [1.0, -2.0, N], equal_nan=True)
    assert (yes, no) == ([True, False, True], [True, False, False])
