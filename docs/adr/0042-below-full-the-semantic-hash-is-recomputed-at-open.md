# 42. Below `full`, the semantic hash is recomputed at open; the row bytes are trusted as declared

- Status: Accepted (2026-11-10, by the owner, issue #329 Decisions)
- Date: 2026-11-15
- Spec: §4.2, §4.4, §5.3.9, TDS 4.5

## Context

`open_snapshot` took the three package hashes from `tds.json` `hashes` as declared. At `[data] verify = "manifest"` (the default) or `"schema"` nothing compared them with the package, so a `tds.json` whose `markets` or availability rules were edited after `tds hash --write` opened with the old semantic hash. Spec 4.2 says such a change makes it different data, and the semantic hash becomes the run manifest's `snapshot_semantic_hash`, part of cache keys (5.3.9), run records (#249) and rerun stamps (#250), where a wrong identity cannot be repaired later.

## Decision

Below `full`, the row bytes are trusted as declared and the manifest's metadata is not:

1. The semantic hash is recomputed at open from `tds.json` as it stands and each dataset's declared `value_sha256` (TDS 4.5's canonical JSON). No row is read. An edited `markets`, availability rule or other hashed field opens with a different semantic hash.
2. The value hash and the physical hash are taken as declared.
3. When a dataset declares no `value_sha256`, or `hashes` lacks the value or physical hash, every hash is computed from the rows, as before.

At `full` the checker reads every row and checks every declared hash, so the three are the computed ones.

## Considered options

- Compute every hash at open: reads every row, against P1's manifest-level budget.
- Keep trusting all three declared values below `full`: the semantic hash could name data the package no longer holds.

## Consequences

An edit of row data that keeps the declared value hashes is still caught only at `full` (or by the sha256 check `rerun`, `reconcile`, `live` and `fill` ask for, 4.4-1). Spec 4.4 is frozen for M1, so this rule lives here until the spec is next revised.
