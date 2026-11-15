"""Dense market blocks from daily bars (spec 5.3.1, 4.6), T1.4 (#236), on synthetic packages."""

from __future__ import annotations

import datetime as dt
import json
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
import yaml

from nexusbt.data import DataConfig, MarketBlock, Snapshot, open_snapshot
from nexusbt.data._block import OBS_STATUS
from nexusbt.testing.synth import make_snapshot, read
from nexusbt_tds.hash import write_hashes

pytestmark = pytest.mark.unit

GOLDEN = Path(__file__).parents[2] / "golden" / "cases"
Rows = list[dict[str, Any]]
A, B = "KR:T00001", "KR:T00002"


@pytest.fixture(scope="module")
def tiny(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return make_snapshot(tmp_path_factory.mktemp("tiny") / "snap", preset="tiny")


def edited(
    source: Path,
    at: Path,
    entry_change: Callable[[dict[str, Any]], None] | None = None,
    **changes: Callable[[Rows], Rows],
) -> Path:
    """A copy of `source` whose rows of each dataset named are `change(rows)`, file by file;
    `entry_change` also edits the tds.json entry of the first one named."""
    shutil.copytree(source, at)
    data = json.loads((at / "tds.json").read_text(encoding="utf-8"))
    for k, (name, change) in enumerate(changes.items()):
        (entry,) = (d for d in data["datasets"] if d["name"] == name)
        if entry_change and k == 0:
            entry_change(entry)
        for f in entry["files"]:
            table = pq.read_table(part := at / f["path"])
            rows = pa.Table.from_pylist(change(table.to_pylist()), schema=table.schema)
            pq.write_table(rows, part)
            f.update(bytes=part.stat().st_size, rows=len(rows))
    (at / "tds.json").write_text(json.dumps(data), encoding="utf-8")
    write_hashes(at)
    return at


def opened(root: Path) -> Snapshot:
    return open_snapshot(DataConfig(path=root))


def whole(snap: Snapshot, market: str, fields: list[str]) -> MarketBlock:
    return snap.market_block(market, fields, snap.calendar(market).dates)


def cell(b: MarketBlock, field: str, day: str, instrument: str) -> float:
    row = int(np.searchsorted(b.dates, np.datetime64(day, "D")))
    return float(b.values[field][row, b.instrument_ids.index(instrument)])


def test_obs_status_halted_is_nan(tiny: Path, tmp_path: Path) -> None:
    marked = {("2020-01-07", B): "halted", ("2020-01-08", B): "missing",
              ("2020-01-09", B): "no_trade"}  # fmt: skip

    def halt(rows: Rows) -> Rows:
        for r in rows:
            status = marked.get((str(r["session_date"]), r["instrument_id"]))
            if status in ("halted", "missing"):
                r.update(obs_status=status, open=None, high=None, low=None, close=None, volume=0.0)
            elif status:
                r.update(obs_status=status, open=None, high=None, low=None, volume=None)
        return rows

    b = whole(opened(edited(tiny, tmp_path / "h", bars_1d=halt)), "KR", ["close", "volume"])
    for day in ("2020-01-07", "2020-01-08"):
        assert np.isnan(cell(b, "close", day, B))
        assert not np.isnan(cell(b, "close", day, A))  # the other instrument traded
    row = int(np.searchsorted(b.dates, np.datetime64("2020-01-07", "D")))
    assert OBS_STATUS[b.obs_status[row, b.instrument_ids.index(B)]] == "halted"
    assert b.exists[row, b.instrument_ids.index(B)]  # halted, still listed
    # no_trade: the reference close stays, volume is 0 (5.2)
    assert cell(b, "close", "2020-01-09", B) > 0
    assert cell(b, "volume", "2020-01-09", B) == 0


def test_existence_mask(tiny: Path, tmp_path: Path) -> None:
    gone = dt.date(2020, 3, 2)

    def delist(rows: Rows) -> Rows:
        for r in rows:
            if r["instrument_id"] == "KR:T00005":
                r.update(last_session=gone, delisted_on=gone)
        return rows

    def cut(rows: Rows) -> Rows:
        return [r for r in rows if r["instrument_id"] != "KR:T00005" or r["session_date"] <= gone]

    root = edited(tiny, tmp_path / "d", instruments=delist, bars_1d=cut)
    b = whole(opened(root), "KR", ["close"])
    late = b.instrument_ids.index("KR:T00006")  # tiny lists it on 2020-02-18
    listed = b.dates >= np.datetime64("2020-02-18", "D")
    assert (b.exists[:, late] == listed).all()
    assert np.isnan(b.values["close"][~listed, late]).all()
    assert not np.isnan(b.values["close"][listed, late]).any()
    out = b.instrument_ids.index("KR:T00005")
    alive = b.dates <= np.datetime64(gone, "D")  # [listed_on, delisted_on], closed (5.3.9)
    assert (b.exists[:, out] == alive).all()
    assert np.isnan(b.values["close"][~alive, out]).all()
    assert (OBS_STATUS[b.obs_status[~alive, out]] == "absent").all()


def test_index_and_synthetic_not_in_block(tiny: Path, tmp_path: Path) -> None:
    extra: dict[str, dict[str, Any]] = {"KR:I00001": {"asset_class": "index", "category": "index"},
                                        "KR:T00099": {"is_synthetic": True}}  # fmt: skip

    def add(rows: Rows) -> Rows:
        first = next(r for r in rows if r["instrument_id"] == A)
        return rows + [{**first, "instrument_id": i, **e} for i, e in extra.items()]

    def bars(rows: Rows) -> Rows:
        if rows[0]["instrument_id"].startswith("US:"):
            return rows
        return rows + [{**r, "instrument_id": i} for r in rows if r["instrument_id"] == A
                       for i in extra]  # fmt: skip

    snap = opened(edited(tiny, tmp_path / "x", instruments=add, bars_1d=bars))
    b = whole(snap, "KR", ["close"])
    assert b.instrument_ids == tuple(f"KR:T0000{k}" for k in range(1, 7))
    assert not set(b.instrument_ids) & {*extra, *(f"US:T0000{k}" for k in range(1, 7))}


def test_dictionary_index_mapping_matches_instrument_ids(tiny: Path, tmp_path: Path) -> None:
    """The file's dictionary order (here reversed) is not the block's column order."""
    root = edited(tiny, tmp_path / "r", bars_1d=lambda rows: rows[::-1])
    part = next(root.glob("bars/freq=1d/market=KR/*/*.parquet"))
    stored = pq.read_table(part, read_dictionary=["instrument_id"])["instrument_id"].chunk(0)
    assert list(stored.dictionary.to_pylist()) != sorted(stored.dictionary.to_pylist())
    b = whole(opened(root), "KR", ["close", "open"])
    assert list(b.instrument_ids) == sorted(b.instrument_ids)
    rows = read(root, "bars_1d").to_pylist()
    for r in (r for r in rows if r["instrument_id"].startswith("KR:")):
        day = str(r["session_date"])
        assert cell(b, "close", day, r["instrument_id"]) == r["close"]
        assert cell(b, "open", day, r["instrument_id"]) == r["open"]
    assert int(b.exists.sum()) == sum(r["instrument_id"].startswith("KR:") for r in rows)


def test_late_bar_stays_in_its_row(tmp_path: Path) -> None:
    """G-TIME-LATE (8.4): the bar of s is in row s with its `ts_available`, never in row s+1;
    which row sees it is the reader's 5.1.2 rule, `ts_available <= ready(t)`."""
    case = yaml.safe_load((GOLDEN / "G-TIME-LATE.yaml").read_text(encoding="utf-8"))
    given = {(r["instrument_id"], r["session_date"]): r for r in case["bars"]["rows"]}

    def stamped(rows: Rows) -> Rows:
        for r in rows:
            row = given.get((r["instrument_id"], str(r["session_date"])))
            r["ts_available"] = r["ts_end"]  # on time, at its session's ready (delta 0)
            if row:
                stamp = dt.datetime.fromisoformat(row["ts_available"].replace("Z", "+00:00"))
                r.update(close=row["close"], ts_available=stamp)
        return rows

    def declared(entry: dict[str, Any]) -> None:
        entry["availability"] = case["bars"]["availability"]

    source = make_snapshot(tmp_path / "src", preset="tiny", markets=("KR",), degrade=["late_bars"])
    snap = opened(edited(source, tmp_path / "late", declared, bars_1d=stamped))
    calendar = snap.calendar("KR")
    b = whole(snap, "KR", ["close"])
    a = b.instrument_ids.index(A)
    for expected in case["expected"]:
        row = int(np.searchsorted(b.dates, np.datetime64(expected["session"], "D")))
        raw = given[(A, expected["session"])]
        assert b.values["close"][row, a] == raw["close"]  # every bar in its own row
        arrives = np.datetime64(expected["a_available"].replace("Z", ""), "us")
        assert b.ts_available[row, a] == arrives
        seen = b.ts_available[row, a] <= calendar.ready[row]  # the row's own reference time
        assert np.isnan(expected["a_close"]) == (not seen)
    s = int(np.searchsorted(b.dates, np.datetime64("2020-01-06", "D")))
    assert b.values["close"][s + 1, a] == 13  # the late 18 did not move into row s+1
