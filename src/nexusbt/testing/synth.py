"""The synthetic TDS package generator (spec 4.8): the `tiny` and `small` presets.

`tiny` is a table set by hand: the holidays, listings, tickers and prices below are literals or
fixed cycles, with no random numbers. `small` follows 4.8's generation rules (1) to (3) with
`numpy.random.Generator(PCG64(seed))`, except that its prices and volumes come from integer
draws and + - x / instead of 4.8 (3)'s exp, normal and lognormal draws, so that its bytes do
not depend on the platform's math library (#128). Both write `instruments`,
`instrument_symbols`, an empty `instrument_xref`, `calendar_sessions`, `corporate_actions`
and `delistings` (both empty in `tiny`; in `small` 4.8 (4) and (6)) and dense daily `bars`
whose raw prices and cumulative factors follow the events (all 1.0 in `tiny`). The hashes in
`tds.json` and `--validate`'s check are the `tds` command's, run as a separate process: spec
2.5 draws no arrow from `testing` to `nexusbt_tds`, so this module does not import it.
"""

from __future__ import annotations

import argparse
import datetime as dt
import itertools
import json
import subprocess
import sys
import sysconfig
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal

import exchange_calendars as xc
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from nexusbt.contracts import ID_COLUMN as ID

START, END = dt.date(2020, 1, 2), dt.date(2020, 3, 31)  # the tiny period (4.8 table)
SMALL = (dt.date(2015, 1, 2), dt.date(2019, 12, 31))  # the small period
SMALL_COUNTS = {"KR": 120, "US": 180, "ZZ": 120}  # 4.8 table; ZZ takes 6 to 120
#: The tds.json `markets` entries. ZZ: a test market without a rules pack (4.8).
MARKETS = {
    "KR": {"calendar_id": "XKRX", "currency": "KRW", "timezone": "Asia/Seoul"},
    "US": {"calendar_id": "XNYS", "currency": "USD", "timezone": "America/New_York"},
    "ZZ": {"calendar_id": "XZZZ", "currency": "XTS", "timezone": "America/New_York"},
}
#: The `instruments.venue_mic` values per market, rows of `costs/venue_groups_v1.csv` (no
#: KONEX). ZZ has no row there, so its `venue_mic` is null.
VENUES = {"KR": ("XKRX", "XKOS"), "US": ("XNYS", "XNAS")}
NAMESPACES = {"KR": "synthetic KR", "US": "synthetic US", "ZZ": "synthetic test market"}
#: The period's weekday holidays, set by hand; XZZZ copies the XNYS sessions (4.8).
HOLIDAYS = {
    "XKRX": {dt.date(2020, 1, 24), dt.date(2020, 1, 27)},  # Seollal and its substitute day
    "XNYS": {dt.date(2020, 1, 20), dt.date(2020, 2, 17)},  # MLK Day, Presidents' Day
}
US_DST = dt.date(2020, 3, 8)  # US daylight saving starts: 14:30Z-21:00Z becomes 13:30Z-20:00Z
KR_CLOSE = dt.date(2016, 8, 1)  # KRX closes at 06:30Z from this day, at 06:00Z before (4.8 (1))
#: Per market 6 instruments `T00001`..`T00006`. T00002 (RENAMED) changes ticker on TICKER_CHANGE
#: and the last, listed on LATE_LISTING, takes its old ticker (symbol reuse, 4.8 (2)).
COUNT, RENAMED, TICKER_CHANGE, LATE_LISTING = 6, 2, dt.date(2020, 2, 14), dt.date(2020, 2, 18)
CYCLE = (100, 101, 102, 101)  # close = base x CYCLE[k % 4] / 100 on the k-th listed session
YEAR = 252  # sessions: small draws listings over 8 such years before its start, to its end
BP, DRIFT = 10_000, 3  # small's price steps: basis points, log drift 3 bp (4.8 (3)'s 0.0003)
PRODUCER = "nexusbt-synth"
HINTS = {
    "TDS-K011": "nexusbt-synth numbers each calendar's sessions from 0 within the preset period",
}
ROW_GROUP = 100_000
_TS = pa.timestamp("us", tz="UTC")
Table = dict[str, Any]  # column name → values, in schema order
_D, _S, _F, _I = pa.date32(), pa.string(), pa.float64(), pa.int64()
#: The TDS 5.11 `corporate_actions` columns the generator writes; the others are all null.
CA = pa.schema({
    "event_id": _S, ID: _S, "kind": _S, "ex_date": _D, "ts_effective": _TS, "record_date": _D,
    "declared_date": _D, "pay_date": _D, "pay_date_status": _S, "resolution_date": _D,
    "resolution_body": _S, "ts_announced": _TS, "ts_terms_available": _TS, "ratio_num": _I,
    "ratio_den": _I, "ratio_new_per_old": _F, "cash_per_share": _F, "currency": _S,
    "gross_or_net": _S, "price_factor": _F, "share_factor": _F, "affects": _S,
    "factor_method": _S, "factor_ref_price": _F, "revision_of": _S, "status": _S, "source": _S,
})  # fmt: skip
#: The TDS 5.13 `delistings` columns the generator writes.
DL = pa.schema({
    "delisting_id": _S, ID: _S, "last_trading_date": _D, "exit_date": _D, "ts_exit_known": _TS,
    "delist_type": _S, "ref_date": _D, "ref_price": _F, "exit_value_status": _S,
    "ret_observed": _F, "ret_observed_includes_distributions": pa.bool_(),
    "ts_value_available": _TS, "ret_policy": _F, "ret_lo": _F, "ret_hi": _F, "policy_id": _S,
    "pay_date": _D,
})  # fmt: skip
STATUS = {"revised": "effective", "cancelled": "cancelled"}  # a later version's status
#: 4.8 (6): the exit value status by a draw from 0 to 9, and the type each status gets.
EXIT = ("observed",) * 5 + ("estimated",) * 3 + ("unobserved",) * 2
EXIT_TYPE = {"observed": "acquisition_cash", "estimated": "performance", "unobserved": "unknown"}
#: 4.8 (4): each share event's yearly rate and its ratios, (new, old) shares; a bonus issue
#: of 0.29 is 129 shares for 100.
SHARE_EVENTS = {
    "split": (0.005, ((2, 1), (5, 1), (7, 1))),
    "reverse_split": (0.002, ((1, 10), (1, 3))),
    "bonus_issue": (0.001, ((129, 100), (21, 20))),
}


