"""G-12 by arithmetic only (spec 8.2): a cash shortfall scales two buys and cancels the rest.

Run it: `uv run python tests/golden/check/G-12.py` prints cash (minor units), fills and
`cancelled_qty` per session. No loops, classes or engine imports
(`tests/golden/test_handcalc_self.py`). Exact fractions, so no float product loses a share.
"""

from fractions import Fraction
from math import floor
from operator import itemgetter
from typing import Any

CAPITAL = 10_000_000  # won, minor unit 1; zero costs
A, B = "KR:T00001", "KR:T00002"
W_A, W_B = Fraction(6, 10), Fraction(4, 10)
CLOSE_0102_A, CLOSE_0102_B = 10_000, 20_000
OPEN_0103_A, OPEN_0103_B = 10_500, 20_400
CLOSE_0103_A, CLOSE_0103_B = 10_600, 20_300
CLOSE_0106_A, CLOSE_0106_B = 10_400, 20_500

# 2020-01-02 close decision (5.6.7): V is the cash, T = floor_lot(w x V / P), lot 1.
target_a = floor(W_A * CAPITAL / CLOSE_0102_A)
target_b = floor(W_B * CAPITAL / CLOSE_0102_B)
# 2020-01-03 open (5.6.7 buy cash allocation): need = quantity x open, nothing else at zero
# costs. (1) k = min(1, cash / sum of needs), q = floor_lot(k x f).
need = target_a * OPEN_0103_A + target_b * OPEN_0103_B
assert need > CAPITAL, "G-12 is the cash-shortfall case"
k = min(Fraction(1), Fraction(CAPITAL, need))
fill_a, fill_b = floor(k * target_a), floor(k * target_b)
notional_a, notional_b = fill_a * OPEN_0103_A, fill_b * OPEN_0103_B
# (2) takes one share at a time off the fullest order while the sum is above the cash: not here.
assert notional_a + notional_b <= CAPITAL, "step (2) of the allocation takes no share off"
cancelled_a, cancelled_b = target_a - fill_a, target_b - fill_b
cash = CAPITAL - notional_a - notional_b
assert cash >= OPEN_0103_A, "the cash left would buy one more share and does not (5.6.7)"
# close_mark (5.6.3 (6)): holding x raw close + cash. Nothing is pending on 2020-01-06.
nav_0103 = fill_a * CLOSE_0103_A + fill_b * CLOSE_0103_B + cash
nav_0106 = fill_a * CLOSE_0106_A + fill_b * CLOSE_0106_B + cash

COLUMNS = ("session", "phase", "instrument_id", "order_qty", "fill_qty", "fill_price",
           "notional_minor", "cancelled_qty", "remaining_qty", "status", "cash_minor", "qty",
           "value_minor")  # fmt: skip
NONE: dict[str, Any] = dict.fromkeys(COLUMNS)
D0, D1, D2 = "2020-01-02", "2020-01-03", "2020-01-06"
ROWS = (
    NONE | {"session": D0, "phase": "decision", "instrument_id": A, "order_qty": target_a,
            "qty": 0},
    NONE | {"session": D0, "phase": "decision", "instrument_id": B, "order_qty": target_b,
            "qty": 0},
    NONE | {"session": D0, "phase": "decision", "cash_minor": CAPITAL, "value_minor": CAPITAL},
    NONE | {"session": D1, "phase": "open", "instrument_id": A, "fill_qty": fill_a,
            "fill_price": OPEN_0103_A, "notional_minor": notional_a,
            "cancelled_qty": cancelled_a, "remaining_qty": target_a - fill_a - cancelled_a,
            "status": "CANCELLED", "qty": fill_a},
    NONE | {"session": D1, "phase": "open", "instrument_id": B, "fill_qty": fill_b,
            "fill_price": OPEN_0103_B, "notional_minor": notional_b,
            "cancelled_qty": cancelled_b, "remaining_qty": target_b - fill_b - cancelled_b,
            "status": "CANCELLED", "qty": fill_b},
    NONE | {"session": D1, "phase": "open", "cash_minor": cash},
    NONE | {"session": D1, "phase": "close_mark", "cash_minor": cash, "value_minor": nav_0103},
    NONE | {"session": D2, "phase": "open", "fill_qty": 0, "cancelled_qty": 0,
            "cash_minor": cash},
    NONE | {"session": D2, "phase": "close_mark", "cash_minor": cash, "value_minor": nav_0106},
)  # fmt: skip


def line(row: dict[str, Any]) -> str:
    cells = itemgetter(*COLUMNS)(row)
    return ("{:<10} {:<10} {!s:<13} {!s:>9} {!s:>8} {!s:>10} {!s:>14} {!s:>13} {!s:>13} "
            "{!s:>9} {!s:>10} {!s:>4} {!s:>11}").format(*cells)  # fmt: skip


if __name__ == "__main__":
    print(line(dict(zip(COLUMNS, COLUMNS, strict=True))))
    print(line(ROWS[0]))
    print(line(ROWS[1]))
    print(line(ROWS[2]))
    print(line(ROWS[3]))
    print(line(ROWS[4]))
    print(line(ROWS[5]))
    print(line(ROWS[6]))
    print(line(ROWS[7]))
    print(line(ROWS[8]))
