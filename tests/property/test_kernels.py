"""P-KERNEL (spec 8.3, 5.3.10, INV-13): each built-in factor's kernel is the explicit left fold.

The oracle below spells every kernel of 3.4 and `nx.ops.rolling` (3.3) one column and one row
at a time, with numpy float64 scalars: sums are `acc = acc + x[r]` from 0.0 in ascending row
order (ADR-0019 definition A), over the finite cells for the NaN-skipping kernels and over
every cell for `EWMA` and `window_sum`, where a NaN makes the value NaN. A variance is two
passes; equal cells give a standard deviation of 0, a rule of the kernel (#523), not of 3.4.
The kernels the executor dispatches (`_factors.KERNELS`) and the registered `window_sum` must
give the same bits on random windows and NaN positions, and `EWMA`'s weights must come from the
compiled `pow` (the transcendental class, 5.3.10 2a). There is no fast path yet: the reference
is the only implementation (spec 10.0, M1 "P-KERNEL (reference)"), so fast = reference holds by
construction until one is added.
"""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Any

import numpy as np
import pytest
from hypothesis import example, given
from hypothesis import strategies as st

from nexusbt.compute import _elem, _kernels
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


Oracle = Callable[..., Any]
#: The oracles of picking kernels: their value is one of several candidates chosen by an order
#: (`fmax`, `fmin`, the middle of a sort), not computed from all of them. See `same_bits`.
PICKING: set[Oracle] = set()


def picking(oracle: Oracle) -> Oracle:
    PICKING.add(oracle)
    return oracle


@picking
def max_drawdown(c: list[Any]) -> Any:
    peak, worst = NAN, NAN
    for v in c:
        finite = v if np.isfinite(v) else NAN
        peak = np.fmax(peak, finite)
        worst = np.fmax(worst, (peak - finite) / peak)
    return worst


