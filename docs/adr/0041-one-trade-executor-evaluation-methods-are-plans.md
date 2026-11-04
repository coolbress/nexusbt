# 41. One trade executor; evaluation methods are plans that call it; diagnostics read records

- Status: Accepted (2026-11-04, by the owner after reading)
- Date: 2026-11-04
- Spec: §2.4, §3.8, §5.5, §5.6, §5.9, §6.2, §6.3, §6.3a

## Context

A design review (2026-11-04, item D16) asked that five responsibilities be kept apart: the trade executor, the research executor, the evaluation plan, diagnostics, and the common record. The aim is that walk-forward, CPCV and other evaluation methods do not grow their own accounting. Engines commonly validate by cutting and stitching trade logs outside the engine, or compute "strategy P&L" in a statistics module with its own simplified costs. Both give a second answer to "what did this strategy earn".

The spec already holds each piece under other names. What it lacks is one statement of the boundaries, which is hard to reverse once code depends on it.

## Decision

1. **Trade executor.** `execution` with `accounting` (§5.6) is the only code that turns a `TargetFrame` into `orders` and `account_events`, the canonical tables everything else is derived from (INV-16, ADR-0026). Its single input is a chronological sequence of targets, and its single output is one account path. An external backend may report fills but does not post money (ADR-0017).
2. **Evaluation methods are plans, not executors.** `backtest(method="linear")` is one executor pass. Walk-forward, CPCV and holdout build the `TargetFrame` of each fold or path, say where an account starts and what it carries (§6.3a "Accounts"), and call the same executor. CSCV and PBO run no trades: they read the stored return matrix of candidates (§6.3).
3. **Research executor, as it stands in v1.** It is the `nx.ml.factor` fit and predict, inside the engine-enforced training window (§5.3.11), and the grid selection inside a fold (§6.3a "What is selected"). A strategy with neither has nothing to fit and needs no plan beyond `method`.
4. **Diagnostics read records and never post money.** PSR, DSR, PBO, MinTRL, offsets and probes read stored series and give E21 with a reason when an input is missing (§6.3). Folds, paths and offsets are diagnostics, not attempts (§6.2).
5. **Two kinds of "what if", with different names.** A scenario replays the same targets through the executor with changed costs or valuation (§3.8 `scenarios`, linear run only). A candidate reruns the whole policy (sweep, grid, `compare`), and its targets may differ. A diagnostic that needs P&L under other costs uses a scenario, never its own arithmetic.
6. **Common record.** The run folder, the index and the study's candidates and cohorts (§5.9, §6.2) are the one place that links a run to its candidates, fits (`fits.parquet`), splits (`split_hash`), selections and outputs.
7. **What the engine checks against what is declared.** Structural guarantees are checked by the engine. A user function, a pretrained model's `training_cutoff` or an external input's `known_on` is a declared assumption, shown as such (the structural-guarantee and diagnostic split of §9.2), and is never shown as audited.

## Considered options

- A separate `validate()` entry point with its own fold accounting: rejected by ADR-0039 (one entry point).
- Statistics modules that recompute P&L from returns and a cost model: rejected, because they would give a second P&L next to the canonical events.

## Consequences

New evaluation methods are added as plans over the same executor. A method that needs a new account rule changes §6.3a and this ADR, not the executor.

The choices this ADR left open were decided on 2026-11-04 in research issue #207:
- the research executor gets no new component in v1;
- user splitter, selector, diagnostic and optimizer protocols, and an external-strategy entry point, are v1.x (spec 12.1 `DR16-1`, `DR16-2`);
- a cost or delisting scenario re-runs the account layer and execution under its own costs, and capacity runs execution only (spec 5.7);
- `study` stays, and "family" names only #196's research family.
