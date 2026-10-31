# 24. Defined fallbacks when data is incomplete

- Status: Accepted
- Date: 2026-10-28
- Spec: §4.5

## Context

A valid package may not fill every column or dataset; the engine should still be useful without hiding gaps.

## Decision

A fallback table (F-01…F-16) defines each behaviour; every fallback warns (E30) and is recorded in the manifest. The engine does not repair packages that break their own declarations. If the result would be undefined, fail. `[data] fallbacks = "fail"` turns fallbacks off. Messages are producer-neutral.

## Consequences

Results carry assumption lines that users must read.
