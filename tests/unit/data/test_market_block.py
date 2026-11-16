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

from nexusbt.contracts import SnapshotError
from nexusbt.data import DataConfig, MarketBlock, Snapshot, open_snapshot
from nexusbt.data._block import OBS_STATUS, partition_values
from nexusbt.testing.synth import make_snapshot, read
from nexusbt_tds.hash import write_hashes

pytestmark = pytest.mark.unit

GOLDEN = Path(__file__).parents[2] / "golden" / "cases"
Rows = list[dict[str, Any]]
A, B = "KR:T00001", "KR:T00002"


@pytest.fixture(scope="module")
def tiny(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return make_snapshot(tmp_path_factory.mktemp("tiny") / "snap", preset="tiny")


@pytest.fixture(scope="module")
def years(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """`small` KR over a year's turn: a bars file per year, 2018 and 2019."""
    at = tmp_path_factory.mktemp("years") / "snap"
    return make_snapshot(at, preset="small", markets=("KR",), n_kr=4,
                         start=dt.date(2018, 12, 3), end=dt.date(2019, 2, 8))  # fmt: skip


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
            if status in ("halted", "missing"):  # the file keeps a close: 3.2 still says NaN
                r.update(obs_status=status, volume=0.0)
            elif status:
                r.update(obs_status=status, open=None, high=None, low=None, volume=None)
        return rows

    b = whole(opened(edited(tiny, tmp_path / "h", bars_1d=halt)), "KR", ["close", "volume"])
    for day, status in (("2020-01-07", "halted"), ("2020-01-08", "missing")):
        assert np.isnan(cell(b, "close", day, B))
        assert not np.isnan(cell(b, "close", day, A))  # the other instrument traded
        row = int(np.searchsorted(b.dates, np.datetime64(day, "D")))
        assert OBS_STATUS[b.obs_status[row, b.instrument_ids.index(B)]] == status
        assert b.exists[row, b.instrument_ids.index(B)]  # still listed
    # no_trade: the reference close stays, volume is 0 (3.2)
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


def test_bare_column_rule_reads_ts_available(tmp_path: Path) -> None:
    """TDS 6.2's bare rule `column` is the `ts_available` column as it is."""
    source = make_snapshot(tmp_path / "src", preset="tiny", markets=("KR",), degrade=["late_bars"])
    bare = edited(source, tmp_path / "bare", lambda e: e.update(availability="column"),
                  bars_1d=lambda rows: rows)  # fmt: skip
    b = whole(opened(bare), "KR", ["close"])
    stored = read(bare, "bars_1d").sort_by(
        [("session_date", "ascending"), ("instrument_id", "ascending")]
    )
    np.testing.assert_array_equal(b.ts_available[b.exists], stored["ts_available"].to_numpy())


def test_without_obs_status_f03(tmp_path: Path) -> None:
    """F-03: without `obs_status`, a bar with a price is traded and a listed session without a
    bar is missing, never `absent`, which means outside the listing period (5.3.1)."""
    sparse = ["sparse_bars"]  # dense rows, no obs_status column
    source = make_snapshot(tmp_path / "src", preset="tiny", markets=("KR",), degrade=sparse)
    hole = ("2020-01-07", B)

    def drop(rows: Rows) -> Rows:
        return [r for r in rows if (str(r["session_date"]), r["instrument_id"]) != hole]

    with pytest.warns(UserWarning, match="F-03"):  # E30: the fallback is said at open (4.5)
        snap = opened(edited(source, tmp_path / "gap", bars_1d=drop))
    b = whole(snap, "KR", ["close"])
    row = int(np.searchsorted(b.dates, np.datetime64("2020-01-07", "D")))
    assert OBS_STATUS[b.obs_status[row, b.instrument_ids.index(B)]] == "missing"
    assert OBS_STATUS[b.obs_status[row, b.instrument_ids.index(A)]] == "traded"
    assert (OBS_STATUS[b.obs_status[b.exists]] != "absent").all()


def test_session_close_rule_is_the_close(tiny: Path, tmp_path: Path) -> None:
    """#460: on daily bars `session_close` is each cell's session close, as `ts_end` is, with
    delta 0; `session_open`, a bar used before it is complete (INV-01), is E14."""
    for rule in ("session_close", "session_open"):

        def declared(entry: dict[str, Any], rule: str = rule) -> None:
            entry["availability"] = rule

        snap = opened(edited(tiny, tmp_path / rule, declared, bars_1d=lambda rows: rows))
        if rule == "session_open":
            with pytest.raises(SnapshotError, match="gives no delay"):
                whole(snap, "KR", ["close"])
            continue
        b, calendar = whole(snap, "KR", ["close"]), snap.calendar("KR")
        close = np.broadcast_to(calendar.ts_close[:, None], b.ts_available.shape)
        np.testing.assert_array_equal(b.ts_available[b.exists], close[b.exists])
        assert calendar.ready_delay == np.timedelta64(0, "us")


def test_sessions_not_of_the_market(tiny: Path) -> None:
    snap = opened(tiny)
    with pytest.raises(ValueError, match="not KR sessions"):  # 2020-01-04 is a Saturday
        snap.market_block("KR", ["close"], np.array(["2020-01-04"], dtype="datetime64[D]"))
    with pytest.raises(ValueError, match="not KR sessions"):
        snap.market_block("KR", ["close"], np.array([], dtype="datetime64[D]"))


def test_tail_overlap_rows(years: Path) -> None:
    snap = opened(years)
    dates = snap.calendar("KR").dates
    own = dates[dates >= np.datetime64("2019-01-01", "D")]
    before = snap.market_block("KR", ["close"], dates[dates < np.datetime64("2019-01-01", "D")])
    b = snap.market_block("KR", ["close"], own, overlap=3)
    assert b.overlap == 3
    assert (b.dates[:3] == before.dates[-3:]).all()
    assert (b.dates[3:] == own).all()
    shared = [i for i in b.instrument_ids if i in before.instrument_ids]
    assert shared
    for instrument in shared:  # the previous chunk's tail, cell for cell
        tail = before.values["close"][-3:, before.instrument_ids.index(instrument)]
        np.testing.assert_array_equal(b.values["close"][:3, b.instrument_ids.index(instrument)],
                                      tail)  # fmt: skip
    # the first chunk's overlap is what the data has: no row before the first session
    first = snap.market_block("KR", ["close"], dates[:5], overlap=3)
    assert first.overlap == 0
    assert len(first.dates) == 5
    with pytest.raises(ValueError, match="negative"):  # it would drop own rows silently
        snap.market_block("KR", ["close"], dates[5:10], overlap=-3)


def test_partition_values_from_path(years: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    declared = [{"name": "freq", "type": "code"}, {"name": "market", "type": "code"},
                {"name": "year", "type": "i16"}]  # fmt: skip
    path = "bars/freq=1d/market=KR/year=2019/part-00000.parquet"
    assert partition_values(path, declared) == {"freq": "1d", "market": "KR", "year": 2019}
    assert partition_values(path, []) == {"freq": "1d", "market": "KR", "year": "2019"}
    opened_files: list[str] = []
    read_table = pq.read_table

    def counted(source: Any, *args: Any, **kwargs: Any) -> pa.Table:
        if "bars" in Path(source).parts:
            opened_files.append(Path(source).parent.name)
        return read_table(source, *args, **kwargs)

    snap = opened(years)
    monkeypatch.setattr(pq, "read_table", counted)
    dates = snap.calendar("KR").dates
    january = dates[(dates >= np.datetime64("2019-01-01", "D"))
                    & (dates < np.datetime64("2019-02-01", "D"))]  # fmt: skip
    snap.market_block("KR", ["close"], january)
    assert opened_files == ["year=2019"]  # the path chose the file, not its rows
    opened_files.clear()
    snap.market_block("KR", ["close"], january, overlap=2)
    assert sorted(opened_files) == ["year=2018", "year=2019"]


def test_files_chosen_by_stats(years: Path, tmp_path: Path) -> None:
    """A file whose `files[].stats` range misses the block's rows is not opened (4.6, P1)."""

    def later(entry: dict[str, Any]) -> None:  # stats that place every file in 2030
        for f in entry["files"]:
            f["stats"] = {"session_date": ["2030-01-01", "2030-12-31"]}

    snap = opened(edited(years, tmp_path / "stats", later, bars_1d=lambda rows: rows))
    b = whole(snap, "KR", ["close"])
    assert b.exists.any()
    assert np.isnan(b.values["close"]).all()
