"""The built-in factors of 3.4 (`nexusbt.factors`); each comes with its ticket.

A constructor builds the node only; `compute` holds its kernel, registered under the node's
operator name with the class `ADJUSTMENT` declares here (3.4, 5.3.3).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from types import MappingProxyType

from ._terms import BoundColumn, Factor, Filter, _node

Inputs = Sequence[BoundColumn | Factor] | None

#: Each built-in factor's adjustment class by its operator name, in 3.4's words (5.3.3).
#: `DailyReturns` is a `Returns` node.
ADJUSTMENT: Mapping[str, str] = MappingProxyType(
    {
        "Returns": "homogeneous of degree 0",
        "SimpleMovingAverage": "homogeneous of degree 1",
        "AverageDollarVolume": "invariant",
        "AverageTradedValue": "invariant",
        "AnnualizedVolatility": "homogeneous of degree 0",
        "RollingStd": "homogeneous of degree 1",
    }
)


def _price(column: str, inputs: Inputs) -> Sequence[BoundColumn | Factor]:
    return [BoundColumn.of("Price", column)] if inputs is None else inputs


def Returns(  # noqa: N802 - the 3.4 name
    window: int, inputs: Inputs = None, *, mask: Filter | None = None
) -> Factor:
    """3.4 `Returns(W, inputs=[Price.close_tr])`: `x[-1]/x[0] - 1`."""
    return _node(Factor, "Returns", *_price("close_tr", inputs), window=window, mask=mask)


def DailyReturns(inputs: Inputs = None, *, mask: Filter | None = None) -> Factor:  # noqa: N802
    """3.4 `DailyReturns()` = `Returns(2)`."""
    return Returns(2, inputs, mask=mask)


def SimpleMovingAverage(  # noqa: N802 - the 3.4 name
    window: int, inputs: Inputs = None, *, mask: Filter | None = None
) -> Factor:
    """3.4 `SimpleMovingAverage(W, inputs=[Price.close])`: the mean of the finite cells."""
    found = _price("close", inputs)
    return _node(Factor, "SimpleMovingAverage", *found, window=window, mask=mask)


SMA = SimpleMovingAverage


def AverageDollarVolume(window: int, *, mask: Filter | None = None) -> Factor:  # noqa: N802
    """3.4 `AverageDollarVolume(W)`: `nansum(close * volume) / W`."""
    close, volume = BoundColumn.of("Price", "close"), BoundColumn.of("Price", "volume")
    return _node(Factor, "AverageDollarVolume", close, volume, window=window, mask=mask)


def AverageTradedValue(  # noqa: N802 - the 3.4 name
    window: int, ccy: str | None = None, *, mask: Filter | None = None
) -> Factor:
    """3.4 `AverageTradedValue(W, ccy=None)`: `nanmean(value_traded)`, `.to(ccy)` with `ccy`."""
    value = BoundColumn.of("Price", "value_traded")
    found = _node(Factor, "AverageTradedValue", value, window=window, mask=mask)
    return found if ccy is None else found.to(ccy)


def AnnualizedVolatility(  # noqa: N802 - the 3.4 name
    window: int = 252,
    annualization_factor: float = 252,
    inputs: Inputs = None,
    *,
    mask: Filter | None = None,
) -> Factor:
    """3.4 `AnnualizedVolatility(W=252, annualization_factor=252, inputs=[Price.close_tr])`:
    the standard deviation (ddof 0) of the W daily returns, so W + 1 prices, times `sqrt(a)`."""
    found = _price("close_tr", inputs)
    return _node(Factor, "AnnualizedVolatility", *found, window=window,
                 annualization_factor=float(annualization_factor), mask=mask)  # fmt: skip


def RollingStd(  # noqa: N802 - the 3.4 name
    window: int, inputs: Inputs = None, *, mask: Filter | None = None
) -> Factor:
    """3.4 `RollingStd(W, inputs)`: the standard deviation (ddof 1) of the finite cells; the
    default input is `Price.close`, as for the other price-level factors (3.4)."""
    return _node(Factor, "RollingStd", *_price("close", inputs), window=window, mask=mask)
