"""T-23 by index arithmetic (spec 3.7, INV-14): `every(n)` is anchored to `session_ord`.

Run it: `uv run python tests/golden/check/T-23.py` prints one row per run: the decisions of
`every(5)` (and once `every(5, offset=2)`) inside the run, next to what counting from the
run's first session would give. No loops, classes or engine imports
(`tests/golden/test_handcalc_self.py`); the sessions are written out and indexed by
`session_ord`, which the tiny package numbers from 0 at 2020-01-02.
"""

from bisect import bisect_left
from typing import Any

# The tiny XKRX sessions of January and February 2020 (spec 4.8), index = session_ord.
S = (
    "2020-01-02", "2020-01-03", "2020-01-06", "2020-01-07", "2020-01-08", "2020-01-09",
    "2020-01-10", "2020-01-13", "2020-01-14", "2020-01-15", "2020-01-16", "2020-01-17",
    "2020-01-20", "2020-01-21", "2020-01-22", "2020-01-23", "2020-01-28", "2020-01-29",
    "2020-01-30", "2020-01-31", "2020-02-03", "2020-02-04", "2020-02-05", "2020-02-06",
    "2020-02-07", "2020-02-10", "2020-02-11", "2020-02-12", "2020-02-13", "2020-02-14",
    "2020-02-17", "2020-02-18", "2020-02-19", "2020-02-20", "2020-02-21", "2020-02-24",
    "2020-02-25", "2020-02-26", "2020-02-27", "2020-02-28",
)  # fmt: skip
assert (len(S), S[15], S[16]) == (40, "2020-01-23", "2020-01-28")  # the holidays are not in
END = S[39]  # every run ends on the last session written out, 2020-02-28
N = 5


def start_of(day: str) -> str:
    """5.1.6: the first session on or after `day`."""
    return S[bisect_left(S, day)]


def anchored(offset: int) -> list[str]:
    """3.7: the sessions with (session_ord - offset) mod N == 0, over the whole calendar."""
    return list(S[offset::N])


def run(term: str, offset: int, start: str) -> dict[str, Any]:
    first = start_of(start)
    grid = anchored(offset)
    # The run's decisions: the fixed grid cut to the run period. The wrong anchor: every N-th
    # session counted from the run's first session.
    return {"term": term, "start": start, "end": END, "aligned_start": first,
            "decisions": grid[bisect_left(grid, first):],
            "from_run_start": list(S[S.index(first)::N])}  # fmt: skip


assert anchored(0) == [S[0], S[5], S[10], S[15], S[20], S[25], S[30], S[35]]
assert anchored(2) == [S[2], S[7], S[12], S[17], S[22], S[27], S[32], S[37]]
ROWS = (
    run("every(5)", 0, "2020-01-02"),  # start on ord 0: the whole grid, both columns equal
    run("every(5)", 0, "2020-01-08"),  # ord 4: the grid from ord 5 on
    run("every(5)", 0, "2020-01-24"),  # holiday -> 2020-01-28, ord 16: the grid from ord 20 on
    run("every(5, offset=2)", 2, "2020-01-02"),
)
assert ROWS[0]["decisions"] == ROWS[0]["from_run_start"]
assert ROWS[1]["decisions"] == ROWS[0]["decisions"][1:]  # INV-14: the overlap is identical
assert ROWS[2]["decisions"] == ROWS[0]["decisions"][4:]
assert ROWS[1]["decisions"] != ROWS[1]["from_run_start"]  # the start does not anchor
assert ROWS[2]["decisions"] != ROWS[2]["from_run_start"]


def line(r: dict[str, Any]) -> str:
    return "{:<19} {:<11} {:<14} {}\n{:>47} {}".format(
        r["term"], r["start"], r["aligned_start"], r["decisions"], "from run start:",
        r["from_run_start"],
    )  # fmt: skip


if __name__ == "__main__":
    print("{:<19} {:<11} {:<14} {}".format("term", "start", "aligned_start", "decisions"))
    print(line(ROWS[0]))
    print(line(ROWS[1]))
    print(line(ROWS[2]))
    print(line(ROWS[3]))
