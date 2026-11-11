"""The `full` level's instant checks from the rows: T001, T002, T005, T007, T008, T010, T011
(TDS 5.1, 5.5, 5.6, 5.13, 5.16, 6.2, 8.3).

Rules chosen with the maintainer (#225, 2026-11-11): T001 compares a stored `ts_available` with
the row's event instant, a bar's `ts_end` or an event's `ts_event`. T002 holds a stored
`ts_available` to the dataset's rule (not `column`), row by row; the calendar rules and a daily
bar's null `ts_end` read `calendar_sessions` through `instruments.calendar_id`, and a row with no
session, or a delay in years or months, is not judged. T005 compares the `ts_start` and `ts_end`
a daily session bar has with that day's open and close. T007 compares the UTC date of
`ts_available` with `period_end`, a warning for `value_how` `preliminary`. T008's tolerance is
0. A row with a null in what a code compares is skipped. One finding per dataset, code and
severity; a code a row could not be judged by is unchecked unless another row found it.
Memory holds the calendar and the instruments' calendars, besides a batch of rows.
"""

from __future__ import annotations

import bisect
import datetime as dt
import re
from collections import defaultdict
from collections.abc import Callable, Iterator, Mapping, Sequence
from typing import Any

import pyarrow as pa

from .check import _COL, _DELAY, _DUR, INSTANT_CODES, RULE, Finding, Severity
from .manifest import Manifest
from .refs import _rows

T001, T002, T005, T007, T008, T010, T011 = INSTANT_CODES
TICKS = frozenset({"trades", "quotes", "book_deltas", "book_snapshots", "trading_status_events"})
_PARTS = re.compile(
    rf"(?P<name>[a-z_]+)(?:\((?P<column>{_COL})(?:\+(?P<inner>{_DUR}))?\))?(?:\+(?P<add>{_DUR}))?"
)
SAID = {T001: "row(s) available before their event", T002: "row(s) whose ts_available is not "
        "what the availability rule gives", T005: "daily bar(s) not bounded by their session",
        T007: "fact(s) available before period_end", T008: "row(s) received before their event",
        T010: "instrument(s) with last_session before listed_on",
        T011: "exit value(s) published before the exit"}  # fmt: skip
Row = dict[str, Any]


def check_instants(m: Manifest, only: Sequence[str] | None, blind: set[str]) -> list[Finding]:
    """The seven codes on the checked datasets; a file they cannot read leaves them unchecked."""
    try:
        return _check(m, only, blind)
    except (OSError, pa.ArrowException, TypeError, ValueError, OverflowError):
        blind.update(INSTANT_CODES)  # unreadable, or a column of the wrong type: not compared
        return []


def _check(m: Manifest, only: Sequence[str] | None, blind: set[str]) -> list[Finding]:
    root = m.root.resolve()

    def rows(kind: str, *columns: str) -> Iterator[tuple[Any, ...]]:
        return (r for d in m.datasets if d.get("kind") == kind for r in _rows(root, d, columns))

    calendar_of = dict(rows("instruments", "instrument_id", "calendar_id"))
    days: defaultdict[Any, dict[Any, tuple[Any, Any]]] = defaultdict(dict)
    for calendar, day, opens, closes in rows(
        "calendar_sessions", "calendar_id", "session_date", "ts_open", "ts_close"
    ):
        days[calendar][day] = (opens, closes)
    ordered = {c: sorted(s.items()) for c, s in days.items()}
    has_calendar = any(d.get("kind") == "calendar_sessions" for d in m.datasets)

    def session(r: Row) -> tuple[Any, Any] | None:
        return days.get(calendar_of.get(r.get("instrument_id")), {}).get(r.get("session_date"))

    def next_open(r: Row, day: Any) -> Any:
        sessions = ordered.get(calendar_of.get(r.get("instrument_id")), [])
        at = bisect.bisect_right([d for d, _ in sessions], day)
        return sessions[at][1][0] if at < len(sessions) else None

    out, undecided = [], set[str]()
    for ds in (d for d in m.datasets if only is None or d.get("name") in only):
        kind, name = str(ds.get("kind")), str(ds.get("name"))
        rule = _rule(ds.get("availability"))
        params = ds["params"] if isinstance(ds.get("params"), dict) else {}
        daily = kind == "bars" and params.get("freq") == "1d"
        bounded = daily and params.get("bar_time") in (None, "session")
        bad: dict[tuple[str, Severity], list[Any]] = {}  # → [count, first row]
        for r in _read(root, ds, kind, rule):
            for code, severity in _broken(kind, r, rule, bounded, session, next_open):
                if severity is None:
                    undecided.add(code)
                else:
                    bad.setdefault((code, severity), [0, r])[0] += 1
            if bounded and not has_calendar and (r.get("ts_start") or r.get("ts_end")):
                undecided.add(T005)
        for (code, severity), (n, first) in sorted(bad.items()):
            key = {c: str(first[c]) for c in first if c.endswith("_id") and first[c] is not None}
            out.append(Finding(code, severity, f"{n} {SAID[code]}", name, key=key, count=n))
    blind.update(c for c in undecided if all(f.code != c for f in out))
    return out


