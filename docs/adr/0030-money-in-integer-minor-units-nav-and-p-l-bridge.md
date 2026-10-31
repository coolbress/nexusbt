# 30. Money in integer minor units; NAV and P&L bridge

- Status: Accepted
- Date: 2026-10-28
- Spec: §5.6, §5.9

## Context

Float rounding is not exact minor-unit accounting, and "sum of cash flows = NAV change" misses unrealised P&L.

## Decision

Round once to an integer per entry; close a daily bridge. Gross − net = direct costs + path effects.

## Consequences

Every currency needs a minor unit.
