"""T-11 by counting comparisons (spec 3.3, 5.4.2, 3.7): ties under `tiebreak = "id"`.

Run it: `uv run python tests/golden/check/T-11.py` prints one row per instrument in id order:
its score, `rank("ordinal")` ascending and descending, the `average`, `min`, `max` and `dense`
ranks, whether `top(2)` picks it, and the decision's `n_tied_at_cutoff`. A rank is one plus the
number of finite cells before it in the order; a tie is broken by ascending `instrument_id`. No
loops, classes or engine imports (`tests/golden/test_handcalc_self.py`); the six cells are written
out in a shuffled memory order.
"""

from math import isnan, nan
from typing import Any

# The decision's cells in memory order, shuffled on purpose (INV-04).
(I0, S0), (I1, S1), (I2, S2) = ("KR:T00003", 2.0), ("KR:T00001", 2.0), ("KR:T00005", nan)
(I3, S3), (I4, S4), (I5, S5) = ("KR:T00002", 5.0), ("KR:T00004", 2.0), ("KR:T00006", 1.0)
VALUES = (1.0, 2.0, 5.0)  # the distinct finite scores, for `dense`
assert isnan(S2)
assert {S0, S1, S3, S4, S5} == set(VALUES)


def below(x: float) -> int:
    """The finite cells with a smaller score (a comparison with NaN is false, 5.4.1)."""
    return int(x > S0) + int(x > S1) + int(x > S2) + int(x > S3) + int(x > S4) + int(x > S5)


def above(x: float) -> int:
    return int(x < S0) + int(x < S1) + int(x < S2) + int(x < S3) + int(x < S4) + int(x < S5)


def tied(x: float) -> int:
    """The cells with this score, the cell itself among them."""
    return int(x == S0) + int(x == S1) + int(x == S2) + int(x == S3) + int(x == S4) + int(x == S5)


def earlier(i: str, x: float) -> int:
    """The tied cells whose `instrument_id` is smaller: the `tiebreak = "id"` key (3.7)."""
    return (int(x == S0 and i > I0) + int(x == S1 and i > I1) + int(x == S2 and i > I2)
            + int(x == S3 and i > I3) + int(x == S4 and i > I4)
            + int(x == S5 and i > I5))  # fmt: skip


def dense(x: float) -> int:
    """One plus the number of distinct finite scores below x (scipy rankdata dense)."""
    return int(VALUES[0] < x) + int(VALUES[1] < x) + int(VALUES[2] < x) + 1


def straddles(x: float, n: int) -> bool:
    """Whether top(n)'s cutoff splits the group of score x: some of it is taken (fewer than n
    cells score higher) and some left out (the group ends after the n-th)."""
    return above(x) < n < above(x) + tied(x)


# 3.7: `n_tied_at_cutoff` is the size of the tie group that straddles the cutoff, 0 when the
# cutoff falls between two different scores. At most one distinct score can straddle it.
N_TIED = (tied(VALUES[0]) * straddles(VALUES[0], 2) + tied(VALUES[1]) * straddles(VALUES[1], 2)
          + tied(VALUES[2]) * straddles(VALUES[2], 2))  # fmt: skip


def row(i: str, x: float) -> dict[str, Any]:
    if isnan(x):  # outside the cross-section (5.4.2: finite cells only)
        return {"instrument_id": i, "score": nan, "rank_ordinal": nan, "rank_ordinal_desc": nan,
                "rank_average": nan, "rank_min": nan, "rank_max": nan, "rank_dense": nan,
                "in_top2": False, "n_tied_at_cutoff": N_TIED}  # fmt: skip
    lo, hi = below(x) + 1, below(x) + tied(x)  # scipy rankdata min and max
    ordinal_desc = above(x) + earlier(i, x) + 1  # the order of top(): score desc, id asc
    return {"instrument_id": i, "score": x, "rank_ordinal": below(x) + earlier(i, x) + 1,
            "rank_ordinal_desc": ordinal_desc, "rank_average": (lo + hi) / 2, "rank_min": lo,
            "rank_max": hi, "rank_dense": dense(x), "in_top2": ordinal_desc <= 2,
            "n_tied_at_cutoff": N_TIED}  # fmt: skip


# In instrument_id order, whatever the memory order above.
ROWS = (row(I1, S1), row(I3, S3), row(I0, S0), row(I4, S4), row(I2, S2), row(I5, S5))
assert I1 < I3 < I0 < I4 < I2 < I5
# The tie: the three 2.0 cells share the average rank; ordinal and top(2) split them by id.
assert ROWS[0]["rank_average"] == ROWS[2]["rank_average"] == ROWS[3]["rank_average"] == 3.0
assert (ROWS[1]["in_top2"], ROWS[0]["in_top2"], ROWS[2]["in_top2"]) == (True, True, False)
# The 2.0 group straddles top(2)'s cutoff (1 taken, 2 left out): the count is the group, 3.
# top(1) and top(4) fall between two scores (0); top(3) splits the same group again (3).
assert (straddles(VALUES[0], 2), straddles(VALUES[1], 2), straddles(VALUES[2], 2)) == (
    False, True, False)  # fmt: skip
assert N_TIED == 3
assert (straddles(VALUES[1], 1), straddles(VALUES[1], 3), straddles(VALUES[1], 4)) == (
    False, True, False)  # fmt: skip


def line(r: dict[str, Any]) -> str:
    return "{:<11} {!s:>5} {!s:>7} {!s:>5} {!s:>7} {!s:>5} {!s:>5} {!s:>5}  {!s:<6}  {!s}".format(
        *r.values()
    )


if __name__ == "__main__":
    print(line({"instrument_id": "instrument", "score": "score", "rank_ordinal": "ordinal",
                "rank_ordinal_desc": "desc", "rank_average": "average", "rank_min": "min",
                "rank_max": "max", "rank_dense": "dense", "in_top2": "top(2)",
                "n_tied_at_cutoff": "n_tied_at_cutoff"}))  # fmt: skip
    print(line(ROWS[0]))
    print(line(ROWS[1]))
    print(line(ROWS[2]))
    print(line(ROWS[3]))
    print(line(ROWS[4]))
    print(line(ROWS[5]))
