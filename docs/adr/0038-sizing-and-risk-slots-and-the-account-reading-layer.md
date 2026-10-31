# 38. Sizing and risk slots and the account-reading layer

- Status: Accepted
- Date: 2026-10-28
- Spec: §5.5.1a, §5.5.2, §5.5.2a

## Context

Sizing from the account (backtrader, Qlib style) makes screen ≠ backtest.

## Decision

Sizing is a pure-function slot and does not read the account. Risk is a list slot that only scales weights toward zero; rules that read the account run only in a separate final-target layer after the canonical target (INV-08 unchanged, INV-23 new). State lives only in engine tables (`risk_state`); iterative solvers use fixed order, fixed iterations, a defined fallback and reported counts; the drawdown brake re-enters by a shadow index. The high-dimensional performance gate (P11) is recorded here after prototype measurement.

## Consequences

Two target columns (`target_weight`, `final_weight`) in every output.
