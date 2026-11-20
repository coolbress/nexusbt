"""The built-in factors of 3.4 (`nexusbt.factors`); each comes with its ticket.

A constructor builds the node only; `compute` holds its kernel, registered under the node's
operator name with the class `ADJUSTMENT` declares here (3.4, 5.3.3).
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from types import MappingProxyType

from ..contracts import ConfigError
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
        "ExponentialWeightedMovingAverage": "homogeneous of degree 1",
        "VWAP": "homogeneous of degree 1",
        "RSI": "homogeneous of degree 0",
        "MaxDrawdown": "homogeneous of degree 0",
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


def _ewma_refused(op: str, name: str, value: float, allowed: str, why: str) -> ConfigError:
    """3.4's `EWMA` row, 6.6 E16 (#666): the argument the person passed, and its range."""
    return ConfigError(
        what=f"{name}={value!r} is not a {name} {op} takes",
        where=f"{op}({name}=...)",
        why=why,
        fix=f"{name}= a finite number with {allowed}",
        more="spec 3.4 (the EWMA row)",
        layer=f"config — argument {name}={value!r}",
    )


def _finite(value: float) -> bool:
    try:
        return math.isfinite(value)
    except OverflowError:  # an int beyond float64, such as 10**400
        return False


#: Why a decay rate outside (0, 1] is refused (decision 2026-11-20, #666).
_RATE_WHY = (
    "a decay rate in (0, 1] gives weights in (0, 1], so their sum is positive and finite;"
    " any other decay rate is not a moving average"
)


class _EWMA:
    """3.4 `ExponentialWeightedMovingAverage(W, decay_rate, inputs)`, alias `EWMA`:
    `average(x, weights=decay_rate ** (W-1-i))`, any NaN -> NaN; the default input is
    `Price.close`, as for the other price-level factors (3.4). The `from_` forms give the
    decay rate as zipline's do. Each refuses an argument outside its range, finite only, when
    the term is built, naming the argument the person passed (E16; #666)."""

    def __call__(
        self, window: int, decay_rate: float, inputs: Inputs = None, *, mask: Filter | None = None
    ) -> Factor:
        if not (_finite(decay_rate) and 0.0 < float(decay_rate) <= 1.0):  # NaN, ±inf too
            raise _ewma_refused("EWMA", "decay_rate", decay_rate, "0 < decay_rate <= 1", _RATE_WHY)
        found = _price("close", inputs)
        return _node(Factor, "ExponentialWeightedMovingAverage", *found, window=window,
                     decay_rate=float(decay_rate), mask=mask)  # fmt: skip

    def _given(
        self,
        name: str,
        value: float,
        inside: Callable[[float], bool],
        allowed: str,
        rate: Callable[[float], float],
        window: int,
        inputs: Inputs,
        mask: Filter | None,
    ) -> Factor:
        """`EWMA.from_<name>(window, value)`: refused in the person's argument when it is not
        finite, outside its range, or gives a decay rate of 0.0 in float64 (#666, decision 7)."""
        op = f"EWMA.from_{name}"
        if not (_finite(value) and inside(value)):
            why = f"{_RATE_WHY}; {allowed} is the range that gives one"
            raise _ewma_refused(op, name, value, allowed, why)
        found = rate(value)
        if not 0.0 < found <= 1.0:
            why = f"{name}={value!r} gives decay_rate {found!r} in float64, and {_RATE_WHY}"
            raise _ewma_refused(op, name, value, allowed, why)
        return self(window, found, inputs, mask=mask)

    def from_span(
        self, window: int, span: float, inputs: Inputs = None, *, mask: Filter | None = None
    ) -> Factor:
        """`decay_rate = 1 - 2 / (span + 1)`, `span > 1`."""
        return self._given("span", span, lambda s: s > 1, "span > 1",
                           lambda s: 1.0 - 2.0 / (s + 1.0), window, inputs, mask)  # fmt: skip

    def from_halflife(
        self, window: int, halflife: float, inputs: Inputs = None, *, mask: Filter | None = None
    ) -> Factor:
        """`decay_rate = exp(log(0.5) / halflife)`, `halflife > 0`."""
        return self._given("halflife", halflife, lambda h: h > 0, "halflife > 0",
                           lambda h: math.exp(math.log(0.5) / h), window, inputs, mask)  # fmt: skip

    def from_center_of_mass(
        self,
        window: int,
        center_of_mass: float,
        inputs: Inputs = None,
        *,
        mask: Filter | None = None,
    ) -> Factor:
        """`decay_rate = 1 - 1 / (1 + center_of_mass)`, `center_of_mass > 0`."""
        return self._given("center_of_mass", center_of_mass, lambda c: c > 0, "center_of_mass > 0",
                           lambda c: 1.0 - 1.0 / (1.0 + c), window, inputs, mask)  # fmt: skip


