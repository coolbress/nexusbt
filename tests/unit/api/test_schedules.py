"""Spec 3.7: the public schedules `nx.monthly` and `nx.daily` on a calendar (T3.2a, #909)."""

from __future__ import annotations

import datetime as dt

import numpy as np
import pytest

import nexusbt as nx
from nexusbt.data import Calendar

pytestmark = pytest.mark.unit


def calendar(first: str, last: str, *holidays: str) -> Calendar:
    """The weekdays of KR from `first` to `last` that are not in `holidays`."""
    days = np.arange(first, np.datetime64(last) + np.timedelta64(1, "D"), dtype="datetime64[D]")
    days = days[(days.astype(np.int64) + 3) % 7 < 5]  # day 0 is a Thursday
    days = days[~np.isin(days, np.array(holidays, dtype="datetime64[D]"))]
    times = days.astype("datetime64[us]")
    return Calendar("KR", "XKRX", days, times, times, np.arange(len(days)), np.timedelta64(0, "m"))


def picks(schedule: nx.Schedule, on: Calendar) -> list[str]:
    return [str(day) for day in on.dates[schedule.rows(on)]]


def test_monthly_picks_sessions_only() -> None:
    """3.7: `monthly(day)` counts the sessions of the month, not its days. July 2021 ends on
    a Saturday, so `monthly(day=-1)` is Friday 2021-07-30; with 2021-07-01 a holiday,
    `monthly(day=1)` is the next session. `daily()` is every session and nothing else."""
    summer = calendar("2021-06-01", "2021-08-31", "2021-07-01")
    assert picks(nx.monthly(day=-1), summer) == ["2021-06-30", "2021-07-30"]
    assert dt.date(2021, 7, 30).weekday() == 4  # a Friday
    assert picks(nx.monthly(), summer) == picks(nx.monthly(day=-1), summer)
    assert picks(nx.monthly(day=1), summer) == ["2021-07-02", "2021-08-02"]
    every = picks(nx.daily(), summer)
    assert every == [str(day) for day in summer.dates]
    assert "2021-07-01" not in every
    assert "2021-07-31" not in every


def test_monthly_needs_a_session_after_the_period() -> None:
    """3.7 (#461, #875): a month-end pick needs a calendar session after the month, else that
    month has no decision: a calendar that ends on 2021-07-30 cannot tell that it is July's
    last session. One more session settles it, and the earlier decisions stay (INV-14)."""
    cut = calendar("2021-06-01", "2021-07-30")
    assert picks(nx.monthly(), cut) == ["2021-06-30"]
    assert picks(nx.monthly(), calendar("2021-06-01", "2021-08-02")) == ["2021-06-30", "2021-07-30"]
    assert picks(nx.monthly(), calendar("2021-06-15", "2021-08-02")) == ["2021-06-30", "2021-07-30"]
    assert picks(nx.daily(), cut)[-1] == "2021-07-30"  # `daily` counts inside no period
