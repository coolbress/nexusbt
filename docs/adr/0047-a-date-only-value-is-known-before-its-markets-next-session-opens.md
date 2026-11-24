# 47. A date-only value is known before its market's next session opens

- Status: Accepted
- Date: 2026-11-24
- Amends: [ADR 0005](0005-one-availability-rule-decision-ts-a-reference-clock.md)
- Spec: §1.3 INV-01, §5.1.2, §5.1.4, §3.11 `label_entry`

## Context

Spec 5.1.4 gave a value known only by a date D the available instant of the next session's open, so it was used from that next session's close decision: one session after D. The engine's own structure already holds a day between knowing and trading: a daily decision is taken at the close and its orders fill at the next session at the earliest (5.1.3, 5.6.4). Delaying the value by a further session counted that day twice, and a value the user computed from D's close was used a day after the engine's own price terms from the same close. No record gave 5.1.4's reason.

The owner's two-part design (#725 Decisions 204 to 263) makes every value outside trading the user's, given with one date in the user's value tables and with no check of that date.

## Decision

A date-only value dated D belongs to the package's one market and is read as known before that market's next session after D opens. The engine keeps it in the row of D (the first session after D when D is not one; the later date wins where two land on one row), and its `ts_available` is that row's freeze time, so the daily decision at that row's close uses it under ADR 0005's one rule, with no exception. That is the daily decision's information cutoff; `decision_ts` stays the instant the decision is taken, an order fills only in a session that opens after it, so no fill in that market precedes the value, and no other market's sleeve reads it (a cross-market term over a value table is E17).

The user writes the publication date as it is, an evening publication on its own date; a value published elsewhere is moved to this market's date by the user. `evaluate`'s `label_entry = "next_open"` is this rule's pair; a run with `label_entry = "close"` whose graph reads a value table is refused before it starts (E18).

## Considered options

- **The next session's open (the old 5.1.4).** Safe for an evening publication without the user's help, but it holds every value a day after the engine's own terms, and the day it adds is the one the fill already takes.
- **A timestamp per value.** Exact, but the user rarely knows the time of day, and the owner's design keeps four words.

## Consequences

ADR 0005's one rule stands as written; what it gains is how a date-only value's `ts_available` is set: the freeze time of its row. Truncation (P-FUT, INV-02) cuts such a value with its row. A user who dates a value later than its publication is never wrong, only late; one who dates it earlier than its publication is not caught, by the owner's choice that the user's values are not checked (#725 Decisions 222, 229).
