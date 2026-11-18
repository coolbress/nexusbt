"""Window-style user functions (spec 3.3, 5.3.7, 6.5 (5)(6); T1.12, #246): run through the
executor on the windows it adjusts as of their row (#548), E8 for a row outside the window and
a user exception as the user raised it."""

from __future__ import annotations

import functools
import traceback
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pytest

import nexusbt as nx
from nexusbt.compute._executor import Actions, execute
from nexusbt.contracts import SchemaRegistry
from nexusbt.data import DataConfig, open_snapshot
from nexusbt.data._block import MarketBlock
from nexusbt.pipeline import BoundColumn, Term, bind, graph_hash
from nexusbt.testing.synth import make_snapshot, write_actions

ID = "KR:T00001"
CLOSE = BoundColumn.of("Price", "close")
#: A 2-for-1 split effective 2020-01-07 (row 3 of the tiny calendar), terms known in advance.
SPLIT = {"event_id": "CA-1", "instrument_id": ID, "kind": "split", "ex_date": "2020-01-07",
         "ts_effective": "2020-01-07T00:00:00Z", "ts_announced": "2019-12-20T07:00:00Z",
         "ratio_num": 2, "ratio_den": 1, "ratio_new_per_old": 2.0, "price_factor": 0.5,
         "share_factor": 2.0, "affects": "split_and_total", "factor_method": "ratio",
         "pay_date_status": "not_applicable", "status": "effective"}  # fmt: skip


def run(at: Path, terms: Sequence[Term], rows: Sequence[int], close: Sequence[float],
        events: Sequence[dict[str, Any]] = ()) -> dict[tuple[int, str], float]:  # fmt: skip
    """Each term's value at `rows` over the tiny KR calendar, one instrument with `close`, the
    `events` known to the snapshot; no function mapping is given, so each user term runs the
    function it was built from."""
    root = make_snapshot(at, preset="tiny", markets=("KR",))
    write_actions(root, list(events))
    snapshot = open_snapshot(DataConfig(path=root))
    calendar, n = snapshot.calendar("KR"), len(close)
    block = MarketBlock("KR", calendar.dates[:n], 0, (ID,), {"close": np.array(close)[:, None]},
                        np.ones((n, 1), bool), np.zeros((n, 1), np.int8),
                        calendar.ts_close[:n, None].copy())  # fmt: skip
    actions = Actions(functools.partial(snapshot.actions, "KR"), calendar.ts_open)
    found = execute(terms, rows, [(0, n - 1)], lambda a, b: block, calendar.ready[:n],
                    actions=actions)  # fmt: skip
    return {(v["row"], key): v["value"] for key, table in found.items()
            for v in table.to_pylist()}  # fmt: skip


def plain(terms: Sequence[Term], rows: Sequence[int], n: int) -> dict[str, Any]:
    """`execute` over `n` sessions of two instruments with closes 100 + row and 1000 + row,
    every bar on time, no corporate actions."""
    dates = np.datetime64("2020-01-01") + np.arange(n).astype("timedelta64[D]")
    ready = (dates + np.timedelta64(16, "h")).astype("datetime64[us]")
    close = np.arange(n)[:, None] + np.array([[100.0, 1000.0]])
    block = MarketBlock("KR", dates, 0, (ID, "KR:T00002"), {"close": close},
                        np.ones((n, 2), bool), np.zeros((n, 2), np.int8),
                        np.repeat(ready[:, None], 2, axis=1))  # fmt: skip
    return execute(terms, rows, [(0, n - 1)], lambda a, b: block, ready)


def _mom_12_1_custom(close: Any) -> Any:
    return close[-22] / close[-273] - 1


def test_out_of_window_index_E8() -> None:  # noqa: N802 - spec 10.1's name
    """5.3.7, 6.6: `close[-273]` in a 253-row window is `WindowError` (E8) naming the function
    and suggesting `window=273`, at the user's line."""
    mom = nx.factor(window=253, inputs=[CLOSE])(_mom_12_1_custom)
    with pytest.raises(nx.WindowError) as caught:
        plain([mom], [260], 261)
    error = caught.value
    assert error.code == "E8"
    assert error.parts["what"] == "_mom_12_1_custom reads close[-273] but window=253"
    assert "@nx.factor(window=273, ...)" in error.parts["fix"]
    assert str(error.at).startswith("test_user_functions.py:")


def _lookup(close: Any) -> Any:
    return {"a": close[-1]}["b"]  # the user's own mistake


