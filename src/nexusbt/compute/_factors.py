"""The built-in factors of 3.4 at one row: each term's windows in, its `(N,)` values out.

The kernels are `_kernels`' (registered with their classes in `_kernels_ref.REGISTERED`); this
module picks one by the term's operator and passes the term's parameters. An `inf` cell or
result is NaN (5.4.1, "`inf` is turned into NaN and counted"): a window's `inf` cell follows its
factor's NaN rule of 3.4. The executor makes every term's `inf` NaN where it stores the row
(#536), so the result's rule here is the same one, applied again with the same value; a window's
column cells come from the block and still pass through here. The count is #249's.
"""

from __future__ import annotations

import functools
from collections.abc import Callable, Mapping, Sequence
from typing import Any

import numpy as np
import numpy.typing as npt

from nexusbt.compute import _kernels
from nexusbt.pipeline import Term

F64 = npt.NDArray[np.float64]
Mask = npt.NDArray[np.bool_]
#: `EWMA`'s weights, computed once for each window and decay rate and passed as a constant (3.4).
_weights = functools.cache(_kernels.ewma_weights)

#: Each built-in factor's kernel by operator, given the window and the term's parameters.
KERNELS: Mapping[str, Callable[[F64, Mapping[str, Any]], F64]] = {
    "Returns": lambda x, _: _kernels.window_returns(x),
    "SimpleMovingAverage": lambda x, _: _kernels.window_nanmean(x),
    "AverageDollarVolume": lambda x, _: _kernels.window_nansum_mean(x),
    "AverageTradedValue": lambda x, _: _kernels.window_nanmean(x),
    "AnnualizedVolatility": lambda x, p: _kernels.window_annualized_volatility(
        x, p["annualization_factor"]
    ),
    "RollingStd": lambda x, _: _kernels.window_nanstd(x, 1),
    "ExponentialWeightedMovingAverage": lambda x, p: _kernels.window_ewma(
        x, _weights(len(x), p["decay_rate"])
    ),
    "VWAP": lambda x, _: _kernels.window_vwap(x[0], x[1]),
    "RSI": lambda x, _: _kernels.window_rsi(x),
    "MaxDrawdown": lambda x, _: _kernels.window_max_drawdown(x),
    "rolling": lambda x, p: _rolling(x, p["how"], p["min_periods"]),
}
#: `nx.ops.rolling`'s operations (3.3) over the finite cells of a term's values.
ROLLING: Mapping[str, Callable[[F64], F64]] = {
    "mean": _kernels.window_nanmean,
    "sum": _kernels.window_nansum,
    "std": lambda x: _kernels.window_nanstd(x, 1),
    "min": _kernels.window_nanmin,
    "max": _kernels.window_nanmax,
    "median": _kernels.window_nanmedian,
}
#: Rows a factor reads beyond its W: `AnnualizedVolatility` takes W returns, so W + 1 prices.
EXTRA = {"AnnualizedVolatility": 1}


def _rolling(x: F64, how: str, min_periods: int) -> F64:
    """A rolling operation's value where the window holds `min_periods` finite cells, else NaN."""
    enough = np.count_nonzero(np.isfinite(x), axis=0) >= min_periods
    found: F64 = np.where(enough, ROLLING[how](x), np.nan)
    return found


def observed(op: str, x: F64) -> npt.NDArray[np.intp]:
    """Per column, the finite observations `min_periods` counts, in 3.4's unit (#868): the
    finite returns of `AnnualizedVolatility`, the pairs of `VWAP` (`x` the two windows stacked),
    the differences of two finite cells of `RSI`, the finite cells otherwise."""
    if op == "VWAP":
        kept = np.isfinite(x[0]) & np.isfinite(x[1])
    elif op == "AnnualizedVolatility":  # a return over a zero price, or overflowed, is left out
        with np.errstate(all="ignore"):
            kept = np.isfinite(x[1:] / x[:-1])
    elif op == "RSI":
        kept = np.isfinite(x[1:]) & np.isfinite(x[:-1])
    else:
        kept = np.isfinite(x)
    counted: npt.NDArray[np.intp] = kept.sum(axis=0)
    return counted


def rows(term: Term) -> int:
    """The window rows the term reads of each input."""
    size: int = dict(term.params)["window"]
    return size + EXTRA.get(term.op, 0)


#: The kernels that divide inside: the columns whose division has a zero divisor (5.4.1
#: `DivisionByZero`, #632), and `AnnualizedVolatility`'s returns that overflowed and are left
#: out (`InfiniteResult`, though the value may be finite).
ZERO: Mapping[str, Callable[[F64], Mask]] = {
    "Returns": _kernels.returns_zero,
    "AnnualizedVolatility": _kernels.daily_zero,
    "MaxDrawdown": _kernels.peak_zero,
    "VWAP": _kernels.vwap_zero,  # NaN by 3.4, counted all the same (#632)
    "RSI": _kernels.rsi_zero,  # 100 or NaN by 3.4, counted all the same
}
OVERFLOW: Mapping[str, Callable[[F64], Mask]] = {"AnnualizedVolatility": _kernels.daily_overflow}


def diagnosed(term: Term, windows: Sequence[F64]) -> tuple[F64, Mask, Mask]:
    """The term's values at the window's last row, and its cells to count once there (5.4.1):
    those with a zero divisor inside the kernel, and those whose overflow came out (as ±inf, made
    NaN) or left a return out. `AverageDollarVolume` reads `close * volume`, an overflowed product
    carried; `VWAP` the two windows stacked. An `inf` input cell is NaN before the kernel. A
    column with fewer observations than the term's `min_periods` is NaN (#868); its cells are
    counted as the kernel found them, as before."""
    cells = [np.where(np.isinf(w), np.nan, w) for w in windows]
    adv, vwap = term.op == "AverageDollarVolume", term.op == "VWAP"
    x = cells[0] * cells[1] if adv else np.stack(cells) if vwap else cells[0]
    params = dict(term.params)
    found = KERNELS[term.op](x, params)
    none = np.zeros(found.shape, dtype=bool)
    # `rolling` applies its own; the other factors without `min_periods` keep every column
    least = "min_periods" in params and term.op != "rolling"
    enough = observed(term.op, x) >= params["min_periods"] if least else ~none
    zero = ZERO[term.op](x) if term.op in ZERO else none
    infinite = np.isinf(found) | (OVERFLOW[term.op](x) if term.op in OVERFLOW else none)
    out: F64 = np.where(np.isinf(found) | ~enough, np.nan, found)
    return out, zero, infinite & ~zero


def value(term: Term, windows: Sequence[F64]) -> F64:
    """The term's values at the window's last row (`diagnosed`, without the counts)."""
    return diagnosed(term, windows)[0]
