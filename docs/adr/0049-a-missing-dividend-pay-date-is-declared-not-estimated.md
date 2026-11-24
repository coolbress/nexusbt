# 49. A missing dividend pay date is declared, not estimated

- Status: Accepted
- Date: 2026-11-24
- Supersedes: [ADR 0015](0015-missing-dividend-pay-dates-are-estimated-and-flagged.md)
- Spec: §5.6.11; TDS 5.11

## Context

ADR 0015 estimated a missing pay date from the median gap of the same country's and kind's events. When no row of a package has a pay date, there is nothing to take a median of, and the estimate is a fact the user did not give (#725 Decision 204).

## Decision

`pay_date` is optional. Without it the user declares once when dividend cash arrives: on the ex-date, or a number of calendar days after it. Without that declaration the tool stops and asks; there is no default. From the ex-date until payment the dividend is a receivable outside buying power, as spec 5.6.11's accounting already holds. TDS 5.11's `pay_date_status` keeps `estimated`, for a producer who says a date is estimated, and gains `declared` (#725 Decisions 214, 215; #752's Decisions).

## Considered options

- **The engine's median estimate (ADR 0015).** Works where some rows carry a date; invents one where none do.
- **The ex-date by default.** Simple, but it makes unpaid cash spendable without the user saying so.

## Consequences

A package without pay dates cannot be built until the user declares the rule; the declaration is kept in `corporate_actions`'s `params` and enters the semantic hash.
