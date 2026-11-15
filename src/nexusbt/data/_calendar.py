"""A market's sessions (spec 5.1.1) and the freeze time of each row (5.1.2), T1.3 (#235)."""

from __future__ import annotations

import datetime as dt
import re
import warnings
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from nexusbt.contracts import CapabilityError, ConfigError, SessionNotice, SnapshotError

if TYPE_CHECKING:
    from numpy.typing import NDArray

    from nexusbt_tds.manifest import Manifest

#: An ISO 8601 duration of fixed length: weeks, days, hours, minutes, seconds (TDS 6.2).
_DURATION = re.compile(r"P(?:(\d+)W)?(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?)?")


@dataclass(frozen=True, slots=True, eq=False)
class Calendar:
    """The sessions of one market in order: row s has its local date (a label), `ts_open(s)`
    and `ts_close(s)` in UTC microseconds (5.1.1) and its absolute number `session_ord` (3.7).

    `ready_delay` is the constant the data sets for the market (5.1.2), so `ready`, the time
    each row freezes, does not depend on any row of the bars (INV-02)."""

    market: str
    calendar_id: str
    dates: NDArray[np.datetime64]
    ts_open: NDArray[np.datetime64]
    ts_close: NDArray[np.datetime64]
    session_ord: NDArray[np.int64]
    ready_delay: np.timedelta64

    @property
    def ready(self) -> NDArray[np.datetime64]:
        """`ready_m(s) = ts_close(s) + delta_m` for every row (5.1.2)."""
        return self.ts_close + self.ready_delay

    def align(self, start: dt.date | str, end: dt.date | str) -> tuple[int, int]:
        """The rows of the first session on or after `start` and the last on or before `end`
        (5.1.6), with an E9 notice for each date that is not a session."""
        given = [np.datetime64(str(d), "D") for d in (start, end)]
        first = int(np.searchsorted(self.dates, given[0], "left"))
        last = int(np.searchsorted(self.dates, given[1], "right")) - 1
        if first > last:
            raise ConfigError(
                what=f"no {self.market} session from {start} to {end}",
                where="arguments start and end", why="a run needs one session or more (5.1.6)",
                fix=f"choose a period inside {self.dates[0]} to {self.dates[-1]}",
                more="spec 5.1.6", layer=f"config — argument start={start}",
            )  # fmt: skip
        for name, day, row, verb in (("start", given[0], first, "begin"),
                                     ("end", given[1], last, "end")):  # fmt: skip
            if self.dates[row] != day:
                using = self.dates[row]
                warnings.warn(str(SessionNotice(
                    what=f"{name} {day} is not a {self.market} session; using {using}",
                    where=f"argument {name}", why=f"runs {verb} on a session",
                    fix=f"{name}='{using}'", more="spec 6.6 E9", subject=name,
                    layer=f"config — argument {name}={day}",
                )), stacklevel=3)  # fmt: skip
        return first, last

    def late_bars(
        self, dates: NDArray[np.datetime64], available: NDArray[np.datetime64]
    ) -> NDArray[np.int64]:
        """Per row, the bars of that session with `ts_available > ready(s)`: the diagnostic
        `LateBar` (5.1.2). `dates` and `available` are the columns of this market's bars, row
        for row; a bar on a day that is not one of the sessions is in no row and not counted."""
        rows = np.minimum(np.searchsorted(self.dates, dates), len(self.dates) - 1)
        late = (self.dates[rows] == dates) & (available.astype("datetime64[us]") > self.ready[rows])
        return np.bincount(rows[late], minlength=len(self.dates))


