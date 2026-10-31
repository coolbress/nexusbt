# 6. Daily state machine and the order types are in v1

- Status: Accepted
- Date: 2026-10-28
- Spec: §5.6

## Context

Reviewers suggested deferring order types; the project owner decided they belong in v1.

## Decision

v1 implements market, limit, stop and stop-limit orders, day/GTC, volume-capped partial fills and pending orders. On a daily bar only open-before-close is known; the unknown high/low order is assumed adverse to the order owner. Intraday order needs minute or tick data (E4). Capacity is approximated by the past 20-session average volume and is not called an open-auction liquidity measure.

## Consequences

Order-type behaviour is tested by hand-computed cases, not by matching another engine.
