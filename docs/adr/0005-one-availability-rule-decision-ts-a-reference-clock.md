# 5. One availability rule, `decision_ts`, a reference clock, and sleeves

- Status: Accepted
- Date: 2026-10-28
- Spec: §5.1

## Context

Multi-market research mixes time zones and currencies; look-ahead bias usually enters through time, not data.

## Decision

Every observation is usable only when `ts_available <= decision_ts`. Korea and the US are separately funded sleeves. The reference clock (`KR_close` default for KR+US, `US_close`, `market_local`) is a setting. The base currency never changes information time. Cross-sections are per market by default; cross-market cross-sections only at the final stage.

## Consequences

One rule to test everywhere (INV-01). Multi-market results depend on the clock, which is recorded in every run.
