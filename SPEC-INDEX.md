# Spec index: milestone → ticket → spec section → tests

Generated from `docs/spec/engine-spec-v3.4.md` (chapter 10) by the spec checker (`tools/spec_lint.py`). Use it in `/to-tickets` and `/implement` sessions to open only the sections a ticket needs. If this file and the spec disagree, the spec wins; regenerate this file.

- **§** = section of the engine spec. **TDS x.y** = section of the data standard (`docs/tds/tds-v1.4.md`; examples in `docs/tds/tds-examples.md`; Korean translations `*.ko.md`).
- **Tests** = hand-computed golden cases (`G-NN`, spec 8.2, `tests/golden/`), property tests (`P-NAME`, spec 8.3, `tests/property/`), point-in-time cases (`T-NN`, spec 8.4). A golden ticket (`T<m>.G…`) is written and merged in a separate session *before* the ticket that consumes it.
- Every ticket also lists its acceptance test names in the spec; those are the red tests to write first.
- Milestone end conditions and the command to show at the end of each milestone: spec 10.0.

## Counts

219 engine tickets: M0 16, M1 40, M2 30, M3a 37, M3b 11, M4 28, M5 24, M6 31, v1.x 2 (T7.G, T7.1 and T7.V are part of M6; T7.2 and T7.5 are v1.x). 107 golden cases (G-01..G-107), 34 property tests, 49 error codes (E1..E49), 40 ADRs.

## Dependency graph (summary)

- Acyclic; every "Blocked by" points to the same or an earlier milestone (checked by `tools/spec_lint.py`, and in the repo by `test_ticket_graph`, T0.12).
- Single root: T0.1. Longest chain: 33 tickets:
  T0.1 → T0.2a → T0.13a → T0.13b → T0.13c → T0.14a → T0.15a → T0.15b → T0.16a → T1.1b → T1.3 → T1.4 → T1.7a → T1.7b → T1.8 → T1.12 → T1.13 → T2.7 → T3.22 → T3.12 → T4.1 → T4.2 → T4.10 → T4.7 → T6.2 → T6.4 → T6.7 → T6.20 → T6.21 → T6.24 → T6.27 → T7.1 → T7.V.
- Most depended-on tickets (number of direct dependents): T0.9 (19), T3.13a (10), T3.14 (9), T0.15a (7), T2.9 (7), T3.Gd (7), T0.2a (6), T2.10a (6), T4.7 (6), T0.14c (5), T1.Gb (5), T1.11 (5), T1.13 (5). Land these early and keep them small.


## M0 — Normative contracts

| Ticket | Title | Spec sections | Tests | Blocked by |
|---|---|---|---|---|
| T0.1 | `docs: add spec v3.4, TDS v1.4, CONTEXT.md, ADRs, license and contributor files` | 2.1, 9.1~9.3 | — | — |
| T0.2a | `chore: workspace skeleton with layer and ban rules` | 2.3–2.6 | — | T0.1 |
| T0.2b | `test(repo): public hygiene and public-name tests` | 2.7, 3.1 | — | T0.2a |
| T0.3 | `feat(contracts): id constant, engine column sets, phases and artifact schema versions` | 2.4, 4.6, 5.6.3 | — | T0.2a |
| T0.4 | `feat(contracts): teaching error classes E1..E39 and message format` | 6.6 | — | T0.2a |
| T0.4b | `feat(contracts): error layer line, layer table, internal-term ban and engine-bug report` | 6.6, 8.4b | — | T0.4 |
| T0.5a | `feat(config): load and validate nexusbt.toml keys with resolved defaults` | 3.11, 2.6, 5.1.3 | — | T0.3 |
| T0.5b | `feat(config): market rules packs, grid units and seed tables with verification flags` | 4.7 | — | T0.5a |
| T0.10 | `ci: add engine and tds check jobs` | 9.1 | — | T0.2a |
| T0.12 | `docs: requirement status map and ticket graph check` | 10 | — | T0.1 |
| T0.13a | `feat(tds): manifest-level checker, profile results, path safety and CLI` | 2.6, 4.3, 4.4, 8.4a, TDS 4 | — | T0.2a |
| T0.13b | `feat(tds): schema files with stability status and table verification` | TDS 5 | — | T0.13a |
| T0.13c | `feat(tds): schema-level checks with S-code conformance packages` | TDS 8 | — | T0.13b |
| T0.14c | `feat(tds): canonical value hash, semantic hash and published test vectors` | 4.2, 5.9.4, TDS 4.5 | — | T0.13b |
| T0.6 | `feat(testing): synthetic TDS package part 1 - hand-authored tiny and small calendars, instruments, symbols, bars` | 4.8 | — | T0.3, T0.13c, T0.14c |
| T0.9 | `test(golden): golden case format, literal-arithmetic checks, guard and G-01` | 8.2 | G-01 | T0.6 |

## M1 — Snapshot + Pipeline slice + first public path

