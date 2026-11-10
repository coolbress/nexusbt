"""The `full` level's key checks from the rows: K001~K004 (TDS 3.5, 3.6), K010 (5.2), K011 (5.4).

Rules chosen with the maintainer (#224, 2026-11-05): a `year=` or `date=` folder holds the rows
whose `session_date` (`period` for the 5.25 panels) falls in it, and a kind without that column
leaves K003 unchecked; a file's time range is its `<ts_min>_<ts_max>` name (3.6), so a
`part-NNNNN` file has none. A null in a sort column sorts last, as Arrow sorts it.
"""

from __future__ import annotations

import ast
import datetime as dt
import re
from collections import defaultdict
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import replace
from itertools import combinations, groupby
from operator import itemgetter
from pathlib import Path, PurePosixPath
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from .check import KEY_CODES, Finding, _unsafe
from .hash import HashError, Record, SortedRuns, spill_folder
from .manifest import Manifest
from .profiles import meets

K001, K002, K003, K004, K010, K011 = KEY_CODES
TIME_PARTS = ("year", "date")  # the partitions that are time ranges, K003's (TDS 3.5)
PANELS = frozenset({"feature_panels", "label_panels"})
_STAMP = r"(\d{4}-\d\d-\d\dT\d\d)-(\d\d)-(\d\d)(?:-(\d{1,9}))?(Z|[+-]\d\d-\d\d)"
_RANGE = re.compile(rf"{_STAMP}_{_STAMP}\.parquet")  # 3.6, `:` and `.` written as `-`

#: The columns K010 and K011 keep as rows, of the two small tables they judge.
KEPT = {
    "instrument_symbols": ("symbol_type", "symbol", "venue_mic", "instrument_id", "valid_from",
                           "valid_to", "ts_known_from", "ts_known_to"),
    "calendar_sessions": ("calendar_id", "session_date", "session_ord"),
}  # fmt: skip
BATCH_ROWS = 65_536
Row = dict[str, Any]
Batch = dict[str, list[Any]]


def check_keys(
    m: Manifest, only: Sequence[str] | None, blind: set[str],
    tmp_dir: Path | None = None, spilled: list[Path] | None = None,
    notes: list[str] | None = None,
) -> list[Finding]:  # fmt: skip
    """K001~K011 reading, of the datasets checked, the key, sort and date columns in batches
    (#309). Memory holds a batch, the last row of each folder (K002) and, of `KEPT`'s tables,
    their columns as rows; K001's keys go in sorted runs to a temporary file (in `tmp_dir`, else
    beside the package; listed in `spilled`, removed), and when none can be made K001 alone is
    unchecked, why in `notes`. A file the codes cannot read, or one with a column name twice,
    leaves them unchecked."""
    from .schemas.verify import load_schemas

    schemas, root, out = load_schemas(), m.root.resolve(), []
    folder, spilled = spill_folder(m.root, tmp_dir), [] if spilled is None else spilled
    notes = [] if notes is None else notes
    for ds in (d for d in m.datasets if only is None or d.get("name") in only):
        kind, schema = ds.get("kind"), schemas.get(str(ds.get("kind")))
        params = ds["params"] if isinstance(ds.get("params"), dict) else {}
        key = _variant(ds.get("key", schema.key if schema else None), params)
        sort = _variant(ds.get("sort", schema.sort if schema else None), params)
        try:
            with SortedRuns(folder, spilled) as runs:
                found = _scan(root, ds, str(kind), key, sort, blind, runs, notes)
        except (OSError, pa.ArrowException):  # a file Parquet cannot read: S010's, rows unseen
            blind.update(KEY_CODES)
            continue
        out += [replace(f, dataset=ds.get("name")) for f in found]
    return out


def batches(
    root: Path, rel: str, parts: Mapping[str, str], columns: Sequence[str], size: int
) -> Iterator[tuple[int, Batch]]:
    """`columns` of the file `rel`, `size` rows at a time, as (rows, Python lists); a column the
    file does not store takes its partition value from the path, and one in neither is left out."""
    source = pq.ParquetFile(root / rel)
    names = source.schema_arrow.names
    if len(set(names)) < len(names):  # which of two `instrument_id`s? its rows unseen
        raise pa.ArrowInvalid(f"{rel}: a column name twice")
    stored = [c for c in columns if c in names]
    for batch in source.iter_batches(batch_size=size, columns=stored):
        given = {c: [parts[c]] * batch.num_rows for c in columns if c in parts}
        yield batch.num_rows, given | {c: batch.column(c).to_pylist() for c in stored}


