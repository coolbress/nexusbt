"""Parts of the synthetic generator (spec 4.8) that `synth` calls for `small`: the KR price
grid of 4.8 (5), `share_counts` (4.8 (7)) and `eligibility_daily` (4.8 (10)).

They draw from `synth`'s one random stream in the order it calls them and keep its
integer-and-+-x/ value path (#128), so moving them here changed no byte of `small`.
"""

from __future__ import annotations

import csv
import functools
import itertools
from collections.abc import Callable, Iterator, Sequence
from importlib.resources import files as resources
from typing import Any

import numpy as np
import pyarrow as pa

from nexusbt.contracts import ID_COLUMN as ID

PRODUCER = "nexusbt-synth"
#: The TDS 5.14 `share_counts` columns the generator writes.
SHARE_COUNTS = pa.schema({ID: pa.string(), "count_kind": pa.string(), "as_of_date": pa.date32(),
                          "shares": pa.float64(), "ts_available": pa.timestamp("us", tz="UTC"),
                          "source": pa.string()})  # fmt: skip
ELIGIBILITY = "investable-v1"  # 4.8 (10)'s rule
#: 4.8 (5): the KR tick and price-limit tables' venue group of each MIC.
KR_GROUP = {"XKRX": "KOSPI", "XKOS": "KOSDAQ"}
OHLC = ("open", "high", "low", "close")


@functools.cache
def _resource(name: str) -> tuple[dict[str, str], ...]:
    with (resources("nexusbt.resources") / name).open(encoding="utf-8") as f:
        return tuple(csv.DictReader(f))


def _kr_rows(
    name: str, venue: str | None, key: str, dates: np.ndarray
) -> Iterator[tuple[dict[str, str], np.ndarray]]:
    """The rows of resource `name` for `venue`'s KR group (or `*`), with the mask of `dates`
    each is valid on."""
    group = KR_GROUP.get(venue or "")
    for r in _resource(name) if group else ():
        if r[key] in (group, "*"):
            start = np.datetime64(r["valid_from"] or "1900-01-01")
            yield r, (dates >= start) & (dates < np.datetime64(r["valid_to"] or "2200-01-01"))


def _snap(prices: np.ndarray, dates: np.ndarray, venue: str | None,
          to: Callable[[Any], Any] = np.round) -> np.ndarray:  # fmt: skip
    """KR raw prices onto the pack's tick table (4.8 (5)), the band chosen by the price before
    snapping; `to` np.floor or np.ceil snaps a limit price inward. Others are returned as they
    are."""
    out = prices.copy()
    for r, valid in _kr_rows("ticks/kr_tick_table_v1.csv", venue, "venue_group", dates):
        tick, high = float(r["tick"]), float(r["price_to"] or "inf")
        band = valid & (prices >= float(r["price_from"])) & (prices < high)
        out[band] = to(prices[band] / tick) * tick
    return out


def _ratios(dates: np.ndarray, venue: str | None) -> np.ndarray:
    """Each date's KR daily price limit ratio, NaN where there is none."""
    out = np.full(len(dates), np.nan)
    for r, valid in _kr_rows("limits/kr_price_limits_v1.csv", venue, "market", dates):
        out[valid] = float(r["limit_ratio"])
    return out


def _venues(
    venues: Sequence[str] | None, n: int, bars: dict[str, list[Any]], rng: np.random.Generator
) -> list[str | None]:
    """Each of the `n` instruments' venue MIC drawn from `venues` (None when there are none),
    and its KR prices snapped onto that venue's tick table."""
    mics = rng.choice(venues, n).tolist() if venues else [None] * n
    for k, name in itertools.product(range(n), OHLC):
        bars[name][k] = _snap(bars[name][k], bars["session_date"][k], mics[k])
    return mics


def _share_counts(
    market: str, sessions: dict[str, Any], bars: dict[str, list[Any]], rng: np.random.Generator
) -> pa.Table:
    """4.8 (7): KR `listed` shares on every session, known at its close; US and ZZ
    `outstanding` shares at each quarter end, filed 40 days later at 21:00Z, the rows filed
    after the period left out. A listing starts with 1e6~1e8 shares, multiplied from each
    share event's ex-date on (the `cum_factor_split` ratio), fractions dropped."""
    end, out = sessions["session_date"][-1], []
    for k in range(len(bars[ID])):
        base = int(rng.integers(1_000_000, 100_000_000, endpoint=True))
        dates, split = bars["session_date"][k], bars["cum_factor_split"][k]
        shares, kind = np.floor(base * (split[0] / split)), "listed"
        asof, at, when = dates, np.arange(len(dates)), bars["ts_end"][k]
        if market != "KR":  # each quarter's last day, the last session on or before it
            month = dates.astype("datetime64[M]").astype(int)
            quarter = (month - month % 3 + 3).astype("datetime64[M]").astype("datetime64[D]")
            asof = np.unique(quarter - np.timedelta64(1, "D"))
            asof = asof[asof <= dates[-1]]
            when = (asof + np.timedelta64(40, "D")).astype("datetime64[us]") + np.timedelta64(
                21, "h"
            )
            filed = when.astype("datetime64[D]") <= end
            asof, when, kind = asof[filed], when[filed], "outstanding"
            at = np.searchsorted(dates, asof, side="right") - 1
        out.append(pa.table({
            ID: [bars[ID][k][0]] * len(asof), "count_kind": [kind] * len(asof),
            "as_of_date": asof, "shares": shares[at], "ts_available": when,
            "source": [PRODUCER] * len(asof)}, schema=SHARE_COUNTS))  # fmt: skip
    return pa.concat_tables([SHARE_COUNTS.empty_table(), *out])


def _eligibility(bars: dict[str, list[Any]], status: dict[str, list[Any]]) -> dict[str, Any]:
    """4.8 (10): `investable-v1` on every bar. All instruments are common stock, so a bar is
    eligible when it traded and its instrument is not administrative that day; the traded
    part is the day's own result, so each row is available at the session close."""
    out: dict[str, list[Any]] = {}
    for k in range(len(bars[ID])):
        traded = np.array(bars["obs_status"][k]) == "traded"
        admin = np.array(status["admin_status"][k]) == "administrative"
        for name, values in {
            "rule_id": [ELIGIBILITY] * len(traded), ID: bars[ID][k],
            "session_date": bars["session_date"][k], "is_eligible": traded & ~admin,
            "reason": [None if t and not a else "administrative" if t else "no_price"
                       for t, a in zip(traded, admin, strict=True)],
            "ts_available": bars["ts_end"][k],
        }.items():  # fmt: skip
            out.setdefault(name, []).append(values)
    return out
