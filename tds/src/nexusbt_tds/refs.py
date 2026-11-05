"""The `full` level's reference checks from the rows: R001~R005 (TDS 8.3); R006~R009 follow.

Rules chosen with the maintainer (#224, 2026-11-05): R002 reads the `calendar_id` of
`instruments`, `calendar_segments` and tds.json `markets`; R003 reads an instrument's calendar
from `instruments.calendar_id`; R004 holds the four currency columns against ISO 4217's current
list (`ISO_4217`) and tds.json `currencies`. A check whose reference table is absent, or a
package with a file Parquet cannot read, leaves its code unchecked.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Sequence
from typing import Any

from .check import REF_CODES, Finding
from .keys import Row, _read
from .manifest import Manifest

R001, R002, R003, R004, R005 = REF_CODES
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
    root, rows = m.root.resolve(), {}
    for ds in m.datasets:
        files = _read(root, ds)
        if files is None:  # a file Parquet cannot read: S010's, its rows unseen
            blind.update(REF_CODES)
            return []
        rows[str(ds.get("name"))] = (ds.get("kind"), [r for _, _, rs in files for r in rs])
    by_kind: defaultdict[object, list[Row]] = defaultdict(list)
    for kind, rs in rows.values():
        by_kind[kind] += rs
    present = {kind for kind, _ in rows.values()}  # a table with no rows is present, not absent
    listed = by_kind["instruments"]
    ids = {r.get("instrument_id") for r in listed} if "instruments" in present else None
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
    return out


def _list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _values(value: object) -> list[Any]:
    return list(value.values()) if isinstance(value, dict) else []


def _missing(
    code: str, column: str, found: list[Any], known: Any, blind: set[str], name: str | None
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
    return [Finding(code, "error", msg, dataset=name, key={column: str(bad[0])}, count=len(bad))]