def test_user_exception_keeps_user_frame() -> None:
    """6.6, R-42: an exception inside a user function comes out as the user raised it, not
    wrapped and not chained, and the frames a reader sees go from the caller straight to the
    user's line: the engine's are hidden (`__tracebackhide__`)."""
    lookup = nx.factor(window=2, inputs=[CLOSE])(_lookup)
    registry = SchemaRegistry(columns={}, labels={})
    for caller, where in ((lambda: plain([lookup], [3], 4), "plain"),
                          (lambda: bind(lookup, registry), None)):  # fmt: skip
        with pytest.raises(KeyError) as caught:
            caller()
        error = caught.value
        assert error.args == ("b",)
        assert error.__cause__ is None
        assert not error.__suppress_context__
        tb, shown = error.__traceback__, []
        while tb is not None:
            if not tb.tb_frame.f_locals.get("__tracebackhide__"):
                shown.append(traceback.extract_tb(tb, limit=1)[0])
            tb = tb.tb_next
        assert [frame.name for frame in shown] == [
            "test_user_exception_keeps_user_frame", "<lambda>", *([where] if where else []),
            "_lookup",
        ]  # fmt: skip
        assert shown[-1].line == 'return {"a": close[-1]}["b"]  # the user\'s own mistake'


def _is_up(close: Any) -> Any:
    return close[-1] > close[0]


def test_a_result_of_another_dtype_is_E8() -> None:  # noqa: N802 - E8 is a code
    """5.3.7: `@nx.factor` returns float64; a bool result is E8, not a Factor of 1.0 and 0.0."""
    up = nx.factor(window=2, inputs=[CLOSE])(_is_up)
    with pytest.raises(nx.WindowError, match=r"returned bool \(2,\), not float64 \(2,\)"):
        plain([up], [3], 4)


def _scaled(by: Any) -> Term:
    def scaled(close: Any) -> Any:
        return close[-1] * by[0]

    return nx.factor(window=2, inputs=[CLOSE])(scaled)


def test_one_hash_for_two_functions_is_refused() -> None:
    """Two user terms whose functions differ only in a non-constant value they read have one
    graph hash (6.5 (6) hashes constants only), so one run cannot tell them apart: it refuses
    them rather than give both the values of one. Built twice from the same values, they run."""
    with pytest.raises(ValueError, match="scaled"):
        plain([_scaled(np.array([1.0])), _scaled(np.array([2.0]))], [3], 4)
    by = np.array([2.0])
    got = plain([_scaled(by), _scaled(by)], [3], 4)
    assert got[graph_hash(_scaled(by))]["value"].to_pylist() == [206.0, 2006.0]


def _width(close: Any) -> Any:
    """The number of columns the window holds, in each column."""
    return np.full(close.shape[1], float(close.shape[1]))


def test_mask_is_the_domain_the_function_computes_on() -> None:
    """3.3 `mask`: the function gets the window of the columns its mask is true at, and the
    cells outside the mask are NaN."""
    width = nx.factor(window=2, inputs=[CLOSE], mask=CLOSE.latest > 500)(_width)
    rows = plain([width], [3], 4)[graph_hash(width)].to_pylist()
    assert [r["instrument_id"] for r in rows] == [ID, "KR:T00002"]
    assert np.isnan(rows[0]["value"])
    assert rows[1]["value"] == 1.0


def test_out_of_window_index_E8_when_the_graph_is_built() -> None:  # noqa: N802 - E8 is a code
    """6.5 (5): binding the graph calls each user function once on `(W, 3)` windows of 1.0, so
    `close[-273]` in a 253-row window is E8 before any data is read; a function that keeps to
    its window binds, and so does a graph holding it twice."""
    mom = nx.factor(window=253, inputs=[CLOSE])(_mom_12_1_custom)
    with pytest.raises(nx.WindowError, match=r"@nx.factor\(window=273, \.\.\.\)"):
        bind(mom.rank(), SchemaRegistry(columns={}, labels={}))
    first = nx.factor(window=3, inputs=[CLOSE])(_first)
    bind(nx.Pipeline({"a": first, "b": first.rank()}), SchemaRegistry(columns={}, labels={}))


def _first(close: Any) -> Any:
    return close[0]


def test_window_is_asof_adjusted(tmp_path: Path) -> None:
    """5.3.7 and 3.3: across the 2-for-1 split at row 3 the window row 4 reads holds the earlier
    closes on row 4's basis, 100 → 50, through the executor's column windows (#548); row 2's
    window, before the split, holds them as they are."""
    first = nx.factor(window=3, inputs=[CLOSE])(_first)
    got = run(tmp_path, [first], [2, 4], [100.0, 100.0, 100.0, 50.0, 50.0], [SPLIT])
    assert got[2, graph_hash(first)] == 100.0
    assert got[4, graph_hash(first)] == 50.0
