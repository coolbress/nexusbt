"""The `full` level's density checks from the rows: D001, D002, D004 (TDS 4.2, 5.5, 8.3).

Rules chosen with the maintainer (#225, 2026-11-11): D001 reads dense daily bars, for each
instrument with a row in the dataset: every session of its calendar from `listed_on` to
`last_session`, or without it to the date of its market's `complete_through`, has a row; rows
on those sessions are counted (a duplicate is K001's), and an instrument with neither end, no
`listed_on` or no calendar is not judged. D002 here is a daily bar outside its instrument's
`listed_on`..`delisted_on`; a non-session day is R003's, and a dataset the statistics already
found is not reported twice. D004 compares a dataset's and each file's `rows` with the rows,
and the `coverage` keys of 4.2's example that are present: `instruments`, `ts_min`, `ts_max`,
`by_market` (`instruments`, `first`, `last`, `rows` per `market=` partition).
D003 (#425, 2026-11-12) reads a dataset with no `last` in a market whose
`processed_through_session` it gives: a row whose 6.2 availability instant (`_known`) is after
that session's close in the market's calendar; the row's market is its `market` column or
partition, else its instrument's. A null instant, or an instrument not found, is not judged.
Memory holds the calendar, the instruments' listings and, per dataset, a count and the
instrument ids seen per market.
"""

from __future__ import annotations

import bisect
import datetime as dt
from collections import Counter, defaultdict
from collections.abc import Collection, Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Any
from zoneinfo import ZoneInfo

import pyarrow as pa
import pyarrow.parquet as pq

from .check import DENSITY_CODES, TIMELESS, Finding, _day, _instant
from .keys import PANELS, batches, listed, time_columns
from .manifest import Manifest
from .refs import _rows

D001, D002, D003, D004 = DENSITY_CODES
LISTING = ("instrument_id", "calendar_id", "market", "listed_on", "last_session", "delisted_on")


def check_densities(
    m: Manifest, only: Sequence[str] | None, blind: set[str], reported: Collection[object],
    notes: list[str],
) -> list[Finding]:  # fmt: skip
    """The four codes on the checked datasets; `reported`: datasets with a D002 already;
    `notes`: why D003 was not judged on a dataset."""
    try:
        return _check(m, only, blind, reported, notes)
    except (OSError, pa.ArrowException, TypeError, ValueError):
        blind.update(DENSITY_CODES)  # unreadable, or a column of the wrong type: not compared
        return []


def _check(
    m: Manifest, only: Sequence[str] | None, blind: set[str], reported: Collection[object],
    notes: list[str],
) -> list[Finding]:  # fmt: skip
    root = m.root.resolve()
    listings = {r[0]: r for d in m.datasets if d.get("kind") == "instruments"
                for r in _rows(root, d, LISTING)}  # fmt: skip
    days: defaultdict[Any, list[Any]] = defaultdict(list)
    closes = {}  # (calendar, session) → its close
    for d in (d for d in m.datasets if d.get("kind") == "calendar_sessions"):
        for calendar, day, close in _rows(root, d, ("calendar_id", "session_date", "ts_close")):
            days[calendar].append(day)
            closes[calendar, day] = close
    sessions = {c: sorted(set(v)) for c, v in days.items()}
    markets = m.data["markets"] if isinstance(m.data.get("markets"), dict) else {}
    market_of = {i: r[2] for i, r in listings.items()}
    out = []
    for ds in (d for d in m.datasets if only is None or d.get("name") in only):
        name, params = str(ds.get("name")), ds.get("params")
        params = params if isinstance(params, dict) else {}
        daily = ds.get("kind") == "bars" and params.get("freq") == "1d"
        if daily:
            dense = params.get("density") == "dense"
            out += _listed(root, ds, name, listings, sessions, markets, dense, blind, reported)
        out += _counts(root, ds, name)
        out += _after(root, ds, name, markets, closes, market_of, blind, notes)
    return out