def _scan(
    root: Path, ds: Mapping[str, Any], kind: str, key: list[str] | None,
    sort: list[str] | None, blind: set[str], runs: SortedRuns, notes: list[str],
) -> list[Finding]:  # fmt: skip
    """One pass over the files in path order, so each folder's files come in name order (3.5)."""
    date, kept = "period" if kind in PANELS else "session_date", KEPT.get(kind, ())
    files = sorted(listed(root, ds))
    unseen = {c for c, cols in ((K001, key), (K002, sort)) if cols is None}  # not judged
    pending: list[Record] = []  # K001: keys not yet in a sorted run
    last: dict[str, list[Any]] = {}  # K002, per folder: the last row's sort values
    unsorted: dict[str, tuple[int, str, Row]] = {}  # per folder: count, first file and row
    off: list[Finding] = []
    rows: list[Row] = []
    for rel, parts in files:
        folder = rel.rpartition("/")[0]
        own = tuple(sorted((p, v) for p, v in parts.items() if p not in TIME_PARTS))
        times = [(p, parts[p]) for p in TIME_PARTS if p in parts]
        wanted = dict.fromkeys([*(key or []), *(sort or []), *([date] if times else []), *kept])
        days: list[Any] = []  # K003: this file's dates outside one of its folders
        dateless = False  # a row without the date column: K003 unchecked for this file
        for n, b in batches(root, rel, parts, list(wanted), BATCH_ROWS):
            if not n:  # pragma: no cover - a row group of no rows, which pyarrow does not write
                continue
            if key is None or any(c not in b for c in key):
                unseen.add(K001)
            elif K001 not in unseen:
                columns = (_literals(b[c]) for c in key)
                pending += ((repr((*k, own)).encode(), b"", 0, b"")
                            for k in zip(*columns, strict=True))  # fmt: skip
                if len(pending) >= BATCH_ROWS:
                    _add(runs, pending, unseen, notes)
                    pending = []
            if sort is None or any(c not in b for c in sort):
                unseen.add(K002)
            else:
                ordered = zip(*([(v is None, v) for v in b[c]] for c in sort), strict=True)
                for i, now in enumerate(map(list, ordered)):  # a null sorts last
                    if folder in last and now < last[folder]:
                        seen = unsorted.get(folder) or (0, rel, {c: b[c][i] for c in sort})
                        unsorted[folder] = (seen[0] + 1, *seen[1:])
                    last[folder] = now
            dateless = dateless or (bool(times) and date not in b)
            if times and not dateless:
                days += [d for d in b[date] if isinstance(d, dt.date)
                         and any(_folder(p, d) != value for p, value in times)]  # fmt: skip
            have = [c for c in kept if c in b]  # none: n rows without them, for K010 to see
            rows += [{c: b[c][i] for c in have} for i in range(n)] if kept else []
        if dateless:
            unseen.add(K003)
            continue
        for part, value in times:
            if bad := [d for d in days if _folder(part, d) != value]:
                msg = f"{len(bad)} row(s) with {date} outside {part}={value}, e.g. {bad[0]}"
                off.append(Finding(K003, "error", msg, file=rel, count=len(bad)))
    _add(runs, pending, unseen, notes)
    blind.update(unseen)
    found = [] if K001 in unseen else list(_duplicates(runs.merged(), key or []))
    for count, rel, row in [] if K002 in unseen else unsorted.values():
        msg = f"{count} row(s) sort before the row above them by {', '.join(sort or [])}"
        found.append(Finding(K002, "error", msg, file=rel, key=_shown(list(row), row), count=count))
    found += [*off, *_overlaps([rel for rel, _ in files])]
    found += _reused(rows, blind) if kind == "instrument_symbols" else []
    found += _numbering(rows) if kind == "calendar_sessions" else []
    return found


