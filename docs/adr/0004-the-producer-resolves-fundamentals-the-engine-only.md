# 4. The producer resolves fundamentals; the engine only queries `fundamentals_state`

- Status: Accepted
- Date: 2026-10-28
- Spec: §5.3.5, TDS 5.17–5.18

## Context

"Latest filing" and "latest amendment of the latest period" are different queries, entangled with consolidated/separate statements, TTM and source choice. Accounting rules written in two places drift apart.

## Decision

The data producer publishes resolved state intervals (`fundamentals_state`, TDS 5.18). The engine only looks up the interval valid at the decision time.

## Consequences

More work on the producer side. Until a producer publishes it, the engine is tested on synthetic data only. Raw facts (`fundamentals_events`) stay explanatory.