def _at(day: dt.date, hour: int, minute: int) -> dt.datetime:
    return dt.datetime(day.year, day.month, day.day, hour, minute, tzinfo=dt.UTC)


def _utc(value: Any) -> dt.datetime:  # a numpy datetime64[us] in UTC
    naive: dt.datetime = value.item()
    return naive.replace(tzinfo=dt.UTC)


def _sessions(calendar: str) -> list[dt.date]:
    holidays = HOLIDAYS["XNYS" if calendar == "XZZZ" else calendar]
    days = (START + dt.timedelta(n) for n in range((END - START).days + 1))
    return [d for d in days if d.weekday() < 5 and d not in holidays]


def _hours(calendar: str, day: dt.date) -> tuple[dt.datetime, dt.datetime]:
    if calendar == "XKRX":
        return _at(day, 0, 0), _at(day, 6, 30 if day >= KR_CLOSE else 0)
    shift = 1 if day >= US_DST else 0
    return _at(day, 14 - shift, 30), _at(day, 21 - shift, 0)


def _listed_on(n: int) -> dt.date:
    return LATE_LISTING if n == COUNT else START


def _ticker(market: str, n: int) -> str:
    return f"Q{market}{n:02d}"


def _columns(records: list[dict[str, Any]]) -> Table:
    return {c: [r[c] for r in records] for c in records[0]}


def _symbols(spans: Sequence[tuple[str, str, dt.date, dt.date | None]]) -> Table:
    """`instrument_symbols` rows from (instrument, ticker, valid from, valid to) spans."""
    return _columns([
        {ID: iid, "symbol_type": "ticker", "symbol": symbol, "venue_mic": None, "ts_known_to": None,
         "valid_from": day, "valid_to": end, "ts_known_from": _at(day, 0, 0), "source": PRODUCER}
        for iid, symbol, day, end in sorted(spans, key=lambda s: (s[0], s[2]))
    ])  # fmt: skip


def _instruments(
    market: str, ids: Sequence[str], mics: Sequence[str | None], listed: Sequence[dt.date],
    **more: Any,
) -> Table:  # fmt: skip
    calendar, currency = MARKETS[market]["calendar_id"], MARKETS[market]["currency"]
    return {ID: list(ids), "asset_class": ["equity"] * len(ids), "category": ["common"] * len(ids),
            "market": [market] * len(ids), "venue_mic": list(mics),
            "calendar_id": [calendar] * len(ids),
            "currency": [currency] * len(ids), "name": [f"synthetic {i}" for i in ids],
            "listed_on": list(listed), **more, "lot_size": [1.0] * len(ids),
            "multiplier": [1.0] * len(ids), "is_synthetic": [False] * len(ids)}  # fmt: skip


def _tiny(market: str) -> dict[str, Table]:
    calendar = MARKETS[market]["calendar_id"]
    ids = [(n, f"{market}:T{n:05d}") for n in range(1, COUNT + 1)]
    renamed, late = ids[RENAMED - 1][1], ids[COUNT - 1][1]
    venues = VENUES.get(market)  # by hand: odd numbers on the first MIC, even on the second
    mics = [venues[(n - 1) % 2] if venues else None for n, _ in ids]
    instruments = _instruments(market, [i for _, i in ids], mics, [_listed_on(n) for n, _ in ids])
    old, new = _ticker(market, RENAMED), _ticker(market, RENAMED * 11)
    spans: list[tuple[str, str, dt.date, dt.date | None]]
    spans = [(iid, _ticker(market, n), START, None) for n, iid in ids if iid not in (renamed, late)]
    spans += [(renamed, old, START, TICKER_CHANGE), (renamed, new, TICKER_CHANGE, None)]
    spans += [(late, old, LATE_LISTING, None)]
    days = _sessions(calendar)
    bars = []
    for n, iid in ids:
        close = None
        for k, day in enumerate(d for d in days if d >= _listed_on(n)):
            price = n * CYCLE[k % 4] * 100.0 if market == "KR" else n * CYCLE[k % 4] / 10
            open_ = price if close is None else close
            ts_open, ts_close = _hours(calendar, day)
            bars.append({
                ID: iid, "session_date": day, "ts_start": ts_open,
                "ts_end": ts_close, "open": open_, "high": max(open_, price),
                "low": min(open_, price), "close": price, "volume": 1000.0 * n,
                "obs_status": "traded", "cum_factor_split": 1.0, "cum_factor_total": 1.0,
            })  # fmt: skip
            close = price
    bars.sort(key=lambda b: (b["session_date"], b[ID]))
    return {"instruments": instruments, "instrument_symbols": _symbols(spans),
            "bars_1d": _columns(bars), "corporate_actions": CA.empty_table(),
            "delistings": DL.empty_table()}  # fmt: skip


