# 36. Shorting and long-short are signed symmetry in the same state machine, off by default

- Status: Accepted
- Date: 2026-10-28
- Spec: §5.5, §5.6.7, §5.6.7a

## Context

The project owner decided (2026-10-28) to replace the earlier long-only v1.

## Decision

Holdings, weights, fill rules, exits, corporate actions and taxes mirror the long side; collateral, borrow cost and short dividends are short-only items. With shorting off, results are bit-identical to the long-only path (INV-22). Borrow availability, uptick rules and (in the cash account) forced liquidation are not modelled and appear as assumption lines; the margin account (spec 5.6.7a, off by default) has its own margin call and liquidation. Accruals at session start on the previous night's exposure; rebate on the marked short value; obligations that must be paid become negative cash; a sleeve with equity ≤ 0 is `ruined` (no new orders, metrics n/a); all three fill phases reduce risk first; the opening leg of a reversal fills after the closing leg; no long margin in the cash account (feasible region, E16).

## Consequences

A differential test plus a value-hash baseline guard the off switch (P-SHORT-OFF).
