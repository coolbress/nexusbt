# 18. The input contract is the public TDS v1; the checker is a separately versioned package

- Status: Accepted
- Date: 2026-10-28
- Spec: §4, TDS

## Context

Engine and data preparation must be decoupled, and anyone's data must be read under the same rules.

## Decision

Format, check codes and profiles are defined by the TDS document and `tds/schemas`. The checker `nexusbt-tds` (import `nexusbt_tds`, pyarrow only) is shared by the engine and every producer. The engine spec keeps only engine-side reading rules. A profile is a conformance claim; what the engine needs is the capability of the graph. Status draft → RC → 1.0; tick and derivative schemas are experimental.

## Consequences

Standard versioning (MAJOR/MINOR) work.
