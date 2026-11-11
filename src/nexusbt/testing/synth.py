"""The synthetic TDS package generator (spec 4.8): the `tiny`, `small` and `full` presets.

`full` is `small` over the 4.8 table's full period and instruments (the M1 datasets only,
T0.8d); a person makes it on the compute machine, CI only a few of its instruments.

`tiny` is a table set by hand: the holidays, listings, tickers and prices below are literals or
fixed cycles, with no random numbers. `small` follows 4.8's generation rules (1) to (3) with
`numpy.random.Generator(PCG64(seed))`, except that its prices and volumes come from integer
draws and + - x / instead of 4.8 (3)'s exp, normal and lognormal draws, so that its bytes do
not depend on the platform's math library (#128). Both write `instruments`,
`instrument_symbols`, an empty `instrument_xref`, `calendar_sessions`, `corporate_actions`
and `delistings` (both empty in `tiny`; in `small` 4.8 (4) and (6)) and dense daily `bars`
whose raw prices and cumulative factors follow the events (all 1.0 in `tiny`); `small` also
`tradability_daily` (4.8 (5), whose KR grid, halts and limits move its bars), `share_counts`
(4.8 (7)), `eligibility_daily` (4.8 (10)), the bars' `value_traded` and, with KR, `market_rules`
(4.8 (11a)). The hashes in
`tds.json` and `--validate`'s check are the `tds` command's, run as a separate process: spec
2.5 draws no arrow from `testing` to `nexusbt_tds`, so this module does not import it.
"""

from __future__ import annotations

import argparse
import datetime as dt
import itertools
import json
import math
import re
import subprocess
import sys
import sysconfig
import time
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, Literal, NamedTuple

import exchange_calendars as xc
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from nexusbt.contracts import ID_COLUMN as ID
from nexusbt.testing import _synth_degrade as dg
from nexusbt.testing import _synth_events as ev
from nexusbt.testing._synth_daily import (
    OHLC,
    PRODUCER,
    TICK_RULE,
    _eligibility,
    _market_rules,
    _ratios,
    _share_counts,
    _snap,
    _value_traded,
    _venues,
)
from nexusbt.testing._synth_events import _cash, _ratio, check, given, targets

START, END = dt.date(2020, 1, 2), dt.date(2020, 3, 31)  # the tiny period (4.8 table)


class Preset(NamedTuple):
    """A seeded preset of the 4.8 table: its period, instruments ever listed per market (ZZ
    takes 6 to 120), the snapshot id the command gives it and each market's mean listing
    life in years (4.8 (2))."""

    start: dt.date
    end: dt.date
    counts: dict[str, int]
    snapshot_id: str
    life: dict[str, int]


#: `full` is `small`'s rules at full scale, the M1 datasets only (T0.8d), hence its id. Its
#: lives give the table's instruments alive on a day, about KR 2,300 and US 5,700, as the
#: mean over the period: fewer on an early day, more on a late one (#334).
PRESETS = {
    "small": Preset(dt.date(2015, 1, 2), dt.date(2019, 12, 31),
                    {"KR": 120, "US": 180, "ZZ": 120}, "synth-0001",
                    {"KR": 8, "US": 8, "ZZ": 8}),
    "full": Preset(dt.date(1995, 1, 2), dt.date(2024, 12, 31),
                   {"KR": 5_500, "US": 22_100, "ZZ": 120}, "synth-full-m1-0001",
                   {"KR": 30, "US": 11, "ZZ": 8}),
}  # fmt: skip
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


#: 4.8 (5): the US day from which tradability status is known; the `tradability_daily`
#: columns known before the open.
US_STATUS = dt.date(2019, 8, 23)
LIMIT_PRICES = ("price_limit_ratio", "up_limit_price", "down_limit_price", "reference_price")
DAY_FLAGS = ("halted_full_day", "limit_up_close", "limit_down_close", "locked_up", "locked_down")
#: TDS 5.10's availability per column group: known before the open, or the day's results.
BY_COLUMN = dict.fromkeys((*LIMIT_PRICES, "admin_status"), "session_open")
BY_COLUMN |= dict.fromkeys((*DAY_FLAGS, "halt_count"), "session_close")


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


def _tiny_actions(
    market: str, ids: Sequence[str], days: Sequence[dt.date], records: list[dict[str, Any]],
    events: Sequence[Mapping[str, Any]], spans: tuple[list[int], list[int]], ended: dict[int, Any],
) -> tuple[pa.Table, pa.Table]:  # fmt: skip
    """The injected events and exits (4.8 `EventSpec`) on tiny's hand-set bars, which the
    events move as in small; tiny draws none of its own, and its prices stay off any grid."""
    held = [[r for r in records if r[ID] == iid] for iid in ids]  # each listing's bars
    first, last = spans
    found = targets(events, ids, days, first, last)
    if not found and not ended:
        return CA.empty_table(), DL.empty_table()
    hours = [_hours(MARKETS[market]["calendar_id"], d) for d in days]
    sessions = {"session_date": np.array(days, "datetime64[D]")} | {
        name: np.array([h[j].replace(tzinfo=None) for h in hours], "datetime64[us]")
        for j, name in enumerate(("ts_open", "ts_close"))}  # fmt: skip
    names = (*OHLC, "volume", "cum_factor_split", "cum_factor_total")
    bars = {c: [np.array([r[c] for r in rs]) for rs in held] for c in (*names, "session_date")}
    actions, _ = _actions(market, ids, first, last, sessions, bars, np.random.default_rng(0),
                          [None] * len(ids), found, random=False)  # fmt: skip
    for k, c in itertools.product(range(len(ids)), names):
        for r, value in zip(held[k], bars[c][k].tolist(), strict=True):
            r[c] = value
    rng = np.random.default_rng(0)  # 4.8 (6)'s draws for the columns an exit leaves out
    return actions, _delistings(market, ids, first, last, sessions, bars, rng, ended)[0]


