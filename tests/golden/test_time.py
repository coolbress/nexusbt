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

import nexusbt as nx
from nexusbt.compute import _crosssection as xs
from nexusbt.compute import _kernels as k
from nexusbt.compute._executor import execute
from nexusbt.compute._kernels_ref import adjusted_window
from nexusbt.contracts import TiebreakPolicy
from nexusbt.data import Calendar, DataConfig, open_snapshot
from nexusbt.data._block import MarketBlock
from nexusbt.factors import SMA, Returns
from nexusbt.pipeline import BoundColumn, graph_hash
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


def _cells(found: tuple[Any, Any]) -> list[bool | None]:
    """A kernel's value and validity mask as the case writes them, None for unknown."""
    return [bool(v) if ok else None for v, ok in zip(*found, strict=True)]


def _tri(cells: list[Any]) -> list[Any]:
    return [None if c == "unknown" else c for c in cells]


def test_T24_filter_unknown() -> None:  # noqa: N802 - spec 10.1's name
    """T-24: every row of the three-valued table through the kernels, from the case's inputs,
    and the `Price` rows through the reference executor (5.4.1, 3.3; #245 Decisions 2026-11-18:
    the executor reads no item or `Trad` column yet)."""
    case = yaml.safe_load((CASES / "T-24.yaml").read_text())
    given = case["input"]
    prev, close = (np.array(given[k], dtype=np.float64) for k in ("close_prev", "close"))
    table = list(dict.fromkeys(s for s in given["sector"] if s is not None))
    codes = np.array([-1 if s is None else table.index(s) for s in given["sector"]], np.int32)
    halted = _tri(given["halted"])
    stop = (np.array([h is True for h in halted]), np.array([h is not None for h in halted]))
    up0, up = k.compare(k.GT, prev, np.full(3, 1e4)), k.compare(k.GT, close, np.full(3, 1e4))
    ok = (~stop[0] & stop[1], stop[1])
    nan = (np.isnan(close), np.ones(3, dtype=bool))
    filled = (ok[0] | ~ok[1], np.ones(3, dtype=bool))
    windows = (np.stack([up0[0], up[0]]), np.stack([up0[1], up[1]]))
    found = {
        "Price.close.latest > 10000": up,
        "~(Price.close.latest > 10000)": (~up[0] & up[1], up[1]),
        "(Price.close.latest > 10000) | Price.close.latest.isnan()": k.kleene_or(*up, *nan),
        "(Price.close.latest > 10000).all(2)": k.kleene_all(*windows),
        "(Price.close.latest > 10000).any(2)": k.kleene_any(*windows),
        "nx.Item.sector.eq(1)": k.codes_in(codes, np.array([table.index(1)], np.int32)),
        "~Trad.halted": ok,
        "(~Trad.halted).fillna(True)": filled,
        "(Price.close.latest > 10000) & ~Trad.halted": k.kleene_and(*up, *ok),
    }
    rows = {row["term"]: row for row in case["expected"]}
    for term, cells in found.items():
        assert _cells(cells) == _tri(rows[term]["values"]), term
        assert [c is True for c in _cells(cells)] == rows[term]["final"], term
    factor = rows["(Price.close.latest > 10000).as_factor()"]["values"]
    assert np.array_equal(np.where(up[1], up[0], np.nan), factor, equal_nan=True)
    _t24_executor(prev, close, rows)


def _t24_executor(prev: Any, close: Any, rows: dict[str, Any]) -> None:
    """The `Price` rows of T-24 through the executor: the session before d is row 0, d row 1."""
    x = BoundColumn.of("Price", "close").latest
    up = x > 10_000
    terms = {"Price.close.latest > 10000": up, "~(Price.close.latest > 10000)": ~up,
             "(Price.close.latest > 10000) | Price.close.latest.isnan()": up | x.isnan(),
             "(Price.close.latest > 10000).all(2)": up.all(2),
             "(Price.close.latest > 10000).any(2)": up.any(2),
             "(Price.close.latest > 10000).as_factor()": up.as_factor()}  # fmt: skip
    dates = np.datetime64("2020-01-01") + np.arange(2).astype("timedelta64[D]")
    ready = (dates + np.timedelta64(16, "h")).astype("datetime64[us]")
    shape, ids = (2, 3), ("KR:T00001", "KR:T00002", "KR:T00003")
    seen = np.broadcast_to(ready[:, None], shape).copy()
    whole = MarketBlock("KR", dates, 0, ids, {"close": np.stack([prev, close])},
                        np.ones(shape, bool), np.zeros(shape, np.int8), seen)  # fmt: skip
    found = execute(list(terms.values()), [1], [(0, 1)], lambda a, b: whole, ready)
    for name, term in terms.items():
        got = found[graph_hash(term)]["value"].to_pylist()
        want = rows[name]["values"]
        if name.endswith("as_factor()"):
            assert np.array_equal(np.array(got), np.array(want), equal_nan=True)
        else:
            assert got == _tri(want), name


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


