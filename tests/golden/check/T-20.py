"""T-20 by arithmetic only (spec 5.1.2, 5.3.1): a late bar under `ready_delay`.

Run it: `uv run python tests/golden/check/T-20.py` prints one row per session: the freeze time
`ready(s)`, when A's bar became available, A's `close` as the row sees it, SMA(3) of A and B
and the top(1) target. The late bar stays in its own row (NaN there) and is used from the first
row whose `ready` reaches its `ts_available`. No loops, classes or engine imports
(`tests/golden/test_handcalc_self.py`).
"""

from datetime import UTC, datetime, timedelta
from math import nan
from typing import Any

A, B = "KR:T00001", "KR:T00002"
READY_DELAY = timedelta(minutes=5)  # bars `params.ready_delay = PT5M`
B_CLOSE = 12.2


def close_at(day: int) -> datetime:
    """XKRX closes at 06:30Z (spec 4.8) on January `day`, 2020."""
    return datetime(2020, 1, day, 6, 30, tzinfo=UTC)


def iso(ts: datetime) -> str:
    return ts.strftime("%Y-%m-%dT%H:%M:%SZ")


# 5.1.2: ready(s) = ts_close(s) + ready_delay; the close decision at s has decision_ts = ready(s).
ready_0102, ready_0103 = close_at(2) + READY_DELAY, close_at(3) + READY_DELAY
ready_0106, ready_0107 = close_at(6) + READY_DELAY, close_at(7) + READY_DELAY
ready_0108 = close_at(8) + READY_DELAY
# A's raw closes and their ts_available. The 2020-01-06 bar is late by 3 minutes less than
# the delay after the next close: 2020-01-07T06:33Z.
A_CLOSE = (10.0, 11.0, 18.0, 13.0, 14.0)
A_AVAILABLE = (ready_0102, ready_0103, close_at(7) + timedelta(minutes=3), ready_0107, ready_0108)
# The cell (s, A) is seen by row t only when ts_available <= ready(t); a row's own late bar
# is NaN (LateBar), never moved to row s+1.
assert A_AVAILABLE[2] > ready_0106  # late in its own row
assert A_AVAILABLE[2] <= ready_0107  # read by the next row's window at its own position
assert A_AVAILABLE[2] > close_at(7)  # with ready_delay 0 it would wait for 2020-01-08


def mean3(x: float, y: float, z: float) -> float:
    return round((x + y + z) / 3, 6)


# Term values of `close` at each row: the row's own cell as its reference time sees it.
a_close = (A_CLOSE[0], A_CLOSE[1], nan, A_CLOSE[3], A_CLOSE[4])
# SMA(3): nanmean over the window as the row's reference time sees the cells (3.4).
a_sma_0106 = round((A_CLOSE[0] + A_CLOSE[1]) / 2, 6)  # the late cell left out
a_sma_0107 = mean3(A_CLOSE[1], A_CLOSE[2], A_CLOSE[3])  # the late cell back at its position
a_sma_0108 = mean3(A_CLOSE[2], A_CLOSE[3], A_CLOSE[4])
b_sma = mean3(B_CLOSE, B_CLOSE, B_CLOSE)


def pick(a_sma: float, b_sma: float) -> str:
    """top(1): the higher score; no tie here."""
    assert a_sma != b_sma
    return A if a_sma > b_sma else B


def row(session: datetime, ready: datetime, avail: datetime, close: float, a_sma: float | None,
        b_sma: float | None, target: str | None) -> dict[str, Any]:  # fmt: skip
    return {"session": session.strftime("%Y-%m-%d"), "ready": iso(ready), "a_available": iso(avail),
            "a_close": close, "a_sma3": a_sma, "b_sma3": b_sma, "target": target}  # fmt: skip


ROWS = (
    row(close_at(2), ready_0102, A_AVAILABLE[0], a_close[0], None, None, None),
    row(close_at(3), ready_0103, A_AVAILABLE[1], a_close[1], None, None, None),
    row(close_at(6), ready_0106, A_AVAILABLE[2], a_close[2], a_sma_0106, b_sma,
        pick(a_sma_0106, b_sma)),
    row(close_at(7), ready_0107, A_AVAILABLE[3], a_close[3], a_sma_0107, b_sma,
        pick(a_sma_0107, b_sma)),
    row(close_at(8), ready_0108, A_AVAILABLE[4], a_close[4], a_sma_0108, b_sma,
        pick(a_sma_0108, b_sma)),
)  # fmt: skip


def line(r: dict[str, Any]) -> str:
    return "{:<10} {:<20} {:<20} {!s:>7} {!s:>7} {!s:>7}  {!s}".format(
        r["session"], r["ready"], r["a_available"], r["a_close"], r["a_sma3"], r["b_sma3"],
        r["target"],
    )  # fmt: skip


if __name__ == "__main__":
    print(line({"session": "session", "ready": "ready", "a_available": "A ts_available",
                "a_close": "A close", "a_sma3": "A SMA3", "b_sma3": "B SMA3",
                "target": "target"}))  # fmt: skip
    print(line(ROWS[0]))
    print(line(ROWS[1]))
    print(line(ROWS[2]))
    print(line(ROWS[3]))
    print(line(ROWS[4]))