def _tiny(market: str, events: Sequence[Mapping[str, Any]] = ()) -> dict[str, Table]:
    calendar, days = MARKETS[market]["calendar_id"], _sessions(MARKETS[market]["calendar_id"])
    ids = [(n, f"{market}:T{n:05d}") for n in range(1, COUNT + 1)]
    renamed, late = ids[RENAMED - 1][1], ids[COUNT - 1][1]
    venues = VENUES.get(market)  # by hand: odd numbers on the first MIC, even on the second
    mics = [venues[(n - 1) % 2] if venues else None for n, _ in ids]
    first, last = [days.index(_listed_on(n)) for n, _ in ids], [len(days) - 1] * COUNT
    ended = ev.exits(events, [i for _, i in ids], days, first, last)  # sets `last`
    instruments = _instruments(
        market, [i for _, i in ids], mics, [_listed_on(n) for n, _ in ids],
        last_session=[days[last[k]] if k in ended else None for k in range(COUNT)],
        delisted_on=[days[last[k] + 1] if k in ended else None for k in range(COUNT)])  # fmt: skip
    old, new = _ticker(market, RENAMED), _ticker(market, RENAMED * 11)
    spans: list[tuple[str, str, dt.date, dt.date | None]]
    spans = [(iid, _ticker(market, n), START, None) for n, iid in ids if iid not in (renamed, late)]
    spans += [(renamed, old, START, TICKER_CHANGE), (renamed, new, TICKER_CHANGE, None)]
    spans += [(late, old, LATE_LISTING, None)]
    ends = {ids[k][1]: days[last[k] + 1] for k in ended}  # a ticker ends with its listing
    spans = [(i, t, f, min(to or ends[i], ends[i]) if i in ends else to)
             for i, t, f, to in spans if f < ends.get(i, f + dt.timedelta(1))]  # fmt: skip
    bars = []
    for n, iid in ids:
        close = None
        for k, day in enumerate(days[first[n - 1] : last[n - 1] + 1]):
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
    actions, exited = _tiny_actions(market, [i for _, i in ids], days, bars, events,
                                    (first, last), ended)  # fmt: skip
    bars.sort(key=lambda b: (b["session_date"], b[ID]))
    return {"instruments": instruments, "instrument_symbols": _symbols(spans),
            "bars_1d": _columns(bars), "corporate_actions": actions,
            "delistings": exited}  # fmt: skip


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


def _listings(
    n: int, sessions: int, life: int, rng: np.random.Generator
) -> tuple[list[int], list[int]]:
    """4.8 (2): the first and last session index, in a period of `sessions`, of `n` listings
    that reach it: uniform listing from 8 years before it, exponential life of mean `life`."""
    first: list[int] = []
    last: list[int] = []
    while len(first) < n:
        listing = int(rng.integers(-8 * YEAR, sessions))
        exit_ = listing + int(np.ceil(rng.exponential(life * YEAR)))
        if exit_ >= 0:
            first.append(max(listing, 0))
            last.append(min(exit_, sessions - 1))
    return first, last


def _small(
    market: str, n: int, sessions: Table, rng: np.random.Generator,
    events: Sequence[Mapping[str, Any]] = (), life: int = 8,
) -> dict[str, Table]:  # fmt: skip
    """4.8 (2) and (3): listings, ticker histories and dense raw bars of `n` instruments."""
    days, opens, closes = sessions["session_date"], sessions["ts_open"], sessions["ts_close"]
    first, last = _listings(n, len(days), life, rng)
    ids = [f"{market}:T{k:05d}" for k in range(1, n + 1)]
    ended = ev.exits(events, ids, days, first, last)  # an injected exit sets its `last`
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
    mics = _venues(VENUES.get(market), n, bars, rng)  # drawn last: the draws above stay
    actions, moved = _actions(market, ids, first, last, sessions, bars, rng, mics,
                              targets(events, ids, days, first, last))  # fmt: skip
    status = _tradability(market, first, last, mics, moved, bars, rng,
                          (events, ids, days))  # moves `bars` too  # fmt: skip
    out, payouts, delisted = _delistings(market, ids, first, last, sessions, bars, rng, ended)
    counts, eligible = _share_counts(market, sessions, bars, rng), _eligibility(bars, status)
    bars["value_traded"] = _value_traded(bars)  # of the bars every event and halt has moved
    instruments = _instruments(
        market, ids, mics, [days[i].item() for i in first],
        listed_on_censored=[i == 0 for i in first],
        last_session=[days[j].item() if g else None for j, g in zip(last, gone, strict=True)],
        delisted_on=delisted, tick_rule_id=[TICK_RULE if market == "KR" else None] * n,
    )  # fmt: skip
    order = [("session_date", "ascending"), (ID, "ascending")]
    table, status, eligible = (
        pa.table(
            {
                c: pa.array(np.concatenate(v), from_pandas=True)  # NaN → null
                for c, v in t.items()
            }
        ).sort_by(order)
        for t in (bars, status, eligible)
    )
    return {"instruments": instruments, "bars_1d": table, "tradability_daily": status,
            "instrument_symbols": _symbols([s for v in spans.values() for s in v]),
            "corporate_actions": pa.concat_tables([actions, payouts]),
            "delistings": out, "eligibility_daily": eligible,
            "share_counts": counts}  # fmt: skip