| Ticket | Title | Spec sections | Tests | Blocked by |
|---|---|---|---|---|
| T0.7 | `feat(testing): synthetic TDS package part 2 - corporate actions with revisions, delistings, tradability, eligibility, share counts` | 4.8 | — | T0.6 |
| T0.14a | `feat(tds): full-level key and reference checks` | TDS 8.3 | — | T0.13c |
| T0.14b | `feat(tds): full-level time and density checks with rectangle lookup` | TDS 6.3 | — | T0.14a |
| T0.15a | `feat(tds): corporate action resolver parameterized by knowledge cutoff` | 5.3.3a, TDS 5.11 | — | T0.14a |
| T0.15b | `feat(tds): adjustment and value checks via the resolver` | TDS 5.11 | — | T0.15a |
| T0.16a | `feat(testing): degraded synthetic packages for core fallbacks` | 4.5, 4.8 | — | T0.7, T0.15b |
| T1.G | `test(golden): time and pipeline cases for M1 (T-07, T-09..T-12, T-15, T-20, T-23)` | 8.2 | T-07, T-09, T-12, T-15, T-20, T-23 | T0.9, T0.7 |
| T1.1a | `feat(data): open TDS snapshots with checker, producer-neutral errors and market rules packs` | 4.1–4.4, 4.7 | — | T0.3, T0.4, T0.5b, T0.13c, T0.14c, T0.6 |
| T1.1b | `feat(data): capabilities, profile results, core fallbacks and pins` | 4.3–4.5, 4.2 | — | T1.1a, T0.16a |
| T1.2 | `feat(cli): nexusbt init and doctor` | 3.10 | — | T1.1b |
| T1.3 | `feat(data): calendars, session rounding, ready times, phases and decision grids` | 5.1.2, 5.1.3, 5.1.6, 5.6.3, 3.7 | T-10 | T1.1b, T1.G |
| T1.4 | `feat(data): dense market blocks from daily bars` | 5.3.1, 4.6, 5.3.9 | — | T1.3 |
| T1.5 | `feat(pipeline): term value objects, operators, graph hash and captured constants` | 3.3, 5.3.9, 6.5 | — | T0.2a |
| T1.6 | `feat(pipeline): datasets from TDS dictionaries and type stubs` | 3.2 | — | T1.1b, T1.5 |
| T1.7a | `feat(compute): planner with window and shift row propagation` | 5.3.2 | — | T1.4, T1.5 |
| T1.7b | `feat(compute): reference executor with fixed summation order and budgeted chunking` | 5.3.8, 5.3.10 | — | T1.7a |
| T1.8 | `feat(compute): as-of adjustment reference and registered kernel classes` | 5.3.3, 5.3.3a, 5.3.4, 4.6 | T-07 | T1.7b, T0.15a, T1.G |
| T1.9 | `feat(factors): returns, moving averages, volatility and traded value` | 3.4, 5.3.10 | T-12 | T1.8, T1.Gb |
| T1.10 | `feat(factors): ewma, vwap, rsi, max drawdown and ops` | 3.3, 3.4 | — | T1.9, T1.Gb |
| T1.11 | `feat(compute): cross-sectional operators with mask and groupby, sorted-index reductions` | 5.4, 5.3.10 | T-11, T-27 | T1.7b, T1.Gb |
| T1.12 | `feat(pipeline): window-style user functions` | 3.3, 5.3.7, 6.5 | — | T1.8, T1.11 |
| T1.14a | `feat(artifacts): sealed run folders with crash recovery and source capture` | 5.9.1–5.9.3, 2.6 | — | T0.5a |
| T1.14b | `feat(artifacts): run index with candidates, observations, cohorts, pins and environment numerics` | 5.9.2, 5.9.5 | — | T1.14a |
| T1.13 | `feat(api): run_pipeline and factor screen` | 3.5, 3.8 | — | T1.12, T1.14b |
| T1.15 | `feat(api): rerun in a fresh process with input stamp, replay failure and trust gate` | 3.8, 5.9.3, 2.6 | — | T1.13 |
| T1.16 | `feat(compat): zipline CustomFactor and USEquityPricing shim` | 3.4 | — | T1.12 |
| T1.17 | `test(parity): isolated zipline env, bundle writer from TDS, L1-a and L1-b` | 8.1 | — | T1.10, T1.16, T0.10 |
| T1.18 | `test(parity): L1-d masks and classifiers, known differences` | 8.1 | — | T1.17 |
| T1.19 | `test(property): chunk, permutation, future-data, determinism and kernel invariants for pipelines` | 8.3 | — | T1.13 |
| T1.21 | `test(property): start-date and metamorphic invariants with preconditions` | 8.3 | P-START | T1.19 |
| T1.22 | `feat(tds): import csv with mapping.yaml and minimal-daily packages` | 4.3, TDS 7 | — | T0.14c, T0.13c |
| T1.23 | `feat(tds): manifest build for an existing folder` | TDS 8.1 | — | T1.22 |
| T1.24 | `feat(bench): benchmark harness and early stage measurements` | 7 | — | T1.13 |
| T1.20 | `docs(examples): m1 walkthrough` | 8.5 | — | T1.15, T1.22 |
| T1.Gb | `test(golden): v3.1 filter, builtin-factor and tie-break cases (T-24, T-25, T-27)` | 5.4.1, 3.4, 3.7, 8.2 | T-24..T-25, T-27 | T0.9 |
| T1.25 | `feat(pipeline): three-valued filters with validity masks` | 3.3, 5.4.1, 5.9.9 | T-24 | T1.11, T1.Gb |
| T1.27 | `test(repo): determinism source bans and cross-process hash-seed runs` | 2.5 | — | T1.19 |
| T0.15c | `feat(tds): v1.2 checks - exact ratios and delisting distributions` | TDS 5.11 | — | T0.15b, T0.14c |
| T0.15d | `feat(tds): v1.2 checks - volume unit, price grid and advisory file value hashes` | TDS 4.2 | — | T0.15b, T0.14c |
| T0.16c | `feat(testing): v1.2 synthetic fields and degrades` | 4.8 | — | T0.7, T0.15c, T0.15d |

