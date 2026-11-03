# 34. Integer share arithmetic; stale marks follow event bases

- Status: Accepted
- Date: 2026-10-28
- Amended: 2026-10-29 (user decision R7-01, spec §3.11 `[corporate_actions] decimal_ratio`); recorded here 2026-11-03
- Spec: §5.6.1, §5.6.10, §3.11, TDS 5.11

## Context

Float flooring turns a share into fractional cash on exact multiples (LEAN#9882, zipline-reloaded#336); stale prices after an event on a no-trade day inflate NAV and order size (LEAN#9819).

## Decision

Share ratios are exact rationals (`ratio_num/ratio_den`) with `floor_shares`; a stale mark is multiplied by the later price factor. Shorts (negative quantities) follow the same rule. No inference from f64. A ratio that is 0 or negative, or has only one of the two columns, raises E13 at open.

A share-changing event without an exact ratio (or one the producer marks unverified) follows `[corporate_actions] decimal_ratio` (amended 2026-10-29, R7-01):

- `exclude_instrument` (default): only the instruments with such an event are excluded, from the time the event becomes visible on (spec §5.6.1 "events without an exact ratio"); the run opens and reports them (E30, `skips`, manifest).
- `require_exact`: E13 when even one such event is in the run's scope.
- `literal`: the user opts into reading the f64 decimal notation as an exact decimal fraction (E30 `ratio_decimal_literal`, a count on the report header line, manifest `policies.corporate_actions`).

Superseded 2026-10-29 (original wording): "Exact ratios are required; missing or invalid ratios raise E13. No inference from f64; the only exception is a decimal literal the user opts into (recorded, warned)."

## Consequences

External data without exact ratios opens by default; the instruments whose events lack an exact ratio drop out of the universe from the time the event becomes visible (never earlier), and the report says how many. A user who wants the run to stop instead chooses `require_exact`.

Superseded 2026-10-29 (original wording): "External data without exact ratios does not open until the user chooses explicitly."