def _terms(kind: str, term: int, ref: float, unit: int, currency: str) -> dict[str, Any]:
    """The terms of one version: `term` is a SHARE_EVENTS index, or for any other kind (a
    dividend, a liquidating return of capital) a cash amount in bp of the previous close."""
    if kind == "cash_dividend":  # whole won or cents, at least one
        return _cash(max(1, round(ref * term / BP * unit)) / unit, ref, currency)
    return _ratio(kind, *SHARE_EVENTS[kind][1][term], ref)


def _actions(
    market: str, ids: Sequence[str], first: Sequence[int], last: Sequence[int],
    sessions: Table, bars: dict[str, list[Any]], rng: np.random.Generator,
    mics: Sequence[str | None], injected: Mapping[Key, Mapping[str, Any]], random: bool = True,
) -> tuple[pa.Table, list[tuple[int, int, str]]]:  # fmt: skip
    """4.8 (4): share events and quarterly cash dividends, ~1 % amended and ~0.5 % cancelled,
    besides the `injected` ones (`EventSpec`); only those without `random` (tiny).

    The latest version of each event moves the raw prices (onto the KR grid again) and volumes
    in `bars` from its ex-date on, and its price factor the cumulative factors (TDS 5.11's A001
    at c = +inf). Returns the rows and each moving event's (instrument, ex-date index, kind).
    """
    moved = []
    days, opens, closes = sessions["session_date"], sessions["ts_open"], sessions["ts_close"]
    keys, drawn, fate = _draw(first, last, rng, set(injected)) if random else ([], {}, {})
    unit, currency = 1 if market == "KR" else 100, MARKETS[market]["currency"]
    rows, later = [], []
    for x, (k, e) in enumerate(sorted([*keys, *injected])):  # close[e-1] moved already
        spec, fated = injected.get((k, e)), fate.get((k, e))
        kind, term = (spec["kind"], 0) if spec else drawn[k, e]
        a = max(first[k], e - 10)  # announced 10 sessions before
        ref, ex, effective = float(bars["close"][k][e - first[k] - 1]), days[e].item(), opens[e]
        row = dict.fromkeys(CA.names) | {
            "event_id": f"{market}:E{x + 1:06d}", ID: ids[k], "kind": kind, "ex_date": ex,
            "ts_effective": _utc(effective), "declared_date": days[a].item(), "pay_date": ex,
            "pay_date_status": "observed", "ts_announced": _utc(closes[a]), "source": PRODUCER,
            "status": "announced" if fated == "cancelled" else "effective",
        }  # fmt: skip
        midway = _utc(closes[a] + (effective - closes[a]) // 2)  # after the first, before ex
        if spec:
            record = days[e + 1].item() if e + 1 < len(days) else None
            row |= given(spec, ref, currency, record, row["declared_date"], CA)
        else:
            row |= _terms(kind, term, ref, unit, currency)
        if kind == "cash_dividend" and not spec:
            row |= _dividend(row, e, sessions, market == "KR", rng)
        rows.append(row)
        latest = row
        if fated == "revised":
            final, midway = _revise(kind, term, row["pay_date"], midway, rng)
            latest = row | _terms(kind, final, ref, unit, currency)
        terms = row["ts_terms_available"]  # a later version does not publish the amount earlier
        if fated:
            later.append(latest | {"revision_of": row["event_id"], "ts_announced": midway,
                                   "ts_terms_available": terms if terms and terms > midway
                                   else None, "status": STATUS[fated]})  # fmt: skip
        if fated != "cancelled":
            _move(bars, k, e - first[k], latest, kind in SHARE_EVENTS, mics[k])
            moved.append((k, e, kind))
    for x, row in enumerate(later, len(rows) + 1):  # numbered after every first version
        row["event_id"] = f"{market}:E{x:06d}"
    return pa.Table.from_pylist(rows + later, schema=CA), moved


Key = tuple[int, int]  # (instrument, ex-date session index)


def _draw(
    first: Sequence[int], last: Sequence[int], rng: np.random.Generator, skip: set[Key]
) -> tuple[list[Key], dict[Key, tuple[str, int]], dict[Key, str]]:
    """4.8 (4)'s events, (instrument, ex-date index) → (kind, term) in key order, none on a
    `skip` day (an injected event's), and the fate of the amended and cancelled ones."""
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
    for key in skip:  # spec 4.8: no random event on an injected event's day (that instrument)
        drawn.pop(key, None)
    keys, order = sorted(drawn), rng.permutation(len(drawn)).tolist()
    revised, cancelled = max(1, round(0.01 * len(keys))), max(1, round(0.005 * len(keys)))
    shares = [x for x in order if drawn[keys[x]][0] in SHARE_EVENTS][:1]  # a ratio amended too
    order = shares + [x for x in order if x not in shares]
    fate = {keys[x]: "revised" for x in order[:revised]}
    fate |= {keys[x]: "cancelled" for x in order[revised : revised + cancelled]}
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
    bars: dict[str, list[Any]], k: int, s: int, version: Mapping[str, Any], share: bool,
    venue: str | None,
) -> None:  # fmt: skip
    """Instrument `k`'s bars from its `s`-th on, moved by one event's factors; an event
    without a factor (`unavailable`) leaves them, and A001 does not compare its session."""
    if version["price_factor"] is None:
        return
    for name in ("open", "high", "low", "close", "cum_factor_total") + (
        ("cum_factor_split",) if share else ()
    ):  # fmt: skip
        bars[name][k][s:] *= version["price_factor"]
        if name in OHLC:
            bars[name][k][s:] = _snap(bars[name][k][s:], bars["session_date"][k][s:], venue)
    bars["volume"][k][s:] = np.round(bars["volume"][k][s:] * version["share_factor"])


