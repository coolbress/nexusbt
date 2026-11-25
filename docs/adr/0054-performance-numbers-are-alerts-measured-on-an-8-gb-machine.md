# 54. Performance numbers are alerts measured on an 8 GB machine, and no machine is a target

- Status: Accepted
- Date: 2026-11-25
- Amends: [ADR 0016](0016-kernels-in-python-numpy-and-numba-behind-a-seam-that.md)
- Spec: §1.4, §2.7, §7, §10 M6 (T6.6, T6.11, T6.28, T7.V)

## Context

Spec chapter 7 named a reference machine (16 GB) and called P1 to P11 gates of the release, and ADR 0016 replaces a Numba kernel with Rust "only when M1 and P1–P7 measurements show Numba misses the budget". The maintainer measures on an 8 GB machine, the numbers were set before anything was measured, and a gate on one named machine says little about another user's (#725 Decisions 256, 257).

## Decision

No machine is a performance target. Measurements are taken on an 8 GB machine; the spec and the docs keep the measured records and say what the engine runs well on (256).

The numbers of P1 to P9 and P11 are first estimates, re-written after the first measurement; afterwards a measurement worse than the one before raises an alert, a regression to fix. None is a pass/fail gate; P10 (the zipline comparison tolerance) stays a correctness gate. M6 measures, records and compares, and its correctness gates stay (257; #752's Decisions, 2026-11-25).

A number the engine's behaviour reads stays a rule: the process-tree memory budget `[compute] memory_budget_gb`, by which chunks split; the running indicator after 2 s; static checks before the heavy computation.

ADR 0016 is amended in one place, its trigger: a Numba kernel is considered for a Rust replacement when, measured on this 8 GB machine, most of a workload's time is in that one kernel and the owner judges the workload too slow to use. The replacement is tested bit for bit against the Python reference, as before (#752's Decisions, 2026-11-25).

Spec chapter 0's "a faster implementation checked bit for bit against the reference" and 5.3.3's "relative 1e-12" for the adjustment shortcut disagree; that is settled after measurement, not here (258).

## Considered options

- **Keep the gates on a named machine.** Clear pass/fail, but tied to hardware the users do not share and to numbers set before measuring.
- **An alert of "slower than before" as the Rust trigger.** Mechanical, but a first measurement has nothing before it, and a slowdown is a regression to fix, not a reason to rewrite (the owner).

## Consequences

Release no longer waits on a time; it waits on correctness. A slow workload becomes a decision of the owner's with a measurement beside it. Result files are named by the measuring machine's kind, never a host name.
