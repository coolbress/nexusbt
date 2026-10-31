# 29. Market names come from the data; market rules come from packs

- Status: Accepted
- Date: 2026-10-28
- Spec: §4.7

## Context

Hard-coding `KR` and `US` breaks the public API for the first user of another market.

## Decision

Market names come from `tds.json`; per-market rules live in `resources/markets/<M>.toml`. Supported markets are those with a pack (v1: KR, US); others raise E18 unless `allow_untested` (recorded).

## Consequences

Adding a market is adding a pack and its tests.
