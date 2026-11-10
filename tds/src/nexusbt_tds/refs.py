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
from collections.abc import Iterable, Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from .check import REF_CODES, Finding, Severity
from .keys import listed
from .manifest import Manifest

R001, R002, R003, R004, R005, R006, R007, R008, R009 = REF_CODES
PANELS = frozenset({"feature_panels", "label_panels"})
FUNDAMENTALS = frozenset({"fundamentals_state", "fundamentals_events"})
CURRENCIES = ("currency", "settlement_currency", "quote_currency", "base_currency")  # 1.2
MICS = ("venue_mic", "operating_mic")
TARGETS = ("new_instrument_id", "underlying_instrument_id", "handled_by_event_id")  # R006
#: The columns of a checked dataset the R codes look at.
VALUES = ("instrument_id", "calendar_id", "session_date", *CURRENCIES, *MICS, *TARGETS,
          "selected_fact_id", "item")  # fmt: skip
#: The only columns read from the tables the R codes look values up in (TDS 8.1 `--datasets`).
LOOKUPS = {
    "instruments": ("instrument_id", "calendar_id", "delisted_on"),
    "calendar_sessions": ("calendar_id", "session_date"),
    "corporate_actions": ("event_id",),
    "fundamentals_events": ("fact_id",),
    "delistings": ("instrument_id", "exit_date"),
    "dictionary/items": ("item",),
    "dictionary/columns": ("dataset", "column"),
}
BATCH_ROWS = 65_536
Batch = dict[str, list[Any]]
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


def _batches(root: Path, ds: Mapping[str, Any], columns: Sequence[str]) -> Iterator[Batch]:
    """`columns` of each listed file, `BATCH_ROWS` rows at a time, as Python lists; a column the
    file does not store takes its partition value from the path, and one in neither is left out."""
    for rel, parts in listed(root, ds):
        source = pq.ParquetFile(root / rel)
        stored = [c for c in columns if c in source.schema_arrow.names]
        for batch in source.iter_batches(batch_size=BATCH_ROWS, columns=stored):
            given = {c: [parts[c]] * batch.num_rows for c in columns if c in parts}
            yield given | {c: batch.column(c).to_pylist() for c in stored}


def _rows(root: Path, ds: Mapping[str, Any], columns: Sequence[str]) -> Iterator[tuple[Any, ...]]:
    """`columns` of each row, None where the file has the column nowhere."""
    for b in _batches(root, ds, columns):
        n = len(next(iter(b.values()), []))
        yield from zip(*(b.get(c, [None] * n) for c in columns), strict=True)


def check_refs(m: Manifest, only: Sequence[str] | None, blind: set[str]) -> list[Finding]:
    """R001~R009 reading, of the datasets checked, the columns these codes look at, and of the
    tables they point to only `LOOKUPS`' columns: memory holds a batch and the distinct values,
    not the rows (#309)."""
    try:
        return _check(m, only, blind)
    except (OSError, pa.ArrowException):  # a file Parquet cannot read: S010's, its rows unseen
        blind.update(REF_CODES)
        return []


