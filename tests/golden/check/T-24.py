"""T-24 by plain logic (spec 5.4.1, 3.3): the three-valued Filter table.

Run it: `uv run python tests/golden/check/T-24.py` prints one row per Filter term. A cell is
True, False or "unknown". No loops, classes or engine imports
(`tests/golden/test_handcalc_self.py`).
"""

from math import isnan, nan
from typing import Any

U = "unknown"
type Cell = bool | str

# KR:T00001, KR:T00002, KR:T00003. KR:T00003 is halted at d: no close.
CLOSE_PREV = (nan, 12_000.0, 8_000.0)  # the session before d (`.all(2)`, `.any(2)`)
CLOSE = (12_000.0, 8_000.0, nan)
SECTOR = ("x", "y", None)  # None: the missing code -1
HALTED: tuple[Cell, ...] = (False, U, True)


def above(close: float) -> Cell:
    """`close > 10000`: a comparison with NaN is unknown."""
    return U if isnan(close) else close > 10_000


def neg(a: Cell) -> Cell:
    """`~`: the value inverts, validity stays."""
    return U if a == U else not a


def and_(a: Cell, b: Cell) -> Cell:
    """Kleene `&`: false & unknown = false."""
    return False if False in (a, b) else (U if U in (a, b) else True)


def or_(a: Cell, b: Cell) -> Cell:
    """Kleene `|`: true | unknown = true."""
    return True if True in (a, b) else (U if U in (a, b) else False)


def as_factor(a: Cell) -> float:
    return nan if a == U else float(a)


def is_x(code: str | None) -> Cell:
    """`Meta.sector.eq("x")`: the missing code gives unknown."""
    return U if code is None else code == "x"


def fill_true(a: Cell) -> Cell:
    return True if a == U else a


def final(a: Cell) -> bool:
    """At a final use (universe, top/bottom candidates, mask, screen), unknown is false."""
    return a is True


def row(term: str, a: Cell, b: Cell, c: Cell) -> dict[str, Any]:
    return {"term": term, "values": [a, b, c], "final": [final(a), final(b), final(c)]}


# One cell at a time, as G-01 does: A, B, C = KR:T00001, KR:T00002, KR:T00003.
up_a0, up_b0, up_c0 = above(CLOSE_PREV[0]), above(CLOSE_PREV[1]), above(CLOSE_PREV[2])
up_a, up_b, up_c = above(CLOSE[0]), above(CLOSE[1]), above(CLOSE[2])
ok_a, ok_b, ok_c = neg(HALTED[0]), neg(HALTED[1]), neg(HALTED[2])
ROWS = (
    row("Price.close.latest > 10000", up_a, up_b, up_c),
    row("~(Price.close.latest > 10000)", neg(up_a), neg(up_b), neg(up_c)),
    row("(Price.close.latest > 10000) | Price.close.latest.isnan()",
        or_(up_a, isnan(CLOSE[0])), or_(up_b, isnan(CLOSE[1])), or_(up_c, isnan(CLOSE[2]))),
    row("(Price.close.latest > 10000).all(2)",
        and_(up_a0, up_a), and_(up_b0, up_b), and_(up_c0, up_c)),
    row("(Price.close.latest > 10000).any(2)",
        or_(up_a0, up_a), or_(up_b0, up_b), or_(up_c0, up_c)),
    {"term": "(Price.close.latest > 10000).as_factor()",
     "values": [as_factor(up_a), as_factor(up_b), as_factor(up_c)], "final": None},
    row('Meta.sector.eq("x")', is_x(SECTOR[0]), is_x(SECTOR[1]), is_x(SECTOR[2])),
    row("~Trad.halted", ok_a, ok_b, ok_c),
    row("(~Trad.halted).fillna(True)", fill_true(ok_a), fill_true(ok_b), fill_true(ok_c)),
    row("(Price.close.latest > 10000) & ~Trad.halted",
        and_(up_a, ok_a), and_(up_b, ok_b), and_(up_c, ok_c)),
)  # fmt: skip


def line(r: dict[str, Any]) -> str:
    return "{:<58} {!s:<26} {!s}".format(r["term"], r["values"], r["final"])


if __name__ == "__main__":
    print(line({"term": "term", "values": "values", "final": "final"}))
    print(line(ROWS[0]))
    print(line(ROWS[1]))
    print(line(ROWS[2]))
    print(line(ROWS[3]))
    print(line(ROWS[4]))
    print(line(ROWS[5]))
    print(line(ROWS[6]))
    print(line(ROWS[7]))
    print(line(ROWS[8]))
    print(line(ROWS[9]))
