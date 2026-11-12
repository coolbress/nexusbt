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
import sys
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal, NamedTuple

import exchange_calendars as xc
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from nexusbt.contracts import ID_COLUMN as ID
from nexusbt.testing import _synth_degrade as dg
from nexusbt.testing import _synth_events as ev
from nexusbt.testing import _synth_package as pk
from nexusbt.testing._synth_actions import BP, CA, YEAR, _actions, _at
from nexusbt.testing._synth_daily import (
    OHLC,
    PRODUCER,
    TICK_RULE,
    _eligibility,
    _share_counts,
    _value_traded,
    _venues,
)
from nexusbt.testing._synth_events import check, targets
from nexusbt.testing._synth_exits import DL, _delistings
from nexusbt.testing._synth_package import Table
from nexusbt.testing._synth_trade import _tradability

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
DRIFT = 3  # small's log drift in basis points per step (4.8 (3)'s 0.0003)


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
                          [None] * len(ids), found, MARKETS[market]["currency"],
                          random=False)  # fmt: skip
    for k, c in itertools.product(range(len(ids)), names):
        for r, value in zip(held[k], bars[c][k].tolist(), strict=True):
            r[c] = value
    rng = np.random.default_rng(0)  # 4.8 (6)'s draws for the columns an exit leaves out
    return actions, _delistings(market, ids, first, last, sessions, bars, rng, ended,
                                MARKETS[market]["currency"])[0]  # fmt: skip


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
                              targets(events, ids, days, first, last),
                              MARKETS[market]["currency"])  # fmt: skip
    status = _tradability(market, first, last, mics, moved, bars, rng,
                          (events, ids, days))  # moves `bars` too  # fmt: skip
    out, payouts, delisted = _delistings(market, ids, first, last, sessions, bars, rng, ended,
                                         MARKETS[market]["currency"])  # fmt: skip
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


def _arguments(
    root: Path, preset: str, markets: Sequence[str], events: Sequence[Mapping[str, Any]],
    overrides: Mapping[str, Any] | None, degrade: Sequence[str], drawn: Sequence[object],
) -> tuple[Path, list[str]]:  # fmt: skip
    """`make_snapshot`'s refusals, in its order, then `root` as a Path and the chosen markets
    in MARKETS' order; `drawn` is the arguments only a seeded preset takes (start, end, n_kr,
    n_us)."""
    if preset not in ("tiny", *PRESETS) or overrides:
        raise NotImplementedError("only presets tiny, small and full, without overrides, are"
                                  " built so far (spec 4.8)")  # fmt: skip
    dg.check(degrade)
    root, chosen = Path(root), [m for m in MARKETS if m in markets]
    if not chosen or set(markets) - set(MARKETS):
        raise ValueError(f"markets {list(markets)}: choose one or more of {sorted(MARKETS)}")
    check(events, chosen, CA, preset == "tiny")
    if preset == "tiny" and any(v is not None for v in drawn):
        raise ValueError("tiny is set by hand: start, end, n_kr and n_us apply to small and"
                         " full only")  # fmt: skip
    return root, chosen


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
    behind: Mapping[str, int] | None = None,
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
    (#354), the others with T0.16b. Each dataset is processed through the watermark session in
    every market (TDS 4.3, #192), but `behind[name]` sessions earlier for each dataset `name`
    without a row per session (4.8 `behind`).
    """
    root, chosen = _arguments(root, preset, markets, events, overrides, degrade,
                              (start, end, n_kr, n_us))  # fmt: skip
    seeded = PRESETS.get(preset, PRESETS["small"])
    first, final = (start or seeded.start, end or seeded.end) if preset != "tiny" else (START, END)
    counts = seeded.counts | {k: v for k, v in (("KR", n_kr), ("US", n_us)) if v is not None}
    # one stream per market from PCG64(seed), so a market's rows do not depend on the others
    rngs = dict(zip(MARKETS, np.random.Generator(np.random.PCG64(seed)).spawn(3), strict=True))
    calendars, tables, entries = {}, {}, {}
    for m in chosen:
        cal = MARKETS[m]["calendar_id"]
        if preset == "tiny":
            calendars[cal], tables[m] = _tiny_calendar(cal), _tiny(m, events)
        else:
            calendars[cal] = _small_calendar(cal, first, final)
            tables[m] = _small(m, counts[m], calendars[cal], rngs[m], events, seeded.life[m])
        entries[m] = MARKETS[m] | pk._watermark(calendars[cal])
        if degrade:
            closes = pk._arrow(calendars[cal])["ts_close"].combine_chunks()
            tables[m] = dg.apply(m, {k: pk._arrow(v) for k, v in tables[m].items()}, degrade,
                                 closes, seed)  # fmt: skip
    # 4.8 (11a) with KR; tiny's prices are on no grid
    made = pk.datasets(tables, calendars, preset != "tiny" and "KR" in chosen)
    about = {"name": f"synth-{preset}", "created": f"{final}T00:00:00Z",
             "snapshot_id": snapshot_id, "markets": entries}  # fmt: skip
    days = {m: pk._arrow(calendars[MARKETS[m]["calendar_id"]])["session_date"].to_pylist()
            for m in chosen}  # fmt: skip
    through = pk.processed(behind or {}, set(made) - set(dg.absent(degrade)), days)
    return pk.write(root, made, tables, about, degrade, through)


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
    done = pk._tds("check", str(root), "--level", "full")
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
