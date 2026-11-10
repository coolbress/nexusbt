"""Spec 4.8 `degrade=`: the core values (T0.16a), each one gap of the 4.5 fallback table.

A value changes the generated rows of each market, or leaves a dataset out, and the package
then declares only the profiles it still keeps (TDS 7), so `tds check` still passes. Which
profile a gap breaks is TDS 7's table: `tds:equity-daily-core@1.0` needs `calendar_sessions`,
`delistings` and dense bars with OHLCV and `obs_status`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc

from nexusbt.contracts import ID_COLUMN as ID

CORE_PROFILE = "tds:equity-daily-core@1.0"
#: Spec 4.8's core values (T0.16a) → whether the gap breaks the core profile (TDS 7).
CORE = {
    "no_ohlc": True,  # F-01: OHLCV
    "no_sessions": True,  # F-02: calendar_sessions
    "sparse_bars": True,  # F-03: density = dense, obs_status
    "no_cum_factors": False,  # F-04: required in no profile
    "kr_ex_is_record": False,  # F-05
    "us_div_split_adjusted_no_dates": False,  # F-09
    "no_delistings": True,  # F-13: delistings
    "late_bars": False,  # #354: no gap of the 4.5 table; a late `ts_available` is valid data
}
#: `late_bars` (#354): the share of the KR bars that are late, by 1 to LATE_BY sessions, drawn
#: from a stream of their own, PCG64 seeded [seed, LATE_STREAM], so no other row changes.
LATE_SHARE, LATE_BY, LATE_STREAM = 0.005, 3, 354
#: Spec 4.8's other values, built by later tickets (spec 10.1: T0.16b, T0.16c).
LATER = ("no_fundamentals_state", "no_eligibility", "no_share_counts", "no_fundamentals_events",
         "no_benchmarks", "no_panels", "no_tick_info", "volume_in_lots")  # fmt: skip
#: The datasets a value leaves out.
ABSENT = {"no_sessions": "calendar_sessions", "no_delistings": "delistings"}
DATES = ("record_date", "declared_date", "pay_date", "resolution_date")


def check(degrade: Sequence[str]) -> None:
    """Refuses a value spec 4.8 does not have, and one a later ticket builds."""
    if isinstance(degrade, str):
        raise ValueError(f"degrade is a sequence of values, not the string {degrade!r}")
    unknown = [v for v in degrade if v not in CORE and v not in LATER]
    if unknown:
        raise ValueError(f"degrade {unknown}: spec 4.8 has {[*CORE, *LATER]}")
    later = [v for v in degrade if v in LATER]
    if later:
        raise NotImplementedError(f"degrade {later} come with T0.16b and T0.16c (spec 10.1);"
                                  f" built so far: {list(CORE)}")  # fmt: skip


def profiles(declared: Sequence[str], degrade: Sequence[str]) -> list[str]:
    """`declared` without the core profile when a value breaks it."""
    broken = any(CORE[v] for v in degrade)
    return [p for p in declared if not (broken and p == CORE_PROFILE)]


def absent(degrade: Sequence[str]) -> set[str]:
    return {ABSENT[v] for v in degrade if v in ABSENT}


def fields(name: str, given: Mapping[str, Any], degrade: Sequence[str]) -> dict[str, Any]:
    """A dataset's tds.json fields; sparse bars say so in `params.density` (TDS 5.5), late bars
    in the column rule, with no `params.ready_delay`, so 5.1.2's delta is 0."""
    out = dict(given)
    if name == "bars_1d" and "sparse_bars" in degrade:
        out["params"] = {**out["params"], "density": "sparse"}
    if name == "bars_1d" and "late_bars" in degrade:
        out["availability"] = {"column": "ts_available"}
        out["columns"] = [*out["columns"], {"name": "ts_available", "type": "ts_us"}]
    return out


