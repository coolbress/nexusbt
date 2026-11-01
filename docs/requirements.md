# Requirement status map

Appendix B of the spec (`docs/spec/engine-spec-v3.4.md`) with the repository's status beside it, so that "where is this project, and what is next" can be answered from the repository (spec §2.3, §9.8, ticket T0.12). One row per appendix row, in the appendix's order and words. An id carries the name of its table (`TDS-D1`, `RV-C01`, `V31-01`, `R3-01`, `R4-01`), so the same number in two tables stays apart; a row that covers several ids keeps the appendix's range (`RV-Q08~Q11`, `R3-29~37`, `V31-LS-01~LS-11`). The R4F, R4G, R4H, R5, R6 and R7 items are not mapped in appendix B (spec 10.0), so they are not here either.

Columns:

- **Spec status** (B.1 and B.2 only): appendix B's own word, unchanged. `v1` = implemented by this spec, `changed` = implemented with a corrected meaning, `later` = after v1 (with the reason), `reserved` = name only.
- **Status**: the repository's word. `planned` = a ticket exists and its pull request has not merged; `implemented` = the pull request merged (its number goes in the Ticket column); `deferred` = `later`, `reserved`, a `v1.x` ticket, or no engine ticket at all (the item is the spec's own, the producer's or the TDS document's: R-21, R-44, R-48, TDS-D22, RV-I06, RV-D9, R4-27); `replaced` = appendix B says the item was folded into another id (no row says so today).
- **Ticket**: the representative ticket as appendix B names it, with the GitHub issue number once the issue exists (the M0 tickets and T6.16 today; a range such as `T0.13a~T0.16b` is left as written) and the pull request number once it merges.

The pull request that implements a ticket moves its rows to `implemented` and adds the pull request number (spec §9.5). The spec columns change only when the spec changes; this file never corrects the spec. `tests/docs/test_requirements_map.py` checks that every id of appendix B has exactly one row here.

## B.1 Requirements R, performance P

