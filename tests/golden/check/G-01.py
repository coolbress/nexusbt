"""G-01 by arithmetic only (spec 8.2): market buy at the open, provisional costs.

Run it: `uv run python tests/golden/check/G-01.py` prints one row per session and phase.
No loops, classes or engine imports (`tests/golden/test_handcalc_self.py`). Exact decimals,
so no float product loses a share.
"""

from decimal import ROUND_FLOOR, ROUND_HALF_UP, Decimal
from operator import itemgetter
from typing import Any

CAPITAL = 10_000_000  # won, minor unit 1
WEIGHT = Decimal("0.99")
BUY_BPS = 5
CLOSE_0102, OPEN_0103, CLOSE_0103, CLOSE_0106 = 10_000, 10_000, 10_100, 10_200


def half_up(x: Decimal) -> int:
    return int(x.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def floor(x: Decimal) -> int:
    return int(x.to_integral_value(rounding=ROUND_FLOOR))


# 2020-01-02 close decision (5.6.7): V is the cash, T = floor_lot(w x V / P), lot 1.
target = floor(WEIGHT * CAPITAL / CLOSE_0102)
# 2020-01-03 open (5.6.4, 5.6.8): the fill amount and the provisional cost, each rounded once.
notional = half_up(Decimal(target * OPEN_0103))
cost = half_up(Decimal(notional) * BUY_BPS / 10_000)
assert notional + cost <= CAPITAL, "G-01 is not a cash-shortfall case (that is G-12)"
cash = CAPITAL - notional - cost
# close_mark (5.6.3 (6)): holding x raw close + cash.
nav_0103 = target * CLOSE_0103 + cash
nav_0106 = target * CLOSE_0106 + cash

NONE: dict[str, Any] = dict.fromkeys(
    ("order_qty", "fill_qty", "fill_price", "notional_minor", "cost_minor", "value_minor")
)
ROWS = (
    NONE | {"session": "2020-01-02", "phase": "decision", "order_qty": target,
            "cash_minor": CAPITAL, "qty": 0, "value_minor": CAPITAL},
    NONE | {"session": "2020-01-03", "phase": "open", "fill_qty": target, "fill_price": OPEN_0103,
            "notional_minor": notional, "cost_minor": cost, "cash_minor": cash, "qty": target},
    NONE | {"session": "2020-01-03", "phase": "close_mark", "cash_minor": cash, "qty": target,
            "value_minor": nav_0103},
    NONE | {"session": "2020-01-06", "phase": "close_mark", "cash_minor": cash, "qty": target,
            "value_minor": nav_0106},
)  # fmt: skip


COLUMNS = ("session", "phase", "order_qty", "fill_qty", "fill_price", "notional_minor",
           "cost_minor", "cash_minor", "qty", "value_minor")  # fmt: skip


def line(row: dict[str, Any]) -> str:
    cells = itemgetter(*COLUMNS)(row)
    return (
        "{:<10} {:<10} {!s:>9} {!s:>8} {!s:>10} {!s:>14} {!s:>10} {!s:>10} {!s:>4} {!s:>11}".format(
            *cells
        )
    )


if __name__ == "__main__":
    header = dict(zip(COLUMNS, COLUMNS, strict=True))
    print(line(header))
    print(line(ROWS[0]))
    print(line(ROWS[1]))
    print(line(ROWS[2]))
    print(line(ROWS[3]))
