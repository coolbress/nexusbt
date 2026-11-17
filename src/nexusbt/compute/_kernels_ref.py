"""The adjustment reference of spec 5.3.3, `compute._kernels_ref.adjusted_window`: the window of
computation day t as the events known at t's reference time adjust it, cell by cell.

It reads the resolver's result as `Snapshot.actions(market, cutoff)` gives it (5.3.3a) and
computes the reference meaning directly, `raw[s] · Π m_e` over the events with `s < e <= t`
that have effect, so an amended or cancelled version and a pending one (5.3.4) need no other
path. A registered kernel's shortcut is checked against it (P-ADJ, INV-11).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence

import numpy as np
import numpy.typing as npt

from nexusbt.contracts import ResolvedActions

F64 = npt.NDArray[np.float64]
#: The `affects` values each basis multiplies (5.3.3): prices by `C_split` or `C_total`,
#: volume by `Q`, whose quantity events are the `split_and_total` ones (5.3.4).
BASES = {
    "split": frozenset({"split_and_total"}),
    "total": frozenset({"split_and_total", "total_only"}),
    "volume": frozenset({"split_and_total"}),
}


def adjusted_window(
    values: F64,
    t: int,
    window: int,
    actions: ResolvedActions,
    ids: Sequence[str],
    ts_open: npt.NDArray[np.datetime64],
    basis: str,
) -> tuple[F64, set[tuple[str, str]]]:
    """Rows `t-window+1 .. t` of `values` (axis rows from 0, one column per `ids`) as row t
    reads them, with `actions` resolved at row t's reference time: each cell s times the
    factor of every event with `s < e <= t` that has effect and published terms, e being the
    first session opening at or after its `ts_effective`. Prices take `m_e`, volume `q_e`.

    A factor that is none makes the cells before e NaN (4.6, INV-12); for a price basis, its
    (instrument, chain) pair is in the second result, the `AdjustmentUnavailable` pairs this
    window crossed (one count per pair in a run, 4.6)."""
    if basis not in BASES:
        raise ValueError(f"basis is one of {sorted(BASES)}, not {basis!r}")
    low = t - window + 1
    if not 0 <= low <= t < len(values):
        raise ValueError(f"rows {low}..{t} are not all rows of the {len(values)} given")
    out = values[low : t + 1].astype(np.float64)
    columns = {instrument: c for c, instrument in enumerate(ids)}
    crossed: set[tuple[str, str]] = set()
    for chain in actions.chains.values():
        c, at = columns.get(chain.instrument_id), chain.ts_effective
        if c is None or at is None or not chain.effective or chain.terms_pending:
            continue  # unknown, cancelled or stale at the cutoff, or its terms not yet out
        if chain.affects not in BASES[basis]:
            continue
        utc = np.datetime64(at.astimezone(dt.UTC).replace(tzinfo=None), "us")
        e = int(np.searchsorted(ts_open, utc))
        if not low < e <= t:
            continue
        effects = chain.effects
        factor = effects.share_factor if basis == "volume" else effects.price_factor
        if factor is None:
            out[: e - low, c] = np.nan
            if basis != "volume":
                crossed.add((chain.instrument_id, chain.chain_id))
        else:
            out[: e - low, c] *= factor
    return out, crossed
