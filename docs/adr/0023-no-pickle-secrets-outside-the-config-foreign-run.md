# 23. No pickle, secrets outside the config, foreign run folders only when trusted

- Status: Accepted
- Date: 2026-10-28
- Spec: §2.6

## Context

Pickle executes code on load; config files get shared.

## Decision

Artifacts, caches and checkpoints are Parquet, Arrow IPC or JSON only. `nexusbt.toml` may not contain key/secret/token/password keys. `rerun` executes source, so run folders from another machine need `--trust`.

## Consequences

Model objects are not saved (ML records predictions and fits instead).
