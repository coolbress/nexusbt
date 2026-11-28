# 55. An instrument with an inexact share ratio returns after the event

- Status: Accepted
- Date: 2026-11-28
- Amends: [ADR 0034](0034-integer-share-arithmetic-stale-marks-follow-event-bases.md)
- Spec: §5.6.1 "events without an exact ratio" (2), (6) and (8), §8.2 G-107

## Context

ADR 0034 (amended 2026-10-29) excludes an instrument whose share-changing event has no exact ratio "from the time the event becomes visible on", and spec §5.6.1 step (6) kept it out until the end of the run ("v1, a simple rule"). A name with one such event was then absent for the rest of every run, which tilts the universe toward names that never had a bonus issue, a rights issue or a merger (#855).

The owner's second look at the design (asked 2026-11-27, answered 2026-11-28) allowed decisions taken before any other engine had been read to be overturned where a better way exists. This is one of its answers.

## Decision

Under `[corporate_actions] decimal_ratio = "exclude_instrument"` (the default), steps (1) to (5) of §5.6.1 stay: the instrument leaves the universe at the first decision with `decision_ts ≥ v(e)` and not before, a holding is sold by the ordinary rules or closed at the last valid close before the event, and a feature whose window crosses the event is NaN.

The instrument is a candidate again from the later of two decisions (the owner, 2026-11-28, #855; spec change #857):

- the first decision on a session after the session of `ts_effective`;
- the decision after the first one with `decision_ts ≥ v(e)`.

The second keeps an event made public after its effective session from leaving the instrument in: it is still out for one decision, so that (3) and (4) close a holding whose share count is in doubt (the owner's answer on #855's first "Not sure yet" item).

From then on the instrument is read like any other. A feature whose window still crosses the event stays NaN, so the name enters a selection again only once the windows of the strategy's terms are clear of the event. The rule holds for each event on its own: while another such event keeps the instrument out by its own step (2), it stays out. `ca_exclusions.parquet`'s `excluded_to` is the last decision before the instrument comes back, or the end of the run when the run ends first.

`require_exact` and `literal` are unchanged.

## Considered options

- **Keep the instrument out until the end of the run** (the rule of 2026-10-29). Simple, but every run drops each name that ever had such an event, and the universe tilts toward names without one.
- **Return from the first decision after the effective session only.** An event made public after its effective session would then never take the instrument out, and a holding whose share count is in doubt would not be closed.

## Consequences

The universe no longer loses a name for good over one event without an exact ratio. The exclusion is reported as a span (`excluded_from`, `excluded_to`), and golden case G-107 pins the dates of the return. The rule is specified only: no code under `src/` implements the removal yet, so no test's expected value changed.
