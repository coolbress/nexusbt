# 25. Three cache layers (L0 raw blocks, L1 term values, L2 runs)

- Status: Accepted
- Date: 2026-10-28
- Spec: §5.3.9

## Context

Re-decompressing Parquet and re-mapping dictionaries on every run is slow.

## Decision

L0 memory-maps uncompressed Arrow IPC raw blocks. Keys include partition sha256, every version and availability time of the corporate-action chain, axis datasets, stable market fields, propagated input rows, the resolved query policy, external inputs and captured constant globals, so keys cannot drift. Nodes reading non-constant globals disable L1; optional `value_sha256` is not identity; L0 has its own LRU. Key rules in M1, implementation in M6.

## Consequences

More key fields to maintain; memory budget counts the process tree.
