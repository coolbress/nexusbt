"""The `full` level's key checks from the rows: K001~K004 (TDS 3.5, 3.6), K010 (5.2), K011 (5.4).

Rules chosen with the maintainer (#224, 2026-11-05): a `year=` or `date=` folder holds the rows
whose `session_date` (`period` for the 5.25 panels) falls in it, and a kind without that column
leaves K003 unchecked; a file's time range is its `<ts_min>_<ts_max>` name (3.6), so a
`part-NNNNN` file has none. A null in a sort column sorts last, as Arrow sorts it.
"""

from __future__ import annotations

import datetime as dt
import re
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import replace
from itertools import combinations, pairwise
from pathlib import Path, PurePosixPath
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from .check import KEY_CODES, Finding, _unsafe
from .manifest import Manifest
from .profiles import meets

K001, K002, K003, K004, K010, K011 = KEY_CODES
TIME_PARTS = ("year", "date")  # the partitions that are time ranges, K003's (TDS 3.5)
PANELS = frozenset({"feature_panels", "label_panels"})
_STAMP = r"(\d{4}-\d\d-\d\dT\d\d)-(\d\d)-(\d\d)(?:-(\d{1,9}))?(Z|[+-]\d\d-\d\d)"
_RANGE = re.compile(rf"{_STAMP}_{_STAMP}\.parquet")  # 3.6, `:` and `.` written as `-`

Row = dict[str, Any]
File = tuple[str, dict[str, str], list[Row]]  # path, partition values, rows


def check_keys(m: Manifest, only: Sequence[str] | None, blind: set[str]) -> list[Finding]:
    from .schemas.verify import load_schemas

    schemas, root, out = load_schemas(), m.root.resolve(), []
    for ds in (d for d in m.datasets if only is None or d.get("name") in only):
        kind, schema = ds.get("kind"), schemas.get(str(ds.get("kind")))
        files = _read(root, ds)
        if files is None:  # a file Parquet cannot read: S010's, its rows unseen
            blind.update(KEY_CODES)
            continue
        params = ds["params"] if isinstance(ds.get("params"), dict) else {}
        key = _variant(ds.get("key", schema.key if schema else None), params)
        sort = _variant(ds.get("sort", schema.sort if schema else None), params)
        found = [*_duplicates(files, key, blind), *_unsorted(files, sort, blind)]
        found += [*_off_partition(files, "period" if kind in PANELS else "session_date", blind)]
        found += [*_overlaps(files)]
        rows = [r for _, _, rs in files for r in rs]
        found += _reused(rows, blind) if kind == "instrument_symbols" else []
        found += _numbering(rows) if kind == "calendar_sessions" else []
        out += [replace(f, dataset=ds.get("name")) for f in found]
    return out


def _read(root: Path, ds: Mapping[str, Any]) -> list[File] | None:
    """Each listed file once (a second listing is M013's), partition values from the path."""
    out, seen = [], set()
    listed = ds.get("files")
    for entry in listed if isinstance(listed, list) else []:
        rel = entry.get("path") if isinstance(entry, dict) else None
        if not isinstance(rel, str) or (rel := str(PurePosixPath(rel))) in seen:
            continue
        seen.add(rel)
        if _unsafe(root, rel) or not (root / rel).is_file():
            continue  # M012, M004
        try:
            rows = pq.read_table(root / rel).to_pylist()
        except (OSError, pa.ArrowException):
            return None
        parts = dict(p.split("=", 1) for p in PurePosixPath(rel).parent.parts if "=" in p)
        out.append((rel, parts, [parts | row for row in rows]))
    return out


def _variant(value: object, params: Mapping[str, Any]) -> list[str] | None:
    """A schema `key` or `sort`; bars name an intraday one (`freq<1d`, TDS 5.5) and a daily one."""
    if isinstance(value, dict):
        value = value.get("intraday" if meets(params, "freq", "<1d") else "daily")
    return value if isinstance(value, list) else None


def _shown(columns: Sequence[str], row: Row) -> dict[str, object]:
    """A row's `columns` as TDS 8.4's JSON `key`."""
    plain = (str, int, float, bool, type(None))
    return {c: row[c] if isinstance(row[c], plain) else str(row[c]) for c in columns}


def _duplicates(files: list[File], key: list[str] | None, blind: set[str]) -> Iterable[Finding]:
    """K001: a key on two rows anywhere in the dataset, with the row's partition values other
    than `year=` and `date=` (TDS 3.5; #224, 2026-11-05)."""
    own = [(rs, {p: v for p, v in parts.items() if p not in TIME_PARTS}) for _, parts, rs in files]
    rows = [(r, folder) for rs, folder in own for r in rs]
    if key is None or any(c not in r for r, _ in rows for c in key):
        blind.add(K001)
        return
    counts = Counter(
        (tuple(r[c] for c in key), tuple(sorted(folder.items()))) for r, folder in rows
    )
    if twice := [k for k, n in counts.items() if n > 1]:
        first = dict(zip(key, twice[0][0], strict=True)) | dict(twice[0][1])
        msg, n = f"{len(twice)} key value(s) on more than one row", sum(counts[k] for k in twice)
        yield Finding(K001, "error", msg, key=_shown(list(first), first), count=n)


