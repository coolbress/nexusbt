"""The developer examples under `examples/dev/` run and print what their ticket says (10.1)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.examples

ROOT = Path(__file__).resolve().parents[2]
#: The last KRX session of each month of 2019 (the exchange is closed on 12-31).
MONTH_ENDS_2019 = (
    "2019-01-31", "2019-02-28", "2019-03-29", "2019-04-30", "2019-05-31", "2019-06-28",
    "2019-07-31", "2019-08-30", "2019-09-30", "2019-10-31", "2019-11-29", "2019-12-30",
)  # fmt: skip


def test_show_grid_prints_the_month_ends_of_2019() -> None:
    """T1.3's "Done means" (#235): 12 month-end sessions with `decision_ts` in UTC, an E9
    notice for a start date on a holiday, and `every(5)` unmoved by a start one day later."""
    command = [sys.executable, str(ROOT / "examples" / "dev" / "show_grid.py")]
    done = subprocess.run(command, capture_output=True, text=True, check=True)  # noqa: S603
    lines = done.stdout.splitlines()
    assert lines[2:14] == [f"{day}  {day}T06:30:00Z" for day in MONTH_ENDS_2019]
    assert lines[14] == "12 month-end sessions"
    e9 = "notice: SessionNotice [E9] start - start 2019-01-01 is not a KR session; using 2019-01-02"
    assert e9 in lines
    every = [line.split(": ")[1] for line in lines if line.startswith("every(5) from")]
    assert every == ["2019-01-03, 2019-01-10, 2019-01-17, 2019-01-24, 2019-01-31"] * 2
    assert lines[-1].endswith("True")


def test_show_adjustment_prints_the_golden_windows() -> None:
    """T1.8's "Done means" (#241): the T-07 windows across a split and a reverse split, NaN
    before a null `price_factor` with the `AdjustmentUnavailable` count of T-15, and an
    amended split ratio giving another window at a later reference time."""
    command = [sys.executable, str(ROOT / "examples" / "dev" / "show_adjustment.py")]
    done = subprocess.run(command, capture_output=True, text=True, check=True)  # noqa: S603
    lines = done.stdout.splitlines()
    cases = ROOT / "tests" / "golden" / "cases"
    t07 = yaml.safe_load((cases / "T-07.yaml").read_text())["expected"]
    for row in (r for r in t07 if r["window"] == 3):
        cells = [float(x) for x in row["adjusted_window"]]
        assert f"{row['session']}  window {cells}  mean {row['sma']}" in lines
    for row in yaml.safe_load((cases / "T-15.yaml").read_text())["expected"]:
        cells = [float(x) for x in row["adjusted_window"]]
        assert (f"{row['session']}  window {cells}  nanmean {row['sma3']}"
                f"  AdjustmentUnavailable {row['adjustment_unavailable']}") in lines  # fmt: skip
    assert lines[-3:] == [
        "window of 2020-01-08 known at 2019-12-01: [104.0, 53.0, 54.0]",  # as traded
        "window of 2020-01-08 known at 2019-12-31: [52.0, 53.0, 54.0]",  # 2 for 1
        "window of 2020-01-08 known at 2020-01-09: [26.0, 53.0, 54.0]",  # amended: 4 for 1
    ]
