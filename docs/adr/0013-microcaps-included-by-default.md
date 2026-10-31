# 13. Microcaps included by default

- Status: Accepted
- Date: 2026-10-28
- Spec: §3.6

## Context

Hidden exclusions change results without the user knowing.

## Decision

No hidden exclusion. `exclude_microcap = true` removes the bottom 20% by market cap per market.

## Consequences

Default results include illiquid names; liquidity filters are written visibly in strategy templates.
