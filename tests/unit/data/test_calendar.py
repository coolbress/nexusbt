"""A market's calendar (spec 5.1.1) and the freeze time of its rows (5.1.2), T1.3 (#235)."""

from __future__ import annotations

import datetime as dt
import json
import shutil
import warnings
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import yaml

from nexusbt.contracts import CapabilityError, ConfigError, SnapshotError
from nexusbt.data import (
    Calendar,
    DataConfig,
    Schedule,
    Snapshot,
    annually,
    daily,
    decision_grid,
    default_clock,
    every,
    monthly,
    open_snapshot,
    quarterly,
    weekly,
)
from nexusbt.testing.synth import make_snapshot

pytestmark = pytest.mark.unit

GOLDEN = Path(__file__).parents[2] / "golden" / "cases"

MINUTE = np.timedelta64(1, "m")


def bars_declared(source: Path, at: Path, **fields: Any) -> Path:
    """A copy of `source` whose bars entry in tds.json takes `fields` (availability, params)."""
    shutil.copytree(source, at)
    data = json.loads((at / "tds.json").read_text(encoding="utf-8"))
    bars = next(d for d in data["datasets"] if d["kind"] == "bars")
    bars.update(fields | {"params": bars["params"] | fields.get("params", {})})
    (at / "tds.json").write_text(json.dumps(data), encoding="utf-8")
    return at


def delay(path: Path) -> np.timedelta64:
    calendar = open_snapshot(DataConfig(path=path)).calendar("KR")
    assert (calendar.ready == calendar.ts_close + calendar.ready_delay).all()
    return calendar.ready_delay


def test_ready_delay_from_availability_rule(tmp_path: Path) -> None:
    """5.1.2: delta is 0 under `ts_end` and `session_close` (#460), the duration under
    `ts_end+<duration>`, and `params.ready_delay` (0 when absent) under the column rule."""
    tiny = make_snapshot(tmp_path / "tiny", preset="tiny")
    kr = open_snapshot(DataConfig(path=tiny)).calendar("KR")
    assert (kr.calendar_id, len(kr.dates), kr.ready_delay) == ("XKRX", 62, 0 * MINUTE)
    assert (kr.dates[0], kr.ts_open[0], kr.ready[0]) == (
        np.datetime64("2020-01-02"), np.datetime64("2020-01-02T00:00"),
        np.datetime64("2020-01-02T06:30"),
    )  # fmt: skip
    assert kr.session_ord.tolist() == list(range(62))  # the package's own numbers (3.7)
    us = open_snapshot(DataConfig(path=tiny)).calendar("US")
    assert (us.calendar_id, us.ready[0]) == ("XNYS", np.datetime64("2020-01-02T21:00"))
    assert delay(bars_declared(tiny, tmp_path / "a", availability="ts_end+PT5M")) == 5 * MINUTE
    ruled = bars_declared(tiny, tmp_path / "b", availability={"rule": "ts_end+P1DT1H0.5S"})
    assert delay(ruled) == np.timedelta64(25 * 3600 * 10**6 + 500_000, "us")
    late = make_snapshot(tmp_path / "late", preset="tiny", degrade=["late_bars"])
    assert delay(late) == 0 * MINUTE  # the column rule with no `ready_delay`
    assert delay(bars_declared(late, tmp_path / "c", params={"ready_delay": "PT5M"})) == 5 * MINUTE
    named = {"availability": {"rule": "column"}, "params": {"ready_delay": "PT5M"}}
    assert delay(bars_declared(late, tmp_path / "e", **named)) == 5 * MINUTE  # TDS 6.2's name
    # under a rule the rule decides, not a stray `ready_delay`
    assert delay(bars_declared(tiny, tmp_path / "d", params={"ready_delay": "PT5M"})) == 0 * MINUTE
    with pytest.raises(CapabilityError, match="market JP is not in the snapshot"):
        open_snapshot(DataConfig(path=tiny)).calendar("JP")
    assert delay(bars_declared(tiny, tmp_path / "f", availability="session_close")) == 0 * MINUTE
    wrongs: list[dict[str, Any]] = [
        {"availability": "session_open"},  # the bar before it is complete (INV-01, #460)
        {"availability": "ts_end+P1M"},  # a month has no fixed length
        {"availability": {"column": "ts_available"}, "params": {"ready_delay": "5 minutes"}},
    ]
    for n, wrong in enumerate(wrongs):
        with pytest.raises(SnapshotError, match="gives no delay"):
            delay(bars_declared(tiny, tmp_path / f"wrong{n}", **wrong))


