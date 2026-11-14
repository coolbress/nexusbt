"""T-10 by plain logic (spec 5.1.6, 3.7, INV-14): a start date on a holiday.

Run it: `uv run python tests/golden/check/T-10.py` prints one row per run: the start and end
as given, where they land on the tiny XKRX calendar, the number of sessions in between and the
`monthly(-1)` decisions inside. No loops, classes or engine imports
(`tests/golden/test_handcalc_self.py`); the sessions are written out.
"""

from bisect import bisect_left, bisect_right
from typing import Any

# The tiny XKRX sessions of January and February 2020 (spec 4.8): weekdays, minus 2020-01-24
# (Seollal) and 2020-01-27 (its substitute day). ISO dates sort as dates.
SESSIONS = (
    "2020-01-02", "2020-01-03", "2020-01-06", "2020-01-07", "2020-01-08", "2020-01-09",
    "2020-01-10", "2020-01-13", "2020-01-14", "2020-01-15", "2020-01-16", "2020-01-17",
    "2020-01-20", "2020-01-21", "2020-01-22", "2020-01-23", "2020-01-28", "2020-01-29",
    "2020-01-30", "2020-01-31", "2020-02-03", "2020-02-04", "2020-02-05", "2020-02-06",
    "2020-02-07", "2020-02-10", "2020-02-11", "2020-02-12", "2020-02-13", "2020-02-14",
    "2020-02-17", "2020-02-18", "2020-02-19", "2020-02-20", "2020-02-21", "2020-02-24",
    "2020-02-25", "2020-02-26", "2020-02-27", "2020-02-28",
)  # fmt: skip
assert SESSIONS[15:17] == ("2020-01-23", "2020-01-28")  # the two holidays are not sessions
# `monthly(-1)`: the last session of each month, anchored to the calendar, not to the run.
JAN_LAST, FEB_LAST = SESSIONS[19], SESSIONS[39]
assert (JAN_LAST, SESSIONS[20], FEB_LAST) == ("2020-01-31", "2020-02-03", "2020-02-28")
assert len(SESSIONS) == 40


def forward(day: str) -> str:
    """5.1.6: the first session on or after `day`."""
    return SESSIONS[bisect_left(SESSIONS, day)]


def backward(day: str) -> str:
    """5.1.6: the last session on or before `day`."""
    return SESSIONS[bisect_right(SESSIONS, day) - 1]


def count(first: str, last: str) -> int:
    return SESSIONS.index(last) - SESSIONS.index(first) + 1


def run(start: str, end: str, decisions: list[str]) -> dict[str, Any]:
    first, last = forward(start), backward(end)
    return {"start": start, "end": end, "aligned_start": first, "aligned_end": last,
            "n_sessions": count(first, last), "decisions": decisions}  # fmt: skip


# Which month ends fall inside each aligned run is stated and asserted, not searched.
assert "2020-01-28" <= JAN_LAST < FEB_LAST <= "2020-02-28"  # run 1 and run 2 hold both
assert "2020-01-28" <= JAN_LAST <= "2020-01-31"  # run 3 holds January's
assert JAN_LAST > "2020-01-23"  # run 4 ends before January's
ROWS = (
    run("2020-01-24", "2020-02-29", [JAN_LAST, FEB_LAST]),  # Friday holiday; Saturday end
    run("2020-01-02", "2020-02-28", [JAN_LAST, FEB_LAST]),  # a session; INV-14: same decisions
    run("2020-01-27", "2020-01-31", [JAN_LAST]),  # the substitute holiday (Monday)
    run("2020-01-13", "2020-01-27", []),  # end on the holiday: backward to 2020-01-23
)
assert ROWS[0]["decisions"] == ROWS[1]["decisions"]  # INV-14 for the overlapping decisions


def line(row: dict[str, Any]) -> str:
    return "{:<11} {:<11} {:<14} {:<12} {!s:>10}  {!s}".format(
        row["start"], row["end"], row["aligned_start"], row["aligned_end"],
        row["n_sessions"], row["decisions"],
    )  # fmt: skip


if __name__ == "__main__":
    print(line({"start": "start", "end": "end", "aligned_start": "aligned_start",
                "aligned_end": "aligned_end", "n_sessions": "n_sessions",
                "decisions": "monthly(-1) decisions"}))  # fmt: skip
    print(line(ROWS[0]))
    print(line(ROWS[1]))
    print(line(ROWS[2]))
    print(line(ROWS[3]))
