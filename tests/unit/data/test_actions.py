"""`Snapshot.actions(market, cutoff)` (spec 5.3.3a, 2.4): one market's chains as the resolver
gives them at the cutoff, on a synthetic package (2.7)."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import numpy as np
import pytest

from nexusbt.data import DataConfig, open_snapshot
from nexusbt.testing.synth import make_snapshot, write_actions
from nexusbt_tds.hash import write_hashes

SPLIT = {"kind": "split", "ex_date": "2020-01-07", "ts_effective": "2020-01-07T00:00:00Z",
         "ratio_num": 2, "ratio_den": 1, "ratio_new_per_old": 2.0, "price_factor": 0.5,
         "share_factor": 2.0, "affects": "split_and_total", "factor_method": "ratio",
         "pay_date_status": "not_applicable", "status": "effective"}  # fmt: skip


def test_actions_of_one_market_at_cutoff(tmp_path: Path) -> None:
    root = make_snapshot(tmp_path, preset="tiny", markets=("KR", "US"))
    write_actions(root, [
        SPLIT | {"event_id": "KR-1", "instrument_id": "KR:T00001",
                 "ts_announced": "2019-12-20T07:00:00Z"},
        SPLIT | {"event_id": "US-1", "instrument_id": "US:T00001",
                 "ts_announced": "2019-12-20T07:00:00Z"},
    ])  # fmt: skip
    snapshot = open_snapshot(DataConfig(path=root))
    before = snapshot.actions("KR", dt.datetime(2019, 12, 1, tzinfo=dt.UTC))
    after = snapshot.actions("KR", np.datetime64("2020-01-02T00:00:00", "us"))  # UTC, as `ready`
    assert list(after.chains) == ["KR-1"]  # the US chain is another market's
    assert before.chains["KR-1"].event_id is None  # not yet known at the cutoff
    found = after.chains["KR-1"]
    assert (found.event_id, found.affects, found.effects.price_factor) == (
        "KR-1", "split_and_total", 0.5)  # fmt: skip
    assert snapshot.actions("KR", None).chains["KR-1"].event_id == "KR-1"  # +inf: the package
    with pytest.raises(TypeError, match="aware datetime"):
        snapshot.actions("KR", dt.datetime(2020, 1, 2))  # a naive time names no instant


def test_actions_of_a_package_without_corporate_actions(tmp_path: Path) -> None:
    """A package whose profiles do not require `corporate_actions` may leave it out: no chain."""
    root = make_snapshot(tmp_path, preset="tiny", markets=("KR",))
    manifest = json.loads((root / "tds.json").read_text(encoding="utf-8"))
    manifest["profiles"] = ["tds:minimal-daily@1.0"]  # equity-daily-core requires the dataset
    manifest["datasets"] = [d for d in manifest["datasets"] if d["kind"] != "corporate_actions"]
    (root / "tds.json").write_text(json.dumps(manifest), encoding="utf-8")
    write_hashes(root)
    assert open_snapshot(DataConfig(path=root)).actions("KR", None).chains == {}
