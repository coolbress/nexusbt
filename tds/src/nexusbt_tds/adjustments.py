"""The `full` level's corporate-action checks from the rows: A001~A009 (TDS 5.11, 8.3).

A001 reads each chain's one latest version from `actions.resolve` at `c = +inf`, never a second
resolver. Rules chosen with the maintainer (#227, 2026-11-10): A001 and A002 read daily bars
(`freq` `1d`); A001 compares a row with the instrument's previous row by date, multiplying the
events with an `ex_date` after the previous row and on or before this one, so a sparse gap
spans its events, and does not compare across a null factor or a null cumulative factor; A002's
first session is the instrument's first bar. A004 compares the `cash_prev_close` rows; A006
asks `stock_merger`, `mixed_merger`, `spinoff` and `exchange_offer` for a `new_instrument_id`
and a ratio (`ratio_new_per_old` or `ratio_num/ratio_den`); A008 and A009 take the resolver's
terms time (`ts_terms_available`, else `ts_announced`, else `ts_effective`). A003~A009 look at
every row, each version of a chain included.
"""

from __future__ import annotations

import bisect
import math
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

import pyarrow as pa

from .actions import ActionsError, _ts_terms, resolve
from .check import ACTION_CODES, Finding, Severity
from .manifest import Manifest
from .refs import _rows

A001, A002, A003, A004, A005, A006, A007, A008, A009 = ACTION_CODES
NEEDS_NEW = frozenset({"stock_merger", "mixed_merger", "spinoff", "exchange_offer"})  # A006
FACTORS = ("cum_factor_split", "cum_factor_total")
#: The columns read: the resolver's and the A codes' (TDS 5.11).
COLUMNS = ("event_id", "instrument_id", "kind", "ex_date", "ts_effective", "ts_announced",
           "ts_terms_available", "ratio_num", "ratio_den", "ratio_new_per_old", "share_factor",
           "new_instrument_id", "cash_per_share", "price_factor", "affects", "factor_method",
           "factor_ref_price", "revision_of", "status")  # fmt: skip
#: Which `affects` each cumulative factor multiplies (TDS 5.11; spec 4.6: total is `≠ none`).
MULTIPLIES = {"cum_factor_split": {"split_and_total"},
              "cum_factor_total": {"split_and_total", "total_only"}}  # fmt: skip


def check_actions(
    m: Manifest, only: Sequence[str] | None, blind: set[str], notes: list[str]
) -> list[Finding]:
    """A001~A009 on the checked datasets; a file the codes cannot read leaves them unchecked."""
    try:
        return _check(m, only, blind, notes)
    except (OSError, pa.ArrowException):  # a file Parquet cannot read: S010's, its rows unseen
        blind.update(ACTION_CODES)
        return []


def _check(
    m: Manifest, only: Sequence[str] | None, blind: set[str], notes: list[str]
) -> list[Finding]:
    root = m.root.resolve()
    present = {d.get("kind") for d in m.datasets}

    def rows(sets: Iterable[Mapping[str, Any]], columns: Sequence[str]) -> list[dict[str, Any]]:
        return [dict(zip(columns, r, strict=True)) for d in sets for r in _rows(root, d, columns)]

    def kind(name: str) -> list[Mapping[str, Any]]:
        return [d for d in m.datasets if d.get("kind") == name]

    calendar = {r["instrument_id"]: r["calendar_id"]
                for r in rows(kind("instruments"), ("instrument_id", "calendar_id"))}  # fmt: skip
    days = rows(kind("calendar_sessions"), ("calendar_id", "session_date", "ts_close"))
    closes = {(r["calendar_id"], r["session_date"]): r["ts_close"] for r in days}
    out: list[Finding] = []
    checked = [d for d in m.datasets if only is None or d.get("name") in only]
    sessions = closes if {"calendar_sessions", "instruments"} <= present else None
    events: list[dict[str, Any]] = []
    for ds in (d for d in m.datasets if d.get("kind") == "corporate_actions"):
        own = rows([ds], COLUMNS)
        events += own
        if ds in checked:
            out += _rules(str(ds.get("name")), own, calendar, sessions, blind)
    daily = [d for d in checked if d.get("kind") == "bars" and _daily(d)]
    if not daily:
        return out
    by_id = {e["event_id"]: e for e in events}
    try:
        chains = resolve(pa.Table.from_pylist(events), None).chains if events else {}
    except (ActionsError, TypeError) as exc:  # a cycle (A007), a dangling `revision_of`
        blind.add(A001)
        notes.append(f"{A001} not checked: the resolver cannot tie the chains: {exc}")
        chains = None
    steps: defaultdict[Any, list[tuple[Any, str | None, float | None]]] = defaultdict(list)
    latest = [by_id[r.event_id] for r in (chains or {}).values() if r.effective and r.event_id]
    for e in sorted((e for e in latest if e["ex_date"] is not None), key=lambda e: e["ex_date"]):
        steps[e["instrument_id"]].append((e["ex_date"], e["affects"], e["price_factor"]))
    known = chains is not None and "corporate_actions" in present
    return out + [f for ds in daily for f in _factors(root, ds, steps, known, blind)]


def _daily(ds: Mapping[str, Any]) -> bool:
    return isinstance(params := ds.get("params"), dict) and params.get("freq") == "1d"