Days = set[tuple[int, int]]  # (instrument, session index) pairs
Hits = dict[tuple[int, int], tuple[bool, bool]]  # a limit close: (at the upper limit, locked)


def _last_traded(close: np.ndarray) -> list[int | None]:
    """For each session after the first, the index of the last one before it with a close."""
    out: list[int | None] = []
    for s in range(1, len(close)):
        out.append(s - 1 if not np.isnan(close[s - 1]) else out[-1] if out else None)
    return out


def _tradability(
    market: str, first: Sequence[int], last: Sequence[int], mics: Sequence[str | None],
    moved: Sequence[tuple[int, int, str]], bars: dict[str, list[Any]], rng: np.random.Generator,
    injected: tuple[Sequence[Mapping[str, Any]], Sequence[str], Any],
) -> dict[str, list[Any]]:  # fmt: skip
    """4.8 (5): KR halts (and those `injected`: events, ids, days), limit closes and 1-ULP
    wobbles moved into `bars`, ~1 % of KR instruments `administrative` over their last 60
    sessions, and a `tradability_daily` row per bar, none moving a close a factor or exit uses."""
    n, held = len(first), ev.halts(*injected, first, last, moved)
    refs = {(k, e - 1) for k, e, _ in moved} | {(k, last[k]) for k in range(n)}
    halted: Days = set()
    hits: Hits = {}
    admin: Days = set()
    if market == "KR":
        halted = _halts(first, last, moved, refs | held, bars, rng, held)
        busy = refs | halted | {(k, e) for k, e, _ in moved} | {(k, d + 1) for k, d in halted}
        settled = [max([e for j, e, _ in moved if j == k], default=first[k]) for k in range(n)]
        hits = _limits(first, last, mics, settled, busy, bars, rng)
        _wobble(first, last, busy | set(hits), bars, rng)
        for k in rng.choice(n, max(1, round(0.01 * n)), replace=False).tolist():
            admin |= {(k, d) for d in range(max(first[k], last[k] - 59), last[k] + 1)}
    out: dict[str, list[Any]] = {}
    for k in range(n):
        rows = _status(market, k, first[k], mics[k], bars, halted, hits, admin)
        for name, values in rows.items():
            out.setdefault(name, []).append(values)
    return out


def _sample(
    first: Sequence[int], last: Sequence[int], rate: float, rng: np.random.Generator,
    take: Callable[[int, int], int],
) -> None:  # fmt: skip
    """Offers `take` random (instrument, session index after its first) pairs until it has
    taken `rate` of the bars, or ten offers per wanted bar have been made."""
    live = [k for k in range(len(first)) if last[k] > first[k]]
    want, taken = round(rate * sum(j - i + 1 for i, j in zip(first, last, strict=True))), 0
    for _ in range(10 * want if live else 0):
        if taken >= want:
            break
        k = live[int(rng.integers(len(live)))]
        taken += take(k, int(rng.integers(first[k] + 1, last[k], endpoint=True)))


def _halts(
    first: Sequence[int], last: Sequence[int], moved: Sequence[tuple[int, int, str]],
    refs: Days, bars: dict[str, list[Any]], rng: np.random.Generator, held: Days,
) -> Days:  # fmt: skip
    """~0.1 % of KR sessions halted all day, in spans of 1~5 sessions, and at least one span
    from a split's ex-date and one from a cash dividend's (spec G-54's two cases), and `held`."""
    halted: Days = set(held)

    def halt(k: int, start: int) -> int:  # 1~5 sessions, unless a close in `refs` would go
        end = min(start + int(rng.integers(1, 5, endpoint=True)), last[k])
        span = {(k, d) for d in range(start, end)}
        if span & refs:
            return 0
        halted.update(span)
        return len(span)

    for kind in ("split", "cash_dividend"):  # the first ex-date of that kind that can take one
        for k, e, x in moved:
            if x == kind and halt(k, e):
                break
    _sample(first, last, 0.001, rng, halt)
    for k, d in halted:
        for name in OHLC:
            bars[name][k][d - first[k]] = np.nan
        bars["volume"][k][d - first[k]], bars["obs_status"][k][d - first[k]] = 0.0, "halted"
    return halted


def _limits(
    first: Sequence[int], last: Sequence[int], mics: Sequence[str | None],
    settled: Sequence[int], busy: Days, bars: dict[str, list[Any]], rng: np.random.Generator,
) -> Hits:  # fmt: skip
    """~0.2 % of KR sessions close at the upper or the lower limit (by half), a quarter of them
    locked there all day: the last close x (1 +- that day's ratio), snapped inward. The bars
    after it move by the same ratio, so the next day trades within its own limits; so a limit
    falls only after an instrument's last ex-date (`settled`), whose factors it would move, and
    only on a day with a limit (`kr_price_limits_v1` starts on 1995-04-01)."""
    hits: Hits = {}

    def pick(k: int, d: int) -> int:  # not next to another limit, which would move its close
        if d <= settled[k] or (k, d) in busy or {(k, d - 1), (k, d), (k, d + 1)} & hits.keys():
            return 0
        day = bars["session_date"][k][d - first[k] : d - first[k] + 1]
        if np.isnan(_ratios(day, mics[k])[0]):  # no limit that day to close at
            return 0
        hits[k, d] = (bool(rng.integers(2)), bool(rng.integers(4) == 0))
        return 1

    _sample(first, last, 0.002, rng, pick)
    for (k, d), (up, locked) in sorted(hits.items()):  # by date: a later one reads the moved
        s, dates = d - first[k], bars["session_date"][k]
        day = dates[s : s + 1]  # the reference is the last close: no halt or event before
        limits = _limit_prices(bars["close"][k][s - 1 : s], _ratios(day, mics[k]), day, mics[k])
        price = limits[0 if up else 1][0]
        moved = price / bars["close"][k][s]
        for name in OHLC:
            bars[name][k][s + 1 :] = _snap(bars[name][k][s + 1 :] * moved, dates[s + 1 :], mics[k])
            bars[name][k][s] = price if locked or name == "close" else bars[name][k][s]
        bars["high"][k][s] = max(bars["high"][k][s], price)
        bars["low"][k][s] = min(bars["low"][k][s], price)
    return hits


