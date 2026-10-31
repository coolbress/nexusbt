# 16. Kernels in Python, numpy and Numba, behind a seam that Rust can replace

- Status: Accepted
- Date: 2026-10-28
- Spec: §2.4, §11.2

## Context

Speed matters, but rewriting before profiling wastes effort.

## Decision

Reference implementations in Python/numpy; only measured hot loops in Numba. Three hot kernels (window and cross-section kernels, the simulator step, accounting state) sit behind a narrow interface of Arrow (or buffer-sharing numpy) arrays and column-array state. Replace one with a Rust crate (PyO3/maturin, optional build) only when M1 and P1–P7 measurements show Numba misses the budget, with a bit-equality test against the Python reference. Intraday and tick (E4) get a Rust core designed then and compared with a Nautilus bridge.

## Consequences

The seam cannot pass Python objects (arrays and integer codes instead of callbacks and dicts).
