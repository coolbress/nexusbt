# NexusBT v1 implementation spec — revision v3.4 (2026-10-28, with the fourth three-reviewer round)

> **Translation in progress.** This English text is made chapter by chapter from the Korean spec at `docs/spec/engine-spec-v3.4.md`, which stays canonical until every chapter is translated. A chapter not yet here is only in the Korean text.

> **Public edition.** This file is the repository's public edition of the revision v3.4 spec (private notes, the producer's work plan and personal paths removed). Normative sentences, section numbers, tickets, golden cases and error codes are the same as in the original. Among the bracketed sources, file names such as `review/`, `teardown/`, `sources/`, `research/` and `STORY.md` point to the design record (outside the repository) and are not needed for implementation.

> **Name (defined in this line only).** Engine name = **NexusBT** ("nexus" = the one point where data, backtest, screen and live, and the strengths of other engines meet). Name decision 2026-10-28: Aion → NexusBT (PyPI refused to register `aion`, and the name collides with two active packages that use `import aion`; PyPI `nexusbt` was registered by the user as a 0.0.1 placeholder). Repository = `<owner>/nexusbt`, distribution name = `nexusbt`, import = `import nexusbt as nx` (`nx.` in this document is this abbreviation), config file = `nexusbt.toml`, CLI = `nexusbt`, environment variables = `NEXUSBT_*`, base error class = `NexusBTError`, optional dependencies = `nexusbt[pandas]` and so on. The names of the data standard TDS (`tds.json`, distribution name `nexusbt-tds`, **import name `nexusbt_tds`**, CLI `tds`) belong to the standard and can change separately from the engine name (TDS chapter 13 Q6). In this document, `tds` as in `tds.check(...)` and `tds.value_hash(...)` abbreviates `import nexusbt_tds as tds` [RV-Q04].
>
> **Identifier name (defined in this line only).** The instrument key is named **`instrument_id`** (in data, internals, output tables, the public API and documents alike; no alias). v2's `security_id` alias was removed by the three-reviewer consensus [RV-Q01]: other column names in external data are changed only in `nx.dataset.from_parquet(..., rename={...})` and in the `mapping.yaml` of `tds import csv`. In code, only the constant `nx.contracts.ID_COLUMN = "instrument_id"` defines this name.
>
> **Status.** Normative spec **v3.4** = v3.3 + all P0 and P1 and the cheap P2 of the **fourth three-reviewer round** (`review/r4-opus.md`, `r4-fable.md`, `r4-sol.md`), and the **user decisions 2026-10-28 (three after round 4 + economic-event investing)** (numbered `[R4F-NN]`, `[R4F-EV-NN]`; summary in appendix I). The rescoring bundle is `review/packet-r4b.md`. The v3.3 description below still holds. Normative spec **v3.3** = v3.2 + the **round 4 topics** (`review/round4-topics.md` sections 0 to 5: the sizing and risk slots, an easy-to-learn block structure, error layers, high-dimensional performance, the validation lab and ML factors) and the **user decisions 2026-10-28 (three before round 4 + one validation entry point)**; it is the draft that reflects them (numbered `[R4-NN]`, appendices H and B.7). Sources: the teardowns `teardown/F-money-risk.md` (C18) and `teardown/G-ux-ml4t.md` (C19), the research `research/validation-and-ml-2026-10-28.md`. Round 4 reviewers read `review/packet-r4.md` and the rubric `review/rubric-r4.md`. The v3.2 description below still holds. Normative spec **v3.2** = v3.1 + all 10 P0 and 16 P1 and two cheap P2 of the **third three-reviewer round consensus** (`review/consensus-r3.md`; Opus 5.5 · Fable 5.1 · GPT-6.1 Sol xhigh, first pass + cross review) (numbered `[R3-NN]`, appendix G) + **four user decisions 2026-10-28** (below). v3.1 = v3 + all P0 and the accepted P1 of the **teardown of existing engines** (`teardown/MATRIX.md`; LEAN, Nautilus, vectorbt, Qlib, bt, QSTrader, backtrader, Backtesting.py, PyBroker, pysystemtrade, screener-style services, 5,005 bug reports) (numbered `[V31-NN]`, appendix F) + the **core of shorting and long–short symmetry** (user decision 2026-10-28, numbered `[V31-LS-NN]`, appendix F). v3 = v2 (v1 + blueprint SC-01~SC-27 + TDS D1~D24) + **all P0 and P1 and the cheap P2 of the three-reviewer consensus (Opus 5.5 · Fable 5.1 · GPT-6.1 Sol xhigh, two rounds)** (`review/consensus.md`, consensus numbers `[RV-…]`). No code. **This document is the only basis for implementation**; v3.3 (`sources/engine-spec-v3.3-2026-10-28.md`), v3.2, v3.1, v3, v2 and v1 remain only for comparison. The input format the engine reads is set by **TDS v1.4** (`engine-data-standard-v1.4.md`; the section numbers "TDS v1.1 x.y" and "TDS v1.2 x.y" in this document are the same in v1.4 — v1.2 added columns, checks and datasets; v1.3 corrected interpretive sentences (choosing the corporate-action version, the terminal-value basis, price-comparison coordinates, file identity and cloning) and fixed the K1 example (TDS chapter 17); v1.4 added the required exact ratio (A010 error), unknown inclusion of delisting distributions, event `series_id`, `consensus` and macro `frequency` (TDS chapter 18)) [R6-01], and chapter 4 of this document holds only the engine-side reading rules. Public scope: the engine, this spec and TDS are written on the premise that they are public (Apache-2.0). This file is the repository's public edition: the private comment lines about the private producer, the body of section 10.2 and TDS chapter 11 are removed, and the producer's name is replaced by "the reference producer" (the `grep` acceptance test of T0.1). An implementing agent does not invent rules that are not in this document or in TDS. When there is no answer, it uses the recommended defaults of chapter 12; when there are none, it stops and asks.
>
> **Inputs.** `sources/engine-spec-v3.1-2026-10-28.md` (the basis of v3.2), `review/consensus-r3.md` and `review/r3-*.md`, `review/r3b-*.md` (the third review round, `R3-` numbers), `STORY.md` (the design story, chapter 0), `sources/engine-spec-v3-2026-10-28.md` (the basis of v3.1), `teardown/MATRIX.md` (the combined teardown, `V31-` numbers) and `teardown/A~E`, `sources/engine-spec-v2-2026-10-27.md` (the basis of v3), `review/consensus.md` (the three-reviewer consensus, `RV-` numbers), `engine-blueprint-by-aspect.md` (below, "the blueprint"; chapter 13 SC, chapter 14 OQ), `engine-data-standard-v1.4.md` (below, "TDS"; chapter 12 D, chapter 13 Q, chapter 11 G and X are a private appendix, chapter 16 v1.1 → v1.2, chapter 17 v1.2 → v1.3, chapter 18 v1.3 → v1.4) [R6-01], `engine-design-2026-10-27.md` (below, "the design"; 9.0 user decisions), `README.md`.
>
> **Priority.** When rules differ, the order is **user decisions (design 9.0 and later decisions) > this spec v3.4 = TDS v1.4 (for the input format, TDS wins over chapter 4 of this spec) > the three-reviewer consensus > the blueprint > the body of the design > sources**. How each conflict was settled is in appendix A (from A-104 for v3).
>
> **Tracing notation.** The bracket at the end of a normative sentence is its source.
> - `[R-xx]`, `[P1]`~`[P10]`: requirements and performance promises of design chapter 8. Numbers from `R-56` on were added by this spec (1.4).
> - `[9.0 …]`: the second round of user decisions. Ones like `[Q6]` are the first-round decisions of design 9.1.
> - `[C1]`~`[C10]`, `[11.4.2]`: the Codex review (design chapter 11). `[D1]`~`[D8]` (bracket + D + one digit): E0 decisions.
> - `[SC-xx]`: spec changes of blueprint chapter 13. `[OQ-x]`: open questions of blueprint chapter 14. `[TDS x.y]`: a TDS section. `[TDS-Dxx]`: a difference in TDS chapter 12 (in this document always with the `TDS-` prefix, so it is not confused with the D of E0). `[TDS-Qx]`: a question of TDS chapter 13.
> - `[A-xx]`: conflict-resolution numbers of appendix A. `[INV-xx]`: invariants of 1.3.
> - `[RV-C01]`, `[RV-I05]`, `[RV-Q02]`, `[RV-D1]`: item and issue numbers of the three-reviewer consensus (`review/consensus.md`). Attached to normative sentences changed in v3.
> - `[V31-NN]`: the de-duplicated gap numbers of the teardown of existing engines (`teardown/MATRIX.md` chapter 2). `[V31-LS-NN]`: shorting and long–short symmetry (user decision 2026-10-28). `[V31-PUB-NN]`: a producer-specific TDS package, linked by path only (user decision 2026-10-28). Attached to normative sentences changed in v3.1.
> - `[R3-NN]`: numbers of the third three-reviewer round consensus (`review/consensus-r3.md` chapters 2 and 4). Attached to normative sentences changed in v3.2.
> - `[R4-NN]`: change numbers of the round 4 topics (`review/round4-topics.md`) and their user decisions. Attached to normative sentences changed in v3.3 (list in appendix B.7, summary in appendix H).
> - `[R4F-NN]`: change numbers of the fourth three-reviewer round (`review/r4-*.md`) and the user decisions after it; `[R4F-EV-NN]`: the user decision on economic-event investing. Attached to normative sentences changed in v3.4 (list and summary in appendix I).
> - Normative sentences say "does / does not". Explanatory sentences give a source or a reason.
>
> **Notation.** [est.] estimated, [unverified] the original could not be checked. Numeric examples show a shape and are not normative (the normative numbers are only those written as "default" in a table). **v1.x** = the small releases right after the v1 release (M6). **Reserved** = only the name and place are taken; calling it in v1 raises `CapabilityError` (E18). **Private comment** = a note about the private producer (removed in this file, the public edition).

---

> **User decision 2026-10-28:** the spec in Korean (private); public material (TDS, README, quick start, error messages, CONTEXT.md) English canonical + Korean translation; v1 release = develop on synthetic data → pass verification on KR/US real data after the reference producer is complete; PyPI only reserves the name, publishing at v1; the zipline comparison covers the preset scope (OI-20); the hold band is the last ticket of v1 M6 (OI-12); the `security_id` alias removed; the stand-alone three-reviewer review of TDS takes place right before 1.0 is settled. Engine name = NexusBT (settled 2026-10-28; changed from Aion the same day).

> **User decision 2026-10-31 (changes "the spec in Korean (private)" of the 2026-10-28 decision above; amends OI-45):** the spec, like every other public document, is English canonical + Korean translation. "Korean" assumed that the spec was private, but the spec became public by the 2026-10-27 decision, and everything a person reads on the remote repository is written in English, with the translation kept separately. While it is translated, the Korean edition is canonical. The English edition grows chapter by chapter in `docs/spec/engine-spec-v3.4.en.md`, and in the last PR the English edition moves to `docs/spec/engine-spec-v3.4.md` and the Korean edition to `docs/spec/engine-spec-v3.4.ko.md` in one step. Section numbers, ticket ids, error codes, golden numbers, property test ids and citation numbers do not change, and a translation PR changes no rule (a wrong rule is a separate spec PR).

> **User decision 2026-10-28 (v3.1, changes "v1 long only" of design 9.0 and 9.1 Q2) [V31-LS-01]:** the core is symmetric between long and short like a mirror image, through signed quantities and weights (+ long, − short) (zipline-style signed holdings, which futures and options later use as they are). Shorting is **in v1 but off by default** (with `[shorting] enabled = false` the results are bit-identical to the long-only path, test P-SHORT-OFF). Borrow cost, collateral ratio and interest on short proceeds are written in the config by the user, like commissions and taxes. There is no data on borrow availability (everything is assumed borrowable unless the market rules pack forbids it, and the documentation says so). The Korean short-sale ban periods are date rules of the market rules pack. The other user decisions stand.

> **User decision 2026-10-28 (v3.1) [V31-PUB-01~03]:** the producer keeps no separate export or conversion layer. The `tds` schema tables of the producer's DB are identical to the TDS datasets; when a build is swapped in, the snapshot folder is written as a TDS package (the 4.1 layout + a `tds.json` with hashes), and the TDS checker is the mandatory check (on failure the build is not swapped in). Year partitions that did not change are hard-linked from the previous snapshot. The engine links by path only (`nx.open(<snapshot path>)` or the path in the config).

