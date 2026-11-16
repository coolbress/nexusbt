"""The 5.3.2 plan: which rows each node computes, T1.7a (#239)."""

from __future__ import annotations

import pytest

from nexusbt.compute._plan import plan
from nexusbt.pipeline import BoundColumn, Factor, factor
from nexusbt.pipeline.factors import Returns

pytestmark = pytest.mark.unit

CLOSE = BoundColumn.of("Price", "close")


def _mean(x: object) -> float:
    return 0.0


def sma(window: int, of: BoundColumn | Factor) -> Factor:
    return factor(window, [of])(_mean)


def test_window_rows_propagate() -> None:
    """A window-W term at row r reads its input on [r-W+1, r] (5.3.2 (2))."""
    ret = Returns(3, inputs=[CLOSE])
    p = plan([ret], rows=[10, 20], sessions=30)
    assert p.rows_of(ret) == [10, 20]
    assert p.rows_of(CLOSE) == [8, 9, 10, 18, 19, 20]


def test_shift_rows_propagate() -> None:
    """`shift(k)` at rows R reads its input at R - k (5.3.2 (2)); rows before the axis drop."""
    ret = Returns(2, inputs=[CLOSE])
    lagged = ret.shift(5)
    p = plan([lagged], rows=[3, 12], sessions=30)
    assert p.rows_of(lagged) == [3, 12]
    assert p.rows_of(ret) == [7]
    assert p.rows_of(CLOSE) == [6, 7]


def test_nested_windows_across_chunks() -> None:
    """A chunk starting at row 100 reads 14 rows of the one before, not just `W_max - 1 = 9`;
    planning each chunk's decisions alone gives the rows of planning them all (INV-03)."""
    inner = sma(10, CLOSE)
    outer = sma(5, inner).shift(2)
    p = plan([outer], rows=[100], sessions=200)
    assert p.rows_of(CLOSE) == list(range(85, 99))
    assert p.rows_of(inner) == list(range(94, 99))
    chunks = [[40, 60, 80], [100, 120], [140, 199]]
    whole = plan([outer], rows=[r for c in chunks for r in c], sessions=200)
    parts = [plan([outer], rows=c, sessions=200) for c in chunks]
    for node in (outer, inner, CLOSE):
        assert whole.rows_of(node) == sorted({r for q in parts for r in q.rows_of(node)})


def test_shared_node_computed_once() -> None:
    """Two outputs using the same structure share one node, which computes the union of the rows
    both need (5.3.2 (5))."""
    a, b = Returns(3, inputs=[CLOSE]), Returns(3, inputs=[CLOSE])
    p = plan([a, b.shift(4)], rows=[10], sessions=30)
    assert len(p.rows) == 3  # Returns(3), its shift, and the column
    assert p.rows_of(a) == [6, 10]
    assert p.rows_of(CLOSE) == [4, 5, 6, 8, 9, 10]


def test_daily_cross_section_feeding_window_computed() -> None:
    """A rank under a 20-row window is computed on every daily row the window covers, and its
    mask with it, though the decisions are monthly (5.3.2 (3))."""
    price = CLOSE.latest
    liquid = price > 1.0
    ranked = price.rank(mask=liquid)
    smooth = sma(20, ranked)
    p = plan([smooth], rows=[50, 100], sessions=120)
    covered = [*range(31, 51), *range(81, 101)]
    assert p.rows_of(smooth) == [50, 100]
    assert p.rows_of(ranked) == covered
    assert p.rows_of(liquid) == covered
    assert p.rows_of(CLOSE) == covered


def test_deep_graph_plans() -> None:
    """A chain deeper than Python's recursion limit plans; terms build without recursing."""
    term = CLOSE.latest
    for _ in range(3000):
        term = term + 1.0
    assert plan([term], rows=[5], sessions=10).rows_of(CLOSE) == [5]


def test_no_decision_rows_plan_nothing() -> None:
    ret = Returns(3, inputs=[CLOSE])
    assert plan([ret], rows=[], sessions=30).rows_of(CLOSE) == []


def test_decision_row_past_the_axis_is_refused() -> None:
    with pytest.raises(ValueError, match=r"\[0, 30\)"):
        plan([CLOSE.latest], rows=[30], sessions=30)


def test_debug_log_counts_rows(caplog: pytest.LogCaptureFixture) -> None:
    """Monthly decisions compute some rows, not every row of every node (spec 10.1 T1.7a)."""
    ret = Returns(3, inputs=[CLOSE])
    with caplog.at_level("DEBUG", logger="nexusbt.compute"):
        plan([ret], rows=[10, 20], sessions=30)
    assert "rows computed: 8 of 60" in caplog.text  # Returns 2 rows + close 6, of 2 nodes by 30
