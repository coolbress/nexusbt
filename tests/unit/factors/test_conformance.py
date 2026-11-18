"""The built-in factors against the 3.4 table (T1.9): each row's default input, missing values,
minimum observations and warm-up, computed by the reference executor; and the class each term
declares in `pipeline` is the class its kernel is registered with in `compute` (5.3.3)."""

from __future__ import annotations

import math

import numpy as np
import pytest

from nexusbt import factors
from nexusbt.compute._executor import execute
from nexusbt.compute._kernels_ref import REGISTERED
from nexusbt.data._block import MarketBlock
from nexusbt.pipeline import BoundColumn, Term, graph_hash
from nexusbt.pipeline.factors import ADJUSTMENT

pytestmark = pytest.mark.unit

NAN, INF = math.nan, math.inf
#: Each built-in factor of this ticket, built with 3.4's defaults.
BUILT = {
    "Returns": factors.Returns(21),
    "DailyReturns": factors.DailyReturns(),
    "SimpleMovingAverage": factors.SMA(20),
    "AverageDollarVolume": factors.AverageDollarVolume(20),
    "AverageTradedValue": factors.AverageTradedValue(20),
    "AnnualizedVolatility": factors.AnnualizedVolatility(),
    "RollingStd": factors.RollingStd(20),
}


Spans = list[tuple[int, int]] | None


def run(term: Term, spans: Spans = None, **columns: list[float]) -> list[float]:
    """`term` at every row of one instrument whose columns are `columns`, each cell on time."""
    n = len(next(iter(columns.values())))
    dates = np.datetime64("2020-01-01") + np.arange(n).astype("timedelta64[D]")
    ready = (dates + np.timedelta64(16, "h")).astype("datetime64[us]")
    values = {k: np.array(v, dtype=np.float64)[:, None] for k, v in columns.items()}
    exists, status = np.ones((n, 1), bool), np.zeros((n, 1), np.int8)

    def read(first: int, last: int) -> MarketBlock:
        s = slice(first, last + 1)
        part = {k: v[s] for k, v in values.items()}
        return MarketBlock("XX", dates[s], 0, ("A",), part, exists[s], status[s], ready[s, None])

    found = execute([term], range(n), spans or [(0, n - 1)], read, ready)
    values_found: list[float] = found[graph_hash(term)]["value"].to_pylist()
    return values_found


def column(term: Term, i: int = 0) -> str:
    found: str = dict(term.inputs[i].params)["column"]
    return found


def same(found: list[float], expected: list[float]) -> None:
    assert found == pytest.approx(expected, abs=5e-7, nan_ok=True)


def test_factor_classes_match_registered_kernels() -> None:
    """#242, Decisions 2026-11-18: a term's class in `pipeline` = its kernel's in `compute`."""
    assert {term.op for term in BUILT.values()} == set(ADJUSTMENT)
    for name, term in BUILT.items():
        assert ADJUSTMENT[term.op] == REGISTERED[term.op].adjustment, name
    assert graph_hash(factors.DailyReturns()) == graph_hash(factors.Returns(2))  # the same node
    assert factors.SMA is factors.SimpleMovingAverage


def test_returns_default_is_close_tr() -> None:
    """3.4 [RV-I02]: the return family reads `Price.close_tr`, not the split-only `close`."""
    for term in (factors.Returns(2), factors.DailyReturns(), factors.AnnualizedVolatility(2)):
        assert column(term) == "close_tr"
    same(run(factors.Returns(2), close=[100, 50], close_tr=[100, 110]), [NAN, 0.1])


def test_returns_nan_rule() -> None:
    """`x[-1]/x[0] - 1`; either end NaN -> NaN, a NaN inside is not read; warm-up W-1."""
    same(run(factors.Returns(3), close_tr=[100, NAN, 110, NAN, 121]), [NAN, NAN, 0.1, NAN, 0.1])


def test_daily_returns_nan_rule() -> None:
    """`Returns(2)`; warm-up 1."""
    found = run(factors.DailyReturns(), close_tr=[100, 110, NAN, 121, 133.1])
    same(found, [NAN, 0.1, NAN, NAN, 0.1])