| Id | Requirement | Section | M | Spec status | Status | Ticket |
|---|---|---|---|---|---|---|
| R-01 | import surface | 3.1, 2.5 | M0 | v1 | planned | T0.2a (#45) |
| R-02 | every feature with daily data alone | 1.1 | M1 | v1 | planned | T1.13 |
| R-03 | zipline names and meanings | 3.3, 3.4 | M1 | v1 | planned | T1.5, T1.9~T1.11 |
| R-04 | column attributes, stubs, typos | 3.2 | M1 | v1 | planned | T1.6 |
| R-05 | user functions in two styles | 3.3 | M1 | changed (window style only; panel later, A-37) | planned | T1.12 |
| R-06 | zipline compatibility layer | 3.4 | M1 | v1 | planned | T1.16 |
| R-07 | declarative Strategy | 3.7 | M3 | changed (no `on_rebalance`, `risk=` slot, A-10, A-46) | planned | T3.2 |
| R-08 | `nx.param` | 3.7 | M3 | v1 | planned | T3.2 |
| R-09 | function and CLI list | 3.8, 3.10 | M5 | v1 | planned | T5.4 |
| R-10 | result object display | 3.9 | M2 | v1 | planned | T2.10a, T3.13a |
| R-11 | counts beside ratios | 3.9 | M2 | v1 | planned | T2.10a |
| R-12 | structure hash, reuse | 5.3.9 (L0·L1) | M6 | changed (semantic key, A-42) | planned | T1.5, T6.4, T6.12 |
| R-13 | screen = backtest | 5.5, INV-08 (anchor) | M3 | changed (A-38) | planned | T3.1, T3.16, T7.1 |
| R-14 | plan pruning | 5.3.2 | M1 | v1 | planned | T1.7a/b |
| R-15 | truncation test | 6.5 | M6 | changed (diagnostic, date priority SC-05, A-25, A-50) | planned | T6.9 |
| R-16 | labels only in target | 6.5 | M2 | v1 | planned | T2.6 |
| R-17 | known_on rule | 5.1 | M2 | changed (`available_at <= decision_ts`, fundamentals_state) | planned | T2.1, T2.2 |
| R-18 | adjustment as of that day | 5.3.3 | M1 | v1 | planned | T1.8 |
| R-19 | units, E5, `.to()` | 3.3, 5.1.5 | M2 | v1 | planned | T2.5 |
| R-20 | reading snapshots directly | chapter 4 (TDS v1) | M1 | v1 | planned | T1.1a/b |
| R-21 | export list | 4.5, 10.2 | E1 | v1 (reference producer side) | deferred | reference producer |
| R-22 | column dictionary | 3.2, 4.6 | M1 | v1 | planned | T1.6 |
| R-23 | trace columns, explain | 4.6, 3.9 | M2 | v1 | planned | T2.11 |
| R-24 | external data known_on | 3.2 | M2 | v1 | planned | T2.6 |
| R-25 | cost table versions | 4.7, 5.6.8 | M3 | v1 | planned | T3.8, T4.5 |
| R-26 | bench suite | chapter 7 | M6 | v1 | planned | T1.24 |
| R-27 | automatic chunking | 5.3.8 | M6 | v1 | planned | T6.5 |
| R-30 | run folder | 5.9 | M1 | v1 (from evaluate) | planned | T1.14a/b |
| R-31 | rerun, determinism | 5.9.4 | M1 | changed (physical/value/semantic hashes, fails without dependencies) | planned | T1.15 |
| R-32 | output in parts | 5.9.1 | M1 | v1 | planned | T1.14a/b |
| R-33 | float32 computation | 3.11 | – | changed (float64, A-18) | planned | T0.5a (#53) |
| R-34 | index, trial count | 5.9.5 | M2 | changed (SQLite, A-43) | planned | T2.9 |
| R-35 | study | 6.2 | M2 | changed (name + UUID, A-04) | planned | T2.9 |
| R-36 | blocking the holdout | 6.1 | M2 | changed (segments, exposure, A-07) | planned | T2.9 |
| R-37 | evaluate report | 5.8 | M2 | v1 | planned | T2.8, T2.10a, T2.16 |
| R-38 | backtest report (including 0×, 1×, 2×) | 5.7 | M3 | v1 | planned | T3.13a, T3.20 |
| R-39 | sweep PBO, DSR, matrix | 6.3 | M6 | v1 | planned | T6.8 |
| R-40 | static check in 1 second | 6.5 | M2 | v1 | planned | T2.12 |
| R-41 | progress display | 3.9 | M6 | v1 | planned | T6.10 |
| R-42 | user exceptions as they are | 6.6 | M1 | v1 | planned | T1.12 |
| R-43 | scope of blocking | 6.6 | M0 | changed (A-01) | planned | T0.4 (#49) |
| R-44 | user experience order | 10.0 | all | v1 | deferred | – |
| R-45 | step-by-step examples | 8.5 | all | v1 | planned | T1.20, T2.14, T3.18, T4.9, T5.6 |
| R-46 | no per-asset arguments | 11.3 | E4 | later (boundary only) | deferred | – |
| R-47 | period windows | 11.3 | E4 | later (A-36) | deferred | – |
| R-48 | engine choice | 11.1 | E4 | changed (`panel` only, A-35) | deferred | – |
| R-49 | ledger adapters | 5.9.6~5.9.7, 11.4 | M5 | v1 (paper), brokers later | planned | T5.1~T5.3, T5.7 |
| R-50 | zipline comparison | 8.1 | M1~M3b | changed (scope narrowed, SC-12, A-57) | planned | T1.17, T1.18, T2.13, T3.17a, T3.17b |
| R-51 | future-information test list | 8.4 | M2, M6 | v1 | planned | T2.6, T6.9, T6.13 |
| R-52 | survivorship, currency, segment tests | 8.4 | M2 | v1 | planned | T2.4, T2.5, T2.9 |
| R-53 | documentation example tests | 8.5 | all | v1 | planned | T1.20 |
| R-54 | automatic truncation | 6.5 | M6 | changed (diagnostic, A-25) | planned | T6.9 |
| R-55 | zipline preset | 5.6.15 | M3 | changed (tests only, A-40) | planned | T3.15a/b |
| R-56 | order types | 3.7, 5.6 | M3 | changed (OHLC rules by hand-calculated tests, A-57) | planned | T3.4~T3.7, T3.17a/b |
| R-57 | segments, no locks | 6.1 | M2 | v1 | planned | T2.9 |
| R-58 | micro-caps | 3.6 | M2 | v1 | planned | T2.4 |
| R-59 | benchmark | 4.6, 5.7 | M4 | v1 | planned | T4.6 |
| R-60 | pay-date estimate | 5.6.11 | M3 | v1 | planned | T3.10 |
| R-61 | provisional costs | 5.6.8 | M3 | v1 | planned | T3.8 |
| R-62 | sleeves, clocks | 5.1.3, 5.6.9 | M4 | v1 | planned | T4.1, T4.2 |
| R-63 | fundamentals_state | 4.6, 5.3.5 | M2 | v1 | planned | T2.2 |
| R-64 | zipline only as oracle | 2.5, 8.1 | M0 | v1 | planned | T0.2a (#45) |
| R-65 | plinth loop | chapter 9 | M0 | v1 | planned | T0.1 (#44), T0.10 (#50) |
| R-66 | TDS as the input contract | chapter 4, 2.3 | M0 | v1 | planned | T0.13a/b (#51, #55), T0.14a~c, T0.15a/b, T1.1a/b |
| R-67 | announcing fallbacks | 4.5 | M1~M3a | v1 | planned | T0.16a/b, T1.1b, T2.2, T2.3, T2.4, T3.10, T3.11 |
| R-68 | market names are data, rules are packs | 4.7, 3.11 | M0, M4 | v1 | planned | T0.5a (#53), T1.1a, T4.4, T4.11 |
| R-69 | public first path (CSV → rerun) | 4.3, 8.5 | M1, M2 | v1 | planned | T1.22, T1.23, T2.17 |
| R-70 | release gate | 9.1, 10.0 | M6 | v1 | planned | T6.15, T6.16 (#8) |
| P1 | import + open 1.5 s | chapter 7 | M1 | v1 | planned | T1.1a/b, T6.11 |
| P2 | screen 2 s | chapter 7 | M3/M6 | v1 | planned | T6.11 |
| P3 | evaluate 5 s / 1 s | chapter 7 | M2/M6 | v1 | planned | T6.11 |
| P4 | daily IC 30 s | chapter 7 | M6 | v1 | planned | T6.11 |
| P5 | backtest 30 s gate / 10 s target | chapter 7 | M6 | changed (A-44) | planned | T6.11 |
| P6 | sweep 120 s / 60 s | chapter 7 | M6 | changed (A-44) | planned | T6.11 |
| P7 | RSS 4 GB | chapter 7 | M6 | v1 | planned | T1.24, T6.11 |
| P8 | static check 1 s | chapter 7 | M2 | v1 | planned | T2.12 |
| P9 | extra time for truncation | chapter 7 | M6 | changed (report only) | planned | T6.9 |
| P10 | comparison tolerance | 8.1 | M1 | changed (A-24) | planned | T1.17, T3.17a/b |

## B.2 Spec changes SC-01~SC-27 (blueprint chapter 13)

| Id | Class | Content | Section | Spec status | Status | Ticket |
|---|---|---|---|---|---|---|
| SC-01 | addition | `risk=` slot, `nx.risk.none`, `TargetFrame.stage/pre_risk_weight` | 1.1, 3.7, 5.5.1–5.5.2 | v1 | planned | T3.1, T3.2 (v1.x T7.3) |
| SC-02 | normative | target-state recursion, anchor, `top(hold=)`, INV-08 wording | 1.3 INV-08, 3.7, 5.5.3, 5.1.3 `anchor_decision_id` | norm v1, implementation v1 (T7.1, the last ticket of M6) | planned | T3.1 (signature, E18), T3.2, **T7.1** |
| SC-03 | normative | kernel numeric rules, INV-03·04 wording, INV-13 | 1.3, 3.4, 5.3.10, ADR-0019 | v1 | planned | T1.7a/b, T1.11, T1.19, T6.2, T6.3 |
| SC-04 | addition | P-START, M-SCALE·DUMMY·SPLIT-NEUTRAL·CCY·SLEEVE, `check(start_probe=)`, E32 | 1.3 INV-14·15, 6.5, 8.3 | v1 | planned | **T1.21**, T4.8, **T6.13** |
| SC-05 | normative | probe date priority, comparison nodes, finite-cell report | 6.5 | v1 | planned | T6.9 |
| SC-06 | addition | `scenarios` name list, `capacity` | 3.8, 5.7, 5.9.1 | v1 | planned | T3.13b (arguments), **T6.14** |
| SC-07 | addition | `attribution.parquet`, `exposures.parquet`, `fx contribution` line | 3.9, 5.6.9, 5.7, 5.9.1 | v1 (Brinson v1.x) | planned | T3.14 (costs), **T4.10**, T4.7 (Brinson T7.5) |
| SC-08 | addition | breadth, expected IR (evaluate), transfer coefficient (backtest) | 5.7, 5.8, 3.9 | v1 | planned | **T2.16**, **T3.20** |
| SC-09 | addition | BHY, MinTRL, Lo Sharpe, drawdown duration, recovery, worst month | 5.7, 5.8, 6.3 | v1 | planned | **T2.16**, **T3.20** |
| SC-10 | addition | N_eff, DSR(N_eff) | 5.7, 6.3 | v1.x | deferred | **T7.2** |
| SC-11 | addition | fill record columns, general impact form, manifest of every knob, appendix C | 3.7, 5.6.2, 5.6.4, 5.6.8, 5.9.1–5.9.2, appendix C | v1 | planned | T3.4, T3.6, T3.8, T3.14 |
| SC-12 | normative | narrowed zipline comparison scope, L2-d, preset trigger line | 1.4 R-56, 5.6.15, 8.1, ADR-0021 | v1 (user decision 2026-10-28 (OI-20) [R6-03]) | planned | T3.15a/b, T3.17a/b |
| SC-13 | addition | `explain(strategy)`, `Run.why` | 3.8, 3.9, 5.9.9 | v1 | planned | **T3.19**, **T5.9** |
| SC-14 | addition | `reconcile`, `status.json`, exit code 4 | 3.8, 3.10, 5.9.6–5.9.7 | v1 | planned | **T5.7**, T5.4 |
| SC-15 | addition | L0 raw block cache, P7 USS | 5.3.9, 7, ADR-0025 | v1 | planned | T1.4 (key), **T6.12**, T6.4 |
| SC-16 | addition | ecosystem adapters, evaluate `signal.parquet` | 2.3, 3.9, 5.8, 5.9.8 | v1 | planned | **T5.8** |
| SC-17 | implementation | `[taxes]` user-configured taxes | 3.11, 5.6.11a | v1 | planned | T0.5a (#53), T4.5b |
| SC-18 | reserved | `[settlement] model` | 1.1, 3.11, 5.6.7 | reserved | deferred | T0.5a (#53) |
| SC-19 | reserved | `fit_segment`, E29 | 1.1, 6.5, 6.6 | reserved | deferred | T0.4 (#49), T2.9 |
| SC-20 | normative | `ts_label_start/end`, generalised purging, triple barrier = exit decision | 3.7, 4.6, 5.8 | v1 | planned | T2.7 |
| SC-21 | reserved | `splits=`, `nx.splits.*` | 3.1, 3.8, 6.3 | reserved | deferred | T2.9 |
| SC-22 | reserved | `nx.risk`, `nx.portfolio.optimize`, `[opt]` | 1.1, 2.2, 2.3, 5.3.10(6), 5.5.2 | reserved | deferred | T0.2a (#45) (names) |
| SC-23 | addition | `coverage.parquet` columns, eligible vs tradable | 1.2, 3.6, 5.9.1 | v1 | planned | T2.4, T3.14 |
| SC-24 | normative | chapter 4 → TDS references, renames | all of chapter 4, the whole spec | v1 | planned | T0.13a~T0.16b, T1.1a/b |
| SC-25 | reserved | `clock = "utc:HH:MM"` | 1.2, 3.11, 11.3 | reserved | deferred | T0.5a (#53), T4.1 |
| SC-26 | addition | numeric environment record | 5.9.2 | v1 | planned | T1.14a/b |
| SC-27 | addition | `rerun --trust`, no secret keys, no pickle | 2.5, 2.6, 3.10, 3.11, 5.9.3 | v1 | planned | T0.2a (#45), T0.5a (#53), T1.14a/b, T1.15 |

## B.3 TDS differences D1~D24 → where this spec reflects them [SC-24]

| Id | Content | Where reflected | Status | Ticket |
|---|---|---|---|---|
| TDS-D1 | `security_id` → `instrument_id` (v3: no alias) | header, 3.1, throughout | implemented | T0.3 (#48, PR #71) |
| TDS-D2 | `*_utc` → `ts_*` | throughout, 5.9 outputs | planned | T0.3 (#48), T1.14a/b |
| TDS-D3 | `manifest.json`+`columns.json` → `tds.json`+`dictionary/` | 4.1, 4.4, 3.2 | planned | T0.13a/b (#51, #55), T1.1a/b, T1.6 |
| TDS-D4 | time unit us/ns | 4.6, 11.3 | planned | T0.13a/b (#51, #55) |
| TDS-D5 | `country=` → `market=` | 4.6 | planned | T1.4 |
| TDS-D6 | `instruments` | 4.6, 3.2 `Meta` | planned | T0.6 (#58), T1.6 |
| TDS-D7 | `instrument_symbols` + `instrument_xref` | 4.6 | planned | T0.6 (#58) |
| TDS-D8 | price limits and rule edition removed from the session table | 4.6, 5.6.5 | planned | T4.4 |
| TDS-D9 | `shares_out` → `share_counts`, factor names | 3.2, 5.3.3, 5.3.5a | planned | T2.15, T1.8 |
| TDS-D10 | `tradability_daily` columns, `trading_status_events` | 4.6, 5.6.5 | planned | T3.5a/b |
| TDS-D11 | `corporate_actions` columns and kinds | 4.6 correspondence table, 5.3.3–5.3.4, 5.6.10–5.6.12 | planned | T3.9–T3.11, T1.8 |
| TDS-D12 | `classifications` two time axes | 4.6, 5.1.5, 5.3.6 | planned | T2.1, T2.3 |
| TDS-D13 | `delistings` | 4.6, 5.6.13 | planned | T3.11 |
| TDS-D14 | `fundamentals_state` + `fundamentals_events` | 4.6, 5.3.5, 3.9 Explanation | planned | T2.2, T2.11 |
| TDS-D15 | benchmark = index instruments + bars | 4.6, 3.11, 5.7 | planned | T4.6 |
| TDS-D16 | `eligibility_daily` + `universe_membership` | 3.6, 4.6, 5.1.5 | planned | T2.3, T2.4 |
| TDS-D17 | `fx_rates` | 4.6, 3.11 `[fx] series`, 5.1.5, 5.6.9 | planned | T2.5, T4.2 |
| TDS-D18 | `feature_panels`/`label_panels` `name=` | 3.2, 3.11 `[panels]`, 4.6 | planned | T2.3, T2.7 |
| TDS-D19 | value hash (v2 logical hash) includes partition columns | 4.2, 5.9.4 | planned | T0.14c (#57) |
| TDS-D20 | no partition columns inside files | 4.6 | planned | T0.13a/b (#51, #55), T1.4 |
| TDS-D21 | checker stages and codes, E14 carries the TDS code | 4.4, 6.6 E14 | planned | T0.13a~T0.15b, T1.1a/b |
| TDS-D22 | `LATEST` and `PINS` are outside the standard | 4.2 | deferred | reference producer |
| TDS-D23 | `kr_price_limits_v1.csv` kept as an engine resource | 4.7 | planned | T4.4 |
| TDS-D24 | the synthetic generator is a TDS package, `test_synth_conforms` | 4.8, INV-17 | planned | T0.6~T0.8c, T0.16a/b |

## B.4 Three-reviewer review consensus RV → where this spec reflects it [`review/consensus.md`]

| Id | Priority | Content | Where reflected | Status | Ticket |
|---|---|---|---|---|---|
| RV-C01 | P0 | account information at decision time (delisting recovery) | INV-01, 5.1.5, 5.6.9, 5.6.13 | planned | T3.3, T3.11, T3.Gc(G-42) |
| RV-C02 | P0 | stage order, late bar `ready` | 5.1.2, 5.2, 5.6.3 | planned | T1.3, T4.1, T4.G(G-50), T1.G(T-20) |
| RV-C03 | P0 | corporate-action resolver | 5.3.3a, 5.3.4, 5.3.5a, 4.6, 5.6.10~5.6.12 | planned | T0.15a, T0.15b, T1.8, T3.9~T3.11 |
| RV-C04a | P0 | three label times, purging | 5.8, 4.6 | planned | T2.7, T2.G(T-22) |
| RV-C04b | P1 | economic label default | 5.8, 3.8, 3.11 | planned | T2.7, T2.G(T-21) |
| RV-C05 | P0 | order life, trigger persistence, quantity conservation, exit orders | 3.7, 5.6.2, 5.6.2a, 5.6.4, INV-18, appendix C | planned | T3.4, T3.6, T3.7, T3.Gb |
| RV-C06 | P0 | buyable quantity, intraday funds | 5.6.3, 5.6.7 | planned | T3.5b, T3.6, T3.8 |
| RV-C07 | P0 | integer minor units, NAV bridge, cost attribution, annual linking | INV-06, 5.6.1, 5.6.8, 5.6.9, 5.7, 5.9.1 | planned | T3.3, T3.14, T4.10 |
| RV-C08 | P0 | rectangular lookup, keys, after-the-fact attributes | 3.2, 4.6, 5.3.6 | planned | T0.14a/b, T2.1, T2.3 |
| RV-C09 | P0 | missing eligibility = false, strict quality | 3.6, 4.4, 5.1.5, 4.8(10) | planned | T0.7, T2.1, T2.4 |
| RV-C10a | P0 | three hashes (physical, value, semantic) | 1.2, 4.2, 5.3.9, 5.9.2, 5.9.4 | planned | T0.14c (#57), T6.12, T6.4 |
| RV-C10b | P1 | cache dependencies (captured constant globals, external inputs, query policy) | 5.3.7, 5.3.9, 6.5 | planned | T1.5, T1.12, T6.4 |
| RV-C11 | P0 | property premises, `every` anchor, leakage tests, numeric grades | INV-03·11·13~15, 3.7, 5.3.10, 8.3, 8.4 | planned | T1.3, T1.7b, T1.19, T1.21, T4.8, T6.2, T6.9 |
| RV-C12 | P1 | candidates, observations, cohorts | 1.2, 5.7, 5.8, 5.9.5, 6.2, 6.3 | planned | T1.14b, T2.9, T2.16, T6.8 |
| RV-C13 | P0 | ledger idempotency, transactions, replay/restatement | 5.9.6, 5.9.7, INV-19 | planned | T5.1, T5.2, T5.3, T5.7 |
| RV-I01 | P1 | capability contract (three outcomes, graph dependency requirements, profile edition, path safety, `cum_factor` choice) | 4.1, 4.3, 4.4, 3.11 | planned | T0.13a/b (#51, #55), T1.1a/b |
| RV-I02 | P1 | return series default `close_tr` | 3.4, A-105, 8.1 | planned | T1.9, T1.10, T1.16, T1.17 |
| RV-I03 | P1 | public first path (CSV, minimal-daily analysis, English quick start) | 1.1, 4.3, 4.6, 8.5 | planned | T1.22, T1.23, T2.17 |
| RV-I04 | P1 | artifact schema, pins, stamps, rerun in a new process, seal recovery | 4.2, 4.4, 5.9.1~5.9.3 | planned | T1.14a/b, T1.15, T3.14 |
| RV-I05 | P1 | ticket graph, M0 reduction, golden location, early measurement, suites under one year | 5.3.8, 7, 8.2, chapter 10 | planned | all of chapter 10, T0.12 (#46), T1.24 |
| RV-I06 | P1 | `std_item` provisional, `preliminary` | TDS v1.1 5.17 | deferred | (TDS document) |
| RV-I07 | P1 | stable scope, release gate, RC | 1.1, 2.3, 9.1, 10.0, 11 | planned | T0.13b (#55), T6.15, T6.16 (#8) |
| RV-I08 | P1 | market names are data, rules packs | 1.2, 3.6, 3.8, 3.11, 4.4, 4.7, 5.1.3, 5.6.5 | planned | T0.5a (#53), T1.1a, T4.4, T4.11 |
| RV-I09 | P2 | producer-neutral errors, `producer.hints` | 3.10, 4.4, 4.5, 6.6 | planned | T0.2b (#47), T0.4 (#49), T1.1a |
| RV-I10 | P1 | column-array state, Numba conditional | 5.6.1, 2.4, 7 | planned | T3.3, T3.4, T6.6 |
| RV-Q01 | P2 | removing the `security_id` alias | header, 3.1, A-73 | implemented | T0.3 (#48, PR #71) |
| RV-Q02 | P2 | honest report wording | 3.8, 3.9, 5.7, 5.8 | planned | T3.13a/b, T3.20, T2.16 |
| RV-Q03 | P2 | missing tickets, small fixes | 2.7, 6.4, 6.6, 11 | planned | T0.2b (#47), T2.18, T3.21, T6.17 |
| RV-Q04 | P2 | public TDS hygiene, `nexusbt_tds` | header, 2.3, TDS v1.1 | planned | T0.1 (#44), T0.2b (#47) |
| RV-Q05 | P2 | public release tickets (PyPI by the user) | 1.1, chapter 12 OI-44·45 | planned | T0.1 (#44), T6.15, T6.16 (#8) |
| RV-Q06 | P2 | cross-section default domain, E34 | 3.3, 5.3.1, 5.4.2, 6.5 | planned | T1.4, T2.12 |
| RV-Q07 | P2 | `cost_reserve_bps` | 3.11, 5.6.7, appendix C | planned | T3.5b |
| RV-Q08~Q11 | P2 | interoperability sentence, `ts_exit_known` null, `availability_by_column`, keeping `fail` | TDS v1.1, 4.6, chapter 12 OI-09 | planned | (TDS document), T0.7 |
| RV-D1 | – | window kernel definition A/B | 5.3.10, ADR-0019, OI-47 | planned | T1.24, T6.2 |
| RV-D2 | – | default label | 5.8, OI-48 | planned | T2.7 |
| RV-D3 | user | hold band timing | OI-12 | planned | T7.1 |
| RV-D9 | – | M3a/M3b | 10.0 | deferred | chapter 10 |

## B.5 Teardown of engines on the market V31 → where this spec reflects it [`teardown/MATRIX.md`]

| Id | Item | Priority | Where reflected | Status | Ticket |
|---|---|---|---|---|---|
| V31-01 | integer quantity arithmetic | P0 | INV-18, 4.6, 5.6.1, 5.6.7, 5.6.10, 5.6.12, TDS 5.11 | planned | T0.15c, T0.16c, T3.Gd, T3.9, T3.5b, T3.11 |
| V31-02 | stale valuation-price adjustment | P0 | INV-06, 5.6.3(6), 5.6.7, 5.6.9, 5.6.13 | planned | T3.Gd, T3.22 |
| V31-03 | that day's volume cap | P0 | INV-01, 5.6.6, 3.11 | planned | T3.Gd, T3.5b |
| V31-04 | distributions just before delisting | P1 | 5.6.13, 4.6, TDS 5.13 | planned | T0.15c, T3.22 |
| V31-05 | price grid, rounding | P1 | INV-20, 3.7, 4.5 F-15, 4.7, 5.6.1, 5.6.4a, 5.6.5, 5.6.8, TDS 5.27 (v3.2 comparison coordinates R3-02, KR rounding R3-27) | planned | T3.Gf, T3.24, T3.23, T4.4, T0.15d, T0.5b (#54) |
| V31-06 | filtering small orders | P1 | 3.7, 3.11, 5.6.7 | planned | T3.25 |
| V31-07 | metrics by hand calculation, kurtosis | P1 | 5.7, 8.2 G-60 | planned | T3.Ge, T3.13a, T3.20, T6.8 |
| V31-08 | no non-deterministic sources | P1 | INV-09, 2.5, 8.3 P-DET | planned | T1.27 |
| V31-09 | E4 backend boundary | P1 | 11.1, ADR-0017 | planned | T6.17 |
| V31-10 | live preflight check | P1 | 5.9.6, 3.9, 3.11, E36 | planned | T5.12 |
| V31-11 | sleeve independence | P1 | INV-21, 5.3.8, 7 | planned | T4.8, T6.11 |
| V31-12 | partition cache key | P1 | 5.3.9, 7 P2b, TDS 4.2 (v3.2 key fix R3-04) | planned | T0.14c (#57), T1.4, T6.12, T6.4 |
| V31-13 | market-level series | P1 | 3.2, 3.3, 5.1.5, 5.3.2 | planned | T2.Gb, T2.19 |
| V31-14 | target gap, execution quality | P1 | 5.6.7, 5.6.8, 5.7, 5.9.1, E37 | planned | T3.Gd, T3.26 |
| V31-15 | benchmark | P1 | 5.7, 3.9, TDS 5.1 | planned | T3.Ge, T4.6, T4.12 |
| V31-16 | volume units | P1 | 4.5 F-16, 4.6, TDS 3.4·5.5 | planned | T0.15d, T1.1b |
| V31-17 | hold band boundary | P1 | 3.7, 5.5.3, 5.6.7 | planned | T7.G, T7.1 |
| V31-18 | ledger with human intervention | P1 | 3.8, 5.6.5, 5.9.6, 5.9.7 | planned | T5.10, T5.11a, T5.11b |
| V31-19 | deposits and withdrawals, TWR | P1 | INV-06, 5.6.9, 5.7, 5.9.6 | planned | T5.G, T5.13 |
| V31-20 | trade table | P1 | 5.9.1, 3.9 | planned | T5.G, T5.14 |
| V31-21 | three-valued Filter | P1 | 3.3, 5.4.1, 8.1 | planned | T1.Gb, T1.25, T1.18 |
| V31-22 | fill causality | P1 | INV-01, 8.3 | planned | T3.16 |
| V31-23 | drawdown boundary | P1 | 5.7 | planned | T3.Ge, T3.20, T3.13a |
| V31-24 | built-in factors by hand calculation, 3.4/8.1 | P1 | 3.4, 8.1 | planned | T1.Gb, T1.9, T1.10 |
| V31-25 | percentile composites | P1 | 3.3, 5.4.2 | planned | T2.Gb, T2.20 |
| V31-26 | date luck, rolling | P1 | 3.8, 5.7, 6.2 | planned | T6.18 |
| V31-27 | provisional cost table (optional) | P1 | 3.7, 5.6.8, 4.7 | planned | T4.13 |
| V31-28 | X-Ray | P1 | 3.8, 3.9, 5.9.9 | planned | T5.15 |
| V31-29 | tie-breaking | P1 | 3.7, 5.5.3, 5.6.15 (v3.2 fixed salt R3-12) | planned | T1.Gb, T1.11, T3.1 |
| V31-30 | `Trad`, exclusions | P1 | 3.2, 3.6, 4.3 | planned | T2.21 |
| V31-33 | no copying from PyBroker | P2 (applied by instruction) | 2.1 | planned | T0.1 (#44) |
| V31-PUB-01~03 | producer-specific packages, path linking | user decision | 4.2, 3.8 `open`, 3.11 `[data] path`, 5.3.9, 10.2, TDS 4.1 | planned | T1.1a |
| V31-LS-01~LS-11 | short selling, long–short | user decision | header, 1.1~1.3, 3.7, 3.11, 4.7, 5.5, 5.6, 5.7, 5.9, 6.6, 8.1~8.3, 11.1, A-117 | planned | T4.Gs, T4.Gt, T4.17, T4.14, T4.15a~c, T4.16a·b, T4.18, T4.19, T5.14, T7.1 |

## B.6 Third round R3 of the three-reviewer review → where this spec reflects it [`review/consensus-r3.md`]

| Id | Item | Priority | Where reflected | Status | Ticket |
|---|---|---|---|---|---|
| R3-01 | resolver existence and terms times | P0 | INV-01, 1.2, 5.1.5, 5.3.3a(2)(4)(9)(10), 5.3.4, 5.6.11, 8.2 G-20, 8.3 P-FUT, TDS 5.11 | planned | T0.15a, T3.Gc, T3.10, T4.15b |
| R3-02 | integer comparison in minor units | P0 | INV-20, 1.1, 1.2, 4.6, 4.7 `base_unit`, 5.6.4a, 8.2 G-57 (f)(h), 8.3 P-GRID, TDS 5.27 | planned | T0.5b (#54), T0.15d, T3.Gf, T3.24 |
| R3-03 | volume-cap sentence, P-FILLCAUSAL | P0 | INV-01, 3.9, 5.6.6, 5.9.2, 8.3 | planned | T3.5b, T3.13a, T3.16 |
| R3-04 | cache key | P0 | INV-05, 4.2, 5.3.9, 3.11 `cache_max_gb`, 7 P2b, 8.3 P-CACHE-INCR, ADR-0025, TDS 4.2 | planned | T0.15a, T1.4, T6.4, T6.11, T6.12 |
| R3-05 | terminal value on three bases | P0 | 4.6, 5.6.9, 5.6.13, 8.2 G-55, TDS 5.13 | planned | T3.Gd, T3.22 |
| R3-06 | ratio fitting | P0 | 4.3, 4.4-4, 5.6.1, 6.6 E13·E30, 8.2 G-53, ADR-0034, TDS 5.11 | planned | T0.15c, T1.1a, T3.Gd, T3.9 |
| R3-07 | exposure stage, INV-22 | P0 | INV-22, 3.7, 3.11, 5.5.2, appendix C | planned | T0.5a (#53), T4.14 |
| R3-08 | long–short target, feasible region | P0 | 1.1, 3.7, 5.6.7, 8.2 G-72, 11.1 | planned | T0.5a (#53), T4.Gt, T4.14 |
| R3-09 | short accounting, ruin | P0 | header, INV-06, 1.1, 1.2, 3.9, 3.11, 4.7, 5.6.1, 5.6.2, 5.6.3, 5.6.7, 5.6.9, 5.6.11, 5.6.11a, 5.6.13, 5.7, 5.9.1, 5.9.6, 6.6 E38, 8.2 G-67·68·70·76, ADR-0036 | planned | T4.Gs, T4.15a, T4.15b |
| R3-10 | mirroring the short life cycle | P0 | INV-18, 1.1, 3.7, 5.6.2, 5.6.2a, 5.6.3, 5.6.4, 5.6.6, 5.6.7, 8.2 G-73 | planned | T3.7, T4.Gt, T4.16a, T4.16b |
| R3-11 | P-SHORT-OFF | P1 | INV-22, 5.9.1, 8.3 | planned | T3.14, T4.17, T4.14, T4.16a |
| R3-12 | fixed tie salt | P1 | 3.3, 3.7, 5.4.2, 8.1, 8.2 T-11·T-27, appendix C | planned | T1.Gb, T1.11, T3.1 |
| R3-13 | completing the three-valued Filter | P1 | 1.2, 3.3, 3.5, 5.3.9, 5.4.1, 5.9.1, 6.6 E39, 8.2 T-24 | planned | T0.4 (#49), T1.25, T2.22, T6.4 |
| R3-14 | grid seed, bars off the grid | P1 | 4.7, 5.6.4a, 8.2 G-57 (g) | planned | T0.5b (#54), T3.24, T6.15 |
| R3-15 | rule validation gate, forbidden syntax | P1 | R-70, 4.6, 4.7, 5.6.5 | planned | T0.5b (#54), T4.16b, T6.15 |
| R3-16 | snapshot immutability, file identity | P1 | header, 3.11, 4.2, 4.4, 5.3.9, 10.2, ADR-0037, TDS 4.1 | planned | T1.1a, T1.1b, T6.12 |
| R3-17 | pin default, retention state | P1 | 3.11, 4.2, 5.9.2, 5.9.6, 10.2 | planned | T0.5a (#53), T1.1b, T1.2, T5.1 |
| R3-18 | default market order | P1 | 1.2, 3.11, 5.1.3, 5.9.2 | planned | T0.5a (#53), T1.3 |
| R3-19 | ledger TWR CAGR | P1 | 1.1, 5.7, 5.9.6, 8.2 G-65 (b) | planned | T3.13a, T5.13 |
| R3-20 | report formulas | P1 | 5.6.7, 5.6.9, 5.6.11a, 5.7, 5.9.1, 8.2 G-75 (b) | planned | T3.26, T4.10, T4.15c, T5.14 |
| R3-21 | ledger context, manual protocol | P1 | 3.8, 5.9.1, 5.9.6, 5.9.9 | planned | T5.10, T5.11a, T5.11b, T5.15 |
| R3-22 | hold band state | P1 | 5.5.3, 5.6.1, 8.2 G-63, ADR-0020 | planned | T5.16, T7.G, T7.1 |
| R3-23 | ticket split, T7.V | P1 | 10.0, 10.1 | planned | T0.12 (#46), T7.V (all the split tickets) |
| R3-24 | PBO common period | P1 | 6.3, 12.1 V31-38 | planned | T6.8 |
| R3-25 | cash interest | P1 (user decision) | header, 1.1, 3.9, 3.11, 5.6.3, 5.6.9, 5.7, 8.2 G-77, 12 OI-50 | planned | T0.5a (#53), T4.Gs, T4.19 |
| R3-26 | Rust seam | P1 (user decision) | header, chapter 0, 2.4, 5.3.10, 5.6.1, 7, 11.2, ADR-0016, 12 OI-53 | planned | T1.7b, T3.3, T3.4, T6.2, T6.6 |
| R3-27 | KR rounding `down` | P2 (applied at the user's instruction) | 4.7, 8.2 G-58, ADR-0035 | planned | T0.5b (#54), T3.23 |
| R3-28 | TDS K1 example | P2 (cheap contradiction, applied) | TDS 2.2 K1 | planned | T6.15 |
| R3-29~37 |  | P2 | 12.1 (deferred; for 37 only the reasoning sentence was fixed) | deferred | – |

## B.7 Round 4 topics R4 → where this spec reflects them [`review/round4-topics.md`]

| Id | Item | Priority | Where reflected | Status | Ticket |
|---|---|---|---|---|---|
| R4-01 | nine-slot block contract table, four promises | P0 | 3.7 | planned | T3.27, T3.29, T3.31 |
| R4-02 | money-management slot, built-in sizers, `top(weight=)` trimmed | P0 | 1.1, 2.3, 3.1, 3.7, 5.5.1, 5.5.1a | planned | T3.27 |
| R4-03 | ERC fixed-order coordinate descent, defined fallback | P1 | 5.5.1a, 6.6 E43 | planned | T3.28 |
| R4-04 | risk-list slot, two layers canonical/final, INV-23 | P0 | 1.3, 5.5.1, 5.5.2, 5.5.2a, 5.5.3, 5.6.7, 8.3 | planned | T3.29, T3.30 |
| R4-05 | built-in risk blocks (group cap v1) | P0 | 1.1, 5.5.2 | planned | T3.29, T3.30 |
| R4-06 | drawdown brake shadow-index re-entry | P0 | 5.5.2a, 8.2 G-84 | planned | T3.30 |
| R4-07 | user blocks `@nx.portfolio`·`@nx.sizer`·`@nx.risk_rule` | P0 | 3.1, 3.7, 3.8, 6.6 E41 | planned | T3.27, T3.29, T3.31 |
| R4-08 | screen account: not evaluated / `--ledger` / `--as-backtest` | P0 | 3.8, 3.10, 6.6 E42 | planned | T5.17 |
| R4-09 | risk waterfall | P1 | 5.5.2a, 5.9.1 | planned | T3.29 |
| R4-10 | `exits.time_stop` v1 | P1 | 1.1, 3.7, 12.1 | planned | T3.33 |
| R4-11 | `strategy.replace`, `compare` variant table | P1 | 3.7, 3.8, 3.10 | planned | T3.34, T5.20 |
| R4-12 | `backtest --preview` | P1 | 3.8, 3.10, 3.11 | planned | T3.34 |
| R4-13 | 20 templates, `init --demo`, 30-minute path, output comparison | P1 | 3.10, 8.5 | planned | T5.18, T6.27 |
| R4-14 | zipline → NexusBT mapping document | P1 | 8.5 | planned | T5.19 |
| R4-15 | error layer line | P0 | 6.6 | planned | T0.4b (#52) |
| R4-16 | no internal terms, layer golden, user exception note | P1 | 6.6, 8.4b | planned | T0.4b (#52) |
| R4-17 | no silent failures (`skips.parquet`) | P0 | 5.9.1, 6.6, 8.3 | planned | T3.32 |
| R4-18 | P11 high-dimensional work, design tools | P1 | 7 | planned | T6.26, T6.11 |
| R4-19 | splitters, purging by label publication time, AFML embargo | P0 | 1.1, 3.8, 3.11, 5.8, 6.3, 6.3a | planned | T6.19 |
| R4-20 | entry point `backtest(method=…)`, validation account | P0 | header, 3.8, 3.10, 6.1, 6.3a | planned | T6.20, T6.21 |
| R4-21 | trial counting (folds, path diagnostics), `sweep` trimmed | P0 | 6.2, 6.3, 6.3a | planned | T6.20, T6.21 |
| R4-22 | path statistics, hygiene first screen | P1 | 3.11, 6.3a | planned | T6.21, T6.22 |
| R4-23 | `nx.ml.factor` | P0 | 1.1, 2.3, 3.1, 3.8, 5.3.11, 6.5, 6.6 | planned | T6.23, T6.24 |
| R4-24 | `labels.triple_barrier` v1 | P1 | 3.7, 5.8 | planned | T6.25 |
| R4-25 | new errors E40~E46 | P1 | 6.6 | planned | T0.4b (#52) |
| R4-26 | tests G-78~G-93, seven properties, error layer tests | P0 | 8.2, 8.3, 8.4b | planned | T3.Gr, T6.Gv |
| R4-27 | tickets 188 → 210 | – | 10.0, 10.1 | deferred | – |
| R4-28 | tidying the reserved list | P1 | 3.1, 6.6 E18 | planned | T0.4b (#52) |