## M2 — Point-in-time + factor evaluation

| Ticket | Title | Spec sections | Tests | Blocked by |
|---|---|---|---|---|
| T0.8a | `feat(testing): synthetic TDS package part 3a - fundamentals and classifications` | 4.8 | — | T0.7, T0.14b |
| T0.8b | `feat(testing): synthetic TDS package part 3b - fx, indices and panels` | 4.8 | — | T0.8a |
| T0.16b | `feat(testing): degraded synthetic packages for research fallbacks` | 4.5, 4.8 | — | T0.8b, T0.16a |
| T2.G | `test(golden): PIT, label and lookup cases for M2 (T-01..T-06, T-08, T-13, T-14, T-16..T-19, T-21, T-22)` | 8.2 | T-01, T-06, T-08, T-13..T-14, T-16, T-19, T-21..T-22 | T0.9, T0.8a |
| T2.1 | `feat(data): point-in-time intervals and rectangle two-time-axis lookup` | 5.3.5, 5.3.6, 5.1.5 | — | T1.4, T0.14b, T2.G |
| T2.2 | `feat(pipeline): Fund dataset over fundamentals_state` | 3.2, 5.3.5, 4.5 | — | T2.1, T1.6 |
| T2.3 | `feat(pipeline): Panel and Meta classifiers with availability, levels, editions and index members` | 3.2, 3.6, 4.6 | T-04 | T2.1, T0.8b |
| T2.15 | `feat(data): share counts point-in-time lookup, shares_out and market_cap` | 5.3.5a, 4.5 | T-13 | T2.1, T0.15a |
| T2.4 | `feat(pipeline): universes with eligibility, fallback, microcap switch and exclusion reasons` | 3.6, 4.5 | — | T2.3, T2.15, T0.16b |
| T2.5 | `feat(pipeline): units, currency conversion and cross-market terms` | 3.3, 5.3.2, 5.1.5, 3.11 | — | T2.1, T1.11, T0.8b |
| T2.6 | `feat(pipeline): label taint and external datasets` | 3.2, 6.5 | — | T1.6 |
| T2.9 | `feat(research): segments, exposures and trial registry with candidates, observations and cohorts` | 6.1, 6.2, 6.3 | — | T1.14b |
| T2.7 | `feat(research): economic and adjusted forward labels, three label times and purging` | 5.8, 5.6.13 | — | T1.13, T2.9, T0.15a, T2.G |
| T2.8 | `feat(research): IC, Newey-West, quantiles, turnover and coverage` | 5.8 | — | T2.7 |
| T2.16 | `feat(research): naive breadth, implied IR and cohort BHY-adjusted p` | 5.8 | — | T2.8, T2.9 |
| T2.10a | `feat(api): evaluate and FactorReport` | 3.8, 3.9 | — | T2.8, T2.9, T2.4, T2.16 |
| T2.10b | `feat(artifacts): report.html template with structural test` | 3.9 | — | T2.10a |
| T2.11 | `feat(api): explain values down to source facts` | 3.9, 4.5 | — | T2.2 |
| T2.12 | `feat(api): static checks before heavy compute` | 6.5 | — | T2.6, T2.5 |
| T2.18 | `feat(api): preregister` | 6.4 | — | T2.9 |
| T2.13 | `test(parity): L1-c fundamentals and producer panel agreement script` | 8.1 | — | T2.2, T1.17 |
| T2.17 | `docs: English quickstart from CSV to rerun` | 8.5 | — | T1.22, T2.10a, T1.15 |
| T2.14 | `docs(examples): m2 factor research walkthrough` | 8.5 | — | T2.10a, T2.11 |
| T2.Gb | `test(golden): v3.1 ranking and market-series cases (T-26, T-28)` | 5.4.2, 3.2 | T-26, T-28 | T0.9 |
| T2.19 | `feat(pipeline): market-level series terms` | 3.2, 5.1.5, 5.3.2 | — | T2.3, T1.8, T2.Gb |
| T2.20 | `feat(pipeline): percentile rank with explicit missing policy and weighted composites` | 3.3, 5.4.2 | T-26 | T1.11, T2.Gb |
| T2.21 | `feat(pipeline): Trad dataset and universe exclusion toggles` | 3.2, 3.6, 4.3, 5.1.5 | — | T2.4 |
| T2.22 | `feat(pipeline): explicit Filter.fillna, unknown counts per leaf and the unknown-universe notice (E39)` | 3.3, 5.4.1, 6.6, 5.9.1 | — | T2.4, T1.25 |
| T2.Ge | `test(golden): macro series vintage and event timing cases (G-96..G-98)` | 5.3.12, 8.2 | G-96..G-98 | T0.9 |
| T2.23 | `feat(pipeline): Macro.series and Events terms over series_observations and events, and from_parquet shapes` | 3.2, 5.1.5, 5.3.12, 6.6 | — | T2.19, T2.6, T2.Ge |

