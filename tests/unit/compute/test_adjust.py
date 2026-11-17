"""The as-of adjustment reference (spec 5.3.3, 5.3.3a, 5.3.4): the window of row t as the
events known at a reference time adjust it, read through `Snapshot.actions` (INV-01)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

import numpy as np

from nexusbt.compute._kernels_ref import adjusted_window
from nexusbt.data import DataConfig, open_snapshot
from nexusbt.testing.synth import make_snapshot, write_actions

V1 = {"event_id": "CA-1", "instrument_id": "KR:T00001", "kind": "split",
      "ex_date": "2020-01-07", "ts_effective": "2020-01-07T00:00:00Z",
      "ts_announced": "2019-12-20T07:00:00Z", "ratio_num": 2, "ratio_den": 1,
      "ratio_new_per_old": 2.0, "price_factor": 0.5, "share_factor": 2.0,
      "affects": "split_and_total", "factor_method": "ratio",
      "pay_date_status": "not_applicable", "status": "effective"}  # fmt: skip
#: The amendment, known after the split took effect: 4 for 1, not 2 for 1.
V2 = V1 | {"event_id": "CA-2", "revision_of": "CA-1", "ts_announced": "2020-01-08T07:00:00Z",
           "ratio_num": 4, "ratio_new_per_old": 4.0, "price_factor": 0.25,
           "share_factor": 4.0}  # fmt: skip


def windows(at: Path, events: list[dict[str, Any]], days: list[dt.date]) -> dict[Any, Any]:
    """Row 4's 3-row window of KR:T00001's closes with `events`, at the start of each day."""
    root = make_snapshot(at, preset="tiny", markets=("KR",))
    write_actions(root, events)
    snapshot = open_snapshot(DataConfig(path=root))
    ts_open = snapshot.calendar("KR").ts_open
    raw = np.array([[100.0], [102.0], [104.0], [53.0], [54.0]])  # rows 0..4, the split at 3
    found = {}
    for day in days:
        actions = snapshot.actions("KR", dt.datetime.combine(day, dt.time(), dt.UTC))
        cells, _ = adjusted_window(raw, 4, 3, actions, ("KR:T00001",), ts_open, "split")
        found[day] = cells[:, 0].tolist()
    return found


def test_revision_changes_window_by_cutoff(tmp_path: Path) -> None:
    days = [dt.date(2019, 12, 1), dt.date(2019, 12, 31), dt.date(2020, 1, 9)]
    assert windows(tmp_path, [V1, V2], days) == {
        dt.date(2019, 12, 1): [104.0, 53.0, 54.0],  # nothing announced: as traded
        dt.date(2019, 12, 31): [52.0, 53.0, 54.0],  # 2 for 1: 104 / 2
        dt.date(2020, 1, 9): [26.0, 53.0, 54.0],  # the amendment, 4 for 1: 104 / 4
    }


def test_late_terms_leave_the_event_out_until_published(tmp_path: Path) -> None:
    """5.3.4: the split is known before it takes effect, its ratio only on 2020-01-08."""
    late = V1 | {"ts_terms_available": "2020-01-08T07:00:00Z"}
    days = [dt.date(2020, 1, 8), dt.date(2020, 1, 9)]
    assert windows(tmp_path, [late], days) == {
        dt.date(2020, 1, 8): [104.0, 53.0, 54.0],  # effective, terms pending: not in the window
        dt.date(2020, 1, 9): [52.0, 53.0, 54.0],
    }
