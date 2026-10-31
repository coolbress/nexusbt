# 21. zipline parity narrowed to equal semantics

- Status: Accepted
- Date: 2026-10-28
- Spec: §8.1, §5.6.15

## Context

zipline's daily-bar limit/stop triggering differs from NexusBT's adverse OHLC rule. The project owner asked for comparison tests against zipline.

## Decision

Compare order types only through a preset that imitates zipline semantics (L2-d). NexusBT's own rules are tested by hand-written per-session arithmetic. Price terms are compared on default inputs (return series default `close_tr`). When parity disagrees, the hand calculation decides; a zipline error is recorded as a known difference. Long-short parity L2-e is included. Confirmed by the project owner on 2026-10-28.

## Consequences

Parity proves the shared semantics, not NexusBT's adverse-fill rules.
