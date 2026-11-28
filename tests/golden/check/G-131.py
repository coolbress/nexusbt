"""G-131 by arithmetic only (spec 8.2, 5.7): one return, or one valuation date.

Run it: `uv run python tests/golden/check/G-131.py` prints one line per value. No loops,
classes or engine imports (`tests/golden/test_handcalc_self.py`).
"""

from datetime import date
from typing import Any

FEW = "n/a (fewer than 2 returns)"


def ratio(returns: int) -> str:
    """Volatility, Sharpe and Sortino of this case: a ddof = 1 deviation needs two returns."""
    assert returns < 2, "G-131's series have fewer than two returns"
    return FEW


def cagr(days: int) -> str:
    """5.7 CAGR for these spans: one valuation date (D = 0) is named before under one year."""
    assert days < 365
    return "n/a (one valuation date)" if days == 0 else "n/a (under one year)"


# (a) NAV 100 on 2024-01-02 and 101 on 2024-01-03: two dates, one return.
A_DAYS = (date(2024, 1, 3) - date(2024, 1, 2)).days
a_returns, a_return = 2 - 1, round(101.0 / 100.0 - 1, 6)
# (b) NAV 100 on 2024-01-02 alone: one date, no return, so no period return either.
B_DAYS = (date(2024, 1, 2) - date(2024, 1, 2)).days
b_returns = 1 - 1


def row(part: str, metric: str, value: Any) -> dict[str, Any]:
    return {"part": part, "metric": metric, "value": value}


ROWS = (
    row("a", "returns", a_returns),
    row("a", "volatility", ratio(a_returns)),
    row("a", "sharpe", ratio(a_returns)),
    row("a", "sortino", ratio(a_returns)),
    row("a", "cagr", cagr(A_DAYS)),
    row("a", "period_return", a_return),
    row("b", "returns", b_returns),
    row("b", "volatility", ratio(b_returns)),
    row("b", "sharpe", ratio(b_returns)),
    row("b", "sortino", ratio(b_returns)),
    row("b", "cagr", cagr(B_DAYS)),
    row("b", "period_return", None),
)

if __name__ == "__main__":
    print(*map("{0[part]} {0[metric]:<14} {0[value]}".format, ROWS), sep="\n")
