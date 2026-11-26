"""The as-of adjustment reference (spec 5.3.3, 5.3.3a, 5.3.4): the window of row t as the
events known at a reference time adjust it, read through `Snapshot.actions` (INV-01)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from nexusbt.compute._kernels_ref import adjusted_window
from nexusbt.contracts import ResolvedActions
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


def windows(
    at: Path, events: list[dict[str, Any]], days: list[dt.date], basis: str = "split"
) -> dict[Any, Any]:
    """Row 4's 3-row window of KR:T00001's closes with `events`, at the start of each day."""
    root = make_snapshot(at, preset="tiny", markets=("KR",))
    write_actions(root, events)
    snapshot = open_snapshot(DataConfig(path=root))
    ts_open = snapshot.calendar("KR").ts_open
    raw = np.array([[100.0], [102.0], [104.0], [53.0], [54.0]])  # rows 0..4, the split at 3
    found = {}
    for day in days:
        actions = snapshot.actions("KR", dt.datetime.combine(day, dt.time(), dt.UTC))
        cells, _ = adjusted_window(raw, 4, 3, actions, ("KR:T00001",), ts_open, basis)
        found[day] = cells[:, 0].tolist()
    return found


def test_adjusted_window_refuses_an_unknown_basis_or_rows_outside() -> None:
    raw, none = np.ones((3, 1)), ResolvedActions({})
    with pytest.raises(ValueError, match="basis is one of"):
        adjusted_window(raw, 2, 3, none, ("KR:T00001",), np.array([], "datetime64[us]"), "open")
    with pytest.raises(ValueError, match="are not all rows"):
        adjusted_window(raw, 2, 4, none, ("KR:T00001",), np.array([], "datetime64[us]"), "split")


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


def test_cash_dividend_moves_total_not_split(tmp_path: Path) -> None:
    """5.3.3: `C_split` multiplies `split_and_total` events only, `C_total` every event."""
    cash = V1 | {"kind": "cash_dividend", "ratio_num": None, "ratio_den": None,
                 "ratio_new_per_old": None, "cash_per_share": 2.08, "currency": "KRW",
                 "gross_or_net": "gross", "price_factor": 0.98, "share_factor": 1.0,
                 "affects": "total_only", "factor_method": "cash_prev_close",
                 "pay_date_status": "estimated"}  # fmt: skip
    day = [dt.date(2020, 1, 9)]
    assert windows(tmp_path / "s", [cash], day, "split")[day[0]] == [104.0, 53.0, 54.0]
    assert windows(tmp_path / "t", [cash], day, "total")[day[0]] == [101.92, 53.0, 54.0]


#: A cash dividend on 2020-01-07 (row 3) whose quantity effect, against 5.3.3, is not 1.
CASH = V1 | {"kind": "cash_dividend", "ratio_num": None, "ratio_den": None,
             "ratio_new_per_old": None, "cash_per_share": 2.08, "currency": "KRW",
             "gross_or_net": "gross", "price_factor": 0.98, "share_factor": 2.0,
             "affects": "total_only", "factor_method": "cash_prev_close",
             "pay_date_status": "estimated"}  # fmt: skip
#: A name change on 2020-01-07 (row 3): `affects = none`, quantity effect 2 all the same.
RENAME = V1 | {"kind": "name_change", "ratio_num": None, "ratio_den": None,
               "ratio_new_per_old": None, "price_factor": None, "share_factor": 2.0,
               "affects": "none", "factor_method": None,
               "pay_date_status": "not_applicable"}  # fmt: skip
DAY = dt.date(2020, 1, 9)


@pytest.mark.parametrize("event", [CASH, RENAME], ids=["total_only", "none"])
def test_volume_q_skips_events_other_than_split_and_total(
    tmp_path: Path, event: dict[str, Any]
) -> None:
    """5.3.3 and the 3.2 `volume` row: `Q` multiplies the `q_e` of `split_and_total` events
    only, so share_factor 2 on any other event leaves the volumes as traded, 104 not 208."""
    assert windows(tmp_path, [event], [DAY], "volume")[DAY] == [104.0, 53.0, 54.0]


def test_volume_q_skips_a_total_only_event_whose_share_factor_is_null(tmp_path: Path) -> None:
    """A null `q_e` makes the cells before e NaN (4.6) only on an event `Q` multiplies."""
    unknown = CASH | {"share_factor": None}
    assert windows(tmp_path, [unknown], [DAY], "volume")[DAY] == [104.0, 53.0, 54.0]
