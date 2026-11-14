"""The `full` level's corporate-action checks from the rows: A001~A011 (TDS 5.11, 5.13, 8.3).

A001 multiplies each chain's latest version from `actions.resolve` at `c = +inf`, never a second
resolver. Where TDS leaves a rule open, the choices on #227 (2026-11-10) apply: daily bars only,
the events between an instrument's adjacent rows (no compare across a null), A004 on
`cash_prev_close` rows, A006 on four kinds, A008 and A009 on the resolver's terms time. And the
choices on #228 (2026-11-10): A010 on every row of a share-changing kind (three kinds only with
a `ratio_new_per_old`) and on any malformed ratio, compared with `share_factor` (else its
`ratio_new_per_old` rule) for split-like kinds and `ratio_new_per_old` for the rest; A011 counts
the distributions that are no older version's and not cancelled, with no upper bound on ex_date.
"""

from __future__ import annotations

import bisect
import math
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

import pyarrow as pa

from .actions import SPLIT_LIKE, ActionsError, _ts_terms, resolve
from .check import ACTION_CODES, Finding, Severity
from .keys import ranked
from .manifest import Manifest
from .refs import _rows

A001, A002, A003, A004, A005, A006, A007, A008, A009, A010, A011 = ACTION_CODES
NEEDS_NEW = frozenset({"stock_merger", "mixed_merger", "spinoff", "exchange_offer"})  # A006
#: TDS 5.11: the kinds that change the shares held (A010); `WITH_RATIO` only with a
#: `ratio_new_per_old` (a consolidation, a share exchange, an allotment ratio).
SHARE_KINDS = frozenset({"split", "reverse_split", "stock_dividend", "bonus_issue", "spinoff",
                         "stock_merger", "mixed_merger"})  # fmt: skip
WITH_RATIO = frozenset({"capital_reduction", "exchange_offer", "rights_issue"})
DISTRIBUTIONS = frozenset({"cash_dividend", "special_dividend", "return_of_capital"})  # A011
EXITS = ("delisting_id", "instrument_id", "last_trading_date",
         "ret_observed_includes_distributions")  # fmt: skip
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
            out += _ratios(str(ds.get("name")), own)
    for ds in (d for d in checked if d.get("kind") == "delistings"):
        if "corporate_actions" not in present:
            blind.add(A011)  # the distributions after the last trading day are unknown
        else:
            try:
                out += _distributions(str(ds.get("name")), rows([ds], EXITS), events)
            except TypeError:  # a date column of another type: S002's, the days not comparable
                blind.add(A011)
    daily = [d for d in checked if d.get("kind") == "bars" and _daily(d)]
    if not daily:
        return out
    by_id = {e["event_id"]: e for e in events}
    try:
        chains = resolve(pa.Table.from_pylist(ranked(events)[0]), None).chains if events else {}
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
    files = [f for f in ds.get("files") or [] if isinstance(f, dict)]  # in path order, as K002
    ordered = {**ds, "files": sorted(files, key=lambda f: str(f.get("path")))}
    for i, day, *values in _rows(root, ordered, ("instrument_id", "session_date", *FACTORS)):
        if i in last and (day is None or last[i][0] is None or day <= last[i][0]):
            continue  # out of order: K002's, never a step back
        if i not in last:
            if any(v is not None and v != 1.0 for v in values):
                bad[A002].append({"instrument_id": str(i), "session_date": str(day)})
        else:
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


def _ratios(name: str, rows: list[dict[str, Any]]) -> list[Finding]:
    """A010 over one `corporate_actions` dataset: a finding per way a ratio is wrong."""
    said = {"missing": "share event(s) without ratio_num/ratio_den",
            "one-sided": "event(s) with only one of ratio_num/ratio_den",
            "not positive": "event(s) with ratio_num or ratio_den <= 0",
            "disagrees": "event(s) whose ratio_num/ratio_den differs from the f64 ratio by more"
                         " than 1e-12 relative"}  # fmt: skip
    bad: dict[str, list[Any]] = {reason: [] for reason in said}
    for e in rows:
        num, den, kind, r = e["ratio_num"], e["ratio_den"], e["kind"], e["ratio_new_per_old"]
        if num is None and den is None:
            if kind in SHARE_KINDS or (kind in WITH_RATIO and r is not None):
                bad["missing"].append(e)
        elif num is None or den is None:
            bad["one-sided"].append(e)
        elif num <= 0 or den <= 0:
            bad["not positive"].append(e)
        elif (f := _f64_ratio(e)) is not None and not math.isclose(num / den, f, rel_tol=1e-12):
            bad["disagrees"].append(e)
    return [Finding(A010, "error", f"{len(found)} {said[reason]}", dataset=name,
                    key={"event_id": str(found[0]["event_id"])}, count=len(found))
            for reason, found in bad.items() if found]  # fmt: skip


def _f64_ratio(e: Mapping[str, Any]) -> float | None:
    """The f64 column `ratio_num/ratio_den` is the quotient of (TDS 5.11), None if null."""
    r, kind = e["ratio_new_per_old"], e["kind"]
    if kind in SPLIT_LIKE and e["share_factor"] is not None:
        return float(e["share_factor"])
    if r is None:
        return None
    return float(1 + r if kind in ("stock_dividend", "bonus_issue") else r)


def _distributions(
    name: str, exits: list[dict[str, Any]], events: list[dict[str, Any]]
) -> list[Finding]:
    """A011 over one `delistings` dataset: a null flag with a distribution after the last day."""
    revised = {e["revision_of"] for e in events}
    paid: defaultdict[Any, list[Any]] = defaultdict(list)  # instrument → its ex_dates
    for e in events:
        live = e["event_id"] not in revised and e["status"] != "cancelled"
        if live and e["kind"] in DISTRIBUTIONS and e["ex_date"] is not None:
            paid[e["instrument_id"]].append(e["ex_date"])
    bad = [x for x in exits if x["ret_observed_includes_distributions"] is None
           and x["last_trading_date"] is not None
           and any(day > x["last_trading_date"] for day in paid.get(x["instrument_id"], []))
    ]  # fmt: skip
    if not bad:
        return []
    msg = (f"{len(bad)} delisting(s) with a cash distribution after the last trading day and a"
           " null ret_observed_includes_distributions")  # fmt: skip
    key = {"delisting_id": str(bad[0]["delisting_id"])}
    return [Finding(A011, "warning", msg, dataset=name, key=key, count=len(bad))]


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
