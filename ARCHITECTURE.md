# Architecture

**Event-driven where it matters, vectorized where it scales. You just snap the blocks together.**

This document describes the high-level architecture of NexusBT. Read it to find your way around the code and to learn which rules hold everywhere. It is a map, not the rules: the rules are in the [engine spec](docs/spec/engine-spec-v3.4.md) (Korean, the single source of truth). Section numbers below (§) point into the spec. Korean translation: [ARCHITECTURE.ko.md](ARCHITECTURE.ko.md).

> Status: the design is complete and the code is not written yet. Every package and module named here is **planned** (spec §2.3, ticket T0.2a).

## Bird's-eye view

NexusBT is a backtesting and screening engine for equity factor research on daily bars. It reads a [TDS](docs/tds/tds-v1.4.md) package (Parquet files plus a `tds.json` manifest) by path, computes factors for every instrument and every date at once, turns scores into target weights through nine strategy slots, and then simulates the account session by session in event order: orders, fills, costs, taxes, corporate actions, dividends, delistings, shorting and FX. The same strategy file gives factor evaluation, a backtest, today's screen and a paper book. Validation (walk-forward, CPCV, CSCV/PBO, DSR) runs inside the engine through one entry point, `backtest(method=…)`.

The split is the point of the design: the heavy, embarrassingly parallel part (terms over the panel) is vectorized; the part where order matters (the account) is event-driven, but each session processes all instruments as arrays. Users never need to know which side a block runs on (§0).

```
 snapshot path (TDS package)
        │  open + check (nexusbt_tds), capabilities, fallbacks         data
        ▼
 market blocks · interval lookup (PIT) · calendars · FX · resolved corporate actions
        │  L0 cache: market × column × year, Arrow IPC
        ▼
 Pipeline graph: factors · filters · classifiers                       pipeline / compute
        │  plan → vectorized kernels (numpy / Numba) → L1 term cache
        ▼
 nine slots: schedule · universe · signal · construction ·             portfolio / risk / ml
             sizing · risk · (execution · exits · costs)
        │  canonical targets (TargetFrame) → account layer → final targets
        ▼
 daily state machine, per session, all instruments as arrays:          execution / accounting
   corporate actions → orders → fills → costs/taxes → valuation → NAV bridge
        │  events (orders, account_events) are the source of truth
        ▼
 run folder: Parquet tables + manifest + hashes · report · screen · paper book   artifacts / api
 (result tables export through the Arrow PyCapsule interface)
```

## Layers

- **Data** (§4, §5.1, §5.3.3a, §5.3.6). `open_snapshot` runs the TDS checker at the declared level, computes which capabilities the graph needs, applies the defined fallbacks (announced and recorded, §4.5), and serves rectangular point-in-time interval lookups. Raw market blocks are cached as uncompressed Arrow IPC files (L0, §5.3.9). One corporate-action resolver feeds both adjustment and accounting.
- **Pipeline** (§3.3–3.6, §5.3). Terms are value objects with a hash; `pipeline` never reads data. `compute` plans the graph, computes only the needed columns, dates and decision rows, and runs registered kernels in Python + numpy/Numba. Hot kernels sit behind a narrow array-in, array-out seam (`compute._kernels`, `execution._step`, `accounting._state`) that a Rust build may replace only if it is bit-equal (§2.4, ADR-0016).
- **Decisions and blocks** (§3.7, §5.5). A `Strategy` has nine slots: schedule, universe, signal, construction, sizing, risk, execution, exits, costs. Scores become a canonical `TargetFrame` through construction → sizing → risk; risk rules that read the account run only in a final account layer (§5.5.2a). Your own factor, sizer or risk rule is one decorated function. `nx.ml.factor` trains forward-only inside the engine (§5.3.11).
- **Execution and accounting** (§5.6). A daily state machine per sleeve: next-session fills, adverse ordering inside a bar, volume caps, price limits, halts, tick grids (§5.6.4a), costs as cash debits, splits and dividends, mergers, delistings, signed long/short (off by default), cash and margin accounts (§5.6.7a). Money is integer minor units, with a daily NAV and P&L bridge.
- **Research** (§5.7, §5.8, §6). `evaluate` (IC, quantiles, turnover, coverage, BHY), `backtest(method="linear" | "walk_forward" | "cpcv" | "cscv")` with purging and real fills on every fold (§6.3a), segments without a future lock (§6.1), an attempt log with PSR/DSR/PBO (§6.2–6.3), and look-ahead probes (§6.5).
- **Outputs** (§3.9, §5.9). Each run is a transaction that writes a sealed run folder (Parquet tables, `manifest.json`, captured sources, three hashes, SQLite index). Derived tables (`positions`, `daily`, `metrics`, `attribution`, `exposures`) are rebuilt from events. Result tables implement `__arrow_c_stream__`; a static HTML report, screens and paper books come from the same records.

