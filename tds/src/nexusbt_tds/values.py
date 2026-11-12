"""The `full` level's value checks from the rows: V001~V050 (TDS 5.1, 5.5, 5.7, 5.13, 5.15,
5.21, 5.25, 8.3).

Rules chosen with the maintainer (#227, 2026-11-10): V001 compares a bar whose open, high, low
and close are all present; V002 reads bars, and an instrument with `asset_class` `index` or
`category` `spread` may have negative prices, never a negative `volume` or `value_traded`; V010
reads the bars of `equity` instruments. V031 is `books`'s (#430); V032 is not judged (#348).

V011 (TDS 3.4; #229, 2026-11-10) reads the bars declared raw, of every instrument but an `index`:
R = value_traded / (volume * multiplier * (high + low + close) / 3) of each bar that has the five
values and a positive denominator, its median per instrument and year of `session_date`; a
dataset where no bar has an R is "volume unit unverified". It holds one partition year's R
values at a time (8 bytes a bar).

V012 (TDS 5.27; #229, 2026-11-10) reads the raw price columns once more, where the package has
grid information. The grid of an instrument on a day: the rule sets its `classifications` rows
of scheme `tick_rule_id` in effect that day name, else its fixed `tick_size`, else the rule set
of its `tick_rule_id`; of a rule set, the `tick_band` rows in effect that day, of every
`venue_group` and known time (the checker has no instrument's group and no decision time: a
price on any of them is on the grid). A price with no band is not compared.
"""

from __future__ import annotations

import math
import statistics
from array import array
from collections import defaultdict
from collections.abc import Iterator, Mapping, Sequence
from itertools import groupby
from pathlib import Path
from typing import Any

import pyarrow as pa

from .check import VALUE_CODES, Finding, Severity
from .keys import listed
from .manifest import Manifest
from .refs import _rows, _stored

V001, V002, V004, V005, V010, V011, V012, V020, V030, V040, V041, V050 = VALUE_CODES
WARNINGS = frozenset({V010, V030, V041})
PRICES = ("open", "high", "low", "close", "vwap")
RATIO = ("instrument_id", "session_date", "high", "low", "close", "volume", "value_traded")
#: TDS 5.27's raw price columns, per kind.
GRID = {"bars": PRICES[:4], "tradability_daily": ("up_limit_price", "down_limit_price")}
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


def check_values(
    m: Manifest, only: Sequence[str] | None, blind: set[str], notes: list[str]
) -> list[Finding]:
    """V001~V050 on the checked datasets; a file the codes cannot read leaves them unchecked."""
    unverified: list[str] = []
    try:
        found = _check(m, only, unverified)
    except (OSError, pa.ArrowException, TypeError, ValueError):  # unreadable, or a column of
        # the wrong type (S010's, S002's): its rows are not compared
        blind.update(VALUE_CODES)
        return []
    if unverified:
        blind.add(V011)
        notes.append(f"{V011} not checked: volume unit unverified, no raw bar with value_traded, "
                     f"volume, high, low and close in {', '.join(unverified)}")  # fmt: skip
    try:
        found += _off_grid(m, only)
    except (OSError, pa.ArrowException, TypeError, ValueError, ArithmeticError):
        blind.add(V012)  # a grid source, a date or a price of the wrong type: not compared
    return found


def _raw(ds: Mapping[str, Any]) -> bool:
    """Whether the dataset's prices are raw: `price_basis` `raw`, the default (TDS 5.5)."""
    params = ds.get("params")
    return not isinstance(params, dict) or (params.get("price_basis") or "raw") == "raw"


