"""The time cases against the engine (spec 8.2, 8.4): `ready(t)` and the `LateBar` count.

T1.3's stage of T-20 and G-TIME-LATE (#235; decision 2026-11-10, #356): the case's bars become
a `tiny` package's `ts_available`, and the opened snapshot's calendar gives each row's freeze
time and late bars. The row is T1.4's, A's `SMA(3)` T1.9's, the target T1.11's.
"""

from __future__ import annotations

import datetime as dt
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
import yaml

from nexusbt.compute import _crosssection as xs
from nexusbt.compute import _kernels as k
from nexusbt.compute._kernels_ref import adjusted_window
from nexusbt.contracts import TiebreakPolicy
from nexusbt.data import Calendar, DataConfig, open_snapshot
from nexusbt.testing.synth import make_snapshot, read, write_actions
from nexusbt_tds.hash import write_hashes

pytestmark = pytest.mark.golden

CASES = Path(__file__).parent / "cases"


def instant(text: str) -> dt.datetime:
    return dt.datetime.fromisoformat(text.replace("Z", "+00:00"))


def package(case: dict[str, Any], at: Path, until: str | None = None) -> Path:
    """`tiny` KR whose bars carry the case's availability, `params` and each `ts_available`;
    a bar the case does not name is on time, at its session's `ready`. With `until`, the
    snapshot as published then: without the bars not yet available."""
    root = make_snapshot(at, preset="tiny", markets=("KR",), degrade=["late_bars"])
    declared = case["bars"]
    delay = dt.timedelta(minutes=5) if declared.get("params") else dt.timedelta(0)
    assert declared.get("params", {"ready_delay": "PT5M"}) == {"ready_delay": "PT5M"}
    given = {(r["instrument_id"], dt.date.fromisoformat(r["session_date"])):
             instant(r["ts_available"]) for r in declared["rows"]}  # fmt: skip
    data = json.loads((root / "tds.json").read_text(encoding="utf-8"))
    entry = next(d for d in data["datasets"] if d["kind"] == "bars")
    entry["availability"] = declared["availability"]
    entry["params"] |= declared.get("params", {})
    for f in entry["files"]:
        table = pq.read_table(part := root / f["path"])
        rows = table.to_pylist()
        for row in rows:
            key = (row["instrument_id"], row["session_date"])
            row["ts_available"] = given.get(key, row["ts_end"] + delay)
        rows = [r for r in rows if until is None or r["ts_available"] <= instant(until)]
        pq.write_table(pa.Table.from_pylist(rows, schema=table.schema), part)
        f.update(bytes=part.stat().st_size, rows=len(rows))
    (root / "tds.json").write_text(json.dumps(data), encoding="utf-8")
    write_hashes(root)
    return root


def measured(root: Path) -> tuple[Calendar, dict[str, tuple[dt.datetime, int]]]:
    """The opened snapshot's calendar, and per session its `ready` and `LateBar` count."""
    calendar = open_snapshot(DataConfig(path=root)).calendar("KR")
    bars = read(root, "bars_1d")
    late = calendar.late_bars(bars["session_date"].to_numpy().astype("datetime64[D]"),
                              bars["ts_available"].to_numpy())  # fmt: skip
    ready = [t.replace(tzinfo=dt.UTC) for t in calendar.ready.tolist()]
    return calendar, {str(d): (r, int(n)) for d, r, n in zip(calendar.dates, ready, late,
                                                              strict=True)}  # fmt: skip


def reached(calendar: Calendar, available: str) -> str:
    """The first session whose `ready` reaches `available` (5.1.2: `ts_available <= ready`)."""
    at = np.datetime64(instant(available).replace(tzinfo=None), "us")
    return str(calendar.dates[np.searchsorted(calendar.ready, at)])


def test_T11_ties() -> None:  # noqa: N802 - spec 10.1's name
    """T-11: ranks and `top(2)` of six cells in a shuffled memory order under `tiebreak = "id"`
    (3.7, 5.4.2, INV-04)."""
    case = yaml.safe_load((CASES / "T-11.yaml").read_text())
    assert case["input"]["tiebreak"] == TiebreakPolicy.ID
    ids = [c["instrument_id"] for c in case["input"]["scores"]]
    x = np.array([c["score"] for c in case["input"]["scores"]], dtype=np.float64)
    mask, groups = np.ones(len(x), dtype=bool), np.zeros(len(x), dtype=np.int32)
    tie = xs.tie_order(ids, TiebreakPolicy.ID)
    found: dict[str, Any] = {
        f"rank_{name}": k.rank(x, mask, groups, tie, code, k.ASCENDING)[0]
        for name, code in (("ordinal", k.ORDINAL), ("average", k.AVERAGE), ("min", k.MIN),
                           ("max", k.MAX), ("dense", k.DENSE))
    }  # fmt: skip
    found["rank_ordinal_desc"] = k.rank(x, mask, groups, tie, k.ORDINAL, k.DESCENDING)[0]
    found["in_top2"], tied, _ = k.select(x, mask, groups, tie, 2, k.DESCENDING)
    for row in case["expected"]:
        i = ids.index(row["instrument_id"])
        assert row["n_tied_at_cutoff"] == tied
        for column, values in found.items():
            assert values[i] == row[column] or (math.isnan(values[i]) and math.isnan(row[column]))