ExponentialWeightedMovingAverage = EWMA = _EWMA()


def VWAP(window: int, *, mask: Filter | None = None) -> Factor:  # noqa: N802 - the 3.4 name
    """3.4 `VWAP(W)`: `sum(close * volume) / sum(volume)` over the rows where both are finite."""
    close, volume = BoundColumn.of("Price", "close"), BoundColumn.of("Price", "volume")
    return _node(Factor, "VWAP", close, volume, window=window, mask=mask)


def RSI(  # noqa: N802 - the 3.4 name
    window: int = 15, inputs: Inputs = None, *, mask: Filter | None = None
) -> Factor:
    """3.4 `RSI(W=15, inputs=[Price.close_tr])`: `100 - 100/(1 + up/dn)` over W - 1 changes."""
    return _node(Factor, "RSI", *_price("close_tr", inputs), window=window, mask=mask)


def MaxDrawdown(  # noqa: N802 - the 3.4 name
    window: int, inputs: Inputs = None, *, mask: Filter | None = None
) -> Factor:
    """3.4 `MaxDrawdown(W, inputs=[Price.close_tr])`: `max((cummax(x) - x) / cummax(x))`."""
    return _node(Factor, "MaxDrawdown", *_price("close_tr", inputs), window=window, mask=mask)


#: Each built-in factor's numerics class (5.3.10 2a): every kernel is of the arithmetic class;
#: `EWMA`'s power weights are the transcendental class, computed once outside the kernel.
NUMERICS: Mapping[str, str] = MappingProxyType(
    dict.fromkeys(ADJUSTMENT, "arithmetic")
    | {
        "ExponentialWeightedMovingAverage": "arithmetic (weights decay^k: transcendental,"
        " computed once outside the kernel)"
    }
)


def table() -> str:
    """`nx.describe(nx.factors)` (T1.10): the 12 built-in factors of 3.4, each with the input it
    reads when none is given, its adjustment class and its numerics class."""
    built = {
        "Returns(W)": Returns(2),
        "DailyReturns()": DailyReturns(),
        "SimpleMovingAverage(W), SMA": SMA(2),
        "ExponentialWeightedMovingAverage(W, decay_rate), EWMA": EWMA(2, 0.5),
        "AverageDollarVolume(W)": AverageDollarVolume(2),
        "AverageTradedValue(W, ccy=None)": AverageTradedValue(2),
        "AnnualizedVolatility(W=252, annualization_factor=252)": AnnualizedVolatility(),
        "RollingStd(W)": RollingStd(2),
        "VWAP(W)": VWAP(2),
        "RSI(W=15)": RSI(),
        "MaxDrawdown(W)": MaxDrawdown(2),
    }
    rows = [("factor", "default input", "adjustment class", "numerics class")]
    for name, term in built.items():
        read = ", ".join(f"Price.{dict(c.params)['column']}" for c in term.inputs)
        rows.append((name, read, ADJUSTMENT[term.op], NUMERICS[term.op]))
    rows.append(("Latest (col.latest)", "a column", "the column table", "-"))
    widths = [max(len(row[i]) for row in rows) for i in range(4)]
    lines = [" | ".join(map(str.ljust, row, widths)).rstrip() for row in rows]
    return "\n".join([lines[0], "-+-".join("-" * w for w in widths), *lines[1:]])