def read_calendar(manifest: Manifest, market: str) -> Calendar:
    """The calendar of `market` from `calendar_sessions`, in session order; without rows for
    its `calendar_id`, the sessions of exchange_calendars over the bars' period (4.5 F-02)."""
    calendar_id = str(manifest.data["markets"][market]["calendar_id"])
    kinds = {d["kind"]: d for d in reversed(manifest.datasets)}  # the first of each kind
    held = kinds.get("calendar_sessions", {}).get("files", [])
    tables = [pq.read_table(manifest.root / f["path"]) for f in held]
    rows = pa.concat_tables(tables) if tables else None
    if rows is not None:
        rows = rows.filter(pc.equal(rows["calendar_id"], calendar_id)).sort_by("session_date")
    bars = kinds.get("bars")
    delta = np.timedelta64(_delay(bars, str(manifest.data["snapshot_id"])), "us")
    if rows is None or not len(rows):
        return _synthesized(market, calendar_id, bars, delta)

    def column(name: str, unit: str) -> Any:
        return rows[name].to_numpy().astype(f"datetime64[{unit}]")

    numbered = "session_ord" in rows.column_names  # 3.7: the package's, else from 0
    ords = rows["session_ord"].to_numpy() if numbered else np.arange(len(rows))
    return Calendar(market, calendar_id, column("session_date", "D"), column("ts_open", "us"),
                    column("ts_close", "us"), ords.astype(np.int64), delta)  # fmt: skip


def _synthesized(
    market: str, calendar_id: str, bars: Mapping[str, Any] | None, delta: np.timedelta64
) -> Calendar:
    """F-02's session table: the library's sessions from the first to the last day of the
    bars, numbered from 0 (3.7); E18 without bars of the market or for a calendar the library
    does not know. `open_snapshot` has said E30 when a feature asked for the sessions."""
    import exchange_calendars as xcals  # only a package without sessions pays its import

    period = (bars or {}).get("coverage", {}).get("by_market", {}).get(market)
    if period is None or calendar_id not in xcals.get_calendar_names():
        raise CapabilityError(
            what=f"no sessions for market {market}: calendar {calendar_id} is not in"
                 " calendar_sessions and cannot be synthesized",
            where=f"market {market}, calendar_id {calendar_id}",
            why="sessions come from calendar_sessions, or from exchange_calendars over the"
                " period of the market's bars (4.5 F-02)",
            fix="add calendar_sessions rows for the calendar to the package",
            more="spec 4.5 F-02 and 5.1.1",
            layer="data — snapshot - / calendar_sessions / column calendar_id / producer -",
        )  # fmt: skip
    days = xcals.get_calendar(calendar_id, start=period["first"], end=period["last"]).schedule

    def utc(name: str) -> Any:
        return days[name].dt.tz_localize(None).to_numpy().astype("datetime64[us]")

    dates = days.index.to_numpy().astype("datetime64[D]")
    return Calendar(market, calendar_id, dates, utc("open"), utc("close"),
                    np.arange(len(dates), dtype=np.int64), delta)  # fmt: skip


def _delay(bars: Mapping[str, Any] | None, snapshot_id: str) -> int:
    """5.1.2's delta in microseconds: 0 under the bars' rule `ts_end`, the duration under
    `ts_end+<duration>`, `params.ready_delay` (0 when absent) under the column rule."""
    declared = (bars or {}).get("availability", "ts_end")
    rule = declared.get("rule") if isinstance(declared, dict) else declared
    if rule == "column" or (isinstance(declared, dict) and "column" in declared):
        text = (bars or {}).get("params", {}).get("ready_delay", "PT0S")
    elif rule == "ts_end":
        return 0
    else:
        text = str(rule)[len("ts_end+") :] if str(rule).startswith("ts_end+") else None
    duration = _DURATION.fullmatch(text) if isinstance(text, str) and text != "P" else None
    if duration is None:
        raise SnapshotError(
            what=f"bars availability {declared!r} with ready_delay {text!r} gives no delay",
            where=f"snapshot {snapshot_id} tds.json, the bars dataset",
            why="a row freezes at ts_close + a delay of fixed length set by the data (5.1.2)",
            fix="declare the rule ts_end, ts_end+<duration>, or a column with params.ready_delay"
                " as an ISO 8601 duration without years or months",
            more="spec 5.1.2 and 4.6; TDS 6.2",
            layer=f"data — snapshot {snapshot_id} / bars / column ts_available / producer -",
        )  # fmt: skip
    w, d, h, m, s = (x or "0" for x in duration.groups())
    whole = (((int(w) * 7 + int(d)) * 24 + int(h)) * 60 + int(m)) * 60
    return whole * 10**6 + round(float(s) * 10**6)