def test_late_bars_counts_only_bars_in_a_row() -> None:
    """5.1.2 `LateBar`: a bar later than its row's `ready`; one on no session is in no row."""
    days = np.array(["2020-01-03", "2020-01-06"], "datetime64[D]")
    close = np.array(["2020-01-03T06:30", "2020-01-06T06:30"], "datetime64[us]")
    kr = Calendar("KR", "XKRX", days, days.astype("datetime64[us]"), close, np.arange(2), MINUTE)
    dates = np.array(["2020-01-03", "2020-01-03", "2020-01-04", "2020-01-06", "2020-04-01"],
                     "datetime64[D]")  # fmt: skip
    available = np.array(["2020-01-03T06:31", "2020-01-03T06:32", "2020-01-09", "2020-01-06T06:00",
                          "2020-04-02"], "datetime64[us]")  # fmt: skip
    assert kr.late_bars(dates, available).tolist() == [1, 0]  # at `ready` is on time


@pytest.fixture(scope="module")
def tiny(tmp_path_factory: pytest.TempPathFactory) -> Snapshot:
    """`tiny` (4.8): KR and US, 2020-01-02 to 2020-03-31; KR holidays 2020-01-24 and 01-27."""
    path = make_snapshot(tmp_path_factory.mktemp("grid") / "tiny", preset="tiny")
    return open_snapshot(DataConfig(path=path))


def decisions(snapshot: Snapshot, schedule: Schedule, start: str = "2020-01-02",
              end: str = "2020-03-31", **given: Any) -> list[str]:  # fmt: skip
    grid = decision_grid(snapshot, schedule, start, end, **given)
    return [str(d) for d in grid.session_dates]


def test_monthly_last_session(tiny: Snapshot) -> None:
    """3.7 `monthly(day)`: the day-th session of the month from 1, from the end when negative,
    the last (or first) when the month has fewer; each decision at its session's `ready`.
    `tiny` ends on 2020-03-31 and starts on 01-02: its calendar does not settle the end of
    March or the start of January (ADR 0043), so a pick that needs them is not there."""
    grid = decision_grid(tiny, monthly(), "2020-01-02", "2020-03-31")
    assert [str(d) for d in grid.session_dates] == ["2020-01-31", "2020-02-28"]
    assert grid.decision_ts[0] == dt.datetime(2020, 1, 31, 6, 30, tzinfo=dt.UTC)  # KR close
    assert (grid.market, grid.calendar_id, grid.clock) == ("KR", "XKRX", "KR_close")
    assert decisions(tiny, monthly(1)) == ["2020-02-03", "2020-03-02"]
    assert decisions(tiny, monthly(-2)) == ["2020-01-30", "2020-02-27"]
    assert decisions(tiny, monthly(16)) == ["2020-02-24", "2020-03-23"]
    assert decisions(tiny, monthly(99)) == ["2020-02-28"]  # the last of a month with fewer
    assert decisions(tiny, monthly(-99)) == ["2020-02-03"]
    us = decisions(tiny, monthly(), clock="US_close")  # the calendar of the clock's market
    assert us == ["2020-01-31", "2020-02-28"]
    us_january = decision_grid(tiny, monthly(), "2020-01-02", "2020-01-31", clock="US_close")
    assert us_january.decision_ts == (dt.datetime(2020, 1, 31, 21, 0, tzinfo=dt.UTC),)
    with pytest.raises(ConfigError, match="day = 0"):
        monthly(0)


