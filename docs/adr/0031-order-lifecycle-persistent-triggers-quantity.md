# 31. Order lifecycle: persistent triggers, quantity conservation, exit orders

- Status: Accepted
- Date: 2026-10-28
- Spec: §5.6.2, §5.6.2a

## Context

Lifecycle, trigger state and quantity accounting are often conflated.

## Decision

Separate them. Exit orders are created right after the entry fill, resized on every holding change and never expire. Intraday sale proceeds are not used for intraday buys on the same bar; buyable quantity uses the real cost function. The state machine uses column arrays (Numba only after measurement).

## Consequences

More states to test; quantities always reconcile (`requested = filled + cancelled + remaining`).
