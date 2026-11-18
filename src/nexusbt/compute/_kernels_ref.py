"""The adjustment reference of spec 5.3.3, `compute._kernels_ref.adjusted_window`: the window of
computation day t as the events known at t's reference time adjust it, cell by cell; and the
registered kernels, each with its declared adjustment class and the shortcut that class allows.

It reads the resolver's result as `Snapshot.actions(market, cutoff)` gives it (5.3.3a) and
computes the reference meaning directly, `raw[s] · Π m_e` over the events with `s < e <= t`
that have effect, so an amended or cancelled version and a pending one (5.3.4) need no other
path. A registered kernel's shortcut is checked against it (P-ADJ, INV-11): a kernel that does
not pass is not registered.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

import numpy as np
import numpy.typing as npt

from nexusbt.compute import _kernels
from nexusbt.contracts import ResolvedActions

F64 = npt.NDArray[np.float64]
#: The `affects` values each basis multiplies (5.3.3): prices by `C_split` or `C_total`,
#: volume by `Q`, whose quantity events are the `split_and_total` ones (5.3.4; #241,
#: Decisions 2026-11-18).
BASES = {
    "split": frozenset({"split_and_total"}),
    "total": frozenset({"split_and_total", "total_only"}),
    "volume": frozenset({"split_and_total"}),
}


class AdjustmentClass(StrEnum):
    """3.4's adjustment classes: under a per-instrument scalar k, a degree-0 kernel's value is
    unchanged, a degree-1 kernel's scales by k; an invariant kernel reads raw values."""

    DEGREE_0 = "homogeneous of degree 0"
    DEGREE_1 = "homogeneous of degree 1"
    INVARIANT = "invariant"


@dataclass(frozen=True, slots=True)
class Registered:
    """A window kernel, `(W, N)` window to `(N,)` values, and its declared class (5.3.3)."""

    kernel: Callable[[F64], F64]
    adjustment: AdjustmentClass


def _total(window: F64) -> F64:
    """`window_sum` of the whole window: its left fold per column (5.3.10)."""
    found: F64 = _kernels.window_sum(window, len(window), np.array([len(window) - 1]))[0]
    return found


def _annualized(window: F64) -> F64:
    """`AnnualizedVolatility` with 3.4's default factor 252."""
    return _kernels.window_annualized_volatility(window, 252.0)


#: The registered kernels by name: a built-in factor's by its term's operator name (3.4), which
#: `pipeline.factors.ADJUSTMENT` declares the same class for. `AverageDollarVolume` reads the
#: window of `close * volume`, a value, so it is invariant (3.4).
REGISTERED: Mapping[str, Registered] = MappingProxyType(
    {
        "window_sum": Registered(_total, AdjustmentClass.DEGREE_1),
        "Returns": Registered(_kernels.window_returns, AdjustmentClass.DEGREE_0),
        "SimpleMovingAverage": Registered(_kernels.window_nanmean, AdjustmentClass.DEGREE_1),
        "AverageDollarVolume": Registered(_kernels.window_nansum_mean, AdjustmentClass.INVARIANT),
        "AverageTradedValue": Registered(_kernels.window_nanmean, AdjustmentClass.INVARIANT),
        "AnnualizedVolatility": Registered(_annualized, AdjustmentClass.DEGREE_0),
        "RollingStd": Registered(
            lambda window: _kernels.window_nanstd(window, 1), AdjustmentClass.DEGREE_1
        ),
    }
)


def _events(
    actions: ResolvedActions, ids: Sequence[str], ts_open: npt.NDArray[np.datetime64],
    basis: str, low: int, t: int,
) -> Iterator[tuple[int, int, float | None, str, str]]:  # fmt: skip
    """(column, e, factor, instrument, chain) of each event with `low < e <= t` that has
    effect and published terms on `basis`, e being the first session opening at or after its
    `ts_effective`; prices take `m_e`, volume `q_e`, None for "none"."""
    if basis not in BASES:
        raise ValueError(f"basis is one of {sorted(BASES)}, not {basis!r}")
    columns = {instrument: c for c, instrument in enumerate(ids)}
    for chain in actions.chains.values():
        c, at = columns.get(chain.instrument_id), chain.ts_effective
        if c is None or at is None or not chain.effective or chain.terms_pending:
            continue  # unknown, cancelled or stale at the cutoff, or its terms not yet out
        if chain.affects not in BASES[basis]:
            continue
        utc = np.datetime64(at.astimezone(dt.UTC).replace(tzinfo=None), "us")
        e = int(np.searchsorted(ts_open, utc))
        if low < e <= t:
            effects = chain.effects
            factor = effects.share_factor if basis == "volume" else effects.price_factor
            yield c, e, factor, chain.instrument_id, chain.chain_id


def _rows(values: F64, t: int, window: int) -> tuple[int, F64]:
    low = t - window + 1
    if not 0 <= low <= t < len(values):
        raise ValueError(f"rows {low}..{t} are not all rows of the {len(values)} given")
    return low, values[low : t + 1].astype(np.float64)


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
    factor of every event with `s < e <= t` that has effect and published terms.

    A factor that is none makes the cells before e NaN (4.6, INV-12); for a price basis, its
    (instrument, chain) pair is in the second result, the `AdjustmentUnavailable` pairs this
    window crossed (one count per pair in a run, 4.6)."""
    low, out = _rows(values, t, window)
    crossed: set[tuple[str, str]] = set()
    for c, e, factor, instrument, chain in _events(actions, ids, ts_open, basis, low, t):
        if factor is None:
            out[: e - low, c] = np.nan
            if basis != "volume":
                crossed.add((instrument, chain))
        else:
            out[: e - low, c] *= factor
    return out, crossed


def shortcut(
    entry: Registered,
    values: F64,
    t: int,
    window: int,
    actions: ResolvedActions,
    ids: Sequence[str],
    ts_open: npt.NDArray[np.datetime64],
    basis: str,
) -> F64:
    """Row t's value of a registered kernel by its class's shortcut (5.3.3): the kernel on the
    base values `B[s] = raw[s] / C[s]` of the window, times `C[t]` for degree 1; on the raw
    values for an invariant kernel. `C` is the product of the factors from the window's first
    row; a cell before an event whose factor is none is NaN in every class, as the reference
    leaves it (4.6), and `values` are the cells row t sees (5.1.2)."""
    low, raw = _rows(values, t, window)
    c_ = np.ones_like(raw)
    apart = np.zeros(raw.shape, dtype=bool)  # a "none" factor lies between the cell and t
    for c, e, factor, _, _ in _events(actions, ids, ts_open, basis, low, t):
        if factor is None:
            apart[: e - low, c] = True
        else:
            c_[e - low :, c] *= factor
    if entry.adjustment is AdjustmentClass.INVARIANT:
        return entry.kernel(np.where(apart, np.nan, raw))
    found = entry.kernel(np.where(apart, np.nan, raw / c_))
    return found * c_[-1] if entry.adjustment is AdjustmentClass.DEGREE_1 else found