## M3a — One market, market orders, end to end (thin slice)

| Ticket | Title | Spec sections | Tests | Blocked by |
|---|---|---|---|---|
| T0.8c | `feat(testing): full and full_ci synthetic presets` | 4.8 | — | T0.8b |
| T3.Ga | `test(golden): market execution and cash cases (G-10..G-15, G-31, G-41)` | 5.6.3–5.6.7, 8.2 | G-10..G-15, G-31, G-41 | T0.9 |
| T3.Gc | `test(golden): accounting cases (G-16..G-26, G-30, G-34, G-35, G-42..G-49)` | 5.3.3a, 5.6.9–5.6.14, 8.2 | G-16..G-26, G-30, G-34..G-35, G-42..G-49 | T0.9, T0.15a |
| T3.1 | `feat(portfolio): pure target construction with stages and risk slot` | 3.7, 5.5 | — | T1.11, T1.9, T2.15, T1.Gb |
| T3.2 | `feat(api): Strategy, schedules, params and strategy screen` | 3.7, 3.8 | — | T3.1, T1.13 |
| T3.3 | `feat(accounting): columnar account state, integer money, valuation and NAV bridge` | 5.6.1, 5.6.9 | G-01, G-48 | T0.3, T3.Gc |
| T3.4 | `feat(execution): order table, lifecycle, trigger state, quantity conservation, sizing and session loop skeleton` | 5.6.2, 5.6.3, 5.6.7 | G-10, G-14..G-15 | T3.3, T3.Ga |
| T3.8 | `feat(execution): cost models, general impact form and cost table coverage` | 5.6.8, 4.7 | — | T3.4 |
| T3.5a | `feat(execution): market fills at open with tradability rules` | 5.6.3–5.6.5 | G-01, G-11, G-13..G-14, G-31 | T3.4, T3.Ga |
| T3.5b | `feat(execution): volume cap and affordable cash allocation with the actual cost function` | 5.6.6, 5.6.7 | G-10, G-12, G-41, G-53 | T3.5a, T3.8, T3.Gd |
| T3.9 | `feat(accounting): splits, reverse splits, stock dividends, bonus issues and capital reductions via the resolver` | 5.6.10, 5.3.3a, 4.6 | G-16..G-18, G-34, G-45..G-46 | T3.4, T0.15a, T3.Gc, T3.Gd |
| T3.9b | `feat(accounting): exclude instruments with share events lacking exact ratios (default policy)` | 5.6.1, 3.11, 6.6 | G-107 | T3.9, T1.1a, T3.Gd |
| T3.10 | `feat(accounting): cash dividends with entitlements, late amounts, corrections, pay-date estimation and data warnings` | 5.6.11, 5.3.3a, 4.5 | G-19..G-21, G-35, G-43..G-44 | T3.9 |
| T3.11 | `feat(accounting): delisting with knowledge-time proceeds, mergers, rights and unsupported actions` | 5.6.12, 5.6.13, 4.5 | G-22..G-26, G-42, G-47 | T3.10 |
| T3.12 | `feat(execution): single-sleeve simulation loop and session step` | 5.6.3, 5.6.14 | G-30 | T3.5b, T3.11, T3.22 |
| T3.13a | `feat(api): single-market backtest and metrics` | 5.7, 3.8, 3.9 | G-61 | T3.12, T3.2, T2.9, T3.Ge |
| T3.13b | `feat(api): named scenarios with a single zero-cost replay` | 3.8, 5.7 | — | T3.13a |
| T3.14 | `feat(artifacts): backtest outputs, event schemas, derived tables, NAV bridge and cost attribution` | 5.9.1 | — | T3.13a |
| T3.15a | `feat(execution): zipline parity preset (market orders, costs, sizing)` | 5.6.15 | — | T3.12 |
| T3.16 | `test(property): accounting and state-machine invariants` | 8.3 | P-BRIDGE, P-QTY | T3.13a |
| T3.17a | `test(parity): L2-a, L2-b, L2-c backtests against the zipline preset` | 8.1 | — | T3.15a, T1.17 |
| T3.21 | `feat(api): coverage and stale-mark warnings (E6, E25)` | 6.6 | — | T3.13a |
| T3.18 | `docs(examples): m3a strategy walkthrough, perf smoke and stage measurement` | 7, 8.5 | — | T3.14, T1.24, T0.8c |
| T3.Gd | `test(golden): v3.1 quantity, stale-mark, delisting-distribution, volume-cap, rounding, small-trade and target-gap cases (G-53..G-56, G-58, G-59, G-66)` | 5.6.1, 5.6.3, 5.6.6, 5.6.7, 5.6.13, 8.2 | G-53..G-56, G-58..G-59, G-66 | T0.9, T0.15a |
| T3.Ge | `test(golden): v3.1 metrics, drawdown and benchmark cases (G-60..G-62)` | 5.7, 8.2 | G-60..G-62 | T0.9 |
| T3.22 | `feat(accounting): stale marks adjusted for corporate actions and distributions before delisting counted once` |  | G-54..G-55 | T3.11, T3.Gd, T2.7 |
| T3.23 | `feat(accounting): per-component money rounding from market rules packs` | 5.6.1, 5.6.8, 4.7 | — | T3.8, T3.Gd |
| T3.25 | `feat(execution): minimum trade threshold and rebalance band at the order-intent stage` | 3.7, 5.6.7, 3.11 | G-59 | T3.5b, T3.Gd |
| T3.26 | `feat(research): target gap, lot rounding drag and execution quality metrics` | 5.6.7, 5.6.8, 5.7, 5.9.1 | — | T3.14, T3.Gd |
| T3.Gr | `test(golden): sizing and risk cases (G-78..G-87, G-95)` | 5.5.1a, 5.5.2, 5.5.2a, 8.2 | G-78..G-87, G-95 | T0.9 |
| T3.27 | `feat(portfolio): sizing slot with built-in sizers and @nx.sizer` | 3.7, 3.8, 5.5.1a | — | T3.1, T3.Gr |
| T3.28 | `feat(portfolio): ERC by fixed-order coordinate descent with defined fallback, and vol_target` | 5.5.1a | — | T3.27 |
| T3.29 | `feat(risk): ordered risk rule list with market-only built-ins, user rules and waterfall` | 5.5.2, 5.5.2a | — | T3.27, T3.Gr |
| T3.30 | `feat(risk): account layer with final targets, risk state, drawdown brake and portfolio stop` | 1.3, 5.5.2a, 5.6.7 | — | T3.29, T3.12, T3.14 |
| T3.31 | `feat(portfolio): @nx.portfolio user construction block` | 3.7, 3.8 | — | T3.1, T0.4b |
| T3.32 | `feat(artifacts): skip ledger and no-silent-failure summary` | 6.6, 5.9.1 | — | T3.14, T0.4b |
| T3.34 | `feat(api): strategy.replace and backtest preview` | 3.7, 3.8, 3.10 | — | T3.13a, T3.27 |

