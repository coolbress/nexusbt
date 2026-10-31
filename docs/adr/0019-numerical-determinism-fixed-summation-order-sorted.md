# 19. Numerical determinism: fixed summation order, sorted-index reductions, same-environment promise

- Status: Accepted
- Date: 2026-10-28
- Spec: §5.3.10

## Context

Bit-identical results across chunkings and permutations need a defined summation order.

## Decision

The promise covers the same environment (same lock file, same CPU family). Windows fold left in row order (definition A); cross-sections reduce in `instrument_id` order. No cumulative-sum differencing, O(1) running sums, BLAS or fastmath. Transcendental functions use the same compiled element functions in reference and fast paths. A pre-registered alternative (definition B, absolute `session_ord // 64` block partial sums) is adopted by amending this ADR only if A misses the M1 budget. User functions promise only "same window → same output".

## Consequences

Some fast kernels are slower (measured in M1).