def _late(market: str, bars: pa.Table, closes: pa.Array, seed: int) -> pa.Table:
    """`bars` with `ts_available`: the close of the bar's session, `ready(s)` at delta 0, or
    for a late KR bar the close 1 to LATE_BY sessions later. Late are LATE_SHARE of the bars
    with LATE_BY sessions after them, and the last row of every year but the last (in the
    generator's order the last row of that year's partition, 5.3.1's overlap tail)."""
    at = pc.index_in(bars["ts_end"], value_set=closes).to_numpy()  # each bar's session
    times = closes.to_numpy()
    available = times[at]
    if market == "KR":
        rng = np.random.Generator(np.random.PCG64([seed, LATE_STREAM]))
        can = np.flatnonzero(at < len(times) - LATE_BY)
        years = pc.year(bars["session_date"]).to_numpy()
        tails = [np.flatnonzero(years == y)[-1] for y in np.unique(years)[:-1]]
        picks = rng.choice(can, round(LATE_SHARE * len(can)), replace=False)
        picks = np.union1d(picks, np.intersect1d(tails, can)).astype(np.int64)
        available[picks] = times[at[picks] + rng.integers(1, LATE_BY, len(picks), endpoint=True)]
    return bars.append_column("ts_available", pa.array(available).cast(bars["ts_end"].type))


def apply(market: str, tables: dict[str, pa.Table], degrade: Sequence[str],
          closes: pa.Array, seed: int) -> dict[str, pa.Table]:  # fmt: skip
    """One market's tables with the gaps `degrade` names; `closes` are the market's session
    closes in order, which `late_bars` counts its sessions on.

    `us_div_split_adjusted_no_dates` divides only the dividends with a share event after them;
    seed 0's `small` has none, so a test of F-09's A004 count injects one (`EventSpec`).
    `kr_ex_is_record` writes `record_date = ex_date` and keeps the bars' ex-dates, which the
    cumulative factors follow (A001)."""
    out = dict(tables)
    bars, actions = out["bars_1d"], out["corporate_actions"]
    if "no_ohlc" in degrade:  # F-01: open, high and low null, the close kept
        null = pa.nulls(len(bars), pa.float64())
        for c in ("open", "high", "low"):
            bars = bars.set_column(bars.schema.get_field_index(c), c, null)
    if "sparse_bars" in degrade:  # F-03: only the sessions it traded, and no obs_status
        bars = bars.filter(pc.equal(bars["obs_status"], "traded")).drop_columns(["obs_status"])
    if "no_cum_factors" in degrade:  # F-04
        bars = bars.drop_columns(["cum_factor_split", "cum_factor_total"])
    if "kr_ex_is_record" in degrade and market == "KR":  # F-05
        actions = _rows(actions, lambda r: r | {"record_date": r["ex_date"]})
    if "us_div_split_adjusted_no_dates" in degrade and market == "US":  # F-09
        later = _later_shares(actions)
        actions = _rows(actions, lambda r: r | dict.fromkeys(DATES) | {
            "pay_date_status": "missing",
            "cash_per_share": r["cash_per_share"] / later(r[ID], r["ex_date"])})  # fmt: skip
    if "late_bars" in degrade:
        bars = _late(market, bars, closes, seed)
    out["bars_1d"], out["corporate_actions"] = bars, actions
    for name in absent(degrade):
        out.pop(name, None)
    return out


def _rows(actions: pa.Table, change: Any) -> pa.Table:
    """`actions` with `change` applied to its cash dividends, every version of them."""
    rows = [change(r) if r["kind"] == "cash_dividend" else r for r in actions.to_pylist()]
    return pa.Table.from_pylist(rows, schema=actions.schema)


def _later_shares(actions: pa.Table) -> Any:
    """(instrument, day) → the product of the share factors of the share events effective
    after that day: the latest version of each, none when cancelled (TDS 5.11's resolution at
    c = +inf, as the generator writes it: a later version names its first in `revision_of`)."""
    rows = actions.to_pylist()
    replaced = {r["revision_of"] for r in rows if r["revision_of"]}
    shares = [r for r in rows if r["event_id"] not in replaced and r["status"] == "effective"
              and r["affects"] == "split_and_total"]  # fmt: skip

    def factor(iid: str, day: Any) -> float:
        product = 1.0
        for r in shares:
            if r[ID] == iid and r["ex_date"] > day:
                product *= r["share_factor"]
        return product

    return factor
