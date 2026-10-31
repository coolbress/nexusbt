# 27. One corporate-action resolver

- Status: Accepted
- Date: 2026-10-28
- Spec: §5.3.3a, TDS 5.11

## Context

If adjustment, accounting, labels and checks each resolve amendments, cancellations and late terms, they disagree.

## Decision

One pure function takes a reference time and returns, per chain, one version and four effects (price factor, share factor, entitlement, settlement). Amounts already booked are corrected by correcting entries. Quantities use an explicit `share_factor`.

## Consequences

The resolver runs per reference time (chains are few, so the cost is small [estimate]).
