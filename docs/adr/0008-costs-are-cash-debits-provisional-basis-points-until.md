# 8. Costs are cash debits; provisional basis points until verified

- Status: Accepted
- Date: 2026-10-28
- Spec: §5.6.8

## Context

Putting spread and impact into both price and cash double-counts.

## Decision

All costs are recorded as cash debits. Until historical fee and tax tables are verified from sources, fixed `provisional` bps per market are the default and the report says so. Cost 0x/1x/2x comparison is always shown.

## Consequences

Results are labelled provisional until cost tables are verified.
