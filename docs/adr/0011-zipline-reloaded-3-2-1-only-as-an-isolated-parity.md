# 11. zipline-reloaded 3.2.1 only as an isolated parity reference

- Status: Accepted
- Date: 2026-10-28
- Spec: §8.1

## Context

zipline-reloaded was the previous research engine; it is a useful oracle but has known bugs.

## Decision

Daily backtests run in NexusBT. A pinned zipline-reloaded runs only in a separate `tests/parity` environment; engine code never imports it. Known zipline bugs are not ground truth.

## Consequences

Parity tests need their own environment. Replaces the earlier plan to backtest with zipline-reloaded.