def test_simple_moving_average_nan_rule() -> None:
    """`nanmean` of `close`; NaN left out, all NaN -> NaN, minimum 1; warm-up W-1."""
    assert column(factors.SMA(3)) == "close"
    found = run(factors.SMA(3), close=[1, NAN, 3, 5, NAN, NAN, NAN])
    same(found, [NAN, NAN, 2.0, 4.0, 4.0, 5.0, NAN])


def test_average_dollar_volume_nan_rule() -> None:
    """`nansum(close * volume) / W`; a NaN counts as 0, minimum 0 (all NaN -> 0); warm-up W-1."""
    term = factors.AverageDollarVolume(2)
    assert (column(term, 0), column(term, 1)) == ("close", "volume")
    found = run(term, close=[10, NAN, 12, 11, 10], volume=[100, 300, NAN, 200, 500])
    same(found, [NAN, 500.0, 0.0, 1100.0, 3600.0])


def test_average_traded_value_nan_rule() -> None:
    """`nanmean(value_traded)`; NaN left out, minimum 1 (all NaN -> NaN); warm-up W-1."""
    assert column(factors.AverageTradedValue(2)) == "value_traded"
    found = run(factors.AverageTradedValue(2), value_traded=[1000, NAN, NAN, 3000, 5000])
    same(found, [NAN, 1000.0, NAN, 3000.0, 4000.0])


def test_annualized_volatility_nan_rule() -> None:
    """`nanstd(DailyReturns, ddof=0) * sqrt(a)` over W returns; NaN left out, minimum 1;
    warm-up W, also when the W + 1 prices reach across a chunk's first row."""
    prices = [100, 110, 99, NAN, 108.9]
    expected = [NAN, NAN, NAN, 0.1 * math.sqrt(252), 0.0]
    same(run(factors.AnnualizedVolatility(3), close_tr=prices), expected)
    same(run(factors.AnnualizedVolatility(3), [(0, 2), (3, 4)], close_tr=prices), expected)


def test_annualized_volatility_uses_its_factor() -> None:
    """The term's `annualization_factor` reaches the kernel, not 3.4's default 252."""
    found = run(factors.AnnualizedVolatility(3, annualization_factor=12),
                close_tr=[100, 110, 99, NAN, 108.9])  # fmt: skip
    same(found, [NAN, NAN, NAN, 0.1 * math.sqrt(12), 0.0])


def test_rolling_std_nan_rule() -> None:
    """`nanstd(x, ddof=1)` of `close`; NaN left out, minimum 2; warm-up W-1."""
    assert column(factors.RollingStd(3)) == "close"
    found = run(factors.RollingStd(3), close=[2, 4, NAN, 8, NAN])
    same(found, [NAN, NAN, math.sqrt(2), math.sqrt(8), NAN])


@pytest.mark.parametrize(
    ("term", "name"),
    [(factors.SMA(3), "close"), (factors.AverageTradedValue(3), "value_traded"),
     (factors.RollingStd(3), "close"), (factors.Returns(3), "close_tr"),
     (factors.AnnualizedVolatility(3), "close_tr")],
)  # fmt: skip
def test_inf_cell_follows_the_nan_rule(term: Term, name: str) -> None:
    """5.4.1 "`inf` is turned into NaN": a window's `inf` cell gives what a NaN cell gives under
    the factor's 3.4 rule. The count is not kept (#536)."""
    for bad in (INF, -INF):
        cells = [1, bad, 3, 5, bad]
        nans = [NAN if math.isinf(c) else c for c in cells]
        same(run(term, None, **{name: cells}), run(term, None, **{name: nans}))


def test_inf_in_dollar_volume_counts_as_nan() -> None:
    """A product that is `inf` is a NaN cell of `AverageDollarVolume`, so it counts as 0."""
    found = run(factors.AverageDollarVolume(2), close=[10, INF, 12], volume=[100, 300, 50])
    same(found, [NAN, 500.0, 300.0])


def test_inf_result_is_nan() -> None:
    """5.4.1: `Returns` over a zero first cell is `inf`, and the factor's value is NaN."""
    same(run(factors.Returns(2), close_tr=[0, 10, 20]), [NAN, NAN, 1.0])


def test_built_in_mask_waits_for_the_filter_executor() -> None:
    masked = factors.SMA(3, mask=BoundColumn.of("Price", "close").latest > 0)
    with pytest.raises(NotImplementedError, match="mask"):
        run(masked, close=[1, 2, 3])