def _after(
    root: Path, ds: Mapping[str, Any], name: str, markets: Mapping[str, Any],
    closes: Mapping[tuple[Any, Any], Any], market_of: Mapping[Any, Any], blind: set[str],
    notes: list[str],
) -> list[Finding]:  # fmt: skip
    """D003 of one dataset (TDS 4.3)."""
    coverage = ds.get("coverage")
    by = coverage.get("by_market") if isinstance(coverage, dict) else None
    through = {m: day for m, said in (by.items() if isinstance(by, dict) else ())
               if isinstance(said, dict) and "last" not in said
               and (day := _day(said.get("processed_through_session")))}  # fmt: skip
    if not through or ds.get("kind") in TIMELESS:
        return []
    columns, limit, why = _known(ds.get("availability")), {}, []
    for m, day in sorted(through.items()):
        entry = markets.get(m)
        close = closes.get((entry.get("calendar_id") if isinstance(entry, dict) else None, day))
        if close is None:
            why.append(f"no close of {m}'s session {day}")
        limit[m] = close
    seen: set[Any] = set()  # markets with a row, and with an instant
    known, late, first = set(), 0, None
    read = ("instrument_id", "market", *columns)
    for i, market, *times in _rows(root, ds, read) if columns else ():
        m = market if market is not None else market_of.get(i)
        if limit.get(m) is None:
            continue  # a market without the field or its close; an instrument not found (R001)
        seen.add(m)
        at = min((t for t in times[:2] if t is not None), default=times[-1])
        if at is not None:
            known.add(m)
            if at > limit[m]:
                late, first = late + 1, first or {"instrument_id": str(i)}
    why += [f"every {'/'.join(columns)} of {m} is null" for m in sorted(seen - known)]
    if not columns or why:
        blind.add(D003)
        notes.append(f"{D003} not checked on {name}: {'; '.join(why) or 'no instant column'}")
    if not late:
        return []
    msg = f"{late} row(s) available after the close of their market's processed_through_session"
    return [Finding(D003, "error", msg, name, key=first, count=late)]


def _known(availability: object) -> tuple[str, ...]:
    """The columns of a row's instant: the earlier of the first two not null, else the last
    (5.11's existence instant `ts_known`, of `corporate_actions`), or the one; a `delistings`'
    `exit`, a column form's column, rule `column`'s `ts_available`; none for another rule."""
    a = availability if isinstance(availability, dict) else {"rule": availability}
    if {"terms", "effect"} <= a.keys():
        named: tuple[object, ...] = ("ts_announced", a["terms"], a["effect"])
    else:
        rule = "ts_available" if a.get("rule") == "column" else None
        named = (a.get("exit") or a.get("column") or rule,)
    return tuple(str(c) for c in named) if all(isinstance(c, str) for c in named) else ()


def _listed(
    root: Path, ds: Mapping[str, Any], name: str, listings: Mapping[Any, tuple[Any, ...]],
    sessions: Mapping[Any, list[Any]], markets: Mapping[str, Any], dense: bool, blind: set[str],
    reported: Collection[object],
) -> list[Finding]:  # fmt: skip
    """D002 and, on dense bars, D001 of one daily bars dataset."""
    outside, first, held = 0, None, Counter[Any]()
    on = {c: set(v) for c, v in sessions.items()} if dense else {}
    ends = {i: _end(r[4], markets.get(r[2])) for i, r in listings.items()} if dense else {}
    for i, day in _rows(root, ds, ("instrument_id", "session_date")):
        _, calendar, _, listed_on, _, delisted = listings.get(i, (None,) * 6)
        if day is None or i not in listings:
            continue  # R001's, S003's
        if (listed_on is not None and day < listed_on) or (delisted and day > delisted):
            outside, first = outside + 1, first or {"instrument_id": i, "session_date": str(day)}
        held[i] += dense and listed_on is not None and ends[i] is not None and (
            listed_on <= day <= ends[i] and day in on.get(calendar, ()))  # fmt: skip
    out = []
    if outside and name not in reported:
        msg = f"{outside} daily bar(s) outside their instrument's listed_on..delisted_on"
        out.append(Finding(D002, "error", msg, name, key=first, count=outside))
    missing, shown = 0, None
    for i in sorted(held, key=str) if dense else ():  # each instrument with a row
        _, calendar, _, listed_on, _, _ = listings[i]
        end = ends[i]
        if end is None or listed_on is None or calendar not in sessions:
            blind.add(D001)
            continue
        lack = len(_between(sessions[calendar], listed_on, end)) - held[i]
        missing, shown = missing + max(lack, 0), shown or ({"instrument_id": i} if lack else None)
    if missing:
        msg = f"{missing} session(s) without a row in dense daily bars"
        out.append(Finding(D001, "error", msg, name, key=shown, count=missing))
    return out


