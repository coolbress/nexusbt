# 43. A schedule decides in a period only when the calendar settles which session the pick is

- Status: Accepted (2026-11-15, by the coordinating session at the owner's request, issue #461 Decision)
- Date: 2026-11-15
- Spec: §3.7, §5.1.3, §5.1.6, §1.3 INV-01, INV-02, INV-14

## Context

Spec 3.7 says `nx.monthly(day)` is "the `day`-th session of the month (from 1), counted from the end when negative", and the same inside the ISO week, the quarter-end months and one month of the year. It did not say what the sessions of a period are when the schedule calendar starts or ends inside it.

As first built (#462), a period the calendar holds only in part counted with the sessions held. On a calendar of weekday sessions from 2020-01-15 to 2020-03-13, `monthly()` decided on 2020-03-13 and `monthly(1)` on 2020-01-15. The decision set then depends on where the snapshot's calendar is cut: a snapshot whose calendar goes a few weeks further has no 2020-03-13 decision and has 2020-03-31 instead, silently. The calendar of 4.5 F-02 is cut to the bars' first and last day, and the calendar `live` reads ends today, so there `monthly()` would decide on every day.

Golden T-10's fourth row already answers the question for the run's edge: a run that ends on 2020-01-23 has no `monthly(-1)` decision, so the run's last session is not taken for a month end.

## Decision

A schedule that counts inside a period (`monthly`, `weekly`, `quarterly`, `annually`) decides in a period only when the calendar settles which session the pick is:

- a pick counted from the end (`day < 0`) needs the calendar to hold a session after the period;
- a pick counted from the start (`day > 0`) needs the calendar to hold a session before the period;
- a pick that falls back to the period's first or last session, because the period holds fewer sessions than `|day|`, needs both.

Otherwise the schedule has no decision in that period. `daily()` and `every(n)` do not change. The rule reads the calendar only, never the run's start or end.

On the calendar above:

| Schedule | Decisions |
|---|---|
| `monthly()` | 2020-01-31, 2020-02-28 |
| `monthly(-2)` | 2020-01-30, 2020-02-27 |
| `monthly(1)` | 2020-02-03, 2020-03-02 |
| `monthly(5)` | 2020-02-07, 2020-03-06 |
| `monthly(99)` | 2020-02-28 |
| `monthly(-99)` | 2020-02-03 |
| `quarterly()` | none |

`tests/unit/data/test_calendar.py::test_partial_period_decides_only_when_the_calendar_settles_it` checks this table and the same rule inside a week.

Why:

- 3.7 anchors every schedule to the calendar, and T-10 applies that to the run's edge. Counting a partial period as whole reads the calendar's edge the other way round: its last session becomes a month end because the calendar stops there.
- "s is the last session of its month" is something to know. A calendar that ends at s does not hold it, so the engine would state what the snapshot cannot show (the reading INV-01 gives for data), and a longer snapshot would take the decision away again (INV-02). Under this rule a decision that was made stays when the snapshot grows; the only change is a decision added at the edge once the calendar settles it.
- What it gives up is small. A decision on the calendar's last session cannot fill in a backtest, since an order first fills in the first later session of the market (5.1.3). A pick counted from the start loses the calendar's first period, where no window has history yet.

## Considered options

- Keep a partial period counting with the sessions held, and say so in 3.7. Not taken, for the reasons above; it would also make `live` decide every day.
- Add a notice when the run period reaches a period the calendar does not settle. Not now: 6.6 has no class for it (E9's text is "start or end is not a session"), and a new class is more than this defect needs. Whether a run says so is left for the spec's next revision.
- For `live`, count the next session predicted with exchange_calendars (2.2) as held. Left to the ticket that builds `live` (5.9.6): it is how `live` supplies what this rule asks for, so the two are one rule.

## Consequences

- A package whose `calendar_sessions` ends on the last session of a month has no `monthly()` decision in that month. 10.1's example for T1.3, "12 month-end sessions (KR, 2019)", runs on a package that goes into 2020 (`make_snapshot`'s `end`), since the calendar of `small` ends on 2019-12-30.
- The calendar of 4.5 F-02 ends on the bars' last day, so its last period is never settled. A `calendar_sessions` table that holds the exchange's scheduled sessions past the bars settles it with no engine change; whether TDS 5.4 should say so is not decided here.
- Golden T-10 and T-23 do not change: every pick of T-10 lies in a period the `tiny` calendar settles, and `every(n)` is not touched.
- The rule is one sentence under 3.7's schedule table, written under the M1 freeze's defect rule (#43, Decisions 2026-11-04): a case 3.7 left undefined, with a counter-example.
