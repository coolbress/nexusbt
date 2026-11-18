"""The executor's column windows adjusted as of their row (spec 5.3.3, 5.3.4, 3.2; #548): the
golden cases T-07 and T-15 through `execute`, each column on its 3.2 basis, a pending event and
a late cell in one window, and what does not change (`.latest`, a window over a `Factor`)."""

from __future__ import annotations

import datetime as dt
import functools
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import yaml

import nexusbt as nx
from nexusbt.compute._executor import Actions, execute
from nexusbt.data import DataConfig, open_snapshot
from nexusbt.data._block import MarketBlock
from nexusbt.factors import SMA, AverageDollarVolume, AverageTradedValue
from nexusbt.pipeline import BoundColumn, Term, graph_hash
from nexusbt.testing.synth import make_snapshot, write_actions

CASES = Path(__file__).parents[2] / "golden" / "cases"
ID = "KR:T00001"
Functions = Mapping[str, Callable[..., Any]] | None
#: A 2-for-1 split effective 2020-01-07 (row 3 of the tiny calendar), terms known in advance.
SPLIT = {"event_id": "CA-1", "instrument_id": ID, "kind": "split", "ex_date": "2020-01-07",
         "ts_effective": "2020-01-07T00:00:00Z", "ts_announced": "2019-12-20T07:00:00Z",
         "ratio_num": 2, "ratio_den": 1, "ratio_new_per_old": 2.0, "price_factor": 0.5,
         "share_factor": 2.0, "affects": "split_and_total", "factor_method": "ratio",
         "pay_date_status": "not_applicable", "status": "effective"}  # fmt: skip
#: A cash dividend effective 2020-01-06 (row 2): `C_total` only (5.3.3).
CASH = SPLIT | {"event_id": "CA-2", "kind": "cash_dividend", "ex_date": "2020-01-06",
                "ts_effective": "2020-01-06T00:00:00Z", "ratio_num": None, "ratio_den": None,
                "ratio_new_per_old": None, "cash_per_share": 2.0, "currency": "KRW",
                "gross_or_net": "gross", "price_factor": 0.98, "share_factor": 1.0,
                "affects": "total_only", "factor_method": "cash_prev_close",
                "pay_date_status": "estimated"}  # fmt: skip


def pick(column: str, window: int, k: int) -> tuple[Term, Callable[..., Any]]:
    """A user window function giving cell k of the `window`-row window of `Price.<column>`
    (5.3.7: the adjusted window a user function reads), and that function."""

    def cell(x: Any) -> Any:
        return x[k]

    return nx.factor(window=window, inputs=[BoundColumn.of("Price", column)])(cell), cell


class Axis:
    """The tiny KR calendar with `events`, and a one-column block of KR:T00001's `columns`."""

    def __init__(self, at: Path, events: list[dict[str, Any]], columns: Mapping[str, Any],
                 available: Mapping[int, np.datetime64] | None = None) -> None:  # fmt: skip
        root = make_snapshot(at, preset="tiny", markets=("KR",))
        write_actions(root, events)
        snapshot = open_snapshot(DataConfig(path=root))
        self.calendar = snapshot.calendar("KR")
        self.n = n = len(next(iter(columns.values())))
        ts = self.calendar.ts_close[:n, None].copy()  # each bar on time, at its session's close
        for row, at_ in (available or {}).items():
            ts[row, 0] = at_
        values = {c: np.asarray(v, dtype=float)[:, None] for c, v in columns.items()}
        self.block = MarketBlock("KR", self.calendar.dates[:n], 0, (ID,), values,
                                 np.ones((n, 1), bool), np.zeros((n, 1), np.int8), ts)  # fmt: skip
        self.actions = Actions(functools.partial(snapshot.actions, "KR"), self.calendar.ts_open)
        self.days = [str(d) for d in self.calendar.dates[:n]]

    def run(
        self, terms: Sequence[Term], rows: Sequence[int], functions: Functions = None
    ) -> dict[Any, float]:
        """Each term's value at `rows`, keyed by `(row, graph hash)`."""
        found = execute(terms, rows, [(0, self.n - 1)], lambda a, b: self.block,
                        self.calendar.ready[: self.n], functions, actions=self.actions)  # fmt: skip
        return {(v["row"], key): v["value"] for key, table in found.items()
                for v in table.to_pylist()}  # fmt: skip

    def windows(self, column: str, size: int, rows: Sequence[int]) -> dict[int, list[float]]:
        """The `size`-row window of `column` each row reads, cell by cell."""
        picks = [pick(column, size, k) for k in range(size)]
        got = self.run([t for t, _ in picks], rows, {graph_hash(t): f for t, f in picks})
        return {r: [got[r, graph_hash(t)] for t, _ in picks] for r in rows}


def golden(name: str, at: Path) -> tuple[dict[str, Any], Axis]:
    case = yaml.safe_load((CASES / f"{name}.yaml").read_text())
    columns = {c: [b.get(c, 1.0) for b in case["bars"]] for c in ("close", "volume")}
    columns["close_tr"] = columns["close"]
    return case, Axis(at, case["corporate_actions"], columns)


