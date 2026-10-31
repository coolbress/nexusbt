# 12. Run records: temporary then sealed, source captured, physical and value hashes, SQLite index

- Status: Accepted
- Date: 2026-10-28
- Spec: §5.9

## Context

Results must be reproducible and attempt counts must not be lost.

## Decision

Capture source, lock file and parameters; seal the run folder only after success (interrupted runs are recoverable). Separate file integrity (physical hash) from result equality (value hash, TDS 4.5 canonical serialisation). Attempt and exposure records are append-only in SQLite. `rerun` fails if the snapshot is gone.

## Consequences

Run folders are larger; reproduction needs the snapshot.