def _tiny_calendar(calendar: str) -> Table:
    return _columns([
        {"calendar_id": calendar, "session_date": day, "ts_open": ts_open, "ts_close": ts_close,
         "session_ord": k, "is_half_day": False, "session_kind": "regular", "source": PRODUCER}
        for k, day in enumerate(_sessions(calendar))
        for ts_open, ts_close in [_hours(calendar, day)]
    ])  # fmt: skip


def _small_calendar(calendar: str, start: dt.date, end: dt.date) -> Table:
    """4.8 (1): exchange_calendars sessions; KR times fixed, US times and half days as given."""
    cal = xc.get_calendar("XNYS" if calendar == "XZZZ" else calendar, start=start, end=end)
    sched = cal.schedule.loc[str(start) : str(end)]
    days = sched.index.to_numpy().astype("datetime64[D]")
    opens = sched["open"].dt.tz_localize(None).to_numpy().astype("datetime64[us]")
    closes = sched["close"].dt.tz_localize(None).to_numpy().astype("datetime64[us]")
    half = closes - opens < np.timedelta64(390, "m")  # NYSE early closes
    if calendar == "XKRX":  # 4.8's fixed times, not the library's late opens; no half days
        late, half = days >= np.datetime64(KR_CLOSE), np.zeros(len(days), bool)
        opens = days.astype("datetime64[us]")
        closes = opens + np.where(late, 390, 360).astype("timedelta64[m]")
    return {"calendar_id": [calendar] * len(days), "session_date": days, "ts_open": opens,
            "ts_close": closes, "session_ord": np.arange(len(days)), "is_half_day": half,
            "session_kind": ["regular"] * len(days), "source": [PRODUCER] * len(days)}  # fmt: skip


