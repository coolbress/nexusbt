# 26. Events are the source of truth; attribution, exposure and reconciliation are derived

- Status: Accepted
- Date: 2026-10-28
- Spec: §5.9

## Context

Derived tables drift if they are written independently.

## Decision

Every table can be rebuilt from `orders` and `account_events` (versioned schemas), and a test proves it. Currency attribution splits local, FX and cross terms exactly; cost attribution splits direct costs and path effects. Paper-ledger reconciliation replays recorded snapshots through the same state machine; comparison with the latest data is a restatement.

## Consequences

Event schemas are versioned and stable.
