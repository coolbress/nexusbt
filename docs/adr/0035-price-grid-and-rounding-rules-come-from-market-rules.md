# 35. Price grid and rounding rules come from market rules packs (or data when present)

- Status: Accepted
- Date: 2026-10-28
- Spec: §5.6.4a, §4.7

## Context

Order prices must lie on the tick grid, and money rounding differs by market and cost component.

## Decision

Order prices are snapped conservatively to the grid; comparisons use integer market minimum units (not tick counts per price band). Money rounding is per component from the pack (KR fees, taxes and withholding `down`; others half_up; user overrides). Source order: instrument → `market_rules` → pack → minimum unit.

## Consequences

Tick-table seeds are unverified until checked against sources.
