# 10. No future lock: segments, attempt records and DSR

- Status: Accepted
- Date: 2026-10-28
- Spec: §6.1–6.3

## Context

Locking out future data is impractical because new data accumulates too slowly.

## Decision

The user defines train/validation/test segments. The engine records exposures and candidate counts and shows DSR and PBO. Run counts and candidate counts are kept apart; without inputs the statistics are "n/a".

## Consequences

Hygiene is visible, not enforced. Users see how many attempts a result took.