def test_G_TIME_LATE_target() -> None:  # noqa: N802 - spec 10.1's name
    """G-TIME-LATE's targets B, B, A: `top(1)` of the table's `SMA(3)` values at s, s+1 and s+2,
    never the look-ahead's A (decision 2026-11-10, #356)."""
    case = yaml.safe_load((CASES / "G-TIME-LATE.yaml").read_text())
    ids = ["KR:T00001", "KR:T00002"]
    tie = xs.tie_order(ids, TiebreakPolicy.HASH)
    mask, groups = np.ones(2, dtype=bool), np.zeros(2, dtype=np.int32)
    rows = [r for r in case["expected"] if r["target"] is not None]
    for row in rows:
        x = np.array([row["a_sma3"], row["b_sma3"]], dtype=np.float64)
        picked, _, _ = k.select(x, mask, groups, tie, 1, k.DESCENDING)
        assert [ids[i] for i in np.flatnonzero(picked)] == [row["target"]]
    assert [r["target"] for r in rows] == ["KR:T00002", "KR:T00002", "KR:T00001"]


def test_T20_late_bar_ready_delay(tmp_path: Path) -> None:  # noqa: N802 - spec 10.1's name
    case = yaml.safe_load((CASES / "T-20.yaml").read_text())
    calendar, rows = measured(package(case, tmp_path / "t20"))
    assert calendar.ready_delay == np.timedelta64(5, "m")
    for row in case["expected"]:  # A's cell is NaN exactly where its bar is late
        assert rows[row["session"]] == (instant(row["ready"]), int(math.isnan(row["a_close"])))
    assert sum(n for _, n in rows.values()) == 1
    # the late bar is read from the next row on: 06:33Z <= ready 06:35Z, a delay of 0 would wait
    assert reached(calendar, "2020-01-07T06:33:00Z") == "2020-01-07"


def test_G_TIME_LATE_ready_and_late_bar(tmp_path: Path) -> None:  # noqa: N802 - spec 10.1's name
    case = yaml.safe_load((CASES / "G-TIME-LATE.yaml").read_text())
    calendar, rows = measured(package(case, tmp_path / "later"))
    assert calendar.ready_delay == np.timedelta64(0, "m")
    for row in case["expected"]:
        assert rows[row["session"]] == (instant(row["ready"]), row["late_bar"])
    assert sum(n for _, n in rows.values()) == 1
    assert reached(calendar, "2020-01-08T06:30:00Z") == "2020-01-08"  # s+2, not s+1
    # INV-02: the snapshot published before the late bar arrived freezes its rows at the
    # same times, `ready` being declared and not read from the bars
    earlier, _ = measured(package(case, tmp_path / "earlier", until="2020-01-07T06:30:00Z"))
    assert len(read(tmp_path / "earlier", "bars_1d")) < len(read(tmp_path / "later", "bars_1d"))
    assert (earlier.ready == calendar.ready).all()


def windows(case: dict[str, Any], at: Path, basis: str, column: str = "close") -> Any:
    """For each expected row, the case's window of KR:T00001 adjusted on `basis` with the
    events `Snapshot.actions` resolves at the row's `ready` (5.3.3), and the pairs it crossed."""
    root = make_snapshot(at, preset="tiny", markets=("KR",))
    write_actions(root, case["corporate_actions"])
    snapshot = open_snapshot(DataConfig(path=root))
    calendar = snapshot.calendar("KR")
    values = np.array([[float(b[column])] for b in case["bars"]])
    days = [str(d) for d in calendar.dates[: len(values)]]
    assert days == [b["session_date"] for b in case["bars"]]
    for row in case["expected"]:
        t = days.index(row["session"])
        yield row, *adjusted_window(values, t, row.get("window", 3), snapshot.actions(
            "KR", calendar.ready[t]), ("KR:T00001",), calendar.ts_open, basis)  # fmt: skip


def test_T07_split_reverse_split_windows(tmp_path: Path) -> None:  # noqa: N802 - spec 10.1's name
    case = yaml.safe_load((CASES / "T-07.yaml").read_text())
    prices = windows(case, tmp_path / "close", "split")
    volumes = windows(case, tmp_path / "volume", "volume", "volume")
    for (row, cells, crossed), (_, volume, _) in zip(prices, volumes, strict=True):
        assert cells[:, 0].tolist() == pytest.approx(row["adjusted_window"], rel=1e-12)
        assert np.mean(cells) == pytest.approx(row["sma"], rel=1e-12)
        assert volume[:, 0].tolist() == pytest.approx(row["volume_window"], rel=1e-12)
        assert not crossed


def test_T15_unavailable_factor_masks_window(tmp_path: Path) -> None:  # noqa: N802 - spec 10.1's name
    case = yaml.safe_load((CASES / "T-15.yaml").read_text())
    pairs: set[tuple[str, str]] = set()  # the run's `AdjustmentUnavailable` pairs so far (4.6)
    for basis in ("split", "total"):  # a spinoff is in both classes: the same rows
        pairs.clear()
        for row, cells, crossed in windows(case, tmp_path / basis, basis):
            pairs |= crossed
            expected = np.array(row["adjusted_window"], dtype=float)
            np.testing.assert_array_equal(cells[:, 0], expected)  # NaN where NaN, no 1.0
            assert np.nanmean(cells) == pytest.approx(row["sma3"], rel=1e-12)
            assert len(pairs) == row["adjustment_unavailable"]
        print(f"{basis}: AdjustmentUnavailable {len(pairs)} {sorted(pairs)}")
        assert pairs == {("KR:T00001", "CA-T15-1")}
