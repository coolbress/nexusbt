# 34. Integer share arithmetic; stale marks follow event bases

- Status: Accepted
- Date: 2026-10-28
- Spec: §5.6.1, §5.6.10, TDS 5.11

## Context

Float flooring turns a share into fractional cash on exact multiples (LEAN#9882, zipline-reloaded#336); stale prices after an event on a no-trade day inflate NAV and order size (LEAN#9819).

## Decision

Share ratios are exact rationals (`ratio_num/ratio_den`) with `floor_shares`; a stale mark is multiplied by the later price factor. Shorts (negative quantities) follow the same rule. Exact ratios are required; missing or invalid ratios raise E13. No inference from f64; the only exception is a decimal literal the user opts into (recorded, warned).

## Consequences

External data without exact ratios does not open until the user chooses explicitly.
