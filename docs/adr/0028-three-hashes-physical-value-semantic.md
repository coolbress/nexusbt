# 28. Three hashes: physical, value, semantic

- Status: Accepted
- Date: 2026-10-28
- Spec: §5.9.4, TDS 4.5

## Context

Arrow IPC bytes differ by implementation and version, so bytes cannot define "same data" in a public standard.

## Decision

A language-neutral canonical value serialisation (with published test vectors) defines the value hash; value hash + resolved metadata is the semantic hash, which the engine uses.

## Consequences

The checker carries one serialisation function.
