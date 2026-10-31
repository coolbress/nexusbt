# 1. Keep the zipline Pipeline vocabulary, build a new executor

- Status: Accepted
- Date: 2026-10-28
- Spec: §3.3–3.5, §5.3

## Context

zipline's Pipeline concepts (Factor, Filter, Classifier, `.latest/.rank/.zscore/.top`, `mask=`, `groupby=`) are well known and sound. Measurements of zipline internals showed the slowness comes from per-date Python loops, window copies, per-holding value lookups and bundle conversion, not from the concepts (20–68x overhead).

## Decision

Keep zipline's names and meanings for terms and operators. Build a new planner/pruning executor over dense per-market blocks.

## Consequences

No full zipline source compatibility; only a thin `compat.zipline` layer. Users who know zipline read NexusBT code without relearning terms.
