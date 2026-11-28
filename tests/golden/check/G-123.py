"""G-123 by arithmetic only (spec 8.2, 5.7): under one year a return is not annualised.

Run it: `uv run python tests/golden/check/G-123.py` prints one line per value. No loops,
classes or engine imports (`tests/golden/test_handcalc_self.py`).
"""

from datetime import date
from typing import Any

YEAR = 365  # 5.7: under one year is D < 365, the shortest calendar year


def cagr(first: float, last: float, days: int) -> float | str:
    """5.7 CAGR: (I_T/I_0)^(365.25/D) - 1, and no number under one year."""
    if days < YEAR:
        return "n/a (under one year)"
    return round((last / first) ** (365.25 / days) - 1, 6)


# (a) NAV 100 on 2024-01-02 and 104 on 2024-07-01.
A_START, A_END, A_FIRST, A_LAST = date(2024, 1, 2), date(2024, 7, 1), 100.0, 104.0
a_days = (A_END - A_START).days
a_return = round(A_LAST / A_FIRST - 1, 6)
headline = f"return    {a_return * 100:.2f}% {A_START} → {A_END}, not annualised"
# (b) NAV 100 on 2023-01-02 and 104 on 2024-01-02: 365 days is not under one year.
B_START, B_END, B_FIRST, B_LAST = date(2023, 1, 2), date(2024, 1, 2), 100.0, 104.0
b_days = (B_END - B_START).days
assert a_days < YEAR <= b_days


def row(part: str, metric: str, value: Any) -> dict[str, Any]:
    return {"part": part, "metric": metric, "value": value}


ROWS = (
    row("a", "calendar_days", a_days),
    row("a", "cagr", cagr(A_FIRST, A_LAST, a_days)),
    row("a", "period_return", a_return),
    row("a", "period_start", A_START.isoformat()),
    row("a", "period_end", A_END.isoformat()),
    row("a", "headline_return", headline),
    row("b", "calendar_days", b_days),
    row("b", "cagr", cagr(B_FIRST, B_LAST, b_days)),
)

if __name__ == "__main__":
    print(*map("{0[part]} {0[metric]:<16} {0[value]}".format, ROWS), sep="\n")
