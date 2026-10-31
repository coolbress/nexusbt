# 7. Account P&L from raw prices and explicit events

- Status: Accepted
- Date: 2026-10-28
- Spec: §5.6.9–5.6.13

## Context

Mixing adjusted-price P&L with dividends double-counts or hides cash flows.

## Decision

Entitlement (ex-date), receivable (amount published), cash (pay date) and valuation are separate. Dividends and delisting proceeds with unknown amounts are excluded from decision value and included in reported value at the realised amount (INV-01 for sizing inputs). Terminal value is applied once as reference price × (1 + policy). An unsupported event on a holding stops the run.

## Consequences

More event types in the ledger; every number traces to an event.
