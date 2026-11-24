# 28. Three hashes: physical, value, semantic

- Status: Accepted
- Date: 2026-10-28; amended 2026-11-24 (`tds-hash-2`)
- Spec: §5.9.4, TDS 4.5

## Context

Arrow IPC bytes differ by implementation and version, so bytes cannot define "same data" in a public standard.

## Decision

A language-neutral canonical value serialisation (with published test vectors) defines the value hash; value hash + resolved metadata is the semantic hash, which the engine uses.

Amended 2026-11-24 (#705 B4; #725 Decisions 144 to 149, 157 to 161, 196 to 198): a dataset that declares `partitioning` takes its value hash from its partitions' value hashes, each the same serialisation over that partition's rows, joined in bytes that name the `partitioning` columns and each partition by its values (TDS 4.5 step 6). Rows stay in key order, not file order, and a per-file value hash stays optional. Not taken: an order-free hash adding or multiplying per-row hashes.

## Consequences

The checker carries one serialisation function. A change in one partition is hashed again alone; the same values hash the same however they are split into files; a package that declares the earlier `tds-hash-1` is refused (TDS-M014) until its hashes are written again.