def _group(items: Iterable[Any], by: Any) -> dict[Any, list[Any]]:
    out: defaultdict[Any, list[Any]] = defaultdict(list)
    for item in items:
        out[by(item)].append(item)
    return out


def _folders(files: list[File]) -> dict[str, list[File]]:
    """The files of each partition folder, in file-name order (3.5)."""
    return _group(sorted(files, key=lambda f: f[0]), lambda f: f[0].rpartition("/")[0])


def _unsorted(files: list[File], sort: list[str] | None, blind: set[str]) -> Iterable[Finding]:
    """K002: rows out of `sort` order in a file, or across a folder's files in name order."""
    if sort is None or any(c not in r for _, _, rows in files for r in rows for c in sort):
        blind.add(K002)
        return
    for group in _folders(files).values():
        rows = [(rel, [(r[c] is None, r[c]) for c in sort], r) for rel, _, rs in group for r in rs]
        bad = [b for a, b in pairwise(rows) if b[1] < a[1]]
        if bad:
            rel, _, row = bad[0]
            msg = f"{len(bad)} row(s) sort before the row above them by {', '.join(sort)}"
            yield Finding(K002, "error", msg, file=rel, key=_shown(sort, row), count=len(bad))


def _off_partition(files: list[File], column: str, blind: set[str]) -> Iterable[Finding]:
    """K003: a row whose `column` lies outside its `year=` or `date=` folder."""
    for rel, parts, rows in files:
        for part, value in ((p, parts[p]) for p in TIME_PARTS if p in parts):
            if any(column not in r for r in rows):
                blind.add(K003)
                continue
            days = [r[column] for r in rows if isinstance(r[column], dt.date)]
            bad = [d for d in days if (str(d.year) if part == "year" else d.isoformat()) != value]
            if bad:
                msg = f"{len(bad)} row(s) with {column} outside {part}={value}, e.g. {bad[0]}"
                yield Finding(K003, "error", msg, file=rel, count=len(bad))


def _instant(match: Sequence[str | None]) -> tuple[dt.datetime, int]:
    """One `_STAMP` of a file name as (instant to the second, nanoseconds)."""
    hour, minute, second, fraction, zone = match
    zone = "+00:00" if zone == "Z" else f"{str(zone)[:3]}:{str(zone)[4:]}"
    when = dt.datetime.fromisoformat(f"{hour}:{minute}:{second}{zone}")
    return when, int((fraction or "").ljust(9, "0"))


def _overlaps(files: list[File]) -> Iterable[Finding]:
    """K004: two `<ts_min>_<ts_max>` files of one folder whose ranges share an instant."""
    for group in _folders(files).values():
        spans = []
        for rel, _, _ in group:
            if match := _RANGE.fullmatch(PurePosixPath(rel).name):
                try:
                    spans.append((_instant(match.groups()[:5]), _instant(match.groups()[5:]), rel))
                except ValueError:  # not a date: no range named
                    continue
        last: tuple[Any, str] | None = None  # the latest end so far and its file
        for start, end, rel in sorted(spans):
            if last and start <= last[0]:
                yield Finding(K004, "error", f"time range overlaps {last[1]}", file=rel)
            last = (end, rel) if not last or end > last[0] else last


def _before(a: Any, b: Any) -> bool | None:  # `a < b`; a null end is open, a null start unknown
    return True if b is None else None if a is None else bool(a < b)


def _reused(rows: list[Row], blind: set[str]) -> list[Finding]:
    """K010: one `(symbol_type, symbol, venue_mic)` pointing to two ids in an effective and a
    known period they share (5.2). A null `ts_known_from` is the session open of `valid_from`:
    a pair it decides leaves K010 unchecked, unless another pair found it."""
    symbol, unknown = ("symbol_type", "symbol", "venue_mic"), False
    out: list[Finding] = []
    if any(c not in r for r in rows for c in (*symbol, "instrument_id", "valid_from")):
        blind.add(K010)
        return out
    for same in _group(rows, lambda r: tuple(r[c] for c in symbol)).values():
        for a, b in combinations(same, 2):
            tests = [_before(x.get(f"{t}_from"), y.get(f"{t}_to"))
                     for t in ("valid", "ts_known") for x, y in ((a, b), (b, a))]  # fmt: skip
            if a["instrument_id"] == b["instrument_id"] or False in tests:
                continue
            if None in tests:
                unknown = True
                continue
            msg = f"points to {a['instrument_id']} and {b['instrument_id']} in the same period"
            out.append(Finding(K010, "error", msg, key=_shown(symbol, a)))
            break
    if unknown and not out:
        blind.add(K010)
    return out


def _numbering(rows: list[Row]) -> Iterable[Finding]:
    """K011: a calendar's `session_ord`, when it has one, is 0, 1, … in session order (5.4)."""
    for calendar, sessions in _group(rows, lambda r: r.get("calendar_id")).items():
        sessions.sort(key=lambda r: (r.get("session_date") is None, r.get("session_date")))
        numbers = [r.get("session_ord") for r in sessions]
        if any(n is not None for n in numbers) and numbers != list(range(len(numbers))):
            msg = f"session_ord {numbers[:3]}… is not 0, 1, … in session_date order"
            yield Finding(K011, "error", msg, key={"calendar_id": str(calendar)})
