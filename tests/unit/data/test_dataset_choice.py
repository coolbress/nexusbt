"""Which dataset of a kind the engine reads (spec 4.3, #547): by `kind`, and for `bars` by
`params.freq = 1d`, never by its place in `datasets[]`; two or more left is E18."""

from __future__ import annotations

import copy
import datetime as dt
import json
import shutil
import warnings
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from nexusbt.contracts import CapabilityError, VerifyPolicy
from nexusbt.data import CapabilityRequest, DataConfig, MarketBlock, Snapshot, open_snapshot
from nexusbt.data._l0 import l0_key
from nexusbt.testing.synth import make_snapshot
from nexusbt_tds import read_manifest
from nexusbt_tds.hash import write_hashes

pytestmark = pytest.mark.unit

Manifest = dict[str, Any]


@pytest.fixture(scope="module")
def tiny(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return make_snapshot(tmp_path_factory.mktemp("tiny") / "snap", preset="tiny", markets=("KR",))


def rewritten(source: Path, at: Path, change: Callable[[Path, Manifest], None]) -> Path:
    """A copy of `source` whose tds.json `change` edits (it may add files), hashes rewritten."""
    shutil.copytree(source, at)
    data = json.loads((at / "tds.json").read_text(encoding="utf-8"))
    change(at, data)
    (at / "tds.json").write_text(json.dumps(data), encoding="utf-8")
    write_hashes(at)
    return at


def entry(data: Manifest, name: str) -> Manifest:
    found: Manifest
    (found,) = (d for d in data["datasets"] if d["name"] == name)
    return found


def minute_bars(first: bool) -> Callable[[Path, Manifest], None]:
    """Issue #547's step 2: `bars_1m` (`params.freq = 1m`) holding one bar of the first
    session's first instrument, close 9990 and volume 10, listed before or after `bars_1d`."""

    def change(root: Path, data: Manifest) -> None:
        daily = entry(data, "bars_1d")
        table = pq.read_table(root / daily["files"][0]["path"])
        row = table.slice(0, 1).to_pylist()[0]
        start = row["ts_start"]
        row |= {"ts_end": start + dt.timedelta(minutes=1), "open": 9990.0, "high": 9990.0,
                "low": 9990.0, "close": 9990.0, "volume": 10.0, "price_type": "last"}  # fmt: skip
        day = row["session_date"].isoformat()
        rel = f"bars/freq=1m/market=KR/date={day}/part-00000.parquet"
        schema = table.schema.append(pa.field("price_type", pa.string()))
        schema = schema.with_metadata({"tds.dataset": "bars_1m", "tds.schema_version": "1.0"})
        (root / rel).parent.mkdir(parents=True)
        pq.write_table(pa.Table.from_pylist([row], schema=schema), root / rel)
        minute = {
            "name": "bars_1m", "kind": "bars", "path": "bars/freq=1m", "schema_version": "1.0",
            "availability": {"rule": "ts_end"}, "columns": daily["columns"],
            "params": {"freq": "1m", "price_basis": "raw", "density": "sparse",
                       "bar_time": "interval"},
            "partitioning": [{"name": "freq", "type": "code"}, {"name": "market", "type": "code"},
                             {"name": "date", "type": "date"}],
            "files": [{"path": rel, "rows": 1, "bytes": (root / rel).stat().st_size}],
            "coverage": {"instruments": 1, "ts_min": day, "ts_max": day, "by_market": {"KR": {
                "instruments": 1, "first": day, "last": day, "rows": 1,
                "processed_through_session": data["markets"]["KR"]["complete_through_session"],
            }}},
        }  # fmt: skip
        at = data["datasets"].index(daily)
        data["datasets"].insert(at if first else at + 1, minute)

    return change


def opened(root: Path) -> tuple[Snapshot, list[str]]:
    """The package opened at `full`, with the warnings opening it raised."""
    with warnings.catch_warnings(record=True) as raised:
        warnings.simplefilter("always")
        snap = open_snapshot(DataConfig(path=root, verify=VerifyPolicy.FULL))
    return snap, [str(w.message) for w in raised]


def first_session(snap: Snapshot) -> MarketBlock:
    day = snap.calendar("KR").dates[:1]
    return snap.market_block("KR", ["close", "volume"], day)


def test_daily_block_does_not_depend_on_dataset_order(tiny: Path, tmp_path: Path) -> None:
    """#547: with `bars_1m` listed before or after `bars_1d`, the first session's block is the
    block of the package without `bars_1m`, and no warning is raised for its sake."""
    base, base_warned = opened(tiny)
    want = first_session(base)
    assert want.values["close"][0, 0] == 10000.0  # the issue's table: the daily bar
    for first in (True, False):
        root = rewritten(tiny, tmp_path / f"first={first}", minute_bars(first))
        snap, warned = opened(root)
        got = first_session(snap)
        for field in ("close", "volume"):
            np.testing.assert_array_equal(got.values[field], want.values[field])
        np.testing.assert_array_equal(got.obs_status, want.obs_status)
        assert warned == base_warned, first


def test_l0_key_does_not_depend_on_dataset_order(tiny: Path, tmp_path: Path) -> None:
    """#547: the L0 key hashes the daily bars (5.3.9), whichever place `bars_1m` takes."""
    want = l0_key(read_manifest(tiny), "KR", "close", 2020, "strict")
    for first in (True, False):
        root = rewritten(tiny, tmp_path / f"first={first}", minute_bars(first))
        assert l0_key(read_manifest(root), "KR", "close", 2020, "strict") == want, first


def without_daily_bars(root: Path, data: Manifest) -> None:
    minute_bars(first=True)(root, data)
    data["datasets"].remove(entry(data, "bars_1d"))
    data["profiles"] = []  # every profile but the intraday ones needs bars(1d) (TDS 7)


def test_no_daily_bars_is_e18_where_bars_are_read(tiny: Path, tmp_path: Path) -> None:
    """#547: minute bars alone are no daily bars: the package opens with what needs them off,
    and reading the daily block, or requesting `price`, is E18 (spec 4.3)."""
    root = rewritten(tiny, tmp_path / "minute", without_daily_bars)
    snap, _ = opened(root)
    with pytest.raises(CapabilityError, match=r"no bars \(freq=1d\) dataset") as raised:
        first_session(snap)
    assert raised.value.code == "E18"
    with pytest.raises(CapabilityError, match="price needs bars"):
        open_snapshot(DataConfig(path=root), required=CapabilityRequest(frozenset({"price"})))


def doubled(name: str) -> Callable[[Path, Manifest], None]:
    """A second copy of the dataset `name`, as `<name>_b` under `<path>_b`, listed after it."""

    def change(root: Path, data: Manifest) -> None:
        source = entry(data, name)
        again = copy.deepcopy(source) | {"name": f"{name}_b", "path": f"{source['path']}_b"}
        for f in again["files"]:
            rel = f["path"].replace(source["path"], again["path"], 1)
            table = pq.read_table(root / f["path"])
            meta = {**(table.schema.metadata or {}), b"tds.dataset": again["name"].encode()}
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            pq.write_table(table.replace_schema_metadata(meta), root / rel)
            f |= {"path": rel, "bytes": (root / rel).stat().st_size}
            f.pop("sha256", None)
        data["datasets"].insert(data["datasets"].index(source) + 1, again)

    return change


#: Each kind the engine reads, a read of it, and a feature that needs it (4.3).
READS: dict[str, tuple[Callable[[Snapshot], object], str]] = {
    "bars_1d": (first_session, "price"),
    "instruments": (first_session, "price"),
    "calendar_sessions": (lambda s: s.calendar("KR"), "adjusted"),
    "corporate_actions": (lambda s: s.actions("KR", None), "adjusted"),
}


@pytest.mark.parametrize("name", READS)
def test_two_of_a_kind_is_e18_naming_both(tiny: Path, tmp_path: Path, name: str) -> None:
    """#547: two datasets the engine cannot tell apart open with what needs them off, and
    reading them, or requesting a feature that needs them, is E18 naming both with the fix."""
    root = rewritten(tiny, tmp_path / name, doubled(name))
    snap, warned = opened(root)
    assert not [w for w in warned if "F-02" in w]  # off, not taken by a fallback
    read, feature = READS[name]
    both = rf"{name}, {name}_b"
    with pytest.raises(CapabilityError, match=both) as raised:
        read(snap)
    assert f"keep only one of {name}, {name}_b in the package" in str(raised.value)
    with pytest.raises(CapabilityError, match=both):
        open_snapshot(DataConfig(path=root), required=CapabilityRequest(frozenset({feature})))