def test_start_rounds_forward_end_backward(tiny: Snapshot) -> None:
    """T-10 (5.1.6): `start` moves to the next session and `end` to the previous one, each
    with an E9 notice, and `monthly(-1)` decides on the same sessions whatever the start."""
    case = yaml.safe_load((GOLDEN / "T-10.yaml").read_text())
    kr = tiny.calendar("KR")
    for row in case["expected"]:
        with warnings.catch_warnings(record=True) as said:
            warnings.simplefilter("always")
            grid = decision_grid(tiny, monthly(-1), row["start"], row["end"], clock="KR_close")
            first, last = kr.align(dt.date.fromisoformat(row["start"]), row["end"])
        del said[len(said) // 2 :]  # `align` again, with a date: the same notices twice
        moved = [f"{name} {row[name]} is not a KR session; using {row[f'aligned_{name}']}"
                 for name in ("start", "end") if row[name] != row[f"aligned_{name}"]]  # fmt: skip
        assert [str(w.message).splitlines()[2].removeprefix("  what   ") for w in said] == moved
        assert all(str(w.message).startswith("SessionNotice [E9]") for w in said)
        assert (str(grid.start), str(grid.end)) == (row["aligned_start"], row["aligned_end"])
        assert (str(kr.dates[first]), str(kr.dates[last])) == (str(grid.start), str(grid.end))
        assert last - first + 1 == row["n_sessions"]
        assert [str(d) for d in grid.session_dates] == row["decisions"]
    with pytest.raises(ConfigError, match="no KR session from 2020-01-25 to 2020-01-27"):
        decision_grid(tiny, monthly(), "2020-01-25", "2020-01-27")
    assert kr.align(dt.datetime(2020, 1, 13, 9, 0), "2020-01-23") == (7, 15)  # a datetime's date
    wrongs: list[Any] = ["2020-1-5", "2020/01/05", "2020-01", "", "NaT", "2020-01-05T10:00", None]
    for wrong in wrongs:
        with pytest.raises(ConfigError, match="is not a date"):
            decision_grid(tiny, monthly(), "2020-01-02", wrong)


def test_weekly_quarterly(tiny: Snapshot, tmp_path: Path) -> None:
    """3.7: `weekly` counts inside the ISO week, `quarterly` is `monthly` of the quarter-end
    months and `annually` of one month; `daily` is every session."""
    january = {"start": "2020-01-02", "end": "2020-01-31"}  # no session on 01-24 and 01-27
    week_ends = ["2020-01-03", "2020-01-10", "2020-01-17", "2020-01-23", "2020-01-31"]
    assert decisions(tiny, weekly(), **january) == week_ends
    # the calendar's first week, of 01-02 and 01-03, has no session before it (ADR 0043)
    assert decisions(tiny, weekly(1), **january) == [
        "2020-01-06", "2020-01-13", "2020-01-20", "2020-01-28"]  # fmt: skip
    assert decisions(tiny, weekly(2), **january) == [
        "2020-01-07", "2020-01-14", "2020-01-21", "2020-01-29"]  # fmt: skip
    assert decisions(tiny, quarterly()) == []  # no session after March
    assert len(decisions(tiny, daily(), **january)) == 20
    path = make_snapshot(tmp_path / "small", preset="small", n_kr=2, n_us=2,
                         end=dt.date(2020, 1, 31))  # fmt: skip
    small = open_snapshot(DataConfig(path=path))  # 2015 into 2020; KRX closes on 12-31
    year = {"start": "2019-01-01", "end": "2019-12-31", "clock": "KR_close"}
    with pytest.warns(UserWarning, match=r"SessionNotice \[E9\]"):
        quarter_ends = decisions(small, quarterly(), **year)
    assert quarter_ends == ["2019-03-29", "2019-06-28", "2019-09-30", "2019-12-30"]
    two = {"start": "2018-01-02", "end": "2019-12-30", "clock": "KR_close"}
    assert decisions(small, annually(), **two) == ["2018-12-28", "2019-12-30"]
    assert decisions(small, annually(6, 1), **two) == ["2018-06-01", "2019-06-03"]
    for build, argument in ((weekly, 0), (quarterly, 0), (annually, 13), (every, 0)):
        with pytest.raises(ConfigError, match="names no session"):
            build(argument)


def test_T23_every_anchor_independent_of_start(tiny: Snapshot) -> None:  # noqa: N802 - spec 10.1's name
    """T-23 (3.7, INV-14): `every(n)` decides on `session_ord`, so a later start keeps the
    decision dates; a count from the run's first session (`from_run_start`) must not appear."""
    case = yaml.safe_load((GOLDEN / "T-23.yaml").read_text())
    terms = {"every(5)": every(5), "every(5, offset=2)": every(5, offset=2)}
    for row in case["expected"]:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # the E9 of the holiday start is T-10's
            grid = decision_grid(tiny, terms[row["term"]], row["start"], row["end"])
        assert str(grid.start) == row["aligned_start"]
        assert [str(d) for d in grid.session_dates] == row["decisions"]
    moved = decisions(tiny, every(5), "2020-01-03", "2020-02-28")  # the start one day later
    assert moved == decisions(tiny, every(5), "2020-01-02", "2020-02-28")[1:]
    days = np.arange("2020-01-06", "2020-01-16", dtype="datetime64[D]")  # ten rows, ord 1003..
    times = days.astype("datetime64[us]")
    numbered = Calendar("KR", "XKRX", days, times, times, np.arange(1003, 1013), 0 * MINUTE)
    assert every(5).rows(numbered).tolist() == [2, 7]  # ord 1005 and 1010, not rows 0 and 5
    assert every(5, offset=-2).rows(numbered).tolist() == [0, 5]  # ord 1003 and 1008


def test_default_clock_codepoint_first_market(tmp_path: Path) -> None:
    """5.1.3 [R3-18]: the default clock is the close of the first market by UTF-8 bytes (code
    point order), whatever the order of the `markets` object in tds.json."""
    assert default_clock(["US", "KR"]) == "KR_close"
    assert default_clock(["b", "a", "É", "B"]) == "B_close"  # no locale, no case folding
    path = make_snapshot(tmp_path / "tiny", preset="tiny")
    data = json.loads((path / "tds.json").read_text(encoding="utf-8"))
    data["markets"] = dict(reversed(data["markets"].items()))
    assert list(data["markets"]) == ["US", "KR"]
    (path / "tds.json").write_text(json.dumps(data), encoding="utf-8")
    snapshot = open_snapshot(DataConfig(path=path))
    grid = decision_grid(snapshot, monthly(), "2020-01-02", "2020-01-31")
    assert (grid.clock, grid.market, grid.calendar_id) == ("KR_close", "KR", "XKRX")
    for wrong in ("JP_close", "KR"):
        with pytest.raises(ConfigError, match="names no market of the snapshot"):
            decision_grid(snapshot, monthly(), "2020-01-02", "2020-01-31", clock=wrong)
    january = (monthly(), "2020-01-02", "2020-01-31")
    with pytest.raises(CapabilityError, match="market_local"):  # a grid per sleeve: M4
        decision_grid(snapshot, *january, clock="market_local")
    alone = make_snapshot(tmp_path / "us", preset="tiny", markets=("US",))
    us = decision_grid(open_snapshot(DataConfig(path=alone)), *january, clock="market_local")
    assert (us.market, us.clock, us.decision_ts[0].hour) == ("US", "market_local", 21)


def test_partial_period_decides_only_when_the_calendar_settles_it() -> None:
    """3.7, ADR 0043 (#461): a pick from the end needs a session after its period, one from
    the start a session before it, a pick that falls back to the first or last session both.
    The calendar is #461's: weekday sessions from 2020-01-15 (a Wednesday) to 2020-03-13."""
    days = np.arange("2020-01-15", "2020-03-14", dtype="datetime64[D]")
    days = days[(days.astype(np.int64) + 3) % 7 < 5]  # day 0 is a Thursday
    times = days.astype("datetime64[us]")
    cut = Calendar("KR", "XKRX", days, times, times, np.arange(len(days)), 0 * MINUTE)

    def picks(schedule: Schedule) -> list[str]:
        return [str(d)[5:] for d in days[schedule.rows(cut)]]

    assert (len(days), str(days[0]), str(days[-1])) == (43, "2020-01-15", "2020-03-13")
    assert picks(monthly()) == ["01-31", "02-28"]  # the table of #461's Decision
    assert picks(monthly(-2)) == ["01-30", "02-27"]
    assert picks(monthly(1)) == ["02-03", "03-02"]
    assert picks(monthly(5)) == ["02-07", "03-06"]
    assert picks(monthly(99)) == ["02-28"]
    assert picks(monthly(-99)) == ["02-03"]
    assert picks(quarterly()) == []
    fridays = ["01-17", "01-24", "01-31", "02-07", "02-14", "02-21", "02-28", "03-06"]
    mondays = ["01-20", "01-27", "02-03", "02-10", "02-17", "02-24", "03-02", "03-09"]
    assert picks(weekly()) == fridays  # the week of 03-09 has no session after it
    assert picks(weekly(1)) == mondays  # the week of 01-15 has no session before it
    assert picks(weekly(3)) == ["01-22", "01-29", "02-05", "02-12", "02-19", "02-26", "03-04",
                                "03-11"]  # fmt: skip
    assert picks(weekly(-9)) == mondays[:-1]  # falls back to the first session: both sides
    assert len(picks(daily())) == 43  # `daily` and `every` count no period
    assert picks(every(20)) == ["01-15", "02-12", "03-11"]
