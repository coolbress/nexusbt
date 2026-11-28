"""A cell where the instrument is not listed holds no term's value (5.3.1, 3.3; decision
2026-11-19, #563): a later row that reads it through `shift` or a window reads "absent", not the
value a term would have computed there, so "listed yesterday with no close" and "not listed
yesterday" stay different events."""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest

import nexusbt as nx
from nexusbt.compute._executor import execute
from nexusbt.data._block import MarketBlock
from nexusbt.pipeline import BoundColumn, Factor, Term, graph_hash
from nexusbt.pipeline._terms import _operand

pytestmark = pytest.mark.unit

NAN = float("nan")
#: T00001 listed throughout, no close at row 2; T00002 lists at row 3; T00003 is delisted at
#: row 2 and listed again at row 3, the block still holding it (the issue's table, #563).
IDS = ("KR:T00001", "KR:T00002", "KR:T00003")
LISTED = np.array([[1, 0, 1], [1, 0, 1], [1, 0, 0], [1, 1, 1], [1, 1, 1]], dtype=bool)
CLOSE = np.array(
    [[10, NAN, 30], [11, NAN, 31], [NAN, NAN, NAN], [12, 20, 32], [13, 21, 33]], dtype=float
)
DATES = np.datetime64("2020-01-01") + np.arange(5).astype("timedelta64[D]")
READY = (DATES + np.timedelta64(16, "h")).astype("datetime64[us]")
PRICE_CLOSE = BoundColumn.of("Price", "close")
#: The value as traded: degree 0, so a window may read a term made from it (3.4, E17).
AS_TRADED = BoundColumn.of("Price", "close_unadjusted")


def block() -> MarketBlock:
    seen = ~np.isnan(CLOSE)
    available = np.where(seen, READY[:, None], np.datetime64("NaT", "us"))
    values = {"close": CLOSE, "close_unadjusted": CLOSE}
    status = np.zeros(CLOSE.shape, np.int8)
    return MarketBlock("KR", DATES, 0, IDS, values, LISTED, status, available)


def at(term: Term, row: int) -> dict[str, Any]:
    """The term's value per listed instrument at the row (None: unknown or NaN)."""
    whole = block()
    table = execute([term], [row], [(0, 4)], lambda a, b: _rows(whole, a, b), READY)
    found = table[graph_hash(term)].to_pylist()
    return {r["instrument_id"]: _plain(r["value"]) for r in found}


def _rows(whole: MarketBlock, first: int, last: int) -> MarketBlock:
    s = slice(first, last + 1)
    values = {k: v[s] for k, v in whole.values.items()}
    cells = (whole.exists[s], whole.obs_status[s], whole.ts_available[s])
    return MarketBlock(whole.market, whole.dates[s], 0, whole.instrument_ids, values, *cells)


def _plain(value: Any) -> Any:
    return None if value is None or (isinstance(value, float) and np.isnan(value)) else value


def missing_yesterday() -> Factor:
    return PRICE_CLOSE.latest.isnan().as_factor().shift(1)


def test_shift_reads_a_cell_before_listing_as_unknown() -> None:
    """The issue's table: at row 3 the instrument listed with no close at row 2 is true, the one
    that was not listed at row 2 is unknown, and both are false at row 4."""
    term = missing_yesterday() > 0
    assert at(term, 2) == {"KR:T00001": False}
    assert at(term, 3) == {"KR:T00001": True, "KR:T00002": None, "KR:T00003": None}
    assert at(term, 4) == {"KR:T00001": False, "KR:T00002": False, "KR:T00003": False}


def test_a_window_reads_unlisted_cells_as_missing_not_as_true() -> None:
    """A count of missing closes over rows 2..4: row 2 is before T00002's listing and after
    T00003's delisting, so the window applies its own rule for NaN there (3.4): with
    `min_periods` = the window it is NaN, with `min_periods=1` it counts the listed rows only.
    Kleene `any` of the test is unknown, not true. T00001 had no close at row 2 and counts it."""
    missing = PRICE_CLOSE.latest.isnan()
    whole = nx.ops.rolling(missing.as_factor(), 3).sum()
    listed = nx.ops.rolling(missing.as_factor(), 3, min_periods=1).sum()
    assert at(whole, 4) == {"KR:T00001": 1.0, "KR:T00002": None, "KR:T00003": None}
    assert at(listed, 4) == {"KR:T00001": 1.0, "KR:T00002": 0.0, "KR:T00003": 0.0}
    assert at(missing.any(3), 4) == {"KR:T00001": True, "KR:T00002": None, "KR:T00003": None}


def test_fillna_fills_listed_cells_only() -> None:
    """`fillna(0)` gives 0 where the instrument is listed with no close (T00001 at row 2) and
    leaves an unlisted cell absent, so a window over it does not count a 0 before listing or
    after delisting: the means over rows 2..4 are of the listed rows."""
    filled = AS_TRADED.latest.fillna(0)
    assert at(filled.shift(1), 3) == {"KR:T00001": 0.0, "KR:T00002": None, "KR:T00003": None}
    expected = {"KR:T00001": 25 / 3, "KR:T00002": 20.5, "KR:T00003": 32.5}
    assert at(nx.ops.rolling(filled, 3, min_periods=1).mean(), 4) == pytest.approx(expected)
    assert at(nx.factors.SMA(3, inputs=[filled], min_periods=1), 4) == pytest.approx(expected)


def test_constant_and_if_else_are_absent_where_not_listed() -> None:
    """A constant and an `if_else` whose condition is always valid are absent at an unlisted
    cell too, as a later row reads them."""
    constant = _operand(5.0)
    picked = PRICE_CLOSE.latest.isnan().if_else(_operand(1.0), _operand(0.0))
    assert at(constant.shift(1), 3) == {"KR:T00001": 5.0, "KR:T00002": None, "KR:T00003": None}
    assert at(picked.shift(1), 3) == {"KR:T00001": 1.0, "KR:T00002": None, "KR:T00003": None}
