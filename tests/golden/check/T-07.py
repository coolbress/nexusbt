"""T-07 by arithmetic only (spec 5.3.3, 3.4): windows across a split and a reverse split.

Run it: `uv run python tests/golden/check/T-07.py` prints one row per computation day t: C[t],
the closes as traded, the adjusted window the kernel sees, SMA by the reference meaning and by
the degree-1 shortcut, and the adjusted volume window. No loops, classes or engine imports
(`tests/golden/test_handcalc_self.py`); the sessions, bars and events are written out.
"""

from typing import Any

# The first eight tiny XKRX sessions of 2020 (spec 4.8); the index is the row.
SESSIONS = ("2020-01-02", "2020-01-03", "2020-01-06", "2020-01-07", "2020-01-08", "2020-01-09",
            "2020-01-10", "2020-01-13")  # fmt: skip
# KR:T00001's bars as traded.
RAW = (100.0, 102.0, 104.0, 53.0, 54.0, 55.0, 560.0, 570.0)
VOLUME = (1000.0, 1100.0, 1200.0, 2600.0, 2800.0, 3000.0, 320.0, 340.0)
# Two events (TDS 5.11): a 2:1 split effective at row 3 and a 1:10 reverse split at row 6.
# m_e = 1 / ratio_new_per_old (the price factor), q_e = share_factor (the quantity factor).
E1, M1, Q1 = 3, 1 / 2, 2.0
E2, M2, Q2 = 6, 10.0, 1 / 10
assert (SESSIONS[E1], SESSIONS[E2]) == ("2020-01-07", "2020-01-10")


def r6(x: float) -> float:
    return round(x, 6)


def m_between(s: int, t: int) -> float:
    """5.3.3 reference meaning: the product of m_e over the events with s < e <= t."""
    return (M1 if s < E1 <= t else 1.0) * (M2 if s < E2 <= t else 1.0)


def q_between(s: int, t: int) -> float:
    """The same product over q_e: vol[s] * Q[t] / Q[s]."""
    return (Q1 if s < E1 <= t else 1.0) * (Q2 if s < E2 <= t else 1.0)


def c(x: int) -> float:
    """C[x] = the product of m_e over e <= x (TDS cum_factor_split)."""
    return (M1 if x >= E1 else 1.0) * (M2 if x >= E2 else 1.0)


def base(s: int) -> float:
    """B[s] = raw[s] / C[s]."""
    return RAW[s] / c(s)


def adjusted(s: int, t: int) -> float:
    """The cell (s) of row t's window: raw[s] times the events in (s, t], = B[s] * C[t]."""
    value = r6(RAW[s] * m_between(s, t))
    assert value == r6(base(s) * c(t))  # every event up to t is known here
    return value


def volume(s: int, t: int) -> float:
    return r6(VOLUME[s] * q_between(s, t))


def row(t: int, adj: tuple[float, ...], sma: float, shortcut: float,
        vol: tuple[float, ...]) -> dict[str, Any]:  # fmt: skip
    w = len(adj)
    return {"session": SESSIONS[t], "window": w, "c_t": c(t),
            "raw_window": list(RAW[t - w + 1:t + 1]), "adjusted_window": list(adj),
            "sma": sma, "sma_shortcut": shortcut, "volume_window": list(vol)}  # fmt: skip


def row3(t: int) -> dict[str, Any]:
    adj = (adjusted(t - 2, t), adjusted(t - 1, t), adjusted(t, t))
    sma = r6((adj[0] + adj[1] + adj[2]) / 3)  # the reference meaning: the adjusted window
    # 3.4: SMA is homogeneous of degree 1, so the mean of B over the window times C[t].
    shortcut = r6((base(t - 2) + base(t - 1) + base(t)) / 3 * c(t))
    return row(t, adj, sma, shortcut, (volume(t - 2, t), volume(t - 1, t), volume(t, t)))


def row5(t: int) -> dict[str, Any]:
    adj = (adjusted(t - 4, t), adjusted(t - 3, t), adjusted(t - 2, t), adjusted(t - 1, t),
           adjusted(t, t))  # fmt: skip
    sma = r6((adj[0] + adj[1] + adj[2] + adj[3] + adj[4]) / 5)
    shortcut = r6((base(t - 4) + base(t - 3) + base(t - 2) + base(t - 1) + base(t)) / 5 * c(t))
    vol = (volume(t - 4, t), volume(t - 3, t), volume(t - 2, t), volume(t - 1, t), volume(t, t))
    return row(t, adj, sma, shortcut, vol)


ROWS = (row3(2), row3(3), row3(4), row3(5), row3(6), row3(7), row5(6))
assert ROWS[1]["sma"] == ROWS[1]["sma_shortcut"] == 52.0  # the split row: both paths agree
assert ROWS[4]["raw_window"] != ROWS[4]["adjusted_window"]  # the raw window is not the kernel's


def line(r: dict[str, Any]) -> str:
    return "{:<11} {!s:>6} {!s:>5}  {!s:<28} {!s:<30} {!s:>7} {!s:>8}  {!s}".format(
        r["session"], r["window"], r["c_t"], r["raw_window"], r["adjusted_window"], r["sma"],
        r["sma_shortcut"], r["volume_window"],
    )  # fmt: skip


if __name__ == "__main__":
    print(line({"session": "session", "window": "window", "c_t": "C[t]", "raw_window": "raw",
                "adjusted_window": "adjusted", "sma": "SMA", "sma_shortcut": "shortcut",
                "volume_window": "volume"}))  # fmt: skip
    print(line(ROWS[0]))
    print(line(ROWS[1]))
    print(line(ROWS[2]))
    print(line(ROWS[3]))
    print(line(ROWS[4]))
    print(line(ROWS[5]))
    print(line(ROWS[6]))
