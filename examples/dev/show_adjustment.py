"""Print price windows as each decision's reference time adjusts them (spec 5.3.3, 4.6).

Run it: `uv run python examples/dev/show_adjustment.py`. It writes a synthetic `tiny` package
(spec 4.8) to a temporary folder with three instruments' corporate actions, and shows the
three things of T1.8:

1. KR:T00001's 3-row close windows across a 2:1 split and a 1:10 reverse split, and their
   mean: the numbers of golden case T-07;
2. KR:T00002's windows across an event whose `price_factor` is null: NaN before it while a
   window crosses it, and the run's `AdjustmentUnavailable` count (golden case T-15);
3. KR:T00003's window of 2020-01-08 at three reference times, its split ratio amended after
   the split took effect.
"""

from __future__ import annotations

import datetime as dt
import tempfile
from pathlib import Path

import numpy as np

from nexusbt.compute._kernels_ref import adjusted_window
from nexusbt.data import DataConfig, open_snapshot
from nexusbt.testing.synth import make_snapshot, write_actions

KNOWN = {"ts_announced": "2019-12-20T07:00:00Z", "pay_date_status": "not_applicable",
         "status": "effective", "affects": "split_and_total"}  # fmt: skip
SPLIT = KNOWN | {"kind": "split", "factor_method": "ratio", "ratio_den": 1}
EVENTS = [
    SPLIT | {"event_id": "CA-1", "instrument_id": "KR:T00001", "ex_date": "2020-01-07",
             "ts_effective": "2020-01-07T00:00:00Z", "ratio_num": 2, "ratio_new_per_old": 2.0,
             "price_factor": 0.5, "share_factor": 2.0},
    KNOWN | {"event_id": "CA-2", "instrument_id": "KR:T00001", "kind": "reverse_split",
             "ex_date": "2020-01-10", "ts_effective": "2020-01-10T00:00:00Z", "ratio_num": 1,
             "ratio_den": 10, "ratio_new_per_old": 0.1, "price_factor": 10.0,
             "share_factor": 0.1, "factor_method": "ratio"},
    KNOWN | {"event_id": "CA-3", "instrument_id": "KR:T00002", "kind": "spinoff",
             "ex_date": "2020-01-07", "ts_effective": "2020-01-07T00:00:00Z",
             "ratio_num": 1, "ratio_den": 1, "ratio_new_per_old": 1.0, "share_factor": 1.0,
             "factor_method": "unavailable"},  # price_factor null: "none" (4.6)
    SPLIT | {"event_id": "CA-4", "instrument_id": "KR:T00003", "ex_date": "2020-01-07",
             "ts_effective": "2020-01-07T00:00:00Z", "ratio_num": 2, "ratio_new_per_old": 2.0,
             "price_factor": 0.5, "share_factor": 2.0},
    SPLIT | {"event_id": "CA-5", "revision_of": "CA-4", "instrument_id": "KR:T00003",
             "ex_date": "2020-01-07", "ts_effective": "2020-01-07T00:00:00Z",
             "ts_announced": "2020-01-08T07:00:00Z", "ratio_num": 4,
             "ratio_new_per_old": 4.0, "price_factor": 0.25, "share_factor": 4.0},
]  # fmt: skip
#: The closes as traded, one column per instrument, rows 2020-01-02 .. 2020-01-13.
IDS = ("KR:T00001", "KR:T00002", "KR:T00003")
CLOSES = np.array([[100, 100, 100], [102, 102, 102], [104, 104, 104], [53, 90, 53],
                   [54, 91, 54], [55, 92, 55], [560, 93, 56], [570, 94, 57]], float)  # fmt: skip


def main() -> None:
    with tempfile.TemporaryDirectory() as folder:
        root = make_snapshot(Path(folder) / "snapshot", preset="tiny", markets=("KR",))
        write_actions(root, EVENTS)
        snapshot = open_snapshot(DataConfig(path=root))
        calendar = snapshot.calendar("KR")
        days = [str(d) for d in calendar.dates[: len(CLOSES)]]

        def window(t: int, cutoff: object) -> np.ndarray:
            actions = snapshot.actions("KR", cutoff)
            cells, crossed = adjusted_window(CLOSES, t, 3, actions, IDS, calendar.ts_open,
                                             "split")  # fmt: skip
            pairs.update(crossed)
            return cells

        pairs: set[tuple[str, str]] = set()
        print("1. KR:T00001, split 2:1 on 2020-01-07, reverse split 1:10 on 2020-01-10")
        for t in range(2, 8):
            cells = window(t, calendar.ready[t])[:, 0]
            print(f"{days[t]}  window {cells.tolist()}  mean {cells.mean()}")
        pairs.clear()
        print("2. KR:T00002, price_factor null on 2020-01-07")
        for t in range(2, 7):
            cells = window(t, calendar.ready[t])[:, 1]
            print(f"{days[t]}  window {cells.tolist()}  nanmean {np.nanmean(cells)}"
                  f"  AdjustmentUnavailable {len(pairs)}")  # fmt: skip
        print("3. KR:T00003, split 2:1 on 2020-01-07, amended to 4:1 on 2020-01-08T07:00Z")
        for day in ("2019-12-01", "2019-12-31", "2020-01-09"):
            at = dt.datetime.fromisoformat(day).replace(tzinfo=dt.UTC)
            print(f"window of {days[4]} known at {day}: {window(4, at)[:, 2].tolist()}")


if __name__ == "__main__":
    main()
