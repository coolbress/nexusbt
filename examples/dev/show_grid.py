"""Print a decision grid: the month-end sessions of KR in 2019 and their `decision_ts` (UTC).

Run it: `uv run python examples/dev/show_grid.py`. It writes a synthetic package (spec 4.8)
to a temporary folder, with a calendar that runs into 2020 so that the last session of
December 2019 is settled (spec 3.7, ADR 0043), and shows three things of T1.3:

1. `monthly()` over 2019 decides on 12 month-end sessions, each at its session's `ready`;
2. a start date on a holiday moves to the next session with an E9 notice (5.1.6);
3. the decision dates of `every(5)` stay the same when the start moves by one day (INV-14).
"""

from __future__ import annotations

import datetime as dt
import tempfile
import warnings
from pathlib import Path

from nexusbt.data import DataConfig, decision_grid, every, monthly, open_snapshot
from nexusbt.testing.synth import make_snapshot


def main() -> None:
    with tempfile.TemporaryDirectory() as folder:
        path = make_snapshot(Path(folder) / "snapshot", preset="small", markets=("KR",), n_kr=2,
                             start=dt.date(2018, 12, 3), end=dt.date(2020, 1, 31))  # fmt: skip
        snapshot = open_snapshot(DataConfig(path=path))
        with warnings.catch_warnings(record=True) as notices:
            warnings.simplefilter("always")
            grid = decision_grid(snapshot, monthly(), "2019-01-01", "2019-12-31")  # holidays
        print(f"monthly(), {grid.market}, clock {grid.clock}: {grid.start} to {grid.end}")
        print(f"{'session':<12}decision_ts (UTC)")
        for day, ts in zip(grid.session_dates, grid.decision_ts, strict=True):
            print(f"{day!s:<12}{ts:%Y-%m-%dT%H:%M:%SZ}")
        print(f"{len(grid.session_dates)} month-end sessions")
        print()
        for notice in notices:  # the `what` line of each E9
            print("notice:", str(notice.message).splitlines()[0], "-",
                  str(notice.message).splitlines()[2].split(None, 1)[1])  # fmt: skip
        print()
        january = [decision_grid(snapshot, every(5), start, "2019-01-31").session_dates
                   for start in ("2019-01-02", "2019-01-03")]  # fmt: skip
        for start, days in zip(("2019-01-02", "2019-01-03"), january, strict=True):
            print(f"every(5) from {start}: {', '.join(map(str, days))}")
        same = set(january[1]) == {d for d in january[0] if d >= dt.date(2019, 1, 3)}
        print("the same decision dates on the sessions both runs hold:", same)


if __name__ == "__main__":
    main()
