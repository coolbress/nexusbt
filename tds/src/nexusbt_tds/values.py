"""The `full` level's value checks from the rows: V001~V050 (TDS 5.1, 5.5, 5.7, 5.13, 5.15,
5.21, 5.25, 8.3).

Rules chosen with the maintainer (#227, 2026-11-10): V001 compares a bar whose open, high, low
and close are all present; V002 reads bars, and an instrument with `asset_class` `index` or
`category` `spread` may have negative prices, never a negative `volume` or `value_traded`; V010
reads the bars of `equity` instruments. V031 and V032 are not judged (follow-up issues), V011
and V012 are T0.15d's: they stay `unchecked`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pyarrow as pa

from .check import VALUE_CODES, Finding, Severity
from .manifest import Manifest
from .refs import _rows, _stored

V001, V002, V004, V005, V010, V020, V030, V040, V041, V050 = VALUE_CODES
WARNINGS = frozenset({V010, V030, V041})
PRICES = ("open", "high", "low", "close", "vwap")
#: TDS 5.1's V020: the columns each `asset_class` needs.
NEEDS = {
    "option": ("underlying_instrument_id", "strike", "option_right", "exercise_style",
               "ts_expiry", "multiplier", "settlement_type"),
    "future": ("root", "ts_expiry", "multiplier", "settlement_type"),
    **dict.fromkeys(("crypto_spot", "crypto_perp", "crypto_future"),
                    ("base_currency", "quote_currency")),
}  # fmt: skip
#: Per kind: the columns read and the codes a row breaks.
COLUMNS = {
    "bars": ("instrument_id", *PRICES, "volume", "value_traded", "obs_status"),
    "instruments": (
        "instrument_id",
        "asset_class",
        *sorted({c for v in NEEDS.values() for c in v}),
    ),
    "fx_rates": ("base", "quote", "rate"),
    "quotes": ("instrument_id", "bid_px", "ask_px"),
    "delistings": ("delisting_id", "ret_lo", "ret_hi"),
    "events": ("event_id", "instrument_id", "issuer_id", "series_id"),
}
SAID = {V001: "bar(s) whose high and low do not enclose open and close",
        V002: "bar(s) with a negative price, volume or value_traded",
        V004: "bar(s) traded with no close", V005: "FX rate(s) <= 0",
        V010: "equity bar(s) whose volume is not an integer",
        V020: "instrument(s) without a column their asset_class needs",
        V030: "locked or crossed quote(s), bid_px >= ask_px",
        V040: "delisting(s) with ret_lo > ret_hi",
        V041: "event(s) with instrument_id, issuer_id and series_id all null",
        V050: "label column(s) also in feature_panels"}  # fmt: skip


def check_values(m: Manifest, only: Sequence[str] | None, blind: set[str]) -> list[Finding]:
    """V001~V050 on the checked datasets; a file the codes cannot read leaves them unchecked."""
    try:
        return _check(m, only)
    except (OSError, pa.ArrowException, TypeError, ValueError):  # unreadable, or a column of
        # the wrong type (S010's, S002's): its rows are not compared
        blind.update(VALUE_CODES)
        return []


def _check(m: Manifest, only: Sequence[str] | None) -> list[Finding]:
    from .schemas.verify import load_schemas

    root, schemas = m.root.resolve(), load_schemas()
    listed = ("instrument_id", "asset_class", "category")
    kinds = {i: (a, c) for d in m.datasets if d.get("kind") == "instruments"
             for i, a, c in _rows(root, d, listed)}  # fmt: skip
    features = {c for d in m.datasets if d.get("kind") == "feature_panels"
                for c in _values(root, d, schemas)}  # fmt: skip
    out = []
    for ds in (d for d in m.datasets if only is None or d.get("name") in only):
        kind, bad = str(ds.get("kind")), dict[str, list[Any]]()  # code → [count, first key]
        for row in _rows(root, ds, COLUMNS[kind]) if kind in COLUMNS else ():
            for code in _broken(kind, dict(zip(COLUMNS[kind], row, strict=True)), kinds):
                bad.setdefault(code, [0, row[0]])[0] += 1
        if kind == "label_panels" and (both := sorted(_values(root, ds, schemas) & features)):
            bad[V050] = [len(both), both[0]]
        named = COLUMNS.get(kind, ("column",))[0]  # the row's id, or the label column
        for code, (n, first) in sorted(bad.items()):
            severity: Severity = "warning" if code in WARNINGS else "error"
            msg, key = f"{n} {SAID[code]}", {named: str(first)}
            out.append(Finding(code, severity, msg, str(ds.get("name")), key=key, count=n))
    return out


def _values(root: Path, ds: Mapping[str, Any], schemas: Mapping[str, Any]) -> set[str]:
    """A panel's value columns: stored, not in its schema file, not `x_`."""
    fixed = {c.name for c in schemas[str(ds.get("kind"))].columns}
    return {c for c in _stored(root, ds) if c not in fixed and not c.startswith("x_")}


def _broken(kind: str, r: dict[str, Any], kinds: Mapping[Any, tuple[Any, Any]]) -> list[str]:
    """The codes one row of `kind` breaks."""
    out = []
    if kind == "bars":
        o, h, lo, c = r["open"], r["high"], r["low"], r["close"]
        if None not in (o, h, lo, c) and not lo <= min(o, c) <= max(o, c) <= h:
            out.append(V001)
        asset, category = kinds.get(r["instrument_id"], (None, None))
        free = asset == "index" or category == "spread"
        prices = () if free else PRICES
        if any(r[k] is not None and r[k] < 0 for k in (*prices, "volume", "value_traded")):
            out.append(V002)
        if r["obs_status"] == "traded" and c is None:
            out.append(V004)
        if asset == "equity" and r["volume"] is not None and not float(r["volume"]).is_integer():
            out.append(V010)
    elif kind == "instruments":
        if any(r[k] is None for k in NEEDS.get(r["asset_class"], ())):
            out.append(V020)
    elif kind == "fx_rates":
        out += [V005] if r["rate"] is not None and r["rate"] <= 0 else []
    elif kind == "quotes":
        bid, ask = r["bid_px"], r["ask_px"]
        out += [V030] if None not in (bid, ask) and bid >= ask else []
    elif kind == "delistings":
        lo, hi = r["ret_lo"], r["ret_hi"]
        out += [V040] if None not in (lo, hi) and lo > hi else []
    elif kind == "events" and r["instrument_id"] is r["issuer_id"] is r["series_id"] is None:
        out.append(V041)
    return out
