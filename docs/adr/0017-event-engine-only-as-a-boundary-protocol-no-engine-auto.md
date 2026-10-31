# 17. Event engine only as a boundary (Protocol); no `engine="auto"`

- Status: Accepted
- Date: 2026-10-28
- Spec: §11.1–11.2

## Context

Silently switching fill semantics between engines makes results incomparable.

## Decision

NautilusTrader attaches behind `ExecutionBackend` in E4. Backends emit fill events only; the engine keeps the accounting truth. v1 fails explicitly on unsupported features.

## Consequences

No automatic engine choice.