def _add(runs: SortedRuns, pending: list[Record], unseen: set[str], notes: list[str]) -> None:
    """K001's keys as one more sorted run; with no temporary file for it, K001 is unchecked."""
    try:
        runs.add(sorted(pending, key=itemgetter(0)))
    except HashError as exc:
        unseen.add(K001)
        notes.append(f"{K001} not checked: {exc}")


def _folder(part: str, day: dt.date) -> str:
    """The `year=` or `date=` folder a day belongs in."""
    return str(day.year) if part == "year" else day.isoformat()


def listed(root: Path, ds: Mapping[str, Any]) -> Iterator[tuple[str, dict[str, str]]]:
    """Each listed file once (a second listing is M013's) that is inside the package and there
    (M012, M004), with its partition values from the path."""
    seen = set()
    files = ds.get("files")
    for entry in files if isinstance(files, list) else []:
        rel = entry.get("path") if isinstance(entry, dict) else None
        if not isinstance(rel, str) or (rel := str(PurePosixPath(rel))) in seen:
            continue
        seen.add(rel)
        if not _unsafe(root, rel) and (root / rel).is_file():
            yield rel, dict(p.split("=", 1) for p in PurePosixPath(rel).parent.parts if "=" in p)


def _variant(value: object, params: Mapping[str, Any]) -> list[str] | None:
    """A schema `key` or `sort`; bars name an intraday one (`freq<1d`, TDS 5.5) and a daily one."""
    if isinstance(value, dict):
        value = value.get("intraday" if meets(params, "freq", "<1d") else "daily")
    return value if isinstance(value, list) else None


def _shown(columns: Sequence[str], row: Row) -> dict[str, object]:
    """A row's `columns` as TDS 8.4's JSON `key`."""
    plain = (str, int, float, bool, type(None))
    return {c: row[c] if isinstance(row[c], plain) else str(row[c]) for c in columns}


_LITERAL = frozenset({str, int, float, bool, type(None)})


def _literals(values: list[Any]) -> list[Any]:
    """A column's values as Python literals, so a key's `repr` is equal for equal keys and reads
    back with `ast.literal_eval`: a date or an instant (made UTC) as (type name, text)."""

    def typed(v: Any) -> tuple[str, str]:
        v = v.astimezone(dt.UTC) if isinstance(v, dt.datetime) and v.tzinfo else v
        return type(v).__name__, str(v)

    return [v if v.__class__ in _LITERAL else typed(v) for v in values]


def _duplicates(records: Iterable[Record], key: list[str]) -> Iterable[Finding]:
    """K001: a key on two rows anywhere in the dataset, with the row's partition values other
    than `year=` and `date=` (TDS 3.5; #224, 2026-11-05). `records` come in the order of their
    `repr` bytes, so a key's rows are next to each other; the example is the first of them."""
    twice, rows, first = 0, 0, b""
    for encoded, same in groupby(records, key=itemgetter(0)):
        if (n := sum(1 for _ in same)) > 1:
            twice, rows, first = twice + 1, rows + n, first or encoded
    if twice:
        *values, own = ast.literal_eval(first.decode())
        shown = dict(zip(key, values, strict=True)) | dict(own)
        shown = {c: v[1] if isinstance(v, tuple) else v for c, v in shown.items()}
        yield Finding(K001, "error", f"{twice} key value(s) on more than one row", key=shown,
                      count=rows)  # fmt: skip


def _group(items: Iterable[Any], by: Any) -> dict[Any, list[Any]]:
    out: defaultdict[Any, list[Any]] = defaultdict(list)
    for item in items:
        out[by(item)].append(item)
    return out


def _instant(match: Sequence[str | None]) -> tuple[dt.datetime, int]:
    """One `_STAMP` of a file name as (instant to the second, nanoseconds)."""
    hour, minute, second, fraction, zone = match
    zone = "+00:00" if zone == "Z" else f"{str(zone)[:3]}:{str(zone)[4:]}"
    when = dt.datetime.fromisoformat(f"{hour}:{minute}:{second}{zone}")
    return when, int((fraction or "").ljust(9, "0"))


def _overlaps(files: list[str]) -> Iterable[Finding]:
    """K004: two `<ts_min>_<ts_max>` files of one folder whose ranges share an instant."""
    for group in _group(sorted(files), lambda rel: rel.rpartition("/")[0]).values():
        spans = []
        for rel in group:
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