## M3b — Order types (limit, stop, stop-limit, exits)

| Ticket | Title | Spec sections | Tests | Blocked by |
|---|---|---|---|---|
| T3.15b | `feat(execution): confirm zipline 3.2.1 trigger semantics for the parity preset` | 5.6.15 | — | T3.15a |
| T3.Gb | `test(golden): order-type cases (G-02..G-09, G-32, G-33, G-37..G-40)` | 5.6.2a, 5.6.4, 8.2 | G-02, G-02..G-09, G-09, G-32..G-33, G-37..G-40 | T0.9 |
| T3.6 | `feat(execution): limit, stop and stop-limit daily fill rules with persistent triggers and fill records` | 5.6.4, 5.6.3 | G-02, G-02..G-06, G-06, G-32..G-33, G-37, G-40 | T3.5b, T3.15b, T3.Gb |
| T3.7 | `feat(execution): exit order lifecycle, resizing and OCO` | 3.7, 5.6.2a, 5.6.4 | G-07, G-07..G-09, G-09, G-38..G-39 | T3.6 |
| T3.17b | `test(parity): L2-d order types against zipline semantics` | 8.1 | — | T3.15b, T3.17a |
| T3.19 | `feat(api): explain strategy decisions` | 3.8, 5.9.9 | — | T3.13a, T3.7 |
| T3.20 | `feat(research): MinTRL, Lo-adjusted Sharpe, drawdown durations and signal-weight correlation` | 5.7 | — | T3.13a, T3.Ge |
| T3.Gf | `test(golden): price grid cases (G-57)` | 5.6.4a, 8.2 | G-57 | T0.9 |
| T3.24 | `feat(execution): market price grid for order prices and minimum-unit integer comparisons` | 5.6.4a, 4.7, 4.5 | G-57 | T3.6, T3.Gf, T0.16c, T0.5b |
| T3.33 | `feat(execution): time stop exit in the OCO group and no-reentry rule` | 3.7, 5.5.2a | — | T3.7, T3.30 |
| T3.35 | `feat(schedule): nx.on_event trigger schedule with incremental decisions and event templates` | 3.7, 5.3.12, 3.10 | G-97 | T2.23, T3.27, T3.33, T3.34 |

