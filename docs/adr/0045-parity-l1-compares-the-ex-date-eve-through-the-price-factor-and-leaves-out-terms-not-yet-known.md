# 45. L1 parity: the ex-date eve compared through the price factor, cells with terms not yet known left out

- Status: Accepted (2026-11-19, #252, the owner's approval)
- Date: 2026-11-19
- Spec: §8.1, §5.3.3a, §5.3.4, §9.7 (3)

## Context

The first L1 run on synthetic `small` (#252) agreed with zipline 3.2.1 on every case except three kinds of cell, none of which is an error of either engine. Spec 9.7 (3) accepts no widening of `KNOWN_DIFFERENCES.md` without an ADR.

- (A) The row before an ex-date. 8.1 aligns zipline's output for D with the engine's row `prev_session(D)`. zipline's D view is built at D's open with every adjustment effective at D applied to the window; the engine's row is fixed at its own ready time (ADR 0044, rule 2), before the event. A price level there differs by exactly that session's price factor (US:T00116 on 2016-01-13: 443.619 x 0.991998 = 440.069); a ratio does not differ.
- (B) Terms not known at the row. In row t's window the engine uses the version of an event known at `cutoff(t)`: none before its terms are published (5.3.4), and for an amended or cancelled event the version known then (5.3.3a). zipline has no knowledge time: its adjustment table holds the final version from the ex-date. Half of the synthetic KR dividends publish their amount 30 to 60 days after the ex-date (4.8 (4)).
- (C) A Filter on a missing input. `close > X` on a halted bar is unknown in the engine and false in zipline: the kind V31-21 records for `~`.

## Decision

- (A) is compared, not left out: on a row whose next session is an instrument's ex-date, a price-level case compares the engine's value x m (the product of the price factors of the events effective that session; split factors only for the cases read without dividends) with zipline's; a ratio compares as it is; `close > X` compares `engine close x m > X`.
- (B) is left out: a cell whose window holds the ex-date of an event whose final version is not known at `cutoff(t)` is not compared.
- (C) is left out as V31-21's cells are.
- The test computes each set from the package's corporate actions and calendar and fixes, for each case, the cells compared through m, the cells left out and the cells compared; a change in any count fails it. The evidence file carries the counts.

The engine's rules stay as the spec has them: (A) is ADR 0044's fixed row, (B) is 5.3.4 and 5.3.3a's point-in-time adjustment, (C) is the three-valued Filter of V31-21.

## Considered options

- Compare (A) by aligning zipline's D with the engine's D instead. Not taken: zipline's D window ends at D-1, so every other row would be off by one.
- Build zipline's bundle so that it knows terms late. Not taken: zipline's adjustment table has no knowledge time; any such bundle would differ from zipline's own meaning.
- Generate the CI fixture without late terms. Not taken: it would remove from the comparison the case 5.3.4 exists for, and change 4.8's generator.

## Consequences

- The L1 comparison does not cover the engine's point-in-time adjustment. It is tested by `tests/unit/compute/test_adjust.py::test_late_terms_leave_the_event_out_until_published` (5.3.4) and `::test_revision_changes_window_by_cutoff` (an amendment, 5.3.3a), `tests/unit/compute/test_executor_adjust.py::test_pending_event_and_late_cell_in_one_window` (5.3.4 through the executor), and `tds/tests/test_actions.py::test_resolver_at_cutoffs` (a cancelled version at each cutoff, 5.3.3a) and `::test_late_terms_revision_visible_at_ex_date`. A cancelled event inside an adjusted window is tested at the resolver only, not through `adjusted_window`.
- Every US dividend, and the KR events whose terms are known at the ex-date, stay in L1-b.

Relation to ADR 0021: 0021 narrows parity to equal semantics; this record names the three cells where the semantics are not equal and how each is compared.
