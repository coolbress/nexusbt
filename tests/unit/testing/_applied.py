"""The generator's self-check (#608, #705): what `_move` applied to a package's prices, as it
recorded them while it multiplied them, against what the checker's resolver reads from the
package's events. The two sides share no function: the generator does not import `nexusbt_tds`
(spec 2.5), and this side reads only the package and `nexusbt_tds`. It took over from TDS-A001,
which compared the bars' `cum_factor_*` with the same resolver until #705 removed them."""

from __future__ import annotations

import datetime as dt
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pyarrow as pa

from nexusbt.testing import synth
from nexusbt.testing.synth import read
from nexusbt_tds.actions import resolve
from nexusbt_tds.keys import ranked

#: TDS 5.11: the adjusted series each `affects` steps, as A001 read them before #705.
BASES = {"split_and_total": ("total", "split"), "total_only": ("total",)}


def applied(package: Path) -> Counter[tuple[Any, ...]]:
    """What the generator applied to `package`'s prices, as `_move` recorded it while it
    multiplied them (after a `behind` cut): (instrument, ex-date, basis, factor, chain id)."""
    return Counter(s for steps in synth.APPLIED[package.resolve()].values() for s in steps)


def resolved(package: Path) -> Counter[tuple[Any, ...]]:
    """The same, as the checker's resolver reads `package`'s events at c = +inf (TDS 5.11):
    each effective chain's version with a factor, once per basis its `affects` steps, on an
    ex-date after the instrument's first bar and up to its last, where A001 compared the
    bars' `cum_factor_*` between adjacent rows before #705."""
    events = read(package, "corporate_actions")
    by_id = {r["event_id"]: r for r in events.to_pylist()}
    days: dict[str, list[dt.date]] = {}
    bars = read(package, "bars_1d")
    for iid, day in zip(bars["instrument_id"].to_pylist(), bars["session_date"].to_pylist(),
                        strict=True):  # fmt: skip
        days.setdefault(iid, []).append(day)
    out: Counter[tuple[Any, ...]] = Counter()
    chains = resolve(pa.Table.from_pylist(ranked(events.to_pylist())[0]), None).chains
    for chain, r in chains.items():
        version = by_id.get(r.event_id or "", {})
        ex, factor = version.get("ex_date"), r.effects.price_factor
        held = days.get(r.instrument_id, [])
        if not r.effective or factor is None or not held or not min(held) < ex <= max(held):
            continue
        for basis in BASES.get(version["affects"], ()):
            out[r.instrument_id, ex, basis, factor, chain] += 1
    return out


def split_at(package: Path) -> Callable[[str, dt.date], float]:
    """(instrument, day) → the product of the split steps the generator applied on or before
    `day`, in ex-date order: the running factor the bars' `cum_factor_split` held before #705."""
    by: dict[str, list[tuple[dt.date, float]]] = {}
    for i, ex, basis, f, _ in sorted(applied(package).elements(), key=lambda s: s[:2]):
        if basis == "split":
            by.setdefault(i, []).append((ex, f))

    def at(iid: str, day: dt.date) -> float:
        out = 1.0
        for ex, f in by.get(iid, []):
            if ex <= day:
                out *= f
        return out

    return at