## M4 — Multi-market (KR/US synthetic, market rules packs) + shorting, long-short, margin account

| Ticket | Title | Spec sections | Tests | Blocked by |
|---|---|---|---|---|
| T4.G | `test(golden): sleeve, timing, currency and tax cases (G-27..G-29, G-36, G-50..G-52)` | 5.1.3, 5.6.3, 5.6.9, 5.6.11a, 8.2 | G-27..G-29, G-36, G-50..G-52 | T0.9 |
| T4.1 | `feat(execution): multi-sleeve event queue, phase order and clock modes` | 5.1.3, 5.6.3 | G-27 | T3.12, T4.G |
| T4.2 | `feat(accounting): sleeve funding, fx valuation and drift` | 5.6.9 | G-27, G-29 | T4.1, T2.5 |
| T4.3 | `feat(compute): cross-market terms gathered at decisions` | 5.3.2 | — | T4.1, T2.5 |
| T4.4 | `feat(execution): price-limit history from market rules packs and unknown tradability policy` | 5.6.5, 4.7 | G-57 | T3.5a, T3.24 |
| T4.5 | `feat(execution): realistic dated cost profile end to end` | 5.6.8, 4.7 | — | T3.8 |
| T4.5b | `feat(accounting): user-configured tax scenario` | 5.6.11a, 3.11 | G-51..G-52 | T4.G, T4.2, T3.13a |
| T4.6 | `feat(api): benchmarks from index instruments` | 5.7, 4.6, 4.5 | — | T3.13a, T3.Ge |
| T4.7 | `feat(api): combined multi-market backtest and screen reports` | 3.9 | — | T4.2, T4.3, T4.6, T4.10 |
| T4.8 | `test(property): DST, holiday mismatch, timing and currency metamorphic cases with preconditions` | 8.2, 8.3 | G-28 | T4.2, T4.10 |
| T4.9 | `docs(examples): m4 multi-market walkthrough` | 8.5 | — | T4.7 |
| T4.10 | `feat(artifacts): currency attribution and exposure tables` | 5.6.9, 5.9.1 | G-36 | T4.2, T3.14 |
| T4.11 | `test(markets): market names from data with a synthetic third market ZZ` | 4.7, 4.8, 3.11 | — | T4.7, T0.5b |
| T4.12 | `feat(research): benchmark-relative metrics and monthly return table` | 5.7, 3.9 | G-62 | T4.6, T3.Ge |
| T4.13 | `feat(execution): optional dated and liquidity-tiered provisional cost tables` | 3.7, 5.6.8, 4.7 | — | T3.8 |
| T4.Gs | `test(golden): short accounting, financing, ruin and cash-interest cases (G-67..G-70, G-74..G-77, G-94)` | 5.6, 8.2 | G-67..G-70, G-74..G-77, G-94 | T0.9 |
| T4.Gt | `test(golden): long-short targets, short orders and ban cases (G-71..G-73)` | 3.7, 5.5, 5.6.2a~5.6.7, 8.2 | G-71..G-73 | T0.9 |
| T4.17 | `test(regression): long-only core-table value-hash baseline and the P-SHORT-OFF harness` | 8.3 | P-SHORT-OFF | T4.7, T4.5b, T4.13 |
| T4.14 | `feat(portfolio): signed targets, bottom(), long-short books and exposure limits` | 3.7, 5.5.1, 5.5.2, 3.11 | — | T4.17, T3.1, T4.Gt |
| T4.15a | `feat(accounting): short positions - signed state, collateral, financing accrual, mandatory debits and ruin` | 5.6.1, 5.6.3, 5.6.7, 5.6.9 | G-67, G-76 | T4.14, T3.22, T4.5b, T4.Gs |
| T4.15b | `feat(accounting): short dividends, corporate actions and delistings on negative quantities with estimate replacement` | 5.3.3a, 5.6.9~5.6.13 | G-68..G-70, G-74 | T4.15a |
| T4.15c | `feat(accounting): short realized gains in the tax scenario` | 5.6.11a | G-75 | T4.15b |
| T4.16a | `feat(execution): short-sale and cover orders - four-action priority in every phase, reversal gating and mirrored daily fills` | 5.6.2, 5.6.3, 5.6.4, 5.6.6, 5.6.7 | G-73 | T4.15a, T3.7, T3.24, T4.Gt |
| T4.16b | `feat(execution): short exits and ban periods from rules packs` | 3.7, 5.6.2a, 5.6.4, 5.6.5, 4.7 | G-71, G-73 | T4.16a, T4.4 |
| T4.18 | `test(parity): L2-e long-short against the zipline preset` | 8.1, 5.6.15 | — | T4.16b, T3.17a |
| T4.19 | `feat(accounting): cash interest on positive cash balances` | 3.11, 5.6.3, 5.6.9, 5.7 | — | T4.15a, T4.Gs |
| T4.Gm | `test(golden): margin account cases (G-99..G-104)` | 5.6.7a, 8.2 | G-99..G-104 | T0.9 |
| T4.20 | `feat(accounting): margin account type - buying power, debit interest, margin call and forced reduction` | 3.11, 5.6.7a, 5.5.1a, 5.6.3 | P-MARGIN-OFF | T4.19, T4.16a, T4.17, T4.Gm |