def _small(market: str, n: int, sessions: Table, rng: np.random.Generator) -> dict[str, Table]:
    """4.8 (2) and (3): listings, ticker histories and dense raw bars of `n` instruments."""
    days, opens, closes = sessions["session_date"], sessions["ts_open"], sessions["ts_close"]
    first: list[int] = []  # each instrument's first and last session index in the period
    last: list[int] = []
    while len(first) < n:  # uniform listing, exponential life of mean 8 years
        listing = int(rng.integers(-8 * YEAR, len(days)))
        exit_ = listing + int(np.ceil(rng.exponential(8 * YEAR)))
        if exit_ >= 0:
            first.append(max(listing, 0))
            last.append(min(exit_, len(days) - 1))
    ids = [f"{market}:T{k:05d}" for k in range(1, n + 1)]
    gone = [j < len(days) - 1 for j in last]
    end = [days[j + 1].item() if g else None for j, g in zip(last, gone, strict=True)]
    tickers = [f"Q{market}{k:04d}" for k in range(1, n + 1)]
    spans = {k: [(ids[k], tickers[k], days[first[k]].item(), end[k])] for k in range(n)}
    long = [k for k in range(n) if last[k] - first[k] > 2]
    freed = []  # (session index the old ticker is free from, ticker)
    for k in rng.choice(long, min(len(long), max(1, round(0.01 * n))), replace=False):  # changes
        at = int(rng.integers(first[k] + 1, last[k]))
        spans[k] = [(ids[k], tickers[k], days[first[k]].item(), days[at].item()),
                    (ids[k], f"R{market}{k + 1:04d}", days[at].item(), end[k])]  # fmt: skip
        freed.append((at, tickers[k]))
    freed += [(last[k] + 1, tickers[k]) for k in range(n) if gone[k] and len(spans[k]) == 1]
    late = [k for k in rng.permutation(n) if first[k] > 0 and len(spans[k]) == 1]
    for _ in range(max(1, round(0.005 * n))):  # another id reuses an old ticker
        pair = next(((k, f) for k in late for f in freed if f[0] < first[k]), None)
        if pair is None:
            break
        k, (_, old) = pair
        spans[k] = [(ids[k], old, *spans[k][0][2:])]
        late.remove(k)
        freed = [f for f in freed if f[1] != old]
    bars: dict[str, list[Any]] = {}
    for k in range(n):  # 4.8 (3): open from the previous close, OHLC enclosed
        i, j = first[k], last[k] + 1
        # Integer draws in basis points and + - x / only: IEEE 754 rounds these the same on
        # every platform, where exp and the normal draw need not (#128). A daily step is
        # uniform on mean +- half; half = sigma x 1.732 (~sqrt 3) gives it the sd sigma, 1%..4%,
        # and mean = DRIFT + sigma^2 / 2 keeps the log return's mean near 4.8 (3)'s 0.0003.
        sigma = int(rng.integers(100, 400, endpoint=True))
        half, mean = sigma * 1732 // 1000, DRIFT + sigma * sigma // (2 * BP)
        low, high, unit = (1_000, 1_000_000, 1) if market == "KR" else (200, 50_000, 100)
        price = rng.integers(low, high, endpoint=True) / unit  # whole won, or US cents
        step = rng.integers(mean - half, mean + half, j - i, endpoint=True)
        close = price * np.multiply.accumulate((BP + step) / BP)
        gap = rng.integers(-(half // 2), half // 2, j - i, endpoint=True)  # sd ~ sigma / 2
        open_ = np.concatenate([[price], close[:-1]]) * ((BP + gap) / BP)
        wick = (BP + rng.integers(0, half // 2, (2, j - i), endpoint=True)) / BP  # >= 1
        for name, values in {
            ID: [ids[k]] * (j - i), "session_date": days[i:j], "ts_start": opens[i:j],
            "ts_end": closes[i:j], "open": open_, "high": np.maximum(open_, close) * wick[0],
            "low": np.minimum(open_, close) / wick[1], "close": close,
            "volume": rng.integers(1_000, 100_000, j - i, endpoint=True).astype(np.float64),
            "obs_status": ["traded"] * (j - i),
            "cum_factor_split": np.ones(j - i), "cum_factor_total": np.ones(j - i),
        }.items():  # fmt: skip
            bars.setdefault(name, []).append(values)
    venues = VENUES.get(market)  # drawn last, so the draws above stay as they were
    mics = rng.choice(venues, n).tolist() if venues else [None] * n
    actions = _actions(market, ids, first, last, sessions, bars, rng)  # moves `bars` too
    exits, payouts, delisted = _delistings(market, ids, first, last, sessions, bars, rng)
    instruments = _instruments(
        market, ids, mics, [days[i].item() for i in first],
        listed_on_censored=[i == 0 for i in first],
        last_session=[days[j].item() if g else None for j, g in zip(last, gone, strict=True)],
        delisted_on=delisted,
    )  # fmt: skip
    table = pa.table({c: np.concatenate(v) for c, v in bars.items()})
    order = [("session_date", "ascending"), (ID, "ascending")]
    return {"instruments": instruments, "bars_1d": table.sort_by(order),
            "instrument_symbols": _symbols([s for v in spans.values() for s in v]),
            "corporate_actions": pa.concat_tables([actions, payouts]),
            "delistings": exits}  # fmt: skip


def _terms(kind: str, term: int, ref: float, unit: int, currency: str) -> dict[str, Any]:
    """The terms of one version: `term` is a SHARE_EVENTS index, or for any other kind (a
    dividend, a liquidating return of capital) a cash amount in bp of the previous close."""
    if kind == "cash_dividend":  # whole won or cents, at least one; m = 1 - D / close[e-1]
        cash = max(1, round(ref * term / BP * unit)) / unit
        return {"cash_per_share": cash, "currency": currency, "gross_or_net": "gross",
                "price_factor": 1 - cash / ref, "share_factor": 1.0, "affects": "total_only",
                "factor_method": "cash_prev_close", "factor_ref_price": ref}  # fmt: skip
    num, den = SHARE_EVENTS[kind][1][term]
    return {"ratio_num": num, "ratio_den": den, "price_factor": den / num,
            "ratio_new_per_old": (num - den) / den if kind == "bonus_issue" else num / den,
            "share_factor": num / den, "affects": "split_and_total", "factor_method": "ratio",
            "factor_ref_price": ref}  # fmt: skip


def _actions(
    market: str, ids: Sequence[str], first: Sequence[int], last: Sequence[int],
    sessions: Table, bars: dict[str, list[Any]], rng: np.random.Generator,
) -> pa.Table:  # fmt: skip
    """4.8 (4): share events and quarterly cash dividends, ~1 % amended and ~0.5 % cancelled.

    The latest version of each event moves the raw prices and volumes in `bars` from its
    ex-date on, and its price factor the cumulative factors (TDS 5.11's A001 at c = +inf).
    """
    days, opens, closes = sessions["session_date"], sessions["ts_open"], sessions["ts_close"]
    keys, drawn, fate = _draw(first, last, rng)
    unit, currency = 1 if market == "KR" else 100, MARKETS[market]["currency"]
    rows, later = [], []
    for x, (k, e) in enumerate(keys):  # by instrument, then ex-date: close[e-1] moved already
        (kind, term), a = drawn[k, e], max(first[k], e - 10)  # announced 10 sessions before
        ref, ex, effective = float(bars["close"][k][e - first[k] - 1]), days[e].item(), opens[e]
        row = dict.fromkeys(CA.names) | {
            "event_id": f"{market}:E{x + 1:06d}", ID: ids[k], "kind": kind, "ex_date": ex,
            "ts_effective": _utc(effective), "declared_date": days[a].item(), "pay_date": ex,
            "pay_date_status": "observed", "ts_announced": _utc(closes[a]), "source": PRODUCER,
            "status": "announced" if fate.get(x) == "cancelled" else "effective",
        } | _terms(kind, term, ref, unit, currency)  # fmt: skip
        midway = _utc(closes[a] + (effective - closes[a]) // 2)  # after the first, before ex
        if kind == "cash_dividend":
            row |= _dividend(row, e, sessions, market == "KR", rng)
        rows.append(row)
        final = term
        if fate.get(x) == "revised":
            final, midway = _revise(kind, term, row["pay_date"], midway, rng)
        latest = row | _terms(kind, final, ref, unit, currency)
        terms = row["ts_terms_available"]  # a later version does not publish the amount earlier
        if x in fate:
            later.append(latest | {"revision_of": row["event_id"], "ts_announced": midway,
                                   "ts_terms_available": terms if terms and terms > midway
                                   else None, "status": STATUS[fate[x]]})  # fmt: skip
        if fate.get(x) != "cancelled":
            _move(bars, k, e - first[k], latest, kind in SHARE_EVENTS)
    for x, row in enumerate(later, len(rows) + 1):  # numbered after every first version
        row["event_id"] = f"{market}:E{x:06d}"
    return pa.Table.from_pylist(rows + later, schema=CA)


def _draw(
    first: Sequence[int], last: Sequence[int], rng: np.random.Generator
) -> tuple[list[tuple[int, int]], dict[tuple[int, int], tuple[str, int]], dict[int, str]]:
    """4.8 (4)'s events, (instrument, ex-date index) → (kind, term) in key order, and the fate
    of the amended and cancelled ones by their position."""
    live = [k for k in range(len(first)) if last[k] > first[k]]  # an ex-date needs close[e-1]
    years = sum(last[k] - first[k] + 1 for k in live) / YEAR
    drawn: dict[tuple[int, int], tuple[str, int]] = {}  # (k, ex-date index) → kind, term
    for kind, (rate, ratios) in SHARE_EVENTS.items():
        for _ in range(max(1, round(rate * years)) if live else 0):
            k = live[int(rng.integers(len(live)))]
            e = int(rng.integers(first[k] + 1, last[k], endpoint=True))
            drawn.setdefault((k, e), (kind, int(rng.integers(len(ratios)))))
    for k in rng.choice(live, round(0.3 * len(live)), replace=False).tolist():
        for e in range(first[k] + int(rng.integers(1, 63, endpoint=True)), last[k] + 1, 63):
            drawn.setdefault((k, e), ("cash_dividend", int(rng.integers(20, 150, endpoint=True))))
    keys, order = sorted(drawn), rng.permutation(len(drawn)).tolist()
    revised, cancelled = max(1, round(0.01 * len(keys))), max(1, round(0.005 * len(keys)))
    shares = [x for x in order if drawn[keys[x]][0] in SHARE_EVENTS][:1]  # a ratio amended too
    order = shares + [x for x in order if x not in shares]
    fate = dict.fromkeys(order[:revised], "revised")
    fate |= dict.fromkeys(order[revised : revised + cancelled], "cancelled")
    return keys, drawn, fate


def _dividend(
    row: Mapping[str, Any], e: int, sessions: Table, kr: bool, rng: np.random.Generator
) -> dict[str, Any]:
    """A cash dividend's dates, its late terms and `resolution_body` (4.8 (4))."""
    terms = None  # half of KR dividends publish their amount 30~60 days after ex
    if kr and rng.integers(2):
        late = dt.timedelta(int(rng.integers(30, 60, endpoint=True)))
        terms = _utc(sessions["ts_close"][e]) + late
    # #220 Decisions: a year-end dividend (ex-date in Q4) meeting 0.8 / board 0.2, any other
    # board, and 5 % of all of them null
    body = None if rng.integers(100) < 5 else "board"
    if body and row["ex_date"].month >= 10 and rng.integers(10) < 8:
        body = "meeting"
    fixed = terms.date() if terms else row["declared_date"]  # the amount's resolution
    days = sessions["session_date"]
    return {"pay_date": fixed + dt.timedelta(30),  # 5.6.11: a month after it
            "record_date": days[e + 1].item() if e + 1 < len(days) else None,
            "resolution_body": body, "ts_terms_available": terms,
            "resolution_date": fixed if body else None}  # fmt: skip


def _revise(
    kind: str, term: int, paid: dt.date, midway: dt.datetime, rng: np.random.Generator
) -> tuple[int, dt.datetime]:
    """An amendment's term and announcement: the next ratio, or 5~30 bp more, half of those
    announced a week after payment."""
    ratios = SHARE_EVENTS.get(kind, (0, ()))[1]
    if ratios:
        return (term + 1) % len(ratios), midway
    final = term + int(rng.integers(5, 30, endpoint=True))
    return final, _at(paid + dt.timedelta(7), 0, 0) if rng.integers(2) else midway


def _move(
    bars: dict[str, list[Any]], k: int, s: int, version: Mapping[str, Any], share: bool
) -> None:
    """Instrument `k`'s bars from its `s`-th on, moved by one event's factors."""
    for name in ("open", "high", "low", "close", "cum_factor_total") + (
        ("cum_factor_split",) if share else ()
    ):  # fmt: skip
        bars[name][k][s:] *= version["price_factor"]
    bars["volume"][k][s:] = np.round(bars["volume"][k][s:] * version["share_factor"])


def _delistings(
    market: str, ids: Sequence[str], first: Sequence[int], last: Sequence[int],
    sessions: Table, bars: dict[str, list[Any]], rng: np.random.Generator,
) -> tuple[pa.Table, pa.Table, list[dt.date | None]]:  # fmt: skip
    """4.8 (6): a `delistings` row for every listing that ends in the period, with 4.8 (4)'s
    liquidating distribution, ex-date between the last trading day and the exit, on ~10 %.

    Returns those rows, the distributions' `corporate_actions` rows and each `delisted_on`.
    """
    days, opens, closes = sessions["session_date"], sessions["ts_open"], sessions["ts_close"]
    gone = [k for k in range(len(ids)) if last[k] < len(days) - 1]
    room = [k for k in gone if last[k] + 2 < len(days)]  # a session for the ex-date
    count = min(len(room), max(1, round(0.1 * len(gone))))
    paid = set(rng.choice(room, count, replace=False).tolist()) if count else set()
    unit, currency = 1 if market == "KR" else 100, MARKETS[market]["currency"]
    delisted: list[dt.date | None] = [None] * len(ids)
    rows, payouts, policy_left = [], [], True  # the first unobserved row keeps ret_policy null
    for n, k in enumerate(gone, 1):
        x, ref = last[k] + (2 if k in paid else 1), float(bars["close"][k][-1])  # exit session
        status = EXIT[int(rng.integers(10))]
        ret, policy = _exit_value(status, policy_left, rng)
        policy_left = policy_left and status != "unobserved"
        known = None  # half of the observed values publish 20~90 days after the exit
        if status == "observed" and rng.integers(2):
            known = _utc(opens[x]) + dt.timedelta(int(rng.integers(20, 90, endpoint=True)))
        out: dt.date = days[x].item()
        delisted[k], told = out, max(first[k], x - 10)  # known 10 sessions before
        rows.append({
            "delisting_id": f"{market}:D{n:05d}", ID: ids[k], "exit_date": out,
            "last_trading_date": days[last[k]].item(), "ts_exit_known": _utc(closes[told]),
            "delist_type": "liquidation" if k in paid else EXIT_TYPE[status],
            "ref_date": days[last[k]].item(), "ref_price": ref, "exit_value_status": status,
            "ret_observed": ret, "ts_value_available": known, "ret_policy": policy,
            "ret_observed_includes_distributions": bool(rng.integers(2)) if k in paid else None,
            "ret_lo": -1.0, "ret_hi": 0.0, "policy_id": "exit-value-v1",
            "pay_date": out + dt.timedelta(30) if status == "observed" else None,
        })  # fmt: skip
        if k in paid:  # a return of capital of 20~80 % of the last close, ex-date the next day
            ex = days[last[k] + 1].item()
            payouts.append(dict.fromkeys(CA.names) | {
                "event_id": f"{market}:L{n:05d}", ID: ids[k], "kind": "return_of_capital",
                "ex_date": ex, "ts_effective": _utc(opens[last[k] + 1]), "pay_date": ex
                + dt.timedelta(30), "declared_date": days[told].item(), "status": "effective",
                "pay_date_status": "observed", "ts_announced": _utc(closes[told]),
                "source": PRODUCER,
            } | _terms("cash_dividend", int(rng.integers(2000, 8000, endpoint=True)), ref,
                       unit, currency))  # fmt: skip
    return (pa.Table.from_pylist(rows, schema=DL), pa.Table.from_pylist(payouts, schema=CA),
            delisted)  # fmt: skip


def _exit_value(
    status: str, policy_left: bool, rng: np.random.Generator
) -> tuple[float | None, float | None]:
    """`ret_observed` and `ret_policy`: an observed -50 %~+30 %, an estimate -50 %~0, and an
    unobserved -30 %, but null for the first, so a holding meets 5.6.13's E13."""
    if status == "observed":
        ret = int(rng.integers(-5000, 3000, endpoint=True)) / BP
        return ret, ret
    if status == "estimated":
        return None, int(rng.integers(-5000, 0, endpoint=True)) / BP
    return None, None if policy_left else -0.3


_TYPES = {
    "listed_on": pa.date32(), "session_date": pa.date32(), "valid_from": pa.date32(),
    "valid_to": pa.date32(), "last_session": pa.date32(), "delisted_on": pa.date32(),
    "ts_known_from": _TS,
    "ts_known_to": _TS, "ts_start": _TS, "ts_end": _TS, "ts_open": _TS, "ts_close": _TS,
    "session_ord": pa.int32(), "venue_mic": pa.string(), "listed_on_censored": pa.bool_(),
}  # fmt: skip
#: TDS 5.3 `instrument_xref`, written empty (4.8 (2)).
XREF = {c: pa.string() for c in (ID, "id_type", "id_value", "link_quality", "source")}
XREF |= {"valid_from": pa.date32(), "valid_to": pa.date32()}


def _arrow(table: Table | pa.Table) -> pa.Table:
    if isinstance(table, pa.Table):
        return table.cast(pa.schema([(c, _TYPES.get(c, t)) for c, t in zip(
            table.column_names, table.schema.types, strict=True)]))  # fmt: skip
    return pa.table({c: pa.array(v, _TYPES.get(c)) for c, v in table.items()})


def _write(root: Path, rel: str, name: str, table: pa.Table) -> dict[str, Any]:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    table = table.replace_schema_metadata({"tds.dataset": name, "tds.schema_version": "1.0"})
    if table.num_rows:
        pq.write_table(table, path, row_group_size=ROW_GROUP)
    else:  # no row group: an empty one has no statistics, so S003 and S006 would go unchecked
        pq.ParquetWriter(path, table.schema).close()
    return {"path": rel, "rows": table.num_rows, "bytes": path.stat().st_size}


def _tds(*args: str) -> subprocess.CompletedProcess[str]:
    """The `tds` command beside this interpreter, as its own process (a development dependency
    until T1.1a: without nexusbt-tds installed, FileNotFoundError)."""
    command = [str(Path(sysconfig.get_path("scripts")) / "tds"), *args]
    return subprocess.run(command, capture_output=True, text=True, check=False)  # noqa: S603


def make_snapshot(
    root: Path,
    *,
    preset: Literal["tiny", "small", "full", "full_ci"] = "small",
    seed: int = 0,
    snapshot_id: str = "synth-0001",
    start: dt.date | None = None,
    end: dt.date | None = None,
    markets: Sequence[str] = ("KR", "US"),
    n_kr: int | None = None,
    n_us: int | None = None,
    events: Sequence[Mapping[str, Any]] = (),
    overrides: Mapping[str, Any] | None = None,
    degrade: Sequence[str] = (),
) -> Path:
    """Write the synthetic TDS package `preset` to `root` and its hashes into `tds.json`.

    Byte-identical for the same arguments. Files are written in place and nothing in `root` is
    deleted, so a `root` used with other markets keeps their files. `tiny` is hand-set and
    takes none of `seed`, `start`, `end`, `n_kr`, `n_us`; `full`, `full_ci`, `events`,
    `overrides` and `degrade` come with later tickets (spec 10.1: T0.7, T0.8c, T0.16a).
    """
    if preset not in ("tiny", "small") or events or overrides or degrade:
        raise NotImplementedError("only presets tiny and small, without events, overrides or"
                                  " degrade, are built so far (spec 4.8)")  # fmt: skip
    root, chosen = Path(root), [m for m in MARKETS if m in markets]
    if not chosen or set(markets) - set(MARKETS):
        raise ValueError(f"markets {list(markets)}: choose one or more of {sorted(MARKETS)}")
    if preset == "tiny" and any(v is not None for v in (start, end, n_kr, n_us)):
        raise ValueError("tiny is set by hand: start, end, n_kr and n_us apply to small only")
    first, final = (start or SMALL[0], end or SMALL[1]) if preset == "small" else (START, END)
    counts = SMALL_COUNTS | {k: v for k, v in (("KR", n_kr), ("US", n_us)) if v is not None}
    # one stream per market from PCG64(seed), so a market's rows do not depend on the others
    rngs = dict(zip(MARKETS, np.random.Generator(np.random.PCG64(seed)).spawn(3), strict=True))
    calendars, tables = {}, {}
    for m in chosen:
        cal = MARKETS[m]["calendar_id"]
        if preset == "tiny":
            calendars[cal], tables[m] = _tiny_calendar(cal), _tiny(m)
        else:
            calendars[cal] = _small_calendar(cal, first, final)
            tables[m] = _small(m, counts[m], calendars[cal], rngs[m])

    def joined(name: str, key: list[str]) -> pa.Table:
        table = pa.concat_tables([_arrow(tables[m][name]) for m in chosen])
        return table.sort_by([(k, "ascending") for k in key])

    sessions = pa.concat_tables([_arrow(calendars[c]) for c in sorted(calendars)])
    files = {
        name: [_write(root, f"{name}/part-00000.parquet", name, table)]
        for name, table in (
            ("instruments", joined("instruments", [ID])),
            ("instrument_symbols", joined("instrument_symbols", [ID, "valid_from"])),
            ("instrument_xref", pa.schema(XREF).empty_table()),
            ("calendar_sessions", sessions),
            ("corporate_actions", joined("corporate_actions", [ID, "ex_date", "event_id"])),
            ("delistings", joined("delistings", [ID, "exit_date"])),
        )
    }  # fmt: skip
    files["bars_1d"] = []
    for m in chosen:
        bars = _arrow(tables[m]["bars_1d"])
        years = pa.compute.year(bars["session_date"]).to_numpy()
        for year in sorted(set(years.tolist())):
            files["bars_1d"].append(_write(
                root, f"bars/freq=1d/market={m}/year={year}/part-00000.parquet", "bars_1d",
                bars.filter(years == year)))  # fmt: skip
    bars = {"kind": "bars", "path": "bars/freq=1d", "availability": {"rule": "ts_end"}, "params":
            {"freq": "1d", "price_basis": "raw", "density": "dense", "bar_time": "session"},
            "columns": [{"name": c, "type": "ts_us"} for c in ("ts_start", "ts_end")]}  # fmt: skip
    unstated = ((ID, "id"), ("id_type", "code"), ("link_quality", "code"), ("source", "string"))
    xref = {"columns": [{"name": c, "type": t} for c, t in unstated]}  # types 5.3 leaves out
    actions = {"availability": {"effect": "ts_effective", "terms": "ts_terms_available"}}  # 6.2
    manifest = {
        "tds_version": "1.0", "name": f"synth-{preset}", "created": f"{final}T00:00:00Z",
        "snapshot_id": snapshot_id, "producer": {"name": PRODUCER, "hints": HINTS},
        "profiles": ["tds:minimal-daily@1.0", "tds:equity-daily-core@1.0"],
        "id_namespaces": {m: NAMESPACES[m] for m in chosen},
        "markets": {m: MARKETS[m] for m in chosen},
        "datasets": [
            {"name": name, "kind": name, "path": name, "schema_version": "1.0",
             **{"bars_1d": bars, "instrument_xref": xref, "corporate_actions": actions}.get(
                 name, {}), "files": entries}
            for name, entries in files.items()
        ],
        "hashes": {"hash_spec": "tds-hash-1"},
        "writer": {"name": PRODUCER, "row_group_rows": ROW_GROUP},
    }  # fmt: skip
    (root / "tds.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    done = _tds("hash", str(root), "--write")
    if done.returncode != 0:
        raise RuntimeError(f"tds hash --write {root} exited {done.returncode}: {done.stderr}")
    return root


def read(root: Path, name: str) -> pa.Table:
    """The rows of dataset `name` from the files its tds.json entry lists."""
    manifest = json.loads((Path(root) / "tds.json").read_text(encoding="utf-8"))
    (ds,) = (d for d in manifest["datasets"] if d["name"] == name)
    return pa.concat_tables([pq.read_table(Path(root) / f["path"]) for f in ds["files"]])


def a001(actions: pa.Table, bars: pa.Table) -> int:
    """TDS 5.11's A001 count: bars whose `cum_factor_*` step from the instrument's previous bar
    is not, to 1e-12 relative, the product of the price factors effective that session.

    Resolved at c = +inf: per `revision_of` chain only the version known last (5.11 step 2,
    ties to the last `event_id`), none when it is cancelled or only announced. The generator's
    own count until `tds check` runs A001 through `nexusbt_tds.actions` (#226, #227), which
    this module may not import (spec 2.5).
    """
    parent = {r["event_id"]: r["revision_of"] for r in actions.to_pylist()}
    latest: dict[str, tuple[Any, dict[str, Any]]] = {}
    for r in sorted(actions.to_pylist(), key=lambda r: r["event_id"]):
        root = r["event_id"]
        while parent[root]:
            root = parent[root]
        known = [t for t in (r["ts_announced"], r["ts_terms_available"]) if t is not None]
        when = min(known, default=r["ts_effective"])
        if root not in latest or when >= latest[root][0]:
            latest[root] = (when, r)
    want: dict[tuple[str, dt.date, str], float] = {}
    for _, r in latest.values():
        bases = {"split_and_total": ("total", "split"), "total_only": ("total",)}
        for basis in bases.get(r["affects"], ()) if r["status"] == "effective" else ():
            key = (r[ID], r["ex_date"], basis)
            want[key] = want.get(key, 1.0) * r["price_factor"]
    rows = bars.select([ID, "session_date", "cum_factor_split", "cum_factor_total"])
    rows = rows.sort_by([(ID, "ascending"), ("session_date", "ascending")]).to_pylist()
    bad = 0
    for before, now in itertools.pairwise(rows):
        for basis in ("total", "split") if before[ID] == now[ID] else ():
            step = now[f"cum_factor_{basis}"] / before[f"cum_factor_{basis}"]
            m = want.get((now[ID], now["session_date"], basis), 1.0)
            bad += abs(step - m) > 1e-12 * abs(m)
    return bad


def main(argv: Sequence[str] | None = None) -> int:
    """`python -m nexusbt.testing.synth --preset P --out DIR [--markets KR,US,ZZ] --validate`."""
    parser = argparse.ArgumentParser(prog="python -m nexusbt.testing.synth")
    parser.add_argument("--preset", choices=["tiny", "small", "full", "full_ci"], default="tiny")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--markets", default="KR,US")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--validate", action="store_true", help="then run tds check --level full")
    args = parser.parse_args(argv)
    root = make_snapshot(
        args.out, preset=args.preset, seed=args.seed, markets=args.markets.split(",")
    )
    manifest = json.loads((root / "tds.json").read_text(encoding="utf-8"))
    for ds in manifest["datasets"]:
        print(f"{ds['name']} {sum(f['rows'] for f in ds['files'])} rows")
    actions = read(root, "corporate_actions")
    status, revision = actions["status"].to_pylist(), actions["revision_of"].to_pylist()
    revised = sum(r is not None and s != "cancelled" for r, s in zip(revision, status, strict=True))
    print(f"corporate_actions revisions {revised}, cancellations {status.count('cancelled')}")
    for name in ("value_sha256", "semantic_sha256"):
        print(f"{name} {manifest['hashes'][name]}")
    if not args.validate:
        return 0
    bad = a001(actions, read(root, "bars_1d"))
    print(f"TDS-A001: {bad}")
    done = _tds("check", str(root), "--level", "full")
    sys.stdout.write(done.stdout)
    sys.stderr.write(done.stderr)
    return done.returncode or int(bad > 0)


if __name__ == "__main__":  # pragma: no cover - run by `python -m`, a separate process
    sys.exit(main())