def _limit_prices(
    ref: np.ndarray, ratio: np.ndarray, dates: np.ndarray, venue: str | None
) -> tuple[np.ndarray, np.ndarray]:
    """TDS 5.10's `up/down_limit_price`: `ref x (1 +- ratio)` with the upper limit rounded down
    and the lower up to the grid (4.8 (5)); first to 1e-6, so a float error just past a tick
    (10,000 x 0.7) does not move it a tick. NaN stays NaN; off KR, nothing is rounded."""
    up = _snap(np.round(ref * (1 + ratio), 6), dates, venue, np.floor)
    return up, _snap(np.round(ref * (1 - ratio), 6), dates, venue, np.ceil)


def _wobble(
    first: Sequence[int], last: Sequence[int], busy: Days, bars: dict[str, list[Any]],
    rng: np.random.Generator,
) -> None:  # fmt: skip
    """~0.1 % of KR closes strictly inside their bar moved up by one ULP, off the grid."""

    def nudge(k: int, d: int) -> int:
        s, close = d - first[k], bars["close"][k][d - first[k]]
        if (k, d) in busy or not bars["low"][k][s] < close < bars["high"][k][s]:
            return 0
        bars["close"][k][s] = np.nextafter(close, np.inf)
        busy.add((k, d))
        return 1

    _sample(first, last, 0.001, rng, nudge)


def _status(
    market: str, k: int, i: int, venue: str | None, bars: dict[str, list[Any]], halted: Days,
    hits: Hits, admin: Days,
) -> dict[str, Any]:  # fmt: skip
    """Instrument `k`'s `tradability_daily` rows; `i` is its first session index."""
    dates, close, split = bars["session_date"][k], bars["close"][k], bars["cum_factor_split"][k]
    ref = np.full(len(dates), np.nan)  # the last close before, over halts, moved by the share
    for s, p in enumerate(_last_traded(close), 1):  # events since (an ex-date's base price)
        ref[s] = np.nan if p is None else close[p] * (split[s] / split[p])
    kr, ratio = market == "KR", _ratios(dates, venue)
    up, down = _limit_prices(ref, ratio, dates, venue)
    known = dates >= np.datetime64(US_STATUS) if market == "US" else np.ones(len(dates), bool)
    days = [(k, d) for d in range(i, i + len(dates))]
    hit = [hits.get(x) for x in days]
    none = [None] * len(days)

    def if_known(values: Sequence[object]) -> list[object]:
        return [v if ok else None for v, ok in zip(values, known, strict=True)]

    return {
        ID: bars[ID][k], "session_date": dates, "status_known": known,
        "halted_full_day": if_known([x in halted for x in days]),
        "halt_count": if_known([0] * len(days)),  # a full-day halt is not an intraday one
        "limit_up_close": [bool(h and h[0]) for h in hit] if kr else none,
        "limit_down_close": [bool(h and not h[0]) for h in hit] if kr else none,
        "locked_up": [bool(h and h[0] and h[1]) for h in hit] if kr else none,
        "locked_down": [bool(h and not h[0] and h[1]) for h in hit] if kr else none,
        "price_limit_ratio": ratio, "up_limit_price": up, "down_limit_price": down,
        "reference_price": ref if kr else ratio * np.nan,
        "admin_status": [("administrative" if x in admin else "normal") if kr else None
                         for x in days],
        "source": [PRODUCER] * len(days),
    }  # fmt: skip


def _delistings(
    market: str, ids: Sequence[str], first: Sequence[int], last: Sequence[int],
    sessions: Table, bars: dict[str, list[Any]], rng: np.random.Generator,
    injected: Mapping[int, Mapping[str, Any]],
) -> tuple[pa.Table, pa.Table, list[dt.date | None]]:  # fmt: skip
    """4.8 (6): a `delistings` row for every listing that ends in the period, with 4.8 (4)'s
    liquidating distribution on ~10 % of those not `injected` (whose columns replace drawn ones).

    Returns those rows, the distributions' `corporate_actions` rows and each `delisted_on`.
    """
    days, opens, closes = sessions["session_date"], sessions["ts_open"], sessions["ts_close"]
    gone = [k for k in range(len(ids)) if last[k] < len(days) - 1]
    room = [k for k in gone if last[k] + 2 < len(days) and k not in injected]  # for the ex-date
    count = min(len(room), max(1, round(0.1 * len(gone))))
    paid = set(rng.choice(room, count, replace=False).tolist()) if count else set()
    unit, currency = 1 if market == "KR" else 100, MARKETS[market]["currency"]
    delisted: list[dt.date | None] = [None] * len(ids)
    rows, payouts, policy_left = [], [], True  # the first unobserved row keeps ret_policy null
    for n, k in enumerate(gone, 1):
        x, ref = last[k] + (2 if k in paid else 1), float(bars["close"][k][-1])  # exit session
        spec = injected.get(k, {})
        status = spec.get("exit_value_status") or EXIT[int(rng.integers(10))]
        ret, policy = ev.exit_value(status, policy_left, rng)
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
        } | ev.columns(spec, DL))  # fmt: skip
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