## M5 — Paper trading (live), ledger, reconcile, CLI, templates

| Ticket | Title | Spec sections | Tests | Blocked by |
|---|---|---|---|---|
| T5.1 | `feat(artifacts): paper book store with locked transactions, state versions and recovery` | 5.9.6 | — | T3.3, T1.14b |
| T5.2 | `feat(api): live order preview with decision-level idempotency` | 3.8, 5.9.6 | — | T5.1, T4.7 |
| T5.3 | `feat(api): advance paper books with the backtest state machine` | 5.9.6 | — | T5.2 |
| T5.7 | `feat(api): reconcile paper books by recorded-snapshot replay or explicit restatement, and write status.json` | 5.9.6, 5.9.7 | — | T5.3 |
| T5.4 | `feat(cli): complete command set and exit codes` | 3.10 | — | T5.7 |
| T5.5 | `feat(api): compare, runs table and html index` | 3.8, 3.9 | — | T3.14 |
| T5.8 | `feat(compat): pyfolio and alphalens adapters, evaluate signal output` | 5.9.8, 5.8 | — | T3.14, T2.10a |
| T5.22 | `feat(api): Arrow PyCapsule in and out (from_frame, zero-copy result tables)` | 3.2, 5.9.8 | — | T2.6, T5.8, T5.G |
| T5.9 | `feat(api): Run.why from run artifacts` | 5.9.9 | — | T3.19, T3.14 |
| T5.6 | `docs(examples): m5 daily paper runbook` | 8.5 | — | T5.4 |
| T5.G | `test(golden): trades table, book cash-flow and frame-hash cases (G-64, G-65, G-105)` | 5.9.1, 5.7, 8.2 | G-64..G-65, G-105 | T0.9 |
| T5.10 | `feat(api): manual overrides as book events` | 3.8, 5.6.5, 5.6.7, 5.9.6 | — | T5.3 |
| T5.11a | `feat(api): manual books - user event schema, CSV import and idempotent transactions` | 3.8, 5.9.6 | — | T5.3, T5.7 |
| T5.11b | `feat(api): manual-book reconcile report` | 5.9.7 | — | T5.11a, T5.10 |
| T5.12 | `feat(api): live pre-trade sanity checks (E36)` | 5.9.6, 3.9, 3.11 | — | T5.2 |
| T5.13 | `feat(accounting): external cash flows and time-weighted returns in books` | 5.6.9, 5.7, 5.9.6 | G-65 | T5.1, T5.G |
| T5.14 | `feat(artifacts): round-trip trades table derived from events` | 5.9.1, 3.9 | G-64 | T3.14, T4.15c, T5.G |
| T5.15 | `feat(api): screen x-ray over the whole universe` | 3.8, 3.9, 5.9.9 | — | T3.19, T2.20, T2.21, T2.22, T5.1 |
| T5.16 | `feat(portfolio): target-state plumbing for checkpoints, books and screens` | 5.5.3, 5.6.1, 5.9.6 | — | T5.1, T3.12 |
| T5.17 | `feat(api): screen account modes for account-reading risk rules` | 3.8, 3.10 | — | T3.30, T5.1, T5.4 |
| T5.18 | `feat(cli): strategy templates, demo snapshot and the 30-minute path` | 3.10, 8.5 | — | T5.4, T3.34, T3.33, T5.17 |
| T5.19 | `docs: zipline to NexusBT mapping page and zipline-port template` | 8.5 | — | T5.18 |
| T5.20 | `feat(api): compare strategy variants in one table` | 3.8 | — | T5.5, T3.34 |
| T5.21 | `feat(cli): commented two-tier nexusbt.toml template, config check and config show` | 3.10, 3.11 | — | T1.2, T0.4b, T0.5a |

## M6 — Performance, research tools (validation, ML), release gate

