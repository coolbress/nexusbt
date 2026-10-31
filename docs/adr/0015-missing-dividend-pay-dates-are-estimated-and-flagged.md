# 15. Missing dividend pay dates are estimated and flagged

- Status: Accepted
- Date: 2026-10-28
- Spec: §5.6.11

## Context

Some sources lack pay dates; failing every run is too strict.

## Decision

Estimate from the median historical gap by country and kind (or a configured value) and count them as "estimated". `fail` is selectable.

## Consequences

Cash timing for some dividends is approximate and reported.
