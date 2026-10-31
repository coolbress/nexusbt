# 9. float64 only in v1

- Status: Accepted
- Date: 2026-10-28
- Spec: §5.3.10, §7

## Context

float32 error can flip the top-N boundary.

## Decision

v1 computes in float64. The memory budget (P7) is measured with float64. float32 only later, as an explicit, measured optimisation.

## Consequences

Higher memory use; simpler numerical guarantees.
