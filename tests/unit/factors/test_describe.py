"""T1.10's done line (10.1): `nx.describe(nx.factors)` prints the 12 built-in factors of 3.4
with their default input, adjustment class and numerics class (5.3.10 2a)."""

from __future__ import annotations

import pytest

import nexusbt as nx
import nexusbt.factors  # 2.5's user import; it binds `nx.factors`

pytestmark = pytest.mark.unit

ARITHMETIC = "arithmetic"
#: The rows of 3.4's table: name, default input, adjustment class, numerics class.
EXPECTED = {
    "Returns(W)": ("Price.close_tr", "homogeneous of degree 0", ARITHMETIC),
    "DailyReturns()": ("Price.close_tr", "homogeneous of degree 0", ARITHMETIC),
    "SimpleMovingAverage(W), SMA": ("Price.close", "homogeneous of degree 1", ARITHMETIC),
    "ExponentialWeightedMovingAverage(W, decay_rate), EWMA": (
        "Price.close",
        "homogeneous of degree 1",
        "arithmetic (weights decay^k: transcendental, computed once outside the kernel)",
    ),
    "AverageDollarVolume(W)": ("Price.close, Price.volume", "invariant", ARITHMETIC),
    "AverageTradedValue(W, ccy=None)": ("Price.value_traded", "invariant", ARITHMETIC),
    "AnnualizedVolatility(W=252, annualization_factor=252)": (
        "Price.close_tr",
        "homogeneous of degree 0",
        ARITHMETIC,
    ),
    "RollingStd(W)": ("Price.close", "homogeneous of degree 1", ARITHMETIC),
    "VWAP(W)": ("Price.close, Price.volume", "homogeneous of degree 1", ARITHMETIC),
    "RSI(W=15)": ("Price.close_tr", "homogeneous of degree 0", ARITHMETIC),
    "MaxDrawdown(W)": ("Price.close_tr", "homogeneous of degree 0", ARITHMETIC),
    "Latest (col.latest)": ("a column", "the column table", "-"),
}


def test_describe_factors_prints_the_12_built_in_factors() -> None:
    """When I run `nx.describe(nx.factors)`, then I see a table of the 12 built-in factors
    with their default input, adjustment class and numerics class."""
    lines = str(nx.describe(nx.factors)).splitlines()
    header = [cell.strip() for cell in lines[0].split("|")]
    assert header == ["factor", "default input", "adjustment class", "numerics class"]
    rows = [[cell.strip() for cell in line.split("|")] for line in lines[2:]]
    assert len(rows) == 12
    assert {name: tuple(rest) for name, *rest in rows} == EXPECTED


def test_describe_still_refuses_other_modules() -> None:
    """Only `nexusbt.factors` has a table; another object is still its own ticket's."""
    with pytest.raises(NotImplementedError):
        nx.describe(nx.ops)
