"""P-KERNEL (spec 8.3, 5.3.10, INV-13): each built-in factor's kernel is the explicit left fold.

The oracle below spells every kernel of 3.4 and `nx.ops.rolling` (3.3) one column and one row
at a time, with numpy float64 scalars: sums are `acc = acc + x[r]` from 0.0 in ascending row
order over the finite cells (ADR-0019 definition A), a variance is two passes, and `EWMA`'s
weights come from the same compiled `pow` (the transcendental class, 5.3.10 2a). The kernels
the executor dispatches (`_factors.KERNELS`) must give the same bits on random windows and NaN
positions. There is no fast path yet: the reference is the only implementation (spec 10.0, M1
"P-KERNEL (reference)"), so fast = reference holds by construction until one is added.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from nexusbt.compute import _elem
from nexusbt.compute._factors import KERNELS, ROLLING
from nexusbt.compute._kernels_ref import REGISTERED

pytestmark = pytest.mark.property

F = np.float64
NAN = F(np.nan)
#: Finite values, ties and zeros among them (the equal-cells rule of a std, a zero divisor),
#: and NaN at random positions.
CELL = st.one_of(
    st.floats(-1e3, 1e3, allow_nan=False), st.sampled_from([0.0, 0.1, 1.0, 2.0]), st.just(np.nan)
)


def fold(cells: list[Any]) -> tuple[Any, int]:
    """The left fold of the finite cells in row order, from 0.0, and their count."""
    acc, n = F(0.0), 0
    for v in cells:
        if np.isfinite(v):
            acc, n = acc + v, n + 1
    return acc, n


def mean(cells: list[Any]) -> Any:
    acc, n = fold(cells)
    return acc / n if n else NAN


def std(cells: list[Any], ddof: int) -> Any:
    acc, n = fold(cells)
    if n <= ddof:
        return NAN
    finite = [v for v in cells if np.isfinite(v)]
    if min(finite) == max(finite):
        return F(0.0)
    m = acc / n
    squares, _ = fold([(v - m) * (v - m) for v in finite])
    return np.sqrt(squares / (n - ddof))


def returns(c: list[Any]) -> Any:
    return c[-1] / c[0] - 1.0


def annualized(c: list[Any], factor: float) -> Any:
    return std([c[i + 1] / c[i] - 1.0 for i in range(len(c) - 1)], 0) * np.sqrt(F(factor))


def ewma(c: list[Any], rate: float) -> Any:
    weights = [_elem.power(F(rate), F(len(c) - 1 - i)) for i in range(len(c))]
    acc, total = F(0.0), F(0.0)
    for w in weights:
        total = total + w
    for v, w in zip(c, weights, strict=True):
        acc = acc + v * w  # a NaN cell makes the value NaN
    return acc / total


def vwap(close: list[Any], volume: list[Any]) -> Any:
    paid, traded, n = F(0.0), F(0.0), 0
    for c, v in zip(close, volume, strict=True):
        if np.isfinite(c) and np.isfinite(v):
            if np.isfinite(c * v):
                paid, n = paid + c * v, n + 1
            traded = traded + v
    return paid / traded if n and traded != 0 else NAN


def rsi(c: list[Any]) -> Any:
    d = [c[i + 1] - c[i] for i in range(len(c) - 1)]
    up, dn = mean([np.maximum(x, 0.0) for x in d]), np.abs(mean([np.minimum(x, 0.0) for x in d]))
    return 100.0 - 100.0 / (1.0 + up / dn)


def max_drawdown(c: list[Any]) -> Any:
    peak, worst = NAN, NAN
    for v in c:
        finite = v if np.isfinite(v) else NAN
        peak = np.fmax(peak, finite)
        worst = np.fmax(worst, (peak - finite) / peak)
    return worst


def median(c: list[Any]) -> Any:
    finite = sorted(v for v in c if np.isfinite(v))
    n = len(finite)
    return (finite[(n - 1) // 2] + finite[n // 2]) / 2 if n else NAN


def rolling(c: list[Any], how: str, min_periods: int) -> Any:
    if sum(bool(np.isfinite(v)) for v in c) < min_periods:
        return NAN
    finite = [v for v in c if np.isfinite(v)]
    found: dict[str, Callable[[], Any]] = {
        "mean": lambda: mean(c),
        "sum": lambda: fold(c)[0],
        "std": lambda: std(c, 1),
        "min": lambda: min(finite) if finite else NAN,
        "max": lambda: max(finite) if finite else NAN,
        "median": lambda: median(c),
    }
    return found[how]()


#: Each kernel's oracle for one column, given the column's cells and the term's parameters.
ORACLES: dict[str, Callable[[Any, dict[str, Any]], Any]] = {
    "Returns": lambda c, _: returns(c),
    "SimpleMovingAverage": lambda c, _: mean(c),
    "AverageDollarVolume": lambda c, _: fold(c)[0] / len(c),
    "AverageTradedValue": lambda c, _: mean(c),
    "AnnualizedVolatility": lambda c, p: annualized(c, p["annualization_factor"]),
    "RollingStd": lambda c, _: std(c, 1),
    "ExponentialWeightedMovingAverage": lambda c, p: ewma(c, p["decay_rate"]),
    "VWAP": lambda c, _: vwap(*c),
    "RSI": lambda c, _: rsi(c),
    "MaxDrawdown": lambda c, _: max_drawdown(c),
    "rolling": lambda c, p: rolling(c, p["how"], p["min_periods"]),
}


def same_bits(found: Any, expected: Any) -> bool:
    """Equal bits, NaN where NaN (a NaN's payload is not a value)."""
    found, expected = np.asarray(found, dtype=F), np.asarray(expected, dtype=F)
    nan = np.isnan(found)
    if not np.array_equal(nan, np.isnan(expected)):
        return False
    return bool(np.array_equal(found[~nan].view(np.int64), expected[~nan].view(np.int64)))


def test_every_kernel_has_an_oracle() -> None:
    """A kernel added to the executor or to the registered table gets its oracle here."""
    assert set(ORACLES) == set(KERNELS)
    assert set(REGISTERED) - {"window_sum"} <= set(KERNELS)


@given(
    rows=st.integers(1, 30),
    cols=st.integers(1, 4),
    data=st.data(),
    factor=st.floats(1.0, 400.0),
    rate=st.floats(0.01, 0.99),
    how=st.sampled_from(sorted(ROLLING)),
)
def test_P_KERNEL_reference_is_left_fold(  # noqa: N802 - spec 10.1's name
    rows: int, cols: int, data: st.DataObject, factor: float, rate: float, how: str
) -> None:
    def window(n: int) -> Any:
        cells = data.draw(st.lists(CELL, min_size=n * cols, max_size=n * cols))
        return np.array(cells, dtype=F).reshape(n, cols)

    min_periods = data.draw(st.integers(1, rows))
    params = {"annualization_factor": factor, "decay_rate": rate, "how": how,
              "min_periods": min_periods}  # fmt: skip
    for op, kernel in KERNELS.items():
        x = np.stack([window(rows), window(rows)]) if op == "VWAP" else window(rows)
        with np.errstate(all="ignore"):  # IEEE results, as the executor computes them
            found = kernel(x, params)
            columns = [x[:, :, j].tolist() if op == "VWAP" else x[:, j].tolist()
                       for j in range(cols)]  # fmt: skip
            expected = [ORACLES[op]([[F(v) for v in s] for s in c] if op == "VWAP"
                                    else [F(v) for v in c], params) for c in columns]  # fmt: skip
        assert same_bits(found, expected), (op, x.tolist(), found, expected)