| Ticket | Title | Spec sections | Tests | Blocked by |
|---|---|---|---|---|
| T6.2 | `perf(compute): numba rolling kernels bit-equal to reference` | 5.3.3, 5.3.10 | — | T1.24, T4.7 |
| T6.3 | `perf(compute): numba cross-sectional kernels` | 5.4, 5.3.10 | — | T6.2 |
| T6.12 | `feat(data): L0 raw block cache with memory mapping` | 5.3.9, 7 | — | T1.24, T1.4 |
| T6.4 | `feat(compute): semantic term cache (L1)` | 5.3.9 | — | T6.2 |
| T6.5 | `feat(compute): process-tree memory budget, bounded workers and parallel scenarios` | 5.3.8 | — | T6.4 |
| T6.6 | `perf(execution): numba session step over the columnar state (conditional)` | 5.6, 7 | — | T1.24, T3.18, T4.7 |
| T6.7 | `feat(api): sweep with shared graph and candidate matrix` | 3.8, 6.3 | — | T6.4 |
| T6.14 | `feat(api): capacity scenario` | 3.8, 5.7 | — | T6.7, T6.5 |
| T6.8 | `feat(research): PSR, DSR and PBO via CSCV over cohorts` | 5.7, 6.3 | G-60 | T6.7, T2.9 |
| T6.9 | `feat(research): truncation probes with prioritized dates and coverage report` | 6.5 | — | T6.4 |
| T6.13 | `feat(research): start-date probe in nx.check` | 6.5 | — | T6.9 |
| T6.10 | `feat(api): progress display for long work` |  | — | T6.5 |
| T6.11 | `perf: compute-host gate run and evidence` | 7 | — | T6.3, T6.5, T6.8, T6.12, T6.26, T6.6 |
| T6.15 | `chore(release): clean-install gate, independent producer acceptance, changelog and contributor docs` | 2.3, 9.1 | — | T2.17, T4.11, T5.4 |
| T6.16 | `ci(release): trusted-publishing workflow (dry run until the user decides)` | 2.1 | — | T6.15 |
| T6.17 | `test(bridge): capability errors for reserved extension points` | 11 | — | T0.4 |
| T6.18 | `feat(api): rebalance-date luck offsets and rolling-window table` | 3.8, 5.7, 6.2, 3.11 | — | T6.4, T4.12 |
| T6.Gv | `test(golden): validation, ML window, triple-barrier and pretrained-cutoff cases (G-88..G-93, G-106)` | 5.3.11, 5.8, 6.3a, 8.2 | G-88..G-93, G-106 | T0.9 |
| T6.19 | `feat(research): split value objects with label-availability purge and AFML embargo` | 6.3a, 5.8 | — | T2.9, T6.Gv |
| T6.20 | `feat(api): backtest(method="walk_forward") with a chained account, fold selection and linear side by side` | 3.8, 6.3a, 6.2 | P-WF-STITCH | T6.19, T6.7, T3.13a |
| T6.21 | `feat(research): CPCV paths with fresh capital per path, CSCV and sweep as a shorthand` | 6.3a, 6.3 | — | T6.20, T6.8 |
| T6.22 | `feat(report): hygiene panel on the first screen and ValidationResult report` | 6.3a, 3.9 | — | T6.21, T2.10b |
| T6.23 | `feat(ml): ml.factor node with engine-enforced training window and fit/predict records` | 5.3.11, 6.5 | — | T6.19, T2.10a, T1.12 |
| T6.24 | `feat(ml): ml.factor inside method folds, rerun refit hash check and determinism warnings` | 5.3.11, 6.3a | — | T6.23, T6.21, T1.15 |
| T6.24b | `feat(ml): pretrained predict-only models with training cutoff leak guard` | 5.3.11, 6.2, 6.6 | — | T6.24, T6.Gv |
| T6.25 | `feat(research): triple-barrier label sharing the exit fill rule` | 5.8, 3.7 | — | T3.33, T2.10a, T6.Gv |
| T6.26 | `perf: P11 high-dimensional workload with decision-date-only evaluation, column pruning and batched reductions` | 7, 5.3.2, 5.3.8 | — | T1.24, T6.4, T6.5 |
| T6.27 | `docs(examples): walk-forward/CPCV and ML factor templates` | 3.10, 8.5 | — | T6.24, T5.18 |
| T7.G | `test(golden): hold-band edge cases (G-63)` | 5.5.3, 8.2 | G-63 | T0.9 |
| T7.1 | `feat(portfolio): target-state recursion and hold band` | 5.5.3 | — | T6.11, T6.18, T7.G, T4.14, T5.16, T6.22, T6.24, T6.25, T6.27 |
| T7.V | `verify: post-T7.1 release re-verification (no features)` | 7, 8, 9.1 | P-SHORT-OFF | T7.1 |

## v1.x — Right after v1

| Ticket | Title | Spec sections | Tests | Blocked by |
|---|---|---|---|---|
| T7.2 | `feat(research): effective number of trials and DSR(N_eff)` | 5.7 | — | T6.8 |
| T7.5 | `feat(artifacts): Brinson sector attribution and first divergence` |  | — | T4.10, T5.5 |

## Where to look for…

- Scope, glossary, invariants: §1.1–1.3 (full glossary: `CONTEXT.md`)
- Package layout, dependency and security rules: §2.3–2.7
- Public API, result objects, CLI, config keys: §3.1–3.11
- Reading TDS packages, fallbacks, market rules packs, synthetic generator: §4.1–4.8
- Time and "as of", Pipeline computation, missing values: §5.1–5.4
- Targets, sizing slot, risk slot, account layer, hold band: §5.5
- Daily state machine: orders, fills, costs, corporate actions, delisting, margin: §5.6
- Metrics, evaluate, run records, ledger, reconcile, explain: §5.7–5.9
- Research hygiene, validation methods, error catalogue: §6.1–6.6
- Performance budgets: §7
- Test suites (parity, golden, property, conformance, errors, docs): §8.1–8.5
- Build order with plinth, ADR list: §9
- Extension points (event backend, Nautilus, assets): §11
- Deferred items and their targets: §12.1