def _off_grid(m: Manifest, only: Sequence[str] | None) -> list[Finding]:
    """V012: the raw prices off their grid, one finding per dataset (the module's docstring)."""
    root = m.root.resolve()

    def rows(kind: str, *columns: str) -> Iterator[tuple[Any, ...]]:
        return (r for d in m.datasets if d.get("kind") == kind for r in _rows(root, d, columns))

    fixed = {i: (tick, rule) for i, tick, rule in rows(
        "instruments", "instrument_id", "tick_size", "tick_rule_id")}  # fmt: skip
    dated: defaultdict[Any, list[list[Any]]] = defaultdict(list)  # [from, to, rule id]
    for i, scheme, *assigned in rows(
        "classifications", "instrument_id", "scheme", "effective_from", "effective_to", "code"
    ):
        dated[i] += [assigned] if scheme == "tick_rule_id" else []
    bands: defaultdict[Any, list[list[Any]]] = defaultdict(list)  # [from, to, lo, hi, tick]
    for rule, kind, *band in rows("market_rules", "rule_id", "rule_kind", "valid_from",
                                  "valid_to", "price_from", "price_to", "tick_size"):  # fmt: skip
        bands[rule] += [band] if kind == "tick_band" and band[-1] and band[-1] > 0 else []

    def on(day: Any, start: Any, end: Any) -> bool:
        return bool(start <= day and (end is None or day < end))

    def grid(i: Any, day: Any) -> list[tuple[Any, Any, Any]]:
        """(price_from, price_to, tick) of the instrument on `day`, in 5.27's source order."""
        tick, rule = fixed.get(i, (None, None))
        rules = [code for start, end, code in dated.get(i, ()) if on(day, start, end)]
        if not rules and tick and tick > 0:
            return [(None, None, tick)]
        return [(lo or 0.0, hi, t) for r in rules or [rule]
                for start, end, lo, hi, t in bands.get(r, ()) if on(day, start, end)]  # fmt: skip

    def off(p: float, ticks: list[tuple[Any, Any, Any]]) -> bool:
        """5.27: `p` and the band bounds as integers of the grid's smallest tick that day find
        its bands; off when over 1e-9 relative from the nearest multiple of each band's tick."""
        unit = min(t for _, _, t in ticks)
        n = round(p / unit)
        inside = [t for lo, hi, t in ticks
                  if (lo is None or round(lo / unit) <= n)
                  and (hi is None or n < round(hi / unit))]  # fmt: skip
        return bool(inside) and all(abs(p - round(p / t) * t) > 1e-9 * abs(p) for t in inside)

    out = []
    for ds in m.datasets if any(dated.values()) or any(map(any, fixed.values())) else ():
        kind, name = str(ds.get("kind")), str(ds.get("name"))
        if kind not in GRID or not _raw(ds) or (only is not None and name not in only):
            continue
        n, first = 0, None
        for i, day, *prices in _rows(root, ds, ("instrument_id", "session_date", *GRID[kind])):
            ticks = grid(i, day) if day is not None else []
            for column, p in zip(GRID[kind], prices, strict=True) if ticks else ():
                if p is not None and math.isfinite(p) and off(p, ticks):
                    n += 1
                    first = first or {
                        "instrument_id": i,
                        "session_date": str(day),
                        "column": column,
                    }
        if n:
            msg = f"{n} raw price(s) off the price grid by more than 1e-9 relative"
            out.append(Finding(V012, "warning", msg, name, key=first, count=n))
    return out


def _volume_units(
    root: Path, ds: Mapping[str, Any], unverified: list[str], kinds: Mapping[Any, tuple[Any, ...]]
) -> list[Finding]:
    """V011 on one bars dataset, the files of one partition year at a time."""

    def year(file: tuple[str, dict[str, str]]) -> str:
        return file[1].get("year") or file[1].get("date", "")[:4]

    out, name, judged = [], str(ds.get("name")), False
    for _, files in groupby(sorted(listed(root, ds), key=year), key=year) if _raw(ds) else ():
        ratios: defaultdict[tuple[Any, Any], array[float]] = defaultdict(lambda: array("d"))
        year_ds = {**ds, "files": [{"path": rel} for rel, _ in files]}  # its kind too (#389)
        for i, day, high, low, close, volume, value in _rows(root, year_ds, RATIO):
            year_of = getattr(day, "year", None)  # a `session_date` that is no date: S002's
            asset, _, multiplier = kinds.get(i, (None, None, None))
            if None in (year_of, high, low, close, volume, value) or asset == "index":
                continue  # an index trades no quantity
            traded = volume * (multiplier or 1) * (high + low + close)  # contracts: 5.1
            if traded > 0 and math.isfinite(r := 3 * value / traded):
                ratios[i, year_of].append(r)
        for i, y in sorted(ratios, key=str):
            if not 0.5 <= (r := statistics.median(rs := ratios[i, y])) <= 2:
                out.append(Finding(V011, "warning", f"median R = {r:.6g} over {len(rs)} bar(s)",
                                   name, key={"instrument_id": i, "year": y}, count=len(rs),
                                   hint="volume may be in lots"))  # fmt: skip
        judged = judged or bool(ratios)
    unverified += [] if judged else [name]
    return out


def _check(m: Manifest, only: Sequence[str] | None, unverified: list[str]) -> list[Finding]:
    from .schemas.verify import load_schemas

    root, schemas = m.root.resolve(), load_schemas()
    listed = ("instrument_id", "asset_class", "category", "multiplier")
    kinds = {i: tuple(rest) for d in m.datasets if d.get("kind") == "instruments"
             for i, *rest in _rows(root, d, listed)}  # fmt: skip
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
        out += _volume_units(root, ds, unverified, kinds) if kind == "bars" else []
    return out


def _values(root: Path, ds: Mapping[str, Any], schemas: Mapping[str, Any]) -> set[str]:
    """A panel's value columns: stored, not in its schema file, not `x_`."""
    fixed = {c.name for c in schemas[str(ds.get("kind"))].columns}
    return {c for c in _stored(root, ds) if c not in fixed and not c.startswith("x_")}


def _broken(kind: str, r: dict[str, Any], kinds: Mapping[Any, tuple[Any, ...]]) -> list[str]:
    """The codes one row of `kind` breaks."""
    out = []
    if kind == "bars":
        o, h, lo, c = r["open"], r["high"], r["low"], r["close"]
        if None not in (o, h, lo, c) and not lo <= min(o, c) <= max(o, c) <= h:
            out.append(V001)
        asset, category = kinds.get(r["instrument_id"], (None, None))[:2]
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
