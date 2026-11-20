"""#632: inside a built-in kernel only an input cell is skipped. An overflow is carried through the
kernel's own arithmetic and comparisons as IEEE 754 carries it, and the term's value is NaN when
±inf or NaN comes out (spec 5.4.1); a division by a zero is NaN whatever the zero's sign."""

from __future__ import annotations

import numpy as np
import pytest

from nexusbt.compute import _kernels
from nexusbt.compute._factors import diagnosed, value
from nexusbt.factors import RSI, VWAP, AverageDollarVolume, MaxDrawdown, RollingStd

pytestmark = pytest.mark.unit


def column(*cells: float) -> np.ndarray:
    return np.array(cells, dtype=np.float64)[:, None]


def at(term: object, *windows: np.ndarray) -> float:
    with np.errstate(all="ignore"):  # as the executor calls the kernels
        return float(value(term, list(windows))[0])  # type: ignore[arg-type]


def test_the_three_inputs_of_the_issue_are_nan() -> None:
    """`RollingStd` of [1e200, -1e200] squares to inf (was 0.0); `VWAP`'s 1e300 * 1e10 overflows
    (was 1e-10); `MaxDrawdown`'s peak of 0.0 or -0.0 divides by a zero (was NaN and -0.0)."""
    assert np.isnan(at(RollingStd(window=2), column(1e200, -1e200)))
    assert np.isnan(at(VWAP(window=2), column(1e300, 1.0), column(1e10, 1.0)))
    assert np.isnan(at(MaxDrawdown(window=3), column(-1.0, 0.0, -1.0)))
    assert np.isnan(at(MaxDrawdown(window=3), column(-1.0, -0.0, -1.0)))


def test_an_overflowed_divisor_or_bound_is_nan_not_a_wrong_number() -> None:
    """The inputs where a finite number came out that is not the formula's (#632 Decisions,
    third form): `VWAP`'s Σ volume (0.0 for 0.1), `RSI`'s overflowed `dn` (0.0 for about 1e-14)
    and overflowed `up` (100 for 66.67, from the fresh-context review), `zscore`'s std ([0, -0]
    for [1, -1]), `winsorize`'s lower bound (the first cell left uncut), and `winsorize(0, 1)`'s
    `inf * 0` bound: NaN, and `inf` from a cross-section kernel, so the executor counts
    `InfiniteResult` there."""
    assert np.isnan(at(VWAP(window=2), column(0.1, 0.1), column(1e308, 1e308)))
    assert np.isnan(at(RSI(window=3), column(1e308, -1e308, -1e308 + 1e292)))
    assert np.isnan(at(RSI(window=3), column(-1e308, 1e308, 0.0)))
    two, three = np.ones(2, bool), np.ones(3, bool)
    g2, g3 = np.zeros(2, np.int32), np.zeros(3, np.int32)
    with np.errstate(all="ignore"):
        scores, _ = _kernels.zscore(np.array([1e200, -1e200]), two, g2, np.arange(2))
        cut, _ = _kernels.winsorize(np.array([-1e308, 1e308, 1e308]), three, g3, 0.3, 0.9)
        whole, _ = _kernels.winsorize(np.array([-1e308, 1e308]), two, g2, 0.0, 1.0)
    for found in (scores, cut, whole):
        assert np.isinf(found).all(), found


def test_an_overflow_that_makes_nan_is_counted() -> None:
    """The fresh-context review's input: `AverageDollarVolume`'s products overflow to +inf and
    -inf, whose sum is NaN; that cell is counted `InfiniteResult` (`diagnosed`'s third part)."""
    term = AverageDollarVolume(window=2)
    with np.errstate(all="ignore"):
        found, zero, infinite = diagnosed(term, [column(1e300, -1e300), column(1e10, 1e10)])
    assert np.isnan(found).all()
    assert infinite.all()
    assert not zero.any()


def test_an_overflow_that_leads_to_a_finite_value_keeps_it() -> None:
    """The decision's two cases: `RSI` whose `up/dn` overflows is 100, as 3.4 gives for `dn = 0`;
    `MaxDrawdown` below a peak under 0, whose ratio overflows to -inf, keeps the finite maximum."""
    assert at(RSI(window=3), column(1.0, 1.0 - 2**-30, 1e300)) == 100.0  # 5e299 / 2**-31
    assert at(MaxDrawdown(window=2), column(-1e-300, -1e300)) == 0.0