> **User decision 2026-10-28 (v3.2, closing the user questions of the third review round) [R3-25, R3-09, R3-16, R3-26]:** (1) **Cash interest**: v1 has `[account] cash_rate_bps` (default 0 = as now), booked on the same accrual as borrow cost (at session start, the previous session's closing balance × calendar days/`day_count`) (5.6.3(1)). (2) **Short ruin**: when the equity (`decision_value`) of a sleeve with shorts falls to 0 or below, that sleeve is marked `ruined` and its new orders stop, and the mandatory obligations (borrow cost, short dividends, terminal obligations, taxes and the like) are recorded only as negative cash; it shows in the output (the header line, `status.json`, E38) (5.6.7). Forced liquidation is still not simulated (cash account; the margin account of the final v3.4 is 5.6.7a [R6-07]). (3) **Snapshot partition reuse**: APFS cloning (`clonefile`) and reflink are used before hard links, stamps and caches check the file identity `(dev, inode, size, mtime_ns)`, and published files are read-only (4.2, TDS 4.1, ADR-0037). The meaning of the decision above (no export layer, linked by path only) stands. (4) **Language**: v1 is Python + numpy/Numba (ADR-0016 stands) with "a seam where Rust can be swapped in" — the hot kernels (window kernels, the session-simulator loop, accounting state) sit behind a narrow interface of Arrow array input and output and columnar state (2.4), and are replaced by a Rust crate (PyO3/maturin) only when M1 and P1~P7 measurements and profiles show that Numba cannot meet the budget, together with a bit-identity test against the Python reference; E4 intraday and tick designs a Rust core and then compares it with a Nautilus bridge (ADR-0016, 11.2).
>
> **Defaults the user set (reviewer consensus, 2026-10-28)** [R3-05, R3-06, R3-07, R3-08, R3-09, R3-11, R3-12, R3-17, R3-27]: pin default `index+root`; no margin loan for longs (feasible region `long_weight + c·short_weight ≤ 1`, a 130/30 book is E16 before the run — from the final v3.4 revision **in the cash account (default) only**; with `[account] type = "margin"`, 5.6.7a [R4G-MG-02]); tie key = the fixed salt `sha256("nexusbt-tiebreak-v1" ‖ instrument_id)` (independent of date and strategy); P-SHORT-OFF = a same-build differential test + value-hash baselines of the four core tables; f64 ratio fitting = ~~the simplest rational within tolerance~~ → removed in v3.4 by user decision (below, 5.6.1) [R4F-01]; borrow cost = at session start, the previous session's closing quantity × calendar days/`day_count` (seed 365 in both markets, unverified); terminal-value basis = three: observed-inclusive, observed-exclusive, policy (5.6.13, consistent with G-55); KR rounding default = the majority option `down` (unverified).

> **User decision 2026-10-28 (after the fourth review round, v3.4) [R4F-01, R4F-02, R4F-03]:** (1) **Split and stock-dividend ratios must be exact integer ratios**: every corporate action that changes the share count must carry TDS `ratio_num/ratio_den` (TDS v1.4 5.11, check A010 = error). The engine does not infer fractions from f64 (the R3-06 inference rule of v3.2 and its thresholds are removed). For external data without an exact ratio, only when the user chooses `[corporate_actions] decimal_ratio = "literal"` is the shortest decimal representation of the f64 used as an exact decimal fraction, with a warning and a count in the report (5.6.1). The canonical producer already writes both columns in `tds.corporate_actions`. (2) **`size.kelly` is v1.x**: it is sensitive to the in-window estimate of μ and is left out of v1 (12.1). (3) **ML training inside a validation method is always forward-only**: every validation method (walk-forward, CPCV, segments) uses only the samples before the refit time τ (label availability time + embargo ≤ τ) — the same shape as live operation (5.3.11, 6.3a).
>
> **User decision 2026-10-28 (v3.4, economic-event investing) [R4F-EV-01~05]:** people who invest on economic indicators and corporate events use the same blocks: `Macro.series` (versioned macro series), `Events.<kind>` (event terms), the event schedule `nx.on_event`, `from_parquet(shape=)`; the invariants (time = availability time, determinism, screen = backtest) stand (3.2, 3.7, 5.3.12).
>
> **User decision 2026-10-28 (before round 4, v3.3) [R4-19, R4-20, R4-23]:** (1) **CPCV in v1**: walk-forward, purged k-fold, CPCV paths, CSCV (PBO), DSR/PSR/MinTRL and automatic attempt records run inside the v1 engine, with real fills and accounting for each path. (2) **Minimum scope of the ML factor block in v1**: `nx.ml.factor(model, features, label, train=rolling|expanding, refit, embargo)`, the training window enforced by the engine (label availability time + embargo ≤ refit time), the fit/predict interface only (sklearn an optional dependency), predictions and fits recorded, model objects not saved (no pickle). MDA feature importance is v1.x. (3) **Validation accounts**: walk-forward = one account carried through, CPCV = fresh capital for each path and carried through within a path, simple segments = fresh capital for each segment. (4) **One entry point** (added the same day): validation is not a new function but a `method=` value of the familiar `nx.backtest(strategy, start=, end=, method="linear")`. The default `"linear"` is the current single linear run as it is; with `method="walk_forward" | "cpcv" | "cscv"` (or an options object such as `method=nx.splits.cpcv(n_groups=6, k_test=2, embargo=5)`), the engine runs trading for each fold and path and combines them into the same `Run` and the same report (path distribution, PBO, DSR/PSR, attempt record). The first screen shows the linear result and the method's distribution side by side. The CLI too: `nexusbt backtest my.py --method cpcv`. To keep the public surface small, a separate `nx.validate` is **not provided** (6.3a).

## Contents

0. The design story
1. v1 scope, terms, invariants
2. Repository layout, dependency rules, security rules
3. Public API
4. Input data: TDS v1.4 references and the engine-side reading rules (capability contract, fallbacks, market rules packs, the synthetic generator)
5. Normative semantics (time, Pipeline computation, the corporate-action resolver, numeric determinism, target construction, the daily state machine, accounting, metrics, labels, run records, ledger transactions, reconciliation)
6. Research hygiene and the list of teaching errors
7. Performance budgets
8. Tests (zipline comparison, hand-calculated golden cases, property and metamorphic tests, TDS conformance)
9. The order of building with plinth (including the TDS conformance checker package)
10. Milestones and tickets (in a form ready to paste as GitHub issues)
11. Extension points (E4 and E5, design only)
12. What remains open (blueprint OQ + TDS Q combined, recommended defaults, marked where a user decision is needed)
- Appendix A. Conflict resolution record
- Appendix B. Requirement map (R/P, SC, TDS-D → section, ticket, status)
- Appendix C. `SimConfig` knob table
- Appendix D. v1 → v2 change summary
- Appendix E. v2 → v3 change summary (with the three-reviewer review)
- Appendix F. v3 → v3.1 change summary (teardown of existing engines + shorting and long–short symmetry)
- Appendix G. v3.1 → v3.2 change summary (third three-reviewer round + user decisions)
- Appendix H. v3.2 → v3.3 change summary (round 4 topics + user decisions)
- Appendix I. v3.3 → v3.4 change summary (fourth three-reviewer round + user decisions)

---

## 0. The design story (user 2026-10-28; original `STORY.md`)

**Trade with event accuracy, compute with vector speed. The user only snaps in blocks.**
(English for public documents: *Event-driven where it matters, vectorized where it scales. You just snap the blocks together.*)

**Why build it.** Whatever the engine, quant researchers hit similar walls (our own Korean and US factor research on zipline-reloaded + a 2026-10 source teardown of some 30 existing engines and 5,005 bug reports). (1) **Fitting the data to the engine leaves no time for research** (bundles, dump_bin, each engine's own folder format; point-in-time financials and delistings left to the user's loader). (2) **Fast means inaccurate and accurate means slow** (US, 3,175 names: vbt PRO 0.87 s, zipline 111 s, backtrader 506 s; high-dimensional factor strategies are hard to test). (3) **My own strategy is hard to assemble** (callbacks and engine internals; sizing and risk-management techniques are hard to swap in). (4) **When it is wrong, I cannot tell where** (errors that do not separate data, code and config; silent failures; future information suspected only when results look too good). (5) **ML-built factors are hard to test** (training outside the engine → predictions back in as data; training-time correctness is hard to check). (6) **One backtest cannot catch overfitting** (walk-forward, CPCV, PBO and DSR are manual work outside the engine). Closed screener services are easy, but I cannot put in my own data or code, and I cannot check their rules.

| Engine | Strong at | Which of the six above it hits |
|---|---|---|
| zipline-reloaded | Pipeline panel computation | 1·2·3·4·5·6, maintenance-only development |
| backtrader | an intuitive event engine, many order types | 2 (very slow)·4·6, development stopped |
| vectorbt (PRO) | overwhelming speed, mass parameter search, segment-splitting tools | 2 (real-world rules left to the user)·5, commercial limits, paid |
| QuantConnect LEAN | the widest real-world model | 1·2 (heavy)·6, accounting bugs such as split quantity loss |
| NautilusTrader | a Rust core, the same code as live trading | 1, no equity corporate actions, dividends or delistings (tick-centred) |
| Qlib | ML factor research, rolling retraining | 1 (its own format)·4, simple fills and accounting, China-centred |
| bt · QSTrader · Backtesting.py · PyBroker | stacking blocks, an easy start, walk-forward (PyBroker) | 2 (shallow realism)·4, development stopped, licence limits |
| pysystemtrade | volatility-target sizing, hold band | futures only |
| Portfolio123 · Genport · Quantus | screener = strategy, easy screens | closed services (no own data or code, rules cannot be checked) |

In the end, today one picks one of **fast factor research** (vectorbt, Qlib), **accurate trading** (LEAN, Nautilus) or **an easy screener** (Portfolio123, domestic services) and loses the rest, and **ML factors and statistically trustworthy validation** remain manual work outside the engine on every side. No engine gives all of the following in one place.

- a way to put in Korean and US equity panels with point-in-time financials and delistings as they are
- realistic fills and accounting that include the Korean market rules
- an open engine where my factors, ML models, sizing and risk management plug in as blocks
- validation inside the engine that measures overfitting over many paths, not one backtest
- today's screen and live operation from the same file as the backtest

NexusBT brings these five into one engine. The strengths taken from each engine and the weaknesses fixed are in `teardown/MATRIX.md`.

**What it aims for.**
- **The trading environment closest to reality**: trading with event-driven accuracy (fills at the next open after the decision, the adverse side when the order inside a daily bar is unknown, volume caps, upper and lower price limits, halts, tick sizes, costs and taxes, corporate actions, delistings, short borrow costs, exchange rates, reconciliation with a real ledger) — the account moves in event order every trading day.
- **Large panels, fast**: factors, filters and classifiers over all names × the whole period as arrays at once (the same term once, only the columns and dates needed, a year-chunk cache); the simulator moves one step per trading day, but takes all names of that day together.
- **The user need not know this split**: a strategy is made by plugging blocks into nine slots (schedule · universe · signal · construction · sizing · risk · execution · exits · costs), and my own factor, sizing or risk management becomes a block with one function.
- **The same file to the end**: factor validation → backtest → today's screen → live operation are one strategy file, and the data is one snapshot path.
- **ML factors are blocks too**, **validated many times, not once** (walk-forward, CPCV, PBO and DSR inside the engine), **know at once when it is wrong** (what, where, why and how to fix it + whether data, code, config or engine; future information blocked before computing).

```
 snapshot path ──▶ [vector computation] Pipeline: factors · filters · classifiers (all names × period, at once)
                         ▼
               [blocks] schedule · universe · signal · construction · sizing · risk  ── target weights
                         ▼
               [event accuracy] every trading day: orders → fills → costs and taxes → corporate actions → account (all names of that day as arrays)
                         ▼
               results · today's screen · live ledger      ── the same strategy file
```

Intraday and tick (E4) need a true event loop, so then the same blocks run on a Rust core (or a NautilusTrader bridge) (ADR-0016, 11.2). **What it does not do**: shortcuts that make results look good (filling at the same close, future information, survivors only), structures usable only by someone who knows the engine's internals (mandatory callbacks, mandatory format conversion), giving up accuracy for speed (when the two collide, accuracy comes first, and speed comes from a faster implementation checked bit for bit against the reference implementation).

This chapter is explanation; the norms start at chapter 1. The sizing block, the block contract table, high-dimensional workloads, the ML factor block, the in-engine validation design and the `layer:` line of errors are round 4 topics (`review/round4-topics.md`) and are not yet in the v3.2 norms (v3.2's walk-forward and CPCV splitters are still reserved, 6.3).

---

## 1. v1 scope, terms, invariants

### 1.1 What v1 includes / does not include

| Area | In v1 | Not in v1 (when) |
|---|---|---|
| Assets and frequency | Daily equity bars. Market names, calendars and currencies are read from the data (`tds.json markets`), and **supported markets = markets with a market rules pack** (v1 = `KR` (XKRX) and `US` (XNYS)). A market without a pack is E18; with `[markets] allow_untested = true` it runs on the generic pack, marked "untested market rules" [RV-I08] | minutes, ticks, quotes, crypto, futures, options (E4 and E5, design only in chapter 11; their TDS schemas are `experimental`) [9.0 Q35, R-46, RV-I07] |
| Input | TDS v1.4 packages (`tds.json` + Parquet). The data required is **computed from the features the graph uses** (4.3; no fixed list of profiles). Check results come in three: declared / check level / engine-supported. `tds:minimal-daily` (adjusted prices only) serves the **analysis paths** only (`evaluate`, `run_pipeline`, `screen(factor)`); an economic backtest needs raw prices + events (E18). The first public path is `tds import csv` + `tds manifest build` (M1). Missing columns get the fallbacks of 4.5 (announced and recorded) [SC-24, R-66, R-67, RV-I01, RV-I03] | an engine-side data ingestion step (ingest), reading DuckDB directly, importing from zipline, LEAN, Nautilus or DBN (v1.x, "planned" in TDS chapter 9) |
| Terms | Factor / Filter / Classifier, an explicit `nx.Pipeline`, operators with zipline names and 12 built-in factors, window-style user functions `@nx.factor/filter/classifier(window=…)` [R-03, R-05, Codex 11.4.4]. Three-valued Filters (missing = unknown, [V31-21]), market-level series terms `nx.Market.series` ([V31-13]), percentile ranks and weighted composites with an explicit missing-value policy (`pct_rank`, `nx.ops.composite`, [V31-25]), Korean trading-status terms `Trad.*` ([V31-30]) | panel-style user functions (`style="panel"`), period windows ("30d"), built-in correlation, regression, `Illiquidity` and `Beta` factors (after v1) [C8, R-47, OQ-15]; transforms with fitted state (`fit_segment`, reserved) [SC-19] — from v3.3 the only learning term is `nx.ml.factor` (5.3.11) [R4-23] |
| Market cross-sections | per-market cross-sections (default), cross-market cross-section operations `across_markets=True` (final stage only) [A-03] | feeding a cross-market cross-section back into a window |
| Financials | interval lookups of the TDS `fundamentals_state` [9.0 Q24, R-63] | choosing fiscal periods, TTM or source priority inside the engine |
| Portfolio | pure-function target construction: `top`, `bottom` (the short side, when shorting is on), the long–short book `nx.long_short`, **signed weights** (+ long, − short), net and gross exposure caps, weighting equal / value / inverse_vol, `max_weight`, weights within a sleeve, a tie-breaking key (`tiebreak`, default hash [V31-29]), **the sizing slot `sizing=`** (pure functions, market information at the decision only: `size.equal`, `value`, `inverse_vol`, `score`, `erc`, `vol_parity`, `stop_risk` + the modifiers `vol_target`, `cash_floor`, user `@nx.sizer`; `kelly` is v1.x [R4F-02]; 5.5.1a) [R4-02, R4-03], **the risk list slot `risk=[...]`** (toward zero only: `group_caps`, `regime`, `vol_cap`, `liquidity_cap`, fitting to the exposure caps, the account-read-only `drawdown_brake`, `portfolio_stop`, `no_reentry`, user `@nx.risk_rule`; 5.5.2 and 5.5.2a) [R4-04, R4-05, R4-06], user construction blocks `@nx.portfolio` [R4-07] [C6, SC-01, V31-LS-02, V31-LS-03] | the target-state recursive hold band `top(n, hold=m)` (its norms are defined now in 5.5.3; it is implemented in T7.1, the last ticket of v1's M6 — user decision 2026-10-28, off by default) [SC-02, OQ-1]; optimisation `nx.portfolio.optimize`, `nx.risk.ledoit_wolf` (reserved, after v1) [SC-22]; an `on_rebalance` callback that relies on holdings [A-10]; buy/hold/sell asymmetry and turnover caps (v1.x, [V31-31]); correlation-shock and VaR overlays, the ATR version `size.stop_risk(atr=)`, the per-order notional cap `[execution] max_order_value_pct_nav` (v1.x) [R4-05] |
| Orders and fills | market, limit, stop and stop-limit, time in force day/GTC, partial fills under a volume cap, pending orders, a persistent trigger state, quantity conservation (`requested = filled + cancelled + remaining`), the exit-order life cycle (created right after the entry fill, resized at every holding change, no expiry), conservative rules for daily OHLC, intraday sale proceeds not used for intraday buys in the same bar, the quantity buyable under the real cost function, recording per fill the decision resolution, rule, decision price and arrival price [9.0 orders, R-56, SC-11, RV-C05, RV-C06]. Order prices snapped to the price grid (tick sizes), price comparisons in integers of the market minimum unit [V31-05, R3-02], a cap from that session's actual volume [V31-03], minimum trade thresholds and weight bands [V31-06]. Short-sale and cover orders mirror the same rules (the adverse side; in all three fill stages in risk-reducing order, and of two orders that cross the sign, the second only after the reducing one is done [R3-10]) [V31-LS-06]. The time stop `exits.time_stop(n)` (the third OCO barrier) [R4-10] | intraday path order (only with minute or tick data, E4), simulating call-auction queues, daily average-price (VWAP) fills (v1.x, [V31-32]), simulating the US uptick rule (Rule 201) [V31-LS-07] |
| Account | signed holdings (long–short symmetric; shorting off by default; when on, short proceeds, collateral, borrow cost and short-dividend payments) [V31-LS-04, V31-LS-05], the margin account (`[account] type = "margin"`, off by default: one requirement formula, loan interest, a close-of-session margin call → a proportional reduction at the next open, 5.6.7a) [R4G-MG-02], integer share arithmetic (rational ratios) [V31-01], stale valuation prices that reflect corporate actions [V31-02], per-component rounding rules (market rules pack) [V31-05], external deposits and withdrawals in the ledger (time-weighted return; the ledger's CAGR is a TWR index too [R3-19]) [V31-19], cash interest `[account] cash_rate_bps` (default 0) [R3-25], the short-sleeve ruin mark `ruined` (new orders stop, mandatory obligations as negative cash) [R3-09], separately funded sleeves per market, multi-currency valuation, money booked in integer minor units and balanced by the NAV and P&L bridge, decision sizing only from values knowable at the decision (delisting recoveries included), the immediate-settlement research model (`[settlement] model = "immediate"`, a reserved key) [9.0 Q23, 11.4.1, SC-18, RV-C01, RV-C07] | moving money between sleeves, leverage above the gross exposure cap, long margin loans in the cash account (default) (a book outside the feasible region `long_weight + c·short_weight ≤ 1` is E16 before the run) [R3-08], forced liquidation for a collateral shortfall in the cash account (for the margin account `type = "margin"` both are in v1 through 5.6.7a [R6-07]), data on borrowable quantities and borrow fees, T+1/T+2 settlement models [OQ-13], periodic-contribution scenarios in backtests [V31-19] |
| Corporate actions | **one resolver** that takes a reference time (amendments, cancellations, late terms, 5.3.3a), shared by adjustment, accounting and checks. Splits, reverse splits, consolidations (capital reductions), bonus issues (stock dividends, free share issues), cash dividends (booking entitlement, receivable, payment and amendment), return of capital, stock mergers and mixed mergers, cash mergers, terminal value on delisting, a lapse policy for the rights of paid-in capital increases [11.4.3, RV-C03] | automatic handling of spinoffs (fails without data), exchange tender offers, selling or exercising rights |
| Costs | the provisional bp profile (default), commission and tax tables by country and period + ½ spread + the general impact `Y·σ^a3·(q/ADV)^a2` (default a2=0.5, a3=1; `realistic`, after the tables are verified), per-share commissions, 0×, 1× and 2× sensitivity [9.0 defaults, Q6, R-61, SC-11] | calibration to real broker trades (TCA calibration later; only the columns in v1). Optional: provisional cost tables by period and liquidity band (a user setting; the default stays fixed bp) [V31-27] |
| Research | `evaluate` (default label = holding return with dividends reinvested, `fwd_return`; `fwd_return_adj` for comparison; three label times; IC, quantiles, turnover, coverage, counts, naive breadth, expected IR, BHY-adjusted p), `backtest`, `screen`, `sweep`, `compare`, `explain` (term values and **strategy decisions**), `check` (static checks, truncation probe, start-date probe), segment splitting (train/validation/test), attempt records, showing PSR, DSR, PBO, MinTRL and the Lo-adjusted Sharpe, capacity scenarios (optional), rebalance-date luck (`offsets`) and rolling-window tables [V31-26]; **validation methods** `backtest(method=…)` (`linear` default, `walk_forward`, `cpcv`, `cscv`; purging by label availability time and the AFML embargo, real fills and accounting for each fold and path, path distributions, PBO, DSR/PSR/MinTRL, automatic attempt records; 6.3a) [R4-19~R4-22]; **ML factors** `nx.ml.factor` (a training window the engine enforces, fit/predict only, `predictions` and `fits` recorded; 5.3.11) [R4-23]; the label `nx.labels.triple_barrier` (5.8) [R4-24] [9.0 Q26, R-37~R-39, R-57, SC-04~SC-09, SC-13] | MDA and clustered MDA feature importance, sample-uniqueness weights, Hansen SPA, ONC N_eff (v1.x) [R4-23]; meta-labels, Monte Carlo on synthetic data, hyperparameter search inside purged CV (later); the effective number of trials N_eff (v1.x) [SC-10], pass badges, automatic blocking gates [Q7] (cash interest moved into v1 in v3.2 — the account row [R3-25]) |
| Output | tables derived from the event truth (`orders`, `account_events`), cost, sleeve and currency attribution (`attribution.parquet`), exposures (`exposures.parquet`), ecosystem adapters (`Run.to_pyfolio`, `FactorReport.to_alphalens`; pandas an optional dependency), the round-trip trade table `trades.parquet` (long and short) [V31-20], deviation from target and execution quality [V31-14], benchmark-relative metrics and monthly tables [V31-15], long, short, gross and net exposure [V31-LS-10] [SC-07, SC-16] | Brinson sector attribution (v1.x), factor attribution (later) |
| Operation | `live` order preview and pre-checks (E36) [V31-10], the paper ledger, ledgers a person writes (`manual:`: real fills and discretionary records, broker fill CSVs) and manual overrides [V31-18], ledger deposits and withdrawals [V31-19], screen X-Ray [V31-28], CSV order sheets, ledger reconciliation `reconcile`, the ledger status file `status.json` [R-49, SC-14] | sending orders to a broker (separately, after E3) [Q11, OQ-10] |
| Surface | Python API, a thin CLI, static HTML reports, an English quick start (CSV → check → factor → saved run → rerun) [RV-I03] | web server, login, job queue, browser editor [L5] |
| Publishing and distribution | a public repository (Apache-2.0), a clean wheel-install gate, an independent-producer acceptance test, a changelog, a contributing guide [RV-I07, RV-Q05] | publishing on PyPI (user decision, chapter 12 OI-44) |
| Verification | zipline-reloaded pinned at 3.2.1, only as a comparison reference (in an isolated environment). Order types are compared **only through presets that imitate zipline's semantics**, and our adverse-side OHLC rules are tested with hand-calculated golden cases [9.0 Q35, R-64, D7, SC-12]. The TDS conformance checker (`tds check`) | a fork, `engine="auto"` [C10, R-48] |

### 1.2 Terms (a short table; the full text is `CONTEXT.md` in 9.2)

| Term | Meaning |
|---|---|
| TDS | NexusBT Data Standard v1 (document edition v1.4, `tds_version = "1.0"`, status = draft → RC → 1.0). The only input format the engine reads (a folder + `tds.json` + Parquet). `engine-data-standard-v1.4.md` [R6-12] |
| Package, snapshot | one immutable folder that follows TDS. It has a `snapshot_id` and a set of three hashes (physical, value, semantic). An export a producer published is a snapshot |
| Hash set (physical / value / semantic) | physical = sha256 of the file bytes. value = sha256 of a language-independent canonical typed serialisation (TDS 4.5). semantic = value hash + normalised resolution metadata (availability rules, parameters, markets, editions, policies, profile versions). The engine's cache, decision records and rerun use the **semantic hash** [RV-C10] |
| Profile | a TDS bundle a package declares it follows, written with a version (`tds:equity-daily-core@1.0`). It is only a conformance claim; what the engine can do is set by **capability** (4.3) |
| Capability result set | declared / checked up to a level (verified@manifest, schema, full) / supported by this engine. What was not checked is not called passing [RV-I01] |
| Fallback | the defined behaviour of the engine when a profile or column is missing. Always left in the warning `DataProfileWarning` (E30) and in the manifest's `assumptions` (4.5) |
| Edition | `strict` (strict edition, default) or `compare` (comparison edition with vendor values) |
| Market | a key of TDS `markets` (for example `KR`, `US`). Each market has one calendar, currency and time zone. Market names are not hard-coded in engine code |
| Market rules pack | `resources/markets/<MARKET>.toml`: that market's price limits, open tolerance, provisional bp, ½-spread floor, fallback interval for dividend payment and tradability rule version. v1 packs = KR, US. Only markets with a pack are "supported markets" [RV-I08] |
| Session | one trading day of a market calendar. `(calendar_id, session_date)` with `ts_open`, `ts_close` |
| Market axis | the session sequence of one market. Market terms are computed on this axis |
| Session cutoff | the time the term values of market-axis row s are based on = `ts_close(s)` |
| Availability time (`ts_available`) | the UTC instant an observation can first be used. TDS gives it as a column or a derivation rule |
| Decision | one time a sleeve sets its target. Recorded as a `DecisionContext` |
| Information cutoff (`decision_ts`) | the last UTC time of information a decision may use. An observation is used only when `ts_available <= decision_ts` |
| Reference clock (clock) | the setting that fixes the decision time in multi-market strategies: `"<MARKET>_close"` (that market's close; default = the first market when the snapshot's `markets` keys are sorted by UTF-8 bytes, `KR_close` for a KR+US package [R3-18]), `market_local` (`utc:HH:MM` reserved) |
| Sleeve | an account compartment funded separately for one market. Cash in local currency, no transfers between sleeves |
| Base currency (base_ccy) | the currency of combined reports. It changes valuation only, not information time |
| Term | Factor (number), Filter (true/false), Classifier (category). A graph node |
| Registered kernel | a computation kernel the engine provides (built-in factors, operators). The numeric rules (5.3.10) and the promise of bit determinism apply to it. User window functions are not registered kernels |
| Eligibility / tradability | eligibility = can it be chosen at the decision (universe). tradability = can it fill in the execution session (state machine). A name halted at the decision can still be chosen if it is eligible; the state machine blocks the fill [SC-23] |
| Canonical target | the `(instrument_id, target_weight)` table one decision produces. What must be the same in screen and backtest |
| Target stage | the stages that build the canonical target: construction (`construction`, `portfolio=`) → sizing (`sizing=`) → risk (the market-only rules of `risk=`). None of them takes the account state; account-reading risk rules come after them, in the final-target layer (5.5.2a) [SC-01, R4-04, R6-12] |
| Target state, anchor | the canonical target set of the previous decision (the recursive input) and the decision where that recursion starts. Used by the hold band (T7.1, the last ticket of v1 M6) [SC-02, R6-12] |
| Order intent | share-quantity orders computed from the canonical target + the account state |
| Run | one `evaluate/backtest/screen/sweep/live`. A `runs/<run_id>/` folder |
| study | the group in which attempts are counted. Default = the strategy (or factor) file name. Stored with a stable `study_id` (UUID) |
| Candidate | a distinct (graph hash, parameters, config, segment) combination within a study. It has identity only |
| Observation | the statistics from running one candidate once (snapshot, period, Sharpe, skewness, kurtosis, NW t). Running again adds an observation and does not overwrite one [RV-C12] |
| Cohort | a set of comparable observations (same study, kind, segment, label, horizon, frequency). DSR's N and V[SR] and BHY's m are counted within one cohort only, and the report keeps `cohort_sha256` [RV-C12] |
| Segment | a user-named period: `train`, `validation`, `test` and so on |
| Exposure | the record of which segments a run computed performance on. (A different word from the portfolio exposure table `exposures.parquet`, which is "holdings exposure") |
| `fundamentals_state` | the table of financial-state intervals that the producer resolved and exported (TDS 5.18) [R6-12] |
| Reconcile | replaying the paper ledger **with the snapshots the ledger recorded** to find the first difference. Comparison with the latest data is `restate=True` (restatement) [SC-14, RV-C13] |
| Resolver | the function that takes a reference time and resolves corporate-action amendments, cancellations and late terms (separating an event's existence time from its terms time, 5.3.3a [R3-01]) into one version per event and four effects (price factor, share factor, entitlement, settlement). Adjustment, accounting and checks use only this (5.3.3a) [RV-C03] |
| Price grid | the price points laid out at the tick size of that market, date and price band. Order prices snap to the grid on the conservative side, and price comparisons use integers of the market minimum unit (KR 1 won, US 0.0001 dollars) — not tick counts that differ by price band (5.6.4a) [V31-05, R3-02] |
| Three-valued Filter | true, false, unknown (missing input). `~`·`&`·`|` follow the Kleene rules; at the final use (universe, selection, mask) unknown = false (5.4.1) [V31-21]. The only explicit replacement is `Filter.fillna(bool)` [R3-13] |
| Signed holding and weight | long = positive, short = negative. Gross exposure = Σ|w|, net exposure = Σw. With shorting off, every target weight ≥ 0 [V31-LS-02] |
| Phase | the full order of events within a session: `session_start < open < intraday < close_fill < close_mark < decision < session_end` [RV-C02] |
| Ruined sleeve (`ruined`) | a sleeve with shorts whose `decision_value ≤ 0`. That sleeve creates no new order intents and books only the mandatory obligations (5.6.7) [R3-09] |
| Rule estimate | a rule value (`short_exit_estimate` and the like) used to put a short's obligation of unknown amount into decision sizing. It is not a cap, and in `nav_economic` it is replaced by the realised amount (5.6.9) [R3-09] |

### 1.3 Invariants (tested in every milestone)

| # | Invariant | Test |
|---|---|---|
| INV-01 | **Information time**: every observation x a decision d uses has `ts_available(x) <= decision_ts(d)`. This holds not only for signal inputs but also for **the account inputs that size orders** (valuation prices, receivables of known amount, terminal recoveries, exchange rates) [11.4.1, C1, RV-C01]. A corporate action is visible from its existence time and, before its terms time, is an entitlement of unknown amount (5.3.3a) [R3-01]. **Fill causality**: fill prices and cost components use only values knowable by that fill stage (an open-stage fill price does not depend on that session's H, L, C or volume; cost inputs up to t−1). Fill **quantities** use that session's realised volume as an **after-the-fact feasibility cap** (5.6.6): it is not a decision input, and it is an approximation that can move results in either direction (v3.1's "it only reduces, so it cannot make results better" was false and was removed; announced as an assumption sentence) [V31-22, V31-03, R3-03] | property tests P-FUT, P-FILLCAUSAL, hand-calculated G-TIME, G-42. There is only one exception: a pretrained model's `allow_overlap=True` (5.3.11, declared, marked and recorded by the user) [R5-03]. |
| INV-02 | **Future-data invariance**: adding data after time τ to a snapshot leaves the canonical targets and orders of the decisions with `decision_ts <= τ` unchanged [11.8] | P-FUT |
| INV-03 | **Chunk invariance**: in the same environment (same `uv.lock`, same CPU kind), changing the period chunk size or the parallel order leaves the results the same. Chosen names and target weights exactly, **registered-kernel node** values bit for bit, **user-function nodes** as "same window input → same output" (the window inputs themselves do not depend on chunking, so the results are the same too). There is no bit promise across different environments [11.7, SC-03, RV-C11] | P-CHUNK |
| INV-04 | **Index permutation invariance**: changing the order of the in-memory dense index leaves the results bit-identical (cross-section reductions use the sorted index order of 5.3.10) [11.8, SC-03] | P-PERM |
| INV-05 | **Cache invariance**: cache hits and misses (L0 raw blocks, L1 term values) give bit-identical results. The key holds everything the result depends on (file sha256, every version and availability time of the corporate-action chain, axis datasets, propagated input rows) (5.3.9) [C9, SC-15, R3-04] | P-CACHE |
| INV-06 | **Accounting balance**: money is booked in integer minor units (int64). Every day `nav_economic = cash + Σ holding×valuation price + receivables + unsettled entitlements (realised amounts)`, with zero difference (in minor units). **NAV and P&L bridge**: per currency, every day `NAV_t − NAV_{t−1} = price-change P&L + distributions (dividends, return of capital, cash consideration) + corporate-action cash (fractional shares) − costs + FX conversion and exchange-rate effects + rounding residual`, and the bridge rows close with zero difference (external deposits and withdrawals are the bridge's `external_flows` row — ledger only, 0 in backtests [V31-19]; borrow cost, rebates, cash interest and margin loan interest (`margin_interest`) are the `financing` row [R3-09, R3-25, R4G-MG-04]). Mandatory obligations (borrow cost, short dividends, terminal obligations, tax payments) are booked as negative cash even when cash is short (`shortfall`), and in the cash account order fills never create negative cash [R3-09] (the margin account's loans are in 5.6.7a; the bridge formula is the same). Valuation prices are on the same corporate-action basis as the holdings at the same time (a stale valuation price on a day without trades is also multiplied by the price factors of later events, 5.6.3 [V31-02]). Holdings are signed (short = negative), and the same formula holds for shorts as it is (including the short-dividend payment and borrow-cost rows) [V31-LS-08]. v2's "sum of cash flows = NAV change" was a false formula that left out valuation gains and was removed [11.4.3, blueprint chapter 9 item 6, RV-C07] | P-NAV, P-BRIDGE, hand-calculated G-48, G-49, G-54, G-65, G-72, report `reconciled: yes` |
| INV-07 | **No duplicates**: after a rerun or a resume, no event, payment or fill is duplicated [11.8] | P-RESUME |
| INV-08 | **screen = backtest**: the same strategy, snapshot, policies, **anchor** and `DecisionContext` give the same canonical target. With the same account state as well, the same order intents. The target is a function only of the information at the decision and the canonical target state of the previous decisions (the target-state recursion), and does not take the account state [R-13, 11.4.6, SC-02] | P-PARITY13 |
| INV-09 | **Determinism**: in the same pinned environment, with the same input (the same semantic hash), the output Parquet bytes are identical and the value hashes are identical [R-31, 11.7]. The deterministic path does not depend on wall-clock time, random numbers or hash-set iteration order, so it is the same even in **two new processes** with different `PYTHONHASHSEED` (2.5) [V31-08] | rerun test, P-DET (two new processes) |
| INV-10 | **Resume = one go**: the result of resuming from a state checkpoint = the result of running without a break. Paper-ledger reconciliation (`reconcile`) is its operational version [11.8 M3, SC-14] | P-RESUME, P-RECON |
| INV-11 | **Adjustment agreement**: a registered kernel's shortcut value = the reference implementation's value (relative 1e-12; an algebraically equal transform, so bit identity is not promised) [C2, RV-C11] | P-ADJ |
| INV-12 | **No hidden filling**: missing values propagate, and filling happens only through an explicit operation (`fillna`). The data fallbacks (4.5) are not hidden filling but defined behaviours that are announced and recorded [C7] | unit tests |
| INV-13 | **Fixed numeric order**: sums, means and variances of registered kernels are computed in the defined order of 5.3.10 (windows by ascending row, cross-sections in sorted `instrument_id` order), and in the same environment the fast kernels are bit-identical to that result. Kernels of the **transcendental-function class** (`log`, `exp`, `pow`) call the same compiled element function on the reference and fast paths (bit-identical in the same environment, relative 1e-12 across environments). BLAS, `fastmath` and parallel reductions are not used [SC-03, RV-C11] | P-KERNEL (fast = reference, bits) |
| INV-14 | **Start-date invariance**: moving the run's start date by k sessions leaves the term values and canonical targets of the overlapping decisions bit-identical (every term is a function only of the data in its own window, and schedules are anchored to the calendar, not to the start of the run — `every(n)` is the absolute `session_ord`). For strategies with the target-state recursion on, only with the same anchor [SC-04, RV-C11] | P-START |
| INV-15 | **Metamorphic relations**: under price scaling (M-SCALE), adding names outside the universe (M-DUMMY), a fake split of ratio 1.0 (M-SPLIT-NEUTRAL), changing the base currency (M-CCY) and summing sleeves (M-SLEEVE), the relations of the table in 8.3 hold **within that table's preconditions**. Counterexamples that break the preconditions are tested too [SC-04, RV-C11] | `tests/property/test_metamorphic.py` |
| INV-16 | **Events are the truth**: `positions`, `daily`, `metrics`, `attribution` and `exposures` can be rebuilt from `orders` and `account_events` (+ snapshot prices and exchange rates) and are equal to the rebuilt values [blueprint chapter 11 item 1] | P-DERIVED |
| INV-17 | **Input conformance**: the engine reads only the datasets and files declared in `tds.json` (inside the package folder, with no duplicate paths), and uses only packages that passed the check level declared at open (4.4). The synthetic generator's output passes `tds check --level full` [SC-24, TDS-D21, TDS-D24, RV-I01] | P-TDS, `test_synth_conforms` |
| INV-18 | **Order quantity conservation**: for every order, always `requested_qty = filled_qty + cancelled_qty + remaining_qty` (all ≥ 0; the order quantity is a size and the direction is `side`), and a split rebase is left as an event (`order_rebased`). Exit orders do not expire until the holding is 0 [RV-C05]. Share counts use integer arithmetic (5.6.1 `floor_shares`, rational ratios), so holdings of integer multiples create no fractional-share cash (long and short alike) [V31-01, V31-LS-05]. A cover quantity does not exceed the short size `|q|` (the excess is `qty_cancelled(over_cover)`) [R3-10] | P-QTY, P-STATE, G-53 |
| INV-19 | **Ledger once**: in the paper ledger, a decision emits its order batch exactly once and a session fills exactly once. After concurrent runs or a forced stop at a commit boundary, it recovers to one valid state [RV-C13] | P-LIVE, P-BOOK |
| INV-20 | **Price grid**: every limit and stop price, and the fill prices set from them, lie on that session's price grid (open and close fills take the data value as it is). Price comparisons use integers of the market minimum unit (`[grid] base_unit`) — not tick counts that differ by price band; an observed bar price that does not fit that integer is not moved, and only that bar is compared in floating point (`off_grid_bar`) [V31-05, R3-02] | P-GRID, G-57 |
| INV-21 | **Sleeve independence**: once the targets are set, sleeves are independent of each other — replaying each sleeve separately = replaying them together (exception: `[taxes] pay = "cash"` spanning several markets) [V31-11] | P-SLEEVE-ISO |
| INV-22 | **Shorting off = long only**: with `[shorting] enabled = false` (default), the exposure-cap stage is not called, there are 0 short events and collateral entries, and the value hashes of the four core tables (`targets`, `orders`, `account_events`, `daily`) equal the baseline from before the shorting tickets. Even when it is on, with no negative targets and `max_gross ≥ 1`, `max_net ⊇ [0, 1]`, the value hashes of all tables equal those of an off run of the same build (borrow cost 0, collateral computed only when there are shorts; if the user gives narrower exposure caps, longs can shrink too, so they are not the same) [V31-LS-09, R3-07, R3-11] | P-SHORT-OFF (differential + baseline) |
| INV-23 | **Risk off = canonical** [R4-04]: without account-reading risk rules (`reads_account=True`), the account layer (5.5.2a) is not called, `targets.final_weight` is bit-identical to `target_weight` (the canonical target), and the `risk_state` table is empty. Even with account rules, if they always return `m = 1`, the value hashes of all the output tables (`targets`, `orders`, `fills`, `account_events`, `daily`, `bridge`, `coverage`, `skips`) **except** the following equal those of a run without rules: `risk_state`, the `step LIKE 'account:%'` rows of `waterfall`, the manifest's `graph_hash`, `settings_hash` and `run_id` (the rule order goes into `graph_hash`, 14.5), and the "risk order" line of the report header [R4F-08]. The sizing slot and the market-only risk rules do not take the account, so they are part of the canonical target and INV-08 holds as it is; the result of account rules (`final_weight`) is screen = backtest, like order intents, only when the account state is the same too | P-RISK-OFF, P-SIZE-PURE, P-RISK-SHRINK |

### 1.4 Requirement numbers added by this spec

| Number | Requirement | Source |
|---|---|---|
| R-56 | v1 implements market, limit, stop and stop-limit orders, day/GTC, partial fills under a volume cap, pending orders and the exit-order life cycle (5.6.2a). On daily bars it decides by the conservative OHLC rules (5.6.4) and **is tested with hand-calculated golden cases (G-02~G-09, G-31~G-33, G-37~G-41)**. Comparison tests against zipline cover only the order types of the preset that imitates zipline's trigger behaviour (`preset="zipline"`) (8.1 L2-d) | 9.0 orders and advanced options, SC-12, A-57 |
| R-57 | There is no future lock. The user sets the train/validation/test segments in `nexusbt.toml [split]`, and a run chooses one with `segment=`. The engine records attempt counts and exposure and shows DSR | 9.0 Q26 |
| R-58 | Micro-caps are included by default and excluded with one config line (`exclude_microcap = true`). No hidden exclusion | 9.0 Q31 |
| R-59 | The benchmark defaults are the KOSPI and S&P 500 total-return indices. If the snapshot has no index members, the benchmark is marked "none" and not built | 9.0 Q30 |
| R-60 | When a dividend pay date is missing, it is estimated from the usual interval of the country and marked "estimated" | 9.0 Q29 |
| R-61 | Until the cost tables are verified, provisional bp costs (`provisional`) are the default and the report shows "provisional costs" | 9.0 Q28 |
| R-62 | Korea and the US are separately funded sleeves. The reference clock stays a setting. Each decision records a UTC `decision_ts` | 9.0 Q23 |
| R-63 | `Fund.*` only looks up intervals of the TDS `fundamentals_state`. The engine does not rebuild accounting selection rules | 9.0 Q24, C3 |
| R-64 | zipline-reloaded is used, at a pinned version, only as the comparison reference (oracle). The engine's run path does not import zipline | 9.0 Q35, D7 |
| R-65 | The engine is built with the plinth loop: the repository with `/plinth:new-project`, `/implement #N` for each ticket, merged after the required checks pass + a visual check | user requirement (chapter 9) |
| R-66 | The engine's input contract is TDS v1.1 (`tds_version` 1.x). The engine calls the TDS conformance checker (the `nexusbt_tds` package) as a library to check snapshots, and raises a failure as a `SnapshotError` (E14) carrying the TDS error code and (if there is one) the producer hint. Error messages do not include a particular producer's internal tickets | SC-24, TDS-D21, RV-I09 |
| R-67 | Even when a package does not fill every column and dataset (a valid lower-profile package), the engine runs by the fallback table of 4.5, announcing each fallback it uses (E30) and leaving it in the manifest. When a fallback cannot define the result, it fails (E18). A package that breaks the profile it declared is not repaired by fallbacks (E14) | the user's principle "no hidden filling", RV-I01 |
| R-68 | Market, currency, clock, sleeve and index ids are read from the data. Per-market rules are in market rules packs (4.7), and a market without a pack does not run without `allow_untested` | RV-I08 |
| R-69 | The public user's first path: two CSVs → `tds import csv` → `tds check` → `evaluate`/`run_pipeline` → a saved run → `rerun` works by the English quick start, without private producer knowledge | RV-I03 |
| R-70 | Release gate: the public examples run from a clean wheel install, and an independent producer's package passes the `full` check and the consumption test. A "KR/US verified" claim is made only with evidence (a summary) on real data. For every market rule applied (ticks, price limits, bans, rounding), the release evidence lists its source, its effective boundary and `verified` [R3-15] | RV-I07 |

---

## 2. Repository layout, dependency rules, security rules

### 2.1 Repository, public scope, licence, environment

- Repository: `<owner>/<name>` (after the name is settled, chapter 12 OI-05), **public**, plinth `--archetype=library`. Separate from the data producer [design 1 principle 4].
- **Public scope** (user decision 2026-10-27, TDS-Q5 decided): the engine code, this spec, and the data standard TDS with its format and checker **are designed on the premise of public distribution**. What stays private is only the **real data** inside the reference producer (raw data files, the DB, snapshots, vendor data). The user memory "personal research only (no redistribution, not public)" now applies only to the data [A-97].
- **Licence: Apache-2.0** (the repository's `LICENSE`, `license = "Apache-2.0"` in each package's `pyproject.toml`, a `NOTICE` file). Reasons:
  1. A permissive licence with a patent grant gives the lowest barrier to reusing a public engine and standard.
  2. It is the same licence as the comparison reference zipline-reloaded (Apache-2.0), so quoting its code and comments in `tests/parity` raises no compatibility problem.
  3. It is compatible with every core dependency (numpy, numba, scipy BSD; pyarrow, exchange-calendars Apache-2.0; polars MIT; jinja2 BSD) [R7-10: exchange-calendars licence = Apache License 2.0, checked against the original text of the repository's LICENSE 2026-10-29 ([LICENSE](https://github.com/gerrymanoim/exchange_calendars/blob/master/LICENSE)); T0.1 checks it again at the pinned version].
  4. NautilusTrader (LGPL-3.0) is used in the E4 bridge only as the **optional dependency** `nexusbt[nautilus]`, by importing the installed library without copying its source. LGPL allows such use and puts no obligation on the Apache-2.0 code (it is enough that the user can swap the library; a Python import satisfies this) [est.: not legal advice]. The engine's default install contains no LGPL code.
  5. The list of code not to copy (GPL: Freqtrade, backtrader, pysystemtrade; AGPL: Backtesting.py; non-commercial: RQAlpha; Commons Clause: vectorbt, **PyBroker** (Apache-2.0 + Commons Clause, the first line of its `LICENSE` is "Commons Clause License Condition v1.0") [V31-33]; subscription: vectorbt PRO; paid implementation: mlfinlab) stands. Only ideas are borrowed. MIT code (ported functions of ml4t-diagnostic) keeps the original repository, commit and licence text at the head of the file and is listed in `NOTICE` [Q22].
  6. The development-only dependency hypothesis (MPL-2.0) does not go into the distribution.
- **What does not go into the repository** (public repository rules, enforced by tests — 2.7): reference-producer data, snapshots or any part of them, answer files (fixtures) made from vendor data, producer data paths (absolute paths under the user's home and the like) and internal host names and addresses, secrets. All test data is made only by the synthetic generator (4.8). Evidence files of Mac mini measurements and real-data comparisons hold **summary numbers only** (row counts, maximum error, pass or fail, `snapshot_id`), not per-instrument values or prices.
- Python: **3.13** (`.python-version`). Package management `uv` (workspace), lockfile `uv.lock` (required by plinth). The comparison test environment is separate, **Python 3.12** (`tests/parity/`, 8.1).
- Where it runs: the user's compute machine that holds the data (currently a Mac mini M4 16 GB; its address and account only in the user's notes outside the repository). A notebook on a laptop attaches to that machine's Jupyter kernel over SSH. The engine builds no remote-call feature [Q9, A-17]. The data location is taken only from config (`[data] root`) or the environment variable `NEXUSBT_DATA_ROOT`.

### 2.2 Pinned versions (as of the first `uv.lock`)

Policy: every dependency is pinned exactly by `uv.lock`. A version published less than 14 days before locking is not used. Versions are raised by plinth step 9, one at a time, after the required checks pass.

| Package | Version | Use | Notes |
|---|---|---|---|
| numpy | 2.5.3 | dense block computation | numba 0.68 needs numpy < 2.6 |
| numba | 0.68.0 (llvmlite 0.50.0) | hot loop kernels | `cache=True`, `fastmath=False`, `parallel=False` (5.3.10). The first JIT delay is measured separately (chapter 7) |
| pyarrow | 26.0.0 | Parquet reading and writing, Arrow tables, IPC (L0 and L1 caches) | the only Parquet writer (deterministic writes) |
| polars | 2.0.0 | helper for interval lookups and sorting, user output tables | not used in the computation graph [Q15] |
| scipy | 1.18.1 | normal distribution functions, ranks | |
| jinja2 | 3.1.6 | `report.html` | one page with no external files |
| pandas | optional dependency `nexusbt[pandas]` | `.to_pandas()`, ecosystem adapters (5.9.8) | the latest 2.x/3.x compatible with numpy 2.5 at locking |
| exchange-calendars | 4.13.2 | predicting the next session in `live`, a substitute session table (4.5 F-02), the synthetic generator | for past sessions TDS `calendar_sessions` is canonical [design 5.2] |
| optional dependency `nexusbt[nautilus]` | pinned when E4 starts (A-30) | event bridge | LGPL-3.0, only the name in v1 |
| optional dependency `nexusbt[ml]` | pinned at locking (scikit-learn 1.x, BSD-3-Clause) | ML examples and tests (the models of `nx.ml.factor`) | the engine does not import it (5.3.11). The default wheel runs without sklearn and the ML examples run in an environment with the extra installed — two install checks (`test_clean_wheel_runs_example`, `test_ml_extra_runs_ml_example`) [R4F-23] |
| optional dependency `nexusbt[opt]` | after v1 | `nx.portfolio.optimize` (reserved) | cvxpy or Riskfolio-Lib, after the licence is checked [OQ-8] |
| development: pytest 9.1.1, hypothesis (14-day rule), psutil 7.2.2 | | tests, memory measurement | ruff, mypy and coverage versions are set by the plinth template |
| comparison environment: zipline-reloaded 3.2.1, pandas 2.3.3 (requires <3.0), numpy as the lock sets it | | only for `tests/parity/` | not installed in the engine environment [R-64] |

### 2.3 Package layout

The split follows the deep-module principle (a small interface, much implementation). Each package exports only the "public interface" below from its `__init__.py`; the rest are internal modules with a `_` prefix [Codex 11.6, codebase-design]. The repository is a uv workspace with two distributions: the engine `nexusbt` (import `nexusbt`) and the data-standard checker `nexusbt-tds` (import `nexusbt_tds`, CLI `tds`). TDS is a **public document and package versioned separately** from the engine (the `tds/` folder, version = `tds_version` `1.0`, package version the matching `1.0.x`, release status draft → RC → 1.0) [A-98, RV-Q04, RV-I07].

```
nexusbt/                                     (public repository, Apache-2.0)
├── LICENSE  NOTICE  pyproject.toml(workspace)  uv.lock  .python-version
├── AGENTS.md  CONTEXT.md  README.md(English)  CONTRIBUTING.md  SECURITY.md  CODE_OF_CONDUCT.md  CHANGELOG.md
├── docs/spec/engine-spec-v3.4.md             (this document [R6-02]; the public edition without private comments, personal information or hosts)
├── docs/quickstart.md                        (English quick start, tested by 8.5)
├── docs/adr/0001-… .md                       (9.3)
├── docs/requirements.md                      (keeps appendix B with its status)
├── tds/                                      ★ data standard (versioned separately)
│   ├── README.md  CHANGELOG.md
│   ├── spec/tds-v1.md                         (the TDS document body; the public edition of engine-data-standard-v1.4.md without chapter 11 (producer mapping) or personal information)
│   ├── schemas/<kind>/<MAJOR.MINOR>.json      (machine-readable dataset schema sources, TDS 10.3; `status: stable|experimental`)
│   ├── conformance/<code>/{pass,fail}/        (small passing and failing packages for each code, TDS 8.5)
│   ├── conformance/hash-vectors.json          (language-independent test vectors for the value and semantic hashes, TDS 4.5)
│   ├── pyproject.toml                         (distribution name nexusbt-tds, dependency: pyarrow only)
│   └── src/nexusbt_tds/                       check, hash, manifest, describe, import_csv (no import of nexusbt)
├── src/nexusbt/
│   ├── __init__.py          re-exports only the public surface (3.1)
│   ├── contracts/           the ID constant, engine-side column sets, units, policies, errors (no dependencies)
│   ├── config/              reading and validating nexusbt.toml (secret keys forbidden)
│   ├── data/                opening snapshots (calls the tds checker), profiles and fallbacks, market blocks, L0 cache, interval lookups, calendars, exchange rates
│   ├── pipeline/            term value objects, datasets, operators, built-in factors, Pipeline, hashes, static checks
│   ├── compute/             planning, reference kernels, fast kernels, adjustment, cross-sections, L1 cache, executor
│   ├── portfolio/           scores → canonical target (pure functions, stages: construction → sizing → risk) + the account layer final [R4-02, R4-04]
│   ├── risk/                money management `size.*` and risk rules `risk.*` (5.5.1a, 5.5.2, 5.5.2a; reserved `ledoit_wolf`) [R4-02, R4-05]
│   ├── ml/                  the `ml.factor` training node, training windows, `fits` and `predictions` records (5.3.11; does not import sklearn) [R4-23]
│   ├── execution/           orders (columnar order table), fill models, costs, sizing, the daily state machine, presets
│   ├── accounting/          columnar account state, integer minor-unit booking, consuming the corporate-action resolver, entitlements, terminal value, valuation, NAV bridge
│   ├── research/            labels (triple barrier included), IC, quantiles, breadth, statistics (NW, PSR, DSR, PBO, MinTRL, BHY, Lo), segments, splitters and validation methods (6.3a), attempt records, probes
│   ├── artifacts/           run transactions, manifests, hashes, index (SQLite), saved sources, ledgers, reconciliation, attribution and exposure, reports
│   ├── api/                 evaluate/backtest/screen/live/fill/reconcile/sweep/compare/explain/check/describe/runs
│   ├── cli/                 argparse subcommands (a thin layer that calls api)
│   ├── compat/              zipline.py (imitates zipline names, no zipline import), adapters.py (pyfolio and alphalens shapes, pandas optional)
│   ├── bridge/              the E4 event-engine boundary (Protocols and data types only, chapter 11)
│   ├── testing/             the synthetic TDS package generator (4.8), hand-calculation helpers
│   └── resources/           markets/{KR,US,_generic}.toml (market rules packs), costs/default_v1.csv, limits/kr_price_limits_v1.csv, ticks/{kr,us}_tick_table_v1.csv [V31-05], shorting/kr_short_bans_v1.csv [V31-LS-07]
├── tests/
│   ├── unit/  property/  golden/  docs/  perf/  repo/  (golden/expected/** cannot be changed by an implementation PR, 8.2)
│   └── parity/              its own pyproject.toml and uv.lock (Python 3.12, zipline 3.2.1)
└── bench/                   measurement scripts and result JSON (summaries only)
```

### 2.4 Public interface by module (deep modules)

Every signature uses `from __future__ import annotations` and passes mypy; data types are `@dataclass(frozen=True, slots=True)`.

| Module | Public interface (only this is called from outside) | What it hides |
|---|---|---|
| `nexusbt_tds` (separate package, `tds` in this document) | `check(path, *, level: Literal["manifest","schema","full"], profiles: Sequence[str] | None = None, datasets: Sequence[str] | None = None, max_errors: int = 1000) -> CheckResult` (`.errors`, `.warnings`, `.profiles: dict[str, ProfileStatus]` — `ProfileStatus(declared: bool, verified_level: Literal["none","manifest","schema","full"], result: Literal["pass","fail","not_checked"])`, `.unchecked: list[str]`, `.to_jsonl()`), `read_manifest(path) -> Manifest`, `value_hash(path, dataset) -> str`, `semantic_hash(path) -> str`, `import_csv(mapping, out) -> Path`, `build_manifest(path) -> Manifest`, `PROFILES`, `SCHEMAS` | the implementation of the check levels, canonical value serialisation and hash computation, reading schema files |
| `contracts` | `ID_COLUMN`, `ENGINE_COLUMNS: Mapping[str, frozenset[str]]` (the columns the engine reads per dataset, 4.6), `Unit`, `Currency`, `Phase` (the stage order of 5.6.3), `Policy*` enums, `NexusBTError` and its sub-errors (6.6), output schema version constants (`RUN_SCHEMA = "nexusbt-run/2"`, `EVENTS_SCHEMA = "nexusbt-events/1"`, `CHECKPOINT_SCHEMA = "nexusbt-checkpoint/1"`) | nothing (value definitions only) |
| `config` | `load_config(path: Path | None = None, overrides: Mapping[str, Any] | None = None, *, markets: Sequence[str] | None = None) -> Config` (keys that contain a market name are validated against the snapshot's `markets`) | toml parsing, merging defaults, validation messages, the secret-key check, reading market rules packs |
| `data` | `open_snapshot(cfg: DataConfig, *, required: CapabilityRequest | None = None) -> Snapshot` | calling the tds checker, deciding capability (declared, checked, supported), fallbacks, reading partitions, dictionary index → column numbers, L0 cache, rectangular interval lookups, calendars, exchange rates, the corporate-action resolver |
| `data.Snapshot` | `.id`, `.semantic_hash`, `.value_hash`, `.physical_hash`, `.profiles -> dict[str, ProfileStatus]`, `.capabilities -> DataCapabilities`, `.fallbacks -> list[FallbackRecord]`, `.markets -> Mapping[str, MarketInfo]` (calendar, currency, time zone, watermark, rules pack or None), `.calendar(market) -> Calendar`, `.market_block(market, fields, sessions) -> MarketBlock`, `.intervals(kind, fields, market, cutoffs, edition, history_mode="economic") -> PITBlock`, `.actions(market, cutoff) -> ResolvedActions` (5.3.3a), `.events(market, start, end) -> EventTables`, `.fx() -> FxSeries`, `.instruments(market) -> pa.Table`, `.share_counts(market, cutoffs) -> PITBlock`, `.explain(instrument_id, field, ts) -> Explanation` | Parquet, partitions, statistics pruning |
| `pipeline` | `Term`, `Factor`, `Filter`, `Classifier`, `Pipeline`, the datasets `Price/Fund/Meta/Panel/Label`, the `factor/filter/classifier` decorators, the `factors` module, `graph_hash(term) -> str`, `static_check(graph, ctx) -> list[Finding]` | node normalisation, hash computation |
| `compute` | `compute(pipeline: Pipeline, grid: DecisionGrid, snapshot: Snapshot, policy: ComputePolicy, cache: TermCache | None = None) -> FactorFrame` | planning, batching, kernel choice, adjustment, cross-section operations, parallelism |
| `portfolio` | `build_targets(scores: FactorFrame, rule: PortfolioRule, grid: DecisionGrid, *, risk: RiskRule | None = None, prior: TargetState | None = None) -> tuple[TargetFrame, TargetState]` | tie handling, caps, weighting, recursion |
| `risk` | `RiskRule` (Protocol: `apply(targets: TargetFrame, inputs: DecisionInputs) -> TargetFrame`), `none() -> RiskRule` | – |
| `accounting` | `AccountState` (columnar, 5.6.1), `apply_session_start(state, session: SessionInputs, actions: ResolvedActions, policy: AccountingPolicy) -> tuple[AccountState, list[Event]]`, `value(state, marks: Marks, fx: FxView, *, asof: datetime) -> Valuation`, `bridge(prev: Valuation, cur: Valuation, events) -> BridgeRows` | handling entitlements, receivables and corporate actions, integer minor-unit booking |
| `execution` | `simulate(targets: TargetFrame, market: MarketView, config: SimConfig, initial: AccountState, sink: EventSink) -> SimResult`, `step_session(state, orders, session: SessionInputs, config) -> StepResult`, `SimConfig` (every knob of appendix C) | the order state machine, fill rules, costs, sizing |
| `research` | `forward_labels(..., kind: Literal["econ","adj"] = "econ") -> LabelFrame`, `factor_stats(values: FactorFrame, labels: LabelFrame, cfg: EvalConfig) -> FactorStats`, `psr`, `dsr`, `min_trl`, `pbo_cscv`, `bhy_adjust`, `lo_sharpe`, `newey_west_t`, `signal_weight_corr`, `Segments`, `TrialRegistry` (candidates, observations, cohorts), `probe_truncation`, `probe_start` | quantile rules, bandwidth |
| `artifacts` | `RunStore(root).begin(kind, name, study, ...) -> RunTxn`; `RunTxn.write_table(name, table)`, `.capture_sources(paths)`, `.set_manifest(fields)`, `.seal() -> RunRecord`, `.abort()`; `Index(root)` (holds the canonical pins); `BookStore(root).open(name) -> BookTxn` (locking, state version comparison, commit, recovery, 5.9.6); `derive_tables(events, prices, fx) -> DerivedTables` (INV-16); `render_report(run) -> Path` | temporary folders, atomic renames, fsync order, hashes |
| `api` | the functions of 3.8 | coordination |

**A seam where Rust can be swapped in** [R3-26, ADR-0016, user decision 2026-10-28]: the three hot kernels sit behind a narrow internal interface — `nx.compute._kernels` (window and cross-section kernels: array input → array output, no state), `nx.execution._step` (one step of the session simulator: columnar state + that session's input arrays → new state + event arrays), `nx.accounting._state` (the columnar account state and its booking functions). These three take no Python objects, callbacks or dicts; they exchange only Arrow arrays (or numpy arrays that share their buffers), integer and float scalars and integer codes. The reference implementation is Python (+ Numba), and another implementation (a Rust crate, PyO3/maturin, an optional build) is swapped in only with the same signatures, while `tests/property/test_kernels.py::test_kernel_swap_bit_equal` checks that it is bit-identical to the reference in the same environment. The condition for swapping is in chapter 7 (measurements and profiles). The signature rules are checked by `tests/unit/test_import_rules.py::test_*_seam_signatures_arrow_only` (T1.7b, T3.3, T3.4).

### 2.5 Dependency rules (enforced by tests)

```
tds (separate package; does not import nexusbt)
contracts ← config ← data ← compute ← api ← cli
nexusbt_tds ← data
contracts ← pipeline ← compute
contracts ← risk ← portfolio ← api
contracts ← accounting ← execution ← api
contracts ← research ← api
contracts ← artifacts ← api
```

- No import against the direction of an arrow. Only `api` combines several modules. `cli` imports only `api`.
- `src/nexusbt/**` and `tds/src/nexusbt_tds/**` do not import `zipline`, `nautilus_trader`, `duckdb`, `pickle`, `dill`, `cloudpickle`, `joblib` or `shelve` [R-64, design 1 principle 4, SC-27]. `np.load(..., allow_pickle=True)` and `pd.read_pickle` are forbidden too. Enforced by ruff `flake8-tidy-imports.banned-api` and `tests/unit/test_import_rules.py` (reads every import and call through the AST and compares them with the graph above). The "checker reference implementation DuckDB (read-only)" of TDS 8.5 is implemented in this repository with pyarrow only [A-99].
- **No sources of non-determinism** [V31-08]: the decision-path modules (`data`, `compute`, `pipeline`, `portfolio`, `risk`, `accounting`, `execution`, `research`) do not use `datetime.now/utcnow/today`, `time.time/monotonic/perf_counter` (for progress display, and only in `api`), `random`, `numpy.random` (except where a `Generator` made from the probes' `[checks] seed` is taken as an argument), `uuid.uuid1/uuid4`, `os.urandom` or `secrets`. Where iteration over a `set`, `frozenset` or `dict` sets the order of events, outputs or sums, it goes through `sorted(...)`. Only `artifacts` makes the run time, `run_id` and `study_id`. Enforced by ruff `banned-api` + the AST test `tests/unit/test_determinism_rules.py`, and P-DET runs in two new processes with different `PYTHONHASHSEED` (Nautilus NT#3914: two runs with the same seed differed by 6% in PnL because of hash iteration order).
- `pipeline` reads no data (value objects and hashes only). The column and capability information needed to build a graph is passed at binding as a **schema registry** (`SchemaRegistry`, a value object) that `api` builds from the snapshot [RV-I05]. `portfolio`, `risk` and `research` take only Arrow/numpy arrays.
- User code imports only `nexusbt`, `nexusbt.factors`, `nexusbt.ops`, `nexusbt.costs`, `nexusbt.exits`, `nexusbt.execution`, `nexusbt.portfolio`, `nexusbt.risk`, `nexusbt.dataset`, `nexusbt.compat.zipline` and `nexusbt.compat.adapters` [R-01]. These names are re-exports of `__init__`.

### 2.6 Security rules [SC-27]

- **No pickle**: run outputs, caches (L0, L1), ledger checkpoints and probe results do not use pickle. Tables are Parquet or Arrow IPC, the rest JSON. (Enforced by the forbidden list of 2.5.)
- **No secrets**: if any table of `nexusbt.toml` has a key whose name contains `key`, `secret`, `token` or `password`, it is a `ConfigError` (E16, "secrets do not belong in nexusbt.toml; use environment variables or the OS keychain"). Broker keys come later, only through environment variables or the keychain, by an adapter ADR. This is blocked together with the repository's `ci / secrets` check.
- **Code that runs**: `rerun` runs the run folder's `source/` in a **new process** (5.9.3; so that a module of the same name already imported in the current session does not get in the way). If the run manifest's `environment.machine_id` (= sha256(host unique id)[:16]; the original host name is not kept) differs from the current machine, it refuses with `UntrustedRunError` (E31) and runs only with `nx.rerun(id, trust=True)` / `nexusbt rerun ID --trust`.
- **No data collection**: the engine does not collect data (that is the producer's job).
- **Package path safety**: the engine and the checker do not read `tds.json` paths that point outside the package folder (`..`, absolute paths, symbolic links that lead outside) or a path that appears twice (TDS-M012/M013, E14) [RV-I01].

### 2.7 Public repository hygiene (enforced by tests)

`tests/repo/test_public_hygiene.py` (part of the default `ci / test`):
- `::test_no_private_paths` — fails if any text file of the repository contains a macOS home path (starting with `/Users`), a word from the **forbidden-word list outside the repository** (the file the environment variable `NEXUSBT_HYGIENE_WORDS_FILE` points to, or the git-ignored `.hygiene-private.txt`; it holds the user's accounts, hosts, data paths and producer name — so that those words themselves are not written in the public repository), or a private IP (the regular expression `\b(10|192\.168|172\.(1[6-9]|2\d|3[01]))(\.\d{1,3}){2,3}\b` — four-number addresses only; text such as "section 10.2" is not caught) (the repository edition of this spec is the edition without such lines) [RV-Q03].
- `::test_no_producer_internal_refs` — zero hits in `src/**`, `tds/src/**` and `docs/**` (the public edition) for the producer name of the forbidden-word list, the ticket shape ` X[0-9]+ ` and `.rebuild.lock` [RV-I09].
- `::test_section_numbers_not_ip` — text cases such as "section 10.2" and "172.16" are not caught by the hygiene test.
- `::test_no_data_files` — fails if it finds `*.parquet`, `*.duckdb` or `*.csv` in the repository (except small hand-written files under `src/nexusbt/resources/**` and `tds/conformance/**`). The data of `tds/conformance/` and `tests/` is made by generation scripts and its hashes must match the generation scripts.
- `::test_fixtures_are_synthetic` — every place in `tests/**` that opens a snapshot uses only paths made by `nx.testing.synth.make_snapshot` (a static check).
- `::test_license_headers` — `LICENSE` is Apache-2.0, and ported files have a source header.
- `::test_tds_public_has_no_producer_names` — `tds/spec/tds-v1.md` has no particular producer's name or tickets (TDS chapter 11 is left out of the public edition) [RV-Q04].

---

## 3. Public API

### 3.1 The import surface [R-01, R-09]

```python
import nexusbt as nx
from nexusbt import Price, Fund, Meta, Panel, Label, Trad, Market   # datasets (autocompletion, .pyi stubs; Trad, Market [V31-30, V31-13])
from nexusbt.factors import (Returns, DailyReturns, SimpleMovingAverage, SMA,
    ExponentialWeightedMovingAverage, EWMA, AverageDollarVolume, AverageTradedValue,
    AnnualizedVolatility, RollingStd, VWAP, RSI, MaxDrawdown)
```

Every public name under `nexusbt.` (a name outside this list starts with `_`):

| Kind | Names |
|---|---|
| Terms | `Factor`, `Filter`, `Classifier`, `Pipeline`, `factor`, `filter`, `classifier`, `ops` (`ops.rolling`, `ops.where`, `ops.coalesce`, `ops.composite` [V31-25]) |
| Data | `Price`, `Fund`, `Meta`, `Panel`, `Label`, `Trad` [V31-30], `Market` [V31-13], `dataset.from_parquet`, `universe`, `universe.index_members` |
| Strategy | `Strategy`, `param`, `monthly`, `weekly`, `daily`, `quarterly`, `annually`, `every`, `top`, `bottom`, `long_short` [V31-LS-02], `portfolio` (+ the user block decorator `portfolio` [R4-07]), `size` (5.5.1a), `sizer`, `risk` (all the built-in blocks of 5.5.2 and 5.5.2a), `risk_rule` [R4-02, R4-05, R4-07], `execution`, `exits` (including `exits.time_stop` [R4-10]), `costs`, `ml` (`ml.factor`, 5.3.11), `labels` (`labels.triple_barrier`, 5.8), `splits` (`holdout`, `walk_forward`, `cpcv`, `cscv`, 6.3a) [R4-19, R4-23, R4-24] |
| Functions | `open` [V31-PUB-03], `evaluate`, `backtest`, `screen`, `live`, `fill`, `reconcile`, `sweep`, `compare`, `run_pipeline`, `explain`, `check`, `describe`, `runs`, `rerun`, `book`, `override`, `record_fills`, `cash_flow` [V31-18, V31-19], `preregister`, `config` |
| Results | `FactorReport`, `Run`, `Screen`, `Orders`, `BookUpdate`, `ReconcileReport`, `SweepResult`, `Comparison`, `ValidationResult` (`Run.validation`), `Split` [R4-20], `PipelineResult`, `Explanation`, `DecisionExplanation`, `CheckReport`, `RunTable` |
| Errors | `NexusBTError` and the subclasses of 6.6 |
| Reserved (E18 when called) | `portfolio.optimize`, `risk.ledoit_wolf`, `ml.importance` (MDA, v1.x), `size.kelly` (v1.x [R4F-02]) [SC-22, R4-28]. v3.2's reserved `splits.*`, `labels.triple_barrier`, `exits.time_stop` and `risk.group_caps` were opened into v1 in v3.3 [R4-28] |

**Identifier** [header "Identifier name", RV-Q01]: public functions, output tables and documents use only `instrument_id` (no alias). Other names in external data are changed explicitly, as in `from_parquet(..., rename={"security_id": "instrument_id"})`.

### 3.2 Datasets and columns

Dataset columns are built from the snapshot's `dictionary/columns` and `dictionary/items` (TDS 4.4). `nexusbt stubs` rebuilds `src/nexusbt/_stubs/*.pyi`, and `nexusbt doctor` reports when the snapshot's columns change [R-04, R-22]. A typo is an `AttributeError` (error E7) that suggests three similar names (`difflib.get_close_matches`, cutoff 0.6).

`Price` (fixed columns, daily on the market axis):

| Column | Type | Unit | Value inside a window (as of the computation day t) [R-18, 11.4.3] |
|---|---|---|---|
| `open, high, low, close` | float64 | local currency/share | adjusted to t for splits, consolidations and stock dividends only: `raw[s]·C_split[t]/C_split[s]`. NaN in a package without `open/high/low` (4.5 F-01) |
| `close_tr` | float64 | local currency/share | adjusted to t for splits + cash dividends (total-return path): `raw[s]·C_total[t]/C_total[s]`. Dividends whose amount is not available at t's decision time are not included (5.3.4) |
| `close_unadjusted` | float64 | local currency/share | the raw price as it is |
| `volume` | float64 | shares | `vol[s]·Q[t]/Q[s]`, `Q[x] = Π_{e ≤ x} share_factor_e` (the resolver's cumulative share factor, 5.3.3a). For pure splits it equals `C_split[s]/C_split[t]` [RV-C03] |
| `volume_unadjusted` | float64 | shares | raw volume |
| `value_traded` | float64 | local currency | raw value traded (no adjustment needed) |
| `shares_out` | float64 | shares | point-in-time lookup of TDS `share_counts` (5.3.5a): the last count `n` available as of row s (its `as_of_date` = a), brought to t's basis by `n·Q[t]/Q[a]` [TDS-D9, TDS-Q4, RV-C03] |
| `market_cap` | float64 | local currency | `close_unadjusted[s] · shares_out_s(s)` (share count as of row s, adjustment-invariant). NaN without `share_counts` (4.5 F-08) |

- Price cells of halted or missing sessions (`obs_status in {"halted","missing"}`) are NaN inside the window. A session without trades (`"no_trade"`) takes `close` when present (the exchange reference price), otherwise NaN, with `volume = 0`.
- `Fund.<item>`: an item of `dictionary/items` (TDS 4.4). Methods `.latest` (Factor), `.age_days` (Factor: days of `session_date − period_end` at t), `.period_end` (Factor: epoch days), `.is_strict` (Filter: `strict_eligible`). Values are interval lookups of `fundamentals_state` (5.3.5) [R-63]. When the snapshot has no `fundamentals_state`, a graph that uses `Fund.*` is `CapabilityError` (E18, 4.5 F-06) when built.
- `Panel.<col>`: a column of `feature_panels` with `name = [panels] feature` (default `factor_pit_monthly`). `.latest`, `.age_days` (= `session_date(s) − as_of_date`). The frequency mark `"monthly"` is attached to results [Q10, TDS-D18].
- `Meta`: `market`, `currency`, `asset_class` (attributes that are fixed for an instrument and do not change over time), `venue_mic`, `category` (Classifier), `sector`, `industry` (Classifier, two-time-axis lookup of `classifications`), `is_financial` (Filter, scheme `is_financial`), and otherwise `Meta.<scheme>(level=)` for each (scheme, level) of `classifications`. **Changeable attributes** (`category`, `venue_mic`) are read on two time axes when `classifications` has a scheme of the same name; otherwise the current value of `instruments` is used, with E30 (`F-14 hindsight_attribute`: "current value used for history") and a manifest record when it reaches a decision input. `instruments.delisted_on`, `last_session` and `name` are not exposed through `Meta` (after-the-fact information) [RV-C08]. Which (scheme, level) `sector` and `industry` are is set by `nexusbt.toml [meta]` (default `"auto"` = what `alias_of` of `dictionary/columns` points to in the form `scheme@level`; when there is none, E16 on use) [chapter 12 OI-07]. v1's `Meta.country` and `Meta.exchange` remain as aliases of `Meta.market` and `Meta.venue_mic`.
- `Label.<col>`: a column of `label_panels` with `name = [panels] label` (default `label_monthly`) (`dictionary/columns.is_label = true`). Used only in `evaluate(target=…)`. Used anywhere else, it is `LabelLeakError` (error E2) when the graph is built [R-16]. When the three label times (`ts_label_start/end/available`, 5.8) are missing, they are built by the rules of 4.6.
- `Trad.<col>` [V31-30]: the columns of TDS `tradability_daily` as terms: `Trad.admin_status` (Classifier; the open enum `normal`, `administrative`, `caution`, `warning`, `liquidation_trading`, unknown values `other`), `Trad.halted` (Filter = `halted_full_day`), `Trad.limit_up_close`, `Trad.limit_down_close` (Filter), `Trad.price_limit_ratio` (Factor). Availability times are TDS `availability_by_column` as they are (prior information `session_open`, the day's outcome `session_close`; 4.6). Without the dataset, a graph that uses `Trad.*` is E18.
- `Market.series(instrument_id: str, column: str = "close") -> Factor` [V31-13]: a term that makes a bar column of one instrument of the snapshot (usually `asset_class = index`, for example `"IDX:KOSPI_TR"`) into a **market-level series** (one value per session). Windows, `shift` and element-wise operations work, and mixed with instrument terms it spreads as the same value to every instrument of that market. It is also used as `inputs=` of built-in factors and user window functions (for example relative strength against the index `Returns(126) - Returns(126, inputs=[Market.series("IDX:KOSPI_TR")])`, the regime filter `Market.series("IDX:KOSPI_TR").latest > SMA(200, inputs=[Market.series("IDX:KOSPI_TR")])`). Its availability rule is the same as `ready_m` (5.1.2) of that instrument's bars. When the series' market differs from the market of the sleeve that uses it, it becomes a term gathered by `row_m(d)` at the decision (5.3.2 (6)) and cannot be the input of a window or `shift` (E17). It does not enter the denominator of cross-section operations (the default domain of 3.3 as it is). A resulting Filter `&`-ed into `universe` becomes a market regime filter (for example "buy only while the index is above its 200-day line" — when false, that decision's universe is empty and the sleeve is in cash). E18 when the instrument is not in the snapshot.
- `Macro.series(series_id: str, *, vintage: Literal["as_of","first"] = "as_of") -> MacroTerm` [R4F-EV-01]: a macro or alternative series of TDS `series_observations` (5.21) as a **market-level term** (like `Market.series`, it spreads as the same value to every instrument of that market and does not enter the denominator of cross-section operations). The value at decision d = the value of the latest observation period (`obs_period_end`) among the rows with `ts_available ≤ decision_ts` — with `"as_of"`, the last vintage of that period known by the decision time (amendments included); with `"first"`, the first released vintage. Monthly CPI for a daily decision = the last released value (carried; previous observations are not interpolated). Methods: `.latest` (Factor), `.obs(k)` (the value of the k-th previous observation period, same vintage rule — for month-over-month comparisons), `.age_days` (calendar days since that value was released), `.changed()` (Filter: true only on sessions where a new release or amendment became known after the previous session), `.surprise` (`latest − consensus` only when the dataset has a `consensus` column; otherwise E18 when the graph is built). Windows, `shift` and comparisons work (as-of values on the session axis), and the unit is recorded from the `unit` column as it is. 5.3.12.
- `Events.<kind>` / `Events.of(event_type: str)` [R4F-EV-02]: terms over TDS event datasets. Built-in `kind`: `earnings` (`events.event_type = earnings.announcement`), `filing` (the filing receipt time of `fundamentals_events`), `dividend`, `split`, `merger` (`ts_announced` of `corporate_actions`); anything else is `Events.of("filing.kr_dart")`. Methods: `.days_since()` (sessions since the last event known at decision d, NaN when none), `.latest(field="value")`, `.count(window)` (the number of events whose `ts_event` lies in the last `window` sessions and that are known by the decision time), `.occurred(window=1)` (Filter), `.surprise` (`value − consensus`, only when both exist, otherwise E18). **Not there before availability**: an event is visible only after its `ts_available` (for corporate_actions `ts_announced`, the terms `ts_terms_available`). Events with a `ts_event` before the instrument's first session are ignored, with skips `event_before_listing`. Events with a `series_id` (macro releases) are market-level terms. 5.3.12.
- External data: `nx.dataset.from_parquet(path, *, known_on: str | None = None, shape: Literal["panel","events","series"] = "panel", key: Sequence[str] | None = None, ts_event: str = "ts_event", period_end: str = "obs_period_end", vintage: str | None = None, value: str = "value", units: Mapping[str,str] | None = None, rename: Mapping[str,str] | None = None, name: str | None = None) -> Dataset` [R4G-04]. `known_on` is optional by its signature, but left empty it is E3 (below). `rename` is applied first, and the other column arguments refer to the names after renaming. With `key=None`, the default per shape. **Required columns and checks per shape** (E47 at open when missing or of the wrong type): `panel` — key default `("instrument_id","date")`, the key columns + `known_on`, no duplicate keys; `events` — no key by default (a row = one event; when there is no `event_id` column, a hash of the row content), a `ts_event` column (a date or a UTC instant) + `known_on` + at least one of `instrument_id`, `issuer_id`, `series_id` (at least one not null in every row), `name` when there is no `event_type`; `series` — key default `("series_id", period_end, known_on)`, a `period_end` column (`date32`) + `known_on` + a `value` column (f64) + an optional `vintage` column; when there is no `series_id` column, every row is the one series `name`; no duplicate keys. For all three, rows whose `ts_event`/`period_end` is later than `known_on` are left only as W (a count; events released in advance can exist), not E47. The file sha256 and the resolved arguments go into the cache key of the nodes that read this dataset (5.3.9) [RV-C10]. `events` and `series_observations` (TDS 5.21) inside a TDS package are read by `Events` and `Macro` from v3.4 [R4F-EV-01, R4F-EV-02]. A `shape="events"` result is read with `Events.of(name)`, a `shape="series"` result with `Macro.series(name)` (or `series_id`); missing columns are E47 (layer data) [R4F-EV-04, R4G-04]. Without `known_on`, `PointInTimeError` (error E3). `known_on="date"` is allowed, with `"<name>: known_on=date"` written in the manifest `assumptions` [R-24]. When the `known_on` column is a date (`date32`), a value is taken as available at the next local session open (5.1.4); when it is a UTC instant (`timestamp[us, UTC]`, for example `known_on="ts_available"`), that instant is used as the availability time as it is.
- In-memory tables [R5-01, user decision 2026-10-28]: `nx.dataset.from_frame(obj, *, known_on, shape=..., key=..., ts_event=..., period_end=..., vintage=..., value=..., units=..., rename=..., name: str) -> Dataset` — the same arguments, the same per-shape checks (E47) and the same point-in-time rules (E3) as `from_parquet`. `obj` is **any table that gives an Arrow PyCapsule stream** (`__arrow_c_stream__`: a pyarrow Table, a Polars DataFrame, a DuckDB relation, a `DataFrame` of pandas ≥ 3.0 and so on (pandas 2.x is passed after converting with `pyarrow.Table.from_pandas`)), and the engine does not import that library (Arrow standard types are taken without copying; other types are converted to the canonical form). Reproducibility: **`value_sha256` = the value-hash rule of TDS 4.5** applied to this table as it is (schema metadata removed, chunks combined, dictionary encoding undone, strings = utf8, times = timestamp[us, UTC], rows sorted by the key columns and then the remaining columns, then the sha256 of the canonical IPC stream). `from_parquet` also uses **the same `value_sha256`** in the node key and keeps the file sha256 only as a physical stamp — so the same data has the same hash whatever the path (file, Polars, pandas) (G-105). This value goes into the node key and the manifest, and one copy is kept in the run folder as `inputs/<name>.parquet` (deterministic pyarrow write), which `rerun` reads. `name` is required (E16). A **`timestamp` column** without a tz is not taken as UTC but is E47 ("timestamp column {c} has no time zone"); a `date32` (date only) column is taken as it is and follows the date availability rule of 5.1.4 (the next local session open) [checked by Sol].

### 3.3 Terms and operators [R-03, Codex 11.4.4]

Common: every term is a value object, and `hash(term)` and `nx.describe(term)` work on it. Numeric results are float64; a Filter is **three-valued with a value and a validity mask** (true, false, unknown; unknown when an input is missing, unknown = false at the final use, 5.4.1) [V31-21]; a Classifier is int32 codes (missing −1) + a code table.

**Factor methods** (zipline names as they are; result type):

| Signature | Result | Meaning |
|---|---|---|
| `+ - * / ** -x`, `abs()`, `log()`, `log1p()`, `exp()`, `sqrt()` | Factor | element-wise operations. NaN propagates; division by 0 → NaN + a count of the diagnostic `DivisionByZero` [C7] |
| `< <= > >= == !=` (with a Factor or a scalar) | Filter | **unknown** when an input is NaN (false at the final use; still unknown after `~`) [V31-21] |
| `rank(method="ordinal", ascending=True, mask=None, groupby=None, across_markets=False)` | Factor | cross-sectional rank 1..n. `method ∈ {"ordinal","average","min","max","dense"}`. `ordinal` ties use the key of `[portfolio] tiebreak` (default the fixed-salt hash, 3.7; `"id"`, the zipline preset and comparisons use ascending `instrument_id`) [11.4.4, R3-12] |
| `zscore(mask=None, groupby=None, across_markets=False)` | Factor | (x−mean)/population standard deviation (ddof=0). Variance 0 → NaN |
| `demean(mask=None, groupby=None, across_markets=False)` | Factor | x − mean |
| `winsorize(min_percentile, max_percentile, mask=None, groupby=None, across_markets=False)` | Factor | clipped at the quantile bounds (linearly interpolated quantiles) |
| `top(N, mask=None, groupby=None, across_markets=False)` / `bottom(...)` | Filter | at most N by descending (ascending) score + the tie key (3.7) [R3-12] |
| `percentile_between(min_percentile, max_percentile, mask=None, across_markets=False)` | Filter | within percentiles [min, max] (both ends included) |
| `pct_rank(higher_is_better=True, mask=None, groupby=None, na="drop", across_markets=False)` | Factor | cross-sectional percentile 0~100 (100 = best; ties take the average rank). `na`: `"drop"` (missing is NaN, default), `"bottom"` (missing values are put in as a tie just below the worst value, then computed), `"middle"` (missing cells = 50, the rest from the valid cells only). Other than `drop`, it is an **explicit** fill operation that gives missing cells a value, so it agrees with INV-12 and is left in the manifest and `explain` [V31-25] |
| `quantiles(bins, mask=None, groupby=None, across_markets=False)`, `quartiles()`, `quintiles()`, `deciles()` | Classifier | tie-preserving quantiles (5.4.3) |
| `isnan()`, `notnan()`, `isfinite()`, `isnull()`, `notnull()` | Filter | |
| `fillna(value: float | Factor)` | Factor | the only explicit fill [INV-12] |
| `clip(lower=None, upper=None)` | Factor | |
| `shift(k: int)` | Factor | the value k sessions earlier on that instrument's market axis. With `k < 0`, `LookAheadError` (error E1) when the graph is built. `k = 0` is unchanged |
| `to(ccy: str)` | Factor | only for columns whose unit is a currency. Exchange rates available at the decision (5.6.9). `UnitError` (error E5) when the unit is not a currency |
| `if_else(...)` | – | a Filter method (below) |
| `downsample(freq)` | – | not in v1 → `CapabilityError` |

- `mask`: the computation domain of that term. Cells outside the mask give NaN (unknown for a Filter). It does not affect the computation of upstream inputs [11.4.4]. **Default domain** (the cells in a cross-section when there is no mask) = the cells of that market block = `asset_class = equity ∧ is_synthetic = false ∧ listed in that session`. Indices do not enter cross-sections and are read only through the benchmark path and the market-level series `Market.series` (3.2) [V31-13]. The engine does not secretly put the Strategy's `universe` into upstream terms as a mask; when a cross-section operation without a mask is on the Strategy's signal path, the static check gives the notice E34 [RV-Q06].
- `groupby`: a Classifier. Cells with a missing group (−1) are left out, and their number is counted as the diagnostic `UnknownGroup` [11.4.4].
- Cross-section operations are computed **separately per market** (market = an implicit group) [A-03]. With `across_markets=True`, the cross-sections of every market of one decision are gathered and computed together, and that term cannot be the input of a window or `shift` (`TermDomainError`, error E17). A cross-section operation with `across_markets=True` on a currency-unit term is `UnitError` (error E5) — after `.to(ccy)` or on a ratio it works [R-19].

**Filter methods**: `& | ~` (Kleene three-valued: false & unknown = false, true | unknown = true, `~`unknown = unknown, otherwise unknown [V31-21]; the results of `isnan()`, `notnan()` and `notnull()` are always true/false), `if_else(if_true: Factor, if_false: Factor) -> Factor` (NaN when the condition is unknown), `all(window: int) -> Filter` (true in all of the last window sessions; Kleene — false if even one is false, otherwise unknown if any is unknown), `any(window: int) -> Filter` (true if even one is true, otherwise unknown if any is unknown), `.as_factor() -> Factor` (true 1.0 / false 0.0 / unknown NaN), `fillna(value: bool) -> Filter` (unknown cells to the given value; the only explicit Filter fill, INV-12) [R3-13].

**Classifier methods**: `eq(value) -> Filter`, `element_of(values) -> Filter`, `isnull()`, `notnull()`, `startswith(prefix) -> Filter` (string code tables only). The result of `eq`, `element_of` and `startswith` on the missing code (−1) is **unknown** (`isnull` and `notnull` are always valid) [R3-13].

**User window functions** [R-05]:

```python
@nx.factor(window: int, inputs: Sequence[BoundColumn | Factor], *, mask: Filter | None = None,
           dtype: Literal["float64"] = "float64")
def f(close: np.ndarray, *, n: int = 21) -> np.ndarray: ...
# close.shape == (window, n_alive); last row = computation day t; returned shape == (n_alive,)
```

- The decorated name is a Factor. Binding parameters with keyword arguments, as in `f(n=63)`, makes a new Factor (the values go into the graph hash).
- Input windows hold values correctly adjusted to t (the table of 3.2). The adjustment shortcut is not used for user functions [C2].
- `@nx.filter` returns bool `(n_alive,)`, `@nx.classifier` int or str `(n_alive,)`.
- When a function indexes rows before `window`, numpy raises `IndexError`, and the engine turns it into `WindowError` (error E8) suggesting "`window=<needed value>`" (needed value = the absolute value of the negative index). Other user exceptions show the original exception and the user's file:line as they are [R-42].
- `nx.ops.rolling(x: Factor, window: int, min_periods: int | None = None).{mean,sum,std,min,max,median}()`: rolling operations that always look backward only (`std` with ddof=1; `min_periods` default = window) [design 3.5].
- `nx.ops.where(cond: Filter, a, b)`, `nx.ops.coalesce(*factors)`: explicit fills.
- `nx.ops.composite(terms: Mapping[Factor, float], *, higher_is_better: Mapping[Factor, bool] | None = None, na: Literal["drop","bottom","middle"] = "drop", mask=None, groupby=None) -> Factor` [V31-25]: turns each term into `pct_rank(na=…)`, takes the weighted sum (divided by the sum of weights) → `pct_rank` again (0~100). It can be nested (another `composite` in a term's place). The behaviour that corresponds to "NA Negative/Neutral" of the Portfolio123 ranking system is kept as a named, explicit operation. The number of instruments kept by filling missing values is `n_na_filled` of `coverage.parquet`.

### 3.4 Built-in factors and the conformance table [Codex 11.4.4, R-03]

Names that are the same as in zipline 3.2.1 follow zipline's missing-value rules and **input meaning**. zipline `USEquityPricing.close` is the value with the adjustment DB (splits + dividends) applied, so the default input of return-type factors is `Price.close_tr`; price-level factors (`SMA`, `EWMA`, `VWAP`, `RollingStd`) default to `Price.close` (split-adjusted only), to fit price-level comparisons and limit-price references [RV-I02, A-39 corrected]. When the rules below differ from zipline in the L1 comparison (8.1, with the same inputs), **the hand-calculated golden cases (T-25, `tests/golden/factors/`) decide**: when the hand calculation agrees with zipline, this table and the code are corrected (ADR); when zipline is wrong, it is written in `tests/parity/KNOWN_DIFFERENCES.md`. It is the same rule as 8.1's "zipline's known bugs are not taken as correct" (v3's sentence "zipline's behaviour is correct" conflicted with 8.1 and was corrected; when two engines have the same mistake, comparison alone cannot catch it — qlib#1228, nautilus#4333, Lean#9713) [V31-24]. `W` = the number of window rows, last row = t.

| Name (default input) | Formula | Missing | Minimum observations | ddof | Warm-up | Adjustment class |
|---|---|---|---|---|---|---|
| `Returns(W, inputs=[Price.close_tr])` | `x[-1]/x[0] − 1` | either end NaN → NaN | both ends | – | W−1 | homogeneous of degree 0 (ratio) |
| `DailyReturns()` = `Returns(2)` | | | | | 1 | degree 0 |
| `SimpleMovingAverage(W, inputs=[Price.close])`, alias `SMA` | `nanmean` | NaN ignored, all NaN → NaN | 1 | – | W−1 | homogeneous of degree 1 |
| `ExponentialWeightedMovingAverage(W, decay_rate, inputs)`, `EWMA`; `.from_span/.from_halflife/.from_center_of_mass` | `average(x, weights=decay^(W−1−i))` | any NaN → NaN | W | – | W−1 | degree 1 |
| `AverageDollarVolume(W)` | `nansum(close·volume)/W` (zipline's formula) | NaN counted as 0 | 0 | – | W−1 | invariant (value = price × volume) |
| `AverageTradedValue(W, ccy=None)` (NexusBT) | `nanmean(value_traded)`; `.to(ccy)` when `ccy` | NaN ignored | 1 | – | W−1 | invariant |
| `AnnualizedVolatility(W=252, annualization_factor=252, inputs=[Price.close_tr])` | `nanstd(DailyReturns window, ddof=0)·√a` | NaN ignored | 1 | 0 | W | degree 0 |
| `RollingStd(W, inputs)` (NexusBT) | `nanstd(x, ddof=1)` | NaN ignored | 2 | 1 | W−1 | degree 1 |
| `VWAP(W)` | `nansum(close·volume)/nansum(volume)` | NaN ignored | 1 | – | W−1 | degree 1 |
| `RSI(W=15, inputs=[Price.close_tr])` | `d=diff(x)`; `up=nanmean(clip(d,0,∞))`; `dn=abs(nanmean(clip(d,−∞,0)))`; `100−100/(1+up/dn)` | as zipline | | | W−1 | degree 0 |
| `MaxDrawdown(W, inputs=[Price.close_tr])` | `max((cummax(x)−x)/cummax(x))` | NaN ignored | 1 | – | W−1 | degree 0 |
| `Latest` (= `col.latest`) | `x[-1]` | | | | 0 | the column table |

Adjustment classes (5.3.3): homogeneous of degree 0 = invariant under multiplication by a per-instrument scalar, degree 1 = scales by the scalar, invariant = the raw value as it is. The class is declared when the kernel is registered and proven by the P-ADJ property test (random scalars).

Every built-in factor is a registered kernel and follows the numeric rules of 5.3.10 (summation order, BLAS and `fastmath` forbidden, the transcendental-function class). The `EWMA` weights `decay^k` are computed once outside the kernel and passed as a constant array; kernels that only divide, such as `Returns` and `RSI`, are of the arithmetic class, and kernels that use logarithms (`log()`, `log1p()`, spread estimates) are of the transcendental class [RV-C11]. The table's `nanmean`, `nanstd` and `nansum` are defined as "the sum of the non-NaN values added from the left in ascending row order" (not numpy's pairwise summation order) [SC-03]. Every built-in factor is a function only of the data inside its own window (no infinite recursion; `EWMA` is a finite-window weighted average) — which is why start-date invariance (INV-14) holds [SC-04].

### 3.5 Pipeline and `run_pipeline` [11.4.4, 11.6]

```python
nx.Pipeline(columns: Mapping[str, Term], screen: Filter | None = None)   # the default cross-section domain is in 3.3
nx.run_pipeline(pipeline: Pipeline, *, start: str | date, end: str | date, freq: Literal["daily","weekly","monthly"] = "daily",
                markets: Sequence[str] | None = None, edition: str | None = None, snapshot: str | None = None,   # markets: keys of the snapshot's markets
                save: bool = False) -> PipelineResult
```

- The result `PipelineResult.table`: an Arrow table `(market: str, session_date: date32, decision_ts: timestamp[us,UTC], instrument_id: str, <columns…>)`, sorted by `(session_date, market, instrument_id)`. Rows where `screen` is false or unknown are not there (unknown = false) [R3-13]. `.to_polars()`, `.to_pandas()` (optional dependency).
- When `start` is not a session, it is moved per market to the next session and `end` to the previous session, with a notice (error E9) [design 3.5 error E9].
- The decision grid of `freq="daily"` = every session of each market (market_local). With several markets, the per-market rows are stacked.

### 3.6 Universe [design 3.6, R-58]

```python
nx.universe(spec: str | Sequence[str] = "<toml defaults.universe>", *, investable: bool = True,
            exclude_microcap: bool | None = None, survivorship_ok: str | None = None,
            exclude: Sequence[str] = ()) -> Filter                      # [V31-30]
nx.universe.index_members(universe_id: str) -> Filter      # "index:KOSPI200" or the short "KOSPI200" (→ "index:" prefix)
```

- `spec`: one key of the snapshot's `markets` (`"KR"`), several joined by `+` (`"KR+US"`), `"all"`, or a list of `instrument_id`. A market name not in the snapshot is E16 (suggesting the list of markets present); a market without a rules pack is E18 (4.4) [RV-I08]. For a list, a survivorship-bias check (error E4 warning): a warning when every instrument of the list is listed in the snapshot's last session and the run period is longer than 3 years. With `survivorship_ok="reason"`, the reason is written in the manifest instead of the warning.
- `investable=True`: `is_eligible` of the TDS `eligibility_daily` rows with `rule_id = [universe] eligibility_rule` (default `investable-v1`). The row used is **that session's one row**, and its `ts_available <= cutoff(s)` must hold. When that session's row is missing or not yet available, **false** (no carry-over; even if true yesterday, false when there is no row today) [RV-C09]. Without the dataset, the `is_investable` column of `feature_panels` (the last available value; panels are periodic data, so "the last available value" is the definition) is used instead, `universe_source = "feature_panels"` is recorded and E30 is raised (4.5 F-07). Without both, `investable=True` is `CapabilityError` (E18, fix `investable=False` — the `nexusbt new strategy` template and the English quick start keep this line visible) [chapter 12 OI-01, RV-I03].
- **Exclusion reasons reported** [SC-23]: per decision and market, the universe size, the number excluded per `eligibility_daily.reason`, the number removed by `exclude_microcap`, and the number dropped because the signal is not finite are left in `coverage.parquet` (5.9.1). A liquidity threshold is not hidden in the default universe (examples and the `nexusbt new strategy` template keep a line such as `AverageTradedValue(63, ccy="USD") > 1e6` visible).
- Listing existence (`listed_on <= session <= last_session`) always applies.
- `exclude` (default `()` = excludes nothing; the same principle as the decision to include micro-caps by default) [V31-30]: values accept only TDS enum names — `admin_status` values (`administrative`, `caution`, `warning`, `liquidation_trading`; that session's `Trad.admin_status`, available at `session_open`) and `category` values (`preferred`, `spac`, `reit`, `etf`, `fund`, `warrant`, `right`, …; `Meta.category`, the two-time-axis rule of 3.2). An unknown name is E16 (with the list of allowed names). It shows as a leaf Filter in step 1 of `explain`, and the excluded counts go per reason into `n_excluded_by_reason` of `coverage.parquet`. `[universe] exclude` can give a default.
- `exclude_microcap` (default = `nexusbt.toml [universe] exclude_microcap`, default false): when true, removes the instruments in the bottom `microcap_pct` (default 0.20) of `market_cap` among that session's investable instruments per market. The boundary value is a `percentile` (linear interpolation), and values equal to the boundary stay [Q17, R-58].
- `index_members`: reads the rows of that `universe_id` in TDS `universe_membership` by the rectangular two-time-axis lookup (5.3.6). When the dataset or that `universe_id` is missing, `CapabilityError` (E18, with the list of `universe_id` present) + the note "a fixed list has survivorship bias (E4)" [TDS-D16, RV-I08].

### 3.7 Strategy parts [R-07, R-08, design 3.3]

```python
nx.Strategy(*, universe: Filter, signal: Factor, rebalance: Schedule, portfolio: PortfolioRule,
            sizing: Sizer | Sequence[Sizer] | None = None,                                   # money-management slot [R4-02]
            risk: RiskRule | Sequence[RiskRule] | None = None,                               # risk-management list slot [R4-04]
            costs: CostModel | None = None, execution: ExecutionRule | None = None,
            exits: Sequence[ExitRule] = (), hypothesis: str | None = None, name: str | None = None)
```

- A value object; `strategy.graph_hash` (a structural hash of the term graph + the parameters of the parts) [R-07, R-12]. On disk it is kept only as source (5.9.3), never stored as a serialised object (2.6). `name` default = the file name of the module that defines it.
- `sizing` (default `None` = the shorthand `weight=` and `max_weight=` of the construction rule, below): the money-management slot (5.5.1a). For a list, the first is the base sizer and the rest are modifiers (`vol_target`, `cash_floor`), in the order written [R4-02].
- `risk` (default `None` = no rules = `nx.risk.none()`): the risk-management list slot (5.5.2). One rule or a list, applied one by one **in the order written**; the order goes into `graph_hash` and the manifest [R4-04, SC-01, OQ-2].
- `strategy.replace(**slots) -> Strategy` [R4-11]: a new value object with one or more slots replaced (the other slots and the name unchanged, with `~{replaced slots}` after the name). It is the basic tool for comparing techniques (`nx.compare`, 3.8). For example: `base.replace(sizing=nx.size.erc())`, `base.replace(risk=[nx.risk.drawdown_brake()])`.
- A callback that reads holdings (`on_rebalance`) is not in v1 [C6, A-10].
- The slots are read in the same order as bt and LEAN: `rebalance` (when) → `universe`, `signal` (what) → `portfolio` (which, on which side) → `sizing` (how much) → `risk` (reduce) → `execution`, `exits`, `costs` (how). A stage function takes only the previous stage's output (a table) and the information at the decision; the account state only in risk rules with `reads_account=True` (read-only, 5.5.2a) and in the execution stage [blueprint E-1, R4-01, R4-04].

**The block contract of the nine slots** [R4-01]. The user plugs blocks into slots. Trying to read anything outside the table's "may read" is an error before the run (account access is E41; future slots do not exist by construction).

| Slot (argument) | Input → output | May read | Built-in blocks | User blocks |
|---|---|---|---|---|
| schedule (`rebalance=`) | calendar → list of decision sessions (for `on_event`, + the target instruments per decision, + liquidation-only decisions at the end of life [R4G-03]) | the schedule calendar (5.1.3); for `on_event`, the events and releases available by the decision time | `monthly`, `weekly`, `quarterly`, `annually`, `daily`, `every`, `on_event` [R4F-EV-03] | none (v1). Conditional decisions through `risk.regime`, Filters, `on_event` |
| universe (`universe=`) | Pipeline → Filter (decision × instrument, true/false/unknown) | snapshot data up to the decision (5.1.2) | `nx.universe`, `index_members`, `Trad.*`, operators | `@nx.filter(window=)` |
| signal (`signal=`) | Pipeline → Factor score | the same | the 12 built-in factors, `ops.*`, `ops.composite`, `ml.factor`, `Macro.series` and `Events.*` terms [R4F-EV-01, R4F-EV-02] | `@nx.factor(window=)`, `nx.ml.factor(...)` (5.3.11) |
| construction (`portfolio=`) | score, universe, previous canonical target state → selection table (id, side, rank) | term values at the decision, the previous decision's `TargetState` (read-only) | `top`, `bottom`, `long_short` | `@nx.portfolio` (3.8) |
| sizing (`sizing=`) | selection table + market window → signed weights, `Σ|w| ≤ 1` per side | only the market window at the decision (prices, value traded, market cap), **no account** | `size.equal`, `value`, `inverse_vol`, `score`, `erc`, `vol_parity`, `stop_risk`, modifiers `vol_target`, `cash_floor` (5.5.1a; `kelly` v1.x [R4F-02]) | `@nx.sizer` (3.8) |
| risk (`risk=[…]`) | weights → weights × m, `m ∈ [0, 1]` (toward zero only) | market information; with `reads_account=True`, the account (up to the decision, read-only) | `risk.group_caps`, `regime`, `vol_cap`, `liquidity_cap`, `drawdown_brake`, `portfolio_stop`, `no_reentry`, fitting to the exposure caps (5.5.2, 5.5.2a) | `@nx.risk_rule(reads_account=…)` (3.8) |
| execution (`execution=`) | final weights + account → order intents | the account (engine) | `execution.market`, `execution.limit` | none (v1; fill semantics are an accounting contract and are not swappable) |
| exits (`exits=[…]`) | fill → a non-expiring exit order per holding | the holding's `avg_cost`, entry session, closes after entry | `stop_loss`, `stop_limit_loss`, `take_profit`, `trailing_stop`, `time_stop` | none (v1) |
| costs (`costs=`) | fill → cost components | the fill, ADV at the decision, user tables | `provisional`, `realistic`, `bps`, `per_share`, `none` | user tables (`provisional(table=)`, `realistic(table=)`) |

**Four block promises** [R4-01]: (1) **No look into the future** — the end of every block's input window is the decision time (INV-01). (2) **Same input, same output** — no randomness or hidden state inside a block; a risk rule that needs state passes it only through the `risk_state` table the engine stores (5.5.2a). (3) **The account from the risk slot on, read-only** — the sizing slot does not take the account, and the risk slot takes a read-only view only with `reads_account=True`. (4) **Effects are visible** — per slot, the change in weight sums, the number of instruments and the reasons go into `waterfall.parquet` and `targets.reason`, and skipped instruments and blocks into `skips.parquet` (6.6 "no silent failures").

**Schedules** (decision dates; the reference calendar is 5.1.3). Every schedule is anchored to the calendar and does not depend on the run's start date (INV-14):

| Function | Decision sessions |
|---|---|
| `nx.monthly(day: int = -1)` | the `day`-th session of the month (from 1), counted from the end when negative. The last session when larger than the number of sessions in the month |
| `nx.weekly(weekday: int = -1)` | the `weekday`-th session of the ISO week (same rule) |
| `nx.quarterly(day: int = -1)` | `monthly(day)` of March, June, September and December |
| `nx.annually(month: int = 12, day: int = -1)` | |
| `nx.daily()` | every session |
| `nx.on_event(trigger, *, delay: int = 0, universe_scope: Literal["event_instruments","all"] \| None = None, hold: Optional[int] = None)` [R4F-EV-03, R4G-01] | `trigger` = `Events.<kind>` (instrument events) or `Macro.series(...).changed()` and events with only a `series_id` (market events). For each event, the trigger session = the first session of the schedule calendar with `decision_ts ≥ ts_available` + `delay` sessions (calendar-anchored, independent of the run's start date — INV-14). The decision targets of that session: `"event_instruments"` = only the instruments triggered in that session (incremental decisions of 5.3.12), `"all"` = everything, like an ordinary schedule. `None` (default) = `"event_instruments"` for instrument events and **`"all"` for market events** (targets = the whole strategy universe). The reason is an **assumption**: a market-level event (a macro indicator release and the like) is not tied to particular instruments, so the engine assumes its effect reaches the whole universe and makes the whole universe the decision target; a user who thinks the effect reaches only some instruments narrows it with the universe or filters. This assumption is left in the manifest `assumptions` ("market-level trigger {t}: assumed to affect the whole universe") and on the report's header line [R4G-MG-01]; writing `"event_instruments"` explicitly for a market event is E16 before the run ("market-level trigger {t} has no instruments; use universe_scope='all' or leave it unset") [R4G-01]. End-of-life sessions enter the decision grid as liquidation-only decisions (5.3.12) [R4G-03]. Can be combined with other schedules by `|` (`nx.monthly() \| nx.on_event(...)`) |
| `nx.every(n: int, offset: int = 0)` | the sessions whose absolute session number `session_ord` on the schedule calendar (the one in TDS `calendar_sessions` when present, otherwise the number the engine builds with the calendar's first session = 0) satisfies `(session_ord − offset) mod n == 0`. Independent of the run's start date [RV-C11] |

**Parameters**: `nx.param(default: T, *, grid: Sequence[T] | None = None, name: str | None = None) -> Param[T]`. Usable wherever an integer or a float goes (window lengths, `top(n)`, `max_weight`, ratios). Without a name, the name is taken from the global variable of the module that built the strategy (`ConfigError` when two names point to the same Param). Values are set by `params={"n": 20}`, the CLI `--set n=20` or `nx.sweep`. The resolved values are left in the manifest `params` [R-08].

**Portfolio** [C6, 11.4.4]:

```python
nx.top(n: int | Param, *, per: Classifier | None = None,
       weight: Literal["equal","value","inverse_vol"] = "equal",
       max_weight: float | None = None, vol_lookback: int = 252, redistribute: bool = False,
       hold: int | Param | None = None, on_missing: Literal["drop","hold"] = "drop",   # [V31-17]
       tiebreak: Literal["hash","id"] = "<toml [portfolio] tiebreak>") -> PortfolioRule   # [V31-29]
nx.bottom(n, **same arguments) -> PortfolioRule          # short side: n by ascending score, negative weights [V31-LS-02]
nx.long_short(long: PortfolioRule, short: PortfolioRule, *, long_weight: float = 0.5, short_weight: float = 0.5,
                max_gross: float | None = None, max_net: tuple[float, float] | None = None) -> PortfolioRule   # [V31-LS-02]
```

- `hold` (hold band, default `None` = off): with `hold=m` (m ≥ n), an instrument that was in the previous decision's canonical target stays while it is within rank m. The norm is 5.5.3 (the target-state recursion). **Until T7.1 (the last ticket of M6) is in, a `hold` other than `None` is `CapabilityError` (E18, "available after ticket T7.1"); supported in the v1 release** [SC-02, OQ-1].

- **Short selling and signs** [V31-LS-02]: `top` is the long side (weights ≥ 0), `bottom` the short side (the same rule applied by ascending score, then the weights multiplied by −1 — the mirror image of the long side). `long_short(long, short)` builds the two sides separately (sum ≤ 1 per side, the remainder under the `max_weight` cap in cash) and then **only multiplies** the long-side weights by `long_weight` and the short-side weights by `short_weight` — it does not normalise again, so `top(1, max_weight=0.1)` + `long_weight = 0.5` is 0.05 (v3.1's "the long side sum is fitted to `long_weight`" undid the cap and was removed). When the same instrument is on both sides, only the long side keeps it and it is removed from the short side (`reason = conflict_long_kept`), and the remaining shorts are not refitted (that share is cash) [R3-08]. **Feasible region** [R3-08]: longs have no margin loan and one short sale reduces `buying_power` by `c·|q|·P` (5.6.7, c = `collateral_ratio`), so in the cash account (default) a book that exceeds `long_weight + c·short_weight ≤ 1` per sleeve (long only = L 1·S 0, short only `bottom` = L 0·S 1) is `ConfigError` before the run (E16, "long-short book needs margin: long_weight + collateral_ratio × short_weight = {x} > 1"; 130/30 = 1.3 + 0.5 × 0.3 = 1.45). The risk stage only shrinks toward zero, so targets during the run do not leave this region. The assumption sentence is "longs are fully cash-funded; no margin loan; short proceeds are restricted as collateral". With `[account] type = "margin"`, the feasible region is 5.6.7a (`L + S ≤ min(max_gross, 1/initial_margin)`) [R4G-MG-02]. With `[shorting] enabled = false` (default), using `bottom`, `long_short` or a rule that makes negative weights is `ConfigError` before the run (E16, "short targets need [shorting] enabled = true"). When gross exposure `Σ|w|` exceeds `max_gross` (default = `[shorting] max_gross`, 1.0) or net exposure `Σw` leaves `max_net` (default `[shorting] max_net`, the closed interval `[−1, 1]`; it must contain 0, otherwise E16 [R3-07]), the risk stage scales proportionally toward zero (5.5.2; never up). Leverage goes only up to the gross exposure cap the user sets.
- Selection: within each sleeve, at most n of the instruments whose `signal` is finite and whose `universe` is true, by descending score (ascending on the short side) + the tie-break key. The tie-break key [V31-29]: `tiebreak = "hash"` (default) = ascending (the first 8 bytes of `sha256("nexusbt-tiebreak-v1" ‖ 0x1F ‖ instrument_id)` as a big-endian unsigned integer, `instrument_id`) — a fixed order per instrument, independent of date, clock, graph, sleeve and snapshot (v3.1's `decision_id` salt reshuffled the order at every decision and made false turnover in strategies with sparse scores) [R3-12], and independent of instrument numbers, so there is no hidden tilt that "always picks the companies with small (old) numbers"; `"id"` = ascending `instrument_id` (the zipline preset, 5.6.15). The number of instruments split by a tie at the cutoff is `n_tied_at_cutoff` of `coverage.parquet`. (The Factor methods `.top()`, `.bottom()` and `.rank("ordinal")` follow the same `[portfolio] tiebreak` — Pipeline selection and portfolio selection pick the same instruments; the zipline comparison (8.1 L1-d) runs with `tiebreak = "id"` [R3-12].) With `per`, n per group (`per=Meta.market` is the same as the sleeve, so it has no effect + a notice).
- **Shorthand** [R4-02]: `weight=`, `max_weight=`, `vol_lookback=` and `redistribute=` are shorthand for `sizing=nx.size.<weight>(max_weight=…, lookback=…, redistribute=…)`. Giving `sizing=` together with any of these four at a non-default value is E16 before the run ("weight given twice: top(weight=...) and sizing=..."). The definitions in the two lines below are exactly the definitions of `size.equal`, `value` and `inverse_vol`.
- Weights before weighting `u_i`: equal = 1, value = `market_cap` at the decision (point-in-time lookup of `share_counts` × raw close; when missing, removed from the selection with E30), inverse_vol = 1/`AnnualizedVolatility(vol_lookback)` (removed from the selection when NaN or 0).
- `on_missing` (meaningful only together with the hold band `hold`): 5.5.3 [V31-17].
- `w_i = u_i / Σu`. With `max_weight`, `w_i ← min(w_i, max_weight)` and the remaining share is cash (`redistribute=False`; not filled from lower ranks). With `redistribute=True`, it is redistributed repeatedly and proportionally to the instruments not at the cap (at most 50 rounds, convergence 1e-12).
- Result: long only, sum ≤ 1 (within the sleeve) [11.4.1]; long–short, `Σ|w| ≤ max_gross`, `Σw ∈ max_net` [V31-LS-02].

**Execution rules** [R-56, 9.0 orders]:

```python
nx.execution.market(at: Literal["open","close"] = "open", *, max_participation: float | None = None,
                    tif: Literal["gtc","day"] = "gtc", max_age_sessions: int | None = None,
                    min_trade_value: float | None = None, min_trade_weight: float | None = None,     # [V31-06]
                    rebalance_band: float | None = None, band_mode: Literal["edge","target"] | None = None) -> ExecutionRule
nx.execution.limit(offset_bps: float = 0.0, *, ref: Literal["decision_close"] = "decision_close",
                   tif: Literal["day","gtc"] = "day", max_participation: float | None = None,
                   max_age_sessions: int | None = None, min_trade_value=None, min_trade_weight=None,
                   rebalance_band=None, band_mode=None) -> ExecutionRule
```

- Default = `market(at="open")`: fills at the open of the first session after the decision (design Q5). `at="close"` is the close of the first session after the decision (used by the zipline preset). There is no "fill at the same close" [11.4.1, A-12].
- `limit`: the buy limit = ref·(1 + offset_bps/1e4) and the sell limit = ref·(1 − offset_bps/1e4) are snapped to that market's price grid on the **conservative side** (buy down, sell up) (5.6.4a). v3's "not rounded to the tick" was removed (fills at prices that do not exist in the Korean tick grid made results slightly better and always broke the comparison with real trades; zipline#2211, freqtrade#13661) [V31-05].
- `min_trade_value`, `min_trade_weight`, `rebalance_band`, `band_mode` (default = toml `[execution]`, all off): filtering out small rebalancing orders (5.6.7) [V31-06].
- `max_participation` default = toml `[execution] max_participation` (0.05), `max_age_sessions` default 20 [11.4.2].

**Exit rules** (non-expiring sell orders attached to each holding; the exit orders of one holding are OCO with each other; life cycle in 5.6.2a) [R-56, Q21 → A-11, RV-C05]:

| Function | Order (long holding / short holding [V31-LS-06]) | Price (long / short) |
|---|---|---|
| `nx.exits.stop_loss(pct: float)` | sell stop / cover (buy) stop | `avg_cost·(1 − pct)` / `avg_cost·(1 + pct)` |
| `nx.exits.stop_limit_loss(stop_pct: float, limit_pct: float)` | sell stop-limit / buy stop-limit | long: stop `avg_cost·(1−stop_pct)`, limit `avg_cost·(1−limit_pct)`; short: stop `avg_cost·(1+stop_pct)`, limit `avg_cost·(1+limit_pct)`; `limit_pct >= stop_pct` |
| `nx.exits.take_profit(pct: float)` | sell limit / buy limit | `avg_cost·(1 + pct)` / `avg_cost·(1 − pct)` |
| `nx.exits.trailing_stop(pct: float)` | sell stop / buy stop | `max(closes after entry)·(1 − pct)` / `min(closes after entry)·(1 + pct)`, recomputed after every session close |
| `nx.exits.time_stop(sessions: int)` [R4-10] | market sell / market cover (buy). Created after the close of the session in which the number of holding sessions (first entry fill session = 1, market calendar sessions, halt days included [V31-52]) reaches `sessions`, and placed in the next session's open stage; when halted, carried over as in 5.6.5 | no price (open); OCO with the stop loss and take profit. When the holding grows or shrinks, the entry session stays the first entry (0 → ≠ 0); when the sign changes, the count starts again |

- A stop loss + take profit + `time_stop` tied as the OCO of one holding is the triple barrier. The label `nx.labels.triple_barrier` (v1, 5.8) is built by calling **the same decision function** (5.6.4) and the same session count [SC-20, blueprint E-10, R4-10, R4-24].

- Creation, quantity and price basis are in 5.6.2a: created in the same stage right after the entry fill event, quantity = the sellable quantity of the holding at that moment, price basis = the `avg_cost` at that moment; refitted immediately at every event that changes the holding. No expiry (`max_age_sessions = None`); `CANCELLED(position_closed)` when the holding becomes 0. `avg_cost` is the weighted average purchase price on the raw-price basis (a float before minor-unit booking; quantity and price adjusted at splits). (v2's wording "the sellable quantity at the start of that session" contradicted the same-bar stop G-08 and was removed.)
- Exit prices are computed and then snapped to the price grid on the conservative side (a long stop-loss sell stop down, a short stop-loss buy stop up, a take-profit sell limit up and buy limit down; 5.6.4a) [V31-05]. The exit orders of a short holding mirror those of a long (price basis = the average short-sale price `avg_cost`), quantity = the size of the short quantity at that moment [V31-LS-06]. They are created right after the short entry (0 → negative) fill, and the trailing reference is `low_water_close = min(closes after entry)` [R3-10].
- Daily-bar assumption sentence (manifest `assumptions`): "stops fill at the stop price unless the open gaps through it; no further slippage past the stop is modeled".

**Cost models** [R-25, R-61, Q6]:

| Function | Meaning |
|---|---|
| `nx.costs.provisional(table: str | None = None)` | default. Fixed bp per market (`provisional_bps` of the market rules pack, overridden by toml `[costs.provisional_bps] <MARKET>`), "provisional costs" in the report. Given `table` (or toml `[costs] provisional_table`), it uses the row of the user's **period and liquidity-band table** (schema of 4.7: `market, side, valid_from, valid_to, adv_from, adv_to, bps, source`) for that fill date and that instrument's ADV at the decision (a currency amount, t−20..t−1). The default is no table = fixed bp (the user decision "commissions and taxes are user settings", R-61 as it is); "cost by liquidity tier" on the report's cost line [V31-27] |
| `nx.costs.realistic(table: str = "default", *, impact_y: float = 0.5, impact_a2: float = 0.5, impact_a3: float = 1.0)` | commission and tax tables by period and country + a ½-spread estimate + the impact `Y·σ^a3·(q/ADV)^a2` (default = square-root impact, 5.6.8) [SC-11]. When the table coverage check fails, it is blocked with `CostTableError` (error E23), suggesting `provisional()` |
| `nx.costs.bps(buy: float, sell: float, *, by_market: Mapping[str, tuple[float, float]] | None = None)` | fixed bp. Overridden by market key (the snapshot's `markets`), as in `by_market={"KR": (5, 25)}` [RV-I08] |
| `nx.costs.per_share(cost: float, min_trade_cost: float = 0.0)` | commission per share (local currency) |
| `nx.costs.none()` | 0 |

### 3.8 Function signatures and returns

Common keywords ("common" in the table below): `snapshot: str | None = None` (default toml), `edition: Literal["strict","compare"] | None = None`, `segment: str | None = None` (default toml `[split] default_segment`), `start`, `end` (only to narrow further inside the segment; `ConfigError` outside it), `study: str | None = None`, `save: bool = True`. v3.2's reserved argument `splits=` was removed: splitting is a value of `backtest(method=…)` (6.3a; `evaluate` is linear only) [SC-21, R4-20].

```python
nx.evaluate(term: Factor | Mapping[str, Factor], *, target: str | BoundColumn = "fwd_return",   # "fwd_return" (economic label) | "fwd_return_adj" | Label.*
            freq: Literal["monthly","weekly","daily"] = "monthly", horizons: Sequence[int | Literal["next"]] = ("next",),
            quantiles: int = 5, universe: Filter | None = None,
            by: Sequence[Literal["market","year","segment"]] = ("market",),
            delisting: Literal["observed_then_policy","observed_only","lo","hi"] | None = None, **common) -> FactorReport

nx.backtest(strategy: Strategy, *, capital: float | None = None, base_ccy: str | None = None,   # ISO 4217; the snapshot must have exchange rates into that currency
            clock: str | None = None,                                                     # "<MARKET>_close" | "market_local"
            sleeves: Mapping[str, float] | None = None, costs: CostModel | None = None,
            delisting: str | None = None, params: Mapping[str, Any] | None = None,
            preset: Literal["realistic","zipline"] = "realistic",
            offsets: int | None = None,                                                   # rebalance-date luck [V31-26]
            scenarios: bool | Sequence[Literal["gross","cost0x","cost2x","delist_lo","delist_hi","capacity"]] = True,   # gross = cost0x (one and the same replay)
            save_signal: bool = False,
            method: Literal["linear","walk_forward","cpcv","cscv"] | Split = "linear",      # validation method, 6.3a [R4-20]
            grid: Mapping[str, Sequence[Any]] | None = None,                                # candidates chosen per fold (method ≠ linear)
            select: Literal["net_sharpe","cagr","calmar"] = "net_sharpe",
            preview: bool = False, **common) -> Run                                          # [R4-12]

nx.screen(obj: Strategy | Factor | Pipeline, *, asof: str | date | None = None, top: int | None = None,
          params: Mapping[str, Any] | None = None, anchor: str | date | None = None,
          show: Literal["selected","all","held+near"] = "selected", near: int = 10,
          book: Book | str | None = None,
          account: Literal["auto","none","book","backtest"] = "auto", **common) -> Screen   # [V31-28, R3-21, R4-08]

nx.live(strategy: Strategy, *, book: Book | str, asof: str | date | None = None,
        params: Mapping[str, Any] | None = None, snapshot: str | None = None) -> Orders
nx.fill(book: Book | str, orders: Orders | None = None, *, at: Literal["next_open"] = "next_open",
        snapshot: str | None = None) -> BookUpdate
nx.reconcile(book: Book | str, *, restate: bool = False, snapshot: str | None = None) -> ReconcileReport
                                   # default: replay with the snapshots the ledger recorded. restate=True: restatement comparison with snapshot (default latest)

nx.sweep(strategy: Strategy, *, grid: Mapping[str, Sequence[Any]] | None = None,
         pbo_blocks: int = 16, **backtest_kwargs) -> SweepResult
nx.compare(*items: str | Run | Strategy, metrics: Sequence[str] | None = None, **backtest_kwargs) -> Comparison   # variant table [R4-11]
nx.splits.holdout() | nx.splits.walk_forward(train="5y", test="1y", step="1y", anchored=False, embargo=0)
    | nx.splits.cpcv(n_groups=6, k_test=2, embargo=5) | nx.splits.cscv(blocks=16) -> Split   # 6.3a [R4-19]
nx.ml.factor(model, features: Sequence[Factor], label: str | LabelTerm | None = None, *, train: Window | None = None, refit: Schedule | None = None,
             embargo: int = 0, sample_weight: None = None, cross_section: Literal["pooled"] = "pooled",
             name: str | None = None) -> Factor                                               # 5.3.11 [R4-23]
nx.ml.rolling(length: str | int) | nx.ml.expanding(min_length: str | int) -> Window     # training window (not a split) [R4F-31]
nx.labels.triple_barrier(*, take_profit: float, stop_loss: float, max_sessions: int,
                         entry: Literal["next_open"] = "next_open") -> LabelTerm               # 5.8 [R4-24]
@nx.portfolio(side: Literal["long","short"] = "long", window: int = 1, inputs: Sequence[Term] = ())   # [R4-07]; "both" is E16 [R4F-17]
def f(ctx: nx.PortfolioContext) -> Mapping[str, int]: ...      # instrument_id → +1 (long) / −1 (short); rank = score order
@nx.sizer(window: int = 252, inputs: Sequence[Term] = (nx.Price.close,), returns: Literal["units","weights"] = "units")
def f(ctx: nx.SizingContext) -> Mapping[str, float]: ...        # finite u ≥ 0 → the engine normalises per side; for "weights", same sign as the side and Σ|w| ≤ 1 per side, otherwise E41 [R4F-38]
@nx.risk_rule(reads_account: bool = False, window: int = 1, inputs: Sequence[Term] = ())
def f(ctx: nx.RiskContext, w: nx.TargetView, state: Mapping[str, Scalar]) -> nx.RiskDecision: ...
                                                                # RiskDecision(mult=float | Mapping[id, float], state={...}, reason="...")
nx.explain(obj: Term | Strategy, instrument_id: str, date: str | date, *, snapshot=None, edition=None,
           params: Mapping[str, Any] | None = None) -> Explanation | DecisionExplanation
nx.check(obj: Term | Pipeline | Strategy, *, probes: int = 0, seed: int = 0, start_probe: bool = False,
         verbose: bool = False) -> CheckReport
nx.describe(obj: object | None = None) -> Description          # None: the list of datasets
nx.runs(*, study: str | None = None, kind: str | None = None, limit: int = 50) -> RunTable
nx.rerun(run_id: str, *, new_snapshot: bool = False, trust: bool = False) -> Run
nx.book(spec: str) -> Book                                       # "paper:<name>" | "manual:<name>" [V31-18]
nx.override(book: Book | str, instrument_id: str, kind: Literal["no_trade","reduce_only","close"], *,
              from_: str | date | None = None, until: str | date | None = None, note: str = "") -> BookUpdate   # [V31-18]
nx.record_fills(book: Book | str, csv: str | Path) -> BookUpdate     # records of real fills and discretionary trades a person made [V31-18]
nx.cash_flow(book: Book | str, amount: float, *, ccy: str, sleeve: str, session: str | date | None = None,
               note: str = "") -> BookUpdate                       # deposit (+) / withdrawal (−) [V31-19]
nx.preregister(strategy: Strategy | Factor, *, metric: Literal["net_sharpe","cagr","ic_mean","dsr"], threshold: float,
               segment: str = "validation", note: str = "") -> Preregistration
nx.config() -> Config                                            # the resolved nexusbt.toml
nx.open(path: str | Path) -> Snapshot   # one package path (or a parent folder with `LATEST` → that snapshot) [V31-PUB-03]; the result can be given to `snapshot=` of every function
```

| Function | Decision grid | Run record | Attempts and exposure |
|---|---|---|---|
| `evaluate` | the last session of `freq` per market (market_local) | `kind="evaluate"` | candidate +1 per factor (for a `Mapping`, a separate candidate and observation per item), segment exposure |
| `backtest` | the strategy schedule, reference clock (5.1.3) | `kind="backtest"` | strategy candidate (+1 when new) + 1 observation, exposure |
| `screen` | one `asof` (default = each market's last snapshot session) | `kind="screen"` | exposure record only (no performance computed) |
| `live` | the ledger's next decision | `kind="live"` + ledger events | none |
| `sweep` | as `backtest` | parent `kind="sweep"` + `kind="backtest"` per candidate | +1 per candidate |
| `backtest(method≠linear)` | the strategy schedule, per fold and path | one `kind="backtest"` (`method`, folds and paths are sub-tables under that run's `validation/`) | strategy candidate +1 (+1 per `grid` point) + 1 observation; folds and paths are diagnostics (6.2) [R4-21] |
| `backtest(preview=True)` | the last year (within the chosen segment), a small universe | `kind="preview"` | +1 when a new candidate, 1 observation (`fidelity="preview"`; not a DSR performance input) [R4-12, R4F-15] |
| `compare(Strategy…)` | as `backtest` per variant | parent `kind="compare"` + `kind="backtest"` per variant | +1 per variant when it is a new candidate (the base strategy may already be a candidate) + 1 observation [R4-11, R4F-39] |
| `reconcile` | the decisions of the ledger period | not saved; updates the ledger's `status.json` | none |
| `override`, `record_fills`, `cash_flow` | – | ledger events (5.9.6) | none [V31-18, V31-19] |
| `compare`, `explain`, `check`, `describe`, `runs` | – | not saved | none |

- `rerun(run_id)`: runs again with the manifest's snapshot (confirmed by the semantic hash; at least `schema` + the file sha256 stamp), source (a new process, 5.9.3), parameters, config and lock, and compares the value hashes. When the snapshot is missing or its semantic hash differs, `ReplayError` (error E15). `new_snapshot=True` is not a rerun: it runs as a "new run" (`kind` the original one, `derived_from=run_id`) and shows the differences [C9, 11.7].
- `screen(strategy)` gives a ranking even on a day that is not a decision day and marks it `scheduled=False`. On such a day `live` places no new rebalancing orders, only exit-rule orders [11.4.6].
- `screen(factor, top=n)`: the top n of one factor per market in the investable universe.
- **Account rule of screen** [R4-08]: `account="auto"` (default) = `"book"` when `book=` is given, otherwise `"none"`. With `"none"`, risk rules that read the account are not evaluated and are set to `m = 1`, the result header and that rule's line say `drawdown_brake: not evaluated (no account) — use --ledger BOOK or --as-backtest`, and the notice E42 is raised (never skipped silently; one line per rule in `skips.parquet`). `"book"` (CLI `--ledger BOOK`) = gives `final_weight` using the ledger state (valuation NAV history, holdings, entry sessions, exit events) as a read-only account; the ledger state version and the snapshot hash go into the manifest. `"backtest"` (CLI `--as-backtest`) = backtests the same strategy from the anchor (`anchor`) to `asof` (not saved, the same determinism) and evaluates with that account (slow; the time taken is shown). The canonical target (`target_weight`) is the same in all three (INV-08).
- **`preview=True`** [R4-12] (CLI `--preview`): period = first `I` = the chosen segment (`segment=`, default train) ∩ explicit `start`/`end` ∩ the snapshot period, then one year back from the last decision of `I` (`[preview] years`, default 1; all of `I` when `I` is shorter) — that result is the interval recorded as exposure [R4F-16]; universe = the strategy universe ∩ per market the top `[preview] max_names` (default 200) by 20-session average value traded at the decision; scenarios, probes and capacity off; saved as `kind="preview"`; counted as an attempt (6.2 [R4F-15]). The first line is "PREVIEW — 1y, top 200 by traded value per market; not a research result". Target: within 5 seconds on synthetic `small` (a measurement reported, not a gate).
- **`compare`** [R4-11]: for run ids and `Run`s, the comparison table as now. Given `Strategy` values, it runs each with `backtest(**backtest_kwargs)` and gives a **variant table**: rows = variants, columns = the names of the slots that differ from the base strategy (the mark of `replace`), metrics (default CAGR, Sharpe, MDD, turnover, average `Σ|w|`, costs), a risk waterfall summary (the average share reduced per slot), DSR (cohort). The same Pipeline values are reused (L1). Variants count as candidates.
- **User blocks** [R4-07]: an `@nx.portfolio` function gives only the selection (weights belong to the sizing slot). An output id outside the universe or a side value different from `side` is E41. User construction in v1 is **one-sided only** (`side="long"` or `"short"`): two sides are combined with `nx.long_short(my_long, my_short, long_weight=, short_weight=)` and get the L/S budget and the feasible-region check (3.7) as they are; `side="both"` is E16 before the run ("combine two one-sided blocks with nx.long_short") [R4F-17]. The output of `@nx.sizer(returns="weights")` must have the same sign as the side and `Σ|w| ≤ 1` per side, otherwise E41 [R4F-38]. An `@nx.sizer` function takes only `SizingContext` (selected ids, sides, scores, ranks, the `inputs` window arrays `(window, n)` — last row = the decision row, `params`) and has no account attributes. A return that is not finite or is negative is E41. `@nx.risk_rule` takes `RiskContext` (the same windows + `ctx.account` only when `reads_account=True`: the NAV series up to the decision time, holding quantities, `avg_cost`, entry sessions, exit events — all read-only arrays), the view of the current weights `TargetView` and its own state from the previous decision, and gives a `RiskDecision`; `mult` out of range or not finite → E41; touching `ctx.account` with `reads_account=False` → E41 ("this rule reads the account; declare @nx.risk_rule(reads_account=True)"). State values are JSON scalars only, and the engine stores them in `risk_state.parquet`. All three decorators get check 6 of 6.5 (purity, captured constants) and E8 (window) as they are.
- `scenarios`: `True` = the default (`gross` (= `cost0x`, the zero-cost replay **once**), `cost2x`, `delist_lo`, `delist_hi` — 4 replays), `False` = none, a list = those names (giving both `gross` and `cost0x` still replays once, and the same series is not stored under two names) [RV-Q02]. `"capacity"` is not in the default (P5 budget) [SC-06, OQ-4]; it is turned on in `sweep`'s report of the final candidate. Every scenario reruns only the state machine with the same `TargetFrame` (Pipeline and targets reused). `capacity` is defined in 5.7.
- `anchor` (screen): the decision date where the target-state recursion (5.5.3) starts. Default = toml `[portfolio] anchor_date`. Ignored for strategies that do not use the recursion. The anchor of `backtest` is that run's first decision; for `live`, the decision that created the ledger.
- `explain(strategy, id, date)`: shows that instrument's path at that decision (5.9.9): true/false of each universe Filter → score and rank → selection / caps / risk overlays → order intent → (when the snapshot has the execution session) the fill or `blocked(reason)`. It recomputes, so no saved run is needed. On a saved run, `Run.why(id, date)` gives the same shape without recomputing [SC-13].
- `reconcile(book)`: 5.9.7 [SC-14]. The default is the deterministic replay (the snapshots the ledger recorded at each decision and fill); `restate=True` is a "restatement" comparison recomputed with new data, and the report names it so [RV-C13].
- `check(..., start_probe=True)`: also runs the start-date probe (6.5) [SC-04].
- `offsets=k` (default None) [V31-26]: shifts the schedule k ways (monthly, quarterly, annual: the `day=1..k`-th session; `every(n)`: `offset=0..k−1`; weekly: `weekday=1..k`), reruns only the targets and the state machine on **the same Pipeline values** (L1 reuse), and shows the minimum, median and maximum of CAGR, Sharpe and MDD on one "rebalance-date luck" line. This is not a new candidate but a **diagnostic** of one candidate (not counted in attempts or cohorts, 6.2). The result is `offsets.parquet`. Like the truncation probe, the extra time is only reported.
- `screen(..., show=…)` [V31-28]: `"selected"` (only the selected instruments, as now), `"held+near"` (target and held instruments + the "just missed" instruments of ranks n+1..n+`near`), `"all"` (the whole universe). `Screen.xray()` gives a table with steps 1~4 of `explain` (5.9.9) spread as vectors on the same rows: a true/false/unknown column per universe leaf Filter, the value and percentile per signal node, a status column (`held` / `buy` / `hold_band` / `sell(reason)` / `near_miss` / `excluded(reason)`). It reuses the Pipeline node values without new computation. CLI `nexusbt screen --show held+near --html`. The columns that show holdings (`held`, `sell(reason)`, whether `hold_band` is held) are filled only when `book=` (a ledger) is given; otherwise those columns are "holdings unavailable" and holdings are never made up (the same for `Screen.xray(book=None)`) [R3-21].

### 3.9 Result objects and output shapes [R-10, R-11]

Every result object gives **the same lines** from `__str__` (terminal) and `_repr_html_` (notebook); table attributes are Arrow tables with `.to_polars()` and `.to_pandas()`. Format rules: ratios `12.3%` (1 decimal), IC and correlations 3 decimals, t, Sharpe and DSR 2 decimals, counts `1,612`, a count next to a ratio `1,612/1,705 (94.5%)`, dates ISO, KRW amounts integers + commas, USD 2 decimals. Work longer than 2 seconds prints a progress line on standard error (`stage · date · time left`) [R-41].

**FactorReport** (attributes: `summary`, `ic`, `quantile_returns`, `coverage`, `turnover`, `by_year`, `delisting`, `hygiene` (`bhy_p`, `m`, `cohort_sha256`, `breadth_naive`, `implied_ir`), `label` (`fwd_return` | `fwd_return_adj` | `Label.*`, a definition sentence), `warnings`, `run_id`; methods `decay(horizons)`, `quantiles()`, `report()`, `to_strategy(path)`, `to_alphalens()` (5.9.8)):

```
{expr}        study: {study}   factor trial #{k} in study ({n_candidates} candidates)
data {snapshot_id} · {edition} · {freq} · {start} → {end} · segment {segment}
label {fwd_return: holding return, dividends reinvested at ex-date close, pre-withholding | …}

                              KR                     US
decisions                    {n}                    {n}
names / decision (median)    {n}                    {n}
coverage                     {a}/{b} ({p}%)         …
IC mean ({h})                {ic:.3f}               …
IC t (Newey-West, L={L})     {t:.2f}                …
Q{q}-Q1 / period             {x:.2%}                …
  t                          {t:.2f}                …
monotonic (Q1<…<Q{q})        {k}/{q-1} steps        …
turnover Q{q} / period       {p}%                   …
worst year IC                {year}  {ic:.3f}       …
exits in Q1 (obs/policy/unobs) {a}/{b}/{c} of {n}   …
naive breadth / yr · IR     {br:,} · {ir:.2f}      …   (naive opportunity count, not independent bets)
BHY-adjusted p (m={m})       {p:.3f}                …   (m = candidates recorded in this cohort)

gates (display only)  KR: IC t {t} {≥|<} {gate}   US: …
next   nx.evaluate(f, by=["year"]) · .quantiles() · .decay() · .to_strategy("strategies/x.py")
saved  runs/{run_id}/report.html
```

**Run** (attributes: `run_id`, `path`, `manifest`, `metrics`, `daily`, `targets`, `orders`, `fills`, `events`, `positions`, `scenarios`, `attribution`, `exposures`, `warnings`; methods `report()`, `why(instrument_id, date)`, `returns(ccy=None)`, `to_pyfolio()`):

```
{name}   run {run_id}   study: {study}  candidate #{k} ({N} candidates in study)
data {snapshot_id} · {edition} · code {graph_hash6} (git {sha}, {clean|dirty}) · params {k=v, …}
period {start} → {end} · segment {segment} · base {base_ccy} · clock {clock} · sleeves KR {w}/US {w}
execution {order} at next {open|close} · costs {profile}{ (provisional) } · markets {KR: rules KR@1 | ZZ: untested market rules}
benchmark {index} ({TR|PR}, {cap|equal|…}-weighted) · portfolio weighting {equal|value|inverse_vol}   [V31-15]
{shorting: on · borrow {bp}/yr KR {a} US {b} · collateral {m} · no borrow-availability data; uptick rule not modeled}   (only when shorting is on) [V31-LS-07]
assumptions  cash earns {r}% · dividends pre-withholding · immediate settlement · fill qty capped by realized session volume (ex-post) · gross = zero-cost replay (includes path effects)   [R3-25, R3-03]
{ruined: {sleeve} on {date} — new orders stopped; obligations booked as negative cash}   (only when there is a ruined sleeve) [R3-09]

                      net        gross      KR net(KRW)  US net(USD)  benchmark
CAGR                  …          …          …            …            {… | n/a: not in snapshot}
vol                   …
Sharpe                …
max drawdown          …
turnover / year       {x:.1f}x
cost drag / year      {p}%  (direct {d}% · path {p2}%; commission · tax · spread · impact)
cost sensitivity      0x {cagr} · 1x {cagr} · 2x {cagr}
holdings (median)     {n} (KR {a} / US {b}) · sleeve weight now KR {p}% / US {p}% (start 50/50)
{exposure (median)    long {l}% · short {s}% · gross {g}% · net {n}%   borrow cost {c}%/yr · short dividends paid {d}}   (only when there are shorts) [V31-LS-10]
vs benchmark          excess {x}%/yr (arith) · {y}%/yr (geom) · tracking error {te}% · IR {ir:.2f} · excess MDD {m}%   [V31-15]
target gap (median)   {g}% (blocked {a} · cash {b} · cap {c} · lot rounding {d} · small/band {e}) · slip vs decision {s} bp   [V31-14]
fx contribution       US sleeve {p}%/yr (local {a}%/yr · fx {b}%/yr · cross {c}%/yr)
signal-weight corr   median {tc:.2f} over {n} decisions   (not risk-adjusted)
{capacity: participation cap binds at ≈ {K} {ccy} (x10 CAGR {a}, x100 CAGR {b})}   (only with the "capacity" scenario)

exits while held      {n}: observed {a}, policy {b}, unobserved {c} · scenario lo/hi CAGR {x}/{y}
orders                filled {a} · partial {b} · expired {c} · cancelled {d} (insufficient cash {k}, {amt} {ccy}) · blocked-days: halt {e}, limit {f}, capacity {g} (bar volume {g2}; ψ-bound fills {b}/{n}), unknown-tradability {h}{, short ban {sb}} · suppressed: small {m}, band {n}   [V31-03, V31-06, V31-LS-07]
{rebalance-date luck  {k} offsets · CAGR min {a} / median {b} / max {c}}   (only with offsets) [V31-26]
dividends             paid {n} · pay date estimated {m}/{n}
PSR(0) {x:.2f} · DSR {x:.2f} (N={N} candidates in cohort {cohort6}, V[SR] from cohort) | DSR n/a ({reason}) · MinTRL(95%) {y:.1f}y
{Sharpe (Lo, ρ1={r:.2f}, lags ≤ 10) {x:.2f}}   (only when |ρ1| > 0.1)
segments seen in study  train {a} · validation {b} · test {c}
warnings {n} (run.warnings) · data fallbacks {k} · reconciled: {yes|NO}
```

The exposure table, risk metrics (drawdown duration, recovery time, worst month), the attribution table, BHY and N_eff (v1.x) are not on the first screen; they go in the "hygiene", "attribution" and "exposures" sections of the `report()` HTML [blueprint chapter 10 risk (1)]. HTML sections added in v3.1: "monthly" (a calendar month × year return table, with the excess over the benchmark at the end of each row [V31-15]), "rolling" (quantile tables of excess returns over 1-year and 3-year windows [V31-26]), "trades" (counts, win rates, average holding periods and MAE/MFE per exit reason [V31-20]), "execution" (the decomposition of target-gap causes, fill price against decision price and arrival price in bp, the count of effective prices outside the bar range [V31-14]), "cost tiers" (costs per liquidity band [V31-27]).

**Screen** (attributes `table`, `scheduled`, `asof`):

```
{name}  screen as of KR {date} close · US {date} close   data {snapshot_id} · {edition}   {scheduled|not a rebalance day (preview)}
rank  instrument_id   name            mkt  score   {signal terms…}  target_w  flags
…
universe {n} KR / {n} US · selected {a}/{n_KR} KR, {b}/{n_US} US · run {run_id}
```

`flags`: `vendor` (vendor input), `fund {d}d old`, `halted`, `limit-up`, `panel {d}d old`, `admin` (administrative issue, caution), `short-ban` (a short target during a short-sale ban period).

With `show = "held+near"|"all"`, the column `status` (`held`/`buy`/`hold_band`/`sell(reason)`/`near_miss`/`excluded(reason)`) is added, and `Screen.xray()` is the Arrow table spread out to the leaf Filter and signal node columns [V31-28].

**Orders** (attribute `table`: `idempotency_key, sleeve, action, instrument_id, name, order_type, qty, limit_price, stop_price, tif, est_price, est_value, reason, check`; `action` ∈ buy / sell / sell_short / buy_to_cover [V31-LS-06], `check` = the result of the pre-checks [V31-10]):

```
{name} live · decision {decision_id} · as of KR {date} close · book {book} (value {v} {ccy})
action  instrument_id  name   type    qty    est_price   est_value   reason
…
orders {n} (risk-reducing first: sells, covers) · est cost {c} · next rebalance {date} · checks: {ok|n flagged (E36)}
write: orders.to_csv("orders/{date}.csv")   apply to paper book: nx.fill(book, orders)
```

**DecisionExplanation** (`nx.explain(strategy, …)`, `Run.why`): gives the stage table of 5.9.9 as lines, as it is (`universe  Filter a: True · Filter b: False ← dropped here` → `score {x} · rank {r}/{n}` → `selected | not_selected | capped | risk_capped` → `order {side} {qty}` → `fill {qty} @ {px} ({fill_rule}) | blocked({reason})`).

**ReconcileReport** (`nx.reconcile`): `book {name} · decisions {n} · sessions {a}→{b} · mode {replay (recorded snapshots) | restate (snapshot {id})}`, then the lines `targets {match|first diff}`, `orders …`, `fills …`, `nav …`, and a last line `reconciled: yes` or `first divergence {date} {instrument_id} {stage}: book {x} vs replay {y}`.

**SweepResult**, **Comparison**, **RunTable** and **Explanation** follow the shapes of design 3.3, but the DSR line follows the Run rule above and the PBO line is written `PBO (CSCV, {S} blocks, {C} splits) {p:.2f}`. `Explanation` shows the `fundamentals_state` interval (`ts_known_from → ts_known_to`, `selected_fact_id`, `lineage_id`, `resolution_policy`) together with the `fundamentals_events` original source (`fact_id`, `doc_id`, `value_how`, `known_on`, `ts_available`) (for a snapshot without the event table = without `tds:pit-fundamentals`, only the interval, with "lineage not in snapshot") [R-23, 4.5 F-11]. In v1.x, `Comparison` gains `first_divergence()` (the date, instrument and cause where daily returns first differ: target / fill / cost).

### 3.10 CLI [R-09]

`nexusbt <command>` calls the API of the same name and prints the same text. Exit codes: 0 success, 1 user error (`NexusBTError`), 2 internal error, 3 waiting for data (`DataAvailabilityError`, live only), 4 reconciliation mismatch (`reconciled: NO` of `reconcile`).

| Command | Arguments |
|---|---|
| `nexusbt init [--data-root PATH] [--demo] [--lang en\|ko]` | writes a commented `nexusbt.toml` template (part 1 "check these" and part 2 "advanced", the two tiers of 3.11; the default English comments are canonical, `--lang ko` is a variant with the same keys and values and only the comments in Korean; the templates are `nexusbt/templates/nexusbt.toml.{en,ko}`, and a test matches their key set with the table of 3.11) [R4G-CFG-02]. With `--demo`, it unpacks the small synthetic KR+US snapshot shipped in the wheel (the `demo` preset of `nx.testing.synth`, a few MB) and writes its path — step 0 of data preparation [R4-13]. Creates `nexusbt.toml`. Without `--data-root`, it uses the environment variable `NEXUSBT_DATA_ROOT`, and without that it explains how to make a synthetic snapshot (no personal paths go into the repository, 2.7) |
| `nexusbt config check [--file PATH]` | checks only the config file and runs nothing: unknown keys, types and ranges (E16) and **contradictions** (margin keys in a cash account, short keys with `[shorting] enabled = false`, groups with `[taxes] profile = "none"`, a `max_net` that does not contain 0, and so on), in plain words in the format of 6.6 as it is (`layer  config`, a fix line). With no problem, one line "config ok: {n} keys set, {m} defaults", exit code 0/1 [R4G-CFG-03] |
| `nexusbt config show [--all] [--file PATH]` | a table of the values in effect now and their **source** (`default` / `file` / `CLI` / `code` — a value overridden by an argument in the strategy code). By default only the part 1 keys and the keys not at their default; `--all` is the whole table of 3.11. It is the same function as the resolver `load_config` the run uses (the 2.x module table), so the values equal the config written in the manifest [R4G-CFG-04] |
| `nexusbt doctor [--full]` | snapshot id, semantic hash, the three profile results (declared / check level / supported), items not checked, counts per TDS code, **the list of fallbacks (4.5)**, the rules pack per market (present / untested), column count, instruments per market, free disk, L0/L1 cache sizes, whether the stubs are current. When the data root has the publishing mark `<root>/.publishing` (a general distribution convention, outside TDS), it shows only "publishing in progress" and says to wait for the new snapshot [blueprint 12.5, RV-I09] |
| `nexusbt new factor NAME` / `nexusbt new strategy NAME [--template T]` / `nexusbt new --list` | creates a file that runs as it is (default template `monthly-topn`). 22 templates (each a runnable example + an output test, 8.5; a template not yet usable is marked in `--list`, for example "(available after T7.1)" [R4F-14]): `monthly-topn`, `value-quality-composite`, `momentum-12-1`, `low-vol`, `dividend-yield`, `sector-neutral`, `kr-us-sleeves`, `long-short`, `inverse-vol-weight`, `erc-vol-target`, `drawdown-brake`, `exits-stop-trail`, `buffer-hold`, `custom-factor`, `custom-sizer`, `custom-risk-rule`, `factor-evaluate-only`, `walk-forward-cpcv`, `ml-factor`, `zipline-port` [R4-13], `event-driven-earnings` (`on_event` after earnings announcements + `time_stop`), `macro-regime` (a `Macro.series` regime filter) [R4F-EV-05] |
| `nexusbt evaluate FILE[:VAR]` | `--segment --start --end --freq --quantiles --set k=v` |
| `nexusbt backtest FILE[:VAR]` | `--segment --start --end --set k=v --preset --no-scenarios --scenarios a,b --offsets K --preview --method linear|walk_forward|cpcv|cscv --method-opt k=v --grid k=v1,v2` [R4-12, R4-20] |
| `nexusbt screen FILE[:VAR]` | `--asof --top --anchor --show selected|held+near|all --near K --html --ledger BOOK --as-backtest` [V31-28, R4-08] |
| `nexusbt explain FILE[:VAR] ID DATE` | for a term, the value explanation; for a strategy, the decision path (5.9.9) |
| `nexusbt sweep FILE[:VAR]` | `--grid k=v1,v2` (= `backtest --method cscv --grid`) [R4-21] |
| `nexusbt compare FILE[:VAR]... | RUN_ID...` | variant table (backtests each file) [R4-11] |
| `nexusbt live FILE[:VAR] --book paper:NAME [--fill next_open]` | first fills pending orders (when the data is there), then today's decision. Updates `status.json` at the end |
| `nexusbt reconcile --book paper:NAME` | 5.9.7. Exit code 4 on a mismatch |
| `nexusbt book override BOOK ID KIND [--from D] [--until D] [--note T]` | manual instruction [V31-18] |
| `nexusbt book record-fills BOOK CSV` | records of fills a person made (`manual:` ledger) [V31-18] |
| `nexusbt book flow BOOK AMOUNT --ccy C --sleeve M [--session D]` | deposits and withdrawals [V31-19] |
| `nexusbt runs [--study S] [--html] [--prune]` | `--prune` deletes only run folders and keeps the index records and attempt counts [R-34] |
| `nexusbt rerun RUN_ID [--new-snapshot] [--trust]` | a run folder made on another machine is refused without `--trust` (E31) |
| `nexusbt stubs` | regenerates `.pyi` |
| `nexusbt check FILE[:VAR] [--probes K] [--start-probe]` | |

The data-standard tools are separate — `tds check PATH [--level manifest|schema|full] [--profile P] [--format json]`, `tds hash`, `tds describe`, `tds import csv MAPPING --out PKG`, `tds manifest build PKG` (TDS 8.1, package `nexusbt-tds`; the commands implemented in v1 and the "planned" commands are in the table of TDS 8.1) — and are not mixed into the engine CLI. `nexusbt doctor --full` calls the same checker as a library.

The default VAR of `FILE[:VAR]`: `strategy` for a strategy file; for a factor file, the last Factor defined (when there are several, `ConfigError` asks for the name).

### 3.11 `nexusbt.toml` schema

**Two tiers** [user request 2026-10-28, R4G-CFG-01]: every value the user sets goes in this one file (strategy code holds only the strategy itself). **Part 1 "check these"** (values that change results a lot from person to person) = `[data] path`, `root`, `edition`, `[defaults] capital`, `base_ccy`, `start`, `end`, `[sleeves] weights`, `[universe] exclude_microcap`, `exclude`, `[account] type`, `cash_rate_bps` (+ `initial_margin`, `maintenance_margin`, `debit_rate_bps` with `type = "margin"`), `[shorting] enabled` (+ `max_gross`, `borrow_bps`, `collateral_ratio` when on), `[costs] profile`, `sensitivity`, `provisional_bps`, `[dividends] withholding`, `[taxes] profile` (+ `currency`, `pay`, `pay_month`, `groups` with `custom`), `[execution] at`, `max_participation`, `max_bar_participation`, `min_trade_weight`, `[split] segments`, `default_segment`. **Part 2 "advanced"** = everything else (left empty, the defaults). The tiers are only a display; the validation rules are the same. `nexusbt init` writes a template commented in these two tiers (3.10), and the report header block "settings (tier 1)" prints every part 1 value actually used by the run with its source (`default`/`file`/`CLI`/`code`) (for part 2, only keys not at their default) [R4G-CFG-05]. Every key of the example file `nexusbt.toml.example` (working folder) is in this table (test `tests/docs/test_config_template.py`).

Validation: an unknown key → `ConfigError` (suggesting similar keys). A key whose name contains `key`, `secret`, `token` or `password` → `ConfigError` (2.6). Reserved keys ("reserved" below) accept only the one value allowed in v1; other values are E18. Dates are `"YYYY-MM-DD"` or `"latest"`/`"start"`. "Default" below is the value when the key is not in the file.

| Key | Type | Default | Validation | Basis |
|---|---|---|---|---|
| `[project] name` | str | the folder name | `[A-Za-z0-9_-]+` | |
| `[data] root` | path | (written by init; otherwise `$NEXUSBT_DATA_ROOT`) | the folder exists and has at least one snapshot folder with `LATEST` or `tds.json` | R-20, 2.7 |
| `[data] snapshot` | str | `"latest"` | `"latest"` or an existing id. `latest` is resolved once per call | 11.7 |
| `[data] path` | path | none | points directly at one package folder (where `tds.json` is). When present, it comes before `root` and `snapshot`. A parent folder is resolved through `LATEST` [V31-PUB-03] | V31-PUB-03 |
| `[data] edition` | str | `"strict"` | strict/compare | user decision (strict edition the only default) |
| `[data] verify` | str | `"manifest"` | manifest / schema / full (TDS check levels, 4.4). `rerun`, `reconcile`, `live` and `fill` use at least `schema` + the file sha256 whatever this value (a package checked once gets the stamp `runs/.cache/verified/<physical_sha256>`; the stamp records `(dev, inode, size, mtime_ns)` per file, and when they differ the sha256 is computed again and the stamp discarded [R3-16]) | C9, TDS 8.2, RV-I04 |
| `[data] require_profiles` | list[str] | `[]` | TDS profile names (`@version` allowed). When empty, **the requirement is computed from the features the graph uses** (4.3); when a list is given, its profiles are required in addition | 4.3, RV-I01 |
| `[data] pins` | str | `"index+root"` | index (canonical pins = `runs/index.sqlite` only) / index+root (default: also written to the data root `PINS/`, with a warning + `retention: unmanaged` when that fails) | 4.2, RV-I04, R3-17 |
| `[data] fallbacks` | str | `"warn"` | warn (uses the fallbacks of 4.5, with E30) / fail (E14 when a fallback is needed) | R-67 |
| `[data] share_count_kinds` | list[str] | `["listed", "outstanding"]` | TDS `count_kind` values; the first one present, from the front | TDS-Q4 |
| `[data] history_mode` | str | `"economic"` | v1 economic only. `"system"` is `CapabilityError` (after `tds:bitemporal` + the engine implementation) | 11.5, OI-08 |
| `[defaults] universe` | str | `"all"` | snapshot `markets` keys joined by `+`, or `"all"` (every market of the snapshot that has a rules pack) | RV-I08 |
| `[defaults] base_ccy` | str | the currency of the first market (first of the `markets` keys in UTF-8 byte order [R3-18]) (`"KRW"` for a KR+US package) | ISO 4217; there must be an exchange-rate series from the other markets' currencies into this currency | Q1, RV-I08 |
| `[defaults] capital` | float | `1_000_000_000` | > 0, in base_ccy units | |
| `[defaults] start` | date | `"1995-01-01"` | | |
| `[defaults] end` | date | `"latest"` | ≥ start | |
| `[defaults] clock` | str | `"<first market>_close"` (first market = first of the `markets` keys in UTF-8 byte order; `"KR_close"` for a KR+US package; the resolved value is fixed in the manifest [R3-18]) | `"<MARKET>_close"` (MARKET a key of the snapshot's `markets`) / market_local (`utc:HH:MM` reserved, E18) | 9.0 Q23, Q1, SC-25, RV-I08 |
| `[defaults] preset` | str | `"realistic"` | realistic (zipline is for tests only, forbidden in toml) | R-55 |
| `[split] segments` | table name→[start,end] | `{train=["start","2021-12-31"], validation=["2022-01-01","latest"]}` | names `[a-z0-9_]+`, no overlapping intervals, in order | 9.0 Q26, R-57 |
| `[split] default_segment` | str | `"train"` | a name of segments, or `"all"` | R-57 |
| `[split] embargo_sessions` | int | 0 | ≥ 0; drops decisions **before** the end of a segment (5.8). Different from the splitters' `embargo=` (the AFML meaning: drops training samples **after** the test block) (6.3a) | 11.4.5, R4-19 |
| `[validate] max_fits` | int | 200 | ≥ 1; when the number of ML fits of `method` exceeds it, the notice E40 before the run (does not block) | R4-22 |
| `[validate] min_samples` | int | 100 | ≥ 1; E40 when a fold has fewer training samples (6.3a) | R4F-30 |
| `[ml] threads` | int | 1 | ≥ 1; the thread count fixed during training (5.3.11). When not 1, manifest `nondeterministic_threads` | R4-23 |
| `[preview] years`, `max_names` | int | 1, 200 | ≥ 1 | R4-12 |
| `[sleeves] weights` | {MARKET: float} | equal weights over the universe's markets ({KR = 0.5, US = 0.5} for KR+US) | keys are the snapshot's `markets` keys, sum 1 ± 1e-9, each ≥ 0. Markets not in the universe are ignored and the rest is rescaled to 1 | 11.4.1, RV-I08 |
| `[markets] allow_untested` | bool | false | when true, runs a market without a rules pack on the generic pack (`_generic.toml`: no price limits, `provisional_bps` must be given by `[costs.provisional_bps] <MARKET>`), with "untested market rules" in the report and manifest | RV-I08 |
| `[universe] investable` | bool | true | | |
| `[universe] exclude_microcap` | bool | false | | 9.0 Q31 |
| `[universe] microcap_pct` | float | 0.20 | (0, 0.5] | Q17 |
| `[universe] eligibility_rule` | str | `"investable-v1"` | a value of `eligibility_daily.rule_id` | TDS-D16 |
| `[universe] exclude` | list[str] | `[]` | the `exclude` names of 3.6 | V31-30 |
| `[panels] feature`, `label` | str | `"factor_pit_monthly"`, `"label_monthly"` | the `name` of `feature_panels`/`label_panels` | TDS-D18 |
| `[portfolio] anchor_date` | date | `"start"` (= `[defaults] start`) | the screen anchor of the target-state recursion (5.5.3) | SC-02 |
| `[portfolio] tiebreak` | str | `"hash"` | hash / id (5.4.2, 3.7; the zipline preset fixes id) | V31-29 |
| `[portfolio] band_entries` | str | `"skip"` | skip / buy — whether to newly buy an instrument kept by the hold band but never bought (5.6.7) | V31-17 |
| `[portfolio] max_missing_decisions` | int | 1 | ≥ 1; the cap on consecutive missing decisions for `on_missing = "hold"` | V31-17 |
| `[shorting] enabled` | bool | false | when false, negative target weights are E16, and results are bit-identical to the long-only path (INV-22) | V31-LS-01 |
| `[shorting] max_gross` | float | 1.0 | (0, 3]; cap on gross exposure Σ|w| (within the sleeve). No leverage beyond this value the user sets | V31-LS-02 |
| `[shorting] max_net` | [float, float] | [−1.0, 1.0] | the closed interval of net exposure Σw; must contain 0 (otherwise E16) | V31-LS-02, R3-07 |
| `[shorting] borrow_bps` | {MARKET: float} | 0 in every market | [0, 5000]; the annual borrow cost (bp) charged on the short value. Accrues at session start as the previous session's closing short quantity × the previous session's valuation price × calendar days/`day_count` (a pack key, seed 365) (5.6.3(1)) | V31-LS-04, R3-09 |
| `[shorting] collateral_ratio` | {MARKET: float} | 0.5 in every market | [0, 2]; short value × (1 + this value) is held as collateral (5.6.7) | V31-LS-04 |
| `[shorting] short_rebate_bps` | {MARKET: float} | 0 in every market | [0, 2000]; the annual rebate on the valued short position (the same accrual as the borrow cost). v3.1's name `proceeds_rate_bps` was changed because its meaning (proceeds basis) and its formula (valuation basis) differed | V31-LS-04, R3-09 |
| `[account] cash_rate_bps` | float or {MARKET: float} | 0 | [0, 2000]; annual interest (bp) on positive cash balances. The same session-start accrual as the borrow cost (only on the previous session's closing `cash_minor > 0`; no interest on negative cash). With 0, results are bit-identical to before this key existed. Report header "cash earns {r}%" | user decision 2026-10-28, R3-25 |
| `[account] type` | `"cash"` \| `"margin"` | `"cash"` | `"cash"` = as now (fills never make cash negative, no long margin loan); `"margin"` = the margin account of 5.6.7a. Writing the margin-only keys below with `"cash"` is E16 ("margin settings need [account] type = \"margin\"") | user decision 2026-10-28, R4G-MG-02 |
| `[account] initial_margin` | {MARKET: float} | rules pack seed (US 0.50, **unverified**); no KR seed | (0, 1]; the initial margin ratio. With `"margin"`, E16 when a run market has no value. For KR the user writes the credit deposit ratio | R4G-MG-03 |
| `[account] maintenance_margin` | {MARKET: float} | rules pack seed (US 0.25, **unverified**); no KR seed | (0, `initial_margin`]; the maintenance margin ratio (for KR the user converts it from the collateral ratio, for example collateral ratio 140% → 1 − 1/1.4 ≈ 0.286). E16 when missing | R4G-MG-03 |
| `[account] debit_rate_bps` | float or {MARKET: float} | 0 | [0, 5000]; annual interest (bp) on the margin loan (the long share of negative cash). The same session-start accrual as the borrow cost (calendar days/`day_count`), event `margin_interest`, bridge `financing` | R4G-MG-04 |
| `[execution] order` | str | `"market"` | market / limit | R-56 |
| `[execution] at` | str | `"open"` | open / close | Q5 |
| `[execution] limit_offset_bps` | float | 0.0 | ≥ −500, ≤ 500 | |
| `[execution] max_participation` | float | 0.05 | (0, 1] | design 3.6 |
| `[execution] max_bar_participation` | float | 0.10 | (0, 1]; cap relative to that session's actual volume (5.6.6) | V31-03 |
| `[execution] min_trade_value` | float or {MARKET: float} | 0 | ≥ 0, local currency | V31-06 |
| `[execution] min_trade_weight` | float | 0.0 | [0, 0.1] | V31-06 |
| `[execution] rebalance_band` | float | off (none) | (0, 1]; a band relative to the target weight | V31-06 |
| `[execution] band_mode` | str | `"edge"` | edge / target | V31-06 |
| `[execution] adv_window` | int | 20 | ≥ 5 | 11.4.2 |
| `[execution] adv_min_obs` | int | 10 | 1..adv_window | |
| `[execution] max_order_age_sessions` | int | 20 | ≥ 1 | 11.4.2 |
| `[execution] limit_fill` | str | `"through"` | through (the price must go past the limit) / touch (touching is enough) | 5.6.4 |
| `[execution] kr_limit_tolerance` | float | 0.005 | [0, 0.05] | 5.6.5 |
| `[execution] unknown_tradability` | str | `"assume_tradable"` | assume_tradable / block (both report counts) | 11.4.2 |
| `[execution] cost_reserve_bps` | float | 0.0 | [0, 500]. Shrinks the executable weight in decision sizing by `(1 − reserve)` to leave room for buy costs (5.6.7). Recorded in the manifest | RV-Q07 |
| `[execution] intraday_proceeds` | str | `"next_phase"` | fixed (the one value allowed in v1): proceeds of intraday-stage sales are usable from the close stage (5.6.3) | RV-C06 |
| `[costs] profile` | str | `"provisional"` | provisional / realistic / none | 9.0, R-61 |
| `[costs] table` | str | `"default"` | default or a CSV path (schema of 4.7) | R-25 |
| `[costs] sensitivity` | list[float] | `[0, 1, 2]` | contains 1 | Q6, R-38 |
| `[costs.provisional_bps] <MARKET>` | {buy, sell} | the market rules pack value (KR pack {buy=5, sell=25}, US pack {buy=5, sell=5}) | ≥ 0. Required for a market without a pack (`allow_untested`) | 9.0, R-61, RV-I08 |
| `[costs] provisional_table` | path | none | a provisional cost table by period and liquidity band (written by the user, schema of 4.7). Fixed bp when absent | V31-27 |
| `[costs] impact_y` | float | 0.5 | ≥ 0 | research 2.4 |
| `[costs] impact_a2`, `impact_a3` | float | 0.5, 1.0 | (0, 2] | SC-11, Kissell |
| `[costs] min_half_spread_bps` | {MARKET: float} | the market rules pack value (KR 5, US 1) | ≥ 0 | RV-I08 |
| `[costs] max_half_spread_bps` | float | 200 | ≥ min | |
| `[dividends] missing_pay_date` | str | `"estimate"` | estimate / fail | 9.0 Q29, R-60 |
| `[dividends] fallback_pay_lag_days` | {MARKET: int} | the market rules pack value (KR 120, US 21) | 1..400 | R-60 [est.], RV-I08 |
| `[dividends] estimate_window_years` | int | 5 | ≥ 1 | |
| `[dividends] estimate_min_obs` | int | 20 | ≥ 1 | |
| `[dividends] withholding` | {MARKET: float} | 0.0 in every market | [0, 0.5]. Not applied to events with `corporate_actions.gross_or_net = "net"`. With 0, "dividends pre-withholding" in the report header | A-14, RV-Q02 |
| `[corporate_actions] rights` | str | `"lapse"` | lapse / fail | A-15 |
| `[corporate_actions] unsupported` | str | `"fail"` | fail / cash_at_adjustment | 11.4.3 |
| `[corporate_actions] bonus_shares_tradable` | str | `"at_pay_date"` | at_ex / at_pay_date | 11.4.3 |
| `[corporate_actions] decimal_ratio` | str | `"exclude_instrument"` | exclude_instrument / require_exact / literal. **exclude_instrument** (default, user decision 2026-10-29 [R7-01]) = only the instruments with an event lacking an exact ratio are excluded, from that event on (5.6.1 "events without an exact ratio"). require_exact = E13 when even one such event is in the run's scope. literal = the f64 decimal notation as an exact decimal fraction (no inference, E30 and a count on the header line, manifest `policies.corporate_actions`) | R4F-01, R7-01 |
| `[delisting] unknown_inclusion` | str | `"conservative"` | conservative / error. When it is unknown whether delisting distributions are included (5.6.13): conservative = the reading that makes the sleeve value smaller + E30, error = E13 | R4F-05 |
| `[delisting] policy` | str | `"observed_then_policy"` | observed_then_policy / observed_only / lo / hi | Q18 |
| `[delisting] scenarios` | bool | true | | |
| `[settlement] model` | str | `"immediate"` | reserved: v1 immediate only | SC-18, OQ-13 |
| `[taxes] profile` | str | `"none"` | none / custom. With custom, the user writes the `[taxes.groups.<name>]` below (in the config file, like commissions; the engine has no built-in tax rates). 5.6.11a | SC-17, OI-18 |
| `[taxes] currency` | str | the base currency | the currency taxes are computed and shown in (for example `"KRW"`). Gains and losses in other currencies are converted at that day's valuation exchange rate (5.6.9) | OI-18 |
| `[taxes] pay` | str | `"report"` | report = NAV unchanged, after-tax NAV and tax lines reported separately / cash = deducted from cash on the payment date | OI-18 |
| `[taxes] pay_month` | int | 5 | 1~12. With `pay = "cash"`, paid on the first session of this month of the next year | OI-18 |
| `[taxes.groups.<name>] markets` | [str] | — | the markets in this group (for example `["US"]`). A market belongs to one group only | OI-18 |
| `[taxes.groups.<name>] gains_rate` | float | 0.0 | [0, 0.6]. Multiplied by each year's sum of realised gains and losses (losses offset) − the exemption, when > 0 | OI-18 |
| `[taxes.groups.<name>] annual_exemption` | int | 0 | ≥ 0, in integer minor units of `[taxes] currency` (for example 2,500,000 won) | OI-18 |
| `[taxes.groups.<name>] basis` | str | `"average"` | average (moving-average cost) / fifo | OI-18 |
| `[fx] max_stale_days_decision` | int | 10 | ≥ 0 | 11.5 |
| `[fx] max_stale_days_valuation` | int | 10 | ≥ 0 | |
| `[fx] series` | str or {"<BASE><QUOTE>": "<rate_kind>@<source>"} | `"auto"` | auto = that one when the currency pair has a single `(rate_kind, source)` series; with several, `rate_kind` priority fixing → close → mid; if still several, `ConfigError` shows the list and asks for a choice | TDS-D17 |
| `[benchmarks] <MARKET>` | str | `"auto"` | `"auto"` = that market's `asset_class = index`, `index_kind = TR` instrument when there is exactly one (with several, the one whose `name` equals the market rules pack's `benchmark_hint`; if still several, E16 with the list), or an instrument id, or `"none"`. When none, "n/a: not in snapshot" | 9.0 Q30, R-59, TDS-D15, OI-02, RV-I08 |
| `[fund] max_age_days` | int | 550 | 0 = off | the reference producer's panel rule |
| `[evaluate] freq`, `quantiles`, `min_pairs`, `label_entry` | | monthly, 5, 20, `"next_open"` | quantiles 2..20, min_pairs ≥ 3, label_entry next_open / close | 11.4.5 |
| `[evaluate] target` | str | `"fwd_return"` | fwd_return (economic: reinvested at the ex-date close) / fwd_return_adj (adjusted-price ratio, for comparison with zipline and alphalens) | RV-C04 |
| `[meta] sector`, `industry` | str or {MARKET: str} | `"auto"` | `"<scheme>@<level>"` (level omitted = the top level of that scheme) | OI-07, RV-C08 |
| `[gates] ic_t`, `dsr` | float | 3.0, 0.95 | display only | Q7 |
| `[checks] auto_truncation_probe` | bool | true | | 6.5 |
| `[checks] probes`, `seed` | int | 4, 0 | probes 0..64 | |
| `[checks] start_probe` | bool | false | runs the start-date probe automatically in evaluate/backtest (off by default; an argument in `nx.check`) | SC-04 |
| `[checks] start_probe_shift` | int | 21 | 1..252 sessions | SC-04 |
| `[runs] dir` | path | `"runs"` | | |
| `[runs] cache_max_gb` | float | 20 | ≥ 0, L0 + L1 together. L0 is not deleted right away when a snapshot is deleted; the LRU of this limit deletes it (starting with what no remaining snapshot refers to) | risk 24, SC-15, R3-04 |
| `[compute] workers` | int | 1 | 1..8 | 11.7 |
| `[compute] threads` | int | 4 | 1..16 | |
| `[compute] memory_budget_gb` | float | 4.0 | ≥ 0.5. One budget for **the whole process tree** (main process + workers); a batch can be smaller than a year (5.3.8) | P7, RV-I05 |
| `[compute] precision` | str | `"float64"` | v1 float64 only | 9.3 Q25 |
| `[live] book_dir`, `orders_dir` | path | `"runs/books"`, `"orders"` | | |
| `[live] max_price_jump` | {MARKET: float} | the rules pack's price limit (KR 0.30), otherwise 0.5 | (0, 5] | V31-10 |
| `[live] spike_sigma` | float | 8.0 | > 0 | V31-10 |
| `[live] max_order_weight_mult` | float | 2.0 | ≥ 1; flagged when one order's amount > sleeve value × maximum target weight × this value | V31-10 |
| `[live] liquidity_floor_pct` | float | 0.10 | [0, 0.5]; flagged when it picks instruments in this bottom share of universe ADV | V31-10 |
| `[rounding.<MARKET>] <component>` | {mode, unit} | the market rules pack's `[rounding]` | mode half_up / half_even / down, unit = a multiple of the minor unit. User override (like commissions and taxes) | V31-05 |
| `[report] rolling_windows_years` | list[int] | `[1, 3]` | 1..10 | V31-26 |

---

## 4. Input data: TDS v1.4 references and the engine-side reading rules

### 4.1 The canonical source and the scope of this chapter [SC-24, R-66]

- **The canonical source of the input format is TDS v1.4** (`engine-data-standard-v1.4.md`; changes from v1.1 are in TDS chapter 16 [V31], from v1.2 in chapter 17 [R3], from v1.3 in chapter 18 [R4F]; in the repository `tds/spec/tds-v1.md`, 9.1). Column names, types, nulls, keys, sort order, partitions, availability rules, hashes and check codes are set by TDS, and this spec does not write them again. When this spec and TDS describe the input format differently, TDS is right (the differences from chapter 4 of the v1 spec, TDS-D1~D24, are already reflected throughout this v2; the mapping is appendix B.3).
- This chapter sets only the **engine side**: the capabilities the engine requires (4.3), the checks at open (4.4), the fallbacks when columns are missing (4.5), the reading rules per dataset (4.6), the engine resource files and market rules packs (4.7), and the synthetic generator (4.8).
- Version rules: the engine opens only packages with `tds_version` MAJOR = 1 (otherwise E14 + `TDS-M002`). A higher MINOR of the same MAJOR is opened, but split by **whether it uses features the engine does not know** [TDS 10.3, RV-I01]: unknown columns and **optional** datasets are ignored with a `TDS-M011` warning; unknown values of **descriptive** open enums (`category`, `delist_type`, `reason` and the like) are read as `other`; unknown values of **closed enums that affect the run** (`kind`, `asset_class`, `obs_status`, `exit_value_status`, `status`) and unknown **required resolution rules** (a new `availability` rule name and the like) are `TDS-M014` → E14 ("this engine does not support …"). It does not promise to accept every future 1.x package unconditionally.
- Schemas with `status: experimental` (ticks, quotes, futures, options, crypto) are not read by the v1 engine (chapter 11).
- The engine does not open DuckDB files [R-20, design 1 principle 4]. The engine reads only the files declared in `tds.json` [INV-17].

### 4.2 Location and distribution conventions (outside TDS, producer conventions) [TDS-D22, RV-I04]

- **Linked by path only** [V31-PUB-03]: the engine's data source is **one TDS package path** — `nx.open(path)`, `[data] path`, or the root below + `LATEST`. The engine has no reading code specific to a particular producer (DB connections, producer schemas, export steps). When a producer writes the package directly from its build (TDS 4.1 "producer-native package") and reuses unchanged partitions by cloning (APFS `clonefile`, reflink; preferred) or hard links (fallback), the engine side is the same: it only reads the package (it requires no write permission; caches and stamps are on the `runs/` side, pins in the index and the root `PINS/`), and it judges content by the file sha256. When the file sha256 is the same, the L0 cache hits as it is (5.3.9). **File identity** [R3-16, ADR-0037]: for every file whose sha256 it has checked, the engine writes `(dev, inode, size, mtime_ns)` in the stamp (`runs/.cache/verified/`) and the L0 entry, and on the next open checks with `stat` that it is the same. When it differs (edited in place, a replaced file), it computes the sha256 again and discards that stamp and L0 entry. The identity check is a defence against accidental edits, not a cryptographic proof (`[data] verify = "full"` reads every byte).
- The engine takes the data root as `[data] root` (or `$NEXUSBT_DATA_ROOT`). `<snapshot_id>/tds.json` under the root is one snapshot. `snapshot_id` = the run id of the published build (for example `20261027-143144`) [Q3].
- `LATEST`: a one-line text file whose content = the latest `snapshot_id`. The writer replaces it atomically, temporary file → `rename` [11.9 Q-E3]. `[data] snapshot = "latest"` is resolved once per call.
- **Pins**: the canonical record is the `pins` table of the engine index `runs/index.sqlite` (5.9.5). With `[data] pins = "index+root"` (**default** — with v3.1's default `index`, the producer's retention rules could not see the engine index, so `rerun` and ledger `reconcile` of a run two days old became E15 [R3-17]), it also writes an empty file `PINS/<snapshot_id>/<run_or_book_id>` under the data root. A write failure (a read-only root, another producer) is left only as a warning, and the run manifest and the ledger `status.json` record `retention: unmanaged` (it does not claim the snapshot is protected). A ledger pin is not released while the ledger exists. `nexusbt doctor` shows the number of runs and ledgers whose root pin could not be written on a "pins not visible to producer" line. Whether the producer's clean-up respects the root `PINS/` is a producer convention. When the disk is short, the engine caches (L0, L1) are deleted first.
- This convention is a promise on the producer side; another producer may give just one snapshot folder without `LATEST` or `PINS` (then `[data] snapshot` is the folder name). The engine runs even when the data root is read-only.
- The snapshot's hash set = the package `physical_sha256`, `value_sha256` and `semantic_sha256` of TDS 4.5 (a dataset value hash includes the partition columns as path values, TDS-D19). The `snapshot_semantic_hash` of the run manifest and `DecisionContext` is the **semantic hash** (cache keys are set more finely, per partition, 5.3.9 [R3-04]): even with the same Parquet, a change in availability rules, fixed-point exponents, policies or market declarations makes it different data [RV-C10].

### 4.3 Capability contract: profiles, check levels, engine support [TDS chapter 7, RV-I01]

A profile is a **conformance claim**, and what the engine does is set by **capability**. The engine requires no fixed list of profiles (v2's requirement of four default profiles is abolished). At open (4.4) it gives three results per package: (a) **declared** — in `tds.json profiles` (with `@version`), (b) **checked** — up to which level (`manifest`/`schema`/`full`) the rules of that profile were confirmed; rules that level cannot see are `not_checked` and are not written as passing, (c) **supported** — whether this engine version implements the feature. Then it computes the datasets and columns needed from **the features the graph uses** ("feature → needs" in the table below), and when something is missing it applies a fallback (4.5) or raises E18. Factor screening that uses only `Price` needs only `instruments` + `bars` (+ `calendar_sessions` and `corporate_actions` when present). Names written in `[data] require_profiles` are required in addition.

| Feature (graph, call) | Datasets needed | When missing or short |
|---|---|---|
| `Price.*`, `run_pipeline`, `screen(factor)`, `evaluate` (`fwd_return_adj`) | `instruments`, `bars(1d)` | E14 if `bars` has no close |
| raw prices + adjustment (`close`, `close_tr` exact), `evaluate` (`fwd_return`) | the above + `bars.price_basis = raw` + `corporate_actions` (empty table allowed) + `calendar_sessions` | an adjusted-price package (`tds:minimal-daily`): `Price.close` = that value, `close_tr` and `fwd_return` → E18 ("economic labels need raw prices and corporate actions") |
| `backtest`, strategy `screen`, `live` | the above + `delistings` (empty table allowed), `bars` OHLCV, `obs_status`, `density = dense` | 4.5 F-01, F-03, F-13; E18 for `minimal-daily` |
| tradability rules | `tradability_daily` | when missing, blocks by `obs_status` only, with E30 |
| `investable=True` | `eligibility_daily` | F-07 |
| `Fund.*` | `fundamentals_state`, `dictionary/items` | F-06 (E18) |
| `Meta.sector/industry/<scheme>` | `classifications` | E18 |
| multi-market sleeves, `.to(ccy)` | `fx_rates` | E18 |
| `weight="value"`, `exclude_microcap`, `shares_out` | `share_counts` | F-08 |
| `Panel.*`, `Label.*` | `feature_panels`, `label_panels`, `dictionary/columns` | E18 |
| `explain` lineage | `fundamentals_events` | F-11 |
| `index_members` | `universe_membership` | E18 |
| `Trad.*`, `universe(exclude=[admin values])` | `tradability_daily` (`admin_status` and so on) | E18 [V31-30] |
| `Market.series(id)` | `instruments` (that id) + `bars` | E18 [V31-13] |
| `Macro.series(id)` | `series_observations` (that `series_id`) | E18 [R4F-EV-01] |
| `Events.<kind>` | `events` (that `event_type`) or `corporate_actions`, `fundamentals_events` | E18 [R4F-EV-02] |
| price grid (limit, stop, exit, price limits) | `instruments.tick_size`/`tick_rule_id` → `market_rules` (TDS v1.2 5.27, optional) → rules pack `[grid]` | F-15 [V31-05] |
| exact split ratios | `corporate_actions.ratio_num/ratio_den` (TDS v1.4, required for events that change the share count) | when missing, 0 or negative, or only one of the two: E13 at open (check A010 error); with `[corporate_actions] decimal_ratio = "literal"`, the f64 decimal notation as it is + E30 `ratio_decimal_literal` [V31-01, R4F-01] |

The table below maps profiles to the features above (for reference).

| Profile | Datasets the engine reads | Engine features it turns on | When missing |
|---|---|---|---|
| `tds:minimal-daily@1.0` | `instruments`, `bars(1d)` (adjusted prices allowed, `price_basis` declared) | analysis paths only: `Price.close`, `run_pipeline`, `screen(factor)`, `evaluate(target="fwd_return_adj")` | backtest and economic labels E18 [RV-I03] |
| `tds:equity-daily-core@1.0` | `instruments`, `calendar_sessions`, `bars` (freq=1d, raw, dense, OHLCV, `obs_status`), `corporate_actions`, `delistings` | `Price.*`, OHLC fill rules, split, dividend and delisting accounting, `backtest`, `screen` | the fallbacks F-01~F-04 of 4.5; E14 if `bars` still has no close |
| `tds:equity-daily-research@1.0` | the above + `tradability_daily`, `eligibility_daily`, `instrument_symbols`, `fx_rates` (two or more markets), `fundamentals_state`, `classifications`, `dictionary/columns`, `dictionary/items` (+ optional `share_counts`, `universe_membership`, `instrument_xref`) | tradability rules, the investable universe, KR+US sleeves, `Fund.*`, `Meta.*`, `.to(ccy)` | F-05~F-10 |
| `tds:panels@1.0` | `feature_panels`, `label_panels` | `Panel.*`, `evaluate(target=Label.*)`, a universe substitute | `Panel.*` and `Label.*` → E18; the default `fwd_return` of `evaluate` still works |
| `tds:pit-fundamentals@1.0` | `fundamentals_events` + `fundamentals_state` (TDS chapter 7 is canonical) | the source lineage of `nx.explain` | F-11 |

`cum_factor_*` is required by no profile (when present it is compared by A001 in `full`; when absent the resolver builds it from the events) [RV-I01]. The engine does not read `tds:bitemporal` or the intraday, tick, futures, options and crypto profiles (`experimental`) in v1 (chapter 11).

### 4.4 When a snapshot is opened [TDS chapter 8, TDS-D21]

1. Calls `tds.check(path, level=…)` as a library. The level is `[data] verify`: `manifest` (default; `tds.json`, path safety (M012, M013), file existence, bytes, presence of the profile datasets), `schema` (+ Parquet footers, statistics, partition paths), `full` (+ every row: keys, sort order, references, time, density, factors ↔ events, values, hashes). `rerun`, `reconcile`, `live` and `fill` use at least `schema` + the file sha256 (skipped when there is a stamp and the file identity `(dev, inode, size, mtime_ns)` is the same, computed again when it differs [R3-16]). `nexusbt doctor --full` and `verify="full"` use `full`. Measurement (P1) is based on `manifest`.
2. If there is even one error (severity E), `SnapshotError` (E14): the first error's TDS code, dataset, file, key and hint, the count per code, and, when the optional block `producer.hints` of `tds.json` has a hint for that code, that sentence (TDS 4.2) — the engine does not know a particular producer's ticket numbers. Warnings (W) are left in the run warnings as counts per code [RV-I09].
3. Capability decision (4.3): three results per profile, the data needed by the features the graph uses. A package that **breaks** a profile it declared (a check error) is not repaired by fallbacks: E14. When a feature is missing in a valid lower-profile package, a feature with a 4.5 fallback is substituted with E30 when `[data] fallbacks = "warn"`, and is E14 when `"fail"`. A feature without a fallback is E18 when that feature is called. Repairing an old format is not the engine's job but the import step's (`tds import`, TDS chapter 9), which makes a new package.
4. Additional engine-side checks (not in the checker; always at engine open): the markets the run needs are in `markets` and **their market rules pack** (4.7) exists — otherwise E18 ("no market rules pack for {m}; supported: {list}; set [markets] allow_untested = true to run with generic rules (recorded)"); the market's `calendar_id` is in `calendar_sessions` (otherwise F-02 only when `exchange_calendars` knows that calendar); the types of the columns the engine reads (`contracts.ENGINE_COLUMNS`) are the same as the TDS types. **strict quality**: rows with row-level `pit_quality = backfilled` in the two-time-axis tables (`classifications`, `universe_membership`, `instrument_symbols`) are left out of strict-edition lookups (TDS K6); using a dataset-level `backfilled`/`mixed` (a table without row-level quality) in a strict run is E30 (naming the dataset) [TDS 6.5, RV-C09]. **Invalid exact ratios**: if the `corporate_actions` of a run market have rows where only one of `ratio_num/ratio_den` is present or either is 0 or below, `AccountingDataError` (E13; the list of event ids) before the run — in TDS v1.4 A010 is an error (E) (5.11), and the engine blocks the same rows with E13 so that it does not compute quantities from a package whose canonical values are invalid [R3-06, R4G-05].
5. As a result it builds `Snapshot.profiles` (the three results), `Snapshot.capabilities` (the set of features turned on) and `Snapshot.fallbacks` (the list of fallbacks used: id, dataset, market, count). They are kept as they are in the run manifest's `data.profiles`, `data.capabilities`, `data.unchecked`, `data.fallbacks` and `assumptions`.
6. When a run starts, (snapshot_id, run_id) goes into the index `pins` (with `[data] pins = "index+root"` also the root `PINS/`; a failure is a warning) [11.7 (9), RV-I04].

### 4.5 Fallbacks [R-67, RV-I01, RV-I09]

The table below is the defined thing the engine does **when a valid package does not fill some column or dataset** (whatever the producer). Every fallback is an E30 warning + a manifest record, not a hidden fallback (INV-12). Each fallback is tested with the synthetic generator's `degrade=` option (4.8). Engine error and warning sentences mention only TDS codes and `producer.hints`. Engine M0~M6 can be finished with synthetic packages (4.8).

| id | What is missing (a gap in TDS) | Engine behaviour | Test |
|---|---|---|---|
| F-01 | `open`, `high`, `low` of `bars` missing/null | `Price.open/high/low` = NaN. Open-stage orders on that row are `blocked(no_open)`, intraday-stage ones (limit, stop, exit) `blocked(no_range)` — 0 fills, the order stays and carries over (5.6.5). If opens are missing for the whole run period of a market, `CapabilityError` (E18) before the run: "open prices not in snapshot for {market}; use nx.execution.market(at='close') (recorded), or use a snapshot whose bars include open/high/low". A strategy that uses limit, stop or `exits` is E18 under the same condition. The Abdi–Ranaldo spread falls back to `min_half_spread_bps` (count reported). With this fallback `equity-daily-core` is recorded as "passed without OHLC" | G-31, `degrade=["no_ohlc"]` |
| F-02 | no `calendar_sessions` | builds each market's `calendar_id` sessions (`ts_open`, `ts_close`, half days) with `exchange_calendars` 4.13.2 (E18 for a calendar that library does not know). The session set = the sessions of that calendar from the first to the last day of `bars`. E14 (`TDS-R003`) if `bars` has dates outside that calendar. Manifest `assumptions`: "sessions synthesized from exchange_calendars 4.13.2" | `degrade=["no_sessions"]` |
| F-03 | `bars` is `density = sparse` or has no `obs_status` | expands in memory to listing period × sessions, with empty cells `obs_status = missing`. Without `obs_status`, `traded` when there is a price, `no_trade` when volume is 0 | `degrade=["sparse_bars"]` |
| F-04 | no `bars.cum_factor_*` | the engine computes the correct adjustment from the event tables anyway (5.3.3). Without the columns it builds `C` from the `price_factor` of `corporate_actions` (a definition, not a fallback; no warning). When the columns are present, the `full` check compares them by `TDS-A001` | `degrade=["no_cum_factors"]` |
| F-05 | the `ex_date` of a Korean cash dividend is really the record date | the engine uses `ex_date` as it is (no repair). It counts the KR cash dividends with `ex_date = record_date` and no `x_*_ex_date_method` column and leaves the count in E30 ("dividend ex_date may equal record date for {n} KR events; entitlement may be one session late" + the `fallback:F-05` sentence of `producer.hints` when there is one) and in the manifest | `degrade=["kr_ex_is_record"]` |
| F-06 | no `fundamentals_state` | a graph that uses `Fund.*` is E18 when built ("snapshot lacks fundamentals_state; use a snapshot with fundamentals_state, or Panel.* monthly fundamentals if present"). Other features are unaffected | `degrade=["no_fundamentals_state"]` |
| F-07 | no `eligibility_daily` | the `feature_panels.is_investable` substitute of 3.6 (`universe_source = "feature_panels"`); without that too, `investable=True` is E18 | `degrade=["no_eligibility"]` (T-06) |
| F-08 | no `share_counts` | `Price.shares_out` and `market_cap` = NaN, `weight="value"` and `exclude_microcap` are E18 before the run ("share_counts not in snapshot") | `degrade=["no_share_counts"]` |
| F-09 | US dividend amounts are split-adjusted values and the dates (record date, declaration date, pay date) are missing | no pay date → the estimation path of 5.6.11 with `pay_date_status = missing` (R-60). The engine cannot know the amount scale, so it counts per market the `TDS-A004` warnings (cash factor ≠ `1 − D/ref_price`) of the `full` check, and when the count is above 0 writes "US dividend amounts unverified (A004 n)" in the manifest `assumptions` and one warning line in the report. No repair | `degrade=["us_div_split_adjusted_no_dates"]` |
| F-10 | both `corporate_actions.ts_terms_available` and `ts_announced` null | as the TDS rule says, the terms are taken as known at `ts_effective` (no pending handling). A dataset with such events must have `pit_quality` `backfilled`/`mixed`, and a strict run gives E30 (4.4-4) | unit test |
| F-11 | no `fundamentals_events` (no `tds:pit-fundamentals`) | `nx.explain` shows the intervals only, with "lineage not in snapshot" | unit test |
| F-12 | no benchmark index instruments | "n/a: not in snapshot"; the engine does not build an index (R-59) | T4.6 |
| F-14 | no point-in-time table for changeable instrument attributes (`category`, `venue_mic`) | `Meta.category` and `Meta.venue_mic` use the current values of `instruments`, and when they reach a decision input, E30 "current value used for history" (count) [RV-C08] | `tests/unit/pipeline/test_meta.py::test_hindsight_attribute_warned` |
| F-15 | no price-grid information anywhere (no instrument `tick_size`, no `market_rules`, no pack `[grid]`) | grid = the currency minor unit (`minor_unit`; KRW 1 won, USD 0.01). E30 "price grid = currency minor unit for {market}" + a manifest record [V31-05] | `degrade=["no_tick_info"]` |
| F-16 | suspected volume unit (TDS-V011 warning: the per-instrument, per-year median of value traded / (volume × representative price) outside [0.5, 2]) | no repair. Raises the warning to E30 (counts per instrument and year), and marks "volume unit unverified" on the ADV cap, impact cost and capacity lines of that instrument and year. When `value_traded` is missing, doctor prints one line "volume unit unverified" [V31-16] | `degrade=["volume_in_lots"]` |
| F-13 | an instrument left the market but there is no delisting event row | when `instruments.delisted_on` (or `last_session` before the watermark) is present and there is no `delistings` row, it builds in memory an event with `exit_value_status = unobserved`, `ret_observed = ret_policy = null`, `ret_lo = −1`, `ret_hi = 0`, `ref_price` = the last valid raw close, `exit_date` = `delisted_on` (when absent, the session after `last_session`). Under the policy `observed_then_policy`, a holding has `ret_policy` null → E13 (5.6.13; fix: `delisting="lo"|"hi"|"observed_only"`) | `degrade=["no_delistings"]` |

### 4.6 Engine reading rules per dataset

Common:
- **Identifiers**: the key is `instrument_id`. The engine builds an integer index in memory (0..N−1 in `instrument_id` sort order; session numbers in `calendar_sessions` sort order). It does not expect integer keys in the files [A-05]. When `session_ord` is present, whether it equals the engine's numbering is checked only in `full`.
- **Partitions**: partition columns (`market=`, `year=`, `edition=`, `freq=`, `name=`) are read from the path (they are not in the files) [TDS-D5, TDS-D20]. The files to read are chosen only from the manifest's `files[].stats` (minimum and maximum of the main columns) and the path values, without opening Parquet footers (P1).
- **Availability time**: when a dataset's `availability` is `{"column": "ts_available"}`, the column is used; when it is a rule (TDS 6.2: `ts_end`, `session_open`, `session_close`, `next_session_open(<col>)`, `ts_end+<duration>`), the engine builds the column by the same rule and uses it. After that every lookup uses the one rule of 5.1.2 (`ts_available <= decision_ts`; market-axis rows by `ts_close(s)`) [INV-01].
- **Enums**: unknown values of descriptive open enums are `other` (the engine handles `delist_type` and `reason` through the general path). Unknown values of closed enums that affect the run (`kind`, `asset_class`, `obs_status`, `exit_value_status`, `status`) are E14 (4.1) [RV-Q11].
- **Edition**: `fundamentals_state` and `feature_panels` have an `edition=` partition, `classifications` an `edition` column (`strict`/`compare`/`both`). A strict run reads only strict (+ both) and does not fill from compare [Codex risk 18].
- **Market watermark**: sessions after `markets.<m>.complete_through_session` and `complete_through` are not used for fills in `live` and `fill` (5.9.6).

Per dataset (only the columns the engine reads; column definitions are in TDS chapter 5):

| TDS dataset | Columns the engine reads | Engine-side rules |
|---|---|---|
| `instruments` | `instrument_id, asset_class, category, market, venue_mic, calendar_id, currency, issuer_id, name, listed_on, listed_on_censored, last_session, delisted_on, lot_size, multiplier, is_synthetic, index_kind` | **an after-the-fact static table** (TDS 5.1): deciding listing existence (`listed_on`, `last_session` and `delisted_on` only for the listing-period mask and delisting handling), name display, units and multipliers. `delisted_on`, `last_session` and `name` are not exposed as decision inputs, and `category` and `venue_mic` follow the rules of 3.2 and F-14 [RV-C08]. v1 uses only `asset_class = equity` (+ `index` for benchmarks). Market block = `equity ∧ is_synthetic = false` (3.3). `is_synthetic = true` is not used for fills. When `listed_on_censored = true`, the window warm-up is taken as cut off at the start of the data and counted in the coverage table |
| `instrument_symbols` | `instrument_id, symbol_type, symbol, venue_mic, valid_from, valid_to, ts_known_from, ts_known_to` | display names and ticker history (the `name` of `Screen` and `Orders`), resolving symbols → ids for fixed-list universes (the `ticker` valid on that date and known at that time; rectangular lookup 5.3.6) [RV-C08] |
| `calendar_sessions` | `calendar_id, session_date, ts_open, ts_close, is_half_day` | the only source of times (5.1.1). Price limits and rule versions are not here (TDS-D8) |
| `bars` (freq=1d) | `instrument_id, session_date, open, high, low, close, volume, value_traded, obs_status, cum_factor_split, cum_factor_total` (+ the availability rule, default `ts_end` = `ts_close`; for a column rule `params.ready_delay`) | before price comparison, bar prices are turned into integers of the market minimum unit (5.6.4a; US `0.6768000000000001` → 6768 × 0.0001); a value that does not fit within 1e-9 is not moved and is counted as `off_grid_bar` [V31-05, R3-02]. Volume units: F-16 [V31-16]. With `price_basis = raw`, every feature. With adjusted prices (`minimal-daily`), analysis paths only (4.3): `Price.close` and `open/high/low` = those values, adjusted `close_tr` and `volume` = the same values (no adjustment), economic labels and backtest E18 [RV-I03]. The time a row freezes is `ready(s)` of 5.1.2. `shares_out` is not in bars (TDS-D9) |
| `tradability_daily` | `status_known, halted_full_day, limit_up_close, limit_down_close, locked_up, locked_down, price_limit_ratio, up_limit_price, down_limit_price, reference_price, admin_status` | 5.6.5. The availability times per column group (`params.availability_by_column`, required for this table from TDS v1.1) matter only when used as decision inputs; when exposed as Pipeline terms, the values known at the end of the day (`locked_*`, `halted_full_day`, `limit_*_close`) are `session_close` [RV-Q10] (the state machine uses the same session's values when executing in that session — the prices and status of the execution session are facts that happened in that session). `trading_status_events` is not read in v1 |
| `corporate_actions` | every column (TDS 5.11) | **only the resolver (5.3.3a) reads it**: it resolves amendments, cancellations, `status`, the existence time and the terms availability time at each reference time [R3-01], and adjustment (5.3.3, 5.3.4), accounting (5.6.10~5.6.12) and checks (A001) use the result [RV-C03]. **Kind mapping**: the table below |
| `delistings` | every column (TDS 5.13; including v1.2 `ret_observed_includes_distributions`) | 5.6.13 (the distribution just before delisting and the terminal value once only; three bases: observed-inclusive, observed-exclusive, policy [V31-04, R3-05]). Recoveries are not put into decision sizing before `ts_value_available` (an entitlement of unknown amount, INV-01) [RV-C01]. For labels, an input of `ts_label_available` (5.8) |
| `share_counts` | `instrument_id, count_kind, as_of_date, shares, ts_available` | 5.3.5a |
| `market_rules` (TDS v1.2 5.27, optional) | `rule_id, market, rule_kind, venue_group, valid_from, valid_to, price_from, price_to, tick_size, limit_ratio, source, verified` | `verified` goes into the release-evidence rule list as it is [R3-15]. `rule_kind = tick_band` is the price grid (5.6.4a), `price_limit` the `pct` source of 5.6.5 (after `tradability_daily`, before the rules pack table). When present it is used before the rules pack table [V31-05] |
| `fx_rates` | `base, quote, rate_kind, obs_date, ts_event, ts_available, rate, source` | one series is chosen by `[fx] series` (3.11). Decision inputs use `ts_available <= decision_ts`, report valuation `ts_event <= valuation time` (5.1.5) [TDS-D17] |
| `fundamentals_state` | every column (TDS 5.18) | 5.3.5. Interval `[ts_known_from, ts_known_to)` |
| `fundamentals_events` | `fact_id, instrument_id, item, period_end, statement_basis, version, value, known_on, ts_available, source, source_rank, doc_id, value_how, vendor_input` | only in `nx.explain` |
| `classifications` | `instrument_id, scheme, level, code, label, effective_from, effective_to, ts_known_from, ts_known_to, edition, pit_quality` | key `(instrument_id, scheme, level, edition, effective_from, ts_known_from)` (TDS v1.1; `level` not null, single level = 0). Rectangular lookup (5.3.6): in the edition (strict = `strict`+`both`, compare = `compare`+`both`), the rows with `ts_known_from <= cutoff(s) < ts_known_to` and `effective_from <= session_date(s) < effective_to` [TDS-D12, RV-C08]. Two or more for the same (instrument, scheme, level, edition) is E14 (`TDS-T012`). strict leaves out rows with row-level `pit_quality = backfilled` |
| `eligibility_daily` | `rule_id, instrument_id, session_date, is_eligible, reason` (+ availability time, TDS v1.1 default `session_close`) | 3.6, 5.1.5: only that session's row; false when missing or not yet available, no carry-over [TDS-D16, RV-C09] |
| `universe_membership` | `universe_id, instrument_id, effective_from, effective_to, ts_known_from, ts_known_to` | `index_members` (3.6) |
| `feature_panels` (name=`[panels] feature`) | `instrument_id, period, as_of_date, ts_available` + feature columns | `Panel.*`. Row `ts_available` required [TDS-D18] |
| `label_panels` (name=`[panels] label`) | `instrument_id, period, entry_date, entry_price_basis, exit_date, horizon, return_definition, terminal_policy_id` (+ optional `ts_label_start, ts_label_end, ts_label_available`) + label columns | `Label.*` (only the target of evaluate). Label times: `ts_label_start` = `ts_open(entry_date)` when `entry_price_basis` is `open`, `ts_close(entry_date)` when `close`; `ts_label_end` = the same rule on `exit_date`; `ts_label_available` = `ts_label_end` when there is no column (with the manifest assumption "label availability assumed at label end"). When it is a column, that is used [SC-20, RV-C04] |
| index instruments (`instruments(asset_class=index)` + `bars`) | `close` (= the index value), `index_kind` | benchmarks (5.7). Only `index_kind = TR` as the default benchmark [TDS-D15] |
| `dictionary/columns`, `dictionary/items` | all | dataset attributes, stubs, units (3.2). Columns with `is_label = true` are forbidden as decision inputs (E2) |

**Corporate-action kind → engine handling** [TDS-D11]:

| TDS `kind` | Engine handling (5.6.x) | Price adjustment (5.3.3) |
|---|---|---|
| `split`, `reverse_split`, `capital_reduction` (share consolidation; `ratio_new_per_old` present, `cash_per_share` null) | 5.6.10 ratio ρ = `ratio_num/ratio_den` (canonical, required in TDS v1.4); E13 when missing — the decimal notation of `ratio_new_per_old` only when the user chose `decimal_ratio = "literal"` (5.6.1) [V31-01, R4F-01] | `price_factor` |
| `stock_dividend`, `bonus_issue` | 5.6.10 ratio ρ = `1 + ratio_new_per_old`, the new shares locked for sale | `price_factor` |
| `capital_reduction` with cash (paid capital reduction: `cash_per_share` present) | 5.6.10 (ρ) + a receivable of cash `q·cash_per_share` (pay date) | `price_factor` |
| `cash_dividend`, `special_dividend`, `return_of_capital` | 5.6.11 (return of capital follows the same entitlement, receivable and payment path; withholding only for `cash_dividend` and `special_dividend`) | `price_factor` (`affects = total_only`) |
| `stock_merger`, `mixed_merger` | 5.6.12 stock merger (mixed = stock + `cash_per_share`) | the old instrument disappears (`price_factor = 1`) |
| `cash_merger` | 5.6.12 cash merger | – |
| `spinoff` | 5.6.12 (handled when `new_instrument_id` and `ratio_new_per_old` are present, otherwise not supported) | `price_factor` |
| `rights_issue` | 5.6.12 rights policy (`lapse`/`fail`); share factor = 1 (holding quantity unchanged) | `price_factor` (TERP) |
| `exchange_offer`, `other` | unsupported events (5.6.12; when held, the policy `unsupported`) | `price_factor` applied when present |
| `symbol_change`, `name_change`, `par_change` | no accounting effect (event record only) | none (`affects = none`) |

Events whose `price_factor` is null (`factor_method = unavailable`): when an instrument's window crosses that event's effective session e (when the window has a row with s < e ≤ t), the engine leaves the adjusted price cells of the rows before e as NaN and counts the diagnostic `AdjustmentUnavailable` (no hidden 1.0 substitute, INV-12). This "none" also propagates into the cumulative factors as it is: even when the package's `cum_factor_*` has values after that event, the resolver leaves the ratio across e as none (A001 does not compare that session) [RV-C03]. When held, the policy for unsupported events applies. The coverage table counts `AdjustmentUnavailable` per instrument and year.

### 4.7 Engine resource files and market rules packs (engine repository, versioned) [R-25, TDS-D23, RV-I08]

**Market rules pack** `src/nexusbt/resources/markets/<MARKET>.toml` (v1: `KR.toml`, `US.toml`, the generic pack `_generic.toml`). The market name equals the TDS `markets` key, and a pack is used for a market only when its `calendar_ids` include that market's `calendar_id`:

```toml
[pack]
market = "KR"            # TDS markets key
version = 1              # "rules KR@1" in the report and manifest
calendar_ids = ["XKRX"]
currency = "KRW"
minor_unit = 0           # digits of the currency minor unit (USD = 2)
benchmark_hint = "KOSPI" # name hint when [benchmarks] auto finds several
[price_limits]
table = "limits/kr_price_limits_v1.csv"   # when absent, no price-limit rule (US)
open_tolerance = 0.005   # source of the default of [execution] kr_limit_tolerance
[costs]
provisional_bps = {buy = 5, sell = 25}
min_half_spread_bps = 5
table_market_groups = "costs/venue_groups_v1.csv"
[dividends]
fallback_pay_lag_days = 120
[tradability]
unknown_status_before = ""   # US pack "2019-08-23" (describes the status_known=false period)
[grid]                       # price grid [V31-05]
tick_table = "ticks/kr_tick_table_v1.csv"   # tick sizes by period and price band (for membership checks and snapping); when absent F-15 (minor_unit)
base_unit = 1                # integer coordinate for price comparison (KR 1 won; US pack 0.0001 dollars) [R3-02]
[rounding]                   # rounding rule per booking component [V31-05]; KR pack default: commission, tax and withholding down (the majority option, a research default, not a claim about settlement practice), the rest half_up [R3-27]; US pack all half_up
proceeds = {mode = "half_up", unit = 1}
commission = {mode = "down", unit = 1}      # the truncation practice of Korean brokers and tax law [unverified, verified = false] — the user overrides it with [rounding.KR]. [R7-08] Facts checked (2026-10-29): National Treasury Management Act Article 47(1) truncates below 10 won at payment to the treasury; Income Tax Act Article 86 does not collect withholding tax below 1,000 won (except interest income); Samsung Securities truncates credit interest below 1 won. Per-fill tax and commission rounding was not checked against an original source, so the seed stays as it is
tax = {mode = "down", unit = 1}
dividend_withholding = {mode = "down", unit = 1}
cash_in_lieu = {mode = "half_up", unit = 1}
borrow_fee = {mode = "half_up", unit = 1}
[shorting]                   # [V31-LS-07]
allowed = true
ban_table = "shorting/kr_short_bans_v1.csv"  # periods when new short-sale orders are forbidden (covers allowed); the US pack has none
uptick_rule_modeled = false  # US pack: Rule 201 (price-restricted short sales) is not simulated (a documented assumption)
borrow_availability = "assume_all"   # no data on borrowable quantity: everything is assumed borrowable outside ban periods (a manifest assumption)
day_count = 365              # days per year of the borrow, rebate and cash-interest accrual [R3-09, R3-25]. [R7-07] KR = 365 verified = true (broker credit-interest terms: loan × rate × days/365, 366 in leap years — Korea Investment & Securities and Samsung Securities guides, 2026-10-29); the US pack seed corrected to 360 verified = true (source: IBKR margin interest USD 360 days, borrow fee /360 — broker practice, not regulation, 2026-10-29)
```

- `ticks/<m>_tick_table_v1.csv` (`valid_from, valid_to, venue_group, price_from, price_to, tick, source, verified`) [V31-05]: KR seed = from 2023-01-25, common to KOSPI, KOSDAQ and KONEX: under 2,000 won 1 won · 2,000~5,000 won 5 won · 5,000~20,000 won 10 won · 20,000~50,000 won 50 won · 50,000~200,000 won 100 won · 200,000~500,000 won 500 won · 500,000 won and above 1,000 won — `verified = true` [R7-02] (source: [Samsung Securities notice "Change of tick sizes in the domestic securities and derivatives markets"](https://samsungpop.com/ux/kor/customer/notice/notice/noticeViewContent.do?MenuSeqNo=19236), effective 2023-01-25; the original KRX regulation could not be seen because law.krx.co.kr was unreachable, 2026-10-29). Before that, the old per-market table for [2010-10-04, 2023-01-25) (under 1,000 won 1 · under 5,000 5 · under 10,000 10 · under 50,000 50 · under 100,000 100 · under 500,000 500 · 500,000 and above 1,000; KOSDAQ 100 from 50,000 won) — the KOSPI rows and KOSDAQ 50,000~500,000 won at 100 won are `verified = true` [R7-02] (source: [the KRX announcement of 2010-02-08 as republished (Mondo Visione)](https://mondovisione.com/media-and-resources/news/krx-to-lower-tick-size-for-low-priced-stocks-to-1-won-2011124/) — 1 won under 1,000 won from 2010-10-04; the "current" table of the Samsung Securities notice above). For KOSDAQ 500,000 won and above, the Samsung Securities "current" table says 1,000 won, which disagrees with the seed (100) → `verified = false` [unverified]. **Before 2010-10-04**, everything under 5,000 won was 5 won (no 1-won band), and above that the same table [R7-02, the KRX announcement above]; earlier effective dates are `verified = false` [unverified]. KR `venue_group = ETF` (`instruments.category ∈ {etf, etn}`): 5 won at every price band, kept in the 2023-01-25 reform as well (ETF, ETN, ELW) `verified = true` [R3-14, R7-03] (source: the Samsung Securities notice above; the start date is unverified). US seed = 0.01 at $1 and above, 0.0001 below $1 (Reg NMS Rule 612(b)(3)) `verified = true` [R7-04] (source: [17 CFR 242.612](https://www.law.cornell.edu/cfr/text/17/242.612)); however, the 2024 amendment (89 FR 81774) sets $0.005 for instruments at $1 and above whose time-weighted average quoted spread is ≤ $0.015, reclassified every half year, and its compliance date was postponed by an SEC exemptive order to **the first business day of November 2027** ([Release 34-105656](https://www.sec.gov/files/rules/exorders/2026/34-105656.pdf), 2026-06) — this table is right only until then. Pre-decimalisation rows — 1/8 dollar before 1997-06-24, 1/16 dollar for [1997-06-24, decimalisation date) — are `verified = false` [unverified: the 1/16 date and the finer unit below $1 have only secondary sources]; the decimalisation date is **per market**: NYSE 2001-01-29 (secondary source: [The Daily Record 2001-01-29](https://thedailyrecord.com/2001/01/29/nyse-goes-totally-decimal-8212-finally/)), Nasdaq 2001-04-09 (source: [SEC testimony 2001-05-24](https://www.sec.gov/news/testimony/052401tslu.htm), the deadline of the SEC order of 2000-06-08) — so the Nasdaq `venue_group` is 1/16 also in [2001-01-29, 2001-04-09) [R7-04, R3-14]. Pilot instruments (NYSE from 2000-08-28, Nasdaq from 2001-03-12) are not represented in the table and show up as `off_grid_bar`. The grid table is used only for membership checks and snapping order prices; comparisons use `base_unit` integers (5.6.4a).
- `shorting/kr_short_bans_v1.csv` (`valid_from, valid_to, scope, except_universe_ids, source, verified`) [V31-LS-07, R3-15]: intervals are **half-open** `[valid_from, valid_to)` (end date = the first day it is allowed again). `scope` grammar = `all` / `index:<id>[,<id>…]` (applies when the instrument is a member of at least one on that date) / `classification:<scheme>=<code>` (two-time-axis lookup). `except_universe_ids` (a list) removes from the ban the instruments that are members of at least one on that date (the union). KR seed — all checked against the original Financial Services Commission press releases, `verified = true` [R7-05] (2026-10-29): [2008-10-01, 2009-06-01) `all` (source: the attachment of [FSC 2008-09-30](https://www.fsc.go.kr/no010101/68952) — KOSPI from 10.1 and KOSDAQ from 10.2, so for KOSDAQ on 2008-10-01 the seed is more conservative by one day; [FSC 2009-05-20](https://www.fsc.go.kr/no010101/69237) lifted for non-financial stocks on 6.1); [2009-06-01, 2013-11-14) `classification:is_financial=true` (financial stocks = the financial sectors of KOSPI and KOSDAQ, including banks, securities and insurance; source: [FSC 2013-11-13](https://www.fsc.go.kr/no010101/70903) "lifted from '13.11.14"); [2011-08-10, 2011-11-10) `all` (source: [FSC 2011-08-09](https://www.fsc.go.kr/no010101/70024) 8.10~11.9, [FSC 2011-11-08](https://www.fsc.go.kr/no010101/70123) non-financial stocks lifted on 11.10, financial stocks kept); [2020-03-16, 2021-05-03) `all`; [2021-05-03, 2023-11-06) `all` but with `except_universe_ids = [index:KOSPI200, index:KOSDAQ150]` (partial resumption; source: [FSC 2021-02-03](https://www.fsc.go.kr/no010101/75290), [FSC 2021-04-29](https://www.fsc.go.kr/no010101/75830)); [2023-11-06, 2025-03-31) `all` (KOSPI, KOSDAQ, KONEX; source: [FSC 2023-11-05](https://www.fsc.go.kr/no010101/81013), [FSC 2024-06-13](https://www.fsc.go.kr/no010101/82454) extended to '25.3.30, [FSC 2025-03-21](https://www.fsc.go.kr/no010101/84216) full resumption on 3.31). During the bans, covered short sales by market makers and liquidity providers were allowed (the 2020 and 2023 originals), but they are not the engine's subject. When the snapshot lacks that membership or classification data, every instrument is taken as banned, with E30.
- **Rule verification gate** [R3-15]: the release evidence (T6.15, R-70) lists, for every rule row applied in the run (tick tables, price limits, bans, rounding, `day_count`), its source, its effective boundary and `verified`, shows the number of `verified = false` rows as numerator/denominator, and shows the off-grid bars `off_grid_bar` per market and year. A "KR/US verified" claim is made only when every row actually applied is `verified = true`.
- Only what the pack sets differs per market; the state machine and the fill rules (5.6) are the same for every market. The price-limit rule (5.6.5) is turned on only when the pack has `price_limits` (instead of v2's condition `market == KR`).
- A market without a pack is E18 (4.4). With `[markets] allow_untested = true`, `_generic.toml` is used (no price limits, ½-spread floor 5 bp, fallback pay interval 30 days, no `provisional_bps` → `[costs.provisional_bps] <MARKET>` required), with "untested market rules: {market}" in the report header and the manifest `assumptions`.
- A new market pack is added only by a PR that has public sources (the exchange's regulations) and at least one hand-calculated case for that market (chapter 10 v1.x "add market rules packs").

`src/nexusbt/resources/costs/default_v1.csv`:

| Column | Type | Meaning |
|---|---|---|
| country | str | market code (TDS `markets` key; the column name is kept for v1 compatibility) |
| market | str | `*`, KOSPI, KOSDAQ, NYSE, NASDAQ (names of price-policy groups, not MICs; the mapping `instruments.venue_mic` → group is `venue_groups_v1.csv` in the same folder) |
| side | buy/sell (a short sale uses the sell row, a cover the buy row) [V31-LS-04] | |
| component | commission / tax / other | other = the US SEC fee, FINRA TAF and the like |
| bps | float | |
| min_amount | float | minimum amount (local currency), 0 when none |
| valid_from, valid_to | date | half-open, empty valid_to = current |
| source | str | URL of the law or broker notice |
| verified | bool | whether a person checked it against the source |

- Coverage check: `realistic` can be used only when run period × run markets × side × (commission, tax) is covered without gaps by `verified = true` rows. Otherwise error E23. The first version holds only `verified = false` seed values (chapter 12 OI-03) [9.0 defaults, R-61].
- `src/nexusbt/resources/limits/kr_price_limits_v1.csv` (`valid_from, valid_to, market, limit_ratio, source, verified`): a fallback table used only when both `tradability_daily.up_limit_price/down_limit_price` and `price_limit_ratio` are null. Seed values [R7-06] (corrected 2026-10-29 — per `market`): KOSPI [1995-04-01 0.06, 1996-11-25 0.08, 1998-03-02 0.12, 1998-12-07 0.15, 2015-06-15 0.30); KOSDAQ 0.12 (start date [unverified]) → 2005-03-28 0.15 → 2015-06-15 0.30; KONEX 0.15 (left out of the 2015-06-15 widening) [design 5.4, research 2.4]. The evidence is all secondary, so `verified = false` stays and only `source` is filled: newspapers of the time (Hankook Ilbo [1996-11-25](https://www.hankookilbo.com/news/article/199611250055411462), [1998-02-12](https://www.hankookilbo.com/news/article/199802120060207540), [2005-03-10](https://www.hankookilbo.com/news/article/200503100043910652)), a summary of the 2015 effective notice ([Crowe 2015-05-29](https://www.crowe.com/kr/news/news20150529_kr)); the original KRX business regulation and its history were not seen. Before 1995-04-01 the limits were **fixed amounts** (amounts per price band), not ratios, and cannot be represented in this table → that period has no `verified = false` row, only "no price-limit information". When the `market_rules` dataset of TDS 1.1 exists, this moves to the data side (TDS-Q15).
- These files are small tables copied by hand from public sources (laws, exchanges, broker notices), not reference-producer data (the allow list of the hygiene test of 2.7).

### 4.8 Synthetic TDS package generator (`nx.testing.synth`) [TDS-D24]

The engine uses only this generator before a real producer package arrives, and in **every test** of the repository (2.7). `tiny` is a **hand-set table** (no randomness; the case yaml becomes rows as it is), and `small` and `full` follow the random rules below [RV-I05]. The generator writes TDS v1 packages (`tds.json`, hashes, dictionaries included), and its output must pass `tds check --level full` with the profiles it declares (test `test_synth_conforms`, INV-17).

```python
def make_snapshot(root: Path, *, preset: Literal["tiny","small","full","full_ci"] = "small", seed: int = 0,
                  snapshot_id: str = "synth-0001", start: date | None = None, end: date | None = None,
                  markets: Sequence[str] = ("KR", "US"),            # "ZZ" = a test market without a rules pack (XZZZ, currency XTS)
                  n_kr: int | None = None, n_us: int | None = None,
                  events: Sequence[EventSpec] = (), overrides: Mapping[str, Any] | None = None,
                  degrade: Sequence[Literal["no_ohlc","no_sessions","sparse_bars","no_cum_factors",
                                            "kr_ex_is_record","no_fundamentals_state","no_eligibility",
                                            "no_share_counts","us_div_split_adjusted_no_dates",
                                            "no_fundamentals_events","no_benchmarks","no_delistings",
                                            "no_panels","no_tick_info","volume_in_lots"]] = ()) -> Path   # two values from v3.1 [V31-05, V31-16]
```

| preset | Markets and instruments | Period | Use |
|---|---|---|---|
| tiny | KR 6, US 6 (fixed names `KR:T00001`…, `US:T00001`…) | 2020-01-02 → 2020-03-31 | hand-calculated golden cases (8.2). Events only through `events` |
| small | KR 120, US 180, with listings and delistings mixed into the period | 2015-01-02 → 2019-12-31 | unit and property tests, CI performance smoke tests |
| full | KR 5,500, US 22,100 instruments ever listed; about KR 2,300 / US 5,700 alive on a day | 1995-01-02 → 2024-12-31 | performance measurement on the compute machine (about 1.2 GB of disk; run by a person on the compute machine) |
| full_ci | 1/50 of the instruments of full (same rules and period) | 1995-01-02 → 2024-12-31 | testing the full generation path in CI |
| ("ZZ" in markets) | ZZ 6~120 instruments, calendar `XZZZ` (a copy of the XNYS sessions, only the name differs), currency `XTS` (the ISO test currency) | the preset's period | tests that market names are not hard-coded (no rules pack → E18; runs when a test `ZZ.toml` is added) [RV-I08] |

- With `degrade=()`, it declares `profiles = ["tds:equity-daily-core@1.0", "tds:equity-daily-research@1.0", "tds:panels@1.0", "tds:pit-fundamentals@1.0"]`. `producer = {"name": "nexusbt-synth", "hints": {...}}` (a few hint lines for the fallback tests). Each value of `degrade` imitates one gap of the 4.5 table, and the profiles it can no longer keep are dropped from the declaration (`tds check` still passes — it checks only what is declared). For example: `no_ohlc` → `open/high/low` null, core declaration dropped; `kr_ex_is_record` → KR cash dividends with `ex_date = record_date`; `us_div_split_adjusted_no_dates` → US dividend amounts divided by the later split factors + null dates.
- Namespaces: `id_namespaces = {"KR": "synthetic KR", "US": "synthetic US", "ZZ": "synthetic test market", "IDX": "synthetic indices"}`. No real instrument codes are used (public repository, 2.7).

Generation rules (deterministic, `numpy.random.Generator(PCG64(seed))`):
1. Calendars: XKRX and XNYS are built from the sessions of `exchange_calendars` 4.13.2 (at generation only). Times: KR open 00:00Z, close 06:30Z (06:00Z before 2016-08-01), US open 14:30Z/13:30Z, close 21:00Z/20:00Z (US daylight saving applied), half days as they are → `calendar_sessions` (with `session_ord`).
2. Instruments: uniform listing dates, exponentially distributed listing periods (mean 8 years), market proportions as in the table above → `instruments`, `instrument_symbols` (1% of ticker histories change, 0.5% have another id reuse an old ticker), `instrument_xref` (empty table).
3. Prices: log returns `μ=0.0003, σ_i ∈ U(0.01, 0.04)`, first price KR `U(1e3, 1e6)` won, US `U(2, 500)` dollars. Open = previous close·exp(N(0, σ/2)); high and low enclose the open and close. Volume lognormal (integer values for equities) → `bars` (freq=1d, raw, dense, `cum_factor_*`, availability rule `ts_end`).
4. Corporate actions: the exact ratio columns `ratio_num/ratio_den` are filled and the f64 column is their quotient (including ratios that are not exact as binary fractions, such as 1:3, 1:7 and a stock dividend of 0.29) [V31-01]; 10% of delisting events have a liquidating distribution whose ex-date lies between the last trading day and the exit, and `ret_observed_includes_distributions` [V31-04]; splits at 0.5% a year (2:1, 5:1, 7:1), reverse splits at 0.2% (1:10, 1:3), bonus issues at 0.1%, quarterly cash dividends for 30% of instruments, half of the Korean dividends with `ts_terms_available` 30~60 days after the ex-date, 1% of events amended (`revision_of`; amount and ratio amendments, some after payment), 0.5% cancelled after announcement (`status = cancelled`), `price_factor`, `share_factor`, `factor_method` and `factor_ref_price` filled → `corporate_actions`.
5. Halts and price limits (Korea): raw prices are rounded to the pack's price grid (some rows get a 1-ULP wobble to test grid snapping [V31-05]), halts on 0.1% of days (some halt periods contain split and dividend effective dates [V31-02]), limit hits on 0.2% of days, `price_limit_ratio` and `up/down_limit_price` (without tick rounding) → `tradability_daily` (US `status_known = false` before 2019-08-23).
6. Exits: a `delistings` row at the end of every listing (policy shares: observed 50%, estimated 30%, unobserved 20%; half of the observed have `ts_value_available` 20~90 days after the exit), matching `instruments.delisted_on`.
7. Share counts: KR `listed` daily (available at session close), US `outstanding` quarterly (available at filing time) → `share_counts`.
8. Financials: every quarter `fundamentals_events` (facts, 2% amended) and `fundamentals_state` (strict/compare; `equity`, `revenue_ttm`, `net_income_ttm`), availability delay 30~90 days → `dictionary/items`.
9. Classifications: `krx_sector`/`gics_sector` on two time axes, 3% with `ts_known_from` later than `effective_from`, `is_financial` → `classifications`. Index membership `index:KOSPI200` and `index:SP500` → `universe_membership`.
10. Investable: `eligibility_daily` (rule `investable-v1`: common stock, not an administrative-issue stock, a price on that day; the decision uses that day's close, so the availability rule is `session_close` — v2's `session_open` was future information inside the synthetic data itself) [RV-C09].
11. Panels: every month `feature_panels(name=factor_pit_monthly)` with 5 columns (`bm`, `mom_12_1`, `mcap`, `is_investable`, `size_grp`), `label_panels(name=label_monthly)` with 2 columns (`ret_fwd_1m_dl`, `ret_fwd_1m_dl_est`) → `dictionary/columns` (`is_label`).
11a. Market rules (optional): `market_rules` (two versions of the KR tick table, price limits) [V31-05]; `degrade=["volume_in_lots"]` divides KR volume by 100 [V31-16].
12. Exchange rates: daily `fx_rates` for each pair of market currencies (`rate_kind = fixing`, one series; USDKRW for KR+US), published with a 1-session delay, a 2-session delay once a week.
13. Benchmarks: two cap-weighted synthetic TR indices (`IDX:KOSPI_TR`, `IDX:SPX_TR`; built only inside the synthetic data) → `instruments(asset_class=index)` + `bars`.

`EventSpec` (event injection): a dict that uses the column names of a TDS dataset (`corporate_actions`, `delistings`, `fundamentals_events`/`fundamentals_state`, `tradability_daily`) as they are, such as `{"kind": "split", "instrument_id": "KR:T00001", "ex_date": "2020-02-03", "ratio_new_per_old": 2.0}`, plus a `"dataset"` key. When there is an injected event, no random event is made on the same date. The generator's output must be byte-identical for the same arguments (test `test_synth_deterministic`).

`python -m nexusbt.testing.synth --preset P --out DIR [--markets KR,US,ZZ] [--degrade a,b] --validate` runs `tds check --level full` after generating and prints the row counts per dataset, the package `value_sha256` and `semantic_sha256`, and the three profile results.