def _factors(
    root: Any, ds: Mapping[str, Any], steps: Mapping[Any, list[tuple[Any, str | None, Any]]],
    known: bool, blind: set[str],
) -> list[Finding]:  # fmt: skip
    """A001 and A002 over one daily bars dataset; `known`: the events could be resolved."""
    last: dict[Any, tuple[Any, ...]] = {}  # instrument → its previous row
    bad: dict[str, list[dict[str, str]]] = {A001: [], A002: []}
    for i, day, *values in _rows(root, ds, ("instrument_id", "session_date", *FACTORS)):
        if i not in last:
            if any(v is not None and v != 1.0 for v in values):
                bad[A002].append({"instrument_id": str(i), "session_date": str(day)})
        elif day is not None and last[i][0] is not None and day > last[i][0]:
            events = steps.get(i, [])
            span = events[bisect.bisect_right(events, last[i][0], key=lambda s: s[0]) :
                          bisect.bisect_right(events, day, key=lambda s: s[0])]  # fmt: skip
            for column, before, now in zip(FACTORS, last[i][1:], values, strict=True):
                if before is None or now is None:
                    continue
                if not known:
                    blind.add(A001)
                    continue
                want = _product(span, MULTIPLIES[column])
                if want is not None and not math.isclose(now, before * want, rel_tol=1e-12):
                    bad[A001].append({"instrument_id": str(i), "session_date": str(day)})
        last[i] = (day, *values)
    name = str(ds.get("name"))
    said = {A001: "cumulative factor ratio(s) differ from the product of the session's events",
            A002: "instrument(s) whose first cumulative factor is not 1.0"}  # fmt: skip
    return [Finding(code, "error", f"{len(keys)} {said[code]}", dataset=name, key=keys[0],
                    count=len(keys)) for code, keys in bad.items() if keys]  # fmt: skip


def _product(span: Iterable[tuple[Any, str | None, Any]], affects: set[str]) -> float | None:
    """The events' price factors this column multiplies; None if one is "none" (TDS 5.11)."""
    out = 1.0
    for _, kind, factor in span:
        if kind in affects:
            if factor is None:
                return None
            out *= factor
    return out


def _rules(
    name: str, rows: list[dict[str, Any]], calendar: Mapping[Any, Any],
    closes: Mapping[tuple[Any, Any], Any] | None, blind: set[str],
) -> list[Finding]:  # fmt: skip
    """A003~A009 over one `corporate_actions` dataset's rows; `closes` None: no calendar."""
    bad: defaultdict[str, list[Any]] = defaultdict(list)
    for e in rows:
        f, method = e["price_factor"], e["factor_method"]
        if method != "unavailable" and (f is None or f <= 0):
            bad[A003].append(e)
        cash, ref = e["cash_per_share"], e["factor_ref_price"]
        compared = method == "cash_prev_close" and None not in (f, cash, ref) and ref != 0
        if compared and not math.isclose(f, 1 - cash / ref, rel_tol=1e-9):
            bad[A004].append(e)
        session = (calendar.get(e["instrument_id"]), e["ex_date"])
        if closes is None:
            blind.update((A005, A009) if rows else ())
        elif session[0] is not None and session not in closes:
            bad[A005].append(e)
        ratio = e["ratio_new_per_old"] is not None or None not in (e["ratio_num"], e["ratio_den"])
        if e["kind"] in NEEDS_NEW and (e["new_instrument_id"] is None or not ratio):
            bad[A006].append(e)
        terms = _ts_terms(e) if e["ts_effective"] is not None else None
        if e["affects"] == "split_and_total" and terms is not None and terms > e["ts_effective"]:
            bad[A008].append(e)
        close = closes.get(session) if closes is not None else None
        if method == "spinoff_first_close" and terms is not None and close is not None:
            bad[A009] += [e] if terms < close else []
    bad[A007] = _cycles(rows)
    said = {A003: "price_factor null or <= 0 while factor_method is not unavailable",
            A004: "cash dividend factor(s) differ from 1 - cash_per_share/factor_ref_price",
            A005: "ex_date(s) not a session of the instrument's calendar",
            A006: "merger, spinoff or exchange row(s) without new_instrument_id or a ratio",
            A007: "event(s) on a revision_of cycle",
            A008: "share event(s) whose terms were published after they took effect",
            A009: "spinoff factor(s) published before the effective session's close"}  # fmt: skip
    out = []
    for code, found in sorted(bad.items()):
        if found:
            severity: Severity = "warning" if code in (A004, A008) else "error"
            key = {"event_id": str(found[0]["event_id"])}
            msg = f"{len(found)} {said[code]}"
            out.append(Finding(code, severity, msg, dataset=name, key=key, count=len(found)))
    return out


def _cycles(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The rows on a `revision_of` cycle (A007), in row order."""
    parent = {e["event_id"]: e["revision_of"] for e in rows}
    on: set[Any] = set()
    for start in parent:
        seen, node = [start], parent[start]
        while node is not None and node in parent and node not in seen:
            seen.append(node)
            node = parent[node]
        if node is not None and node in seen:
            on.update(seen[seen.index(node) :])
    return [e for e in rows if e["event_id"] in on]
