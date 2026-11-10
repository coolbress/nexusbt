"""T-12 by arithmetic only (spec 3.4, 3.3, 5.3.7): the three forms of 12-1 momentum.

Run it: `uv run python tests/golden/check/T-12.py` prints one row per computation row t: the two
cells every form reads, then `Returns(232).shift(21)`, the 253-row window close[-22]/close[0] - 1
and the direct P[t-21]/P[t-252] - 1, the same value in every row. No loops, classes or engine
imports (`tests/golden/test_handcalc_self.py`); the price series is a rule, P[i] = 100 + i with a
NaN at row 240, so a 253-cell window is read without writing it out.
"""

from math import isnan, nan
from typing import Any

HALTED = 240  # the one NaN cell
LAST = 262  # rows 0 .. 262 are in the data


def price(i: int) -> float | None:
    """P[i] = 100 + i; NaN at the halted row; None (not in the data) outside 0 .. LAST."""
    if i < 0 or i > LAST:
        return None
    return nan if i == HALTED else 100.0 + i


def ratio(end: float | None, start: float | None) -> float:
    """3.4 Returns: x[-1]/x[0] - 1; either end NaN or not in the data -> NaN."""
    if end is None or start is None or isnan(end) or isnan(start):
        return nan
    return round(end / start - 1, 6)


def returns_232_shift_21(t: int) -> float:
    """Form (a): `Returns(232)` at row t - 21 (3.3 shift); its window is rows t - 252 .. t - 21."""
    s = t - 21
    return ratio(price(s), price(s - 231))


def window_253(t: int) -> float:
    """Form (b), `@nx.factor(window=253)` on rows t - 252 .. t: close[-22]/close[0] - 1 (5.3.7)."""
    first = t - 252  # close[0]; close[-22] is the 22nd cell from the end
    return ratio(price(first + 253 - 22), price(first))


def direct(t: int) -> float:
    """Form (c): P[t - 21] / P[t - 252] - 1."""
    return ratio(price(t - 21), price(t - 252))


def row(t: int) -> dict[str, Any]:
    return {"row": t, "p_end": price(t - 21), "p_start": price(t - 252),
            "returns_232_shift_21": returns_232_shift_21(t), "window_253": window_253(t),
            "direct": direct(t)}  # fmt: skip


def same(r: dict[str, Any]) -> bool:
    """The three forms agree: the same number, or all NaN."""
    a, b, c = r["returns_232_shift_21"], r["window_253"], r["direct"]
    return (isnan(a) and isnan(b) and isnan(c)) or a == b == c


ROWS = (row(251), row(252), row(253), row(255), row(260), row(261), row(262))
assert (same(ROWS[0]), same(ROWS[1]), same(ROWS[2]), same(ROWS[3])) == (True,) * 4
assert (same(ROWS[4]), same(ROWS[5]), same(ROWS[6])) == (True,) * 3
assert isnan(ROWS[0]["direct"])  # warm-up: row -1 is not in the data
assert ROWS[1]["direct"] == 2.31  # the first full row
assert not isnan(ROWS[3]["direct"])  # the NaN at row 240 is inside the window, not at an end
assert isnan(ROWS[5]["direct"])  # the NaN at row 240 is the end cell


def line(r: dict[str, Any]) -> str:
    return "{!s:>5} {!s:>7} {!s:>8}  {!s:>22} {!s:>10} {!s:>10}".format(*r.values())


if __name__ == "__main__":
    print(line({"row": "row", "p_end": "P[t-21]", "p_start": "P[t-252]",
                "returns_232_shift_21": "Returns(232).shift(21)", "window_253": "window 253",
                "direct": "direct"}))  # fmt: skip
    print(line(ROWS[0]))
    print(line(ROWS[1]))
    print(line(ROWS[2]))
    print(line(ROWS[3]))
    print(line(ROWS[4]))
    print(line(ROWS[5]))
    print(line(ROWS[6]))
