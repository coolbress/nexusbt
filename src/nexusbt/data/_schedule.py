"""The schedules of spec 3.7 and the decision grid they give on a calendar (5.1.3), T1.3 (#235)."""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

import numpy as np

from nexusbt.contracts import CapabilityError, ConfigError, DecisionGrid

if TYPE_CHECKING:
    from numpy.typing import NDArray

    from nexusbt.data import Snapshot
    from nexusbt.data._calendar import Calendar

_Kind = Literal["monthly", "weekly", "quarterly", "annually", "daily", "every"]


@dataclass(frozen=True, slots=True)
class Schedule:
    """Decision dates as a rule on the schedule calendar (3.7). `rows` reads only the
    calendar, never the run's start date, so a run that starts later decides on the same
    sessions (INV-14). Built by `monthly`, `weekly`, `quarterly`, `annually`, `daily`, `every`."""

    kind: _Kind
    day: int = -1
    month: int = 12
    n: int = 1
    offset: int = 0

    def __post_init__(self) -> None:
        wrong = {"day": self.day == 0, "month": not 1 <= self.month <= 12, "n": self.n < 1}
        for name in (name for name, bad in wrong.items() if bad):
            value = getattr(self, name)
            raise ConfigError(
                what=f"{self.kind}: {name} = {value} names no session",
                where=f"the {self.kind} schedule",
                why="sessions count from 1, or from the end with a negative number (3.7)",
                fix="day: a number other than 0; month: 1 to 12; n: 1 or more",
                more="spec 3.7 schedules", layer=f"config — argument {name}={value}",
            )  # fmt: skip

    def rows(self, calendar: Calendar) -> NDArray[np.intp]:
        """The rows of `calendar` the schedule decides on. A schedule that counts inside a
        month or week decides there only when the calendar settles which session the pick is
        (3.7, ADR 0043): a pick from the end needs a session after the period, one from the
        start a session before it, one that falls back to the first or last session both."""
        if self.kind == "daily":
            return np.arange(len(calendar.dates))
        if self.kind == "every":  # the absolute session number, not a count from the start
            return np.flatnonzero((calendar.session_ord - self.offset) % self.n == 0)
        days = calendar.dates.astype("datetime64[D]").astype(np.int64)
        months = calendar.dates.astype("datetime64[M]").astype(np.int64)
        # ISO weeks start on Monday; day 0 (1970-01-01) is a Thursday
        period = (days + 3) // 7 if self.kind == "weekly" else months
        first = np.flatnonzero(np.r_[True, period[1:] != period[:-1]])
        size = np.diff(np.r_[first, len(period)])
        # the day-th session from 1, from the end when negative, inside the period
        at = np.minimum(self.day, size) - 1 if self.day > 0 else np.maximum(size + self.day, 0)
        month = months[first] % 12 + 1
        held = {"quarterly": month % 3 == 0, "annually": month == self.month}
        short = size < abs(self.day)  # the pick falls back to the first or last session
        before, after = first > 0, first + size < len(period)  # a session on that side
        settled = (before | ~(short | (self.day > 0))) & (after | ~(short | (self.day < 0)))
        rows: NDArray[np.intp] = (first + at)[settled & held.get(self.kind, True)]
        return rows


def monthly(day: int = -1) -> Schedule:
    """The `day`-th session of each month (3.7)."""
    return Schedule("monthly", day)


def weekly(weekday: int = -1) -> Schedule:
    """The `weekday`-th session of each ISO week (3.7)."""
    return Schedule("weekly", weekday)


def quarterly(day: int = -1) -> Schedule:
    """`monthly(day)` of March, June, September and December (3.7)."""
    return Schedule("quarterly", day)


def annually(month: int = 12, day: int = -1) -> Schedule:
    """`monthly(day)` of `month` (3.7)."""
    return Schedule("annually", day, month)


def daily() -> Schedule:
    """Every session (3.7)."""
    return Schedule("daily")


def every(n: int, offset: int = 0) -> Schedule:
    """The sessions with `(session_ord - offset) mod n == 0` (3.7, RV-C11)."""
    return Schedule("every", n=n, offset=offset)


def default_clock(markets: Iterable[str]) -> str:
    """`"<M>_close"` of the first market when the names are sorted by UTF-8 bytes, which is
    their code point order and not the order of the JSON object (5.1.3, R3-18)."""
    return f"{min(markets, key=str.encode)}_close"


def decision_grid(
    snapshot: Snapshot, schedule: Schedule, start: dt.date | str, end: dt.date | str,
    *, clock: str | None = None,
) -> DecisionGrid:  # fmt: skip
    """The decisions of `schedule` from `start` to `end` on the calendar of the clock's
    market M: `decision_ts = ts_close(M, d) + delta_M` (5.1.3), the period aligned to sessions
    with an E9 notice (5.1.6). `clock` is `"<M>_close"`, by default the snapshot's first
    market; the clock of each sleeve's own calendar (`market_local`) comes with the sleeves."""
    clock = clock or default_clock(snapshot.markets)
    market = clock.removesuffix("_close")
    if clock == "market_local" and len(snapshot.markets) == 1:
        market = next(iter(snapshot.markets))  # one market: its own calendar and `ready`
    elif clock == "market_local":
        raise CapabilityError(
            what="clock = 'market_local' is not available yet for several markets",
            where="argument clock", why="a grid per sleeve comes with the sleeves (M4)",
            fix=f"use one of: {', '.join(f'{m}_close' for m in sorted(snapshot.markets))}",
            more="spec 5.1.3", layer="config — argument clock='market_local'",
        )  # fmt: skip
    elif not clock.endswith("_close") or market not in snapshot.markets:
        raise ConfigError(
            what=f"clock = {clock!r} names no market of the snapshot",
            where="argument clock", why="the decision schedule runs on one market's calendar",
            fix=f"use one of: {', '.join(f'{m}_close' for m in sorted(snapshot.markets))}",
            more="spec 5.1.3", layer=f"config — argument clock={clock}",
        )  # fmt: skip
    calendar = snapshot.calendar(market)
    first, last = calendar.align(start, end)
    rows = schedule.rows(calendar)
    rows = rows[(rows >= first) & (rows <= last)]
    times = tuple(t.replace(tzinfo=dt.UTC) for t in calendar.ready[rows].tolist())
    days = calendar.dates.tolist()
    return DecisionGrid(market, calendar.calendar_id, clock, days[first], days[last],
                        tuple(days[r] for r in rows), times)  # fmt: skip