def _rule(availability: object) -> str | None:
    """The dataset's 6.2 rule, bare or `{"rule": …}`, when it is one T002 compares: not
    `column`, and known (an unknown one is M014's)."""
    rule = availability.get("rule") if isinstance(availability, dict) else availability
    return rule if isinstance(rule, str) and rule != "column" and RULE.fullmatch(rule) else None


#: Per kind: the columns read besides those a rule needs.
COLUMNS = {
    "bars": ("instrument_id", "session_date", "ts_start", "ts_end", "ts_available"),
    "events": ("event_id", "ts_event", "ts_available"),
    "fundamentals_events": ("fact_id", "period_end", "ts_available", "value_how"),
    "instruments": ("instrument_id", "listed_on", "last_session"),
    "delistings": ("delisting_id", "ts_exit_known", "ts_value_available"),
    **dict.fromkeys(TICKS, ("instrument_id", "ts_event", "ts_recv")),
}


def _read(root: Any, ds: Mapping[str, Any], kind: str, rule: str | None) -> Iterator[Row]:
    columns = list(COLUMNS.get(kind, ()))
    if rule:
        match = _PARTS.fullmatch(rule)
        columns += ["instrument_id", "session_date", "ts_available", "ts_end", "ts_recv"]
        columns += [match["column"] or "known_on"] if match else []
    if not columns:
        return
    columns = list(dict.fromkeys(columns))
    yield from (dict(zip(columns, r, strict=True)) for r in _rows(root, ds, columns))


def _broken(
    kind: str, r: Row, rule: str | None, bounded: bool,
    session: Callable[[Row], tuple[Any, Any] | None], next_open: Callable[[Row, Any], Any],
) -> Iterator[tuple[str, Severity | None]]:  # fmt: skip
    """The codes row `r` breaks, with their severity; None: the row cannot be judged."""
    available: Any = r.get("ts_available")
    if kind in ("bars", "events") and _before(available, r.get(EVENT[kind])):
        yield T001, "error"
    if rule and available is not None:
        expected = _derive(rule, r, session, next_open)
        if expected is None or expected != available:
            yield T002, None if expected is None else "error"
    day = session(r) if bounded else None
    if day and any(v is not None and v != s for v, s in zip(
        (r["ts_start"], r["ts_end"]), day, strict=True)):  # fmt: skip
        yield T005, "error"
    utc_day = available.astimezone(dt.UTC).date() if available is not None else None
    if kind == "fundamentals_events" and _before(utc_day, r["period_end"]):
        yield T007, "warning" if r["value_how"] == "preliminary" else "error"
    for code, severity, kinds, (early, late) in LATER:
        if kind in kinds and _before(r[early], r[late]):
            yield code, severity


#: T001's event instant: a bar is complete at its end (5.5, 6.1).
EVENT = {"bars": "ts_end", "events": "ts_event"}
#: (code, severity, kinds, (column, column it must not precede)).
LATER: tuple[tuple[str, Severity, frozenset[str], tuple[str, str]], ...] = (
    (T008, "warning", TICKS, ("ts_recv", "ts_event")),  # tolerance 0 (#225)
    (T010, "error", frozenset({"instruments"}), ("last_session", "listed_on")),
    (T011, "warning", frozenset({"delistings"}), ("ts_value_available", "ts_exit_known")),
)


def _before(a: Any, b: Any) -> bool:
    """`a < b` when both are present."""
    return a is not None and b is not None and bool(a < b)


def _span(text: str | None) -> dt.timedelta | None:
    """An ISO 8601 delay without years or months; None for one with them."""
    delay = _DELAY.fullmatch(text or "P")
    if delay is None:
        return None
    w, d, h, minutes, s = (float(x or 0) for x in delay.groups())
    return dt.timedelta(weeks=w, days=d, hours=h, minutes=minutes, seconds=s)


def _derive(
    rule: str, r: Row, session: Callable[[Row], tuple[Any, Any] | None],
    next_open: Callable[[Row, Any], Any],
) -> Any:  # fmt: skip
    """The instant TDS 6.2's `rule` gives row `r`; None when it cannot say."""
    match = _PARTS.fullmatch(rule)
    add = _span(match["add"]) if match else None
    if match is None or add is None:
        return None
    name, column, inner = match["name"], match["column"], match["inner"]
    day, base = session(r), None
    if name in ("ts_end", "ts_recv"):
        base = r.get(name)
        base = day[1] if base is None and name == "ts_end" and day else base  # 5.5
    elif name == "ts_recv_else":
        fallback: Any = r.get(str(column))
        more = _span(inner)
        base = r.get("ts_recv")
        if base is None and fallback is not None and more is not None:
            base = fallback + more
    elif name in ("session_open", "session_close"):
        base = day[name == "session_close"] if day else None
    else:  # next_session_open(<date column>), `known_on` by default
        on = r.get(column or "known_on")
        base = next_open(r, on) if on is not None else None
    return None if base is None else base + add
