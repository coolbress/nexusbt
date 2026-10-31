# 22. Public repository, Apache-2.0, data outside the repository

- Status: Accepted
- Date: 2026-10-28
- Spec: §2.1, §2.7

## Context

Engine, spec and data standard are meant to be public; real data is not.

## Decision

Apache-2.0 (same as zipline-reloaded, compatible with core dependencies). NautilusTrader (LGPL) is an optional dependency only. Repository hygiene tests block personal paths, data and vendor-derived files; tests use only the synthetic generator.

## Consequences

Every test fixture is synthetic.
