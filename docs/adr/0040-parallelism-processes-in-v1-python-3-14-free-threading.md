# 40. Parallelism: processes in v1; Python 3.14 free-threading is a seam swapped after measurement

- Status: Accepted
- Date: 2026-10-28
- Spec: §5.3.8, §5.3.10, §7

## Context

Free-threaded Python 3.14 (3.14t) is officially supported and Numba 0.65 supports it, but C-extension support is not yet universal.

## Decision

v1 runs on Python 3.13 with worker processes (`[compute] workers`) for sweeps, CPCV paths and markets. The parallel executor is a seam with two implementations (`ProcessExecutor`, `ThreadExecutor`) behind one interface, with a bit-equality test. Switch the default by amending this ADR only when every locked dependency ships 3.14t wheels and P5, P6 and P11 measurements show the threaded version wins on memory and time. Kernels keep `parallel=False` and the fixed reduction order in both.

## Consequences

Process start-up and memory overhead in v1.