def _momentum_253(close: Any) -> Any:
    """Form (b) of T-12, `@nx.factor(window=253)`: close[-22]/close[0] - 1 (5.3.7)."""
    return close[-22] / close[0] - 1


def test_T12_momentum_forms_equal() -> None:  # noqa: N802 - spec 10.1's name
    """T-12: `Returns(232).shift(21)`, the 253-row window close[-22]/close[0] - 1 and the direct
    P[t-21]/P[t-252] - 1 are one value at every row of the case, NaN where an end is NaN or
    not in the data (3.4, 3.3, A-32); P[i] = 100 + i by hand, NaN at the halted row 240."""
    case = yaml.safe_load((CASES / "T-12.yaml").read_text())
    n = 263
    p = np.arange(100, 100 + n, dtype=np.float64)
    p[240] = np.nan
    dates = np.datetime64("2020-01-01") + np.arange(n).astype("timedelta64[D]")
    ready = (dates + np.timedelta64(16, "h")).astype("datetime64[us]")
    cells = (np.ones((n, 1), bool), np.zeros((n, 1), np.int8), ready[:, None])
    whole = MarketBlock("KR", dates, 0, ("KR:T00001",), {"close_tr": p[:, None]}, *cells)
    close_tr = BoundColumn.of("Price", "close_tr")
    shifted = Returns(232).shift(21)
    window = nx.factor(window=253, inputs=[close_tr])(_momentum_253)
    rows = [r["row"] for r in case["expected"]]
    found = execute([shifted, window], rows, [(0, n - 1)], lambda a, b: whole, ready,
                    {graph_hash(window): _momentum_253})  # fmt: skip
    a, b = (found[graph_hash(t)]["value"].to_pylist() for t in (shifted, window))
    for row, x, y in zip(case["expected"], a, b, strict=True):
        t = row["row"]
        direct = p[t - 21] / p[t - 252] - 1 if t >= 252 else np.nan
        for value, name in ((x, "returns_232_shift_21"), (y, "window_253"), (direct, "direct")):
            assert value == pytest.approx(row[name], abs=5e-7, nan_ok=True), (t, name)


def _sma3_rows(case: dict[str, Any], root: Path, rows: list[str]) -> dict[str, list[float]]:
    """`SMA(3)` of `close` for A and B at the case's `rows`, through the executor over the
    snapshot's block: each cell's `ts_available` is the snapshot's, its close the case's."""
    snapshot = open_snapshot(DataConfig(path=root))
    calendar = snapshot.calendar("KR")
    days = [str(d) for d in calendar.dates]
    sessions = {r["row"]: r["session"] for r in case["expected"]}
    last = days.index(sessions["s+2"])
    whole = snapshot.market_block("KR", ["close"], calendar.dates[: last + 1])
    close, ids = whole.values["close"].copy(), whole.instrument_ids
    for bar in case["bars"]["rows"]:
        close[days.index(bar["session_date"]), ids.index(bar["instrument_id"])] = bar["close"]
    block = MarketBlock(whole.market, whole.dates, 0, whole.instrument_ids, {"close": close},
                        whole.exists, whole.obs_status, whole.ts_available)  # fmt: skip
    term = SMA(3)
    wanted = [days.index(sessions[r]) for r in rows]
    found = execute([term], wanted, [(0, last)], lambda a, b: block, calendar.ready[: last + 1])
    table = found[graph_hash(term)].to_pylist()
    return {i: [next(v["value"] for v in table if v["row"] == r and v["instrument_id"] == i)
                for r in wanted] for i in ("KR:T00001", "KR:T00002")}  # fmt: skip


def test_G_TIME_LATE_sma_values(tmp_path: Path) -> None:  # noqa: N802 - spec 10.1's name
    """G-TIME-LATE's `SMA(3)`: A 10.5, 12, 15 at s, s+1, s+2, the late bar NaN at s and s+1
    and read at its own position by s+2; rows s and s+1 the same with the snapshot published
    before the late bar arrived (INV-02), never the look-ahead's 13, 14 (decision 2026-11-10)."""
    case = yaml.safe_load((CASES / "G-TIME-LATE.yaml").read_text())
    rows = ["s", "s+1", "s+2"]
    table = {r["row"]: r for r in case["expected"]}
    later = _sma3_rows(case, package(case, tmp_path / "later"), rows)
    assert later["KR:T00001"] == pytest.approx([table[r]["a_sma3"] for r in rows])
    assert later["KR:T00002"] == pytest.approx([table[r]["b_sma3"] for r in rows])
    for r, value in zip(rows[:2], later["KR:T00001"], strict=False):  # not 13, 14
        assert value != pytest.approx(table[r]["lookahead_a_sma3"])
    before = package(case, tmp_path / "earlier", until="2020-01-07T06:30:00Z")
    earlier = _sma3_rows(case, before, rows[:2])
    assert earlier == {i: v[:2] for i, v in later.items()}


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
