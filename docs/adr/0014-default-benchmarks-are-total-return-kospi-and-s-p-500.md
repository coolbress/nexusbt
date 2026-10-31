# 14. Default benchmarks are total-return KOSPI and S&P 500; none if missing

- Status: Accepted
- Date: 2026-10-28
- Spec: §3.11 `[benchmarks]`

## Context

Silently building a benchmark from the investable universe is another strategy.

## Decision

Benchmarks are read from index series in the snapshot. If missing, the benchmark is "n/a".

## Consequences

Benchmark availability depends on the snapshot.
