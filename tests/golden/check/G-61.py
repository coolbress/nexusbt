"""G-61 by arithmetic only (spec 8.2, 5.7): drawdown boundaries.

Run it: `uv run python tests/golden/check/G-61.py` prints one line per value. No loops, classes
or engine imports (`tests/golden/test_handcalc_self.py`): each running peak is a `max` written
out, and each date the case names is held to the rule by an assert.
"""

from datetime import date
from typing import Any

D02, D03, D06, D07, D08 = (date(2020, 1, 2), date(2020, 1, 3), date(2020, 1, 6),
                           date(2020, 1, 7), date(2020, 1, 8))  # fmt: skip

# (a) NAV_0 100 at inception, then 90, 94.5, 100.17. NAV_0 counts in the peak (5.7).
A0, A1, A2, A3 = 100.0, 90.0, 94.5, 100.17
a_mdd = min(A0 / A0 - 1, A1 / max(A0, A1) - 1, A2 / max(A0, A1, A2) - 1,
            A3 / max(A0, A1, A2, A3) - 1)  # fmt: skip
assert a_mdd == A1 / A0 - 1, "the lowest point is 90 on 01-03, under the peak of 01-02"
# Recovery = the first NAV at or above the previous peak: not 94.5, then 100.17.
assert A2 < A0 <= A3

# (b) 100, 100, 99, 100, 99 on 01-02, 03, 06, 07, 08.
B0, B1, B2, B3, B4 = 100.0, 100.0, 99.0, 100.0, 99.0
b_mdd = min(B0 / B0 - 1, B1 / max(B0, B1) - 1, B2 / max(B0, B1, B2) - 1,
            B3 / max(B0, B1, B2, B3) - 1, B4 / max(B0, B1, B2, B3, B4) - 1)  # fmt: skip
# The first drawdown's peak date is the last day at or above the previous peak before the
# trough: 01-03 (B1 >= B0), not 01-02. Equality on 01-07 recovers it (B3 >= B1), so the fall
# of 01-08 is a second drawdown from the peak of 01-07, with no NAV after it.
assert B0 <= B1 > B2
assert B1 <= B3 > B4
drawdowns = (B2 < B1) + (B4 < B3)


def row(part: str, metric: str, value: Any) -> dict[str, Any]:
    shown = value.isoformat() if isinstance(value, date) else value
    return {"part": part, "metric": metric,
            "value": round(shown, 6) if isinstance(shown, float) else shown}  # fmt: skip


ROWS = (
    row("a", "max_drawdown", a_mdd),
    row("a", "peak_date", D02),
    row("a", "trough_date", D03),
    row("a", "drawdown_days", (D03 - D02).days),
    row("a", "recovery_date", D07),
    row("a", "recovery_days", (D07 - D03).days),
    row("b", "max_drawdown", b_mdd),
    row("b", "drawdowns", drawdowns),
    row("b", "first_peak_date", D03),
    row("b", "first_trough_date", D06),
    row("b", "first_drawdown_days", (D06 - D03).days),
    row("b", "first_recovery_date", D07),
    row("b", "first_recovery_days", (D07 - D06).days),
    row("b", "second_peak_date", D07),
    row("b", "second_trough_date", D08),
    row("b", "second_drawdown_days", (D08 - D07).days),
    row("b", "second_recovery", "not recovered"),
)

if __name__ == "__main__":
    print(*map("{0[part]} {0[metric]:<21} {0[value]}".format, ROWS), sep="\n")
