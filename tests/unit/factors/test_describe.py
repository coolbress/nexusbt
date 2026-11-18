"""T1.10's done line (10.1): `nx.describe(nx.factors)` prints the 12 built-in factors of 3.4
with their default input, adjustment class and numerics class (5.3.10 2a)."""

from __future__ import annotations

import subprocess
import sys

import pytest

import nexusbt as nx

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


def rows_of(text: str) -> dict[str, tuple[str, ...]]:
    """The table's rows by factor, after checking its header."""
    lines = text.splitlines()
    header = [cell.strip() for cell in lines[0].split("|")]
    assert header == ["factor", "default input", "adjustment class", "numerics class"]
    rows = [[cell.strip() for cell in line.split("|")] for line in lines[2:]]
    assert len(rows) == 12
    return {name: tuple(rest) for name, *rest in rows}


def test_describe_factors_prints_the_12_built_in_factors() -> None:
    """When I run `nx.describe(nx.factors)`, then I see a table of the 12 built-in factors
    with their default input, adjustment class and numerics class."""
    assert rows_of(str(nx.describe(nx.factors))) == EXPECTED


def test_describe_factors_after_only_import_nexusbt() -> None:
    """3.1's Terms row and 2.5 ("re-exports of `__init__`"): in a fresh interpreter whose only
    import is `import nexusbt as nx`, `nx.factors` is there; no other test's import helps."""
    code = "import nexusbt as nx; print(nx.describe(nx.factors))"
    done = subprocess.run(  # noqa: S603 - this interpreter and the literal above
        [sys.executable, "-c", code], capture_output=True, text=True, check=True, timeout=120
    )
    assert rows_of(done.stdout) == EXPECTED


def test_describe_still_refuses_other_modules() -> None:
    """Only `nexusbt.factors` has a table; another object is still its own ticket's."""
    with pytest.raises(NotImplementedError):
        nx.describe(nx.ops)
