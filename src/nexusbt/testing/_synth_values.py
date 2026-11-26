"""`small`'s value tables (spec 4.8, 5.3.5; TDS 5.28; #752's V2b, the owner's decisions of
2026-11-27).

Five items of example data. Their names are this generator's, not names the engine expects:
- `values`: `shares_out` (`kind: share_count`), each quarter-end in that date's share basis;
  `eps` (`kind: per_share`, `carry: 63`), each quarter-end; `in_index` (`carry: next_listing`),
  value 1 on each quarter's first session for about a third of the listed equities.
- `market_values`: `cash_rate`, the annual rate in bp (spec 3.11's `[account] cash_rate`), on
  each month's first session.
- `symbol_values`: `sector`, a code from 1 to 10.

The draws come from a stream of their own, `PCG64([seed, 752])`, one child per market as the
other stages spawn theirs, so no other dataset's rows change. Integer draws and the four
arithmetic operations only (4.8 rule 3; IEEE rounds a division the same everywhere), so
the bytes are the same on every platform.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping
from typing import Any

import numpy as np
import pyarrow as pa

from nexusbt.contracts import ID_COLUMN as ID

#: The value tables' declarations (TDS 5.28), in their datasets' `params.items`.
ITEMS = {
    "values": {"shares_out": {"kind": "share_count"},
               "eps": {"kind": "per_share", "carry": 63},
               "in_index": {"carry": "next_listing"}},
    "market_values": {},
    "symbol_values": {},
}  # fmt: skip
KINDS = tuple(ITEMS)
#: (kind, market, item) → that partition's rows.
Parts = dict[tuple[str, str, str], pa.Table]
#: A market's first cash rate and its bounds, in bp a year (example values of this generator).
CASH = {"KR": (250, 50, 400), "US": (150, 0, 500), "ZZ": (100, 0, 300)}


def value_tables(
    tables: Mapping[str, Mapping[str, Any]], sessions: Mapping[str, list[dt.date]], seed: int,
    markets: tuple[str, ...],
) -> Parts:  # fmt: skip
    """Each market's partitions of the three value tables, from its final `instruments` and
    `corporate_actions` and its `sessions`; `markets` orders the streams (`synth.MARKETS`)."""
    streams = np.random.Generator(np.random.PCG64([seed, 752])).spawn(len(markets))
    out: Parts = {}
    for m, rng in zip(markets, streams, strict=True):
        if m not in tables:
            continue
        out |= _market(m, tables[m], sessions[m], rng)
    return dict(sorted(out.items()))


def _market(m: str, t: Mapping[str, Any], days: list[dt.date], rng: np.random.Generator) -> Parts:
    inst = t["instruments"]
    inst = inst if isinstance(inst, pa.Table) else pa.table(inst)
    rows = [r for r in inst.to_pylist() if r["asset_class"] == "equity"]
    rows.sort(key=lambda r: r[ID])
    end = days[-1]
    spans = {r[ID]: (r["listed_on"], r["last_session"] or end) for r in rows}
    quarters = _quarter_ends(days[0], end)
    shares = _shares(t["corporate_actions"])
    out: Parts = {}
    counts: list[tuple[str, dt.date, float]] = []
    eps: list[tuple[str, dt.date, float]] = []
    for i, (first, last) in spans.items():
        base = int(rng.integers(1_000_000, 500_000_001))
        for q in (q for q in quarters if first <= q <= last):
            count = base
            for ex, num, den in shares.get(i, ()):
                if ex <= q:  # date q's share basis (5.3.5), TDS 5.11's integer arithmetic
                    count = count * num // den
            counts.append((i, q, float(count)))
            eps.append((i, q, int(rng.integers(-200, 801)) / 100))
    out[("values", m, "shares_out")] = _table(counts)
    out[("values", m, "eps")] = _table(eps)
    listed = []
    for day in _quarter_firsts(days):
        alive = [i for i, (first, last) in spans.items() if first <= day <= last]
        chosen = sorted(i for i in alive if rng.integers(0, 3) == 0)
        listed += [(i, day, 1.0) for i in chosen]
    out[("values", m, "in_index")] = _table(listed)
    rate, low, high = CASH.get(m, CASH["ZZ"])
    monthly = []
    for day in _month_firsts(days):
        monthly.append((day, float(rate)))
        rate = min(high, max(low, rate + 25 * int(rng.integers(-1, 2))))
    out[("market_values", m, "cash_rate")] = pa.table({
        "date": pa.array([d for d, _ in monthly], pa.date32()),
        "value": pa.array([v for _, v in monthly], pa.float64())})  # fmt: skip
    sectors = [(i, float(rng.integers(1, 11))) for i in spans]
    out[("symbol_values", m, "sector")] = pa.table({
        ID: pa.array([i for i, _ in sectors], pa.string()),
        "value": pa.array([v for _, v in sectors], pa.float64())})  # fmt: skip
    return out


def _table(rows: list[tuple[str, dt.date, float]]) -> pa.Table:
    rows = sorted(rows, key=lambda r: (r[0], r[1]))  # TDS 5.28's sort
    return pa.table({ID: pa.array([r[0] for r in rows], pa.string()),
                     "date": pa.array([r[1] for r in rows], pa.date32()),
                     "value": pa.array([r[2] for r in rows], pa.float64())})  # fmt: skip


def _shares(actions: Any) -> dict[str, list[tuple[dt.date, int, int]]]:
    """Per instrument, the effective last versions that change the share count: (ex-date,
    `ratio_num`, `ratio_den`), the exact ratio TDS 5.11 makes canonical."""
    table = actions if isinstance(actions, pa.Table) else pa.table(actions)
    rows = table.to_pylist()
    revised = {r["revision_of"] for r in rows if r["revision_of"]}
    out: dict[str, list[tuple[dt.date, int, int]]] = {}
    for r in rows:
        if r["status"] != "effective" or r["event_id"] in revised:
            continue
        if r["share_factor"] in (None, 1) or r["ratio_num"] is None or r["ratio_den"] is None:
            continue
        out.setdefault(r[ID], []).append((r["ex_date"], int(r["ratio_num"]), int(r["ratio_den"])))
    return {i: sorted(v) for i, v in out.items()}


def _quarter_ends(first: dt.date, last: dt.date) -> list[dt.date]:
    """Calendar quarter-ends from `first` to `last`: a date need not be a session (5.28)."""
    ends = []
    for year in range(first.year, last.year + 1):
        for month, day in ((3, 31), (6, 30), (9, 30), (12, 31)):
            if first <= (q := dt.date(year, month, day)) <= last:
                ends.append(q)
    return ends


def _quarter_firsts(days: list[dt.date]) -> list[dt.date]:
    seen: set[tuple[int, int]] = set()
    out = []
    for d in days:
        if (key := (d.year, (d.month - 1) // 3)) not in seen:
            seen.add(key)
            out.append(d)
    return out


def _month_firsts(days: list[dt.date]) -> list[dt.date]:
    seen: set[tuple[int, int]] = set()
    out = []
    for d in days:
        if (key := (d.year, d.month)) not in seen:
            seen.add(key)
            out.append(d)
    return out