@picking
def median(c: list[Any]) -> Any:
    finite = sorted(v for v in c if np.isfinite(v))
    n = len(finite)
    return (finite[(n - 1) // 2] + finite[n // 2]) / 2 if n else NAN


@picking
def lowest(c: list[Any]) -> Any:
    """The smallest finite cell by `fmin` in row order; NaN when none."""
    low = NAN
    for v in c:
        low = np.fmin(low, v if np.isfinite(v) else NAN)
    return low


@picking
def highest(c: list[Any]) -> Any:
    return -lowest([-v for v in c])


#: `nx.ops.rolling`'s operations, each over a column's cells.
ROLLING_ORACLES: dict[str, Oracle] = {
    "mean": mean, "sum": lambda c: fold(c)[0], "std": lambda c: std(c, 1),
    "min": lowest, "max": highest, "median": median,
}  # fmt: skip


def rolling(c: list[Any], how: str, min_periods: int) -> Any:
    if sum(bool(np.isfinite(v)) for v in c) < min_periods:
        return NAN
    return ROLLING_ORACLES[how](c)


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
    "MaxDrawdown": picking(lambda c, _: max_drawdown(c)),
    "rolling": lambda c, p: rolling(c, p["how"], p["min_periods"]),
}


def picks(op: str, params: dict[str, Any]) -> bool:
    """Whether the kernel's value is picked rather than computed (`PICKING`)."""
    return (ROLLING_ORACLES[params["how"]] if op == "rolling" else ORACLES[op]) in PICKING


def same_bits(found: Any, expected: Any, *, zero_sign: bool = True) -> bool:
    """Equal bits, NaN where NaN (a NaN's payload is not a value). With `zero_sign=False`, a
    cell where both sides are zero matches whatever their signs; every other cell keeps its bits.

    Only picking kernels take `zero_sign=False` (`picks`). Which of two equal zeros a pick
    returns (`fmax(-0.0, 0.0)`, the middle of a sort holding 0.0 and -0.0) is left open by
    IEEE 754 and by spec 3.4 and 5.3.10, and two correct implementations may answer
    differently: P-KERNEL failed so on an x86 runner for `MaxDrawdown` (run 44656168938, the
    oracle's scalar `fmax` against the kernel's array `fmax`), and for the median wherever the
    oracle's stable `sorted` and the kernel's `np.sort` place -0.0 and 0.0 differently (seen on
    arm64; #254's Decisions, 2026-11-20). The value hash does not see the sign either: TDS 4.5
    writes an `f64` cell as "IEEE-754 bits, 8 bytes little-endian (-0.0 normalised to +0.0;
    ...)" (its minus sign is U+2212 there). So this test does not ask for that sign.
    Computing kernels (sums, means, standard deviations, ratios) keep the signed-zero comparison.
    """
    found, expected = np.asarray(found, dtype=F), np.asarray(expected, dtype=F)
    nan = np.isnan(found)
    if not np.array_equal(nan, np.isnan(expected)):
        return False
    keep = ~nan if zero_sign else ~nan & ~((found == 0) & (expected == 0))
    return bool(np.array_equal(found[keep].view(np.int64), expected[keep].view(np.int64)))


class Draws:
    """A stand-in for `st.data()` in an `@example` (which cannot carry its draws): the draw of
    an integer gives `min_periods`, the draw of a window the same fixed cells each time, so
    every kernel gets the fixed column."""

    def __init__(self, min_periods: int, cells: list[float]) -> None:
        self.min_periods, self.cells = min_periods, cells

    def draw(self, strategy: Any) -> Any:
        return self.min_periods if "integers" in repr(strategy) else list(self.cells)


#: The inputs P-KERNEL failed on, 2026-11-20 (#254's Decisions): the `MaxDrawdown` column of
#: an x86 runner (run 44656168938, as hypothesis shrank it), and a `rolling` median of zeros on
#: arm64, whose full column was not kept: `[0.0, -0.0, 0.0]` is the shortest column of zeros
#: whose median sign differs between the kernel and the oracle there.
MAX_DRAWDOWN_TIE = Draws(1, [np.nan, -1.0, 0.1, np.nan])
MEDIAN_OF_ZEROS = Draws(1, [0.0, -0.0, 0.0])


def test_every_kernel_has_an_oracle() -> None:
    """A kernel added to the executor or to the registered table gets its oracle here."""
    assert set(ORACLES) == set(KERNELS)
    assert set(REGISTERED) - {"window_sum"} <= set(KERNELS)  # `window_sum`: checked below


def test_picking_is_the_order_choosing_kernels() -> None:
    """The kernels whose value is picked: `MaxDrawdown` and `rolling` min, max and median."""
    picked = {op for op in KERNELS if op != "rolling" and picks(op, {})}
    picked |= {f"rolling.{how}" for how in ROLLING if picks("rolling", {"how": how})}
    assert picked == {"MaxDrawdown", "rolling.min", "rolling.max", "rolling.median"}


def test_same_bits_without_zero_sign_still_compares_the_rest() -> None:
    """Only a zero on both sides drops its sign; NaN and every other bit still count."""
    assert same_bits([0.0, 1.0], [-0.0, 1.0], zero_sign=False)
    assert not same_bits([0.0, 1.0], [-0.0, 1.0])
    assert not same_bits([0.0], [5e-324], zero_sign=False)  # the smallest subnormal is not 0
    assert not same_bits([np.nan], [0.0], zero_sign=False)
    assert not same_bits([1.0], [np.nextafter(1.0, 2.0)], zero_sign=False)


def test_ewma_weights_use_the_compiled_pow(monkeypatch: pytest.MonkeyPatch) -> None:
    """5.3.10 2a: the weights go through `_elem.power`, the one compiled element function."""
    calls = []
    compiled = _elem.power

    def spy(base: Any, exponent: Any) -> Any:
        calls.append(len(base))
        return compiled(base, exponent)

    monkeypatch.setattr(_elem, "power", spy)
    _kernels.ewma_weights(7, 0.3)
    assert calls == [7]


@given(
    rows=st.integers(1, 30),
    cols=st.integers(1, 4),
    data=st.data(),
    factor=st.floats(1.0, 400.0),
    rate=st.floats(0.01, 0.99),
    how=st.sampled_from(sorted(ROLLING)),
)
@example(rows=4, cols=1, data=MAX_DRAWDOWN_TIE, factor=1.0, rate=0.5, how="max")
@example(rows=3, cols=1, data=MEDIAN_OF_ZEROS, factor=1.0, rate=0.5, how="median")
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
        assert same_bits(found, expected, zero_sign=not picks(op, params)), (
            op, x.tolist(), found, expected,
        )  # fmt: skip
    x = window(rows)  # `window_sum`: every cell in row order, a NaN making the value NaN
    expected = [functools.reduce(lambda acc, v: acc + v, map(F, x[:, j]), F(0.0))
                for j in range(cols)]  # fmt: skip
    assert same_bits(REGISTERED["window_sum"].kernel(x), expected), x.tolist()
