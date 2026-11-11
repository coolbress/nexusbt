"""The `full` level's interval checks from the rows: T003, T004, T012 (TDS 5.2, 5.18~5.20,
5.27, 6.3, 8.3).

Rules chosen with the maintainer (#225, 2026-11-11): T012 holds the three rectangle-lookup
tables to one visible row per discriminating key and edition filter, found as two rows whose
known and effective intervals both meet, then shown by `pit.rect_lookup` at the corner they
share; T003 holds the one-axis intervals, `fundamentals_state`'s known intervals per
`(edition, instrument_id, item)` and `market_rules`' tick bands per `(rule_id, venue_group)`
on a shared date. 5.2's T003 line is T012's condition and is reported as T012 only. T004 reads
every `[from, to)` pair of `INTERVALS`; a null end is open, and a row it breaks takes part in
no overlap. A null `instrument_symbols.ts_known_from` is the session open of `valid_from` (5.2):
a pair it decides leaves T012 unchecked unless another pair found it, as K010 does.
Memory holds these tables' interval columns, grouped by key; one finding per dataset and code.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable, Mapping, Sequence
from itertools import combinations
from typing import Any

import pyarrow as pa

from . import pit
from .check import TIME_CODES, Finding
from .keys import _before, _group, _shown
from .manifest import Manifest
from .refs import _rows

T003, T004, T012 = TIME_CODES
KNOWN = ("ts_known_from", "ts_known_to")
#: T004's `[from, to)` pairs, per kind.
INTERVALS = {
    "fundamentals_state": (KNOWN,),
    "classifications": (("effective_from", "effective_to"), KNOWN),
    "universe_membership": (("effective_from", "effective_to"), KNOWN),
    "instrument_symbols": (("valid_from", "valid_to"), KNOWN),
    "instrument_xref": (("valid_from", "valid_to"),),
    "market_rules": (("valid_from", "valid_to"),),
}
#: Per kind: the overlap code, the key its intervals are grouped by, and the columns read besides.
OVERLAPS = {
    "classifications": (T012, ("instrument_id", "scheme", "level"), ("edition", "pit_quality")),
    "universe_membership": (T012, ("universe_id", "instrument_id"), ()),
    "instrument_symbols": (T012, ("instrument_id", "symbol_type"), ()),
    "fundamentals_state": (T003, ("edition", "instrument_id", "item"), ()),
    "market_rules": (T003, ("rule_id", "venue_group"), ("rule_kind", "price_from", "price_to")),
}
SAID = {
    T003: "key(s) with overlapping intervals",
    T004: "row(s) with an interval end <= start",
    T012: "key(s) (per edition filter) the rectangle lookup finds more than one row for",
}


def check_times(m: Manifest, only: Sequence[str] | None, blind: set[str]) -> list[Finding]:
    """T003, T004, T012 on the checked datasets; a file they cannot read leaves them unchecked."""
    undecided: list[bool] = []
    try:
        found = [f for ds in m.datasets if only is None or ds.get("name") in only
                 for f in _dataset(m, ds, undecided)]  # fmt: skip
    except (OSError, pa.ArrowException, TypeError, ValueError):  # unreadable, or a column of
        blind.update(TIME_CODES)  # the wrong type (S010's, S002's): its rows are not compared
        return []
    if any(undecided) and all(f.code != T012 for f in found):
        blind.add(T012)
    return found


def _dataset(m: Manifest, ds: Mapping[str, Any], undecided: list[bool]) -> list[Finding]:
    kind, name = str(ds.get("kind")), str(ds.get("name"))
    if kind not in INTERVALS:
        return []
    code, key, extra = OVERLAPS.get(kind, (None, ("instrument_id", "id_type", "id_value"), ()))
    pairs = INTERVALS[kind]
    columns = list(dict.fromkeys([*key, *extra, *(c for p in pairs for c in p)]))
    rows = [dict(zip(columns, r, strict=True)) for r in _rows(m.root.resolve(), ds, columns)]
    broken = [r for r in rows if any(r[b] is not None and r[a] is not None and r[b] <= r[a]
                                     for a, b in pairs)]  # fmt: skip
    out = []
    if broken:
        msg = f"{len(broken)} {SAID[T004]}"
        out.append(Finding(T004, "error", msg, name, key=_shown(key, broken[0]),
                           count=len(broken)))  # fmt: skip
    if code is None:
        return out
    if kind == "market_rules":  # tick bands only; a null `price_from` is 0 (5.27)
        rows = [r | {"price_from": r["price_from"] or 0.0} for r in rows
                if r["rule_kind"] == "tick_band"]  # fmt: skip
        pairs = (*pairs, ("price_from", "price_to"))
    ids = {id(r) for r in broken}
    groups = _group(_filtered(kind, [r for r in rows if id(r) not in ids]),
                    lambda r: tuple(r[c] for c in (*key, "filter")))  # fmt: skip
    hits = [h for g in groups.values() if (h := _overlap(g, pairs, undecided))]
    if hits:
        a, b = hits[0]
        msg = f"{len(hits)} {SAID[code]}" + (_shown_at(a, b) if code == T012 else "")
        shown = _shown([*key, *(["filter"] if a["filter"] else [])], a)
        out.append(Finding(code, "error", msg, name, key=shown, count=len(hits)))
    return out


def _filtered(kind: str, rows: list[dict[str, Any]]) -> Iterable[dict[str, Any]]:
    """Each row under each edition filter it belongs to (5.19); other kinds have none."""
    for r in rows:
        if kind != "classifications":
            yield r | {"filter": None}
            continue
        for f, editions in pit.EDITIONS.items():
            backfilled = f == "strict" and r["pit_quality"] == "backfilled"
            if (r["edition"] or "both") in editions and not backfilled:
                yield r | {"filter": f}


def _overlap(
    rows: list[dict[str, Any]], pairs: Sequence[tuple[str, str]], undecided: list[bool]
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    """The first two rows whose intervals meet on every pair; an unknown start is undecided."""
    for a, b in combinations(rows, 2):
        tests = [_before(x[lo], y[hi]) for lo, hi in pairs for x, y in ((a, b), (b, a))]
        if False in tests:
            continue
        if None in tests:
            undecided.append(True)
            continue
        return a, b
    return None


def _shown_at(a: dict[str, Any], b: dict[str, Any]) -> str:
    """Where `pit.rect_lookup` sees both rows: the latest known start, the latest effective."""
    start = next(p[0] for p in pit.EFFECTIVE if p[0] in a)
    cutoff, date = max(a["ts_known_from"], b["ts_known_from"]), max(a[start], b[start])
    table = pa.Table.from_pylist([a, b])
    n = pit.rect_lookup(table, cutoff, date, edition=a["filter"]).num_rows
    when = cutoff.astimezone(dt.UTC).isoformat() if isinstance(cutoff, dt.datetime) else cutoff
    return f"; at known time {when} on {date}, {n} rows"
