"""The built-in factors against the 3.4 table (T1.9): the class each term declares in `pipeline`
is the class its kernel is registered with in `compute`, which P-ADJ proves (5.3.3)."""

from __future__ import annotations

from nexusbt import factors
from nexusbt.compute._kernels_ref import REGISTERED
from nexusbt.pipeline import graph_hash
from nexusbt.pipeline.factors import ADJUSTMENT

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


def test_factor_classes_match_registered_kernels() -> None:
    """#242, Decisions 2026-11-18: a term's class in `pipeline` = its kernel's in `compute`."""
    assert {term.op for term in BUILT.values()} == set(ADJUSTMENT)
    for name, term in BUILT.items():
        assert ADJUSTMENT[term.op] == REGISTERED[term.op].adjustment, name
    assert graph_hash(factors.DailyReturns()) == graph_hash(factors.Returns(2))  # the same node
    assert factors.SMA is factors.SimpleMovingAverage
