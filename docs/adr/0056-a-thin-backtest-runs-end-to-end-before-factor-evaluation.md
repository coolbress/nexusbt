# 56. A thin backtest runs end to end before factor evaluation

- Status: Accepted
- Date: 2026-11-28
- Spec: §3.9 (a line not built yet), §9.4; the plan `docs/plan/plan.md` 10.0 and M1b

## Context

The plan built in this order: M0 normative contracts → M1 snapshot, pipeline slice and first public path → M2 PIT and factor evaluation → M3a single-market market orders end to end → M3b → M4 → M5 → M6 → v1.x. The first run of a backtest from start to end was M3a's, after every ticket of M2. #43's decision of 2026-11-04 kept it there: reordering the milestones would have been a spec change the owner had not asked for.

On 2026-11-28, as #43 records it, 55 of the 222 v1 tickets were closed (the plan's count before the six removed on 2026-11-24, #752), all in M0 and M1, and nothing could run a backtest (#43's Decisions, 2026-11-28; #858).

## Decision

The order of building changes (the owner, 2026-11-28; it overturns #43's decision of 2026-11-04). A new milestone, **M1b**, between M1 and M2, holds a thin backtest that runs end to end: one market in a run, long only, in that market's currency; a monthly or daily schedule, `top(n)` on a factor the M1 pipeline computes, equal weights; a decision at the close and market orders filled at the next session's open, in whole shares, with no fill on a halted or missing bar and no volume cap or price-limit logic; the ledger in integer minor units with the daily balance; cash dividends, share-changing events with an exact ratio and a delisting with an observed terminal value; no cost code; six metrics, the first screen, the saved run and `rerun`, demo data and the zipline comparison. The later milestones add the rest one piece at a time.

The order now: M0 → M1 → **M1b** → M2 → M3a → M3b → M4 → M5 → M6 → v1.x.

No rule of the spec changes, and when a check becomes required does not change. A request outside the thin backtest stops with E18, as a feature not built does. A first-screen line whose source is not built yet prints `n/a (not built yet; available after ticket {ticket})` (spec §3.9).

What was split, as the plan has it (#858, #871). M1b has 24 tickets (23 until 2026-11-28, when #901 split T3.13c into T3.13c and T3.13d). In each split, the half that stays keeps the original id, and the M1b half takes a new letter:

- **Moved whole:** T3.3, T3.4, T3.9, T3.12 and T3.15a from M3a, and T1.20 from M1.
- **Split, the M1b half first:**
  - T2.4a / T2.4 and T2.7a / T2.7 (M2);
  - T3.1a / T3.1, T3.2a / T3.2, T3.5c / T3.5a, T3.5d / T3.5b, T3.10a / T3.10, T3.11a / T3.11, T3.13c and T3.13d / T3.13a, T3.14a / T3.14, T3.16a / T3.16, T3.17c / T3.17a and T3.22a / T3.22 (M3a);
  - T5.18a / T5.18 (M5).
- **Golden cases:** T3.Gg takes the cases the M1b tickets use from T3.Ga, T3.Gc, T3.Gd and T3.Ge, and adds G-119 to G-122 (#875).
- **New:** T3.36 (`rerun` of a backtest run) and T3.37 (`examples/factors/momentum.py` and `examples/strategies/mom_kr.py`).

## Considered options

- **Keep the order of 2026-11-04**, with the first end-to-end run in M3a. It changes nothing in the plan, but no backtest runs until M2's tickets and most of M3a's are done.

## Consequences

A backtest runs on demo data before factor evaluation is built, and each later milestone adds to a run that already works. The factor that M1b's strategy first trades is the one M2 evaluates and M3a trades. Some first-screen lines print as not built until the tickets that own them land. The ticket counts in the plan are from before M1b.
