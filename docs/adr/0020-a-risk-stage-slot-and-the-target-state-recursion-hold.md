# 20. A risk stage slot and the target-state recursion (hold band)

- Status: Accepted
- Date: 2026-10-28
- Spec: §5.5.2, §5.5.3

## Context

Separating stages (LEAN style) keeps strategies composable; a hold band normally reads account holdings, which breaks screen = backtest.

## Decision

Keep a `risk=` slot. Since spec v3.3 it holds a v1 list of built-in rules plus an account layer (details in ADR-0038). The hold band is defined on the previous decision's canonical target set (`TargetState = (S_long, S_short, missing_streak)`), not on account holdings, so it stays a pure function and screen = backtest holds (anchor included). Normative now, implemented as the last v1 ticket (T7.1), off by default. Missing scores follow `on_missing`; band names never bought are not bought at execution (`band_entries`); `bottom(hold=)` mirrors it.

## Consequences

The recursion is replayed on resume and rerun.
