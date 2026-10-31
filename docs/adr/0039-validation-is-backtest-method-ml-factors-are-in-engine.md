# 39. Validation is `backtest(method=…)`; ML factors are in-engine training nodes

- Status: Accepted
- Date: 2026-10-28
- Spec: §6.3a, §5.3.11, §5.8

## Context

Validation in most engines means cutting and stitching trade logs outside the engine; ML factors are trained outside and re-imported.

## Decision

One entry point (no separate `validate`): linear result and distribution side by side. Splits use decision and label availability times; purge and embargo are separate meanings. Accounts: walk-forward chains one account, CPCV gives each path fresh capital, simple segments get fresh capital each. Folds and paths are diagnostics and do not count as attempts. ML factors use a fit/predict contract only; the engine enforces the training window (always forward-only); no pickle — prediction and fit tables plus a refit hash check on rerun; single-threaded by default. Triple-barrier labels reuse the exit fill rule.

## Consequences

Validation cost is dominated by ML fits (reported separately, capped by `[validate] max_fits`).