def _end(last: Any, market: object) -> Any:
    """D001's last day: `last_session`, else the market's `complete_through` as a date in the
    market's `timezone` (UTC when it names none); None without either."""
    entry = market if isinstance(market, dict) else {}
    through = _instant(entry.get("complete_through"))
    if last is not None or through is None:
        return last
    try:
        zone: dt.tzinfo = ZoneInfo(str(entry.get("timezone")))
    except (KeyError, ValueError):  # no or an unknown zone name
        zone = dt.UTC
    return through.astimezone(zone).date()


def _between(days: list[Any], start: Any, end: Any) -> list[Any]:
    """The sorted `days` from `start` to `end`, both included."""
    return days[bisect.bisect_left(days, start) : bisect.bisect_right(days, end)]


def _counts(root: Path, ds: Mapping[str, Any], name: str) -> list[Finding]:
    """D004: the declared `rows` and `coverage` against the files."""
    files = list(listed(root, ds))  # inside the package and there (M012, M004), once each
    read = {rel: pq.ParquetFile(root / rel).metadata.num_rows for rel, _ in files}
    total, wrong = sum(read.values()), []
    for entry in (f for f in ds.get("files") or [] if isinstance(f, dict) and "rows" in f):
        n = read.get(str(PurePosixPath(str(entry.get("path")))))
        if n is not None and n != entry["rows"]:
            wrong.append(f"{entry['path']} rows {entry['rows']}, read {n}")
    if "rows" in ds and ds["rows"] != total:
        wrong.append(f"rows {ds['rows']}, read {total}")
    coverage = ds.get("coverage")
    if isinstance(coverage, dict):
        wrong += _coverage(root, ds, files, coverage)
    if not wrong:
        return []
    return [Finding(D004, "error", "; ".join(wrong), name, count=len(wrong))]


def _coverage(
    root: Path, ds: Mapping[str, Any], files: list[tuple[str, dict[str, str]]],
    declared: Mapping[str, Any],
) -> list[str]:  # fmt: skip
    """The `coverage` keys present that differ from the rows (4.2's example)."""
    date = "period" if ds.get("kind") in PANELS else "session_date"
    ids: defaultdict[Any, set[Any]] = defaultdict(set)  # market (None: all) → instrument ids
    spans: dict[Any, list[Any]] = {}  # market → [first, last, rows]
    typed = time_columns(ds)
    for rel, parts in files:
        market = parts.get("market")
        for n, b in batches(root, rel, parts, ("instrument_id", date), 65_536, typed):
            ids[None].update(b.get("instrument_id", ()))
            ids[market].update(b.get("instrument_id", ()))
            got = [d for d in b.get(date, ()) if d is not None]
            for key in (None, market):
                span = spans.setdefault(key, [None, None, 0])
                span[2] += n
                if got:
                    span[0] = min([*got, *([span[0]] if span[0] else [])])
                    span[1] = max([*got, *([span[1]] if span[1] else [])])
    whole = spans.get(None, [None, None, 0])
    actual: dict[str, Any] = {"instruments": len(ids[None] - {None})}
    actual |= {"ts_min": _text(whole[0]), "ts_max": _text(whole[1])} if whole[0] else {}
    out = [f"coverage.{k} {declared[k]}, read {v}" for k, v in actual.items()
           if k in declared and declared[k] != v]  # fmt: skip
    by_market = declared.get("by_market")
    for market, said in by_market.items() if isinstance(by_market, dict) else ():
        first, last, rows = spans.get(market, [None, None, 0])
        read = {"instruments": len(ids[market] - {None}), "first": _text(first),
                "last": _text(last), "rows": rows}  # fmt: skip
        out += [f"coverage.by_market.{market}.{k} {said[k]}, read {v}" for k, v in read.items()
                if isinstance(said, dict) and k in said and said[k] != v]  # fmt: skip
    return out


def _text(day: object) -> str | None:
    return day.isoformat() if isinstance(day, dt.date) else None