## Code map (planned)

The repository is a uv workspace with two distributions: the engine `nexusbt` (`import nexusbt as nx`) and the data-standard checker `nexusbt-tds` (`import nexusbt_tds`, CLI `tds`). Layout from §2.3; public interfaces in §2.4; import rules in §2.5.

| Path | What lives there |
|---|---|
| `tds/` | The TDS standard, versioned separately: `spec/tds-v1.md`, `schemas/`, `conformance/`, and `src/nexusbt_tds/` (check, hash, manifest, describe, import_csv). Depends on pyarrow only; never imports `nexusbt`. |
| `src/nexusbt/contracts/` | Id constants, engine column sets, units, policies, the error hierarchy (§6.6). No dependencies. |
| `src/nexusbt/config/` | Reads and validates `nexusbt.toml` (§3.11); refuses secret keys. |
| `src/nexusbt/data/` | Snapshot open (calls the checker), capabilities and fallbacks, market blocks, L0 cache, interval lookup, calendars, FX, corporate-action resolver. |
| `src/nexusbt/pipeline/` | Terms, datasets, operators, built-in factors, `Pipeline`, graph hash, static checks. |
| `src/nexusbt/compute/` | Planner, reference kernels, fast kernels, adjustment, cross-sections, L1 cache, executor. |
| `src/nexusbt/portfolio/` | Scores → canonical targets (construction → sizing → risk) and the account layer. |
| `src/nexusbt/risk/` | Sizing `size.*` and risk rules `risk.*`. |
| `src/nexusbt/ml/` | `ml.factor` training node, training windows, `fits` / `predictions` records. Does not import sklearn. |
| `src/nexusbt/execution/` | Columnar order table, fill model, costs, sizing to shares, daily state machine, presets. |
| `src/nexusbt/accounting/` | Columnar account state, integer minor-unit postings, rights, exit values, valuation, NAV bridge. |
| `src/nexusbt/research/` | Labels, IC/quantiles, statistics (NW, PSR, DSR, PBO, MinTRL, BHY, Lo), segments, splitters and validation methods, trial registry, probes. |
| `src/nexusbt/artifacts/` | Run transactions, manifest, hashes, SQLite index, source capture, paper books, reconcile, attribution, report. |
| `src/nexusbt/api/`, `cli/` | `evaluate`, `backtest`, `screen`, `live`, `reconcile`, `sweep`, `compare`, `explain`, `check`, …; the CLI is a thin argparse layer over `api`. |
| `src/nexusbt/compat/` | `zipline.py` (zipline names, no zipline import), `adapters.py` (pyfolio / alphalens shapes, optional pandas). |
| `src/nexusbt/bridge/` | Event-engine boundary for later intraday work: Protocols and types only (§11). |
| `src/nexusbt/testing/` | Synthetic TDS package generator (§4.8) and hand-calculation helpers. |
| `src/nexusbt/resources/` | Market rule packs `markets/{KR,US,_generic}.toml`, cost, price-limit, tick and short-ban tables (§4.7). |
| `tests/` | `unit/`, `property/`, `golden/` (expected values that implementation PRs may not edit), `docs/`, `perf/`, `repo/`, and `parity/` (isolated zipline-reloaded 3.2.1 environment). |
| `bench/` | Measurement scripts and summary JSON. |

Dependency direction (enforced by an AST test): `contracts ← config ← data ← compute ← api ← cli`, `contracts ← pipeline ← compute`, `contracts ← risk ← portfolio ← api`, `contracts ← accounting ← execution ← api`, `contracts ← research ← api`, `contracts ← artifacts ← api`, `nexusbt_tds ← data`. Only `api` composes modules.

## Invariants

All of them are tested in every milestone (§1.3). The ones that shape the architecture most:

