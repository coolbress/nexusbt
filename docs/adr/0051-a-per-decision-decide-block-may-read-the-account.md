# 51. A per-decision `decide` block may read the account

- Status: Accepted
- Date: 2026-11-25
- Amends: [ADR 0041](0041-one-trade-executor-evaluation-methods-are-plans.md)
- Spec: §1.3 INV-08, INV-23, §3.7, §5.5.2a, §5.6.3, §6.3a, §6.6 E41

## Context

Until now a strategy's target was a function of the information at the decision and the previous canonical target only; a callback that read holdings (`on_rebalance`) was left out of v1, and so were "imperative per-bar handlers" (the user decision of 2026-11-03). ADR 0041 rests on that: a scenario replays the same targets through the one executor. Some strategies a user brings cannot be written without reading the account at the decision: rules that depend on what is held, what it cost, or orders still pending. The owner decided to admit them as one more slot (#725 Decisions 236 to 241), named `decide`, `fn(ctx) -> Decision` with arrays in and out (#752's Decisions).

## Decision

A tenth slot, `decide`, holds an optional user block called once per decision session, in the decision step after the canonical target (#752's Decisions, 2026-11-25). It reads the account up to the decision (read-only; unpublished dividend amounts unseen), its own state and the Pipeline columns it declares; never the fill session's volume (#725 Decisions 235, 237). It returns target weights or order intents, cancel and replace of its own orders included, with quantity and holding limits and a record per decision; it cannot change fill, cost or settlement rules (238).

What it returns passes the risk slot's rules again, the account layer, the exposure caps, the final check and shorting, each of which only shrinks it (239). For those checks an order intent is read as the weight it would leave, every intent and every pending order left standing taken as filled in full at the decision's valuation price.

Its state is an engine-given table keyed by `instrument_id`, kept in the run record, equal on a continued run, and started and carried with the account as `risk_state` is (240; #752's Decisions, 2026-11-25). Its source is hashed as `@nx.factor`'s is.

ADR 0041 is amended in one place: for a strategy with a `decide` block, a scenario calls the block again over the scenario's account, so the scenario's targets after the block may differ from the base run's (241). The executor stays one; folds and paths start the block's state where their accounts start (spec 6.3a).

INV-08 (screen = backtest) is promised up to the Pipeline values for such a strategy (241). INV-23 reads the block's output in place of the canonical target.

## Considered options

- **Keep the account out of every user block** (the rule before). Keeps screen = backtest whole, but leaves out strategies users need.
- **The block after the account layer, just before orders.** Freer, but it could undo the drawdown brake or a re-entry ban, which would then have to be checked again; the owner chose the place before the risk rules.
- **Fresh block state at every fold or path start.** Simpler, but in walk-forward the holdings carry while the block's memory would not, as if two strategies shared one account.

## Consequences

A strategy without `decide` keeps every guarantee as it was. A strategy with it trades screen = backtest after the Pipeline values for the account-reading rules it needs, and its scenarios cost one block call per decision more. The fill rules and the one executor of ADR 0041 do not change.
