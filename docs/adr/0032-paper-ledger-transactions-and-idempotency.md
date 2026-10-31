# 32. Paper-ledger transactions and idempotency

- Status: Accepted
- Date: 2026-10-28
- Spec: §5.9.6–5.9.7

## Context

Live (paper) runs must not double-order after a crash or retry.

## Decision

The idempotency key is (ledger, decision, graph, parameters), without checkpoint numbers. Single-writer lock, state-version compare, HEAD swap as the commit point, recovery at each commit boundary. Reconciliation replays recorded snapshots by default; comparison with the latest data is a restatement.

## Consequences

A second concurrent writer fails (E35).
