# 44. The time contract: cells seen by the reader's time, values fixed at their row, bars without versions

- Status: Accepted (2026-11-04, #147; 2026-11-16 and 2026-11-17, #240 and #492; 2026-11-17, #494; recorded 2026-11-18, issue #530)
- Date: 2026-11-18
- Spec: §5.1.2, §5.3.1, §3.3, TDS §5.5

## Context

ADR 0005 records the one availability rule: an observation is usable only when `ts_available <= decision_ts`. It does not say how the engine applies that rule inside a computation that runs over rows: in which row a late observation is kept, by whose time a cell is judged when a term reads a window, what a term that reads another term's values sees, or what a later snapshot that replaces a bar does to a row that has already frozen.

Spec 5.1.2 freezes row s of market m at `ready_m(s) = ts_close(s) + Δ_m`, and a decision reads the latest row with `ready_m(s) <= decision_ts(d)`. Two readings of a late cell both satisfy ADR 0005 and still give different values. The case that tells them apart is a single late cell: A's close at row s, with `ts_available = ready(s+1)`. At row s+1:

| Term | Each value fixed at its row (taken) | Every cell judged by the reading row (not taken) |
|---|---|---|
| `CLOSE.latest.shift(1)` | NaN for A | the cell's value |
| `sma(2, CLOSE.latest)` | computed with row s NaN | computed with the cell's value at row s |
| `sma(2, CLOSE)` | reads the cell at row s | reads the cell at row s |

Under the first reading `sma(2, CLOSE)` and `sma(2, CLOSE.latest)` differ when a cell is late, which is surprising without this record.

## Decision

The three rules below are the time contract. Each applies ADR 0005's rule; none adds to it. They are stated in the words of the spec.

1. **Storage is bitemporal, visibility is the reader's** (2026-11-04, #147; spec 5.1.2, 5.3.1). An observation has three times: the observed time (the session s it belongs to), the available time (its `ts_available`) and the reference time of a reader. The block keeps the observation of session s in row s together with its `ts_available`; an observation of s is never placed in row s+1. A term that reads column cells sees, at row t, a cell (for a window term, each cell of its window) only when that cell's `ts_available <= ready_m(t)`. The rule is applied when a window is read and not when the block is built, so one block serves every row and every reader. A late bar of s is NaN in row s for the term values, and the window of a later row t whose `ready_m(t)` reaches its `ts_available` reads it at its own position s (G-TIME-LATE). A reader with a later reference time, the report and `reconcile`, sees the cell as stored.
2. **A term's value at row s is fixed at row s** (2026-11-16 and 2026-11-17, #240, #492; spec 5.1.2, 3.3). A term that reads another term's values (`shift`, a window over a term, an element-wise operation) reads the values that term has at each row, each fixed at its own row's `ready_m`. `col.latest` is a term: its value at row s is fixed at row s; a window that should see each cell as known at t takes the column itself (`inputs=[col]`), not `col.latest`. No term value of row t therefore holds information later than `ready_m(t)`.
3. **Bars carry no versions in v1** (2026-11-17, #494; spec 5.1.2, TDS 5.5). A bar that a later snapshot replaced is not late data but another history of that row. With the same `ts_available` the row shows the replacement's value; with one later than `ready_m(s)` the cell is NaN and counted in `LateBar`. That a frozen row does not change holds between snapshots that hold the same bars for the rows read; a run is reproduced from the snapshot it recorded (`manifest.json`, 5.9.2).

## Considered options

- **Judge every cell, also inside a term's values, by the reading row's `ready`** (#492). Not taken: its cost is in the structure (the plan, the L1 values, shared nodes computed once), where the taken reading's cost is in sentences; it would change what a lagged factor means for someone who knows zipline (ADR 0001); and the spec already gives "the past as known today" an accessor for each kind of data (a window over the column for bars, `.obs(k)` for macro series, `.count(window)` for events).
- **Move a late observation into the row where it becomes available.** Replaced on 2026-11-04 (#147): 5.1.2's former phrase "enters windows from the next row" gave an observation of s a place in a window of s+1.
- **For a replaced bar, require the original's `ts_available`** (#494, option 1). Not taken: the row still changes on a rerun, as a changed value in place of a NaN, and a check for it needs two snapshots where the checker reads one.
- **Change the engine rule to tell a replacement from a late arrival** (#494, option 3). Not taken: with one `ts_available` for each cell the engine cannot tell a bar that first arrived late from a replacement of a bar that was on time.

## Consequences

What is given up, knowingly:

- Identities across the seam hold only when no cell is late: T-12's three forms, and `sma(2, CLOSE)` against `sma(2, CLOSE.latest)`.
- A late cell stays NaN in a lagged or derived value for as long as the expression looks back.
- A replaced bar changes a rerun on the later snapshot: the row shows the replacement's value, or NaN when its `ts_available` is later than `ready_m(s)`. Versions of bars, and a comparison of two snapshots, are not in v1.

What rests on it:

- The plan (5.3.2): each node is computed once on each row the plan gives it, and the executor does not plan and compute again for each decision (#240).
- The L1 cache's value shape (5.3.9): a node's values by row, valid for every later reader because a row's values do not change once frozen.
- #499's refusal (decided 2026-11-18): a term whose degree is known and is not 0, such as `Price.close.latest`, keeps through `shift(k ≥ 1)` or as a `Factor` input of a window of two rows or more the value each row gave it, adjusted as of that row, so across a split the earlier row stands on another share basis; the graph build refuses that input (E17) instead of reading it silently.
- `tests/unit/compute/test_executor.py::test_cutoff_hides_late_cells` pins the three terms of the table above.