def _check(m: Manifest, only: Sequence[str] | None, blind: set[str]) -> list[Finding]:
    from .schemas.verify import load_schemas

    root, schemas = m.root.resolve(), load_schemas()
    checked = [d for d in m.datasets if only is None or d.get("name") in only]
    present = {d.get("kind") for d in m.datasets}  # a table with no rows is present, not absent

    def lookup(kind: str) -> Iterator[tuple[Any, ...]]:
        for ds in (d for d in m.datasets if d.get("kind") == kind):
            yield from _rows(root, ds, LOOKUPS[kind])

    instruments = list(lookup("instruments"))  # (instrument_id, calendar_id, delisted_on)
    ids = {i for i, _, _ in instruments} if "instruments" in present else None
    calendar = {i: c for i, c, _ in instruments}
    events = {e for (e,) in lookup("corporate_actions")}
    targets = {  # R006: TDS 8.3's three named columns and the table each points to
        "new_instrument_id": ids,
        "underlying_instrument_id": ids,
        "handled_by_event_id": events if "corporate_actions" in present else None,
    }
    states = any(d.get("kind") == "fundamentals_state" for d in checked)
    facts = {f for (f,) in lookup("fundamentals_events")} if states else set()
    items = {i for (i,) in lookup("dictionary/items")}  # absent: every item missing
    described = set(lookup("dictionary/columns"))
    sessions: defaultdict[object, set[object]] | None = None
    if "calendar_sessions" in present:
        sessions = defaultdict(set)
        for c, day in lookup("calendar_sessions"):
            sessions[c].add(day)
    own = {c.get("code") for c in _list(m.data.get("currencies")) if isinstance(c, dict)}
    markets = m.data.get("markets")
    named = [v.get("calendar_id") for v in _values(markets) if isinstance(v, dict)]
    out = _missing(R002, "calendar_id", named, sessions, blind, None) if only is None else []
    if {"delistings", "instruments"} <= present and only is None:
        out += _delisted([(i, day) for i, _, day in instruments], lookup("delistings"))
    else:  # no delistings or instruments to compare, or a check of some datasets only
        blind.add(R008)
    for ds in checked:
        name, kind = str(ds.get("name")), ds.get("kind")
        seen: defaultdict[str, set[Any]] = defaultdict(set)  # each column's distinct values
        off, first, dated = 0, None, False
        for b in _batches(root, ds, VALUES):
            for column in b.keys() - {"session_date"}:
                seen[column].update(b[column])
            if "instrument_id" not in b or "session_date" not in b or kind == "calendar_sessions":
                continue
            dated = dated or bool(b["session_date"])
            for i, day in zip(b["instrument_id"], b["session_date"], strict=True):
                c = calendar.get(i)
                if sessions is not None and c in sessions and day not in sessions[c]:
                    off += 1
                    first = first or {"instrument_id": i, "session_date": day}
        if kind != "instruments":
            out += _missing(R001, "instrument_id", seen["instrument_id"], ids, blind, name)
        if kind in ("instruments", "calendar_segments"):
            out += _missing(R002, "calendar_id", seen["calendar_id"], sessions, blind, name)
        if dated and (sessions is None or ids is None):
            blind.add(R003)
        elif off and first is not None:
            msg = f"{off} row(s) on a day not a session of the instrument's calendar"
            key = {c: str(v) for c, v in first.items()}
            out.append(Finding(R003, "error", msg, dataset=name, key=key, count=off))
        for column in CURRENCIES:
            bad = sorted({v for v in seen[column] if isinstance(v, str)} - ISO_4217 - own)
            if bad:
                msg = f"{column} {', '.join(bad)} is neither ISO 4217 nor in tds.json currencies"
                out.append(Finding(R004, "error", msg, dataset=name))
        for column in MICS:
            strings = {v for v in seen[column] if isinstance(v, str)}
            if bad := sorted(v for v in strings if not _MIC.fullmatch(v)):
                msg = f"{column} {', '.join(bad)} is not 4 uppercase letters or digits"
                out.append(Finding(R005, "warning", msg, dataset=name))
        for column, known in targets.items():
            out += _missing(R006, column, seen[column], known, blind, name)
        if "fundamentals_events" in present and kind == "fundamentals_state":  # 8.3: only then
            found = seen["selected_fact_id"]
            out += _missing(R007, "selected_fact_id", found, facts, blind, name, "warning")
        if kind in FUNDAMENTALS:
            bad = sorted(seen["item"] - items - {None}, key=str)
            out += _undescribed(name, "item", bad, "dictionary/items", present)
        if kind in PANELS and str(kind) in schemas:
            fixed = {c.name for c in schemas[str(kind)].columns}
            stored = _stored(root, ds)  # from the footers: a file with no rows has columns too
            values = [c for c in stored if c not in fixed and not c.startswith("x_")]
            bad = sorted(c for c in values if (name, c) not in described)
            out += _undescribed(name, "panel column", bad, "dictionary/columns", present)
    return out


def _stored(root: Path, ds: Mapping[str, Any]) -> set[str]:
    """The columns the files store, partition columns aside."""
    return {c for rel, p in listed(root, ds) for c in pq.read_schema(root / rel).names
            if c not in p}  # fmt: skip


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


def _delisted(known: list[tuple[Any, Any]], exits: Iterable[tuple[Any, ...]]) -> list[Finding]:
    """R008 both ways: an instrument in `delistings` has `delisted_on` = `exit_date` (its latest,
    when it was delisted more than once), and an instrument with a `delisted_on` has a row in
    `delistings`. `known` is (instrument_id, delisted_on), `exits` (instrument_id, exit_date)."""
    on: dict[object, Any] = {}
    for i, day in exits:  # in any row order: the latest exit_date
        on[i] = day if on.get(i) is None or (day is not None and day > on[i]) else on[i]
    bad = []
    for i, day in known:
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
    found: Iterable[Any],
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
