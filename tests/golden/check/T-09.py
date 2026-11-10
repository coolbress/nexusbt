"""T-09 by interval comparisons (spec 5.3.6, TDS 5.2): symbol reuse in `instrument_symbols`.

Run it: `uv run python tests/golden/check/T-09.py` prints one row per query (cutoff, date): the
ticker KR:T00001 carries and the instrument the ticker ABC names, each with the row that
answered, or none. A row answers when `ts_known_from <= cutoff < ts_known_to` and `valid_from <=
date < valid_to`, both at once (the rectangle). No loops, classes or engine imports
(`tests/golden/test_handcalc_self.py`); the four rows are written out.
"""

from datetime import UTC, date, datetime
from typing import Any

T1, T2 = "KR:T00001", "KR:T00002"
ANNOUNCED = datetime(2020, 1, 7, 7, tzinfo=UTC)  # after the 01-07 close, before the 01-08 one
# (row, instrument_id, symbol, valid_from, valid_to, ts_known_from, ts_known_to); None = open.
Row = tuple[str, str, str, date, date | None, datetime, datetime | None]
R1: Row = ("R1", T1, "ABC", date(2020, 1, 2), None, datetime(2019, 12, 31, tzinfo=UTC), ANNOUNCED)
R2: Row = ("R2", T1, "ABC", date(2020, 1, 2), date(2020, 1, 8), ANNOUNCED, None)
R3: Row = ("R3", T1, "ABCD", date(2020, 1, 8), None, ANNOUNCED, None)
R4: Row = ("R4", T2, "ABC", date(2020, 1, 9), None, ANNOUNCED, None)
assert (R1[6], R2[4]) == (R2[5], R3[3])  # R1's trust ends where R2's begins; R2 hands over to R3


def cutoff(day: int) -> datetime:
    """ready(s) of the close decision at January `day`: the XKRX close, 06:30Z (5.1.2, 4.8)."""
    return datetime(2020, 1, day, 6, 30, tzinfo=UTC)


assert cutoff(7) < ANNOUNCED <= cutoff(8)


def answers(r: Row, c: datetime, q: date) -> bool:
    """Known at c (ts_known_from <= c < ts_known_to) and effective on q (valid_from <= q < to)."""
    known = r[5] <= c and (r[6] is None or c < r[6])
    return known and r[3] <= q and (r[4] is None or q < r[4])


def one(a: Row, b: Row, d: Row, c: datetime, q: date) -> Row | None:
    """5.3.6: the one row of a key that answers; none is missing; two would be TDS-T012 (E14)."""
    ma, mb, md = answers(a, c, q), answers(b, c, q), answers(d, c, q)
    assert ma + mb + md <= 1
    return a if ma else b if mb else d if md else None


def row(day: int, q_day: int) -> dict[str, Any]:
    c, q = cutoff(day), date(2020, 1, q_day)
    ticker = one(R1, R2, R3, c, q)  # key (KR:T00001, ticker)
    abc = one(R1, R2, R4, c, q)  # the rows whose symbol is ABC
    return {"session": c.date().isoformat(), "cutoff": c.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "date": q.isoformat(), "t00001_row": None if ticker is None else ticker[0],
            "t00001_ticker": None if ticker is None else ticker[2],
            "abc_row": None if abc is None else abc[0],
            "abc_instrument": None if abc is None else abc[1]}  # fmt: skip


ROWS = (row(6, 6), row(7, 7), row(7, 9), row(8, 7), row(8, 8), row(9, 9), row(9, 6))
assert ROWS[2]["abc_instrument"] == T1  # before the announcement, the reuse is unseen (INV-01)
assert ROWS[4]["abc_row"] is None  # on 2020-01-08 the ticker names nobody
assert ROWS[5]["abc_instrument"] == T2  # the reuse, once known and effective
assert ROWS[6]["abc_instrument"] == T1  # the past as the corrected row R2 tells it


def line(r: dict[str, Any]) -> str:
    return "{:<11} {:<21} {:<11} {!s:>4} {!s:<7} {!s:>4} {!s}".format(*r.values())


if __name__ == "__main__":
    print(line({"session": "session", "cutoff": "cutoff", "date": "date",
                "t00001_row": "row", "t00001_ticker": "T00001", "abc_row": "row",
                "abc_instrument": "ABC names"}))  # fmt: skip
    print(line(ROWS[0]))
    print(line(ROWS[1]))
    print(line(ROWS[2]))
    print(line(ROWS[3]))
    print(line(ROWS[4]))
    print(line(ROWS[5]))
    print(line(ROWS[6]))
