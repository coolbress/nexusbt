"""The synthetic generator's stage 4.8 (5), on `synth`'s one random stream: KR halts, limit
closes and 1-ULP wobbles moved into `small`'s bars, and the `tradability_daily` rows."""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable, Mapping, Sequence
from typing import Any

import numpy as np

from nexusbt.contracts import ID_COLUMN as ID
from nexusbt.testing import _synth_events as ev
from nexusbt.testing._synth_daily import OHLC, PRODUCER, _ratios, _snap

#: 4.8 (5): the US day from which tradability status is known.
US_STATUS = dt.date(2019, 8, 23)
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