- **Point-in-time** (INV-01, INV-02): a decision uses only observations with `ts_available <= decision_ts`, including the account inputs that size orders; adding later data never changes earlier targets.
- **Determinism** (INV-03, INV-04, INV-09, INV-13): same pinned environment and inputs give byte-identical Parquet, regardless of chunking, index order, process or `PYTHONHASHSEED`; reductions use a fixed summation order, no BLAS, no `fastmath`.
- **Caches are invisible** (INV-05): a cache hit and a miss give bit-identical results.
- **screen = backtest** (INV-08): same strategy, snapshot, policy, anchor and context give the same canonical targets; targets never read account state.
- **No hidden fills** (INV-12): missing values propagate; filling is an explicit operator, and data fallbacks are announced and recorded.
- **Integer money and shares** (INV-06, INV-18): money is int64 minor units and the NAV bridge closes to zero every day; share counts use integer arithmetic and `requested = filled + cancelled + remaining`.
- **Exact ratios, `exclude_instrument` default** (INV-18, §5.6.1, §3.11): share-changing corporate actions need exact integer ratios; an instrument with an inexact ratio is excluded from the moment the event is visible (`[corporate_actions] decimal_ratio = "exclude_instrument"`), never inferred from floats.
- **Events are the source of truth** (INV-16): every derived table can be rebuilt from `orders` and `account_events`.
- **Switches off = baseline** (INV-22, INV-23): shorting off is bit-identical to long-only; no account-reading risk rule means final targets equal canonical targets.

## Cross-cutting concerns

- **Errors that teach** (§6.6): every error names what, where, why and how to fix, and its layer (data, your code, config, engine bug). Error codes E1–E49.
- **Research hygiene** (§6): attempt counts, pre-registration, look-ahead blocked before computing.
- **Security and public hygiene** (§2.6, §2.7): no pickle anywhere (Parquet, Arrow IPC, JSON only); no secrets in config; repository hygiene tests keep private data out.
- **Market rules come from packs** (§4.7, ADR-0029, ADR-0035): market names come from the data; tick grids, limits, rounding and short bans come from versioned rule packs.
- **Testing** (§8): hand-computed golden cases, property and metamorphic tests, look-ahead tests, TDS conformance, a narrowed zipline parity suite (ADR-0021). Measured prototype evidence: [docs/design/prototype-results.md](docs/design/prototype-results.md).
- **Performance** (§7): budgets per workload; parallelism is processes in v1 (ADR-0040).

## Where to look in the spec

| Area | Spec sections |
|---|---|
| Scope, glossary, invariants | §1.1–1.3 (glossary also in [GLOSSARY.md](GLOSSARY.md)) |
| Packages, interfaces, import rules, security | §2.3–2.7 |
| Public API, strategy slots, results, CLI, config | §3.1–3.11 |
| Input data (TDS), fallbacks, rule packs, synthetic data | §4 |
| Time and availability, Pipeline compute, caches, determinism | §5.1–5.4 |
| Targets, sizing, risk, hold band | §5.5 |
| Daily state machine, fills, costs, corporate actions, margin | §5.6 |
| Metrics, evaluate, run records, paper book | §5.7–5.9 |
| Research hygiene, validation methods, errors | §6 |
| Performance, tests | §7, §8 |
| Milestones and tickets | §10 and [SPEC-INDEX.md](SPEC-INDEX.md) |
| Extension points | §11 |
| Decisions | [docs/adr/](docs/adr/) (short form in §9.3) |

## Not in v1 (on purpose)

From §1.1 and §12.1; each has a target release there.

- Intraday, tick and order-book data, crypto, futures, options (E4/E5; only the boundary in §11).
- An engine-side ingest step, direct DuckDB reads, zipline/LEAN/Nautilus/DBN importers (v1.x).
- `engine="auto"` switching and a zipline fork; zipline is a parity reference only.
- Broker order routing; brokerage-calibrated costs (TCA).
- Panel-style user functions, period windows ("30d"), correlation/regression/`Beta`/`Illiquidity` built-ins, more time-series kernels.
- `size.kelly`, ERC `fallback="fail"`, two-sided ML training.
- Buy/hold/sell asymmetry (`min_hold`, `cooldown`, `max_replace`), drift-triggered rebalancing, strategy blending, exit ladders.
- VWAP fills, T+n settlement calendars, house margin requirements, portfolio margin, intraday margin calls.
- Bootstrap Sharpe intervals, randomized null tests, sweep landscapes.
- Brinson and factor attribution.
- Web server, logins, job queue, browser editor.
- Publishing to PyPI before v1 passes real-data verification.
