# 37. Snapshot immutability: clone first, read-only, atomic publish, file identity

- Status: Accepted
- Date: 2026-10-28
- Spec: §4.2, §4.4, TDS 4.1

## Context

Reusing unchanged partitions saves disk, but hard links let one edit change two snapshots.

## Decision

Producers never edit published files in place. Unchanged partitions are reused by APFS `clonefile` or reflink; hard links + read-only only where cloning is unavailable. Publish = staging folder → check → atomic `LATEST`. The engine records the identity `(dev, inode, size, mtime_ns)` of each sha256-verified file in stamps and L0 and recomputes when it differs. Pins default to `index+root`; otherwise `retention: unmanaged`.

## Consequences

Identity checks guard against accidents, not attacks (`verify="full"` reads every byte).
