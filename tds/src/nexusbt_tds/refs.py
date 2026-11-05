"""The `full` level's reference checks from the rows: R001~R009 (TDS 8.3).

Rules chosen with the maintainer (#224, 2026-11-05): R002 reads the `calendar_id` of
`instruments`, `calendar_segments` and tds.json `markets`; R003 reads an instrument's calendar
from `instruments.calendar_id`; R004 holds the four currency columns against ISO 4217's current
list (`ISO_4217`) and tds.json `currencies`; R006 checks only the three columns TDS 8.3 names;
R007 checks `selected_fact_id` only; R008 holds both ways; R009 matches `dictionary/columns`
`dataset` to the panel dataset's tds.json `name` (4.4), and an absent dictionary is one R009
per dataset that names it. A check whose reference table is absent, or a package with a file Parquet
cannot read, leaves its code unchecked; R007 applies only when `fundamentals_events` exists.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Sequence
from typing import Any

import pyarrow.parquet as pq

from .check import REF_CODES, Finding, Severity
from .keys import Row, _read
from .manifest import Manifest

R001, R002, R003, R004, R005, R006, R007, R008, R009 = REF_CODES
PANELS = frozenset({"feature_panels", "label_panels"})
FUNDAMENTALS = frozenset({"fundamentals_state", "fundamentals_events"})
CURRENCIES = ("currency", "settlement_currency", "quote_currency", "base_currency")  # 1.2
MICS = ("venue_mic", "operating_mic")
_MIC = re.compile(r"[A-Z0-9]{4}")  # R005, ISO 10383
#: ISO 4217 list one as SIX published it on 2026-09-17 (six-group.com, list-one.xml).
_ISO = """
AED AFN ALL AMD AOA ARS AUD AWG AZN BAM BBD BDT BHD BIF BMD BND BOB BOV BRL BSD BTN BWP BYN BZD
CAD CDF CHE CHF CHW CLF CLP CNY COP COU CRC CUP CVE CZK DJF DKK DOP DZD EGP ERN ETB EUR FJD FKP
GBP GEL GHS GIP GMD GNF GTQ GYD HKD HNL HTG HUF IDR ILS INR IQD IRR ISK JMD JOD JPY KES KGS KHR
KMF KPW KRW KWD KYD KZT LAK LBP LKR LRD LSL LYD MAD MDL MGA MKD MMK MNT MOP MRU MUR MVR MWK MXN
MXV MYR MZN NAD NGN NIO NOK NPR NZD OMR PAB PEN PGK PHP PKR PLN PYG QAR RON RSD RUB RWF SAR SBD
SCR SDG SEK SGD SHP SLE SOS SRD SSP STN SVC SYP SZL THB TJS TMT TND TOP TRY TTD TWD TZS UAH UGX
USD USN UYI UYU UYW UZS VED VES VND VUV WST XAD XAF XAG XAU XBA XBB XBC XBD XCD XCG XDR XOF XPD
XPF XPT XSU XTS XUA XXX YER ZAR ZMW ZWG
"""
ISO_4217 = frozenset(_ISO.split())


def check_refs(m: Manifest, only: Sequence[str] | None, blind: set[str]) -> list[Finding]:
    from .schemas.verify import load_schemas

    root, rows, stored = m.root.resolve(), {}, {}
    for ds in m.datasets:
        files = _read(root, ds)
        if files is None:  # a file Parquet cannot read: S010's, its rows unseen
            blind.update(REF_CODES)
            return []
        rows[str(ds.get("name"))] = (ds.get("kind"), [r for _, _, rs in files for r in rs])
        if ds.get("kind") in PANELS:  # from the footers: a file with no rows has columns too
            names = (
                c for rel, p, _ in files for c in pq.read_schema(root / rel).names if c not in p
            )
            stored[str(ds.get("name"))] = set(names)
    by_kind: defaultdict[object, list[Row]] = defaultdict(list)
    for kind, rs in rows.values():
        by_kind[kind] += rs
    present = {kind for kind, _ in rows.values()}  # a table with no rows is present, not absent
    listed = by_kind["instruments"]
    ids = {r.get("instrument_id") for r in listed} if "instruments" in present else None
    events = {r.get("event_id") for r in by_kind["corporate_actions"]}
    targets = {  # R006: TDS 8.3's three named columns and the table each points to
        "new_instrument_id": ids,
        "underlying_instrument_id": ids,
        "handled_by_event_id": events if "corporate_actions" in present else None,
    }
    facts = {r.get("fact_id") for r in by_kind["fundamentals_events"]}
    items = {r.get("item") for r in by_kind["dictionary/items"]}  # absent: every item missing
    described = {(r.get("dataset"), r.get("column")) for r in by_kind["dictionary/columns"]}
    schemas = load_schemas()
    calendar = {r.get("instrument_id"): r.get("calendar_id") for r in listed}
    sessions: defaultdict[object, set[object]] | None = None
    if "calendar_sessions" in present:
        sessions = defaultdict(set)
        for r in by_kind["calendar_sessions"]:
            sessions[r.get("calendar_id")].add(r.get("session_date"))
    own = {c.get("code") for c in _list(m.data.get("currencies")) if isinstance(c, dict)}
    markets = m.data.get("markets")
    named = [v.get("calendar_id") for v in _values(markets) if isinstance(v, dict)]
    out = _missing(R002, "calendar_id", named, sessions, blind, None) if only is None else []
    if {"delistings", "instruments"} <= present and only is None:
        out += _delisted(listed, by_kind["delistings"])
    else:  # no delistings or instruments to compare, or a check of some datasets only
        blind.add(R008)
    for name, (kind, rs) in ((n, v) for n, v in rows.items() if only is None or n in only):
        if kind != "instruments":
            found = [r.get("instrument_id") for r in rs]
            out += _missing(R001, "instrument_id", found, ids, blind, name)
        if kind in ("instruments", "calendar_segments"):
            found = [r.get("calendar_id") for r in rs]
            out += _missing(R002, "calendar_id", found, sessions, blind, name)
        dated = [r for r in rs if "instrument_id" in r and "session_date" in r]
        if dated and kind != "calendar_sessions" and (sessions is None or ids is None):
            blind.add(R003)
        elif dated and kind != "calendar_sessions" and sessions is not None:
            off = [r for r in dated if (c := calendar.get(r["instrument_id"])) in sessions
                   and r["session_date"] not in sessions[c]]  # fmt: skip
            if off:
                msg = f"{len(off)} row(s) on a day not a session of the instrument's calendar"
                key = {c: str(off[0][c]) for c in ("instrument_id", "session_date")}
                out.append(Finding(R003, "error", msg, dataset=name, key=key, count=len(off)))
        for column in CURRENCIES:
            bad = sorted({v for r in rs if isinstance(v := r.get(column), str)} - ISO_4217 - own)
            if bad:
                msg = f"{column} {', '.join(bad)} is neither ISO 4217 nor in tds.json currencies"
                out.append(Finding(R004, "error", msg, dataset=name))
        for column in MICS:
            seen = {v for r in rs if isinstance(v := r.get(column), str)}
            if bad := sorted(v for v in seen if not _MIC.fullmatch(v)):
                msg = f"{column} {', '.join(bad)} is not 4 uppercase letters or digits"
                out.append(Finding(R005, "warning", msg, dataset=name))
        for column, known in targets.items():
            out += _missing(R006, column, [r.get(column) for r in rs], known, blind, name)
        if "fundamentals_events" in present and kind == "fundamentals_state":  # 8.3: only then
            found = [r.get("selected_fact_id") for r in rs]
            out += _missing(R007, "selected_fact_id", found, facts, blind, name, "warning")
        if kind in FUNDAMENTALS:
            used = {v for r in rs if (v := r.get("item")) is not None}
            bad = sorted(used - items, key=str)
            out += _undescribed(name, "item", bad, "dictionary/items", present)
        if kind in PANELS and str(kind) in schemas:
            fixed = {c.name for c in schemas[str(kind)].columns}
            values = [c for c in stored[name] if c not in fixed and not c.startswith("x_")]
            bad = sorted(c for c in values if (name, c) not in described)
            out += _undescribed(name, "panel column", bad, "dictionary/columns", present)
    return out


def _undescribed(
    name: str, what: str, bad: list[Any], table: str, present: set[Any]
) -> list[Finding]:
    """R009, one finding per dataset; it names the dictionary when the package has none."""
    if not bad:
        return []
    shown = ", ".join(map(str, bad[:3])) + (", …" if len(bad) > 3 else "")
    why = f"not in {table}" if table in present else f"undescribed: the package has no {table}"
    msg = f"{len(bad)} {what}(s) {shown} {why}"
    return [Finding(R009, "error", msg, dataset=name, count=len(bad))]


def _delisted(listed: list[Row], exits: list[Row]) -> list[Finding]:
    """R008 both ways: an instrument in `delistings` has `delisted_on` = `exit_date`, and an
    instrument with a `delisted_on` has a row in `delistings`."""
    on = {r.get("instrument_id"): r.get("exit_date") for r in exits}
    bad = []
    for r in listed:
        i, day = r.get("instrument_id"), r.get("delisted_on")
        if (day != on[i]) if i in on else day is not None:
            bad.append(str(i))
    if not bad:
        return []
    msg = f"{len(bad)} instrument(s) whose delisted_on differs from delistings.exit_date"
    return [Finding(R008, "error", msg, key={"instrument_id": bad[0]}, count=len(bad))]


def _list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _values(value: object) -> list[Any]:
    return list(value.values()) if isinstance(value, dict) else []


def _missing(
    code: str,
    column: str,
    found: list[Any],
    known: Any,
    blind: set[str],
    name: str | None,
    severity: Severity = "error",
) -> list[Finding]:
    """`code` for the values of `column` not in `known`; unchecked when `known` is None."""
    if known is None:
        if any(v is not None for v in found):
            blind.add(code)
        return []
    bad = sorted({v for v in found if v is not None and v not in known}, key=str)
    if not bad:
        return []
    msg = f"{len(bad)} {column} value(s) not in their table, e.g. {bad[0]}"
    key = {column: str(bad[0])}
    return [Finding(code, severity, msg, dataset=name, key=key, count=len(bad))]
