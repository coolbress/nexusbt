# 3. Adjustment by cumulative factors, a reference implementation, and proven kernels only for shortcuts

- Status: Accepted
- Date: 2026-10-28
- Spec: §5.3.3, §8.3

## Context

`P_t[s] = raw[s]·C[t]/C[s]` is exact, but a scalar cannot fix an arbitrary term afterwards (thresholds, non-linear terms, price-level ranks).

## Decision

A slow reference implementation that builds each day's as-of window is the oracle. Only registered kernels that declare a homogeneity class and pass the P-ADJ property test may take the fast path. Because of reverse splits, check events against factors instead of factor monotonicity.

## Consequences

Two code paths for adjusted windows, tied by a property test.
