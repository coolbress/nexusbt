"""#632 Decisions (third form): a term's value in a cell is a finite number only where that number
is the formula's value (3.4, 5.4.2); where the float computation overflowed and can no longer give
it, the value is NaN. Each arithmetic kernel on inputs large enough to overflow: a finite result
equals the formula in exact arithmetic (`Decimal` of 2000 digits, which holds every float64 and
their sums and products exactly, rounding only a division or a root; its exponent does not
overflow)
within a relative 1e-9, and anything else is NaN. Underflow is not covered (#43)."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from decimal import Context, Decimal, localcontext
from typing import Any

import numpy as np
import pytest

import nexusbt as nx
from nexusbt.compute import _kernels
from nexusbt.compute._factors import value
from nexusbt.factors import (
    EWMA,
    RSI,
    VWAP,
    AnnualizedVolatility,
    AverageDollarVolume,
    AverageTradedValue,
    MaxDrawdown,
    Returns,
    RollingStd,
    SimpleMovingAverage,
)

pytestmark = pytest.mark.unit

CTX = Context(prec=2000, Emax=10**6, Emin=-(10**6))
D = Sequence[Decimal]
#: The largest finite float64: a daily return beyond it is `DailyReturns`' NaN (3.4).
BIG = Decimal(float(np.finfo(np.float64).max))


def dec(cells: Sequence[float]) -> list[Decimal]:
    return [Decimal(c) for c in cells]  # each float exactly


def mean(x: D) -> Decimal:
    return CTX.divide(sum(x, Decimal(0)), Decimal(len(x)))


def std(x: D, ddof: int) -> Decimal:
    m = mean(x)
    return CTX.sqrt(CTX.divide(sum(((v - m) ** 2 for v in x), Decimal(0)), Decimal(len(x) - ddof)))


def returns(x: D) -> Decimal | None:
    return None if x[0] == 0 else CTX.divide(x[-1], x[0]) - 1


def annualized(x: D, a: float) -> Decimal:
    daily = [CTX.divide(x[i + 1], x[i]) - 1 for i in range(len(x) - 1) if x[i] != 0]
    kept = [r for r in daily if abs(r) <= BIG]  # an overflowed return is NaN, left out
    return std(kept, 0) * CTX.sqrt(Decimal(a))


def vwap(close: D, volume: D) -> Decimal:
    paid = sum((c * v for c, v in zip(close, volume, strict=True)), Decimal(0))
    return CTX.divide(paid, sum(volume, Decimal(0)))


def rsi(x: D) -> Decimal:
    d = [x[i + 1] - x[i] for i in range(len(x) - 1)]
    up, dn = mean([max(v, Decimal(0)) for v in d]), abs(mean([min(v, Decimal(0)) for v in d]))
    return Decimal(100) if dn == 0 else 100 - CTX.divide(Decimal(100), 1 + CTX.divide(up, dn))


def max_drawdown(x: D) -> Decimal | None:
    peaks = [max(x[: i + 1]) for i in range(len(x))]
    if any(p == 0 for p in peaks):
        return None  # a division by a zero
    return max(CTX.divide(p - v, p) for p, v in zip(peaks, x, strict=True))


def ewma(x: D, rate: float) -> Decimal:
    w = [Decimal(float(v)) for v in _kernels.ewma_weights(len(x), rate)]  # the kernel's weights
    return CTX.divide(sum((v * u for v, u in zip(x, w, strict=True)), Decimal(0)), sum(w))


def quantile(x: D, q: float) -> Decimal:
    s, at = sorted(x), Decimal(q) * (len(x) - 1)  # numpy's "linear"
    i = int(at)
    return s[i] if i + 1 == len(s) else s[i] + (s[i + 1] - s[i]) * (at - i)


Exact = Callable[..., Any]
#: (name, the kernel's values made as the executor makes them, the formula, the inputs)
CASES: list[tuple[str, Callable[..., Any], Exact, tuple[list[float], ...]]] = []


def window(term: Any) -> Callable[..., Any]:
    def run(*cols: list[float]) -> Any:
        return value(term, [np.array(c, dtype=np.float64)[:, None] for c in cols])

    return run


def section(name: str, *args: Any) -> Callable[..., Any]:
    def run(x: list[float]) -> Any:
        n = len(x)
        out, _ = getattr(_kernels, name)(np.array(x), np.ones(n, bool), np.zeros(n, np.int32),
                                          *(args or (np.arange(n),)))  # fmt: skip
        return np.where(np.isinf(out), np.nan, out)  # the executor's 5.4.1

    return run


Cells = tuple[list[float], ...]


def case(name: str, kernel: Callable[..., Any], exact: Exact, *inputs: Cells) -> None:
    CASES.extend((name, kernel, exact, cells) for cells in inputs)


case("Returns", window(Returns(2)), returns, ([1e-300, 1e300],), ([1e300, 1e-300],), ([0.0, 5.0],))
BIGS = ([1e308, 1e308],), ([1e308, -1e308, 1e308],), ([1e200, -1e200, 3.0],)
case("SimpleMovingAverage", window(SimpleMovingAverage(2)), mean, *BIGS[:1])
case("SimpleMovingAverage(3)", window(SimpleMovingAverage(3)), mean, *BIGS[1:])
case("AverageTradedValue", window(AverageTradedValue(2)), mean, *BIGS[:1])
for how, exact in (
    ("mean", mean),
    ("sum", lambda x: sum(x, Decimal(0))),
    ("std", lambda x: std(x, 1)),
    ("median", lambda x: quantile(x, 0.5)),
):
    rolled = getattr(nx.ops.rolling(nx.Price.close.latest, 2, 1), how)()
    case(f"rolling.{how}", window(rolled), exact, *BIGS[:1])
    rolled3 = getattr(nx.ops.rolling(nx.Price.close.latest, 3, 1), how)()
    case(f"rolling(3).{how}", window(rolled3), exact, *BIGS[1:])  # fmt: skip
case("RollingStd", window(RollingStd(2)), lambda x: std(x, 1),
     ([1e200, -1e200],), ([1e308, 1.5e308],), ([1e308, 1e308],))  # fmt: skip
case("AnnualizedVolatility", window(AnnualizedVolatility(2, 252)), lambda x: annualized(x, 252),
     ([1e-300, 1e300, 1e300],), ([1.0, 1e200, -1e200],), ([1.0, 0.0, 2.0],))  # fmt: skip
case("VWAP", window(VWAP(2)), vwap, ([1e300, 1.0], [1e10, 1.0]), ([0.1, 0.1], [1e308, 1e308]),
     ([1e200, 2e200], [1e200, 1e100]))  # fmt: skip
case("RSI", window(RSI(3)), rsi, ([1.0, 1.0 - 2**-30, 1e300],), ([-1e308, 1e308, 1e308],),
     ([1e308, -1e308, 1e308],), ([1e308, -1e308, -1e308 + 1e292],),
     ([-1e308, 1e308, 0.0],))  # fmt: skip
case("MaxDrawdown", window(MaxDrawdown(3)), max_drawdown, ([-1.0, 0.0, -1.0],),
     ([-1.0, -0.0, -1.0],), ([1e308, -1e308, 0.5],), ([-1e-300, -1e300, -2e300],))  # fmt: skip
case("EWMA", window(EWMA(3, 0.5)), lambda x: ewma(x, 0.5), ([1e308, 1e308, 1e308],),
     ([1e308, -1e308, 1e308],))  # fmt: skip
case("EWMA decay 2", window(EWMA(3, 2.0)), lambda x: ewma(x, 2.0), ([1e308, -1e308, 1e308],))
case("AverageDollarVolume", window(AverageDollarVolume(2)),
     lambda c, v: mean([a * b for a, b in zip(c, v, strict=True)]),
     ([1e200, 1e200], [1e200, 1e100]), ([1e154, 1e154], [1e154, 1e154]),
     ([1e300, 1.0], [1e-10, 1.0]), ([1e300, -1e300], [1e10, 1e10]))  # fmt: skip
case("zscore", section("zscore"), lambda x: [CTX.divide(v - mean(x), std(x, 0)) for v in x],
     ([1e200, -1e200],), ([1e308, 1.5e308],), ([1e308, -1e308, 0.0],))  # fmt: skip
case("demean", section("demean"), lambda x: [v - mean(x) for v in x],
     ([1e308, 1e308, -1e308],), ([1e308, -1e308],))  # fmt: skip
for low, high in ((0.3, 0.9), (0.0, 1.0)):
    case(f"winsorize({low}, {high})", section("winsorize", low, high),
         lambda x, lo=low, hi=high: [min(max(v, quantile(x, lo)), quantile(x, hi)) for v in x],
         ([-1e308, 1e308, 1e308],), ([-1e308, 1e308],))  # fmt: skip


@pytest.mark.parametrize(("name", "kernel", "exact", "cells"), CASES,
                         ids=[f"{c[0]}-{i}" for i, c in enumerate(CASES)])  # fmt: skip
def test_a_finite_result_is_the_formula_s_value(
    name: str, kernel: Callable[..., Any], exact: Exact, cells: tuple[list[float], ...]
) -> None:
    with np.errstate(all="ignore"):
        found = np.atleast_1d(np.asarray(kernel(*cells), dtype=np.float64))
    with localcontext(CTX):  # `+`, `-` and `*` too, not only CTX's own methods
        expected = exact(*(dec(c) for c in cells))
    expected = expected if isinstance(expected, list) else [expected]
    for got, want in zip(found.tolist(), expected, strict=True):
        if np.isnan(got):
            continue  # the float computation could not give the formula's value
        assert want is not None, (name, cells, got)  # a division by a zero is NaN
        assert abs(Decimal(got) - want) <= abs(want) * Decimal("1e-9"), (name, cells, got, want)