def test_T07_through_executor(tmp_path: Path) -> None:  # noqa: N802 - spec 10.1's name
    """`SMA(3)` of `close` is the case's `sma` on every row, 52 and not 86.33 at 2020-01-07,
    the 5-row window across both events included; a `volume` window is its `volume_window`."""
    case, axis = golden("T-07", tmp_path)
    for row in case["expected"]:
        t, w = axis.days.index(row["session"]), row["window"]
        assert axis.run([sma := SMA(w)], [t])[t, graph_hash(sma)] == pytest.approx(row["sma"])
        assert axis.windows("close", w, [t])[t] == pytest.approx(row["adjusted_window"])
        assert axis.windows("volume", w, [t])[t] == pytest.approx(row["volume_window"])


def test_T15_through_executor(tmp_path: Path) -> None:  # noqa: N802 - spec 10.1's name
    """Across the spinoff whose `price_factor` is null the cells before it are NaN, on `close`
    and `close_tr` (no hidden 1.0); the invariant `AverageDollarVolume` reads the values as
    traded with NaN where the reference leaves a cell NaN (volume 1 in every row here)."""
    case, axis = golden("T-15", tmp_path)
    rows = [axis.days.index(r["session"]) for r in case["expected"]]
    terms = [SMA(3), SMA(3, inputs=[BoundColumn.of("Price", "close_tr")]), AverageDollarVolume(3)]
    got = axis.run(terms, rows)
    for t, row in zip(rows, case["expected"], strict=True):
        cells = np.array(row["adjusted_window"], dtype=float)
        np.testing.assert_array_equal(axis.windows("close", 3, [t])[t], cells)
        np.testing.assert_array_equal(axis.windows("close_tr", 3, [t])[t], cells)
        values = [got[t, graph_hash(term)] for term in terms]
        assert values == pytest.approx([row["sma3"], row["sma3"], np.nansum(cells) / 3])


def test_each_column_on_its_basis(tmp_path: Path) -> None:
    """3.2: `close` on the split basis, `close_tr` on the total one, `volume` by `Q`,
    `close_unadjusted` as traded, over a window holding a cash dividend and a split."""
    raw = [100.0] * 5
    columns = dict.fromkeys(("close", "close_tr", "volume", "close_unadjusted"), raw)
    axis = Axis(tmp_path, [SPLIT, CASH], columns)
    assert {c: axis.windows(c, 5, [4])[4] for c in columns} == {
        "close": pytest.approx([50, 50, 50, 100, 100]),
        "close_tr": pytest.approx([49, 49, 50, 100, 100]),  # 100 * 0.98 * 0.5 before both
        "volume": pytest.approx([200, 200, 200, 100, 100]),
        "close_unadjusted": pytest.approx(raw),
    }


def test_invariant_kernel_reads_values_as_traded(tmp_path: Path) -> None:
    """3.4: `AverageDollarVolume` and `AverageTradedValue` are invariant, so across an event
    whose price and quantity factors do not cancel (0.8 and 1) they read the values as traded:
    `close * volume` 1000, not 880; `value_traded`, a column 3.2 does not adjust, 1000."""
    spinoff = SPLIT | {"kind": "spinoff", "price_factor": 0.8, "share_factor": 1.0}
    columns = {"close": [100.0] * 5, "volume": [10.0] * 5, "value_traded": [1000.0] * 5}
    terms = [AverageDollarVolume(5), AverageTradedValue(5)]
    got = Axis(tmp_path, [spinoff], columns).run(terms, [4])
    assert [got[4, graph_hash(t)] for t in terms] == [1000.0, 1000.0]


def test_pending_event_and_late_cell_in_one_window(tmp_path: Path) -> None:
    """5.3.4: the split's terms come out after row 3 freezes, so row 3's window leaves it out
    and row 4's applies it; 5.1.2: row 1's bar arrives after row 4 freezes, so it stays NaN."""
    probe = Axis(tmp_path / "probe", [], {"close": [0.0] * 5})
    ready = probe.calendar.ready
    terms = (ready[3] + np.timedelta64(1, "h")).astype(dt.datetime).replace(tzinfo=dt.UTC)
    pending = SPLIT | {"ts_terms_available": terms.isoformat().replace("+00:00", "Z")}
    late = {1: ready[4] + np.timedelta64(1, "h")}
    axis = Axis(tmp_path / "run", [pending], {"close": [100, 100, 100, 50, 50]}, late)
    found = axis.windows("close", 4, [3, 4])
    np.testing.assert_array_equal(found[3], [100, np.nan, 100, 50])  # pending: as traded
    np.testing.assert_array_equal(found[4], [np.nan, 50, 50, 50])  # published: 100 * 0.5


def test_latest_and_factor_input_windows_are_not_adjusted(tmp_path: Path) -> None:
    """`.latest` is the row's own cell; a window over a `Factor` reads the term's values as
    each row gave them (5.1.2), so across T-07's split it is (102 + 104 + 53) / 3."""
    _, axis = golden("T-07", tmp_path)
    latest = BoundColumn.of("Price", "close").latest
    over = SMA(3, inputs=[latest])
    got = axis.run([latest, over], [3])
    assert (got[3, graph_hash(latest)], got[3, graph_hash(over)]) == (53.0, (102 + 104 + 53) / 3)


def test_shares_out_window_waits_for_5_3_5a(tmp_path: Path) -> None:
    axis = Axis(tmp_path, [SPLIT], {"shares_out": [1.0] * 5})
    with pytest.raises(NotImplementedError, match=r"5\.3\.5a"):
        axis.windows("shares_out", 3, [4])
