"""G-TIME-LATE by arithmetic only (spec 8.4, 5.1.2, 5.3.1): a bar two sessions late, Δ = 0.

Run it: `uv run python tests/golden/check/G-TIME-LATE.py` prints the five rows of the 8.4 table:
A's `close` as the row sees it (NaN at s, `LateBar` 1), SMA(3) of A and B, the top(1) target,
the order intents (M3a's column) and the look-ahead SMA(3) that must not appear. No loops,
classes or engine imports (`tests/golden/test_handcalc_self.py`).
"""

from datetime import UTC, datetime
from math import nan
from typing import Any

A, B = "KR:T00001", "KR:T00002"
NAME = {A: "A", B: "B"}  # the table's names, used in its order-intent text
B_CLOSE = 12.2


def close_at(day: int) -> datetime:
    """XKRX closes at 06:30Z (spec 4.8) on January `day`, 2020."""
    return datetime(2020, 1, day, 6, 30, tzinfo=UTC)


def iso(ts: datetime) -> str:
    return ts.strftime("%Y-%m-%dT%H:%M:%SZ")


# 5.1.2: a column rule without `ready_delay` has Δ = 0, so ready(t) = ts_close(t).
# Sessions s-2 … s+2 are January 2, 3, 6, 7 and 8; s is January 6.
ready_m2, ready_m1, ready_s, ready_p1, ready_p2 = (
    close_at(2), close_at(3), close_at(6), close_at(7), close_at(8),
)  # fmt: skip
# A's raw closes and their ts_available: the bar of s arrives at ready(s+2).
A_CLOSE = (10.0, 11.0, 18.0, 13.0, 14.0)
A_AVAILABLE = (ready_m2, ready_m1, ready_p2, ready_p1, ready_p2)
# The cell (s, A) is seen by row t only when ts_available <= ready(t).
assert A_AVAILABLE[2] > ready_s  # NaN in its own row (LateBar)
assert A_AVAILABLE[2] > ready_p1  # still unseen by the window of s+1
assert A_AVAILABLE[2] <= ready_p2  # read at its own position by the window of s+2


def mean2(x: float, y: float) -> float:
    return round((x + y) / 2, 6)


def mean3(x: float, y: float, z: float) -> float:
    return round((x + y + z) / 3, 6)


# SMA(3): nanmean over the window as the row's reference time sees the cells (3.4).
a_sma_s = mean2(A_CLOSE[0], A_CLOSE[1])  # the late cell left out
a_sma_p1 = mean2(A_CLOSE[1], A_CLOSE[3])  # still left out
a_sma_p2 = mean3(A_CLOSE[2], A_CLOSE[3], A_CLOSE[4])  # back at its position
b_sma = mean3(B_CLOSE, B_CLOSE, B_CLOSE)
# Look-ahead: the late cell read from the start. These must not appear in a run.
look_s = mean3(A_CLOSE[0], A_CLOSE[1], A_CLOSE[2])
look_p1 = mean3(A_CLOSE[1], A_CLOSE[2], A_CLOSE[3])
look_p2 = a_sma_p2


def pick(a_sma: float, b_sma: float) -> str:
    """top(1): the higher score; no tie here."""
    assert a_sma != b_sma
    return A if a_sma > b_sma else B


def intents(held: str | None, target: str, fill_row: str) -> str:
    """The table's order-intent text (M3a's column): from the holding `held` to `target`."""
    if held is None:
        return f"buy {NAME[target]} at the open of {fill_row}"
    if held == target:
        return "none"
    return f"sell {NAME[held]}, buy {NAME[target]} at the open of {fill_row}"


def warm_up(label: str, ready: datetime, close: float) -> dict[str, Any]:
    """A row before the run starts: only A's term value, on time."""
    return {"row": label, "session": ready.strftime("%Y-%m-%d"), "ready": iso(ready),
            "a_available": iso(ready), "a_close": close, "late_bar": 0, "a_sma3": None,
            "b_sma3": None, "target": None, "order_intents_m3a": None, "lookahead_a_sma3": None,
            "lookahead_target": None}  # fmt: skip


def row(label: str, ready: datetime, avail: datetime, close: float, a_sma: float,
        held: str | None, fill_row: str, look: float) -> dict[str, Any]:  # fmt: skip
    target = pick(a_sma, b_sma)
    return {"row": label, "session": ready.strftime("%Y-%m-%d"), "ready": iso(ready),
            "a_available": iso(avail), "a_close": close, "late_bar": int(avail > ready),
            "a_sma3": a_sma, "b_sma3": b_sma, "target": target,
            "order_intents_m3a": intents(held, target, fill_row), "lookahead_a_sma3": look,
            "lookahead_target": pick(look, b_sma)}  # fmt: skip


ROW_S = row("s", ready_s, A_AVAILABLE[2], nan, a_sma_s, None, "s+1", look_s)
HELD_P1 = ROW_S["target"]  # what the decision of s+1 holds: the target of s
ROW_P1 = row("s+1", ready_p1, A_AVAILABLE[3], A_CLOSE[3], a_sma_p1, HELD_P1, "s+2", look_p1)
HELD_P2 = ROW_P1["target"]
ROW_P2 = row("s+2", ready_p2, A_AVAILABLE[4], A_CLOSE[4], a_sma_p2, HELD_P2, "s+3", look_p2)
ROWS = (warm_up("s-2", ready_m2, A_CLOSE[0]), warm_up("s-1", ready_m1, A_CLOSE[1]),
        ROW_S, ROW_P1, ROW_P2)  # fmt: skip


def line(r: dict[str, Any]) -> str:
    return "{:<4} {:<10} {!s:>7} {!s:>7} {!s:>6} {!s:>6}  {!s:<9}  {!s:<32}  {!s:>4} {!s}".format(
        r["row"], r["session"], r["a_close"], r["late_bar"], r["a_sma3"], r["b_sma3"],
        r["target"], r["order_intents_m3a"], r["lookahead_a_sma3"], r["lookahead_target"],
    )  # fmt: skip


if __name__ == "__main__":
    print("the last two columns are the look-ahead A SMA3 and its target: they must not appear")
    print(line({"row": "row", "session": "session", "a_close": "A close", "late_bar": "LateBar",
                "a_sma3": "A SMA3", "b_sma3": "B SMA3", "target": "target",
                "order_intents_m3a": "order intents (M3a)", "lookahead_a_sma3": "look",
                "lookahead_target": "(target)"}))  # fmt: skip
    print(line(ROWS[0]))
    print(line(ROWS[1]))
    print(line(ROWS[2]))
    print(line(ROWS[3]))
    print(line(ROWS[4]))
