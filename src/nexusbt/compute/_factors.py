"""The built-in factors of 3.4 at one row: each term's windows in, its `(N,)` values out.

The kernels are `_kernels`' (registered with their classes in `_kernels_ref.REGISTERED`); this
module picks one by the term's operator and passes the term's parameters. An `inf` cell or
result is NaN (5.4.1, "`inf` is turned into NaN and counted"): a window's `inf` cell follows its
factor's NaN rule of 3.4. The executor makes every term's `inf` NaN where it stores the row
(#536), so the result's rule here is the same one, applied again with the same value; a window's
column cells come from the block and still pass through here. The count is #249's.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

import numpy as np
import numpy.typing as npt

from nexusbt.compute import _kernels
from nexusbt.pipeline import Term

F64 = npt.NDArray[np.float64]

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
}
#: Rows a factor reads beyond its W: `AnnualizedVolatility` takes W returns, so W + 1 prices.
EXTRA = {"AnnualizedVolatility": 1}


def rows(term: Term) -> int:
    """The window rows the term reads of each input."""
    size: int = dict(term.params)["window"]
    return size + EXTRA.get(term.op, 0)


def value(term: Term, windows: Sequence[F64]) -> F64:
    """The term's values at the window's last row; `AverageDollarVolume` reads `close * volume`."""
    x = windows[0] * windows[1] if term.op == "AverageDollarVolume" else windows[0]
    found = KERNELS[term.op](np.where(np.isinf(x), np.nan, x), dict(term.params))
    out: F64 = np.where(np.isinf(found), np.nan, found)
    return out