_TYPES = {
    "listed_on": pa.date32(), "session_date": pa.date32(), "valid_from": pa.date32(),
    "valid_to": pa.date32(), "last_session": pa.date32(), "delisted_on": pa.date32(),
    "ts_known_from": _TS,
    "ts_known_to": _TS, "ts_start": _TS, "ts_end": _TS, "ts_open": _TS, "ts_close": _TS,
    "session_ord": pa.int32(), "venue_mic": pa.string(), "listed_on_censored": pa.bool_(),
    "halt_count": pa.int32(), "admin_status": pa.string(), "ts_available": _TS,
    "reason": pa.string(), "tick_rule_id": pa.string(),
    **dict.fromkeys(DAY_FLAGS, pa.bool_()), **dict.fromkeys(LIMIT_PRICES, pa.float64()),
}  # fmt: skip


def _typed(*pairs: tuple[str, str]) -> list[dict[str, str]]:
    """tds.json `columns` for types a TDS kind leaves out."""
    return [{"name": c, "type": t} for c, t in pairs]


#: Each dataset's tds.json fields besides its name, kind, path and files.
FIELDS: dict[str, dict[str, Any]] = {
    "bars_1d": {
        "kind": "bars", "path": "bars/freq=1d", "availability": {"rule": "ts_end"},
        "params": {"freq": "1d", "price_basis": "raw", "density": "dense", "bar_time": "session"},
        "columns": _typed(("ts_start", "ts_us"), ("ts_end", "ts_us"))},
    "instrument_xref": {"columns": _typed(
        (ID, "id"), ("id_type", "code"), ("link_quality", "code"), ("source", "string"))},
    # TDS 4.2, 6.2: availability as the columns that hold it (#276)
    "instrument_symbols": {"availability": {"column": "ts_known_from"}},
    "corporate_actions": {
        "availability": {"effect": "ts_effective", "terms": "ts_terms_available"}},
    "delistings": {"availability": {"exit": "ts_exit_known", "value": "ts_value_available"}},
    "tradability_daily": {
        "path": "tradability_daily/freq=1d", "params": {"availability_by_column": BY_COLUMN},
        "columns": _typed((ID, "id"), ("session_date", "date"))},
    "eligibility_daily": {  # TDS 5.20: the rule is session_close, a missing row means false
        "availability": {"rule": "session_close"}, "params": {"missing_means": False},
        "columns": _typed(("rule_id", "id"), (ID, "id"), ("session_date", "date"),
                          ("is_eligible", "bool"), ("ts_available", "ts_us"))},
    "share_counts": {"availability": {"column": "ts_available"}, "columns": _typed(
        (ID, "id"), ("count_kind", "code"), ("ts_available", "ts_us"), ("source", "string"))},
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


def _span(table: pa.Table) -> dict[str, Any]:
    """`table`'s distinct instruments and its first and last `session_date`, each when it has
    the column, and its rows: the values D004 reads from the files (TDS 8.3)."""
    out: dict[str, Any] = {}
    if ID in table.column_names:
        out["instruments"] = pa.compute.count_distinct(table[ID]).as_py()
    if "session_date" in table.column_names and table.num_rows:
        low, high = pa.compute.min_max(table["session_date"]).as_py().values()
        out |= {"first": low.isoformat(), "last": high.isoformat()}
    return out | {"rows": table.num_rows}


def _coverage(parts: Mapping[str | None, pa.Table]) -> dict[str, Any]:
    """A dataset's tds.json `coverage` (TDS 4.3), from its `market=` partitions `parts` (key
    None: it has none, so no `by_market`): the keys of 4.2's example it has a column for, and
    no block when it has neither column."""
    slim = {m: t.select([c for c in (ID, "session_date") if c in t.column_names])
            for m, t in parts.items()}  # fmt: skip
    whole = _span(pa.concat_tables(list(slim.values())))
    keys = {"instruments": "instruments", "ts_min": "first", "ts_max": "last"}
    out: dict[str, Any] = {k: whole[v] for k, v in keys.items() if v in whole}
    if out and None not in slim:
        out["by_market"] = {m: _span(t) for m, t in slim.items()}
    return {"coverage": out} if out else {}


def _watermark(sessions: Table) -> dict[str, str]:
    """TDS 3.8's watermark of the market whose calendar rows are `sessions`: a synthetic
    package is complete through its period's last session, to that session's close (4.8)."""
    last = _arrow(sessions).slice(len(sessions["session_date"]) - 1).to_pylist()[0]
    return {"complete_through_session": last["session_date"].isoformat(),
            "complete_through": f"{last['ts_close']:%Y-%m-%dT%H:%M:%SZ}"}  # fmt: skip


def _daily(
    root: Path, tables: Mapping[str, Mapping[str, Any]], files: dict[str, list[Any]],
    cover: dict[str, Any],
) -> None:  # fmt: skip
    """Writes the datasets partitioned by market and year, of the markets that have them
    (tiny: the bars only so far), adding their `files` entries and their coverage."""
    for name in ("bars_1d", "tradability_daily", "eligibility_daily"):
        path = FIELDS[name].get("path", name)
        parts: dict[str | None, pa.Table]
        parts = {m: _arrow(tables[m][name]) for m in tables if name in tables[m]}
        for m, rows in parts.items():
            files.setdefault(name, []).extend(_by_year(root, f"{path}/market={m}", name, rows))
        if parts:
            cover[name] = _coverage(parts)


def _by_year(root: Path, rel: str, name: str, rows: pa.Table) -> list[dict[str, Any]]:
    """A daily dataset's rows written in `rel/year=Y/` partitions (TDS 3.6)."""
    years = pa.compute.year(rows["session_date"]).to_numpy()
    return [_write(root, f"{rel}/year={y}/part-00000.parquet", name, rows.filter(years == y))
            for y in sorted(set(years.tolist()))]  # fmt: skip


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
    takes none of `seed`, `start`, `end`, `n_kr`, `n_us`. `events` (4.8 `EventSpec`) injects
    `corporate_actions` and `delistings` rows, in `tiny` too, and KR halts in `small` and
    `full`. Every preset writes each dataset's `coverage` (TDS 4.3) and each market's
    watermark at the period's last session (TDS 3.8; #390), neither in a hash. `full` is
    `small`'s rules over full's period, counts and lives, the M1 datasets only;
    its M2 datasets, `full_ci` and `overrides` come with later tickets (spec 10.1: T0.8c).
    `degrade` takes 4.8's core values (T0.16a, T0.16c; `_synth_degrade`) and `late_bars`
    (#354), the others with T0.16b.
    """
    if preset not in ("tiny", *PRESETS) or overrides:
        raise NotImplementedError("only presets tiny, small and full, without overrides, are"
                                  " built so far (spec 4.8)")  # fmt: skip
    dg.check(degrade)
    root, chosen = Path(root), [m for m in MARKETS if m in markets]
    if not chosen or set(markets) - set(MARKETS):
        raise ValueError(f"markets {list(markets)}: choose one or more of {sorted(MARKETS)}")
    check(events, chosen, CA, preset == "tiny")
    if preset == "tiny" and any(v is not None for v in (start, end, n_kr, n_us)):
        raise ValueError("tiny is set by hand: start, end, n_kr and n_us apply to small and"
                         " full only")  # fmt: skip
    seeded = PRESETS.get(preset, PRESETS["small"])
    first, final = (start or seeded.start, end or seeded.end) if preset != "tiny" else (START, END)
    counts = seeded.counts | {k: v for k, v in (("KR", n_kr), ("US", n_us)) if v is not None}
    # one stream per market from PCG64(seed), so a market's rows do not depend on the others
    rngs = dict(zip(MARKETS, np.random.Generator(np.random.PCG64(seed)).spawn(3), strict=True))
    calendars, tables, through = {}, {}, {}
    for m in chosen:
        cal = MARKETS[m]["calendar_id"]
        if preset == "tiny":
            calendars[cal], tables[m] = _tiny_calendar(cal), _tiny(m, events)
        else:
            calendars[cal] = _small_calendar(cal, first, final)
            tables[m] = _small(m, counts[m], calendars[cal], rngs[m], events, seeded.life[m])
        through[m] = _watermark(calendars[cal])
        if degrade:
            closes = _arrow(calendars[cal])["ts_close"].combine_chunks()
            tables[m] = dg.apply(m, {k: _arrow(v) for k, v in tables[m].items()}, degrade,
                                 closes, seed)  # fmt: skip

    def joined(name: str, key: list[str]) -> pa.Table:
        table = pa.concat_tables([_arrow(tables[m][name]) for m in chosen])
        return table.sort_by([(k, "ascending") for k in key])

    made: dict[str, Callable[[], pa.Table]] = {
        "instruments": lambda: joined("instruments", [ID]),
        "instrument_symbols": lambda: joined("instrument_symbols", [ID, "valid_from"]),
        "instrument_xref": lambda: pa.schema(XREF).empty_table(),
        "calendar_sessions": lambda: pa.concat_tables(
            [_arrow(calendars[c]) for c in sorted(calendars)]),
        "corporate_actions": lambda: joined("corporate_actions", [ID, "ex_date", "event_id"]),
        "delistings": lambda: joined("delistings", [ID, "exit_date"]),
    }  # fmt: skip
    if preset != "tiny" and "KR" in chosen:  # 4.8 (11a); tiny's prices are on no grid
        made["market_rules"] = _market_rules
    if all("share_counts" in tables[m] for m in chosen):  # tiny has none yet
        made["share_counts"] = lambda: joined("share_counts", [ID, "count_kind", "as_of_date"])
    files: dict[str, list[Any]] = {}
    cover: dict[str, Any] = {}  # dataset → its `coverage` field, or nothing (TDS 4.3)
    for name, make in made.items():
        if name not in dg.absent(degrade):
            table = make()
            files[name] = [_write(root, f"{name}/part-00000.parquet", name, table)]
            cover[name] = _coverage({None: table})
    _daily(root, {m: tables[m] for m in chosen}, files, cover)
    manifest = {
        "tds_version": "1.0", "name": f"synth-{preset}", "created": f"{final}T00:00:00Z",
        "snapshot_id": snapshot_id, "producer": {"name": PRODUCER, "hints": HINTS},
        "profiles": dg.profiles(["tds:minimal-daily@1.0", "tds:equity-daily-core@1.0"], degrade),
        "id_namespaces": {m: NAMESPACES[m] for m in chosen},
        "markets": {m: MARKETS[m] | through[m] for m in chosen},
        "datasets": [
            {"name": name, "kind": name, "path": name, "schema_version": "1.0",
             **dg.fields(name, FIELDS.get(name, {}), degrade), **cover[name], "files": entries}
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


def a001(actions: pa.Table, bars: pa.Table) -> int | None:
    """TDS 5.11's A001 count: bars whose `cum_factor_*` step from the instrument's previous bar
    is not, to 1e-12 relative, the product of the price factors effective after that bar and
    by this one (one session in dense bars, more where sparse bars skip); None without them.

    Resolved at c = +inf: per `revision_of` chain only the version known last (5.11 step 2,
    ties to the last `event_id`), none when it is cancelled or only announced. The generator's
    own count until `tds check` runs A001 through `nexusbt_tds.actions` (#226, #227), which
    this module may not import (spec 2.5).
    """
    if "cum_factor_split" not in bars.column_names:  # degrade no_cum_factors (F-04)
        return None
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
    want: dict[tuple[str, str], list[tuple[dt.date, float]]] = {}  # (id, basis) → ex, factor
    for _, r in latest.values():
        bases = {"split_and_total": ("total", "split"), "total_only": ("total",)}
        for basis in bases.get(r["affects"], ()) if r["status"] == "effective" else ():
            want.setdefault((r[ID], basis), []).append((r["ex_date"], r["price_factor"]))
    rows = bars.select([ID, "session_date", "cum_factor_split", "cum_factor_total"])
    rows = rows.sort_by([(ID, "ascending"), ("session_date", "ascending")]).to_pylist()
    bad = 0
    for before, now in itertools.pairwise(rows):
        for basis in ("total", "split") if before[ID] == now[ID] else ():
            step = now[f"cum_factor_{basis}"] / before[f"cum_factor_{basis}"]
            due = [f for ex, f in want.get((now[ID], basis), ())
                   if before["session_date"] < ex <= now["session_date"]]  # fmt: skip
            if None not in due:  # a session with a "none" factor is not reconciled (5.11)
                m = math.prod(due)
                bad += abs(step - m) > 1e-12 * abs(m)
    return bad


def main(argv: Sequence[str] | None = None) -> int:
    """`python -m nexusbt.testing.synth --preset P --out DIR [--markets KR,US,ZZ]
    [--degrade a,b] --validate`."""
    parser = argparse.ArgumentParser(prog="python -m nexusbt.testing.synth")
    parser.add_argument("--preset", choices=["tiny", "small", "full", "full_ci"], default="tiny")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--markets", default="KR,US")
    parser.add_argument("--degrade", default="", help="spec 4.8 degrade values, a,b")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--validate", action="store_true", help="then run tds check --level full")
    args = parser.parse_args(argv)
    began = time.perf_counter()
    root = make_snapshot(
        args.out, preset=args.preset, seed=args.seed, markets=args.markets.split(","),
        snapshot_id=PRESETS.get(args.preset, PRESETS["small"]).snapshot_id,
        degrade=[v for v in args.degrade.split(",") if v],
    )  # fmt: skip
    took = time.perf_counter() - began
    manifest = json.loads((root / "tds.json").read_text(encoding="utf-8"))
    for ds in manifest["datasets"]:
        print(f"{ds['name']} {sum(f['rows'] for f in ds['files'])} rows")
    actions = read(root, "corporate_actions")
    status, revision = actions["status"].to_pylist(), actions["revision_of"].to_pylist()
    revised = sum(r is not None and s != "cancelled" for r, s in zip(revision, status, strict=True))
    print(f"corporate_actions revisions {revised}, cancellations {status.count('cancelled')}")
    for name in ("value_sha256", "semantic_sha256"):
        print(f"{name} {manifest['hashes'][name]}")
    size = sum(f["bytes"] for ds in manifest["datasets"] for f in ds["files"])
    print(f"time {took:.1f} s, size {size} bytes")
    print(f"profiles {', '.join(manifest['profiles'])}")
    if not args.validate:
        return 0
    bars = read(root, "bars_1d")
    bad = a001(actions, bars)
    print(f"TDS-A001: {'no cum_factor_* columns' if bad is None else bad}")
    if "ts_available" in bars.column_names:  # degrade late_bars (#354)
        late = pa.compute.greater(bars["ts_available"], bars["ts_end"])
        print(f"late bars {pa.compute.sum(late).as_py()}")
    done = _tds("check", str(root), "--level", "full")
    names = {ds["name"] for ds in manifest["datasets"]}
    # from `instruments`, which a package without `delistings` (F-13) still has
    last = {r[ID]: r["last_session"] for r in read(root, "instruments").to_pylist()}
    rows = actions.to_pylist()
    paid = sum(r["cash_per_share"] is not None and (last[r[ID]] or r["ex_date"]) < r["ex_date"]
               for r in rows)  # fmt: skip
    # the checker's own counts: V012's raw prices per dataset, V011's instrument-years
    off = sum(int(n) for n in re.findall(r"^warning TDS-V012 .*: (\d+) raw price", done.stdout,
                                         re.M))  # fmt: skip
    print(f"exact ratios: {sum(r['ratio_num'] is not None for r in rows)}, distributions before"
          f" delisting: {paid}, off-grid rows:"
          f" {off if 'market_rules' in names else 'no grid information'}")  # fmt: skip
    if "TDS-V011 not checked" not in done.stdout:  # the checker's note: volume unit unverified
        print(f"TDS-V011 warnings: {len(re.findall(r'^warning TDS-V011 ', done.stdout, re.M))}")
    sys.stdout.write(done.stdout)
    sys.stderr.write(done.stderr)
    return done.returncode or int(bool(bad))


if __name__ == "__main__":  # pragma: no cover - run by `python -m`, a separate process
    sys.exit(main())
