# 51. A per-decision `decide` block may read the account

- Status: Accepted
- Date: 2026-11-25
- Amends: [ADR 0041](0041-one-trade-executor-evaluation-methods-are-plans.md), [ADR 0038](0038-sizing-and-risk-slots-and-the-account-reading-layer.md)
- Spec: §1.3 INV-08, INV-23, §3.7, §5.5.2, §5.5.2a, §5.5.3, §5.6.3, §5.7, §6.3a, §6.6 E16, E41, E42

## Context

Until now a strategy's target was a function of the information at the decision and the previous canonical target only; a callback that read holdings (`on_rebalance`) was left out of v1, and so were "imperative per-bar handlers" (the user decision of 2026-11-03). ADR 0041 rests on that: a scenario replays the same targets through the one executor. Some strategies a user brings cannot be written without reading the account at the decision: rules that depend on what is held, what it cost, or orders still pending. The owner decided to admit them as one more slot (#725 Decisions 236 to 241), named `decide`, `fn(ctx) -> Decision` with arrays in and out (#752's Decisions).

## Decision

A tenth slot, `decide`, holds an optional user block called once per decision session, in the decision step after the canonical target (#752's Decisions, 2026-11-25). It reads the account up to the decision (read-only; unpublished dividend amounts unseen), its own state and the Pipeline columns it declares; never the fill session's volume (#725 Decisions 235, 237). It returns target weights or order intents, cancel and replace of its own orders included, with quantity and holding limits and a record per decision; it cannot change fill, cost or settlement rules (238).

What it returns takes the place of the sizing slot's output and passes the risk slot's market rules and the exposure-cap fitting once, giving the decided target `decided_weight`; then the account layer, the final check and shorting (239). Each only shrinks it; a short while shorting is off is E16. A block that returns the sizing output unchanged gives the canonical target, bit for bit. For those checks an order intent is read as the weight it would leave, every intent and every order the block left standing taken as filled in full at the decision's valuation price, exit orders not counted. The block's orders are not cancelled at the next decision as rebalance orders are. Stop-losses fill in the session's phases before the decision, so the block reads their result; re-entry bans and the drawdown brake, as account rules, come after it.

Its state is an engine-given table keyed by `instrument_id`, a third part of the strategy state record, kept in the run record, equal on a continued run, and started and carried with the account as `risk_state` is (240; #752's Decisions, 2026-11-25). Its source is hashed as `@nx.factor`'s is.

ADR 0041 is amended in one place: for a strategy with a `decide` block, a scenario that runs the account layer again calls the block again over the scenario's account, so its targets from `decided_weight` on may differ from the base run's; `ca_exit_hi` and `capacity`, which reuse the base run's results, do not (241). The executor stays one; folds and paths start the block's state where their accounts start (spec 6.3a). `screen` without an account does not call the block (E42).

ADR 0038 is amended in one place: the account is read in the account layer and, read-only, in `decide`; the sizing slot still never reads it.

INV-08 (screen = backtest) is promised up to the Pipeline values for such a strategy (241). INV-23 reads `decided_weight` in place of the canonical target.

## Considered options

- **Keep the account out of every user block** (the rule before). Keeps screen = backtest whole, but leaves out strategies users need.
- **The block after the account layer, just before orders.** Freer, but it could undo the drawdown brake or a re-entry ban, which would then have to be checked again; the owner chose the place before the risk rules.
- **Fresh block state at every fold or path start.** Simpler, but in walk-forward the holdings carry while the block's memory would not, as if two strategies shared one account.

## Consequences

A strategy without `decide` keeps every guarantee as it was. Running the risk list once on the block's output, rather than again on the canonical target, keeps a block that changes nothing from changing results. A strategy with it trades screen = backtest after the Pipeline values for the account-reading rules it needs, and its scenarios cost one block call per decision more. The fill rules and the one executor of ADR 0041 do not change.
