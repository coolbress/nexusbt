"""T-15 by arithmetic only (spec 4.6, 5.3.3, INV-12): a `price_factor` null event.

Run it: `uv run python tests/golden/check/T-15.py` prints one row per computation day t: the
closes as traded, the adjusted window with NaN in the rows before the event while the window
crosses it, SMA(3) as nanmean, and the value a silent 1.0 would give, which must not appear.
No loops, classes or engine imports (`tests/golden/test_handcalc_self.py`); the sessions, bars
and the event are written out.
"""

from math import isnan, nan
from typing import Any

# The first seven tiny XKRX sessions of 2020 (spec 4.8); the index is the row.
SESSIONS = ("2020-01-02", "2020-01-03", "2020-01-06", "2020-01-07", "2020-01-08", "2020-01-09",
            "2020-01-10")  # fmt: skip
# KR:T00001's closes as traded.
RAW = (100.0, 102.0, 104.0, 90.0, 91.0, 92.0, 93.0)
# The event: a spinoff effective at row 3 with its exact ratio and new instrument present (so
# 5.6.1's exclusion does not apply) and `price_factor` null (`factor_method = unavailable`), so
# its m_e is "none" (4.6), not 1.0. The package's cum_factor_split of 1.0 after it is not used.
E = 3
assert SESSIONS[E] == "2020-01-07"


def r6(x: float) -> float:
    return round(x, 6)


def adjusted(s: int, t: int) -> float:
    """4.6: NaN when the window of row t crosses e above s (s < e <= t); otherwise as traded."""
    return nan if s < E <= t else RAW[s]


def hidden_one(s: int, _t: int) -> float:
    """What substituting 1.0 for the missing factor would give: always the traded close."""
    return RAW[s]


def nanmean3(a: float, b: float, c: float) -> float:
    """3.4 SMA: the mean of the finite cells (NaN ignored, all NaN -> NaN)."""
    n = (not isnan(a)) + (not isnan(b)) + (not isnan(c))
    total = (0.0 if isnan(a) else a) + (0.0 if isnan(b) else b) + (0.0 if isnan(c) else c)
    return r6(total / n) if n else nan


def cells(t: int) -> int:
    """The NaN cells of row t: the rows s of the window with s < e <= t (row e itself is not)."""
    return int(t - 2 < E <= t) + int(t - 1 < E <= t) + int(t < E <= t)


def row(t: int) -> dict[str, Any]:
    adj = (adjusted(t - 2, t), adjusted(t - 1, t), adjusted(t, t))
    one = (hidden_one(t - 2, t), hidden_one(t - 1, t), hidden_one(t, t))
    return {"session": SESSIONS[t], "raw_window": list(RAW[t - 2:t + 1]),
            "adjusted_window": list(adj), "sma3": nanmean3(*adj),
            "hidden_one_sma3": nanmean3(*one)}  # fmt: skip


ROWS = (row(2), row(3), row(4), row(5), row(6))
# The NaN cells: 2 in the row of e, 1 in the next, none elsewhere; 4.6 does not fix the unit of
# the `AdjustmentUnavailable` count (cell, row or event), so the rows carry no count.
assert (cells(2), cells(3), cells(4), cells(5), cells(6)) == (0, 2, 1, 0, 0)
assert ROWS[1]["sma3"] != ROWS[1]["hidden_one_sma3"]  # the silent 1.0 would show here (INV-12)
assert ROWS[2]["sma3"] != ROWS[2]["hidden_one_sma3"]
assert ROWS[3]["sma3"] == ROWS[3]["hidden_one_sma3"]  # and nowhere else


def line(r: dict[str, Any]) -> str:
    return "{:<11} {!s:<22} {!s:<22} {!s:>7}  {!s}".format(
        r["session"], r["raw_window"], r["adjusted_window"], r["sma3"], r["hidden_one_sma3"],
    )  # fmt: skip


if __name__ == "__main__":
    print(line({"session": "session", "raw_window": "raw", "adjusted_window": "adjusted",
                "sma3": "SMA3", "hidden_one_sma3": "silent 1.0 (must not appear)"}))  # fmt: skip
    print(line(ROWS[0]))
    print(line(ROWS[1]))
    print(line(ROWS[2]))
    print(line(ROWS[3]))
    print(line(ROWS[4]))
