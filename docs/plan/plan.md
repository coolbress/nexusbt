## 10. Milestones and tickets

### 10.0 Milestone table [Codex 11.8, design 6, R-44]

Following the three-reviewer consensus, v3 **cut M0 down to contracts only**, and moved the checker's full level, the synthetic small/full presets and the hand calculations to **just before** the milestone that uses them. M3 is split into **M3a (a thin market-order end-to-end slice)** and **M3b (all the order types of 9.0)**. The release definition stays as in 9.0 (end of M6, every order type). The performance measurement harness moved up to M1. The column "What the user can use right away" is the early usable path, milestone by milestone; the final v1 scope is the release of 9.0 and the release gate after M6 (OI-46), and a milestone's early use does not promise any part of it ahead of time (design review D15, 2026-11-04).

**M1b, a thin backtest before factor evaluation** (the owner, 2026-11-28, #858; it replaces #43's decision of 2026-11-04 that left the first end-to-end run in M3a): M1b, between M1 and M2, builds a backtest that runs end to end, and later milestones add to it one piece at a time. A ticket split for it keeps its id on the half that stays and gives the half in M1b a new letter; the end conditions the v3.1 to v3.4 paragraphs below give M3a are M1b's for the parts that moved.

| M | Stage (E) | What the user can use right away [R-44] | End conditions (all required) | Command to show (`/run`) |
|---|---|---|---|---|
| M0 normative contracts | E1 (engine side) | Nothing (foundation) — `tds check --level manifest|schema`, `tds hash` | spec v3.4·TDS v1.4 public edition·CONTEXT·the first decision records in `docs/adr/`·LICENSE merged; every R·SC·TDS-D·RV·V31·R3·R4 item mapped in appendix B (R4F, R4G, R4H, R5, R6 and R7 are not); ticket graph test passes; TDS checker manifest·schema levels + three results + path safety + hash test vectors; hand-authored `tiny` synthetic passes `schema`; golden format + G-01 | `uv run python -m nexusbt.testing.synth --preset tiny --out .scratch/snap --validate` → row count per dataset, `value_sha256`·`semantic_sha256`, the profile's three results (what was not checked is `not_checked`); `uv run tds check .scratch/snap --level schema` → exit code 0 |
| M1 snapshot + Pipeline slice + first public path | E2 | `run_pipeline`, factor screening, run records·rerun, `tds import csv`, English quick start (analysis) | checker full (K·R·T·D·A·V·H) + resolver (decision 2026-11-10, #356: "checker full" means that the `full` level judges every K, R, T, D, A, V and H code of TDS 8.3; the codes still `unchecked` on that date belong to M1 tickets, T0.14b (T·D), T0.15c (A010·A011) and T0.15d (V011·V012·H004)); synthetic small (with events·revisions) and core `degrade` pass `full`; T-07, T-09~T-12, T-15, T-20, T-23; P-CHUNK (including sub-year chunks)·P-PERM·P-FUT·P-DET·P-KERNEL (reference)·P-START·M-SCALE·M-DUMMY·M-SPLIT-NEUTRAL (with preconditions·counterexamples); L1-a (default inputs on both sides)·L1-b·L1-d; F-02~F-04 tests; first per-stage measurements (open·block·adjustment·window kernel·cross-section) in `bench/results`; **requirement evidence** (user decision 2026-11-03, for this and every row below; R1 to R5 are the owner's five requirements: R1 reality, R2 scale and validity, R3 strategy writing, R4 live continuation, R5 outputs): R2 — the M1 early measurement of chapter 7 (T1.24), which counts as evidence only once T1.19 (P-CHUNK, P-FUT) and T1.21 (P-START) pass on the late-bar synthetic variant (#354); before that it is profiling (decision 2026-11-10, #356) | `uv run python examples/m1_screen.py` → top 10 momentum per market on the reference date; `uv run nexusbt rerun <id>` → "outputs identical"; `uv run nexusbt doctor` → the profile's three results·fallback list·rules packs; `uv run python bench/run.py --stages m1 --snapshot synth-small` |
| M1b first backtest end to end (thin slice) | E3 (first part) | `backtest` of one market, long only, `top(n)` with equal weights, market orders at the next open, no costs; the first screen; the saved run·`rerun`; `init --demo` | G-01, G-12, G-15~G-20, G-22 (observed), G-30, G-34, G-45, G-46, G-48, G-53, G-54, G-55 (the parts of T3.22a), G-61 (a), G-119~G-123, G-124 (a), G-127, G-129 (the parts of T3.5c, T3.22a and T3.13d), G-130~G-135, G-137, G-138; P-NAV, P-BRIDGE, P-QTY; L2-a·L2-c; the person runs a first backtest on demo data (`init --demo`, then `examples/strategies/mom_kr.py`) and reads it against the first screen of 3.9: the six metrics, the line that says costs are not included, the simulated-result line, and each line not built yet naming the ticket it waits for | `uv run nexusbt init --demo` then `uv run nexusbt backtest examples/strategies/mom_kr.py` → the first screen (return, CAGR, volatility, Sharpe, maximum drawdown, turnover; costs not included; `family: n/a (not built yet; available after ticket T2.9)`); `uv run nexusbt rerun <id>` → "outputs identical" |
| M2 PIT + factor evaluation | E2 | `evaluate` (economic label·label time set·naive breadth·cohort BHY), `explain` (values), segments, `preregister` | T-08, T-16, T-18, T-21, T-22 (T-01~T-06, T-13, T-14, T-17, T-19, strict-edition lineage, L1-c, F-06~F-08·F-11 and the monthly panel removed 2026-11-24, #752); labels crossing a segment excluded (`ts_label_available`); candidates·observations·cohorts; F-14 tests; P3 measurement; English quick start test; the person opens `report.html` of the representative factor result (`examples/factors/momentum.py`) and reads it against the 3.9 FactorReport list and the 2 s budget; **requirement evidence**: R2 — the end-of-M2 early measurement of chapter 7 (T2.14, and the reduced P11 (a) of T2.24); R5 — `report.html` (T2.10b) carries the FactorReport sections and the visual rules of 3.9, and the eye check reads the factor result by the 3.9 metrics per strategy style (the three representative results: the factor here, which M1b's strategy already trades; long-only in M3a, whose first screen M1b showed first; long-short in M4) | `uv run nexusbt evaluate examples/factors/momentum.py` → FactorReport (label definition line·naive breadth·BHY(cohort) line) |
| M3a single-market market-order backtest, completed | E3 | `backtest` (one market, market orders) with costs, volume cap, price limits and every corporate action, strategy `screen` | G-10, G-11, G-13, G-14, G-21, G-22 (policy, lo, hi), G-23~G-26, G-31, G-35, G-41~G-44, G-47, G-49, G-60, the `at=close` sell of G-129 (a); P-RESUME, P-STATE, P-PARITY13, P-DERIVED; L2-b; F-05·F-09·F-13 tests; state machine stage measurement (`full_ci`, `full` on the compute machine); the person opens `report.html` of the representative long-only result (`examples/strategies/mom_kr.py`) and reads it against the 3.9 Run list and the 2 s budget (the long-short result is looked at in M4, where shorting arrives); **requirement evidence**: R1 — before the long-only report is read, the owner's `nexusbt.toml` `[costs]` carries their broker's commission, since a run books none of the user's own costs unless they are set (#841); R2 — the end-of-M3a early measurement of chapter 7 (T3.18, P5-daily and the full P11 (a) included); R5 — the eye check reads the Run sections of 3.9 in their order (questions 1 to 7) by the metrics per strategy style; **one-market path** (design review D15, 2026-11-04): `examples/strategies/mom_kr.py` ranks on the factor of `examples/factors/momentum.py` (imported, not a copy; both written in M1b, T3.37), so the factor M1b first traded and M2 evaluated is the one M3a trades, and `screen` of that strategy on one decision date gives the canonical target the backtest holds for that date (P-PARITY13, INV-08). This is target equality only: equality of the orders and fills an account makes from that target is M5's evidence (T5.17 `test_as_backtest_equals_backtest_account`, P-RECON) | `uv run nexusbt backtest examples/strategies/mom_kr.py` → Run summary (assumption line·direct cost/path effect·reconciled: yes) |
| M3b order types | E3 | limit·stop·stop-limit·exit orders, `explain(strategy)`, MinTRL·signal-weight correlation | G-02~G-09, G-32, G-33, G-37~G-40; P-STATE (no expiry of exit orders)·P-QTY; L2-d (preset meaning); (optional) summary evidence that the user reproduced 3 months of one strategy by hand | `uv run nexusbt explain examples/strategies/mom_kr_exits.py KR:T00007 2019-06-28` → decision path and exit order events |
| M4 multi-market | E3 | multi-sleeve backtests·screening, currency attribution, market rules packs | G-27~G-29, G-36, G-50~G-52; M-CCY·M-SLEEVE (preconditions·counterexamples); a Korean decision cannot use a later US close; FX direction·silence; rule boundaries; the `ZZ` market gives E18 / runs once a pack is added; two-sleeve stage measurement; the person opens `report.html` of the representative long-short result (`examples/strategies/long_short_kr.py --set shorting.enabled=true`) and reads it against the 3.9 Run list; **requirement evidence**: R2 — the end-of-M4 early measurement of chapter 7 (T4.9); R5 — that eye check reads the long-short result by the 3.9 metrics per strategy style, the last of the three representative results | `uv run nexusbt backtest examples/strategies/value_mom.py` → Run summary with per-market columns and an `fx contribution` line |
| M5 paper trading | after E3 (live) | `live`, paper book (transactional), `reconcile` (replay/restatement), `status.json`, `compare`, `Run.why`, adapters, the full CLI | same decision·book → same idempotency key; one order in `live → fill → live`; recovery from a forced kill at a commit boundary (P-BOOK); concurrent writer E35; no future open fill before the data; P-RECON; **requirement evidence**: R1 — the `[costs]` part of the config template (3.11, T5.21) has the line for the broker's US commission and says that the KR `provisional` buy rate of 5 bp (3.11) is optimistic against KR broker commissions of 7 to 25 bp; R3 — the strategy-writing trial of T5.18 (three strategies, each step's time, help and outcome) in the M5 end evidence; R4 — P-LIVE (8.3), E19, `status.json` `last_reconcile` and `first_divergence` (5.9.6), the manual live-operation exception rules (5.9.6 rules 1 to 4), and one measured representative order day (orders, order types, time taken, exceptions, re-entries; the record of 5.9.7 (5)) in the M5 end evidence | `uv run nexusbt live examples/strategies/value_mom.py --book paper:demo --fill next_open` twice → the second is IdempotencyNotice; `uv run nexusbt reconcile --book paper:demo` → `reconciled: yes (replay)` |
| M6 performance·research tools·release gate | E3 performance | `sweep`, DSR·PBO (cohort), probes, start-date probe, L0·L1 caches, capacity scenarios, clean install | fast kernel = reference (same-environment bits); P-CACHE (L0·L1, resolution metadata·captured constants); process-tree RSS·USS measured against 4 GB (an alert, chapter 7); P-STAT; chapter 7 measurement JSON (compared with the earlier ones; no performance gate, #725 Decisions 257); `engine / release` passes (clean wheel + independent producer); **requirement evidence**: R2 — the T6.11 JSON shows equal cold and warm output hashes, P-CACHE-INCR passes (8.3), the attempts line of the 6.3a hygiene box states the recorded-trial scope; R5 — the `hygiene` section (question 8 of 3.9, T6.22) and an eye check of the three representative results with every section. M6 ends at synthetic conformance without the following; they belong to the release gate that comes after it (OI-46): R1 — a backtest on a real snapshot whose first screen shows the CAGR range under cost 0×/1×/2× (5.7), delisting lo/hi (3.8 `scenarios`) and `offsets=3`, and the event-by-event ledger verification table with the fill-vs-decision bp measured against the model's reference (next open, matched order time, type and quantity) (T6.28, T6.29 and the 8.4 table, #162); R2 — on that snapshot, the report's `skipped:` line (6.6) and the coverage outputs (#160) show the per-year missingness | `uv run nexusbt sweep examples/strategies/value_mom.py` → candidate table + PBO + DSR(cohort) + capacity line for the final candidate |
| v1.x | right after v1 | N_eff, Brinson·`first_divergence` | the tests of each T7.x ticket | per ticket |
| (M7) event bridge | E4 | – | chapter 11 design only, no v1 tickets | – |
| (M8) options | E5 | – | chapter 11 design only | – |

**v3.1 end conditions added** [V31, V31-LS]: M1 — T-24·T-25, P-DET (two fresh processes), TDS-A010·A011·V011·V012·H004 pass/fail, F-15·F-16; M2 — T-26~T-28; M3a — G-53~G-56, G-58~G-60, G-66, P-FILLCAUSAL, P-QTY (integer ratios), P-BRIDGE (halt-day events); M3b — G-57, G-61, P-GRID; M4 — G-62, G-67~G-75, P-SLEEVE-ISO, P-SHORT-OFF, L2-e, short-sale ban period test pack; M5 — G-64, G-65, P-TRADES, pre-trade check E36, override·human book replay; M6 — P-CACHE-INCR, task P2b, G-63 (T7.1). Commands to show added: M4 `uv run nexusbt backtest examples/strategies/long_short_kr.py --set shorting.enabled=true` → exposure line·borrow cost·`reconciled: yes`; M5 `uv run nexusbt screen examples/strategies/value_mom.py --show held+near --html`.

**v3.2 end conditions added** [R3]: M0 — resolved defaults fixed (codepoint-first market), pack `base_unit`·`day_count`·KR rounding `down`·ETF/fractional-era seeds·ban table grammar (T0.5a·T0.5b); M1 — resolver existence/terms time (`test_late_terms_revision_visible_at_ex_date`), the four three-valued operations, fixed-salt ties (new T-27 values), malformed exact ratio E13, stamp file identity·pin default `index+root`; M2 — E39·unknown counts per leaf (T2.22); M3a — G-20 variant, G-53 (e)(g)~(j), G-55 (a)~(f), the two P-FILLCAUSAL properties, the two `daily` bridge columns; M3b — minor-unit integer comparison G-57 (f)~(h); M4 — short accounting·lifecycle (G-67 rewritten, G-68 (b)~(d), G-70 (b), G-72 (b)(c), G-73 variant, G-75 (b), G-76, G-77), P-SHORT-OFF differential + baseline, cash interest; M5 — book TWR CAGR (G-65 (b)), manual event protocol, `book=` X-Ray, `TargetState` plumbing (T5.16); M6 — new P-CACHE-INCR cases, shared L0 retention, PBO common period, G-63 (c)(d), T7.V release re-verification.

**v3.3 end conditions added** [R4]: M0 — error layer table·layer case format·internal-term ban test (T0.4b), E40~E46 classes; M3a — money-management slots·built-in sizers·ERC fallback (G-78~G-83), risk rule list·order (G-82·G-85·G-86), account layer·`final_weight`·`risk_state`·drawdown brake round trip (G-84·G-87), P-RISK-OFF·P-SIZE-PURE·P-RISK-SHRINK·P-SKIP, `waterfall.parquet`·`skips.parquet`, `strategy.replace`·`--preview`; M3b — `exits.time_stop` OCO, `risk.no_reentry`; M5 — screen account set (`--ledger`·`--as-backtest`·not evaluated), 20 templates·`init --demo`·30-minute path test, zipline mapping table document, `compare` variant table; M6 — splitters·purging (G-88·G-89, P-SPLIT-DET), `backtest(method=…)` account rules (G-90·G-91, P-WF-STITCH), CPCV·CSCV·hygiene first screen, `ml.factor` (G-92, P-ML-REPRO), triple barrier (G-93), P11 measurement JSON. Commands to show added: M3a `uv run nexusbt backtest examples/strategies/erc_brake.py --preview` → "PREVIEW" line + risk waterfall line; M6 `uv run nexusbt backtest examples/strategies/value_mom.py --method cpcv` → linear result and distribution over 5 paths·PBO·DSR lines.

**v3.4 end conditions added** [R4F]: M1 — TDS A010 error (exact ratio required, T0.15c), an event without an exact ratio follows `decimal_ratio` (the default `exclude_instrument` excludes that instrument from the time the event becomes visible on), a malformed ratio stays E13 (T1.1a); M2 — shared `terminal_value` (T2.7), `Macro.series`·`Events`·`from_parquet(shape=)`·E47 (T2.Ge, T2.23; G-96·G-98; superseded 2026-11-24, #752); M3a — `vol_target` fourth term (G-81 (c)(d)), sizer hand calculation (G-95), INV-23 exclusion list·−0.0, shadow index removal reflected (G-84 (b)), account rule order E16, preview calculation·period (T3.34), conservative side when inclusion is unknown (G-55 (g)(h)); M3b — `on_event` (T3.35; G-97, two templates; superseded 2026-11-24, #752); M4 — exit order `blocked(cash)` (G-94); M5 — 30-minute path first line `uv init` (T5.18, 16 templates); M6 — forward-only ML training (T6.24), grid IS trimming·`backtest(start=t_1)` comparison (T6.20), G-90 numbers, P11 fixture·stage budget·output hash (T1.24, T6.26), `[ml]` install check (T6.15), `buffer-hold` template test (T7.1). Tickets 210 → **213** (new T2.Ge·T2.23·T3.35), golden 93 → **98** (G-94~G-98), error E47.

**v3.4 final-revision end conditions added** [R4G]: M2 — `from_parquet` per-shape signatures·running the E47 fix line (T2.23); M3b — market event target = all (assumption recorded)·explicit `event_instruments` E16, per-side budget + combined-book `k` shrink, end-of-life liquidation-only decision·screen "scheduled exit", end of life·`time_stop` one order (T3.35; G-97 (c)~(e)) (both superseded 2026-11-24, #752); M4 — margin account (T4.Gm, T4.20; G-99~G-102, P-MARGIN-OFF); M5 — two-part config format·`config check`·`config show`·report part 1 values (T5.21). Tickets 213 → **216** (T4.Gm·T4.20·T5.21), golden 98 → **102** (G-99~G-102), property test + P-MARGIN-OFF.

**When spec changes are reflected**: v3 put blueprint SC-01~SC-27 and the P0·P1 (and cheap P2) of the three-reviewer consensus into the body. When a spec gap appears during implementation, it is fixed through the "spec deviation" procedure of 9.5 and this document is revised — v2's "there will be no further spec changes before a milestone starts" was removed because the three-reviewer review refuted it. The ticket where each SC is first implemented·tested is in appendix B.2, RV items in appendix B.4.

**Ticket rules**: a session works on one ticket, and a ticket lands in one or more PRs (decision 2026-11-10, #356, in place of "one ticket = one session = one PR", which practice and the repository's split rule contradicted): each PR has changed lines ≤ 400 (excluding docs·lockfiles; plinth `ci / diff-size`), each is branched from `main` after the previous one merged (none is stacked on an unmerged PR) and says which acceptance criteria it meets and which it leaves to a later one, and the last one closes the issue with every criterion listed beside the PR that met it. Size S ≤ 150 lines, M ≤ 400 lines. The title is a Conventional Commits title also used as the PR title. "Context" is the work, "Done means" is what a person looks at and confirms, "Acceptance" is the names of the tests to write (made to fail first with tdd), "Blocked by" is ticket numbers (replaced by issue numbers once made into issues). **Golden tickets** (`T<m>.G…`) are hand-written per-session arithmetic (8.2) and are merged before the implementation tickets that use them, in a different session. **Engine ticket count (current = v3.4 final + R5 + R7, counted by `tools/spec_lint.py`): M0 16, M1 41 (T0.8d added for the M1 bench), M2 31 (T2.24 added for the reduced P11 (a)), M3a 37, M3b 12 (T5.16a split from T5.16 so that T3.35 has the state record, #152), M4 28, M5 24, M6 31 (including T7.G·T7.1·T7.V), v1.x 2 (T7.2·T7.5) = 222.** Since 2026-11-24 (#752) T0.8a, T2.2, T2.13, T2.Ge, T2.23 (M2) and T3.35 (M3b) are removed, their numbers not reused: M2 26, M3b 11, 216 in all. These counts are from before M1b (#858). Test·decision ids by the same count: hand-calculation answers G-01~G-107 (107), property tests 36 (table 8.3), errors E1~E49 (49, 6.6), ADR 0001~0041 (41, 9.3). The other numbers in this paragraph and below are records from their version. **Engine ticket count: M0 16, M1 40, M2 28, M3a 36, M3b 10, M4 26, M5 22, M6 27, v1.x section: 5 (T7.G·T7.1 at the end of M6, T7.V a check step after T7.1, T7.2·T7.5 in v1.x) = 210** (24 new from v3.2's 188; T7.3·T7.4, moved from v1.x to v1, are absorbed into new tickets T3.29·T3.33). The numbers in the v3.2 sentence below are records from v3.2. Engine ticket count: M0 15, M1 40, M2 28, M3a 28, M3b 9, M4 26, M5 18, M6 17, v1.x section: 7 (T7.G·T7.1 at the end of M6, T7.V a check step after T7.1, T7.2~T7.5 in v1.x) = 188 (from v3.1's 176, 8 by splitting·4 new, mapping table below). The numbers in the v3.1 sentence below are records from v3.1. Engine ticket count: M0 13, M1 39, M2 27, M3a 28, M3b 9, M4 21, M5 16, M6 17, v1.x section: 6 (T7.G·T7.1 go at the end of M6 and T7.2~T7.5 in v1.x) = **176** (34 new from v3's 142 = 141 + tax T4.5b) [V31, V31-LS]. The numbers in the v3 sentence below are records from v3: M0 13, M1 34, M2 23, M3a 22, M3b 7, M4 12, M5 9, M6 16, v1.x 5 = **141** (grown from v2's 112 by splits·new tickets·golden tickets; v2's T0.11·T0.17 were scattered into golden tickets and are gone, and T6.1 moved to T1.24). The dependency graph is acyclic and every "Blocked by" is in the same or an earlier milestone (checked by script when v3 was written; in the repository, T0.12's `test_ticket_graph`).

Rules across tickets, one line each (written as `README.md` in this folder says):

- decided (#43 Decisions, 2026-11-04): from the M1 cut on, the sections the M1 tickets implement (chapter 4, 5.1 to 5.3, 5.9.5, chapter 7's M1 rows, the T0 and T1 entries of 10.1) change only for a defect (a contradiction, a rule a ticket cannot implement as written, a counter-example), proposed as a spec pull request by the ticket that found it; a new feature, guidance text or scenario touching them waits for the end of M1. A rule is changed by #764 piece 6's route: put to the owner, in its own pull request.
- decided (#43 Decisions, 2026-11-18): the spec states a rule in its own words and names plinth only where a command or a file of plinth's is meant; past records are not rewritten.

**v2 → v3 ticket mapping** (check against this table when creating issues):

| v2 | v3 | Reason |
|---|---|---|
| T0.2 | T0.2a (skeleton·ban rules), T0.2b (hygiene·public-name tests) | size |
| T0.7 | T0.7 (to M1) | M0 cut down |
| T0.8 | T0.8a (financials·classifications, M2), T0.8b (FX·indexes·panels, M2), T0.8c (`full`·`full_ci` presets, M3a) | size, moved to just before the consuming milestone |
| T0.9, T0.11, T0.17 | T0.9 (golden format + G-01, M0) + T1.G, T2.G, T3.Ga, T3.Gb, T3.Gc, T4.G | no second engine, moved to just before the consuming tickets |
| T0.13 | T0.13a (manifest·three results·path safety·CLI), T0.13b (schema level·schema files) | size |
| T0.14 | T0.14a (K·R, M1), T0.14b (T·D, M1), T0.14c (value·semantic hash + test vectors, M0) | size, hash before 1.0 |
| T0.15 | T0.15a (corporate-action resolver, `nexusbt_tds.actions`, M1), T0.15b (A·V checks, M1) | one resolver, size |
| T0.16 | T0.16a (core `degrade`, M1), T0.16b (research `degrade`, M2) | so M1 does not wait for all of M0 |
| T1.1 | T1.1a (open·check·E14·rules packs), T1.1b (capabilities·three results·fallbacks F-02~F-04 (F-04 retired 2026-11-22, F-02 2026-11-23, #705)·pins) | size |
| T1.7 | T1.7a (plan·windows·shift propagation), T1.7b (reference executor·fixed summation order·chunk size) | size |
| T1.14 | T1.14a (sealed folders·recovery·source capture), T1.14b (index: candidates·observations·cohorts·pins, numerics environment) | size |
| T2.10 | T2.10a (evaluate API·FactorReport), T2.10b (report.html structure tests) | size, eye check turned into structure tests |
| T3.5 | T3.5a (market orders at the open·tradability), T3.5b (caps·cash allocation by the real cost function) | size, cost function dependency |
| T3.13 | T3.13a (backtest API·metrics), T3.13b (scenarios: gross once) | size |
| T6.1 | T1.24 (to M1) | early measurement |
| (none) | T1.22 `tds import csv`, T1.23 `tds manifest build`, T2.17 English quick start, T2.18 `preregister`, T3.21 E6·E25 warnings, T4.11 `ZZ` market, T6.15 release gate, T6.16 release workflow, T6.17 `bridge` capability test | missing tickets |

**v3.1 → v3.2 ticket mapping** (split by the 400-line rule and meaning boundaries):

| v3.1 | v3.2 | Reason |
|---|---|---|
| T0.5 | T0.5a (config keys·resolved defaults), T0.5b (market rules packs·seed tables) | size; pack seeds grew |
| T0.13b | T0.13b (schema files·verification), T0.13c (schema-level checks) | size |
| T0.15c | T0.15c (A010·A011), T0.15d (V011·V012·H004·`market_rules`) | size |
| T-27 of T2.Gb | moved to T1.Gb | T1.11 (M1) uses T-27 |
| T4.Gs | T4.Gs (short accounting·accrual·bankruptcy·cash interest), T4.Gt (long-short targets·short orders·bans) | size (new cases G-76·G-77, variants) |
| T4.15 | T4.15a (state·collateral·accrual·obligations·bankruptcy), T4.15b (dividends·corporate actions·delisting·estimated replacement), T4.15c (short tax) | size |
| T4.16 | T4.16a (order·reversal·mirror·capacity), T4.16b (exits·bans) | size |
| T5.11 | T5.11a (manual event protocol·import), T5.11b (manual book reconciliation) | size |
| (none) | T2.22 `Filter.fillna`·E39, T4.19 cash interest, T5.16 `TargetState` plumbing, T7.V release re-verification after T7.1 | |

**v3.2 → v3.3 ticket mapping**:

| v3.2 | v3.3 | Reason |
|---|---|---|
| T7.3 `risk.group_caps` (v1.x) | T3.29 (M3a) | group caps into v1 |
| T7.4 `exits.time_stop` (v1.x) | T3.33 (M3b, + `risk.no_reentry`) | time stop into v1 |
| T0.4 | T0.4 + T0.4b (layer line·E40~E46) | size |
| (none) | T3.Gr, T3.27, T3.28, T3.30, T3.31, T3.32, T3.34, T5.17, T5.18, T5.19, T5.20, T6.Gv, T6.19~T6.27 | |

### 10.1 Engine tickets (ready to paste as GitHub issues)

#### M0 — Normative contracts

**T0.1 `docs: add spec v3.4, TDS v1.4, CONTEXT.md, ADRs, license and contributor files`** · `M0` `docs` · S (docs) · Blocked by: none · §2.1, §9.1~9.3
- Context: this spec as `docs/spec/engine-spec-v3.4.md`, TDS v1.4 as `tds/spec/tds-v1.md` (both the 2.7 public edition: private notes·TDS chapter 11·personal paths·hosts removed), 9.2 as `CONTEXT.md`, the spec's first decision records one file each in `docs/adr/` (English canonical drafts = `CONTEXT.md`·`CONTEXT.ko.md`·`docs/adr/*.md`·`README.md`·`README.ko.md`·`SPEC-INDEX.md` in the engine folder's `handoff/`, copied as they are), `LICENSE` (full Apache-2.0 text)·`NOTICE`, `CONTRIBUTING.md`·`SECURITY.md`·`CODE_OF_CONDUCT.md` (short templates), English `README.md` template (public document language is chapter 12 OI-45).
- Done means: on GitHub, `CONTEXT.md`, the files of `docs/adr/`, `tds/spec/tds-v1.md`, `LICENSE` and `CONTRIBUTING.md` are visible, and each ADR has the three sections "Status: accepted, Date, Context/Decision/Consequences" (ADR-0021 is accepted too — OI-20 user decision 2026-10-28). No producer name from the banned-word list (`.hygiene-private.txt`) is in the public-edition documents.
- Acceptance: (docs PR) `grep -c "Apache License" LICENSE` ≥ 1; `grep -riFf .hygiene-private.txt docs/spec tds/spec docs/adr CONTEXT.md CONTEXT.ko.md README.md README.ko.md | wc -l` = 0.

**T0.2a `chore: workspace skeleton with layer and ban rules`** · `M0` `infra` · M · Blocked by: T0.1 · §2.3–2.6
- Context: the empty packages of the 2.3 tree (`src/nexusbt/*`, `tds/src/nexusbt_tds`), the 2.4 public names in each `__init__` (body `NotImplementedError`), ruff banned-api (the 2.5 list), pytest markers·hypothesis profiles (`ci`, `deep`), `[project.scripts] nexusbt`, `tds`.
- Done means: `uv run nexusbt --help` and `uv run tds --help` print their subcommand lists, and `uv run pytest` passes the import tests.
- Acceptance: `tests/unit/test_import_rules.py::test_layer_graph_respected`, `::test_banned_imports_absent_in_src` (including pickle·duckdb·zipline), `::test_tds_does_not_import_nexusbt`.

**T0.2b `test(repo): public hygiene and public-name tests`** · `M0` `repo` · S · Blocked by: T0.2a · §2.7, §3.1
- Context: all the 2.7 tests in `tests/repo/test_public_hygiene.py`, `test_public_names_match_spec_3_1`.
- Done means: creating a file that deliberately contains a `/Users` home path, or a sentence with a producer name from the banned-word list + a ticket number, makes the tests fail, and a document containing "section 10.2" passes.
- Acceptance: `tests/repo/test_public_hygiene.py::test_no_private_paths`, `::test_section_numbers_not_ip`, `::test_no_producer_internal_refs`, `::test_no_data_files`, `::test_license_headers`, `::test_tds_public_has_no_producer_names`; `tests/unit/test_import_rules.py::test_public_names_match_spec_3_1`.

**T0.3 `feat(contracts): id constant, engine column sets, phases and artifact schema versions`** · `M0` `contracts` · M · Blocked by: T0.2a · §2.4, §4.6, §5.6.3, header "Identifier name"
- Context: `ID_COLUMN`, `ENGINE_COLUMNS` (the per-dataset columns·TDS types of the 4.6 table), `Unit`, `Currency`, `Phase` (5.6.3 order), the 26 policy enums of 2.4 (`DelistingPolicy` … `RoundingModePolicy`), `RUN_SCHEMA`·`EVENTS_SCHEMA`·`CHECKPOINT_SCHEMA`.
- Done means: `uv run python -c "from nexusbt.contracts import ENGINE_COLUMNS, Phase; print(sorted(ENGINE_COLUMNS)); print(list(Phase))"` prints the dataset names of the 4.6 table and the seven phases in order.
- Acceptance: `tests/unit/contracts/test_contracts.py::test_engine_columns_subset_of_tds_schemas`, `::test_no_id_alias_public`, `::test_phase_order_matches_5_6_3`.

**T0.4 `feat(contracts): teaching error classes E1..E39 and message format`** · `M0` `contracts` · M · Blocked by: T0.2a · §6.6
- Context: `NexusBTError` and the E1~E39 classes, the five-part message formatter, the blocking/failure/warning/notice classification, the format in which E14 carries the TDS code list and `producer.hints`.
- Done means: `uv run python -c "import nexusbt as nx; raise nx.ColumnNameError.example()"` prints in the 6.6 shape (what/where/why/fix/more).
- Acceptance: `tests/unit/contracts/test_errors.py::test_all_codes_present_E1_to_E39`, `::test_message_has_five_parts`, `::test_blocking_classification_matches_table`, `::test_snapshot_error_carries_tds_codes_and_hints`, `::test_messages_have_no_producer_tickets`.

**T0.4b `feat(contracts): error layer line, layer table, internal-term ban and engine-bug report`** · `M0` `contracts` · M · Blocked by: T0.4 · §6.6, §8.4b
- Context: a second `layer` line and per-layer tails in the 6.6 format, `tests/errors/layers.toml` (code·condition → layer), the E40~E49 classes (E47 `DatasetShapeError` v3.4; E48 `PretrainedLeakError`·E49 `PretrainedOverlapWarning` R5), `EngineBugError` (exit code 2) and `nexusbt bugreport RUN_ID` (reproduction command·manifest·version bundle), a helper that attaches layer·fix lines to user-function exceptions with `add_note`, and `errors/hints.toml`.
- Done means: `uv run python -c "import nexusbt as nx; raise nx.ColumnNameError.example()"` prints six parts including a `layer  your code — …` line, and `nexusbt bugreport demo` prints the bundle file path.
- Acceptance: `tests/errors/test_layers.py::test_every_code_has_layer_case`, `::test_layer_line_matches_table`, `::test_layer_tail_fields`, `::test_fix_line_present`, `tests/errors/test_no_internal_terms.py::test_public_layers_have_no_internal_names`, `tests/errors/test_user_exception_note.py::test_original_class_and_traceback_kept`, `tests/unit/contracts/test_errors.py::test_codes_E40_to_E49_present`.

**T0.5a `feat(config): load and validate nexusbt.toml keys with resolved defaults`** · `M0` `config` · M · Blocked by: T0.3 · §3.11, §2.6, §5.1.3
- Context: every key·default·validation of 3.11, `nx.config()`, suggestions for unknown keys, a ban on secret key names, reserved keys, validating keys that contain a market name against the snapshot's `markets` (`load_config(markets=)`), returning the resolved defaults (first market = first by UTF-8 byte order of the `markets` keys → `clock`·`base_ccy`·`sleeves`) for the manifest, a check that the closed interval `max_net` ∋ 0, a long-short feasible-region check function (3.7; called by T4.14).
- Done means: with an empty `nexusbt.toml` + markets `KR`,`US`, `nx.config()` prints the 3.11 defaults, and reordering the `markets` object to `US, KR` leaves the resolved `clock = KR_close`·`base_ccy = KRW` the same; `[sleeves] weights = {JP = 1}` gives E16 "unknown market JP; snapshot markets: KR, US"; `[broker] api_key = "x"` gives E16 "secrets do not belong in nexusbt.toml"; `[shorting] max_net = [0.2, 0.8]` gives E16.
- Acceptance: `tests/unit/config/test_config.py::test_defaults_match_spec_table`, `::test_unknown_key_suggests`, `::test_sleeve_weights_must_sum_to_one`, `::test_markets_from_manifest`, `::test_segments_must_not_overlap`, `::test_preset_zipline_forbidden_in_toml`, `::test_secret_like_keys_rejected`, `::test_reserved_keys_accept_only_v1_value`, `::test_data_root_from_env`, `::test_shorting_disabled_by_default`, `::test_market_object_reordering_preserves_resolved_defaults`, `::test_net_interval_must_contain_zero`, `::test_pins_default_index_root`, `::test_cash_rate_default_zero`.

**T0.5b `feat(config): market rules packs, grid units and seed tables with verification flags`** · `M0` `config` · M · Blocked by: T0.5a · §4.7
- Context: `resources/markets/{KR,US,_generic}.toml` and their schema check (`[grid]`·`[rounding]`·`[shorting]` sections), `ticks/{kr,us}_tick_table_v1.csv` (with `venue_group`), `shorting/kr_short_bans_v1.csv` (half-open intervals, `scope` grammar, `except_universe_ids`), the `limits/`·`costs/` seeds, `source`·`verified` on every seed row, a rule listing function for release evidence (source·bounds·`verified` of the rows applied).
- Done means: `uv run python -m nexusbt.config.packs --describe KR` prints the pack version·`base_unit`·rounding rule·`day_count`·seed table row counts and the number of `verified = false` rows (numerator/denominator).
- Acceptance: `tests/unit/config/test_rules_packs.py::test_kr_us_generic_packs_valid`, `::test_grid_rounding_shorting_sections`, `::test_seed_tables_marked_unverified`, `::test_base_unit_per_market`, `::test_kr_rounding_default_down`, `::test_etf_venue_group_tick`, `::test_us_pre_decimal_rows`, `::test_ban_table_scope_grammar`, `::test_ban_intervals_half_open`, `::test_rule_listing_has_source_and_verified`.

**T0.10 `ci: add engine and tds check jobs`** · `M0` `infra` · S · Blocked by: T0.2a · §9.1 — **pushed by the user** (workflow permission)
- Context: the `engine / parity`, `engine / property-deep`, `engine / perf-smoke`, `engine / docs-examples`, `engine / golden-guard`, `engine / release`, `tds / conformance`, `tds / schemas` jobs. A job with no tests yet passes with "no tests yet", but **the end conditions of the milestone where each job joins the required list (9.1 table) include "that job actually runs ≥ 1 test"**.
- Done means: the eight jobs show green in the PR's Checks tab. Adding them to the required list is done by the user at the end of each milestone (`tds / *`·`engine / golden-guard` at the end of M0).
- Acceptance: each job log shows the command it runs (9.1 table).

**T0.12 `docs: requirement status map and ticket graph check`** · `M0` `docs` · S · Blocked by: T0.1 · appendix B, §10
- Context: `tests/repo/test_ticket_graph.py` (reads the ticket lines of the plan and checks that the "Blocked by" graph is acyclic and that each dependency is in the same or an earlier milestone).
- Done means: the graph test passes, and so does the test that every ticket appendix B names is a ticket of the plan.
- Acceptance: `tests/repo/test_ticket_graph.py::test_acyclic_and_milestone_order`, `::test_every_ticket_appendix_b_names_is_a_ticket_of_the_plan`.

**T0.13a `feat(tds): manifest-level checker, profile results, path safety and CLI`** · `M0` `tds` · M · Blocked by: T0.2a · §2.6, §4.3, §4.4, §8.4a, TDS 4·7·8·10
- Context: `read_manifest`, `check(level="manifest")` (M001~M014: including path safety M012·duplicate path M013·unknown required resolution rule M014), `PROFILES` (TDS chapter 7, `@version`), the profile's **three results** (`ProfileStatus`: declared / verified_level / result; rules that level cannot see are `not_checked`), reading `producer.hints`, CLI `tds check/describe`, JSON Lines output, exit codes, M-code pass/fail packages in `tds/conformance/build.py`.
- Done means: `uv run tds check tds/conformance/TDS-M012/fail --format json` gives one `TDS-M012` line and a summary line (the profile's three results) with exit code 1; checking a package that only declares a profile at `manifest` reports its row rules as `not_checked`.
- Acceptance: `tds/tests/test_conformance.py::test_M_codes`, `::test_M012_path_escape`, `::test_M013_duplicate_path`, `::test_M014_unknown_required_rule`; `tds/tests/test_profiles.py::test_profile_three_results`, `::test_manifest_level_never_reports_unchecked_as_pass`; `tds/tests/test_cli.py::test_exit_codes`, `::test_jsonl_output_schema`.

**T0.13b `feat(tds): schema files with stability status and table verification`** · `M0` `tds` · S · Blocked by: T0.13a · TDS 5·10
- Context: `tds/schemas/<kind>/1.0.json` (the TDS chapter 5 datasets, each file with `status: stable|experimental`; only the daily equity datasets are stable), `tds.schemas.verify` (document tables = schema files).
- Done means: `uv run python -m nexusbt_tds.schemas.verify` prints the stable/experimental lists and "doc tables match schema files".
- Acceptance: `tds/tests/test_schemas.py::test_schema_files_cover_stable_datasets`, `::test_experimental_schemas_flagged`, `::test_doc_tables_match_schema_files`.

**T0.13c `feat(tds): schema-level checks with S-code conformance packages`** · `M0` `tds` · M · Blocked by: T0.13b · TDS 8
- Context: `check(level="schema")` (S001~S010: Parquet footer·statistics·partition paths·types), S-code pass/fail packages (`tds/conformance/build.py`).
- Done means: `uv run tds check tds/conformance/TDS-S002/fail --format json` gives `TDS-S002` and exit code 1; the row rules of a profile checked at the `schema` level are `not_checked`.
- Acceptance: `tds/tests/test_conformance.py::test_S_codes`, `::test_schema_level_reports_rows_not_checked`.

**T0.14c `feat(tds): canonical value hash, semantic hash and published test vectors`** · `M0` `tds` · M · Blocked by: T0.13b · TDS 4.5, §4.2, §5.9.4
- Context: the canonical value serialisation of TDS 4.5 (per-type byte rules, null tag, −0.0 normalisation, key sorting, partition columns included) → `value_hash`, package `value_sha256`, canonical JSON of resolved metadata + value hash → `semantic_sha256`, `physical_sha256`, `tds hash [--write]`, `tds/conformance/hash-vectors.json` (11 small hand-written tables with expected byte strings·sha256; cross-checked with `tds/tests/ref_encoder.py`, a pure-Python reference encoder that does not use pyarrow), H001~H003.
- Done means: `uv run tds hash PKG` gives the same value·semantic hashes for two packages with the same content written with only compression·row groups changed, and a package with only one `availability` rule changed has the same value hash and a different semantic hash.
- Acceptance: `tds/tests/test_hash.py::test_file_value_hash_written`, `::test_vectors_match_published`, `::test_reference_encoder_matches_pyarrow_path`, `::test_value_hash_ignores_physical_choices`, `::test_recompress_same_semantic`, `::test_availability_change_changes_semantic`, `::test_partition_columns_from_path`; `tds/tests/test_conformance.py::test_H_codes`.

**T0.6 `feat(testing): synthetic TDS package part 1 - hand-authored tiny and small calendars, instruments, symbols, bars`** · `M0` `testing` · M · Blocked by: T0.3, T0.13c, T0.14c · §4.8 (1)(2)(3)
- Context: the `make_snapshot` skeleton, `tiny` (a table set by hand in which the case yaml becomes the rows as it is, no randomness) and `small`'s `calendar_sessions` (with `session_ord`)·`instruments`·`instrument_symbols` (with `ts_known_to`)·dense `bars` (cum factor 1.0), the `markets=("KR","US","ZZ")` choice, `tds.json` (hashes from `tds.hash`, a few lines of `producer.hints`).
- Done means: `uv run python -m nexusbt.testing.synth --preset tiny --out .scratch/snap --validate` prints row counts per dataset and `value_sha256`·`semantic_sha256`, identical on two runs; `tds check --level schema` passes.
- Acceptance: `tests/unit/testing/test_synth.py::test_deterministic_bytes`, `::test_tiny_is_hand_authored_no_rng`, `::test_bars_dense_per_listing`, `::test_sessions_have_utc_open_close_with_dst`, `::test_symbol_reuse_present`, `::test_zz_market_generated`.

**T0.9 `test(golden): golden case format, literal-arithmetic checks, guard and G-01`** · `M0` `golden` · S · Blocked by: T0.6 · §8.2
- Context: the `tests/golden/cases/<id>.yaml` format (expected numbers per session·phase), `tests/golden/check/<id>.py` check rules (arithmetic·rounding only), `test_handcalc_self.py` (AST: no loops·classes·engine imports), `tests/repo/test_golden_guard.py`, `.github/CODEOWNERS` (`tests/golden/**` = the user), case G-01 (market buy at the open, provisional costs, integer minor units).
- Done means: `uv run python tests/golden/check/G-01.py` prints a per-session cash (minor units)·fill quantity table that equals the hand-checked numbers in the yaml comments; editing `cases/G-01.yaml` on an implementation branch makes the guard test fail.
- Acceptance: `tests/golden/test_handcalc_self.py::test_no_general_loops`, `::test_checks_import_no_engine`, `::test_case_G01_expected_present`; `tests/repo/test_golden_guard.py::test_impl_pr_cannot_edit_expected`.

#### M1 — Snapshot + Pipeline slice + first public path

**T0.7 `feat(testing): synthetic TDS package part 2 - corporate actions with revisions, delistings, tradability, eligibility, share counts`** (eligibility, share counts: leaves with its code in #752's R3) · `M1` `testing` · M · Blocked by: T0.6 · §4.8 (4)~(6) *(to M1, revision·cancellation events, late publication of delisting proceeds; eligibility and share counts removed 2026-11-24, #752)*
- Context: event generation and `EventSpec` injection, revisions (`revision_of`)·cancellations, `price_factor`·`share_factor`·`factor_method`, what the events applied to the prices agrees with the resolver's latest revision (until 2026-11-22 as `cum_factor_*`, #705), `delistings` (some with late `ts_value_available`), `tradability_daily` (`availability_by_column`).
- Done means: the `--preset small --validate` output has a line with the counts of revision·cancellation events, and the generator's record of what the events applied matches the checker's resolver (`test_factor_event_reconciliation`; until 2026-11-22 the output's "TDS-A001: 0", #705).
- Acceptance: `test_synth.py::test_factor_event_reconciliation`, `::test_reverse_split_makes_factor_non_monotonic`, `::test_revisions_and_cancellations_present`, `::test_injected_event_overrides_random`, `::test_delisted_on_matches_delistings`.

**T0.8d `feat(testing): full-scale synthetic preset of the m1 datasets for the bench`** · `M1` `testing` · S · Blocked by: T0.7 · §4.8, §7
- Context: `--preset full` at the scale of the 4.8 table (KR 5,500 + US 22,100 instruments ever listed, 1995-01-02 → 2024-12-31), generating the datasets of T0.6 and T0.7 only, which the M1 workloads of chapter 7 read; its snapshot id is `synth-full-m1-0001`. T0.8c adds the M2 datasets and `full_ci` later.
- Done means: `python -m nexusbt.testing.synth --preset full --out DIR --validate`, run by a person on the compute machine, passes and prints the row counts, time and size (figures into the milestone tracking issue).
- Acceptance: `test_synth.py::test_full_preset_parameters_match_table`, `::test_full_is_small_rules_at_full_scale` (both check the preset's parameters and rules without generating `full` in CI).

**T0.14a `feat(tds): full-level key and reference checks`** · `M1` `tds` · M · Blocked by: T0.13c · TDS 8.3
- Context: K001~K011 and R001~R009 (including edition keys) of `level="full"`, pass/fail packages per code.
- Done means: in hand-made conformance packages each code appears exactly once; GICS level 1·3 rows with the same effective·known periods do not raise K001.
- Acceptance: `tds/tests/test_conformance.py::test_K_codes`, `::test_R_codes`, `::test_classification_levels_not_duplicate`.

**T0.14b `feat(tds): full-level time and density checks with rectangle lookup`** · `M1` `tds` · M · Blocked by: T0.14a · TDS 6.3, 8.3
- Context: T001~T013 (T012 = uniqueness of the rectangle lookup on two time axes, level·edition cases), D001~D004, the reference implementation `nexusbt_tds.pit.rect_lookup` (the engine uses the same function, 5.3.6).
- Done means: in a package with rows announced in advance with a future effective date, T012 is not raised; it is raised only for two rows that truly overlap.
- Acceptance: `tds/tests/test_conformance.py::test_T_codes`, `::test_D_codes`, `::test_T012_rectangle_examples_1_to_5`.

**T0.15a `feat(tds): corporate action resolver parameterized by knowledge cutoff`** · `M1` `tds` · M · Blocked by: T0.14a · §5.3.3a, TDS 5.11
- Context: `nexusbt_tds.actions.resolve(events: pa.Table, cutoff) -> ResolvedActions` (chains, the revision chosen by existence time `ts_known`, status, waiting on terms time `ts_terms`, the four effects, a helper computing revision differences, marking late-discovered events, the canonical chain hash for the L0 key `chain_digest(market, year_end)`). pyarrow only, a pure function. The engine (`Snapshot.actions`) and, until 2026-11-22 (#705), the checker (A001) use the same function.
- Done means: an example prints as a table the result of resolving one instrument's revision chain at three reference times (chosen revision·price factor·share factor·entitlement).
- Acceptance: `tds/tests/test_actions.py::test_resolver_at_cutoffs` (amended split·cancelled dividend·amendment after payment·split + dividend on the same day·lapsed entitlement·no factor × 3 reference times), `::test_share_factor_explicit_not_inferred`, `::test_revision_cycle_A007`, `::test_late_terms_revision_visible_at_ex_date`, `::test_existence_time_ignores_effective_when_announced`, `::test_late_discovered_event_flagged`, `::test_chain_digest_includes_all_revisions_and_times`.

**T0.15b `feat(tds): adjustment and value checks via the resolver`** · `M1` `tds` · M · Blocked by: T0.15a · TDS 5.11, 8.3
- Context: A001~A009 (A001, until 2026-11-22 (#705), multiplied only the one latest revision per amendment chain with the resolver at `c = +∞`; A008 share-event terms published after the effective date; A009 spin-off factor publication time < effective session close), V001~V050.
- Done means: in a package with a reverse split, A001 is not raised even though the factor is not monotonic, and a factor that multiplies both the old and the new revision of an amendment chain is caught by A001 (A001 was retired on 2026-11-22 with `cum_factor_*`, #705; the reverse-split test now holds that no A code fires).
- Acceptance: `tds/tests/test_conformance.py::test_A_codes`, `::test_V_codes`, `::test_reverse_split_not_flagged`; until 2026-11-22 also `::test_A001_multiplies_latest_revision_once`.

**T0.16a `feat(testing): degraded synthetic packages for core fallbacks`** · `M1` `testing` · M · Blocked by: T0.7, T0.15b · §4.5, §4.8
- Context: the core data values of `degrade=`: `no_ohlc`, `kr_ex_is_record`, `us_div_split_adjusted_no_dates`, `no_delistings` (`no_cum_factors` left on 2026-11-22: the generator writes no `cum_factor_*`, #705; `no_sessions` left on 2026-11-23 with F-02: a package without `calendar_sessions` is E14 at open, #705; `sparse_bars` left on 2026-11-23 with F-03: daily bars are dense, TDS 5.5, #705); each value removes from the declaration the profiles it cannot keep (checks still pass).
- Done means: `--preset small --degrade no_ohlc,kr_ex_is_record --validate` prints the declared profiles (no core) and the three results.
- Acceptance: `test_synth.py::test_synth_conforms_degraded_core[<each value>]` (one per value of the test's `DROPS_CORE`), `::test_degrade_drops_declared_profiles`.

**T1.G `test(golden): time and pipeline cases for M1 (T-07, T-09..T-12, T-15, T-20, T-23)`** · `M1` `golden` · M · Blocked by: T0.9, T0.7 · §8.2
- Context: windows before and after a split·reverse split, symbol reuse, a start date on a holiday, ties, the three forms of 12-1 momentum, a window with a null factor, late bar `ready_delay`, `every(n)` calendar anchor. For each case, yaml numbers + a check file. Written in a different session and merged before the consuming tickets (T1.3, T1.8, T1.9, T1.11).
- Done means: `uv run python tests/golden/check/T-12.py` prints the same value for the three forms, and `T-20.py` a table in which a late bar stays in its own row and the decision uses it from the first row whose `ready` reaches its `ts_available`.
- Acceptance: `test_handcalc_self.py::test_time_cases_M1_expected_present`.

**T1.1a `feat(data): open TDS snapshots with checker, producer-neutral errors and market rules packs`** · `M1` `data` · M · Blocked by: T0.3, T0.4, T0.5b, T0.13c, T0.14c, T0.6 · §4.1–4.4, §4.7
- Context: `open_snapshot`, resolving `LATEST`, check level, path safety, E14 (TDS code + `producer.hints`), version rules (M011 warning·M014 E14), a rules pack check per market (E18 if missing, `allow_untested` recorded), `Snapshot.semantic_hash/value_hash/physical_hash`, `.markets`.
- Done means: on synthetic small, prints `s.id, s.semantic_hash, s.markets`; on a `markets=("KR","ZZ")` snapshot, `nx.universe("ZZ")` gives E18 ("no market rules pack for ZZ"); the E14 of a broken package with `producer.hints` carries the hint sentence.
- Acceptance: `tests/unit/data/test_open_snapshot.py::test_latest_resolved_once`, `::test_E14_carries_tds_code_and_hint_not_ticket`, `::test_unknown_required_rule_E14`, `::test_market_without_pack_E18`, `::test_allow_untested_recorded`, `::test_semantic_hash_exposed`, `::test_open_path_and_latest_parent` (`nx.open`·`[data] path`), `::test_cloned_and_hardlinked_partitions_ok`, `::test_malformed_exact_ratio_E13`, `::test_missing_exact_ratio_excludes_instrument_from_event` (the default `exclude_instrument`: the snapshot opens and only that instrument is excluded from the time the event becomes visible on).

**T1.1b `feat(data): capabilities, profile results, core fallbacks and pins`** · `M1` `data` · M · Blocked by: T1.1a, T0.16a · §4.3–4.5, §4.2
- Context: `CapabilityRequest` (features the graph uses → required data, 4.3 table), the profile's three results, `capabilities`·`fallbacks`, F-02 (session table fallback; retired 2026-11-23, #705)·F-03 (densifying; retired 2026-11-23, #705)·F-04 (factors from the resolver; retired 2026-11-22, #705), E14 for packages violating their declaration (no fallback), pins (index + root by default, failure is a warning + `retention: unmanaged`), the `verify` stamp (`runs/.cache/verified/`, `(dev, inode, size, mtime_ns)` per file).
- Done means: a graph using only `Price` runs on a package with only core datasets; on a `degrade=["no_tick_info"]` snapshot with the untested market ZZ, one E30 line and F-15 in `s.fallbacks` (F-02's `no_sessions` and F-03's `sparse_bars` until their retirement, 2026-11-23, #705); a run works on a read-only data root and the pin is in the index; changing one file gives E14 (`TDS-H001`) under `verify="full"`; editing one file in place after the stamp makes the next open see a different identity, recompute sha256 and give E14.
- Acceptance: `test_open_snapshot.py::test_three_status_distinct`, `::test_price_only_graph_needs_core_only`, `::test_declared_but_broken_is_E14_not_fallback`, `::test_full_verify_detects_tamper`, `::test_readonly_root_runs`, `::test_pin_in_index`, `::test_a_package_without_calendar_sessions_is_e14_at_open` (in place of `::test_fallback_F02_sessions`, F-02 retired 2026-11-23, #705), (`::test_fallback_F03_densify` left with F-03, 2026-11-23, #705), `::test_fallback_F04_factors_from_resolver`, `::test_fallbacks_fail_mode_raises_E14`, `::test_volume_unit_warning_lifted_E30`, `::test_fallback_F15_grid_minor_unit`, `::test_verified_stamp_detects_later_tamper`, `::test_inplace_edit_invalidates_stamp_and_l0`, `::test_readonly_package_all_consumption_paths`, `::test_default_pins_written_to_root_or_warn`, `::test_default_pin_survives_three_publications`, `::test_bars_keep_ts_available` (G-TIME-LATE: an opened snapshot keeps each bar's `ts_available`).

**T1.2 `feat(cli): nexusbt init and doctor`** · `M1` `cli` · S · Blocked by: T1.1b · §3.10
- Done means: `uv run nexusbt init --data-root .scratch/snap && uv run nexusbt doctor` prints the snapshot id, semantic hash, edition, the profile's three results, unchecked items, the fallback list, per-market rules pack·period·instrument count·daily row count, column count and free disk space; with `.publishing` in the root, "publishing in progress"; a line with the number of runs whose root pin could not be written, "pins not visible to producer".
- Acceptance: `tests/unit/cli/test_doctor.py::test_doctor_lists_markets_packs_and_counts`, `::test_doctor_lists_fallbacks_and_unchecked`, `::test_init_uses_env_root`, `::test_publishing_marker`, `::test_pins_not_visible_line`.

**T1.3 `feat(data): calendars, session rounding, ready times, phases and decision grids`** · `M1` `data` · M · Blocked by: T1.1b, T1.G · §5.1.2, §5.1.3, §5.1.6, §5.6.3, §3.7 schedule
- Done means: `examples/dev/show_grid.py`, made by this ticket (monthly schedule, KR, 2019), prints 12 month-end sessions and `decision_ts` (UTC); an E9 notice for a start date on a holiday; the decision dates of `every(5)` stay the same when the start date moves by one day.
- Acceptance: `tests/unit/data/test_calendar.py::test_monthly_last_session`, `::test_start_rounds_forward_end_backward` (T-10), `::test_weekly_quarterly`, `::test_T23_every_anchor_independent_of_start`, `::test_ready_delay_from_availability_rule`, `::test_default_clock_codepoint_first_market`, `tests/golden/test_time.py::test_T20_late_bar_ready_delay`, `::test_G_TIME_LATE_ready_and_late_bar` (G-TIME-LATE: `ready(t)` and the `LateBar` count of the 8.4 table; decision 2026-11-10, #356: this ticket's dependencies give no `SMA`, `top` or orders, so each later stage owns one test of the table, T1.4 the row, T1.9 A's `SMA(3)`, T1.11 the target and T3.4 the order intents).

**T1.4 `feat(data): dense market blocks from daily bars`** · `M1` `data` · M · Blocked by: T1.3 · §5.3.1, §4.6, §5.3.9 L0 key
- Context: `market_block`, dictionary index → column number, `obs_status`, existence mask, tail overlap, choosing files by manifest statistics, excluding index·synthetic instruments, the `l0_key(...)` function (the cache implementation is T6.12).
- Done means: an example printing the shape·existence mask of `Snapshot.market_block("KR", ["close"], sessions)` shows NaN on halted sessions, False before listing, and no index instruments.
- Acceptance: `tests/unit/data/test_market_block.py::test_obs_status_halted_is_nan`, `::test_existence_mask`, `::test_index_and_synthetic_not_in_block`, `::test_dictionary_index_mapping_matches_instrument_ids`, `::test_tail_overlap_rows`, `::test_partition_values_from_path`, `::test_l0_key_partition_scoped`, `::test_l0_key_ignores_watermark`, `::test_l0_key_ignores_advisory_value_hash`, `::test_late_bar_stays_in_its_row` (G-TIME-LATE: the bar of s is in row s with its `ts_available`, never in row s+1), `::test_l0_key_axis_rows_invalidation_table` (2026-11-04: the four rows of the 5.3.9 table change exactly the keys of the years they name), `::test_l0_key_ignores_axis_rows_outside_the_year`.

**T1.5 `feat(pipeline): term value objects, operators, graph hash and captured constants`** · `M1` `pipeline` · M · Blocked by: T0.2a · §3.3, §5.3.9, §6.5(6)
- Done means: `print(nx.describe(Returns(232).shift(21) + 1))` prints the node tree and the structural hash; the same expression twice → the same hash; changing `THRESHOLD = 10`, read by a user function, to 20 changes the hash.
- Acceptance: `tests/unit/pipeline/test_terms.py::test_operator_result_types`, `::test_negative_shift_raises_E1`, `::test_graph_hash_stable_and_order_sensitive`, `::test_pipeline_object_columns_screen`, `::test_captured_scalar_changes_hash`.

**T1.6 `feat(pipeline): datasets from TDS dictionaries and type stubs`** · `M1` `pipeline` · M · Blocked by: T1.1b, T1.5 · §3.2
- Done means: after `uv run nexusbt stubs`, `Price.`·`Meta.` autocomplete in the editor; `Price.clsoe` → E7 "Did you mean: close"; `Meta.country` works as an alias of `Meta.market`; `Meta.delisted_on` does not exist (E7).
- Acceptance: `tests/unit/pipeline/test_datasets.py::test_price_columns_fixed`, `::test_typo_suggestions`, `::test_stub_file_generated`, `::test_meta_aliases`, `::test_meta_has_no_hindsight_columns`, `::test_is_label_columns_only_in_Label`, `::test_schema_registry_injected_at_binding`.

**T1.7a `feat(compute): planner with window and shift row propagation`** · `M1` `compute` · M · Blocked by: T1.4, T1.5 · §5.3.2
- Done means: the debug log of `nx.run_pipeline(..., freq="monthly")` shows "rows computed: X of Y", confirming that monthly computes only some rows; nested windows + shift get the needed rows right even across chunk boundaries.
- Acceptance: `tests/unit/compute/test_planner.py::test_window_rows_propagate`, `::test_shift_rows_propagate`, `::test_nested_windows_across_chunks`, `::test_shared_node_computed_once`, `::test_daily_cross_section_feeding_window_computed`.

**T1.7b `feat(compute): reference executor with fixed summation order and budgeted chunking`** · `M1` `compute` · M · Blocked by: T1.7a · §5.3.8, §5.3.10
- Done means: the reference sum function gives the left-fold value in a case where its order differs from `np.sum`; when `memory_budget_gb` is small, the result stays the same even though chunks split into quarters·months.
- Acceptance: `tests/unit/compute/test_reference_numerics.py::test_left_fold_order_defined`, `::test_no_numpy_pairwise_in_reference`, `::test_transcendental_uses_compiled_elementwise`; `tests/unit/compute/test_chunking.py::test_sub_year_chunks_when_budget_small`; `tests/unit/test_import_rules.py::test_kernel_seam_signatures_arrow_only` (`nx.compute._kernels` seam); `tests/unit/compute/test_executor.py::test_chunk_boundary_values_equal_unchunked`, `::test_cutoff_hides_late_cells` (decision 2026-11-10, #356: the part of P-CHUNK and P-FUT that needs no built-in factor or selection, tested at the executor before T1.19).

**T1.8 `feat(compute): as-of adjustment reference and registered kernel classes`** · `M1` `compute` · M · Blocked by: T1.7b, T0.15a, T1.G · §5.3.3, §5.3.3a, §5.3.4, §4.6 (null factors)
- Done means: an example printing the windows before and after split·reverse split events gives the same numbers as the T-07 case; rows before a `price_factor` null event are NaN and the `AdjustmentUnavailable` count is printed; an amended split ratio gives different windows depending on the reference time.
- Acceptance: `tests/golden/test_time.py::test_T07_split_reverse_split_windows`, `::test_T15_unavailable_factor_masks_window`, `tests/unit/compute/test_adjust.py::test_revision_changes_window_by_cutoff`, `tests/property/test_adjust.py::test_P_ADJ_kernel_classes`.

**T1.9 `feat(factors): returns, moving averages, volatility and traded value`** · `M1` `factors` · M · Blocked by: T1.8, T1.Gb · §3.4, §5.3.10
- Context: Returns, DailyReturns, SMA, AverageDollarVolume, AverageTradedValue, AnnualizedVolatility, RollingStd (reference implementation, left-fold definition).
- Done means: unit tests showing the default input·missing values·minimum observations·ready rule of each row of the 3.4 table pass; T-12 passes.
- Acceptance: `tests/unit/factors/test_conformance.py::test_<name>_nan_rule` (7), `::test_returns_default_is_close_tr`, `tests/golden/test_time.py::test_T12_momentum_forms_equal`, `tests/golden/test_factors.py::test_T25_<name>` (7, v3.1), `tests/golden/test_time.py::test_G_TIME_LATE_sma_values` (G-TIME-LATE: A's `SMA(3)` 10.5, 12, 15 with the late bar NaN at s, rows s and s+1 the same with the earlier and the later snapshot; decision 2026-11-10, #356).

**T1.10 `feat(factors): ewma, vwap, rsi, max drawdown and ops`** · `M1` `factors` · M · Blocked by: T1.9, T1.Gb · §3.3, §3.4
- Done means: `nx.describe(nx.factors)` prints a table of the 12 built-in factors (the three return-series kernels of 2026-11-24 join the table with T2.19) with default input·adjustment class·numerics class.
- Acceptance: `test_conformance.py::test_ewma/vwap/rsi/maxdd_*`, `::test_ewma_weights_precomputed`, `tests/unit/pipeline/test_ops.py::test_rolling_min_periods`, `::test_coalesce_explicit_fill`, `tests/golden/test_factors.py::test_T25_<name>` (5, v3.1).

**T1.11 `feat(compute): cross-sectional operators with mask and groupby, sorted-index reductions`** · `M1` `compute` · M · Blocked by: T1.7b, T1.Gb · §5.4, §5.3.10, ADR-0019
- Done means: output from a ties example in which `rank(method="ordinal")` gives 1,2,3 in `instrument_id` order (T-11) with `tiebreak="id"` and in T-27 order with the default hash; output showing that `zscore` is bit-identical when the in-memory column order is shuffled.
- Acceptance: `tests/unit/compute/test_crosssection.py::test_zscore_ddof0_zero_var_nan`, `::test_top_stable_ties`, `::test_unknown_group_counted`, `::test_quantiles_preserve_ties`, `::test_reduction_in_instrument_id_order`, `::test_rank_ordinal_uses_tiebreak_key`, `tests/golden/test_time.py::test_T11_ties`, `::test_G_TIME_LATE_target` (G-TIME-LATE: the target B, B, A, from the table's `SMA(3)` values as input; decision 2026-11-10, #356).

**T1.12 `feat(pipeline): window-style user functions`** · `M1` `pipeline` · M · Blocked by: T1.8, T1.11 · §3.3, §5.3.7, §6.5 (5)(6)
- Done means: the chapter 3 example `mom_12_1_custom` (253 rows) runs, and using `close[-273]` gives an E8 suggestion "window=273"; reading a global array gives E24 and "L1 cache disabled for node".
- Acceptance: `tests/unit/pipeline/test_user_functions.py::test_window_is_asof_adjusted`, `::test_out_of_window_index_E8`, `::test_global_array_read_E24_disables_l1`, `::test_source_hash_includes_helpers`, `::test_user_exception_keeps_user_frame`.

**T1.14a `feat(artifacts): sealed run folders with crash recovery and source capture`** · `M1` `artifacts` · M · Blocked by: T0.5a · §5.9.1–5.9.3, §2.6
- Done means: after a run, `ls runs/<id>` has `manifest.json`·`SEALED`·`source/` and the files are read-only; a failed run is aborted in the index with no folder; reopening a run killed between the rename and the seal recovers it or moves it to aborted.
- Acceptance: `tests/unit/artifacts/test_runstore.py::test_seal_only_on_success`, `::test_interrupted_seal_recovers`, `::test_sources_captured_with_helpers`, `::test_value_hash_ignores_created_at`, `::test_no_pickle_files_written`.

**T1.14b `feat(artifacts): run index with candidates, observations, cohorts, pins and environment numerics`** · `M1` `artifacts` · M · Blocked by: T1.14a · §5.9.2, §5.9.5
- Done means: `sqlite3 runs/index.sqlite '.tables'` shows `studies runs candidates observations cohorts exposures preregistrations pins books`; `manifest.json` has `environment.numerics` and `machine_id`.
- Acceptance: `tests/unit/artifacts/test_index.py::test_append_only_triggers`, `::test_tables_match_spec`, `::test_pins_canonical_in_index`, `::test_preregistration_claim_and_look_columns` (the `preregistrations` claim columns and `runs.conditions_hash`, `runs.preregistration_id`, `runs.look_number` of 5.9.5, #269), `tests/unit/artifacts/test_runstore.py::test_environment_numerics_recorded`.

**T1.13 `feat(api): run_pipeline and factor screen`** · `M1` `api` · M · Blocked by: T1.12, T1.14b · §3.5, §3.8 screen
- Done means: `uv run python examples/m1_screen.py` prints the top 10 momentum per market on the reference date and the `run_id`.
- Acceptance: `tests/unit/api/test_run_pipeline.py::test_output_schema_and_sort`, `::test_screen_rows_filtered`, `::test_markets_from_snapshot`, `tests/unit/api/test_screen_factor.py::test_top_per_market`.

**T1.15 `feat(api): rerun in a fresh process with input stamp, replay failure and trust gate`** · `M1` `api` · S · Blocked by: T1.13 · §3.8 rerun, §5.9.3, §2.6
- Done means: `uv run nexusbt rerun <id>` gives "outputs identical (value, physical)"; renaming the snapshot folder gives E15; changing Parquet bytes gives E15 (semantic·physical mismatch); editing a helper module in the working folder still lets rerun give the same values from the captured source; a run folder whose manifest `machine_id` was changed gives E31, and runs with `--trust`.
- Acceptance: `tests/unit/api/test_rerun.py::test_rerun_identical`, `::test_missing_snapshot_E15`, `::test_tampered_parquet_detected`, `::test_archived_helpers_override_local`, `::test_new_snapshot_is_new_run`, `::test_foreign_run_requires_trust_E31`.

**T1.16 `feat(compat): zipline CustomFactor and USEquityPricing shim`** · `M1` `compat` · S · Blocked by: T1.12 · §3.4, design 3.4
- Done means: the zipline `Mom(CustomFactor)` code of design 3.4 runs with only its import changed to `from nexusbt.compat.zipline import ...`.
- Acceptance: `tests/unit/compat/test_zipline_shim.py::test_compute_signature`, `::test_usequitypricing_close_is_close_tr`.

**T1.17 `test(parity): isolated zipline env, bundle writer from TDS, L1-a and L1-b`** · `M1` `parity` · M · Blocked by: T1.10, T1.16, T0.10 · §8.1
- Done means: the `engine / parity` job log shows the per-case `max_rel` of L1-a·L1-b below tolerance (including windows spanning a dividend), and an evidence JSON (summary only, "parity does not imply realism", the number of scaled instruments) is produced.
- Acceptance: `tests/parity_compare/test_L1.py::test_L1a_price_terms_default_inputs`, `::test_L1b_adjustment_windows`, `::test_price_scale_for_uint32_overflow`.

**T1.18 `test(parity): L1-d masks and classifiers, known differences`** · `M1` `parity` · S · Blocked by: T1.17 · §8.1
- Done means: `tests/parity/KNOWN_DIFFERENCES.md` exists and the L1-d cases agree as 8.1's table says (sets and ranks exactly, `zscore` values within L1-a's tolerance; ADR 0046).
- Acceptance: `test_L1.py::test_L1d_top_rank_zscore_percentile_quantiles`, `::test_L1d_known_differences_listed`.

**T1.19 `test(property): chunk, permutation, future-data, determinism and kernel invariants for pipelines`** · `M1` `property` · M · Blocked by: T1.13 · §8.3
- Done means: `uv run pytest -m property -k "CHUNK or PERM or FUT or DET or KERNEL"` passes and prints the case counts.
- Acceptance: `tests/property/test_pipeline_invariants.py::test_P_CHUNK`, `::test_P_PERM`, `::test_P_FUT_pipeline`, `::test_P_DET_pipeline`, `tests/property/test_kernels.py::test_P_KERNEL_reference_is_left_fold`; `test_P_CHUNK` and `test_P_FUT_pipeline` run on the late-bar synthetic variant (#354) as well as `small` (decision 2026-11-10, #356).

**T1.21 `test(property): start-date and metamorphic invariants with preconditions`** · `M1` `property` · M · Blocked by: T1.19 · §8.3, INV-14, INV-15 [SC-04]
- Context: P-START (1·21·252 sessions, including `every(n)`), M-SCALE, M-DUMMY, M-SPLIT-NEUTRAL — each with holding cases (random graphs satisfying the precondition) and counterexamples (price threshold, zscore without a mask) (M-CCY·M-SLEEVE are T4.8).
- Done means: `uv run pytest -m property -k "START or SCALE or DUMMY or SPLIT_NEUTRAL"` passes and prints the case and counterexample counts.
- Acceptance: `tests/property/test_metamorphic.py::test_P_START`, `::test_M_SCALE`, `::test_M_SCALE_counterexample_threshold`, `::test_M_DUMMY`, `::test_M_DUMMY_counterexample_unmasked`, `::test_M_SPLIT_NEUTRAL`; `test_P_START` runs on the late-bar synthetic variant (#354) too (decision 2026-11-10, #356).

**T1.22 `feat(tds): import csv with mapping.yaml and minimal-daily packages`** · `M1` `tds` · M · Blocked by: T0.14c, T0.13c · TDS 7·9.5, §4.3
- Context: `tds import csv MAPPING.yaml --out PKG` (TDS 9.5: column mapping, `template`, date formats, `missing_values`, market declaration, `price_basis`), package writing (sorting·partitions·hashes·`pit_quality = backfilled` by default), the `tds:minimal-daily@1.0` declaration, a conversion report (`import_report.json`: kept·assumed·dropped rows).
- Done means: `tds import csv` on the two CSVs of TDS chapter 7 → `tds check --level full` passes and prints the profile's three results.
- Acceptance: `tds/tests/test_import_csv.py::test_minimal_two_csv`, `::test_mapping_template_and_format`, `::test_offsetless_time_requires_timezone`, `::test_import_report_written`.

**T1.23 `feat(tds): manifest build for an existing folder`** · `M1` `tds` · S · Blocked by: T1.22 · TDS 8.1
- Context: `tds manifest build PKG` (scans the folder into a `tds.json` draft: datasets·files·statistics·hashes; the required fields the files do not give are left out, so `tds check` reports them as M003; publication rules are written `"TODO"`, which `tds check` reports as M014; descriptions are named only in the `TODO` list at the top of the file).
- Done means: in a folder with a few Parquet files, `tds manifest build` writes a draft, and after the `TODO`s are filled in `tds check` passes.
- Acceptance: `tds/tests/test_manifest_build.py::test_draft_lists_files_and_stats`, `::test_todo_fields_flagged`.

**T1.24 `feat(bench): benchmark harness and early stage measurements`** · `M1` `bench` · M · Blocked by: T1.13, T0.8d · §7
- Context: `bench/run.py` (workloads·repetitions·p50/p95/max·summed process-tree RSS·USS·JIT first latency·cache state), `--stages m1` measurements (P1·open·block read·adjustment·`SMA(252)` over all daily rows (ADR-0019 definition A)·cross-section), each stage cold and warm as chapter 7 defines them, `provisional: true` on warm numbers while #144 or #148 is open, result JSON (summary only).
- Done means: `uv run python bench/run.py --stages m1 --reps 3 --snapshot synth-small` prints JSON with per-stage p50/p95 and RSS/USS; `bench/run.py --stages m1 --reps 10 --snapshot synth-full-m1-0001`, run by a person on the compute machine, prints a cold and a warm p95 for each M1 stage and the summed USS of the process tree (figures into the milestone tracking issue); the PR description has one line of grounds for the decision to keep ADR-0019 A or switch to B. The measurement counts as M1 evidence (R2, 10.0) only once T1.19 and T1.21 pass on the late-bar synthetic variant; run before that, it is profiling and is recorded as such (decision 2026-11-10, #356).
- Acceptance: `tests/unit/bench/test_harness.py::test_result_schema`, `::test_no_paths_in_results`, `::test_process_tree_memory_summed`, `::test_output_value_hash_in_results`, `::test_cold_and_warm_p95_per_stage`, `::test_warm_marked_provisional_while_cache_keys_open`.

**T1.Gb `test(golden): v3.1 filter, builtin-factor and tie-break cases (T-24, T-25, T-27)`** · `M1` `golden` · S · Blocked by: T0.9 · §5.4.1, §3.4, §3.7, §8.2
- Context: T-24 (three-valued Filter table), T-25 (for each of the 12 built-in factors of M1, a 5-row hand-calculation case; the three return-series kernels of 2026-11-24 get theirs before they are built with NaN positions placed in it, `tests/golden/factors/<name>.yaml` + a check file), T-27 (fixed-salt hash ties). Merged before the consuming tickets T1.9·T1.10·T1.11·T1.25.
- Done means: `uv run python tests/golden/check/T-25.py` prints the expected values of the 12 as a table, and `check/T-27.py` prints the hash keys and order of three instruments (T00002, T00001, T00003).
- Acceptance: `test_handcalc_self.py::test_cases_v31_M1_expected_present`.

**T1.25 `feat(pipeline): three-valued filters with validity masks`** · `M1` `pipeline` · M · Blocked by: T1.11, T1.Gb · §3.3, §5.4.1, §5.9.9
- Context: a Filter node carries a value and a validity mask; a comparison's missing value = unknown, `~` keeps validity as it is, `&`·`|` Kleene, `if_else` unknown → NaN, unknown = false at the final uses (`universe`, selection, `mask`, `screen`); `explain`'s "unknown (input NaN: …)".
- Done means: the T-24 table is printed as it is, and a `~(Price.close.latest > 10_000)` universe has no halted instruments.
- Acceptance: `tests/golden/test_time.py::test_T24_filter_unknown`, `tests/unit/pipeline/test_filters.py::test_kleene_and_or`, `::test_not_keeps_unknown`, `::test_isnan_always_valid`, `::test_final_use_unknown_is_false`, `::test_all_any_kleene`, `::test_as_factor_unknown_nan`, `::test_classifier_missing_is_unknown`, `::test_pipeline_screen_unknown_false`.

**T1.27 `test(repo): determinism source bans and cross-process hash-seed runs`** · `M1` `repo` · S · Blocked by: T1.19 · §2.5, INV-09
- Context: add wall clock·random numbers·`uuid4`·`os.urandom` in decision-path modules to ruff `banned-api`, an AST test (detecting places where iteration over an unsorted `set`/`frozenset` sets event·output order), P-DET with two fresh processes with different `PYTHONHASHSEED`.
- Done means: the tests fail on a branch that deliberately puts `datetime.now()` into `accounting`, and a line says the output hashes of the two process runs are equal.
- Acceptance: `tests/unit/test_determinism_rules.py::test_no_wallclock_or_rng_in_decision_modules`, `::test_no_unsorted_set_iteration_in_event_paths`, `tests/property/test_pipeline_invariants.py::test_P_DET_cross_process_hashseed`.

**T0.15c `feat(tds): v1.2 checks - exact ratios and delisting distributions`** · `M1` `tds` · S · Blocked by: T0.15b, T0.14c · TDS 5.11·5.13·8.3
- Context: TDS error A010 (v1.4 E: a share-changing event without `ratio_num/ratio_den`·with one side only·≤ 0·disagreeing with the f64 ratio), warning A011 (unknown whether a distribution is included), pass/fail packages per code.
- Done means: `uv run tds check tds/conformance/TDS-A010/fail --format json --level full` (the default level `schema` reads no rows; decision 2026-11-10, #229) reports four lines as errors (E) — the missing row·the one-sided row·the zero row·the disagreeing row — and prints a profile failure.
- Acceptance: `tds/tests/test_conformance.py::test_A010`, `::test_A011`.

**T0.15d `feat(tds): v1.2 checks - volume unit, price grid and advisory file value hashes`** · `M1` `tds` · S · Blocked by: T0.15b, T0.14c · TDS 4.2·5.5·5.27·8.3
- Context: V011 (suspected volume unit), V012 (price deviates from the declared grid·minor-unit integer by more than 1e-9 relative), H004 (`files[].value_sha256` mismatch — an advisory field), `market_rules` schema·key checks (including the `verified` column), pass/fail packages per code.
- Done means: `uv run tds check tds/conformance/TDS-V011/fail --format json --level full` (the default level `schema` reads no rows; decision 2026-11-10, #229) gives one `TDS-V011` line (instrument·year, R = 100), and the pass package (R = 1) gives 0 warnings.
- Acceptance: `tds/tests/test_conformance.py::test_V011`, `::test_V012`, `::test_H004`, `tds/tests/test_schemas.py::test_market_rules_schema_stable_optional`.

**T0.16c `feat(testing): v1.2 synthetic fields and degrades`** · `M1` `testing` · S · Blocked by: T0.7, T0.15c, T0.15d · §4.8
- Context: `ratio_num/ratio_den` and their f64 quotient (including 1:3·1:7·0.29), distributions just before delisting + flag, splits·dividends inside a halt period, raw prices fitted to the pack grid with some jittered by 1 ULP, `market_rules` seeds, `degrade=["no_tick_info", "volume_in_lots"]`.
- Done means: `--preset small --validate` prints "exact ratios: n, distributions before delisting: k, off-grid rows: 0", and `--degrade volume_in_lots` shows the number of V011 warnings.
- Acceptance: `test_synth.py::test_exact_ratios_present`, `::test_prices_on_grid_with_ulp_noise`, `::test_volume_in_lots_triggers_V011`, `::test_synth_conforms_degraded_core[no_tick_info]`.

#### M1b — first backtest end to end (thin slice)

The thin backtest (#858, the owner, 2026-11-28): one market in a run (KR or US), long only, in that market's currency; a schedule (monthly or daily), `top(n)` on a factor the M1 pipeline computes, among the names the strategy's `universe=` holds (3.7; `nx.universe` of that market, 3.6, T2.4a), equal weights; a decision at the close, market orders filled at the next session's open, whole shares, no fill on a halted or missing bar, no volume cap and no price-limit logic; the ledger in integer minor units with the daily balance; the `[account] cash_rate` (the constant `cash_rate_bps`, default 0, when there is no series) read as the Sharpe's `rf_t` only (5.7; G-119 (c)): M1b books no cash interest, the accrual being T4.19's, and a run given a rate other than 0 prints the cash interest as a line not built yet (the owner, 2026-11-28, #901); a held position through cash dividends (entitlement at the ex-date, an amount published later joining it when it is known, cash at the pay date), share-changing events with an exact ratio and a delisting with an observed terminal value; no cost code, and the line that says costs are not included (#841 Decisions, 2026-11-27). Anything outside it stops with E18, as a feature not built does (6.6).

- decided (#858, 2026-11-28): T3.23 (money rounding from the packs) and T3.24 (the price grid) are not in M1b: every entry M1b books (fills, dividends, fractional-share cash, terminal amounts) is half_up to the minor unit in every pack (5.6.1), and the grid serves only order prices and the price-limit comparisons (5.6.4a); a withholding other than 0 or a user `[rounding.<MARKET>]` is E18 until T3.10 and T3.23.

**T3.Gg `test(golden): first-backtest cases (G-12, G-15..G-20, G-22, G-30, G-34, G-45, G-46, G-48, G-53..G-55, G-60, G-61, G-119..G-124, G-127, G-129..G-135, G-137, G-138)`** · `M1b` `golden` · M · Blocked by: T0.9, T0.15a · §5.6.3–5.6.13, §5.7, §8.2
- Context: the cases the M1b tickets use, taken from T3.Ga (G-12, G-15), T3.Gc (G-16~G-20, G-22, G-30, G-34, G-45, G-46, G-48), T3.Gd (G-53~G-55) and T3.Ge (G-60, G-61), which keep the rest, and the thin backtest's metrics, cash, delisting and share-event cases G-119~G-122 (#875), and its under-one-year cases G-123, G-124 (#873) and G-127 (#874), and from #874 the numbers of G-46, the price and dividend-amount cases G-129 and G-130, the foundation cases G-131 to G-135 (one return, unreadable data, lot size, long-only ruin, delisted in the period), G-137 (small values) and G-138 (a pending order rebased at a split). G-60 is written here beside G-61 and is first read in M3a (T3.13a); the `at=close` sell of G-129 (a) is first read by T3.5a, and G-124 (b), whose cash earns interest, by T4.19. Merged before the consuming tickets T3.3, T3.4, T3.5c, T3.5d, T3.9, T3.10a, T3.11a, T3.12, T3.13c, T3.13d and T3.22a.
- Done means: `uv run python tests/golden/check/G-12.py` prints cash (minimum units), fills and `cancelled_qty` per session; `uv run python tests/golden/check/G-60.py` prints PSR 0.759233 and the line "excess-kurtosis value 0.915240 is wrong".
- Acceptance: `tests/golden/test_handcalc_self.py::test_cases_first_backtest_expected_present`.
- Notes:
  - decided (the owner, 2026-11-28, #901): the `at=close` sell of G-129 (a) (`blocked(close_not_positive)`, filled at the next close) is read by the M3a ticket whose cases fill at the close, T3.5a (G-112, G-114); the thin backtest fills at the next open.

**T2.4a `feat(pipeline): the basic universe of one market`** · `M1b` `pipeline` · S · Blocked by: T1.13 · §3.6
- Context: `nx.universe("KR")` of one market: the instruments listed that session (`listed_on <= session <= last_session`), market names from the snapshot. The microcap switch, exclusion reasons and fixed lists stay in T2.4.
- Done means: prints the per-session instrument count of `nx.universe("KR")` on synthetic small beside the listed count of the same session; a market name not in the snapshot is E16.
- Acceptance: `tests/unit/pipeline/test_universe.py::test_listed_that_session`, `::test_unknown_market_E16`.
- Notes:
  - carried (#43 Decisions, 2026-11-19, #249; #752 Decisions, 2026-11-26): `nx.screen(factor, top=n)` picks among the listed cells of 3.3's default domain and says `universe: listed (the default universe comes with T2.4)`, a line two tests hold (`tests/unit/api/test_screen_factor.py`, `tests/docs/test_dev_examples.py`); this ticket makes it pick within 3.6's default universe and changes that line and both tests.

**T2.7a `feat(contracts): the shared terminal value of a delisting`** · `M1b` `contracts` · S · Blocked by: T0.15a · §5.6.13, §2.3
- Context: the one function `terminal_value(q, held_path, delisting_row, policy, as_of) -> (amount, ts_known, basis)` of 5.6.13: the bases (a)~(d), the policy table and the time the amount is known. It lives in `contracts`, which every module may import, so that accounting and the labels of `research` call the same function with 2.5's arrows as they are (the owner, 2026-11-28, #901). The labels and the label times stay in T2.7.
- Done means: an example prints, for one held delisting of synthetic small, the amount, `ts_known` and basis under each policy of the table.
- Acceptance: `tests/unit/contracts/test_terminal_value.py::test_bases_a_to_d`, `::test_policy_table`, `::test_amount_known_time`.

**T3.1a `feat(portfolio): top(n) with equal weights in one stage`** · `M1b` `portfolio` · S · Blocked by: T1.11, T1.9, T1.Gb · §3.7 portfolio, §5.5
- Context: `nx.top(n)` on one factor with equal weights, one construction stage. Sizing slots, `hold`, group caps and the risk slot stay in T3.1.
- Done means: an example prints the TargetFrame of one decision (selection rank, weight) with sum ≤ 1.
- Acceptance: `tests/unit/portfolio/test_targets.py::test_top_n_equal_weights`, `tests/golden/test_time.py::test_T27_hash_tiebreak` (new values), `::test_n_tied_at_cutoff_counted`, `tests/unit/portfolio/test_targets.py::test_tiebreak_stable_across_decisions`, `::test_factor_top_matches_portfolio_top`, `::test_unrelated_output_does_not_reshuffle`, `tests/unit/portfolio/test_targets.py::test_fewer_finite_scores_than_n_weigh_one_over_k` (5 names, 2 NaN, `top(4)` → 3 at 1/3; 10 names, 4 finite → 0.25 each, #875).

**T3.2a `feat(api): Strategy object and schedules`** · `M1b` `api` · S · Blocked by: T3.1a, T1.13 · §3.7, §3.8
- Context: the `Strategy` object with its params and its schedules (monthly, daily). The strategy `screen` with `--asof` stays in T3.2.
- Done means: a one-factor strategy prints its decision dates over one year, monthly and daily.
- Acceptance: `tests/unit/api/test_strategy.py::test_param_name_inference`, `::test_strategy_hash_includes_risk`, `::test_decision_context_anchor_field`, `tests/unit/api/test_schedules.py::test_monthly_picks_sessions_only` (`monthly(day=-1)` in July 2021 → Friday 2021-07-30; `day=1` on a holiday → the next session), `::test_monthly_needs_a_session_after_the_period` (3.7: a month-end pick needs a calendar session after the month, else that month has no decision; #875).

**T3.3 `feat(accounting): columnar account state, integer money, valuation and NAV bridge`** · `M1b` `accounting` · M · Blocked by: T0.3, T3.Gg · §5.6.1, §5.6.9, INV-06
- Done means: the G-01 state written as an Arrow IPC checkpoint → restored → the same valuation; prints that the bridge row closes in G-48 (valuation gain without trades).
- Acceptance: `tests/unit/accounting/test_state.py::test_columnar_state_checkpoint_arrow`, `::test_money_is_integer_minor_units`, `::test_minor_unit_rounding_half_up`, `::test_decision_value_excludes_unknown_entitlements`, `::test_decision_value_uses_only_known_values`, `tests/golden/test_accounting.py::test_G48_appreciation_without_trades`, `tests/unit/test_import_rules.py::test_state_seam_signatures_arrow_only` (`nx.accounting._state` seam, `ruined` and `shortfall` fields).

**T3.4 `feat(execution): order table, lifecycle, trigger state, quantity conservation, sizing and session loop skeleton`** · `M1b` `execution` · M · Blocked by: T3.3, T3.Gg · §5.6.2, §5.6.3, §5.6.7, appendix C [SC-11]
- Context: the order table (5.6.1), lifecycle state, trigger state and the four quantities (INV-18), quantity events, `SimConfig`, quantity frozen at the decision, the `step_session` skeleton (the 7 phases in order, market orders only, zero cost) — so that the following tickets can use multi-session cases (G-12 and G-30 in M1b; G-10 and G-14 in M3a) right away.
- Done means: `nx.describe(nx.execution)` printing the state transition table and the `SimConfig` knob table (in the same order as appendix C); G-15 passes; quantities are conserved after random quantity events.
- Acceptance: `tests/unit/execution/test_orders.py::test_allowed_transitions_only`, `::test_quantity_conservation`, `::test_partial_cancel_is_qty_event_not_status`, `::test_frozen_shares_from_decision_value`, `::test_decision_price_recorded`, `tests/unit/execution/test_simconfig.py::test_knobs_match_appendix_C`, `tests/unit/execution/test_loop.py::test_phase_order_skeleton`, `tests/golden/test_execution.py::test_G15`, `tests/unit/test_import_rules.py::test_step_seam_signatures_arrow_only` (`nx.execution._step` seam), `tests/golden/test_time.py::test_G_TIME_LATE_order_intents` (G-TIME-LATE: the order intents of the 8.4 table, from its targets and with the holding each row presupposes set in the account state; decision 2026-11-10, #356), and from #875 (5.6.7 `T_i` and `Δ_i`): `tests/unit/execution/test_sizing.py::test_order_is_target_minus_holding` (100 held, target 120 → one buy of 20), `::test_target_shares_from_a_weight` (weight 1.0, V 10,000.00, price 50.00 → 200; V 300.00, three 1/3 targets at 100.00 → 1 each), `::test_whole_shares_and_leftover_cash` (cash 1,000,000 won, three equal targets: at 700,000 won each 0 shares; at 70,000 won 4 shares each and 160,000 won left as cash), `tests/unit/execution/test_orders.py::test_ten_buys_then_one_sell_leave_integer_zero`.
- Notes:
  - decided (the owner, 2026-11-28, #901): M1b books no cash interest. The session-start accrual that this entry's Done means held until then (#313, decision 2026-11-10) is T4.19's, with its event and the `financing` bridge; the skeleton's accrual step is there and adds nothing.
  - decided (#874, 2026-11-28, by #900; it answers #705 Decisions 12 of 2026-11-21 and #752 Decisions of 2026-11-26): a null `lot_size` (TDS 5.1: null when not known) takes the lot of the market's rules pack, and is E13 before the run when the pack has none; a `lot_size` of 0 is E13 (8.2, G-133). T3.13c holds the test `test_G133_lot_from_pack_or_E13`.

**T3.5c `feat(execution): market fills at the open, none on a halted or missing bar`** · `M1b` `execution` · S · Blocked by: T3.4, T3.Gg · §5.6.3–5.6.5
- Context: a market order filled at the next session's open; a bar whose `bars.obs_status` is not `traded` does not fill (5.6.5). Limit locks, the null-open variants, expiry and carry-over stay in T3.5a.
- Done means: the per-session table equals case G-01.
- Acceptance: `tests/golden/test_execution.py::test_G01`, `tests/unit/execution/test_tradability.py::test_halted_or_missing_bar_does_not_fill`, `tests/unit/execution/test_fills.py::test_open_fill_ignores_the_same_sessions_close` (INV-01: open 101.00, close 90.00 or 150.00 → fill 101.00; #875), `tests/golden/test_execution.py::test_G129_open_not_positive_blocks_the_fill` (G-129 (b): an `open` of −1.00 → `blocked(no_open)`, the run not stopped; #874).

**T3.5d `feat(execution): whole-share allocation from available cash`** · `M1b` `execution` · S · Blocked by: T3.5c, T3.Gg · §5.6.7
- Context: each order's quantity in whole shares from the cash available at the fill, with the reduction and partial cancel of a cash shortfall, at zero cost. The volume cap and impact stay in T3.5b.
- Done means: the table equals case G-12; cash never becomes negative; the `insufficient_cash` count and amount in the orders line.
- Acceptance: `tests/golden/test_execution.py::test_G12`, `tests/unit/execution/test_costs.py::test_trim_order_highest_fill_ratio_first`, `tests/unit/execution/test_sizing.py::test_floor_shares_no_lost_share` (G-53 (d)), `tests/golden/test_execution.py::test_G120_sell_funds_buy`, `::test_G120_gap_up_shortfall`, `tests/unit/execution/test_allocation.py::test_need_in_integer_minor_units_terminates` (#875).

**T3.9 `feat(accounting): splits, reverse splits, stock dividends, bonus issues and capital reductions via the resolver`** · `M1b` `accounting` · M · Blocked by: T3.4, T0.15a, T3.Gg · §5.6.10, §5.3.3a, §4.6 kind table
- Done means: G-16~G-18, G-34, G-45, G-46 pass.
- Acceptance: `tests/golden/test_accounting.py::test_G16`, `::test_G17`, `::test_G18`, `::test_G34`, `::test_G45_split_ratio_revised`, `::test_G46_split_and_dividend_same_day`, `::test_G138_pending_order_rebase_rounding` (#874), `::test_G53_exact_share_arithmetic`, `tests/unit/accounting/test_ratios.py::test_ratio_rule_examples`, `::test_ratio_product_overflow_checked`, `::test_invalid_exact_ratio_rejected_E13`, `tests/golden/test_accounting.py::test_G122_reverse_splits_and_a_pending_order` (#875).

**T3.10a `feat(accounting): cash dividends with the entitlement at the ex-date, an amount published later and cash at the pay date`** · `M1b` `accounting` · M · Blocked by: T3.9, T3.Gg · §5.6.11, §5.3.3a(4)
- Context: the entitlement made at the ex-date for the holding at the previous close, and the cash booked on the pay date, an amount of zero included (G-130 (a)). An amount not known at the ex-date is held as an entitlement of unknown amount, its quantity fixed even when the holding is sold before the terms are published, and becomes a receivable at the start of the first session after they are (5.3.3a (4), 5.6.11; moved here from T3.10 on 2026-11-28, the owner, #901, since half of the synthetic KR dividends publish the amount after the ex-date, 4.8 (4)). Corrections and cancellations, events learned late, the pay-date declaration and the data warnings stay in T3.10.
- Done means: G-19 and G-20 pass.
- Acceptance: `tests/golden/test_accounting.py::test_G19`, `tests/unit/accounting/test_dividends.py::test_entitlement_from_previous_close_holding`, `tests/golden/test_accounting.py::test_G120_dividend_rounded_once`, `::test_G120_receivable_to_cash_leaves_nav`, `::test_G120_pay_date_on_a_weekend` (#875), `::test_G130_amount_of_zero_is_a_zero_receivable` (G-130 (a): no E13), `::test_G130_amount_missing_with_terms_time_E13` (G-130 (c); #874), and for the amount published later (#901; the first two moved from T3.10): `::test_G20`, `::test_G20_entitlement_survives_exit_before_terms`, `::test_G130_amount_given_later` (G-130 (b): an entitlement of unknown amount, left out of `decision_value`, then a receivable of 50.00; #874).

**T3.11a `feat(accounting): delisting with an observed terminal value`** · `M1b` `accounting` · S · Blocked by: T3.10a, T2.7a, T3.Gg · §5.6.13
- Context: a held instrument's delisting whose row has `ret_observed`: its orders cancelled at the terminal session, the holding removed, the amount from T2.7a's `terminal_value`, booked when it is known. Policy values, mergers, rights and unsupported actions stay in T3.11.
- Done means: the observed rows of G-22 pass.
- Acceptance: `tests/golden/test_accounting.py::test_G22_observed`, `tests/golden/test_accounting.py::test_G121a_removal_at_the_terminal_session`, `tests/unit/accounting/test_delisting_thin.py::test_unobserved_delisting_held_E18`, `::test_cash_merger_held_E18` (the M1b E18 of a kind T3.11 builds, 5.6.12, 5.6.13; #875).

**T3.22a `feat(accounting): stale marks of a held name with no bar, and a distribution before delisting counted once`** · `M1b` `accounting` · M · Blocked by: T3.11a, T2.7a, T3.Gg · §5.6.3(6), §5.6.9, §5.6.13
- Context: stale mark = last valid close × Π price factors (`stale_adjusted`), the same value used by `decision_value`, `P_i` and `ref*`; the distribution just before delisting booked once, with `ret_observed_includes_distributions` true or false. A null flag, `unknown_inclusion` and the label check stay in T3.22.
- Done means: the G-54 table and G-55's distribution counted once print as they are, shown side by side with the values the v3 formula would have given (2,000 / 1,100 / 302.30).
- Acceptance: `tests/golden/test_accounting.py::test_G54_stale_mark_after_action`, `::test_G55_distribution_counted_once`, `::test_G129_price_not_positive_keeps_the_last_mark` (G-129 (a): day 3 values the holding at 1,000.00, not 0; #874), `tests/unit/accounting/test_marks.py::test_exclusive_observed_has_no_distribution_factor`, `::test_stale_adjusted_status`, `::test_decision_value_uses_adjusted_mark`, `tests/property/test_execution_invariants.py::test_P_BRIDGE_events_on_no_trade_days`.

**T3.12 `feat(execution): single-sleeve simulation loop and session step`** · `M1b` `execution` · M · Blocked by: T3.5d, T3.11a, T3.22a, T3.Gg · §5.6.3, §5.6.14
- Done means: G-30 passes, `simulate` and repeated `step_session` give the same result, and cutting a checkpoint at any phase boundary and resuming gives the same.
- Acceptance: `tests/golden/test_execution.py::test_G30`, `tests/unit/execution/test_loop.py::test_simulate_equals_stepwise`, `::test_resume_at_phase_boundary`, `tests/golden/test_accounting.py::test_G121b_terminal_cash_funds_the_next_open`, `::test_G121c_missing_bars_then_delisting`, `tests/unit/execution/test_loop.py::test_held_name_turning_nan_is_sold` (3.7: only finite scores are selected; 5.6.7: `T_i = 0` sells the holding; #875).

**T3.13c `feat(api): single-market backtest and its six metrics`** · `M1b` `api` · M · Blocked by: T3.12, T3.2a, T2.4a, T3.Gg · §5.7, §3.8
- Context: `nx.backtest` and `nexusbt backtest` for M1b's thin backtest: the run, what it refuses, its manifest, and the six metrics of 5.7 (return, CAGR, volatility, Sharpe with its standard error under independent returns, maximum drawdown, turnover). The run selects among the names the strategy's `universe=` holds (3.7), `nx.universe` of the market (T2.4a). Split on 2026-11-28 (the owner, #901): the first screen is T3.13d. PSR, DSR, MinTRL, the delisting scenarios and the cost lines stay in T3.13a.
- Done means: `nx.backtest` of a strategy file on synthetic small returns a Run whose `metrics` hold the six values; Sharpe computes on the excess returns `r_t − rf_t` of 5.7; a request outside the thin backtest (a second market, a cost setting, a limit order) is E18.
- Acceptance: `tests/unit/api/test_backtest.py::test_outside_thin_backtest_E18`, `tests/unit/research/test_metrics.py::test_cagr_sharpe_mdd_turnover_known_values`, `::test_cagr_from_twr_index_equals_nav_ratio_without_flows`, `::test_turnover_long_only_unchanged`, `tests/golden/test_metrics.py::test_mdd_includes_inception_nav` (G-61 (a)), and from #875: `tests/golden/test_metrics.py::test_G119_thin_metrics`, and from #873: `::test_G123_under_one_year_not_annualised`, `::test_G124_under_one_year_label` (G-124 (a); named `…_and_zero_variance_bound` until #901, when (b), which books cash interest, went to T4.19), and from #874: `::test_G127_turnover_under_one_year`, `tests/unit/config/test_precedence.py::test_closer_place_wins`, `::test_manifest_holds_resolved_value_and_place`, `::test_none_means_not_given`, `::test_same_key_twice_at_one_height_E16` (four of 3.11's five rules; the fifth is T3.13d's), `tests/unit/research/test_metrics.py::test_volatility_is_not_the_factor` (5.7: `std(r, ddof=1)·√252`), `::test_mdd_zero_without_drawdown`, `::test_long_only_total_loss_is_ruin` (5.6.7: a long-only sleeve that reaches 0 is ruin too, CAGR and Sharpe "n/a (ruin)", G-134, #874), `tests/golden/test_metrics.py::test_G131_one_return_or_one_date`, `tests/golden/test_accounting.py::test_G133_lot_from_pack_or_E13`, `tests/unit/api/test_backtest.py::test_G132_unreadable_data_aborts_unsealed`, `::test_minimal_daily_package_E18_before_any_fill` (4.3), `::test_missing_pay_date_declaration_E18_at_start` (5.6.11), `::test_close_column_float32_refused_E14` (4.4 step 4), `::test_tzless_time_column_refused_E14` (4.4 step 4, TDS-S004), `::test_manifest_lists_rows_not_checked_at_the_default_level` (4.3, 4.4 step 5), `::test_manifest_records_immediate_settlement` (5.6.7), and from #901: `tests/unit/research/test_metrics.py::test_sharpe_standard_error_under_independent_returns` (5.7; 3.9's headline rule 4), `tests/unit/api/test_backtest.py::test_no_cash_interest_is_booked_whatever_the_rate` (the owner, 2026-11-28: M1b books no cash interest, and `[account] cash_rate` is read as `rf_t` only; G-119 (c)).
- Notes:
  - carried (#43 Decisions, 2026-11-21, #667 via pull request #691): `AverageDollarVolume` is NaN in a market F-18 records for `volume` because `run_pipeline` reads the market's F-18 records from `snapshot.fallbacks`; F-18 is taken under the `price` feature only, so a snapshot opened with `required=CapabilityRequest(features={"backtest"})` holds no F-18 record and the value there is 0.0 again. This ticket's run opens the snapshot for `backtest` and makes the F-18 records reach the terms it computes.
  - carried (#43 Decisions, 2026-11-19, #445, #450 and #451): `open_snapshot(cfg, sha256=True)`, the open with the verification stamp that `rerun`, `reconcile`, `live` and `fill` need (4.4 step 1), has no caller; the backtest's entry points still raise `NotImplementedError`, and this ticket starts their runs through `api._begin_run`.
  - carried (#725 Decisions 169, 2026-11-23): no code yet gives 4.3's E18 for a `minimal-daily` package on `backtest`.

**T3.13d `feat(api): the first screen of the thin backtest`** · `M1b` `api` · M · Blocked by: T3.13c, T3.Gg · §3.9 Run, §5.7
- Context: the first screen of 3.9 for M1b's thin backtest, split from T3.13c on 2026-11-28 (the owner, #901): the headline (#870) with `Run.details()` and `nexusbt backtest … --full` printing the details after it; return, CAGR, volatility, Sharpe, maximum drawdown and turnover; the line that says costs are not included; the simulated-result line (#764, decision 2026-11-25); and each line whose source is not built printed as 3.9 says, naming the ticket it waits for and counted in `lines not built`. PSR, DSR, MinTRL, the delisting scenarios and the cost lines stay in T3.13a.
- Done means: `uv run nexusbt backtest <strategy file>` on synthetic small prints that first screen with `family: n/a (not built yet; available after ticket T2.9)`.
- Acceptance: `tests/unit/api/test_backtest.py::test_first_screen_thin`, `::test_costs_not_included_line`, `::test_not_built_line_names_its_ticket`, `tests/unit/config/test_precedence.py::test_override_named_in_details_and_headline` (3.11), `tests/golden/test_metrics.py::test_G135_delisted_in_period_always_shown`, `::test_G137_small_values` (#874), `tests/unit/api/test_backtest.py::test_checks_line_names_rows_not_checked`, `::test_assumptions_pre_withholding_and_pre_tax` (5.6.11, 5.6.11a), `::test_orders_line_counts_halt_and_cash_trim` (3.9 `orders`), and from #888: `::test_data_line_names_dropped_bars_only_when_not_zero` (3.9 `data`, 4.4 step 5, #877), `::test_assumptions_count_the_inferred_calendar_rows` (3.9 `assumptions`, 4.4 step 5, #884), and from #901 (3.9's headline, #870): `::test_headline_opens_the_first_screen_in_its_order` (the name line with the run's years and decisions, the simulated-result line, then `return`, `trust`, `costs`, `assumed`, `data`, `details`), `::test_headline_repeats_the_numbers_of_the_details` (rule 1: CAGR, maximum drawdown, Sharpe and turnover), `::test_headline_costs_place_in_the_thin_backtest` (rule 3: `n/a (not built yet; available after ticket T3.8) · no costs and no statutory charges included`), `::test_headline_places_not_built_take_the_not_built_form` (rules 2 and 3: `PSR(0)`, the family count, `luck` and the break-even cost are printed in that form, never left out; a place whose ticket is not cut names the issue, as rule 3 says), `::test_lines_not_built_counts_the_headline_and_the_details` (rule 1), `::test_headline_assumed_names_the_order_settlement_and_dividends` (rule 5), `::test_details_and_full_print_the_details_after_the_headline` (`Run.details()`, `--full`), `::test_G129_first_screen_counts_prices_not_positive` (G-129: `data.no_price`, one E30, `prices not positive 1`, `rows dropped 0`; rule 10, #874), and from the owner's answers of 2026-11-28 (#901 Decisions): `::test_headline_trust_prints_the_sharpe_with_its_standard_error` (rule 4: `Sharpe {s} ± {se} (IID-based)`, computed in M1b), `::test_headline_benchmark_and_excess_not_built` (`return`: the benchmark as `n/a (not built yet; available after ticket T4.6)` and the excess after T4.12), `::test_fill_cap_place_reads_no_fill_cap` (the headline's `assumed` and the details' `assumptions`: `no fill cap`, 3.9 rule 5), `::test_evaluation_label_is_research_data` (always `research data` in M1b), `::test_cash_interest_not_built_when_a_rate_is_given` (a run given a `cash_rate_bps` other than 0, or a series: the cash item of `assumptions` reads `n/a (not built yet; available after ticket T4.19)`; at 0 it reads as 3.9 gives it).
- Notes:
  - decided (the owner, 2026-11-28, #901): in M1b the headline computes `± se`, prints the benchmark and the excess in the not-built form, reads `no fill cap` where the fill cap goes, and gives the evaluation label `research data`; a run given a cash rate other than 0 prints the cash interest in the not-built form.

**T3.14a `feat(artifacts): the saved run's orders, account events and daily table with the bridge`** · `M1b` `artifacts` · S · Blocked by: T3.13c · §5.9.1, INV-06
- Context: `runs/<id>/orders.parquet`, `account_events.parquet` and `daily.parquet` with its bridge rows. Cost attribution, `report.html` and the scenario tables stay in T3.14.
- Done means: opening `runs/<id>/orders.parquet` and `account_events.parquet` with polars gives the canonical columns of 5.9.1; the sum of the bridge rows of `daily.parquet` = the NAV change.
- Acceptance: `tests/unit/artifacts/test_backtest_outputs.py::test_orders_schema`, `::test_account_events_schema_v1`, `::test_pnl_bridge_closes`, `::test_daily_has_financing_and_flow_bridge_columns`.

**T3.16a `test(property): NAV, bridge and quantity invariants`** · `M1b` `property` · S · Blocked by: T3.13c, T3.14a · §8.3
- Done means: `uv run pytest -m property -k "NAV or BRIDGE or QTY or ADJ_ORDER"` passes.
- Acceptance: `tests/property/test_execution_invariants.py::test_P_NAV`, `::test_P_BRIDGE`, `::test_P_QTY`, `::test_P_QTY_integer_ratios`, `tests/property/test_adjust.py::test_P_ADJ_ORDER` (adjusted prices keep their order, #874).
- Notes:
  - carried (#43 Decisions, 2026-11-20, #254; moved here from T3.16 by #901, since M1b makes targets and orders first): in M1 P-FUT compares `run_pipeline`'s table and `term_diagnostics` at rows with `decision_ts ≤ τ`; the ticket that makes targets and orders widens P-FUT to compare them, as 8.3's row says (also T3.13c; T3.16 and T3.13a widen them again for what M3a adds).
  - carried (#43 Decisions, 2026-11-21, #255; moved here from T3.16 by #901): in M1 P-START and M-SCALE compare `run_pipeline`'s table and `term_diagnostics`; the ticket that makes targets widens both to the canonical targets and target weights 8.3 names (also T3.13c; T3.16 and T3.13a widen them again for what M3a adds).

**T3.15a `feat(execution): zipline parity preset (market orders, costs, sizing)`** · `M1b` `execution` · S · Blocked by: T3.12, T3.13d · §5.6.15 [SC-12]
- Done means: the first screen of a `preset="zipline"` run has "parity preset (not a realistic model)" (5.6.15's report header; `report.html` comes with T3.14).
- Acceptance: `tests/unit/execution/test_preset_zipline.py::test_knobs_table`, `::test_forbidden_in_toml`, and from #874 (3.11): `::test_preset_takes_the_height_of_its_place`, `::test_explicit_value_beside_realistic_wins_and_is_reported`, `::test_value_zipline_fixes_given_beside_it_E16`.
- Notes:
  - carried (#858, 2026-11-28): the preset's commission and its same-bar volume cap (5.6.15) act once T3.8 and T3.5b are in; L2-a and L2-c run it at zero cost, and T3.17a (L2-b) is the first to use them.

**T3.17c `test(parity): L2-a and L2-c backtests against the zipline preset`** · `M1b` `parity` · M · Blocked by: T3.15a, T1.17 · §8.1 [SC-12]
- Context: the L2 levels both engines run with no costs; L2-b, with costs and the volume cap, stays in T3.17a.
- Done means: the L2-a and L2-c evidence JSON is committed.
- Acceptance: `tests/parity_compare/test_L2.py::test_L2a_zero_cost`, `::test_L2c_corporate_actions`.
- Notes:
  - owner decides (#901, 2026-11-28): whether L2-c compares a holding through a cash dividend whose amount is published after the ex-date. 8.1's L2-c row says "a cash dividend (pay date)" and no more; for L1, 8.1 and ADR 0045 leave out a cell whose event is not final at the row, since the other engine has no knowledge time. Half of the KR dividends of synthetic `small` are of this kind (4.8 (4)).

**T3.36 `test(api): rerun of a backtest run`** · `M1b` `api` · S · Blocked by: T3.14a, T1.15 · §3.8 rerun, §5.9.3
- Context: `nexusbt rerun <id>` of a saved backtest run in a fresh process; no ticket held this test before #858.
- Done means: `uv run nexusbt rerun <id>` of a backtest run prints "outputs identical".
- Acceptance: `tests/unit/api/test_rerun.py::test_backtest_run_reruns_identical`.

**T5.18a `feat(cli): init --demo and the demo snapshot`** · `M1b` `cli` · S · Blocked by: T1.2, T0.16c · §3.10, §8.5
- Context: `nexusbt init --demo`, with the synthetic `demo` snapshot shipped in the wheel. The strategy templates and the 30-minute path stay in T5.18.
- Done means: in an empty folder `uv run nexusbt init --demo` writes `nexusbt.toml` and the demo snapshot, and `uv run nexusbt doctor` opens it.
- Acceptance: `tests/unit/cli/test_init.py::test_demo_writes_snapshot_that_opens`.

**T3.37 `docs(examples): the momentum factor and the mom_kr strategy`** · `M1b` `docs` · S · Blocked by: T3.13d, T5.18a · §8.5
- Context: `examples/factors/momentum.py` and `examples/strategies/mom_kr.py`, which ranks on that factor (imported, not a copy); no ticket held them before #858. M2 evaluates the factor and M3a reads the strategy's full report.
- Done means: `uv run nexusbt backtest examples/strategies/mom_kr.py` on the demo snapshot prints the first screen.
- Acceptance: `tests/docs/test_examples.py::test_mom_kr_backtest_runs`.

**T1.20 `docs(examples): first five minutes around a first backtest`** · `M1b` `docs` · S · Blocked by: T1.15, T1.22, T3.36, T3.37, T5.18a · §8.5
- Done means: pasting the commands of the README "first 5 minutes" section as they are does: `init --demo` → doctor → a backtest of `examples/strategies/mom_kr.py` → its first screen → rerun; building a synthetic snapshot or importing a CSV, `tds check` and screening follow as next steps.
- Acceptance: `tests/docs/test_examples.py::test_readme_first_five_minutes` (named `test_readme_m1` until #901).
- Notes:
  - carried (#858, 2026-11-28): #260 holds this ticket's earlier text (an M1 walkthrough ending in screening); its body follows this entry when the ticket is next worked.

#### M2 — PIT + factor evaluation

**T0.8a `superseded`** · `M2` · Blocked by: none · removed 2026-11-24 (#752) with `fundamentals_events`, `fundamentals_state`, `classifications`, `universe_membership` and `dictionary/items` [#725 Decisions 250].

**T0.8b `feat(testing): synthetic TDS package part 3b - fx and indices`** · `M2` `testing` · M · Blocked by: T0.7 · §4.8 (12)~(13) *(splits T0.8; panels removed 2026-11-24, #752)*
- Context: `fx_rates` (publication lag, per market currency pair), index instruments, `dictionary/columns`.
- Done means: `--preset small --validate` prints pass for the three results of the core profile.
- Acceptance: `test_synth.py::test_synth_conforms[tiny]`, `::test_synth_conforms[small]`, `::test_fx_publication_lag`.

**T0.16b `feat(testing): degraded synthetic packages for research fallbacks`** · `M2` `testing` · S · Blocked by: T0.8b, T0.16a · §4.5, §4.8
- Context: the remaining values of `degrade=`: `no_benchmarks` and `no_dated_category` (F-14); the values of the removed kinds left 2026-11-24 (#752).
- Done means: `--preset small --degrade no_benchmarks --validate` prints the declared profiles and the three results.
- Acceptance: `test_synth.py::test_synth_conforms_degraded_research[<each value>]` (2 of them).

**T2.G `test(golden): PIT, label and lookup cases for M2 (T-08, T-16, T-18, T-21, T-22)`** · `M2` `golden` · M · Blocked by: T0.9 · §8.2 *(the M2 share of v2 T0.11 and T0.17; T-01~T-06, T-13, T-14, T-17 and T-19 removed 2026-11-24, #752)*
- Context: late dividend `close_tr`, label times, rectangle lookup examples 1~3, economic label 10%, late-recovery purging. Merged before the consuming tickets (T2.1~T2.7).
- Done means: `uv run python tests/golden/check/T-21.py` prints the economic label 10% and the adjusted-price ratio 11.1% side by side, and the T-21 cases (a)~(f) of 8.2 with their 1-share accounting values (2026-11-04).
- Acceptance: `test_handcalc_self.py::test_time_cases_M2_expected_present`.
- Notes:
  - carried (#43 Decisions, 2026-11-19, #583): when this ticket writes T-08, it also checks #583's behaviour through that case: `Price.close_tr` read through the public `nx.run_pipeline`, with the hand-checked values and 5.3.4's late amount.
**T2.1 `feat(data): rectangle two-time-axis lookup of symbol periods`** · `M2` `data` · M · Blocked by: T1.4, T0.14b, T2.G · §5.3.6, §5.1.5 *(rectangle lookup (`nexusbt_tds.pit.rect_lookup`), strict excludes backfilled rows row by row; the interval lookups of the removed kinds left 2026-11-24, #752)*
- Done means: an example prints the `instrument_symbols` rows of one instrument and the lookup result per session side by side; a row announced in advance with a future effect does not hide the current row.
- Acceptance: `tests/unit/data/test_intervals.py::test_half_open_lookup`, `::test_two_axis_known_after_effective`, `::test_T18_future_effective_does_not_hide_current`, `::test_strict_skips_backfilled_rows`, `::test_no_daily_expansion_memory`, `::test_history_mode_system_E18`.

**T2.2 `superseded`** · `M2` · Blocked by: none · removed 2026-11-24 (#752) with `Fund` and `fundamentals_state` [#725 Decisions 251].

**T2.3 `feat(pipeline): Meta attributes and the hindsight warning`** · `M2` `pipeline` · S · Blocked by: T0.8b · §3.2, §4.5 F-14 *(F-14; `Panel`, the `Meta` classifiers of `classifications` and `index_members` removed 2026-11-24, #752)*
- Done means: an example showing `Meta.market`, `Meta.currency` and `Meta.category` per instrument; using the current `category` of `instruments` is E30 (F-14).
- Acceptance: `tests/unit/pipeline/test_meta.py::test_hindsight_attribute_warned`.
- Notes:
  - carried (#43 Decisions, 2026-11-18, #245 and #542): the reference executor holds a Classifier as its integer codes only: `eq` or `element_of` with a name or a bool is refused with `NotImplementedError` ("Classifier names come with its code table") and `startswith` is not computed; this ticket, which reads `Meta.category`'s code table, computes both and removes the two refusals.

**T2.15 `feat(data): share-count items and market capitalisation`** · `M2` `data` · S · Blocked by: T2.1, T0.15a · §5.3.5a [TDS-D9, TDS-Q4] *(share factor `Q`; `share_counts`, `shares_out` and `market_cap` removed 2026-11-24, #752)*
- Done means: an example printing a share-count item (5.3.5) before and after a split, scaled by the split ratio, and the market capitalisation it gives; without such an item, `weight="value"` is E18.
- Acceptance: `tests/unit/data/test_items.py::test_share_count_item_scaled_by_splits_after_its_date`, `::test_market_cap_without_share_count_item_E18`.

**T2.4 `feat(pipeline): universes with microcap switch and exclusion reasons`** · `M2` `pipeline` · M · Blocked by: T2.4a, T2.15, T0.16b · §3.6 [SC-23] *(market names from the snapshot; eligibility and its fallback removed 2026-11-24, #752)*
- Done means: prints that the per-session instrument count of `nx.universe("KR", exclude_microcap=True)` is about 80% of the instrument count of `nx.universe("KR")` in the same session; the `coverage` table has exclusion counts per reason; a fixed list → E4.
- Acceptance: `tests/unit/pipeline/test_universe.py::test_microcap_bottom_20pct`, `::test_survivorship_warning`, `::test_exclusion_reason_counts`.

**T2.5 `feat(pipeline): units, currency conversion and cross-market terms`** · `M2` `pipeline` · M · Blocked by: T2.1, T1.11, T0.8b · §3.3, §5.3.2 (6), §5.1.5 fx, §3.11 `[fx] series`
- Done means: `Price.value_traded.latest.rank(across_markets=True)` → E5; after `.to("USD")` it works and prints a value reflecting the FX publication lag; with two series, `[fx] series = "auto"` shows the list with E16.
- Acceptance: `tests/unit/pipeline/test_units.py::test_E5_cross_market_currency`, `::test_to_uses_available_fx`, `::test_E17_cross_market_into_window`, `::test_fx_series_auto_selection`.
- Notes:
  - carried (#43 Decisions, 2026-11-16, #482 and #486): this ticket and T2.19 both list 5.3.2 (6), and the planner of #482 plans one market axis only; what it has to do for cross-market terms is in #486's Findings.
  - carried (#43 Decisions, 2026-11-20, #250): `nx.rerun`'s new process sends a 6.6 error back without its `kind`, so a warning-kind E20 `FxStaleError` comes back as a fail once a saved run converts currency through `.to`; writing `kind` with the other fields is the fix (also T3.13a).

**T2.6 `feat(pipeline): label taint`** · `M2` `pipeline` · S · Blocked by: T1.6 · §6.5 *(external datasets, `from_parquet` and the user label path removed 2026-11-24, #752)*
- Done means: using a label node (5.3.11) as a signal is E2.
- Acceptance: `tests/unit/test_leaks.py::test_label_taint_E2`.

**T2.9 `feat(research): segments, exposures and trial registry with candidates, observations and cohorts`** · `M2` `research` · M · Blocked by: T1.14b · §6.1, §6.2, §6.3 reserved [SC-19, SC-21]
- Done means: computing the validation segment for the first time gives the E10 notice, `nx.runs(study=...)` shows the exposure, candidate and observation counts; rerunning the same candidate with another snapshot adds one more observation and leaves the earlier observation as it is; giving a `splits=` value is E18.
- Acceptance: `tests/unit/research/test_segments.py::test_no_blocking`, `::test_exposure_logged`, `::test_splits_reserved_E18`, `tests/unit/research/test_trials.py::test_candidate_key_excludes_snapshot`, `::test_rerun_adds_observation_not_overwrite`, `::test_cohort_frozen_with_digest`, `::test_study_id_stable_on_rerun`, `tests/unit/research/test_segments.py::test_look_number_counts_family_exposures`, `::test_rerun_adds_no_look`, `::test_corrected_snapshot_continues_look_count` (6.2 looks, #269).
- Notes:
  - carried (#43 Decisions, 2026-11-19, #249): `nx.screen` (`kind="screen"`) and `nx.run_pipeline(save=True)` (`kind="pipeline"`) seal a run record and write no `exposures` row; this ticket writes those rows for both kinds (3.8 "exposure record only", 6.1), adding neither a candidate nor an observation.
  - carried (#43 Decisions, 2026-11-16, #466 and #485): `nexusbt init` writes `[research] family_id` into `nexusbt.toml` and no row in the run index; this ticket writes the `families` row of the first id (5.9.5's reason `init`) and `runs.family_id`, and says what an id the index does not know means.
  - owner decides at the cut (#43 Decisions, 2026-11-11, #386 and #305): what a `[research] family_id` that differs from the migrated index's family means (opening with another id is silent today, 5.9.5), and whether a run's `warnings` belong in the manifest's logical hash (today they do).

**T2.7 `feat(research): economic and adjusted forward labels, three label times and purging`** · `M2` `research` · M · Blocked by: T2.7a, T1.13, T2.9, T0.15a, T2.G · §5.8, §5.6.13 [SC-20]
- Done means: an example printing the label computation of one instrument for one month (entry and exit prices, dividend reinvestment factor, share factor, terminal value, the three label times); on synthetic small, the IC difference of the two labels reported in one line.
- Acceptance: `tests/unit/research/test_labels.py::test_econ_reinvest_at_ex_close`, `::test_adj_ratio_label`, `::test_delisting_terminal_policies`, `::test_terminal_uses_shared_resolver`, `::test_purge_uses_label_available`, `::test_no_entry_counted`, `tests/golden/test_time.py::test_T16_label_times`, `::test_T21_economic_label_10pct`, `::test_T22_purge_uses_label_available`, and (2026-11-04) `tests/unit/research/test_labels.py::test_econ_exit_on_ex_date_keeps_right_as_cash` (T-21 (b), (d)), `::test_econ_ignores_unread_bars` (T-21 (c): the close of e changed, `R` unchanged), `::test_label_available_covers_every_read_value` (T-21 (a), (e)), `tests/golden/test_time.py::test_T21_cases` (the T-21 table of 8.2).

**T2.8 `feat(research): IC, Newey-West, quantiles, turnover and coverage`** · `M2` `research` · M · Blocked by: T2.7 · §5.8
- Done means: on a hand-made IC series, NW t and L print equal to the test's expected values; the rank autocorrelation of 5.8 is computed per market over the instruments of two neighbouring decisions (#764, decision 2026-11-25).
- Acceptance: `tests/unit/research/test_factor_stats.py::test_spearman_min_pairs`, `::test_newey_west_known_value`, `::test_quantile_ties`, `::test_turnover`, `::test_coverage_counts`, `tests/docs/test_tool_cards.py::test_card[ic-newey-west]`, `::test_every_tool_has_a_card_row` (D19, #219).
- Notes:
  - owner decides at the cut (#43 Decisions, outside review of 2026-11-03): whether M2's evaluation also gives realised turnover and a group-neutral IC.

**T2.16 `feat(research): naive breadth, implied IR and cohort BHY-adjusted p`** · `M2` `research` · S · Blocked by: T2.8, T2.9 · §5.8 [SC-08, SC-09]
- Done means: on 5 hand-made candidates (NW t given), prints the BHY-adjusted p, equal to the expected values; a candidate with a different horizon does not enter the same cohort; prints naive breadth and expected IR.
- Acceptance: `tests/unit/research/test_hygiene_stats.py::test_bhy_known_values`, `::test_bhy_cohort_excludes_other_horizon`, `::test_breadth_naive_definition`, `::test_implied_ir`, `::test_bhy_limit_sentence_present`, `tests/docs/test_tool_cards.py::test_card[bhy]` (D19, #219).

**T2.10a `feat(api): evaluate and FactorReport`** · `M2` `api` · M · Blocked by: T2.8, T2.9, T2.4, T2.16 · §3.8, §3.9
- Done means: `uv run nexusbt evaluate examples/factors/momentum.py` prints a FactorReport in the shape of 3.9 (with the label definition, naive breadth and BHY(cohort) lines, and the simulated-result line of 3.9, #764, decision 2026-11-25) and the `report.html` path.
- Acceptance: `tests/unit/api/test_evaluate.py::test_report_lines_match_template`, `::test_counts_next_to_rates`, `::test_saved_run_folder`, `::test_hygiene_block`, `::test_mapping_terms_are_separate_candidates`, `::test_minimal_daily_adj_label_only`.
- Notes:
  - decided (#314 Decision, 2026-11-10; #43 Decisions): before this ticket is cut, it is shown whether the factor-selection history that follows a strategy importing an evaluated factor can be recovered from the recorded node hashes and the `exposures` and `selection_events` tables; if it cannot, this ticket adds the link, since a missing selection history cannot be rebuilt later.

**T2.10b `feat(artifacts): report.html template with structural test`** · `M2` `artifacts` · S · Blocked by: T2.10a · §3.9
- Context: a one-page jinja2 template (no external files) shared by FactorReport and Run (3.9 page frame), the FactorReport sections of 3.9 in their order, the n/a line for a left-out section, the rendering means chosen by measurement and recorded in an ADR (3.9 visual rules).
- Done means: the generated FactorReport HTML has the 3.9 FactorReport sections in the 3.9 order and meets the 3.9 visual rules a test can check (no external resource, a unit on every axis, losses with a sign or a pattern, within the size budget); the person's look at it is the M2 row of 10.0, against the 3.9 list, not an eye check without one.
- Acceptance: `tests/unit/artifacts/test_report_html.py::test_required_sections_present`, `::test_sections_in_3_9_order`, `::test_no_external_resources`, `::test_axes_have_units`, `::test_losses_not_by_colour_alone`, `::test_size_budget`.
- Notes:
  - decided (#43 Decisions, 2026-11-19, #249): the report's question 7 says that its totals per term are of the cells computed, since a longer window over the same term adds earlier rows and their counts (also T3.14).

**T2.11 `feat(api): explain values of price and item terms`** · `M2` `api` · S · Blocked by: none · §3.9 Explanation *(narrowed 2026-11-24, #752: the `fundamentals_events` lineage and F-11 removed [#725 Decisions 251])*
- Done means: `nx.explain(Price.close.latest, "KR:T00003", "2020-02-28")` prints the bar the value came from, and `nx.explain` of an `nx.Item` term prints the value-table row it read (its date and value) and its age (5.3.5).
- Acceptance: `tests/unit/api/test_explain.py::test_not_usable_yet_message`.
- Notes:
  - builder's choice (#43 Decisions, 2026-11-19, #249; recommended: read saved files by their recorded form, because files already written keep the old `term`): when this ticket fixes how `explain` writes a node, the `term` column of `term_diagnostics.parquet` changes to that form.
  - decided (#43 Decisions, 2026-11-19, #587): `explain` says why a cell is absent.

**T2.12 `feat(api): static checks before heavy compute`** · `M2` `api` · M · Blocked by: T2.6, T2.5 · §6.5 static checks, P8
- Done means: `nx.check(strategy)` prints the result table of the 10 checks within 1 second (time shown); a narrow universe over an unmasked `zscore` is E34.
- Acceptance: `tests/unit/api/test_check.py::test_static_checks_list`, `::test_runs_before_compute`, `::test_capability_check_E18`, `::test_unmasked_cross_section_notice_E34`, `tests/perf/test_P8.py::test_static_under_1s` (`perf_smoke`).

**T2.18 `feat(api): preregister`** · `M2` `api` · M · Blocked by: T2.9 · §6.4, §6.2 *(#269: the claim fields, the conditions hash and the look labels)*
- Done means: after `nx.preregister(f, metric="ic_mean", threshold=0.02, segment="validation")`, the evaluation report of that segment has "preregistered ic_mean ≥ 0.02: pass/fail · registered before first validation exposure: yes/no"; `preregistrations` holds the claim fields of 6.4, and the label computed from index rows (the `backtest` report that prints it is T3.13a's) is "independent final test (look 1)" for one matching look, "repeated look on preregistered data (look 2)" for the next one with the end date extended, unchanged after `rerun`, and never "independent final test" with a changed cost setting.
- Acceptance: `tests/unit/research/test_preregister.py::test_record_and_report_line`, `::test_registered_after_exposure_flagged`, `::test_claim_fields_and_defaults_recorded`, `::test_conditions_hash_covers_claim_parameters`, `::test_snapshot_not_in_conditions_hash`, `::test_look_one_independent_final_test`, `::test_later_look_repeated_with_fixed_sample_line`, `::test_changed_conditions_not_independent`, `tests/property/test_research_record.py::test_P_LOOK` (8.3), `tests/docs/test_tool_cards.py::test_card[holdout]` (D19, #219).
- Notes:
  - owner decides at the cut (#43 Decisions, 2026-11-19, #274 and #269): what three things mean before this ticket builds them: `judge_at`, which no rule uses to judge a claim; `benchmark=` of `nx.preregister`, which has no run-side counterpart in `nx.backtest` (3.8); `select=`, which is not among 6.4's conditions-hash parameters.

**T2.13 `superseded`** · `M2` · Blocked by: none · removed 2026-11-24 (#752) with `Fund` and L1-c.

**T2.17 `docs: English quickstart from CSV to rerun`** · `M2` `docs` · S · Blocked by: T1.22, T2.10a, T1.15 · §8.5
- Context: `docs/quickstart.md` (English): two hand-written CSVs → `tds import csv` → `tds check` → `nx.evaluate(Returns(252).shift(21), target="fwd_return_adj")` → the saved run → `nexusbt rerun`; the E18 sentence given when `backtest` is called on a minimal package, and how to fix it (raw prices + events).
- Done means: pasting the document's commands as they are into a clean folder runs to the end.
- Acceptance: `tests/docs/test_examples.py::test_quickstart_csv_to_rerun_en`.
- Notes:
  - decided (#705 Decisions 23, 2026-11-22): the quick start says at most that the engine is designed to take other engines' strengths and solve their weaknesses, until that has been run and shown ("Work with no ticket yet", Stage (2)).
  - decided (#43 Decisions, 2026-11-19, #587): the quick start shows one cell that is absent and why.
  - decided (#725 Decisions 118, 2026-11-23): the user docs say with numbers that `Returns(W)` spans W closes with W−1 steps, so a "20-session return" is `Returns(21)`.
  - owner decides at the cut (#725 Decisions 118, 2026-11-23): whether the name or the default of `Returns` changes.
  - carried (#43 Decisions, 2026-11-20, #250): the guide on run folders says that `manifest.json`'s `source.outside` and `source/` hold the person's module and file names as written, since `manifest.json` is a file a person may hand to someone else (5.9.3).

**T2.14 `docs(examples): m2 factor research walkthrough and stage measurement`** · `M2` `docs` · S · Blocked by: T2.10a, T2.11, T2.12, T1.24 · §7, §8.5
- Done means: the commands of the README section "Evaluate one factor" run as they are, and `bench/run.py --stages m2 --snapshot synth-full-m1-0001`, run by a person on the compute machine, prints P3 and P8, cold and warm (figures into the milestone tracking issue).
- Acceptance: `tests/docs/test_examples.py::test_readme_m2`, `tests/docs/test_scenarios.py::test_scenario[2]` (8.5 use scenarios, D19, #219).
- Notes:
  - decided (#43 Decisions, 2026-11-19, #587): the walkthrough writes a 52-week-high ratio with `@nx.factor(..., adjustment="degree 0")` beside the same momentum with `Returns`, and warns against ranking across instruments inside a window function.
  - carried (#43 Decisions, 2026-11-20, #675): the user documentation of `@nx.factor` warns that a user function reading the sign of a tied zero can give another value on x86.

**T2.Gb `test(golden): v3.1 ranking and market-series cases (T-26, T-28)`** · `M2` `golden` · S · Blocked by: T0.9 · §5.4.2, §3.2 [V31-13]
- Context: T-26 percentile composite, T-28 row selection of a market-level series. Merged before the consuming tickets T2.19 and T2.20.
- Done means: `uv run python tests/golden/check/T-26.py` prints the percentile composite table.
- Acceptance: `test_handcalc_self.py::test_cases_v31_M2_expected_present`.

**T2.19 `feat(pipeline): market-level series terms`** · `M2` `pipeline` · M · Blocked by: T2.3, T1.8, T2.Gb · §3.2, §5.1.5, §5.3.2 (6) [V31-13]
- Also (added 2026-11-25, #725 Decisions 246): the three return-series kernels of 3.4 (`SimpleBeta`, `RollingPearsonOfReturns`, `RollingLinearRegressionOfReturns`) with their T-25 cases written first, and 3.4's rule that a degree-0 kernel gives 0 over a `Market.series` term, in the graph build's degree walk.
- Context: `Market.series(id, column)` market-level terms (on the market axis of that instrument, `ready` as it is), column-wise broadcast when mixed with instrument terms, a series of another market gathered at the decision and E17 when it is a window input, built-in factors and user functions `inputs=`, a missing id E18, `explain` display.
- Done means: the example `examples/dev/regime_filter.py` prints, per decision, true/false of the Filter "KOSPI TR above its 200-day line", and that the sleeve is cash at the decisions where it is false.
- Acceptance: `tests/golden/test_time.py::test_T28_market_series_rows`, `tests/unit/pipeline/test_market_series.py::test_broadcast_to_instruments`, `::test_not_in_cross_section_denominator`, `::test_cross_market_series_window_E17`, `::test_missing_instrument_E18`.
- Notes:
  - carried (#43 Decisions, 2026-11-16, #482 and #486): this ticket and T2.5 both list 5.3.2 (6); the planner of #482 plans one market axis only, and what it has to do for cross-market terms is in #486's Findings.

**T2.20 `feat(pipeline): percentile rank with explicit missing policy and weighted composites`** · `M2` `pipeline` · M · Blocked by: T1.11, T2.Gb · §3.3, §5.4.2
- Context: `pct_rank(higher_is_better, na=drop|bottom|middle)`, `nx.ops.composite` (nested), the `na` policy recorded in the manifest, `coverage.n_na_filled`, `explain` percentile and whether filled, per node.
- Done means: the T-26 table prints as it is and `explain` shows "C: na=middle → 50 (filled)".
- Acceptance: `tests/golden/test_time.py::test_T26_pct_rank_and_composite`, `tests/unit/compute/test_pct_rank.py::test_ties_average`, `::test_na_policies`, `::test_composite_nested`, `::test_na_filled_counted`.

**T2.21 `feat(pipeline): Trad dataset and universe exclusion toggles`** · `M2` `pipeline` · M · Blocked by: T2.4 · §3.2, §3.6, §4.3, §5.1.5
- Context: `Trad.admin_status/halted/limit_up_close/limit_down_close/price_limit_ratio` (publication time per column group), `universe(exclude=[…])` and `[universe] exclude`, validation of allowed names (E16), `coverage.n_excluded_by_reason`, `explain` leaves.
- Done means: the per-decision exclusion counts of `nx.universe("KR", exclude=["administrative", "spac"])` print by reason, and `exclude=["foo"]` gives the list of allowed names and E16.
- Acceptance: `tests/unit/pipeline/test_trad.py::test_column_availability_by_group`, `::test_missing_dataset_E18`, `tests/unit/pipeline/test_universe.py::test_exclude_admin_and_category`, `::test_exclude_unknown_name_E16`, `::test_default_excludes_nothing`.
- Notes:
  - carried (#43 Decisions, 2026-11-18, #245): `test_T24_filter_unknown` runs T-24's `Trad.halted` rows through the kernels only; this ticket, which makes the executor read trading state, runs them through the executor.

**T2.22 `feat(pipeline): explicit Filter.fillna, unknown counts per leaf and the unknown-universe notice (E39)`** · `M2` `pipeline` · S · Blocked by: T2.4, T1.25 · §3.3, §5.4.1, §6.6 E39, §5.9.1
- Context: `Filter.fillna(bool)` (explicit replacement, recorded in the manifest and `explain`), universe unknown share > 50% during a run → E39 (number of decisions, leaf names, input columns), `coverage.n_unknown_by_leaf` (json).
- Done means: on synthetic small, using `nx.universe("US") & ~Trad.halted` at US decisions before 2019-08-23 gives one E39 line and a fix sentence (`.fillna(True)`), and changing it to `(~Trad.halted).fillna(True)` brings the universe size back.
- Acceptance: `tests/unit/pipeline/test_filters.py::test_fillna_bool_explicit`, `tests/unit/pipeline/test_universe.py::test_unknown_universe_notice_E39`, `::test_unknown_by_leaf_counted`.

**T2.Ge `superseded`** · `M2` · Blocked by: none · removed 2026-11-24 (#752) with G-96~G-98.

**T2.23 `superseded`** · `M2` · Blocked by: none · removed 2026-11-24 (#752) with `Macro`, `Events`, `from_parquet` and E47 [#725 Decisions 251].

**T2.24 `perf(bench): P11 fixture and factor-graph generator with the reduced P11 (a) on the m1 columns`** · `M2` `bench` · S · Blocked by: T1.24, T2.10a · §7 P11 [#175]
- Context: the synthetic 300-factor graph generator and `bench/fixtures/p11.json` (chapter 7 "P11 fixed fixture", moved here from T6.26; each base column recorded with the dataset it comes from), and the reduced P11 (a) of the chapter 7 early-measurement table: the same seed, window length distribution, rank and composite ratios and node sharing rate, with the base columns limited to those the M1 datasets carry (price, volume, calendar-derived), and `nx.evaluate` of the 300 factors at monthly decisions on decision rows only (5.3.2). The result JSON records the base columns used and the P11 reporting columns (bytes of columns read, decision rows computed, node count, shared node count).
- Done means: `uv run python bench/run.py --workload P11 --part a --columns m1 --fixture bench/fixtures/p11.json --reps 3 --snapshot synth-small` prints JSON with the time, USS, `fixture_sha256`, the output value hash and the base columns used; `bench/run.py --workload P11 --part a --columns m1 --fixture bench/fixtures/p11.json --snapshot synth-full-m1-0001`, run by a person on the compute machine, prints the cold and warm time and per-stage time against the P11 (a) stage budget, with the summed USS of the process tree (figures into the milestone tracking issue, as "reduced, M1 columns").
- Acceptance: `tests/unit/bench/test_p11_fixture.py::test_generator_same_seed_same_graph`, `::test_base_columns_carry_their_dataset`, `::test_m1_columns_keep_the_ratios`, `tests/perf/test_p11_smoke.py::test_fixture_hash_recorded`, `::test_m1_columns_variant_reports_columns_used`.

#### M3a — single-market market orders, the backtest completed

**T0.8c `feat(testing): full and full_ci synthetic presets`** · `M3a` `testing` · S · Blocked by: T0.8b, T0.8d · §4.8
- Done means: `--preset full_ci --validate` prints time and size in CI and passes; `--preset full` records time and size in the compute-machine manual checklist (the milestone tracking issue).
- Acceptance: `test_synth.py::test_full_ci_conforms`, `::test_full_ci_is_fraction_of_full_rules`.

**T3.Ga `test(golden): market execution and cash cases (G-10, G-11, G-13, G-14, G-31, G-41, G-112..G-114)`** · `M3a` `golden` · M · Blocked by: T0.9 · §5.6.3–5.6.7, §8.2
- Context: volume cap carried over 3 sessions, unknown ADV for a new listing, Korean upper and lower limit blocks, halt carry-over and 20-session expiry, null open, minimum commission + affordable quantity with impact; the cash shortfall (G-12) and the replacement by a new decision (G-15) are T3.Gg's. Merged before the consuming tickets T3.5a and T3.5b.
- Done means: `uv run python tests/golden/check/G-14.py` prints the order's state per session through the halt and its expiry after 20 sessions.
- Acceptance: `test_handcalc_self.py::test_cases_market_execution_expected_present`.

**T3.Gc `test(golden): accounting cases (G-21, G-23..G-26, G-35, G-42..G-44, G-47, G-49, G-111, G-115)`** · `M3a` `golden` · M · Blocked by: T0.9, T0.15a · §5.3.3a, §5.6.9–5.6.14, §8.2
- Context: pay-date declaration, delisting after a long halt, merger, unsupported, lapse of rights, return of capital, late recovery (G-42), amendments and cancellations (G-43, G-44), entitlement quantity unchanged (G-47), bridge with a fee (G-49); the split, dividend (the undisclosed amount of G-20 with them, #901), delisting, end-of-run and bridge cases of M1b are T3.Gg's. Merged before the consuming tickets T3.10 and T3.11.
- Done means: `uv run python tests/golden/check/G-42.py` prints the `decision_value` of months 10 and 11 (recovery excluded) and the conversion to a receivable in month 12.
- Acceptance: `test_handcalc_self.py::test_cases_accounting_expected_present`.

**T3.1 `feat(portfolio): pure target construction with stages and risk slot`** · `M3a` `portfolio` · M · Blocked by: T3.1a, T2.15 · §3.7 portfolio, §5.5 [SC-01, SC-02 wording]
- Done means: an example prints the TargetFrame of one decision (selection rank, weights of the two stages, capped reason) with sum ≤ 1; `nx.top(10, hold=20)` → before T7.1, E18 "available after ticket T7.1".
- Acceptance: `tests/unit/portfolio/test_targets.py::test_equal_cap_residual_cash`, `::test_value_weights`, `::test_inverse_vol_excludes_nan`, `::test_redistribute_converges`, `::test_per_group`, `::test_risk_none_identity_stage_columns`, `::test_hold_reserved_E18`, `::test_prior_state_returned_empty_in_v1`.

**T3.2 `feat(api): Strategy, schedules, params and strategy screen`** · `M3a` `api` · M · Blocked by: T3.2a, T3.1 · §3.7, §3.8 screen
- Done means: `uv run nexusbt screen examples/strategies/mom_kr.py --asof 2019-06-28` prints the 3.9 Screen shape, "(preview)" when it is not a decision date.
- Acceptance: `tests/unit/api/test_strategy.py::test_screen_scheduled_flag`.

**T3.8 `feat(execution): cost models, general impact form and cost table coverage`** · `M3a` `execution` · M · Blocked by: T3.4 · §5.6.8, §4.7 [SC-11]
- Done means: choosing `nx.costs.realistic()` with unverified tables gives E23 listing the empty (market, period, component); provisional is E22; at a2=0.5, a3=1 the same value as the square-root formula; impact on the session's cumulative quantity, so an order split into several fills pays the same impact as one order before minor-unit rounding (5.6.8; #311, decision 2026-11-10); cost components booked as minimum-unit integers; the default profile stays `provisional`, a fixed bp per market, with the ½ spread and the impact in `realistic` only and no half-tick floor (5.6.8; #764, decision 2026-11-25).
- Acceptance: `tests/unit/execution/test_costs.py::test_provisional_bps_from_pack`, `::test_per_share_min`, `::test_abdi_ranaldo_known_value`, `::test_general_impact_equals_sqrt_default`, `::test_spread_floor_without_high_low`, `::test_coverage_E23`, `::test_components_rounded_to_minor_units`.

**T3.5a `feat(execution): market fills at open with tradability rules`** · `M3a` `execution` · M · Blocked by: T3.5c, T3.Ga · §5.6.3–5.6.5
- Done means: per-session tables equal to cases G-11, G-13, G-14, G-31, G-112, G-114 (#310).
- Acceptance: `test_execution.py::test_G11`, `::test_G13`, `::test_G14`, `::test_G31`, `tests/unit/execution/test_tradability.py::test_price_limits_only_with_pack`, and from #901: `tests/golden/test_execution.py::test_G129_close_not_positive_blocks_the_close_sell` (G-129 (a): a market `at=close` sell on a day whose `close` is 0.00 is `blocked(close_not_positive)` and fills at the next close; #874).

**T3.5b `feat(execution): volume cap and affordable cash allocation with the actual cost function`** · `M3a` `execution` · M · Blocked by: T3.5d, T3.5a, T3.8, T3.Gd · §5.6.6, §5.6.7
- Done means: tables equal to cases G-10, G-41, G-113 (#310); cash never becomes negative; the allocation evaluates impact with the session's `Q_before` (5.6.7, 5.6.8; #311, decision 2026-11-10).
- Acceptance: `test_execution.py::test_G10`, `tests/unit/execution/test_costs.py::test_G41_affordable_lots_never_negative_cash`, `::test_cost_reserve_default_zero_recorded`, `test_execution.py::test_G56_bar_volume_cap`, `tests/unit/execution/test_capacity.py::test_bar_volume_bound_counted` (ψ-bound ratio).
- Notes:
  - builder's choice (#43 Decisions, 2026-11-13, #436; recommended: accumulating, because it keeps "splitting an order does not lower the total"): whether `Q_before` for two candidates of the same instrument and side in one allocation step is taken at the step's start or accumulating; a sleeve holds one target per instrument, so it may not arise.

**T3.9b `feat(accounting): exclude instruments with share events lacking exact ratios (default policy)`** · `M3a` `accounting` · M · Blocked by: T3.9, T1.1a, T3.Gd, T3.13b, T2.10b · §5.6.1, §3.11, §6.6 E13·E30
- Context: default `decimal_ratio = "exclude_instrument"` — removed from the universe from the visible time v(e) (not removed before it), holdings target 0, if unfilled before `ts_effective` closed at the last valid close (`ca_unverified_exit`), windows crossing the event NaN, no re-entry, header line, E30, skips, manifest; `require_exact` is E13, `literal` kept. The reporting of 5.6.1 (8) [#150]: `exit_reason = ca_unverified_exit`, `ca_exclusions.parquet` (a row for a name not held too), the `hypothetical exits` line, the section 7 per-year table, and the `ca_exit_lo`/`ca_exit_hi` pair (`ca_exit_lo` replayed only when n > 0, `ca_exit_hi` the base run's value; otherwise the line `ca sensitivity: n/a (0 hypothetical exits)`; a short holding counted as `bound open`).
- Done means: an example printing the numbers of G-107, its `ca_exclusions.parquet` rows and its first-screen `hypothetical exits` line in both cases; with the same snapshot, the screen and backtest universes are the same.
- Acceptance: `tests/golden/test_ca.py::test_G107`, `tests/unit/accounting/test_ca_exclude.py::test_not_before_visible`, `::test_exit_before_effective`, `::test_unverified_exit_close`, `::test_window_nan_across_event`, `::test_require_exact_E13`, `::test_exclusion_row_for_name_not_held`, `::test_hypothetical_exit_pnl_line`, `::test_ca_exit_lo_hi_bracket_long`, `::test_ca_exit_short_bound_open`, `::test_no_ca_exit_replay_without_exit`, `tests/property/test_screen_backtest.py::test_same_universe_with_exclusions`.
- Notes:
  - carried (#43 Decisions, 2026-11-19, #445, #450 and #451): applying `Snapshot.ca_exclusions` in a run is this ticket's.

**T3.10 `feat(accounting): cash dividends with corrections, events learned late, pay-date declaration and data warnings`** · `M3a` `accounting` · M · Blocked by: T3.10a, T3.Gc · §5.6.11, §5.3.3a(7)(10), §4.5 F-05·F-09 *(pay-date estimation replaced by the user's declaration 2026-11-24, #752; the amount published after the ex-date moved to T3.10a 2026-11-28, #901)*
- Done means: G-21, G-35, G-43, G-44, G-111 (#310) pass, the E28 count in the run warnings; with `degrade=["kr_ex_is_record"]`, the E30 count; with `degrade=["us_div_split_adjusted_no_dates"]`, the "amounts unverified" assumption line.
- Acceptance: `test_accounting.py::test_G21`, `::test_G35`, `::test_G43_dividend_revised_after_payment`, `::test_G44_dividend_cancelled`, `tests/unit/accounting/test_actions_late.py::test_late_discovered_event_uses_effective_holding`, `tests/unit/accounting/test_dividend_data_warnings.py::test_F05_counted`, `::test_F09_assumption`.

**T3.11 `feat(accounting): delisting with knowledge-time proceeds, mergers, rights and unsupported actions`** · `M3a` `accounting` · M · Blocked by: T3.11a, T3.10 · §5.6.12, §5.6.13, §4.5 F-13
- Done means: G-22~G-26, G-42, G-47, G-115 (#310) pass (G-25 with the E12 message); with `degrade=["no_delistings"]`, an exit while holding is E13 (fix sentence, no producer name).
- Acceptance: `test_accounting.py::test_G22` … `::test_G26`, `::test_G42_recovery_known_later`, `::test_G47_rights_lapse_quantity_unchanged`, `tests/unit/accounting/test_delisting_fallback.py::test_F13_unobserved_synthesized`, `::test_mixed_merger_cash_and_shares`, `::test_merger_exact_ratio`.
- Notes:
  - owner decides at the cut (#43 Decisions, outside review of 2026-11-03): whether a Shumway delisting-return policy is added (5.6.13).
  - carried (#752 Decisions, 2026-11-27): #747 holds two engine-side gaps of an exit whose consideration is not known (5.6.13), answered when this ticket is built.

**T3.13a `feat(api): single-market backtest and metrics`** · `M3a` `api` · M · Blocked by: T3.13c, T3.13d, T3.5b, T3.22, T3.2, T2.9, T2.18, T3.Ge · §5.7, §3.8, §3.9 Run
- Done means: `uv run nexusbt backtest examples/strategies/mom_kr.py` prints the 3.9 Run shape (net/gross, assumption lines, costs direct/path, delisting lo/hi, PSR); the Calmar row of 5.7 matches G-110 (#310); PSR, DSR and MinTRL compute on the excess returns `r_t − rf_t` of 5.7 and the `assumptions` line shows the series or the constant form of 3.9 (#313, decision 2026-11-10).
- Acceptance: `tests/unit/api/test_backtest.py::test_run_summary_template`, `::test_assumption_lines_present`, `::test_observation_recorded`, `::test_evaluation_label_and_fixed_sample_line` (the 3.9 `evaluation` line and "fixed-sample statistic; n looks" on the PSR and DSR line at look 2, #269), `tests/unit/research/test_metrics.py::test_cost_drag_direct_vs_path`, `tests/golden/test_metrics.py::test_G60_metrics_and_month_compounding`, `::test_G125_sortino_no_downside` (#873), `::test_G128_per_year_values_under_one_year` (#874), `::test_G136_shared_issuer_line` (#874), `tests/unit/config/test_precedence.py::test_backtest_costs_over_strategy_costs` (3.11's strategy rung, #874), `tests/unit/api/test_backtest.py::test_assumption_ex_post_volume_cap`, `tests/docs/test_tool_cards.py::test_card[linear]`, `tests/unit/report/test_next_line.py::test_entries_from_run_facts_not_values` (D19, #218, #219).
- Notes:
  - owner decides at the cut (#314 Findings, 2026-11-06; #314 Decision, 2026-11-10): whether benchmark α and β come as two lines in 5.7's "Relative to benchmark" row. The builder's recommendation is to add them, because they need no new input; today the plan's "Later (P3)" paragraph under v1.x lists α and β among the benchmark regression metrics left for later.
  - owner decides at the cut (#43 Decisions, 2026-11-19, #437): four points #437's Outcome left open (A1, A4 to A6): the `day_count` and `date_t` of `rf_t` in a multi-currency run, the fallback when two markets share a currency, several currencies on one `assumptions` line, and a test name for G-77 (b) (also T3.4 and T3.Ge).

**T3.13b `feat(api): named scenarios with a single zero-cost replay`** · `M3a` `api` · S · Blocked by: T3.13a · §3.8, §5.7 [SC-06 argument shape]
- Done means: `--scenarios gross,cost0x,cost2x` replays only twice (gross, cost2x) and in the result table cost0x appears as the same series as gross; `capacity` is E18 before T6.14.
- Acceptance: `tests/unit/api/test_backtest.py::test_gross_replayed_once`, `::test_cost_sensitivity_rows`, `::test_scenarios_named_list`, `::test_capacity_not_yet_E18`, `tests/docs/test_tool_cards.py::test_card[scenarios]` (D19, #219).
- Notes:
  - decided (#725 Decisions 165, 2026-11-23; #725 Decisions 245): the backtest finds each held instrument whose end is not known, with its last valid close and `ref*`, takes it into the `delist_lo` and `delist_hi` range as 5.6.13 says, and adds one golden case for it.

**T3.14 `feat(artifacts): backtest outputs, event schemas, derived tables, NAV bridge and cost attribution`** · `M3a` `artifacts` · M · Blocked by: T3.14a, T3.13a · §5.9.1, INV-06, INV-16 [SC-07 costs, SC-23]
- Done means: the sum of the cost rows of `attribution.parquet` = the sum of the order cost columns (gross − net shown as \"direct + path\"); `report.html` has the cost breakdown, scenario and order status tables, and the Run sections of 3.9 in the 3.9 order (a section whose table a later ticket adds shows its n/a line) within the 3.9 size budget.
- Acceptance: `tests/unit/artifacts/test_report_html.py::test_run_sections_in_3_9_order`, `::test_run_size_budget`, `tests/unit/artifacts/test_backtest_outputs.py::test_costs_equal_order_costs`, `::test_G49_fee_reduces_quantity`, `::test_coverage_columns`, `tests/property/test_execution_invariants.py::test_P_DERIVED`, `tests/repo/test_shareable_outputs.py::test_shareable_files_hold_no_local_values`.
- Shareable outputs (5.9.3, #163): `test_shareable_files_hold_no_local_values` runs a backtest on the synthetic `small` snapshot made with `degrade=["kr_ex_is_record"]` (4.8), so that F-05 fires, with these planted values: `HOME` set to a temporary folder whose name holds `nxplant-home`; the project, its `runs/` and the temporary git repository holding them in `<HOME>/nxplant-project`; `[data] root` = `<HOME>/nxplant-data-root`; the git user name `nxplant-git-user`; the account number `NXPLANT-ACCT-90417` in a comment of `nexusbt.toml` and in the `note` of a fill row recorded in a `manual:nxplant` book under the same `runs/` (a backtest reads no book today, so this part guards a later change); and, in place of the `producer` block the generator writes (4.8), one with name `nxplant-producer`, version `nxplant-build` and a `fallback:F-05` hint sentence holding `nxplant-hint`. It first checks that the run's warnings carry `fallback:F-05`. It then reads every shareable file of 5.9.3 as text — JSON and HTML as written, each Parquet file decoded (every string value and the key-value metadata), since its pages are compressed — and finds none of: the `HOME` path in its written and resolved forms, `nxplant-project`, `nxplant-data-root`, `nxplant-git-user`, `NXPLANT-ACCT-90417`, `nxplant-producer`, `nxplant-build`, `nxplant-hint`, and the host name (`socket.gethostname()`) and login (`getpass.getuser()`) when each has 4 or more characters (a shorter one is reported as not checked). It also finds `nxplant-data-root` in `source/nexusbt.toml`, so a planted value is shown to reach the run.
- Notes:
  - carried (#43 Decisions, 2026-11-19, #249): 4.6's `AdjustmentUnavailable` count, one per (instrument, event) pair, kept per instrument and year in the coverage table with the event ids in the report, is this ticket's; `execute()` drops the pairs `adjusted_window` returns, so this ticket also has the executor hand them to its caller.
  - owner decides at the cut (#43 Decisions, 2026-11-19, #401 and #420): which golden ticket writes G-117 and G-118, which 8.2 gives to "the M3 golden ticket that precedes T3.14" and none of T3.Ga, T3.Gc, T3.Gd, T3.Ge and T3.Gr lists, and the tests of `survivorship.parquet` and `coverage_fields.parquet`.
  - owner decides at the cut (#43 Decisions, 2026-11-20, #250): the rule for raising a run manifest's `schema_version` before the first change that alters a key's meaning (#250 kept `"nexusbt-run/2"` when adding the optional `source{entry, outside}`).

**T3.16 `test(property): accounting and state-machine invariants`** · `M3a` `property` · M · Blocked by: T3.16a, T3.13a · §8.3
- Done means: `uv run pytest -m property -k "RESUME or STATE or PARITY13"` passes.
- Acceptance: `tests/property/test_execution_invariants.py::test_P_RESUME`, `::test_P_STATE`, `::test_P_PARITY13_single_market`, `tests/property/test_fillcausal.py::test_P_FILLCAUSAL_open_independent_of_later_hlc`, `::test_bar_volume_cap_monotone_for_isolated_order` (two properties).
- Notes:
  - carried (#43 Decisions, 2026-11-04, #207): 8.3 has no property row checking that the account layer runs again inside a scenario (for example a brake that triggers only under `cost2x`), as 5.7 says it does; the cut adds the row and names the ticket that tests it (also T3.13b).

**T3.17a `test(parity): L2-b backtests with costs against the zipline preset`** · `M3a` `parity` · S · Blocked by: T3.17c, T3.8, T3.5b · §8.1 [SC-12]
- Done means: the L2-b evidence JSON is committed.
- Acceptance: `tests/parity_compare/test_L2.py::test_L2b_costs_and_volume_cap`.

**T3.21 `feat(api): coverage and stale-mark warnings (E6, E25)`** · `M3a` `api` · S · Blocked by: T3.13a · §6.6
- Done means: in a synthetic run where decisions with valid/universe < 50% exceed 5%, one E6 line (NaN count per causing column); E25 for a holding whose mark is stale for more than 20 sessions.
- Acceptance: `tests/unit/api/test_warnings.py::test_E6_coverage`, `::test_E25_stale_mark`.

**T3.18 `docs(examples): m3a strategy walkthrough, perf smoke and stage measurement`** · `M3a` `docs` · S · Blocked by: T3.14, T1.24, T0.8c, T2.24 · §7, §8.5 *(the M3a workloads of the chapter 7 table, the full P11 (a) included [#175])*
- Done means: the README section "Backtest one strategy" runs, `uv run pytest -m perf_smoke` prints the P5-small time, and `bench/run.py --stages m3a --snapshot synth-full_ci` prints the state-machine stage times; on the compute machine, `bench/run.py --stages m3a --snapshot synth-full-0001` prints P5 and P5-daily on one market and P7, and `bench/run.py --workload P11 --part a --fixture bench/fixtures/p11.json --snapshot synth-full-0001` prints the full P11 (a) with its per-stage time, cold and warm (figures into the milestone tracking issue, and with the first P5-daily figure the person sets the P5-daily budget and target in chapter 7).
- Acceptance: `tests/docs/test_examples.py::test_readme_m3a`, `tests/perf/test_smoke.py::test_P5_small`, `tests/docs/test_lessons.py::test_lesson[cost-change]`, `tests/docs/test_scenarios.py::test_scenario[1]`, `::test_scenario[5]` (the 8.5 lesson and use scenarios, D19, #219).

**T3.Gd `test(golden): v3.1 volume-cap, rounding, small-trade and target-gap cases (G-56, G-58, G-59, G-66)`** · `M3a` `golden` · M · Blocked by: T0.9, T0.15a · §5.6.1, §5.6.6, §5.6.7, §8.2
- Context: the cases of the 8.2 table; the quantity, stale-mark and delisting-distribution cases G-53~G-55 are T3.Gg's. Merged before the consuming tickets T3.5b, T3.23, T3.25 and T3.26.
- Done means: `uv run python tests/golden/check/G-56.py` prints the filled and carried-over quantity per session.
- Acceptance: `test_handcalc_self.py::test_cases_v31_M3a_expected_present`.

**T3.Ge `test(golden): v3.1 benchmark, Calmar and Sortino cases (G-62, G-110, G-125, G-128, G-136)`** · `M3a` `golden` · S · Blocked by: T0.9 · §5.7, §8.2
- Context: benchmark alignment and relative metrics, Calmar; the metrics and drawdown cases G-60 and G-61 are T3.Gg's. Merged before the consuming tickets T3.13a, T3.20, T4.6 and T4.12.
- Done means: `uv run python tests/golden/check/G-110.py` prints Calmar 2.001499 for (a) and "n/a (no drawdown)" for (b); the case beside G-77 (8.2): three sessions whose rates are 0%, 4% and 2%, with the hand-computed accrual and excess return, the numbers computed by this ticket (#313, decision 2026-11-10).
- Acceptance: `test_handcalc_self.py::test_cases_v31_metrics_expected_present`.

**T3.22 `feat(accounting): stale marks adjusted for corporate actions and distributions before delisting counted once`** · `M3a` `accounting` · M · Blocked by: T3.22a, T3.11, T2.7 · · §5.6.3(6), §5.6.7, §5.6.9, §5.6.13
- Context: beyond T3.22a: `distribution_in_terminal`, when null (d) the conservative side + E30, or E13 when `unknown_inclusion = "error"`, a late inclusion flag, and the label's terminal amount equal to the accounting one through the shared `terminal_value` of T2.7a.
- Done means: the G-55 (g) and (h) case tables print as they are.
- Acceptance: `tests/golden/test_accounting.py::test_G55_late_inclusion_flag_preserves_prior_orders`, `::test_G55h_unknown_inclusion_conservative`, `::test_G55g_label_equals_accounting_terminal`.

**T3.23 `feat(accounting): per-component money rounding from market rules packs`** · `M3a` `accounting` · S · Blocked by: T3.8, T3.Gd · §5.6.1, §5.6.8, §4.7
- Context: pack `[rounding]` (mode and unit per component), user `[rounding.<MARKET>]` overrides, default KR commission, tax and withholding `down` and the rest half_up, US half_up, the pack edition in `settings_hash`.
- Done means: G-58 prints 23 won for the default KR pack and 24 won for the test pack (half_up), and the bridge `rounding` row closes.
- Acceptance: `tests/golden/test_execution.py::test_G58_component_rounding`, `tests/unit/accounting/test_rounding.py::test_kr_default_down_us_half_up`, `::test_user_override_recorded_in_settings_hash`.
- Notes:
  - carried (#43 Decisions, 2026-11-02, #95): the rules packs hold the rounding `mode` as a plain string checked against `RoundingModePolicy`'s values; this ticket, which merges a pack's `[rounding]` with the user's `[rounding.<MARKET>]`, turns it into the member.
  - carried (#43 Decisions, 2026-11-02, #94): `load_config` does not compare a rules-pack default.

**T3.25 `feat(execution): minimum trade threshold and rebalance band at the order-intent stage`** · `M3a` `execution` · S · Blocked by: T3.5b, T3.Gd · §3.7, §5.6.7, §3.11
- Context: `min_trade_value`, `min_trade_weight`, `rebalance_band`, `band_mode` (arguments and toml), new entries, full exits and sign changes exempt, `order_suppressed(small|band)`, the report line, off in the preset.
- Done means: the tables of the three G-59 cases print, and a run with the knobs off is byte-identical to v3.
- Acceptance: `tests/golden/test_execution.py::test_G59_small_trades_and_band`, `tests/unit/execution/test_small_trades.py::test_entries_and_exits_exempt`, `::test_default_off_identical`, `::test_targets_unchanged`.

**T3.26 `feat(research): target gap, lot rounding drag and execution quality metrics`** · `M3a` `research` · M · Blocked by: T3.14, T3.Gd · §5.6.7, §5.6.8, §5.7, §5.9.1
- Context: `target_gap` and its breakdown by cause, `rounding_gap` and `n_zero_lot_targets` (E37), per fill `slip_vs_decision_bps`, `slip_vs_arrival_bps`, `effective_price` and `outside_range`, the first-screen "target gap" line, the HTML "execution" section, derived from the canonical events.
- Done means: G-66 prints 3.33%, 1 instrument, 1.67% and the E37 case, and the target gap line appears on the Run first screen.
- Acceptance: `tests/golden/test_execution.py::test_G66_target_gap_and_lot_rounding`, `tests/unit/research/test_exec_quality.py::test_slip_bps_sign`, `::test_outside_range_count`, `::test_gap_by_cause_sums`, `::test_intended_cash_not_reported_as_rounding_gap`, `tests/property/test_execution_invariants.py::test_P_DERIVED_quality_columns`.

**T3.Gr `test(golden): sizing and risk cases (G-78..G-87, G-95)`** · `M3a` `golden` · M · Blocked by: T0.9 · §5.5.1a, §5.5.2, §5.5.2a, §5.5.2b, §8.2
- Context: case yaml moving G-R1~G-R10 of teardown F to G-78~G-87, writing per-decision weights, multipliers and states literally, plus a check (arithmetic and square roots only). Merged in another session before the implementation PR.
- Done means: `uv run python tests/golden/check/G-84.py` prints a table of NAV, shadow index, DD, state and m per decision.
- Acceptance: `tests/golden/test_handcalc_self.py::test_case_G78_to_G87_expected_present`, `::test_case_G95_expected_present` (G-108 removed 2026-11-24, #752 [#151]).

**T3.27 `feat(portfolio): sizing slot with built-in sizers and @nx.sizer`** · `M3a` `portfolio` · M · Blocked by: T3.1, T3.Gr · §3.7, §3.8, §5.5.1a
- Context: `Strategy(sizing=)`, the `top(weight=…)` shorthand and E16 when given twice, `size.equal`, `value`, `inverse_vol`, `score`, `vol_parity`, `stop_risk`, the modifier `cash_floor` (`size.kelly` reserved E18, v1.x [R4F-02]), list order, `SizingContext` (no account), `@nx.sizer` (units/weights, E41), skips for instruments without inputs, `TargetFrame.stage = sizing` and `pre_risk_weight`.
- Done means: at one decision of `examples/strategies/inverse_vol_kr.py`, `explain` shows the construction → sizing weights and prints that the shorthand and the explicit sizer give the same result.
- Acceptance: `tests/golden/test_sizing.py::test_G78`, `::test_G83`, `::test_G95_score_vol_parity_cash_floor`, `tests/unit/portfolio/test_sizing.py::test_shorthand_equals_explicit_bit`, `::test_weight_given_twice_E16`, `::test_kelly_reserved_E18`, `::test_stop_risk_reads_exit_pct`, `::test_user_sizer_negative_E41`, `tests/property/test_risk_invariants.py::test_P_SIZE_PURE`.

**T3.28 `feat(portfolio): ERC by fixed-order coordinate descent with defined fallback, and vol_target`** · `M3a` `portfolio` · M · Blocked by: T3.27 · §5.5.1a
- Context: listwise-deletion covariance (left fold in `instrument_id` order, no BLAS), shrinkage `shrink`, coordinate descent (start 1/σ, 500 sweeps, 1e-14), fallbacks a/b/c → `inverse_vol` + E43 + skips, the modifier `vol_target` (minimum of four terms — the fourth = the long–short feasible region, cap on scaling up).
- Done means: in a synthetic strategy where the fallback happens, the report prints "erc did not converge on k of m decisions; inverse_vol used" and the counts per reason.
- Acceptance: `tests/golden/test_sizing.py::test_G79`, `::test_G80`, `::test_G81`, `::test_G81d_long_short_bound`, `tests/unit/portfolio/test_erc.py::test_fixed_order_bit_stable`, `::test_fallback_reasons_counted`, `::test_no_blas_calls`.

**T3.29 `feat(risk): ordered risk rule list with market-only built-ins, user rules and waterfall`** · `M3a` `risk` · M · Blocked by: T3.27, T3.Gr · §5.5.2, §5.5.2a waterfall
- Context: the `risk=[…]` list (written order, `graph_hash`), applying the multiplier `m ∈ [0,1]` and E41, `group_caps` (gross/net, `<unknown>`), `regime` (three-valued), `vol_cap`, `liquidity_cap(capital="notional")`, exposure-cap fitting after the list, `@nx.risk_rule(reads_account=False)`, `reason = risk:{rule}`, `waterfall.parquet`, the report lines "risk waterfall" and "risk order".
- Done means: the report of a `risk=[nx.risk.group_caps(nx.Item.sector, max=0.3), nx.risk.vol_cap(0.15)]` strategy prints the mean `Σ|w|` per section and the number of decisions where it triggered (numerator/denominator).
- Acceptance: `tests/golden/test_risk.py::test_G82`, `::test_G85`, `::test_G86`, `tests/unit/risk/test_group_caps.py::test_caps_and_cash`, `::test_no_account_state_input`, `tests/unit/risk/test_rules.py::test_mult_out_of_range_E41`, `::test_order_in_graph_hash`, `::test_account_rule_before_market_rule_E16`, `tests/unit/risk/test_liquidity_cap.py::test_adv_needs_half_lookback`, `tests/property/test_risk_invariants.py::test_P_RISK_SHRINK`.

**T3.30 `feat(risk): account layer with final targets, risk state, drawdown brake and portfolio stop`** · `M3a` `risk` · M · Blocked by: T3.29, T3.12, T3.5b, T3.22, T3.14 · §1.3 INV-23, §5.5.2a, §5.5.2b, §5.6.7
- Context: the `final_weight` column and the account layer (without rules, copied without being called), a read-only account view, `risk_state.parquet` (included in checkpoints), `drawdown_brake` (brake/linear, shadow index, peak reset at re-entry), `portfolio_stop`, `liquidity_cap(capital="nav")`, user rules with `reads_account=True`, a ruined sleeve skips the layer, 5.6.7 uses `final_weight`, the final constraint check after the layer with `constraint_residual` skips rows and its report header line (5.5.2b) [#151].
- Done means: the run summary of `examples/strategies/erc_brake.py` shows "drawdown brake: 2 of 120 decisions braked, 1 round trip" and the brake intervals.
- Acceptance: `tests/golden/test_risk.py::test_G84`, `::test_G87_account_part`, `tests/property/test_risk_invariants.py::test_P_RISK_OFF`, `tests/unit/risk/test_account_layer.py::test_not_called_without_account_rules`, `::test_state_roundtrip_resume`, `::test_shadow_includes_delisting_loss`, `::test_ruined_writes_suspended_row`, `::test_negative_zero_normalized`, `::test_band_prior_uses_canonical`, `tests/property/test_execution_invariants.py::test_P_RESUME_with_risk_state`, `tests/unit/risk/test_final_check.py::test_residual_kept_never_E46`.

**T3.31 `feat(portfolio): @nx.portfolio user construction block`** · `M3a` `portfolio` · S · Blocked by: T3.1, T0.4b · §3.7 block contract, §3.8
- Context: `PortfolioContext` (scores, ranks, universe, the previous `TargetState`, read only), output = id → ±1, rank = score order + tie key, out-of-universe and side value errors E41, −1 with shorting off is E16.
- Done means: the `custom-portfolio` example (1 per industry among the top scores) prints screen targets.
- Acceptance: `tests/unit/portfolio/test_user_portfolio.py::test_selection_only`, `::test_out_of_universe_E41`, `::test_short_needs_shorting_E16`, `::test_side_both_E16_use_long_short`.

**T3.32 `feat(artifacts): skip ledger and no-silent-failure summary`** · `M3a` `artifacts` · S · Blocked by: T3.14, T0.4b · §6.6 no silent failure, §5.9.1
- Context: `skips.parquet`, the reason code list `skips.toml` (an E code for every reason), E45, the "skipped:" line on the report and CLI first screen (none when 0).
- Done means: the backtest first screen of a synthetic strategy with many missing values shows "skipped: n rows in k reasons (top: …)".
- Acceptance: `tests/property/test_skips.py::test_P_SKIP`, `tests/unit/artifacts/test_skips.py::test_every_reason_has_code`, `::test_summary_line_always_present`.
- Notes:
  - carried (#43 Decisions, 2026-11-19, #246 and #570): `declaration_unchecked` (E45) is in 6.6's reason list and the engine warns it at the end of a run, but no row goes to `skips.parquet` and `skips.toml` does not exist; this ticket writes that row.

**T3.34 `feat(api): strategy.replace and backtest preview`** · `M3a` `api` · S · Blocked by: T3.13a, T3.27 · §3.7, §3.8 preview, §3.10
- Context: `Strategy.replace(**slots)` (name shown as `~slot`), `backtest(preview=True)` and CLI `--preview` (last 1 year inside the chosen segment, top 200 by value traded, scenarios off, `kind="preview"`, for a new strategy candidate +1 and an observation `fidelity="preview"`, the hygiene `preview runs` line), the `[preview]` keys.
- Done means: `uv run nexusbt backtest examples/strategies/mom_kr.py --preview` prints the line "PREVIEW — 1y (train segment), top 200 …" and the time taken, and for a strategy seen for the first time the study candidate count goes up by 1 and the `preview runs` line appears in hygiene.
- Acceptance: `tests/unit/api/test_replace.py::test_replace_changes_only_named_slots`, `tests/unit/api/test_preview.py::test_preview_new_strategy_counts_as_candidate`, `::test_preview_period_inside_segment`.

#### M3b — order types (the limit, stop, stop-limit and exits of 9.0)

**T3.15b `feat(execution): confirm zipline 3.2.1 trigger semantics for the parity preset`** · `M3b` `execution` · S · Blocked by: T3.15a, T3.5b, T3.22 · §5.6.15 [SC-12, OQ-9]
- Context: read zipline 3.2.1 `finance/execution.py`, `finance/order.py` (trigger state) and `finance/slippage.py` at the pinned version, confirm the daily-bar trigger and fill price rules, and settle or fix the "[est.]" lines of the 5.6.15 table (a spec fix = "spec deviation" in the PR description + an ADR-0021 update).
- Done means: quotes of source lines of the pinned zipline version and the settled rules in the PR description.
- Acceptance: `tests/unit/execution/test_preset_zipline.py::test_trigger_on_close_only`.

**T3.Gb `test(golden): order-type cases (G-02..G-09, G-32, G-33, G-37..G-40)`** · `M3b` `golden` · M · Blocked by: T0.9 · §5.6.2a, §5.6.4, §8.2
- Context: limit at the open and through/touch, stop gaps and intraday, stop-limit (including the `Lp = Sp` boundary), OCO, a stop on the same bar as an entry at the open, no take-profit on the same bar as an intraday entry, H/L null, fill record columns, persistent triggers (G-37), partial OCO protection (G-38), no exit expiry (G-39), intraday sale proceeds (G-40). Merged before T3.6 and T3.7.
- Done means: `uv run python tests/golden/check/G-37.py` prints the trigger state and `remaining_qty` per session.
- Acceptance: `test_handcalc_self.py::test_cases_order_types_expected_present`.

**T3.6 `feat(execution): limit, stop and stop-limit daily fill rules with persistent triggers and fill records`** · `M3b` `execution` · M · Blocked by: T3.5b, T3.15b, T3.Gb · §5.6.4, §5.6.3 [SC-11]
- Done means: G-02~G-06, G-32, G-33, G-37, G-40 pass, one E11 line and "x/n fills judged on daily bars" in the run warnings, the assumption sentence line.
- Acceptance: `test_execution.py::test_G02` … `::test_G06`, `::test_G32`, `::test_G33`, `::test_G37_stop_stays_triggered_after_partial`, `::test_G40_intraday_sale_cannot_fund_same_bar_buy`, `tests/unit/execution/test_fill_rules.py::test_through_vs_touch_table`, `::test_stop_limit_equal_boundary`, `::test_fill_rule_names`.

**T3.7 `feat(execution): exit order lifecycle, resizing and OCO`** · `M3b` `execution` · M · Blocked by: T3.6 · §3.7 exits, §5.6.2a, §5.6.4
- Done means: G-07~G-09, G-38, G-39 pass; prints a table with the trailing stop price rising day by day.
- Acceptance: `test_execution.py::test_G07`, `::test_G08`, `::test_G09`, `::test_G38_partial_oco_keeps_protection`, `::test_G39_exit_never_expires`, `tests/unit/execution/test_exits.py::test_created_after_entry_fill`, `::test_resized_on_position_change`, `::test_trailing_updates_at_close`, `::test_time_stop_reserved`, `::test_partial_adverse_oco_keeps_remaining_protection`.
- Notes:
  - owner decides at the cut (#43 Decisions, outside review of 2026-11-03): whether a same-bar take-profit exception is added when the path is determinable (a behaviour change, with a golden case; 5.6.4).

**T3.17b `test(parity): L2-d order types against zipline semantics`** · `M3b` `parity` · S · Blocked by: T3.15b, T3.17a · §8.1 [SC-12]
- Done means: the L2-d evidence JSON is committed and `engine / parity` is added as a required check (by the user).
- Acceptance: `tests/parity_compare/test_L2.py::test_L2d_order_types_preset`.

**T3.19 `feat(api): explain strategy decisions`** · `M3b` `api` · M · Blocked by: T3.13a, T3.7 · §3.8, §5.9.9 [SC-13]
- Done means: `uv run nexusbt explain examples/strategies/mom_kr_exits.py KR:T00007 2019-06-28` prints stages 1~4 and the execution-session judgement (stage 6, including exit order events) in the shape of 5.9.9; an instrument dropped by the universe Filter gets a "dropped here" line.
- Acceptance: `tests/unit/api/test_explain_strategy.py::test_filter_tree_drop_point`, `::test_rank_and_selection`, `::test_stage_weights`, `::test_execution_session_blocked_reason`, `::test_needs_account_state_marked`.

**T3.20 `feat(research): MinTRL, Lo-adjusted Sharpe, drawdown durations and signal-weight correlation`** · `M3b` `research` · M · Blocked by: T3.13a, T3.Ge · §5.7 [SC-08, SC-09]
- Done means: on a hand-made return series, MinTRL, ρ1, Lo Sharpe (lags ≤ 10), drawdown duration, recovery duration and worst month print equal to the expected values; MinTRL and signal-weight corr lines on the Run first screen.
- Acceptance: `tests/unit/research/test_risk_stats.py::test_min_trl_known_value`, `::test_lo_sharpe_only_when_rho_large`, `::test_drawdown_and_recovery_durations`, `::test_worst_month`, `tests/golden/test_metrics.py::test_G61_drawdown_edges`, `::test_worst_month_compounds`, `::test_signal_weight_corr_definition`, `::test_stat_unavailable_cases`, `tests/docs/test_tool_cards.py::test_card[min-trl]`, `::test_card[lo-sharpe]` (D19, #219).
- Notes:
  - carried (#43 Decisions, 2026-11-19, #439): Sharpe, PSR, DSR and MinTRL compute on excess returns `r_t − rf_t`, while 5.7's `ρ1` and 6.3's Lo Sharpe row still read "daily net returns"; this ticket says which returns the autocorrelations take and the rows follow.

**T3.Gf `test(golden): price grid cases (G-57)`** · `M3b` `golden` · S · Blocked by: T0.9 · §5.6.4a, §8.2
- Context: G-57 (a)~(h) (US 1 ULP, KR stop rounded down, limit buy rounded down, computed upper and lower limits, short-cover stop rounded up; comparisons across price bands, the fractional era and off-grid bars, snapping across a boundary and GTC re-snapping). Merged before T3.24.
- Done means: `uv run python tests/golden/check/G-57.py` prints the raw values, grid values and fills of the eight cases (a)~(h).
- Acceptance: `test_handcalc_self.py::test_case_G57_expected_present`.

**T3.24 `feat(execution): market price grid for order prices and minimum-unit integer comparisons`** · `M3b` `execution` · M · Blocked by: T3.6, T3.Gf, T0.16c, T0.5b · §5.6.4a, §4.7, §4.5 F-15
- Context: grid source order (instrument → `market_rules` → pack → minimum unit), conservative snapping of order prices (limit, stop, exit, resizing, after a split; snapping across a price band boundary), GTC re-snapping on rule dates (`order_rebased(grid)`), the `price_rounded` event and `price_unrounded`, conversion of bar and order prices to `base_unit` integers and their comparison, off-grid bars `off_grid_bar`, F-15, off in the preset.
- Done means: the G-57 (a)~(h) case tables come out as they are, and with `degrade=["no_tick_info"]`, E30 "price grid = currency minor unit".
- Acceptance: `tests/golden/test_execution.py::test_G57_price_grid`, `tests/unit/execution/test_grid.py::test_source_order`, `::test_conservative_direction_table`, `::test_ulp_noise_compares_equal`, `::test_price_order_preserved_across_tick_bands`, `::test_snap_crosses_band_to_valid_price`, `::test_gtc_regridded_at_rule_date_boundary`, `::test_off_grid_bar_kept_and_counted`, `tests/property/test_execution_invariants.py::test_P_GRID`.
- Notes:
  - decided (#844 Decisions, 2026-11-27; #802): a US tick that depends on a class the exchange assigns to single stocks, the per-instrument increment from 2027-11-01 included, is not simulated; every stock takes its market's general rule, and the spec and the rules pack say so as a documented assumption.
  - carried (#43 Decisions, 2026-11-20, #660): `_no_grid` reads whether a market has a rule of a kind at any date, so a later row can change an earlier decision's grid source; this ticket settles the presence check by #660's rule (a row applies from `valid_from` to `valid_to`, never read ahead), and P-FUT then cuts `market_rules` by `valid_from`.
  - carried (#43 Decisions, 2026-11-05, #287 and #303): 5.6.4a's "`U` and `D` … are snapped to the grid too" reads as unconditional while 5.6.5 leaves them unrounded when the market has no tick table; this ticket has 5.6.4a say the no-tick-table case, put to the owner as a spec change.
  - carried (#43 Decisions, 2026-11-16, #453): an instrument without a grid source in a market that has one is not F-15 but falls to the minor unit at the decision; this ticket names the source in its assumption sentence and gives the count of such instruments.
  - owner decides at the cut (#43 Decisions, 2026-11-16, #453): whether a pack `[grid]` with only `base_unit` counts as a grid at open.
  - carried (#43 Decisions, 2026-11-02, #104): in `ticks/kr_tick_table_v1.csv` an ETF matches both the 2023 table common to KOSPI, KOSDAQ and KONEX (`venue_group = *`) and the `ETF` row (5 won at every band); this ticket says which wins.
  - carried (#43 Decisions, 2026-11-02, #54): spec 4.7 gives no value for the pre-decimal US sub-$1 tick or for a KONEX row in the 2010–2023 KR tick table, so the seed tables hold neither row.

**T3.33 `feat(execution): time stop exit in the OCO group and no-reentry rule`** · `M3b` `execution` · S · Blocked by: T3.7, T3.30 · §3.7 exits, §5.5.2a
- Context: `exits.time_stop(n)` (first entry session = 1, market calendar sessions including halt days [V31-52], created after the close, next open), OCO with stops and take-profits, counting restarts when the sign changes; `risk.no_reentry(sessions, after)` (reads exit events).
- Done means: `explain` shows that `nx.exits.time_stop(5)` sells at the next open 5 sessions after entry and that at the following decisions `no_reentry(21)` keeps that instrument at 0.
- Acceptance: `tests/unit/execution/test_exits.py::test_time_stop_oco`, `::test_time_stop_counts_sessions`, `::test_time_stop_resets_on_sign_flip`, `tests/unit/risk/test_no_reentry.py::test_blocks_after_stop_exit`.

**T5.16a `feat(portfolio): strategy state record with checkpoint save and restore`** **[2026-11-04]** · `M3b` `portfolio` · S · Blocked by: T3.12, T3.5b, T3.22 · §5.5.3, §5.6.1 [#152]
- Context: split from T5.16 (decision 2026-11-04, #152; the T3.35 note removed 2026-11-24, #752). The strategy state record of 5.5.3 (`target_state` rows keyed by `sleeve_id` and `instrument_id` with `target_weight`, `set_by`, `missing_streak`; `risk_state` rows), its Arrow serialisation sorted by key, writing it to the checkpoint (5.6.1) and alongside `targets.parquet`, restoring it, and `build_targets(..., prior=)` receiving and returning it (empty for a schedule-only strategy before T7.1). The ledger manifest part stays in T5.16.
- Done means: a run checkpointed at a random session and restored gives bit-identical canonical and final targets and the same state record as a run without a stop, with a `missing_streak` carried across the stop.
- Acceptance: `tests/unit/portfolio/test_target_state.py::test_missing_counter_survives_checkpoint`, `::test_short_band_state_roundtrip`, `::test_risk_state_rows_roundtrip` (the event-target checkpoint test removed 2026-11-24, #752).

**T3.35 `superseded`** · `M3b` · Blocked by: none · removed 2026-11-24 (#752) with `on_event`, G-97 and G-108 [#725 Decisions 224].

#### M4 — Multiple markets (KR/US synthetic, market rules packs) + short selling and long–short [V31-LS]

**T4.G `test(golden): sleeve, timing, currency and tax cases (G-27..G-29, G-36, G-50..G-52)`** · `M4` `golden` · S · Blocked by: T0.9 · §5.1.3, §5.6.3, §5.6.9, §5.6.11a, §8.2
- Context: sleeve funding wait, DST and holiday mismatches, silent FX, currency attribution, a close fill at the same instant as `KR_close` → decision, tax scenarios. Merged before T4.1, T4.2, T4.5b and T4.10.
- Done means: `uv run python tests/golden/check/G-50.py` prints the order quantities in which the close-fill `q_i` is reflected in the decision.
- Acceptance: `test_handcalc_self.py::test_cases_sleeves_expected_present`.

**T4.1 `feat(execution): multi-sleeve event queue, phase order and clock modes`** · `M4` `execution` · M · Blocked by: T3.12, T3.5b, T3.22, T4.G · §5.1.3, §5.6.3
- Done means: an example showing that the US fill dates and prices of a `KR_close` run and a `market_local` run are the same (no cross-market terms, part of G-27); an event-order table showing that a close fill at the same instant is processed before the decision.
- Acceptance: `tests/unit/execution/test_clock.py::test_kr_close_us_uses_previous_close`, `::test_us_close_kr_same_day`, `::test_single_market_forces_local`, `::test_utc_clock_reserved_E18`, `::test_equal_time_close_fill_before_decision`, `::test_clock_name_from_snapshot_markets`, `tests/golden/test_sleeves.py::test_G50`.

**T4.2 `feat(accounting): sleeve funding, fx valuation and drift`** · `M4` `accounting` · M · Blocked by: T4.1, T2.5 · §5.6.9
- Done means: G-27 and G-29 pass; the sleeve_weight path in daily.parquet.
- Acceptance: `tests/golden/test_sleeves.py::test_G27`, `::test_G29`, `tests/unit/accounting/test_fx.py::test_direction_and_inverse`.

**T4.3 `feat(compute): cross-market terms gathered at decisions`** · `M4` `compute` · S · Blocked by: T4.1, T2.5 · §5.3.2 (6)
- Done means: the result of `.to("USD").rank(across_markets=True)` is one ranking table per decision.
- Acceptance: `tests/unit/compute/test_cross_market.py::test_gather_uses_row_m_of_d`.
- Notes:
  - carried (#43 Decisions, 2026-11-19, #249): `nx.run_pipeline` and the executor refuse a term with `across_markets=True` with `NotImplementedError` naming T4.3 (`test_across_markets_not_supported_yet`); this ticket gathers the markets' rows at a decision (5.3.1 step 6) and removes both refusals.

**T4.4 `feat(execution): price-limit history from market rules packs and unknown tradability policy`** · `M4` `execution` · S · Blocked by: T3.5a, T3.24 · §5.6.5, §4.7
- Done means: the limit widths 0.15/0.30 of the sessions before and after 2015-06-15 are printed; with the US pack (no price limits) there are no upper or lower limit locks; E27 in the `unknown_tradability="block"` sensitivity run.
- Acceptance: `tests/unit/execution/test_limits.py::test_resolution_order`, `::test_rule_boundary_2015_06_15`, `::test_limits_only_where_pack_defines`, `::test_unknown_tradability_block`, `::test_missing_tradability_dataset_E30`, `::test_computed_limits_on_grid` (G-57 (d)), `::test_market_rules_limit_source_order`.

**T4.5 `feat(execution): realistic dated cost profile end to end`** · `M4` `execution` · M · Blocked by: T3.8 · §5.6.8, §4.7
- Done means: with the verification table (a `verified=true` copy for tests), the KR 2014 and 2024 sell taxes are recorded as the table's different values.
- Acceptance: `tests/unit/execution/test_costs_dated.py::test_tax_by_date`, `::test_us_other_fees`, `::test_venue_group_mapping`.
- Notes:
  - owner decides at the cut (#43 Decisions, outside review of 2026-11-03): whether KR taxes get an ETF transaction-tax exemption axis.
  - carried (#43 Decisions, 2026-11-01, #38, #17 and #27): the verification table says whether its KOSPI rows include the rural-development special tax (0.15%), with a primary source for each year it gives; the securities transaction tax of 2014 and 2016 is the same under Decree No. 24641, so this ticket compares 2014 with 2024.
  - carried (#43 Decisions, 2026-11-19, #125 and #103): the cost seed table has no KONEX and no `commission` rows and no FINRA TAF, and no spec rule covers overlapping securities-tax and rural-tax rows.

**T4.5b `feat(accounting): user-configured tax scenario`** · `M4` `accounting` · M · Blocked by: T4.G, T4.2, T3.13a · §5.6.11a, §3.11 *(user decision 2026-10-28: the user writes taxes in the config file)*
- Done means: running the `[taxes] profile = "custom"` example config (US group 22%, deduction 2,500,000 won, average) gives yearly taxes in `tax.parquet` equal to the G-51 hand calculation, and with `pay = "cash"` the cash of the first session of May of the next year drops by that amount (G-52). With `profile = "none"` the result is bit-identical to before this ticket.
- Acceptance: `tests/golden/test_taxes.py::test_G51`, `::test_G52`, `tests/unit/accounting/test_tax_basis.py::test_average_vs_fifo`, `::test_fx_conversion_at_valuation_rate`, `::test_none_profile_unchanged`.

**T4.6 `feat(api): benchmarks from index instruments`** · `M4` `api` · S · Blocked by: T3.13a, T3.Ge · §5.7, §4.6, §4.5 F-12
- Done means: a benchmark column on the synthetic snapshot (`auto` picks one TR index per market); "n/a: not in snapshot" with `degrade=["no_benchmarks"]`; an E16 list when there are two TR indexes.
- Acceptance: `tests/unit/api/test_benchmarks.py::test_combined_benchmark_sleeve_weighted`, `::test_missing_is_na`, `::test_auto_picks_single_tr_index`, `::test_auto_ambiguous_E16`, `tests/golden/test_metrics.py::test_G62_benchmark_alignment`, `::test_weighting_label_in_header`.

**T4.7 `feat(api): combined multi-market backtest and screen reports`** · `M4` `api` · M · Blocked by: T4.2, T4.3, T4.6, T4.10 · §3.9
- Done means: `uv run nexusbt backtest examples/strategies/value_mom.py` prints KR/US columns, the sleeve weight path, cost sensitivity and the `fx contribution` line; `nexusbt screen` prints "KR {date} close · US {date} close".
- Acceptance: `tests/unit/api/test_combined.py::test_combined_equals_sum_of_sleeves`, `::test_screen_two_markets_asof`, `::test_fx_contribution_line`, `::test_markets_header_line`.

**T4.8 `test(property): DST, holiday mismatch, timing and currency metamorphic cases with preconditions`** · `M4` `property` · S · Blocked by: T4.2, T4.10 · §8.2, §8.3
- Done means: G-28 passes; M-CCY and M-SLEEVE pass (within their preconditions), and the `KR_close` + cross-market rank counterexample confirms that the relation breaks.
- Acceptance: `tests/golden/test_sleeves.py::test_G28`, `tests/property/test_execution_invariants.py::test_P_FUT_two_markets`, `tests/property/test_metamorphic.py::test_M_CCY`, `::test_M_SLEEVE`, `::test_M_SLEEVE_counterexample_cross_market`, `tests/property/test_execution_invariants.py::test_P_SLEEVE_ISO`.

**T4.9 `docs(examples): m4 multi-market walkthrough and stage measurement`** · `M4` `docs` · S · Blocked by: T4.7, T1.24, T0.8c · §7, §8.5
- Done means: the README section "Korea + US together" runs, and `bench/run.py --stages m4 --snapshot synth-full-0001`, run by a person on the compute machine, prints the whole P5 (two sleeves, five scenarios), P5-daily KR+US and P7, cold and warm (figures into the milestone tracking issue).
- Acceptance: `tests/docs/test_examples.py::test_readme_m4`.
- Notes:
  - carried (#43 Decisions, 2026-11-19, #264): "five scenarios" in chapter 7's P5 and end-of-M4 rows, in this entry and in A-51 is left as written at the owner's request, although a KR run with a hypothetical exit replays `ca_exit_lo` as one more.

**T4.10 `feat(artifacts): currency attribution and exposure tables`** · `M4` `artifacts` · M · Blocked by: T4.2, T3.14 · §5.6.9, §5.9.1 [SC-07, OQ-3]
- Done means: G-36 passes; in `runs/<id>/attribution.parquet`, local + FX + cross = the base-currency sleeve return (per date); `exposures.parquet` has currency, sector (per sleeve), size, top 10 and cash weight.
- Acceptance: `tests/golden/test_sleeves.py::test_G36`, `tests/unit/artifacts/test_attribution.py::test_fx_attribution_sums`, `::test_annual_linking_exact`, `::test_annual_fx_components_sum_G36` (cross = `R − L − F`), `::test_exposures_columns`, `::test_sector_exposure_per_sleeve_only`.
- Notes:
  - owner decides at the cut (#752 Decisions, 2026-11-27; #725 Decisions 250): what the `sector` column of `exposures.parquet` (5.9.1) groups by, now that the classification scheme it read has left with `classifications`; the column stays, with no new rule or setting name.

**T4.11 `test(markets): market names from data with a synthetic third market ZZ`** · `M4` `markets` · S · Blocked by: T4.7, T0.5b · §4.7, §4.8, §3.11
- Context: a synthetic `markets=("KR","ZZ")` snapshot (calendar `XZZZ`, currency `XTS`), a test rules pack `tests/fixtures/ZZ.toml`.
- Done means: without a pack, an `nx.universe("ZZ")` backtest gives the E18 sentence; with `allow_untested = true` it runs with the header line "untested market rules: ZZ"; with the test pack added the same strategy runs without code changes; `grep -rn '"KR"\|"US"\|XKRX\|XNYS' src/nexusbt` finds 0 hits outside `resources/markets/` and documentation strings.
- Acceptance: `tests/unit/markets/test_markets.py::test_zz_without_pack_E18`, `::test_allow_untested_stamped`, `::test_zz_with_pack_runs`, `tests/repo/test_no_hardcoded_markets.py::test_no_market_literals_in_src`.

**T4.12 `feat(research): benchmark-relative metrics and monthly return table`** · `M4` `research` · S · Blocked by: T4.6, T3.Ge · §5.7, §3.9
- Context: excess return (arithmetic and geometric named separately), tracking error, IR, excess MDD, a calendar-month compounded table (HTML "monthly"), the first-screen "vs benchmark" line, the weighting method shown in the header.
- Done means: the G-62 numbers (tracking error 0.112250, IR 11.224972) are printed and the HTML has the monthly table.
- Acceptance: `tests/golden/test_metrics.py::test_G62_relative_metrics`, `tests/unit/research/test_benchmark_relative.py::test_arith_vs_geom_named`, `::test_monthly_compounds`, `::test_na_without_benchmark`.

**T4.13 `feat(execution): optional dated and liquidity-tiered provisional cost tables`** · `M4` `execution` · S · Blocked by: T3.8 · §3.7, §5.6.8, §4.7 [V31-27]
- Context: `provisional(table=)` and `[costs] provisional_table` (a user-written CSV: market, side, period, ADV amount band, bp), row lookup by the ADV at the decision, E23 for gaps, HTML "cost tiers". The default (no table) is the same as v3.
- Done means: with the test table, KR 2014 and 2024 sells and low- and high-ADV instruments are recorded with different bp, and a run without a table is byte-identical.
- Acceptance: `tests/unit/execution/test_provisional_table.py::test_dated_rows`, `::test_adv_tiers_use_lagged_adv`, `::test_gap_E23`, `::test_default_unchanged`.

**T4.Gs `test(golden): short accounting, financing, ruin and cash-interest cases (G-67..G-70, G-74..G-77, G-94)`** · `M4` `golden` · M · Blocked by: T0.9 · §5.6, §8.2
- Context: short basics and borrow accrual (weekends, before entry, 0 intraday), short dividend payment, estimate replacement, late terms, net restoration, short splits, short delisting gain and rule estimate, short mergers, short realised-gain tax (entry cost once), short ruin, cash interest. Merged before T4.15a~c and T4.19.
- Done means: `uv run python tests/golden/check/G-67.py` prints the per-session borrow accrual days and amounts and the bridge rows.
- Acceptance: `test_handcalc_self.py::test_cases_short_accounting_expected_present`.

**T4.Gt `test(golden): long-short targets, short orders and ban cases (G-71..G-73, G-109)`** · `M4` `golden` · S · Blocked by: T0.9 · §3.7, §5.5, §5.5.2b, §5.6.2a~5.6.7, §8.2
- Context: short-sale ban periods (half-open, range syntax), the long–short book bridge, exposure caps, side budgets, the feasible region, the short exit mirror (three phases), reversal wait. Merged before T4.14, T4.16a and T4.16b.
- Done means: `uv run python tests/golden/check/G-72.py` prints the long and short bridge rows and the exposure (gross 1.0, net 0), (b) 0.05, and the (c) E16 sentence.
- Acceptance: `test_handcalc_self.py::test_cases_short_orders_expected_present`, `::test_case_G109_expected_present` (2026-11-04: a cap on one leg of a pair [#151]).

**T4.17 `test(regression): long-only core-table value-hash baseline and the P-SHORT-OFF harness`** · `M4` `property` · S · Blocked by: T4.7, T4.5b, T4.13 · INV-22, §8.3
- Context: a script that runs the example strategies (M3a, M3b and M4 examples) and a few random long strategies on synthetic small and records the **value hashes** of the four core tables (`targets`, `orders`, `account_events`, `daily`) in `tests/regression/longonly_core_value_hashes.json`; the same-build differential test harness (`enabled=false` vs `enabled=true` + no negatives + default exposure); a test of 0 short events in a run with shorting off. The baseline file is a golden-protected path, and only a ticket that changes a schema edits it, with the reason in the PR description + the user approval label `baseline-update` (the guard rejects a change without the label).
- Done means: `uv run pytest -k P_SHORT_OFF` prints "core tables n/n match baseline · differential runs identical", and a PR changing the baseline without the label fails in the guard.
- Acceptance: `tests/property/test_shorting.py::test_P_SHORT_OFF_differential`, `::test_P_SHORT_OFF_no_short_events_when_disabled`, `::test_P_SHORT_OFF_core_tables_baseline`, `tests/repo/test_golden_guard.py::test_baseline_update_needs_label`.

**T4.14 `feat(portfolio): signed targets, bottom(), long-short books and exposure limits`** · `M4` `portfolio` · M · Blocked by: T4.17, T3.1, T3.30, T4.Gt · §3.7, §5.5.1, §5.5.2, §5.5.2b, §3.11 `[shorting]`
- Context: signed `target_weight` and `side`, `bottom`, `long_short` (side budgets multiply, the conflict rule for the same instrument), the feasible region `long_weight + c·short_weight ≤ 1` with E16 before the run, fitting to the gross and net exposure caps (only when on, `math.fsum`, scaling toward 0 only), E16 when shorting is off, exposure columns.
- Done means: the G-72 target table (long +0.25 × 2, short −0.25 × 2) and the scaling under `max_gross = 0.8`, (b) 0.05 on the `top(1, max_weight=0.1)` side, and (c) the 130/30 E16 sentence are printed, and `bottom` is E16 with the setting off.
- Acceptance: `tests/golden/test_portfolio.py::test_G72_targets_and_caps`, `tests/unit/portfolio/test_long_short.py::test_bottom_mirrors_top`, `::test_conflict_long_kept`, `::test_scale_toward_zero_only`, `::test_disabled_E16`, `::test_side_budget_preserves_cap_residual`, `::test_empty_and_overlapping_sides`, `::test_infeasible_book_E16`, `tests/unit/portfolio/test_risk.py::test_exposure_cap_skipped_when_disabled`, `::test_equal_weight_ninths_not_rescaled`, `::test_net_interval_must_contain_zero`, `tests/property/test_shorting.py::test_P_SHORT_OFF_differential`, `::test_P_SHORT_OFF_core_tables_baseline`, `tests/golden/test_risk.py::test_G109_pair_leg_cap_residual` [#151].

**T4.15a `feat(accounting): short positions - signed state, collateral, financing accrual, mandatory debits and ruin`** · `M4` `accounting` · M · Blocked by: T4.14, T3.22, T4.5b, T4.Gs · §5.6.1, §5.6.3(1)(6), §5.6.7, §5.6.9
- Context: signed `qty`, average short-sale price, collateral `reserved` and `buying_power` (the short-sale allocation cost function), borrow cost and rebate accrual at session start, the bridge `financing` row, booking mandatory obligations as negative cash, the ruin check (before `T_i`), the `ruined` state, order stop, metrics n/a, header line, E38 (collateral shortfall, negative cash, ruin).
- Done means: G-67 (a)~(c) and the G-76 table are printed and a run holding shorts shows `reconciled: yes`; the Run header of a ruined run shows "ruined KR on {date}".
- Acceptance: `tests/golden/test_short.py::test_G67`, `::test_G76_ruin`, `tests/unit/accounting/test_short.py::test_collateral_buying_power`, `::test_no_forced_buy_in_E38`, `::test_borrow_fee_weekend_cover`, `::test_new_short_not_charged_before_entry`, `::test_unfunded_short_obligation_books_negative_cash`, `::test_negative_V_never_flips_sides`, `::test_ruined_sleeve_stops_new_orders`, `tests/golden/test_short.py::test_G94_exit_blocked_cash_carried`, `tests/property/test_execution_invariants.py::test_P_BRIDGE_with_shorts`.
- Notes:
  - owner decides at the cut (#43 Decisions, 2026-11-13, #312): how a per-instrument borrow fee enters now that the `from_parquet` input path, `known_on`, E3 and E47 that #312's Decision rested on are gone (for example as a value-table item), and whether the US short maintenance floor of #312's Decision (4) goes into the spec with it.

**T4.15b `feat(accounting): short dividends, corporate actions and delistings on negative quantities with estimate replacement`** · `M4` `accounting` · M · Blocked by: T4.15a · §5.3.3a, §5.6.9~5.6.13
- Context: short dividend obligation (gross; if net, restored or E13; withholding only for q > 0), the obligation quantity fixed at the holding on the effective session, negative quantities in splits, stock dividends, mergers and spin-offs (integer arithmetic), the short delisting terminal obligation (three bases, 5.6.13) and the rule estimate in `decision_value`, the `nav_economic` estimate replacement.
- Done means: the G-68 (a)~(d), G-69, G-70 (a)(b) and G-74 tables are printed.
- Acceptance: `tests/golden/test_short.py::test_G68`, `::test_G68c_short_obligation_survives_cover_before_terms`, `::test_G69`, `::test_G70`, `::test_G74`, `tests/unit/accounting/test_short.py::test_unknown_short_estimate_replaced_once`, `::test_short_net_dividend_gross_up_or_E13`, `tests/property/test_execution_invariants.py::test_P_QTY_with_shorts`.

**T4.15c `feat(accounting): short realized gains in the tax scenario`** · `M4` `accounting` · S · Blocked by: T4.15b · §5.6.11a
- Context: realised P&L of a short cover (short-sale proceeds − short-sale cost (once, by the ratio) − cover amount − cover cost), sums and loss offset within the same group.
- Done means: G-75 (a)(b) is printed.
- Acceptance: `tests/golden/test_short.py::test_G75`, `::test_G75b_short_entry_cost_allocated_once`.

**T4.16a `feat(execution): short-sale and cover orders - four-action priority in every phase, reversal gating and mirrored daily fills`** · `M4` `execution` · M · Blocked by: T4.15a, T3.7, T3.24, T4.Gt · §5.6.2, §5.6.3, §5.6.4, §5.6.6, §5.6.7
- Context: `sell_short` and `buy_to_cover`, two orders for a Δ crossing the sign and `blocked(closing_leg_pending)`, the risk-reducing order and allocation in the three fill phases (an intraday increasing order does not use the same phase's proceeds or released collateral), capacity shared by physical direction, the mirrored fill rule, cover ≤ `|q|` (`qty_cancelled(over_cover)`), collateral valuation time per phase.
- Done means: the G-73 three-phase variant table is printed, and with an intent of long 10 shares → short 5 shares, on a day when the long sell fills only 6 shares because of a cap, the short sale does not fill.
- Acceptance: `tests/unit/execution/test_short_orders.py::test_split_crossing_zero`, `::test_four_action_priority_each_phase[open]`, `::test_four_action_priority_each_phase[intraday]`, `::test_four_action_priority_each_phase[close_fill]`, `::test_short_leg_waits_for_close_leg`, `::test_cover_capped_at_short_size`, `::test_capacity_shared_by_physical_direction`, `::test_collateral_mark_per_phase`, `tests/property/test_shorting.py::test_P_SHORT_OFF_differential`.

**T4.16b `feat(execution): short exits and ban periods from rules packs`** · `M4` `execution` · M · Blocked by: T4.16a, T4.4 · §3.7 exits, §5.6.2a, §5.6.4, §5.6.5, §4.7
- Context: short exit orders (stop loss, take profit, trailing) and their life (entry = 0 → negative, the adverse side within the same bar, trailing minimum, an OCO sibling cancelled only when the remaining holding is 0), the pack's `[shorting] ban_table` (half-open intervals, `scope` = `all`/`index:`/`classification:`, union of `except_universe_ids`), `blocked(short_ban)`, assumption sentences (no borrowable quantity, no uptick rule).
- Done means: the G-71 and G-73 tables are printed, and in the KR test pack's ban period the Run line shows 0 new short sales and n cover fills.
- Acceptance: `tests/golden/test_short.py::test_G71_ban_period`, `::test_G73_short_exit_mirror`, `tests/unit/execution/test_short_orders.py::test_short_entry_creates_exit_immediately`, `::test_short_intraday_entry_adverse_exit`, `::test_short_trailing_low_water`, `::test_partial_adverse_oco_keeps_remaining_protection`, `::test_ban_allows_cover`, `::test_partial_reopening_union_membership`, `::test_ban_interval_endpoints`, `::test_ban_classification_scope`, `::test_assumption_lines`.
- Notes:
  - owner decides at the cut (#43 Decisions, outside review of 2026-11-03): whether the ban table takes the KR short-sale overheated-stock designation (the KRX text was obtained; the next-session ban only from a secondary source).

**T4.18 `test(parity): L2-e long-short against the zipline preset`** · `M4` `parity` · S · Blocked by: T4.16b, T3.17a · §8.1, §5.6.15
- Context: with the zipline preset's negative holdings (no collateral constraint, borrow 0, short dividends paid), month-end top-N long + bottom-N short is compared with zipline.
- Done means: the L2-e evidence JSON is committed.
- Acceptance: `tests/parity_compare/test_L2.py::test_L2e_long_short_preset`.

**T4.19 `feat(accounting): cash interest on positive cash balances`** · `M4` `accounting` · S · Blocked by: T4.15a, T4.Gs · §3.11 `[account]`, §5.6.3(1), §5.6.9, §5.7 [user decision 2026-10-28]
- Context: `[account] cash_rate_bps` (float or {MARKET: float}, default 0), the rate read from the `[account] cash_rate` series by the rule of 5.6.3 (0) and from `cash_rate_bps` when there is none (#313, decision 2026-11-10; held by T3.4's Done means until #901), accrual at session start (only `cash_minor > 0` at the end of the previous session; 0 for negative cash), event `cash_interest`, bridge `financing`, report header "cash earns {r}%", included in the financing-cost reconciliation.
- Done means: G-77 is printed and the core-table value hashes of a `cash_rate_bps = 0` run are the same as before this ticket.
- Acceptance: `tests/golden/test_accounting.py::test_G77_cash_interest`, `tests/unit/accounting/test_cash_interest.py::test_default_zero_identical`, `::test_no_interest_on_negative_cash`, `tests/property/test_execution_invariants.py::test_P_BRIDGE_with_cash_interest`, and from #901: `tests/golden/test_metrics.py::test_G124_cash_only_zero_variance_bound` (G-124 (b), #873: a cash-only run whose interest is booked gives Sharpe "n/a (zero variance)"; not M1b's, which books no interest).

**T4.Gm `test(golden): margin account cases (G-99..G-104)`** · `M4` `golden` · S · Blocked by: T0.9 · §5.6.7a, §8.2
- Context: hand-calculated cases of 130/30 margin and loan interest (G-99), proportional reduction at the next open after a margin call (G-100), `vol_target` 1.5× (G-101), cash account rejection E16 (G-102), forced liquidation on negative equity and the holding-quantity cap (G-104) [R4H]. Written in another session and merged before T4.20 (8.2).
- Done means: `uv run python tests/golden/check/G-100.py` prints a table of the call session, the shortfall, the forced reduction quantity and E/MM after the reduction.
- Acceptance: `test_handcalc_self.py::test_cases_margin_expected_present`.

**T4.20 `feat(accounting): margin account type - buying power, debit interest, margin call and forced reduction`** · `M4` `accounting` · M · Blocked by: T4.19, T4.16a, T4.17, T4.Gm · §3.11 `[account]`, §5.6.7a, §5.5.1a, §5.6.3(1) [user decision 2026-10-28]
- Context: `[account] type` (`"cash"` default), `initial_margin`, `maintenance_margin`, `debit_rate_bps` (rules pack seeds US 0.50/0.25 unverified, none for KR), one requirement formula `R(ρ)`, allocation within `excess`, E16 for the margin feasible region, loan interest `margin_interest` and bridge `financing`, close `margin_call` → next open `forced_liquidation` (risk-reducing groups first), the ruin check as it is, the margin `G_max` of `vol_target`, E16 for margin keys on a cash account, manifest `policies.account`, report header line; the P-MARGIN-OFF baseline is recorded in this ticket's first commit.
- Done means: `uv run nexusbt backtest examples/strategies/long_short_130_30_margin.py` prints the total loan interest, the number of margin call sessions and the forced reduction amount, and running the same strategy with `type = "cash"` gives E16; the core-table value hashes of a run with the default settings are the same as before this ticket.
- Acceptance: `tests/golden/test_accounting.py::test_G99_margin_130_30_interest`, `::test_G100_margin_call_next_open`, `::test_G101_vol_target_margin`, `::test_G102_cash_rejects_margin_keys`, `tests/unit/accounting/test_margin.py::test_single_requirement_formula`, `::test_debit_excludes_short_proceeds`, `::test_forced_reduction_order_risk_reducing_first`, `::test_ruin_check_with_debit`, `tests/property/test_margin.py::test_P_MARGIN_OFF_baseline`, `::test_P_MARGIN_OFF_differential`, `tests/property/test_execution_invariants.py::test_P_BRIDGE_with_margin_interest`.
- Notes:
  - carried (#43 Decisions, 2026-11-02, #54): the US margin seeds of the rules pack are this ticket's.

#### M5 — Paper trading

**T5.1 `feat(artifacts): paper book store with locked transactions, state versions and recovery`** · `M5` `artifacts` · M · Blocked by: T3.3, T1.14b · §5.9.6 [INV-19]
- Done means: after `nx.book("paper:demo")`, `runs/books/demo/HEAD`, `book.json` (definition_sha256) and the checkpoint folder exist; reopening after a write killed at each commit boundary gives exactly one of the previous or next state, with leftovers in `orphans/`; a second writer is E35.
- Acceptance: `tests/unit/artifacts/test_books.py::test_atomic_head`, `::test_events_append_only`, `::test_book_json_definition`, `::test_P_BOOK_crash_at_each_boundary_recovers`, `::test_concurrent_writer_rejected_E35`, `::test_definition_change_E35`, `::test_snapshot_history_recorded`, `::test_book_pin_held_while_book_exists`.

**T5.2 `feat(api): live order preview with decision-level idempotency`** · `M5` `api` · M · Blocked by: T5.1, T4.7 · §3.8 live, §5.9.6
- Context: 5.9.6 rule 1 (`sheet_emitted`, `sheet_id`, a new sheet on a corrected snapshot or a changed book, `CANCELLED(superseded)`, closed sheets in T5.3); `status.json` `current_sheets` and rule 3 come with `reconcile` in T5.7.
- Done means: a second call of `nexusbt live ... --book paper:demo` gives an E26 notice and the same order table; `live → fill → live` (same decision) also produces no new orders; `live` on a corrected snapshot before the fill gives a new `sheet_id` that names the old one.
- Acceptance: `tests/unit/api/test_live.py::test_same_key_same_orders`, `::test_key_excludes_checkpoint_seq`, `::test_live_fill_live_same_decision_once`, `::test_non_rebalance_day_exits_only`, `::test_orders_csv_columns`, `::test_same_snapshot_same_sheet_id`, `::test_corrected_snapshot_supersedes_sheet`.

**T5.3 `feat(api): advance paper books with the backtest state machine`** · `M5` `api` · M · Blocked by: T5.2 · §5.9.6
- Done means: `nx.fill(book)` is E19 (exit code 3) beyond the watermark and a fill table within it; restart after a crash = the same ledger.
- Acceptance: `tests/unit/api/test_fill.py::test_watermark_E19`, `::test_crash_recovery_same_book`, `::test_foreign_order_bundle_rejected_E35`, `tests/unit/api/test_live.py::test_closed_sheet_not_superseded` (5.9.6 rule 1), `tests/property/test_live.py::test_P_LIVE`.

**T5.7 `feat(api): reconcile paper books by recorded-snapshot replay or explicit restatement, and write status.json`** · `M5` `api` · M · Blocked by: T5.3 · §5.9.6, §5.9.7 [SC-14]
- Context: 5.9.6 rule 3 (`first_divergence.id`, no sheet from `live` while the last `reconciled: NO` is unacknowledged, E35, no `--force`, `nx.acknowledge` and `nexusbt book acknowledge`, the event `divergence_acknowledged`), the `status.json` fields `current_sheets` and `first_divergence`, 5.9.7 (5) (`reconcile --day`, the order-day record).
- Done means: `uv run nexusbt reconcile --book paper:demo` gives `reconciled: yes (replay)` (exit code 0); with a correction event put in a new snapshot and `--restate`, a "restatement" mark and the first difference; on a copy with one ledger event file changed by hand, the first difference (date, instrument, phase) and exit code 4; `status.json` updated after every `live`, `fill` and `reconcile`.
- Acceptance: `tests/unit/api/test_reconcile.py::test_match_yes`, `::test_restate_distinct_from_replay`, `::test_first_divergence_reported`, `::test_exit_code_4`, `tests/unit/artifacts/test_status_json.py::test_atomic_and_fields`, `tests/property/test_live.py::test_P_RECON`, `tests/unit/api/test_reconcile.py::test_divergence_id_stable`, `::test_order_day_record`, `tests/unit/api/test_acknowledge.py::test_acknowledge_records_note_and_by`, `::test_acknowledge_not_current_divergence_E35`, `::test_empty_note_rejected`, `tests/unit/api/test_live.py::test_unacknowledged_divergence_refused_E35`, `::test_acknowledged_divergence_proceeds`.

**T5.4 `feat(cli): complete command set and exit codes`** · `M5` `cli` · M · Blocked by: T5.7 · §3.10
- Done means: the command list of `uv run nexusbt --help` equals the 3.10 table, and `nexusbt new strategy x` makes a file that runs as is (with the liquidity threshold line visible).
- Acceptance: `tests/unit/cli/test_cli.py::test_commands_match_spec`, `::test_exit_codes`, `::test_new_strategy_runs`, `::test_new_strategy_has_visible_liquidity_filter`.

**T5.5 `feat(api): compare, runs table and html index`** · `M5` `api` · M · Blocked by: T3.14 · §3.8, §3.9
- Done means: `nx.compare(a, b)` gives same/different (data, code lines, parameters) and metric changes; `nexusbt runs --html` creates `runs/index.html`.
- Acceptance: `tests/unit/api/test_compare.py::test_code_diff_lines`, `::test_data_vs_code_vs_params`, `tests/unit/cli/test_runs.py::test_prune_keeps_counts`.

**T5.8 `feat(compat): pyfolio and alphalens adapters, evaluate signal output`** · `M5` `compat` · S · Blocked by: T3.14, T2.10a · §5.9.8, §5.8 [SC-16]
- Done means: an example in which `run.to_pyfolio()` returns three pandas objects and `report.to_alphalens()` a MultiIndex table; `evaluate(..., save_signal=True)` leaves `signal.parquet`; E18 in an environment without pandas.
- Acceptance: `tests/unit/compat/test_adapters.py::test_returns_series_shape`, `::test_pyfolio_triplet_shape`, `::test_alphalens_factor_data_shape`, `::test_no_pandas_E18`, `tests/unit/api/test_evaluate.py::test_signal_parquet_same_schema`.
- Notes:
  - decided (#43 Decisions, 2026-11-19, #251): spec 2.5's arrow `contracts ← pipeline ← compat` was decided for `compat.zipline` only; if the adapters need another module, this ticket asks the owner before adding an arrow.

**T5.22 `feat(api): Arrow PyCapsule out (zero-copy result tables)`** · `M5` `api` · S · Blocked by: T5.8 · §5.9.8 *(the input side, `from_frame` and G-105, removed 2026-11-24, #752)*
- Context: `__arrow_c_stream__` on the result table objects; the engine does not import the receiving library.
- Done means: `pl.from_arrow(run.trades)` and `pd.DataFrame.from_arrow(run.trades)` (pandas ≥ 3.0) build tables, and columns of Arrow standard types pass without copying (a buffer address comparison test).
- Acceptance: `tests/unit/api/test_pycapsule.py::test_results_export_stream`, `::test_no_import_of_frame_libs`.

**T5.9 `feat(api): Run.why from run artifacts`** · `M5` `api` · S · Blocked by: T3.19, T3.14 · §5.9.9 [SC-13]
- Done means: on a saved run, `run.why("KR:T00007", "2019-06-28")` prints the 5.9.9 shape without recomputation (computation time near 0, shown); a `save_signal=False` run gives steps 1 and 2 as a guidance sentence.
- Acceptance: `tests/unit/api/test_why.py::test_matches_explain_strategy_steps_3_to_6`, `::test_no_recompute`, `::test_signal_missing_message`.

**T5.6 `docs(examples): m5 daily paper runbook`** · `M5` `docs` · S · Blocked by: T5.4 · §8.5
- Done means: the launchd plist example in `docs/runbook-paper.md` (not installed; uses `status.json` and the exit codes) and the manual commands run as written on two synthetic snapshots (yesterday and today).
- Acceptance: `tests/docs/test_examples.py::test_runbook_paper`, `tests/docs/test_lessons.py::test_lesson[daily-watch-vs-good-day]` (the 8.5 lesson, D19, #219).

**T5.G `test(golden): trades table, book cash-flow and frame-hash cases (G-64, G-65, G-105)`** *(R6: the G-105 in-memory table hash first here — golden protection rule 8.2)* · `M5` `golden` · S · Blocked by: T0.9 · §5.9.1, §5.7, §8.2 [V31-19]
- Context: round-trip trades (long, short, open trades), TWR with ledger deposits and withdrawals. Merged before T5.13 and T5.14.
- Done means: `uv run python tests/golden/check/G-64.py` prints three lines of the trades table and the total reconciliation.
- Acceptance: `test_handcalc_self.py::test_cases_v31_M5_expected_present`.

**T5.10 `feat(api): manual overrides as book events`** · `M5` `api` · M · Blocked by: T5.3 · §3.8, §5.6.5, §5.6.7, §5.9.6
- Context: `nx.override` and `nexusbt book override`, events `override_set/cleared` (inside the transaction, definition hash unchanged), cut at the order intent step (`no_trade`/`reduce_only`/`close`), an input of the `reconcile` replay, report "manual overrides {n}".
- Done means: after `override(book, id, "no_trade")`, `live` places no orders for that instrument and `reconcile` is `yes`; a copy with the instruction removed shows the first difference at that date.
- Acceptance: `tests/unit/api/test_override.py::test_no_trade_suppresses`, `::test_reduce_only`, `::test_close_reduces_only`, `::test_definition_hash_unchanged`, `::test_reconcile_replays_overrides`, `::test_override_existing_orders_policy` (rule for pending and exit orders).

**T5.11a `feat(api): manual books - user event schema, CSV import and idempotent transactions`** · `M5` `api` · M · Blocked by: T5.3, T5.7 · §3.8, §5.9.6
- Context: `nx.book("manual:<name>")`, `nx.record_fills` (validating the CSV columns `event_kind, idempotency_key, order_ref, sheet_id, corrects, instrument_id, side, qty, price, fees, ts, note`), events `user_fill`/`user_reject`/`user_correct`/`user_trade`, one transaction, the same account accounting code; 5.9.6 rule 1 (a CSV naming a superseded sheet is refused whole, E35 names the newer sheet) and rule 2 (`corrects`, derived `superseded_by`, a corrected fill counts once, E35 for an unknown or already replaced row).
- Done means: a CSV in which 2 of 3 order-table lines fill at different prices (one line filled in two parts), 1 line is rejected, one fill is corrected and 1 trade not in the recommendation is added creates its events only once even when put in twice, and a different quantity under the same key is E35.
- Acceptance: `tests/unit/api/test_manual_book.py::test_record_fills_idempotent`, `::test_manual_partial_fill_and_rejection`, `::test_user_correct_appends`, `::test_duplicate_fill_key_conflict_rejected_E35`, `::test_user_trade_outside_recommendation`, `::test_csv_column_validation`, `::test_superseded_sheet_fills_refused_E35`, `::test_correction_chain_superseded_by`, `::test_correct_unknown_or_replaced_E35`, `tests/property/test_live.py::test_P_LIVE_superseded_sheet_refused`, `::test_P_LIVE_corrected_fill_counts_once`.

**T5.11b `feat(api): manual-book reconcile report`** · `M5` `api` · S · Blocked by: T5.11a, T5.10 · §5.9.7
- Context: the `reconcile` report of a `manual:` ledger (model targets vs actual holdings, model fill prices vs actual fill prices in bp, list of discretionary trades, instruction replay); exit code 4 not used; 5.9.6 rule 2 (the day's corrections as a count and a list) and the order-day record of 5.9.7 (5) for a `manual:` book.
- Done means: with the CSV of T5.11a, `reconcile` prints the three columns and one correction; `reconcile --day` prints the order-day record of that session.
- Acceptance: `tests/unit/api/test_manual_book.py::test_reconcile_manual_report`, `::test_manual_reconcile_exit_code_0`, `::test_reconcile_lists_day_corrections`, `::test_manual_order_day_record`.

**T5.12 `feat(api): live pre-trade sanity checks (E36)`** · `M5` `api` · M · Blocked by: T5.2 · §5.9.6, §3.9 Orders, §3.11 `[live]`
- Context: five checks (price jump and spike, maximum amount per order, selling beyond the holding and covering beyond the short, a value change that does not match the event factors, no liquidity threshold), the order table's `check` column, `status.json` `warnings`, E36, non-blocking; before the sheet, the blocking newest-data check of 5.9.6 rule 4 (per dataset the strategy reads, E19 with every short dataset, exit code 3).
- Done means: on a synthetic snapshot with the close cut to 1/100, `nexusbt live` places the orders but prints `check = price_jump` on that line and one E36 line; the newest-data case of 8.4 gives its E19 and no sheet.
- Acceptance: `tests/unit/api/test_live_checks.py::test_price_jump_flagged`, `::test_order_value_cap`, `::test_oversell_flagged`, `::test_event_value_mismatch`, `::test_liquidity_floor`, `::test_not_blocking_exit_code_0`, `::test_newest_data_per_dataset_E19`, `::test_newest_data_names_every_missing_dataset`, `::test_newest_data_event_dataset_E19_names_its_items`, `::test_newest_data_event_dataset_current_without_an_event`, `::test_newest_data_without_processed_through_E30`.

**T5.13 `feat(accounting): external cash flows and time-weighted returns in books`** · `M5` `accounting` · M · Blocked by: T5.1, T5.G · §5.6.9, §5.7, §5.9.6, INV-06 [V31-19]
- Context: `nx.cash_flow` and `nexusbt book flow`, event `external_flow` (session start), bridge `external_flows` row, TWR returns, E16 for a withdrawal beyond cash, `reconcile` replay.
- Done means: the G-65 `r_1` 0.6667% and the bridge rows are printed, and a ledger with deposits only has CAGR 0 and `account_growth` 50% (G-65 (b), v3.2).
- Acceptance: `tests/golden/test_books.py::test_G65_twr`, `tests/unit/accounting/test_flows.py::test_withdrawal_over_cash_E16`, `::test_flow_only_book_has_zero_cagr`, `::test_flow_boundary_replay_is_idempotent`, `tests/property/test_execution_invariants.py::test_P_BRIDGE_with_flows`.

**T5.14 `feat(artifacts): round-trip trades table derived from events`** · `M5` `artifacts` · M · Blocked by: T3.14, T4.15c, T5.G · §5.9.1, §3.9
- Context: `trades.parquet` (average-price basis; opened at 0 → non-0 and closed at 0, partial sells are legs, a flip is the closing part + the opening part, short trades, open trades `status = open`), exit reason, MAE and MFE (H/L after entry excluding the extremes of the entry and exit bars, "daily-bar approximation"), included in `derive_tables`, HTML "trades" column.
- Done means: the three G-64 trades come out as they are, and the HTML has the count, win rate and average holding period per exit reason.
- Acceptance: `tests/golden/test_trades.py::test_G64`, `tests/property/test_execution_invariants.py::test_P_TRADES`, `::test_P_DERIVED_includes_trades`, `tests/unit/artifacts/test_trades.py::test_flip_splits_legs`, `::test_intraday_entry_mae_excludes_entry_bar`.

**T5.15 `feat(api): screen x-ray over the whole universe`** · `M5` `api` · M · Blocked by: T3.19, T2.20, T2.21, T2.22, T5.1 · §3.8, §3.9 Screen, §5.9.9
- Context: `screen(show=…, near=)`, `Screen.xray()` (leaf Filter true/false/unknown, signal node values and percentiles, status column), CLI `--show --html`, reuse of node values without new computation.
- Done means: `uv run nexusbt screen examples/strategies/value_mom.py --show held+near --html` writes HTML with the held, buy, hold band, sell and just-missed instrument statuses and true/false per rule.
- Acceptance: `tests/unit/api/test_xray.py::test_statuses`, `::test_leaf_filters_three_valued`, `::test_no_recompute`, `::test_matches_explain_rows`, `::test_xray_without_book_does_not_invent_holdings`.

**T5.16 `feat(portfolio): strategy state record in paper books and screens`** · `M5` `portfolio` · S · Blocked by: T5.1, T5.16a · §5.5.3, §5.9.6
- Context: the ledger part of the strategy state record (the record type, its serialisation and the checkpoint are T5.16a; decision 2026-11-04, #152): writing the record and the anchor into the ledger manifest (5.9.6) at each commit, restoring it when a book is reopened, and `screen` carrying it over from a book. The recursive feature is not switched on (T7.1).
- Done means: the ledger manifest shows the anchor and the state record, and reopening a book after a commit gives the same next targets as not stopping.
- Acceptance: `tests/unit/portfolio/test_target_state.py::test_book_manifest_records_state`, `::test_book_reopen_restores_state`.

**T5.17 `feat(api): screen account modes for account-reading risk rules`** · `M5` `api` · M · Blocked by: T3.30, T5.1, T5.4 · §3.8 screen, §3.10
- Context: `screen(account="auto"|"none"|"book"|"backtest")`, CLI `--ledger BOOK` and `--as-backtest`, the not evaluated line, E42 and skips, the ledger state version and snapshot hash in the manifest, the elapsed time of `--as-backtest`.
- Done means: three screens of the same strategy, without a ledger, with `--ledger paper:demo` and with `--as-backtest`, print the same canonical targets, and `final_weight` columns that can differ only when the strategy has account-reading risk rules.
- Acceptance: `tests/golden/test_risk.py::test_G87_screen_part`, `tests/unit/api/test_screen_account.py::test_not_evaluated_line_and_E42`, `::test_ledger_reads_book_state`, `::test_as_backtest_equals_backtest_account`.

**T5.18 `feat(cli): strategy templates, demo snapshot and the 30-minute path`** · `M5` `cli` · M · Blocked by: T5.18a, T5.4, T3.34, T3.33, T5.17 · §3.10, §8.5 *(the strategy-writing trial, user decision 2026-11-03; T3.35 left Blocked by and its two event templates came here 2026-11-24, #752)*
- Context: (`init --demo` and the demo snapshot are T5.18a's) `nexusbt new strategy NAME --template T` and `--list`, 18 of the 22 templates (3.10) (`event-driven-earnings` and `macro-regime` turned on when stage (2) builds `nx.Item` (#752), and marked not yet usable until then; the other 4 in their feature tickets: validation and ML two in T6.27, zipline in T5.19, `buffer-hold` in T7.1 — `--list` marks the ones not yet usable "(available after T…)"), an output comparison test per template, `test_first_30_minutes.py` (first line `uv init quant && cd quant && uv add nexusbt`, CI uses `--find-links dist/`).
- Done means: in a clean environment the five commands (8.5, first line `uv init quant && cd quant && uv add nexusbt`) run in turn, and the PR has a record of one first-time user (chosen by the user) finishing a first backtest and a first screen within 30 minutes. **Strategy-writing trial** (R3, user decision 2026-11-03, an M5 end condition): the owner writes three strategies alone from the templates — (a) monthly KR value top-50, long only, provisional costs (`monthly-topn`); (b) 12-1 momentum long-short on KR and US with shorting on and a gross cap (`momentum-12-1`, `long-short`); (c) entry after an earnings release with a five-session time stop (`event-driven-earnings`, `nx.Item.<name>.age()`). The owner may replace any of the three before M5. Each strategy has three steps — write it from a template, change one rule, read one error — and each step is one recorded row: strategy, step, minutes, help needed (none, the docs, or a person, and what), outcome (done, or not done and why). The rows go in the M5 end evidence, and the three strategies are kept as `examples/trial/` files, each run on the synthetic `small` snapshot by `tests/docs/test_examples.py` (8.5). Each row also records whether the guide `docs/guide/choose-by-question.md` (3.10) was used and whether the owner could say what the output shows and what it cannot (8.5 use scenarios, D19, #219).
- Acceptance: `tests/docs/test_templates.py::test_template_runs`, `tests/docs/test_first_30_minutes.py::test_five_commands`, `tests/unit/cli/test_new.py::test_list_templates`, `tests/docs/test_examples.py::test_trial_strategies_run`, `tests/docs/test_scenarios.py::test_scenario[6]` (D19, #219).

**T5.19 `docs: zipline to NexusBT mapping page and zipline-port template`** · `M5` `docs` · S · Blocked by: T5.18 · §8.5
- Context: `docs/migrate-from-zipline.md` (English + Korean): what bundle, `initialize`, `handle_data`, `context`, `schedule_function`, `order_target_percent`, `attach_pipeline`, `pipeline_output`, `run_algorithm` and `CustomFactor` each become and what changes (the table of part 3 of teardown G), every code snippet `<!-- test -->` and `<!-- output -->`, the `zipline-port` template.
- Done means: the documentation page renders and the code in every NexusBT column of the table runs in tests.
- Acceptance: `tests/docs/test_examples.py::test_migrate_from_zipline`, `tests/docs/test_templates.py::test_template_runs[zipline-port]`.
- Notes:
  - decided (#43 Decisions, 2026-11-19, #587): the guide lists zipline's `outputs` as having no counterpart.
  - carried (#43 Decisions, 2026-11-19, #251): the guide says that the shim ignores `window_safe` (only E17's degree rule refuses, so a ratio `CustomFactor` without the flag passes here and is refused by zipline) and that a class setting `outputs`, `params`, `domain` or a non-default `dtype`, `missing_value` or `ndim` stops where it is defined.
  - decided (#43 Decisions, 2026-11-19, #251): the shim passes no real `today` and `assets` to `compute` until a user needs them, so the compat layer stays thin (ADR 0001).
  - carried (#43 Decisions, 2026-11-19, #587): spec 3.3 or chapter 12 says that a user function gives one value per instrument and that zipline's `outputs` is not in v1, so that it reads as a choice; put to the owner as a spec change.

**T5.20 `feat(api): compare strategy variants in one table`** · `M5` `api` · S · Blocked by: T5.5, T3.34 · §3.8 compare
- Context: `nx.compare(Strategy…)` backtests each (reusing the Pipeline) and then gives a variant table (names of the changed slots, metrics, waterfall summary, DSR (cohort)), CLI `nexusbt compare`.
- Done means: `nx.compare(base, base.replace(sizing=nx.size.erc()), base.replace(risk=[nx.risk.drawdown_brake(off=0.20, on=0.10)]))` prints a three-line table and three candidates are recorded.
- Acceptance: `tests/unit/api/test_compare.py::test_variant_table_columns`, `::test_variants_counted_as_candidates`, `::test_pipeline_values_reused`.

**T5.21 `feat(cli): commented two-tier nexusbt.toml template, config check and config show`** · `M5` `cli` · S · Blocked by: T1.2, T0.4b, T0.5a · §3.10, §3.11 [user request 2026-10-28]
- Context: `nexusbt init` writes a template commented with part 1 "check these" and part 2 "advanced" (English canonical + `--lang ko`), `nexusbt config check` (type, range and contradictions in the `layer config` format), `nexusbt config show [--all]` (resolved values + place CLI/backtest()/preset/strategy/nexusbt.toml/default, 3.11 #874, the same resolver as `load_config`), the report header block "settings (tier 1)".
- Done means: `uv run nexusbt init --lang ko && uv run nexusbt config check` prints "config ok", and with `debit_rate_bps = 300` added under `[account] type = "cash"`, `config check` gives a `layer  config` line and a fix line with exit code 1; `config show` shows the source of `capital` as `file` and `start` overridden by strategy code as `code`.
- Acceptance: `tests/docs/test_config_template.py::test_template_keys_match_3_11`, `::test_en_ko_same_keys_and_values`, `::test_example_file_keys_exist`, `tests/unit/cli/test_config_check.py::test_margin_keys_on_cash_account_E16`, `::test_contradictions_listed_with_layer_config`, `tests/unit/cli/test_config_show.py::test_source_default_file_cli_code`, `::test_show_matches_manifest_config`, `tests/golden/test_report.py::test_header_lists_tier1_values`.

#### M6 — Performance, research tools, release gate

**T6.1** → moved in v3 to **T1.24** (M1) (early measurement). The measurements of M6 use the T1.24 harness.

**T6.2 `perf(compute): numba rolling kernels bit-equal to reference`** · `M6` `compute` · M · Blocked by: T1.24, T4.7 · §5.3.3, §5.3.10, ADR-0016, ADR-0019
- Done means: a PR description with the P3 measurement recorded before and after; fast kernel = reference (bits).
- Acceptance: `tests/property/test_kernels.py::test_P_KERNEL_rolling_bit_equal`, `::test_transcendental_same_function_both_paths`, `::test_py_func_covered`, `::test_no_fastmath_no_parallel`, `::test_kernel_swap_bit_equal` (swapped only inside the seam).
- Notes:
  - owner decides at the cut (#43 Decisions, 2026-11-20, #632): whether a built-in kernel's cell whose square or product underflows to 0 (the standard deviation of `[1e-200, −1e-200]` is 0) is that small number, 0 or NaN.
  - owner decides at the cut (#43 Decisions, 2026-11-20, #632): whether `MaxDrawdown` is defined only for a positive running peak (on `[-1.0, -2.0]` it gives `-0.0`, a fall read as no drawdown).
  - owner decides at the cut (#725 Decisions 258, 2026-11-24): spec 0's "checked bit for bit against the reference implementation" and the adjustment shortcut's "relative 1e-12" (INV-11, 5.3.3) disagree; the owner settles which promise holds after the first measurement.

**T6.3 `perf(compute): numba cross-sectional kernels`** · `M6` `compute` · M · Blocked by: T6.2 · §5.4, §5.3.10
- Done means: P2 and P3 measurements before and after.
- Acceptance: `tests/property/test_kernels.py::test_P_KERNEL_crosssection_bit_equal`.

**T6.12 `feat(data): L0 raw block cache with memory mapping`** · `M6` `data` · M · Blocked by: T1.24, T1.4 · §5.3.9 L0, §7 P7 [SC-15]
- Done means: prints that block read time dropped on the second run of the same screen (L0 hit); deleting the L0 folder leaves the result bit-identical; `nexusbt doctor` shows the L0 size.
- Acceptance: `tests/property/test_cache.py::test_P_CACHE_L0`, `::test_P_CACHE_INCR` (on a new snapshot where only the last year changed, past partitions hit and an old correction misses; 2026-11-04: the axis cases and the L1 cases of 8.3, an L1 hit rate > 0 after tomorrow's session is added), `tests/unit/data/test_l0.py::test_readonly_mmap`, `::test_key_changes_with_partition_file_sha256`, `::test_intermediate_action_revision_invalidates`, `::test_terms_availability_only_change_invalidates`, `::test_axis_row_changes_miss_only_the_table_years`, `::test_watermark_change_keeps_l0_hits`, `::test_bad_advisory_value_hash_never_reuses_wrong_block`, `::test_l0_shared_entry_survives_old_snapshot_removal`, `::test_l0_identity_mismatch_rehashes`.
- Notes:
  - owner decides at the cut (#725 Decisions 151, 2026-11-23): whether the L0 cache key moves from a partition's file sha256 to its partition value hash (5.3.9, ADR 0025).
  - builder's choice (#43 Decisions, 2026-11-19, #233, #450 and #451; recommended: extend the T1.1b test with the L0 half, because one test then holds both halves): `test_inplace_edit_invalidates_stamp_and_l0` checks the stamp half only; this ticket extends it with the L0 half or says that `test_l0_identity_mismatch_rehashes` is that half.

**T6.4 `feat(compute): semantic term cache (L1)`** · `M6` `compute` · M · Blocked by: T6.2 · §5.3.9
- Done means: the second run of the same evaluate is within the P3 cache target (time printed); deleting the cache folder leaves the result the same; a snapshot with only `availability` changed and a function with only `THRESHOLD` changed do not use the cache.
- Acceptance: `tests/property/test_cache.py::test_P_CACHE`, `::test_key_changes_with_resolution_metadata`, `::test_key_changes_with_policy` (2026-11-04: was `::test_key_changes_with_policy_and_calendar`; the L1 key has no calendar version), `::test_l1_key_has_no_axis_file_hash` (2026-11-04: a new `calendar_sessions` row outside the input row set leaves the key unchanged, and so does a new `instruments` row for a node that reads only the fields the L0 key hashes; a node that reads `Meta.category` changes key), `::test_l1_key_first_session_ord_for_absolute_schedule` (2026-11-04: a node that reads the absolute `session_ord` changes key when an earlier year gains a session), `::test_captured_scalar_changes_key`, `::test_nonconst_global_disables_l1`, `::test_external_input_hash_in_key`, `::test_atomic_write`, `::test_budget_counts_L0_and_L1`, `::test_l1_key_from_input_l0_keys`, `::test_january_nested_window_depends_on_prior_year`, `::test_partial_l1_coverage_cannot_satisfy_missing_rows`, `::test_validity_mask_cache_roundtrip`, `::test_l1_learning_context_keys_learned_node_and_downstream` (2026-11-04: `fit_id`, seed and pretrained identity change the key of a learned node and its downstream, and not of a node without a learned input).
- Notes:
  - builder's choice (#43 Decisions, 2026-11-04, #190 and #184; recommended: a row rule like the axis tables, because otherwise every L1 entry of such a node misses each day): a daily snapshot that rewrites the datasets without year partitions makes every L1 entry of a node that reads one miss each day; this ticket gives them a row rule, or P2b's warm `screen` states that such nodes are recomputed (also T6.11).

**T6.5 `feat(compute): process-tree memory budget, bounded workers and parallel scenarios`** · `M6` `compute` · M · Blocked by: T6.4 · §5.3.8
- Done means: with `memory_budget_gb=1`, `workers=2`, the P5-small process-tree RSS total is printed near 1 GB and the result is the same; scenario result order and values are the same.
- Acceptance: `tests/property/test_pipeline_invariants.py::test_P_CHUNK_budget`, `tests/perf/test_smoke.py::test_rss_bounded`, `tests/unit/compute/test_workers.py::test_parallel_scenarios_identical`.
- Notes:
  - carried (#43 Decisions, 2026-11-17, #240 and #497): 5.3.8's E16 sentence is not what `compute._chunks.spans` does (it raises when one session row with its lookback rows does not fit); the same edit says whether `memory_budget_gb` is 10^9 bytes, as the code reads it, or 2^30, and what the estimate's `+ 2` covers; put to the owner as a spec change.

**T6.6 `perf(execution): numba session step over the columnar state (conditional)`** · `M6` `execution` · M · Blocked by: T1.24, T3.18, T4.7 · §5.6, §7 *(conditional — only when the M3a and M4 measurements put most of P5's time in the session step and the owner judges P5 too slow to use (since 2026-11-24 there is no P5 gate, ADR 0054); otherwise this ticket is closed as "not needed by measurement")*
- Done means: P5 measurement before and after, every golden unchanged (`@njit` over the column-array state, data structures not changed).
- Acceptance: `tests/property/test_kernels.py::test_fast_step_equals_reference`.

**T6.7 `feat(api): sweep with shared graph and candidate matrix`** · `M6` `api` · M · Blocked by: T6.4 · §3.8 sweep, §6.3
- Done means: `uv run nexusbt sweep examples/strategies/value_mom.py` prints the candidate table and `candidates.parquet` is created.
- Acceptance: `tests/unit/api/test_sweep.py::test_shared_nodes_computed_once`, `::test_candidates_registered`.

**T6.14 `feat(api): capacity scenario`** · `M6` `api` · S · Blocked by: T6.7, T6.5 · §3.8, §5.7 [SC-06, OQ-4]
- Done means: `backtest(..., scenarios=[..., "capacity"])` prints ×10 and ×100 CAGR, the share capped, the average participation rate and a "cap binds at ≈ K" line; switched on automatically in the `sweep` final candidate report; under the default profile `provisional` the result says that the cost per unit traded (its bp) does not grow with order size and the limit shows only through the volume caps (5.7; #764, decision 2026-11-25).
- Acceptance: `tests/unit/api/test_capacity.py::test_capacity_rows`, `::test_binds_at_definition`, `::test_sweep_final_candidates_have_capacity`.
- Notes:
  - owner decides at the cut (#43 Decisions, outside review of 2026-11-03): whether the capacity scenario gives days to liquidate.

**T6.8 `feat(research): PSR, DSR and PBO via CSCV over cohorts`** · `M6` `research` · M · Blocked by: T6.7, T2.9 · §5.7, §6.3
- Done means: a PBO line in the sweep output, a DSR line in backtest (N, V[SR] source = cohort, `cohort_sha256`); "n/a (reason)" when inputs are insufficient (the 6.3 list). (2026-11-04, #197) the hygiene section's `ρ1…ρ10` band, the 5.7 label "IID-based: dependence visible (Ljung–Box lags 1–10, p < 0.05; may also reflect changing volatility)" on the PSR line when that test has p < 0.05, MinTRL against SR*_N when N > 1, and "not supported in v1" for a reality-check request.
- Acceptance: `tests/property/test_stats.py::test_P_STAT_psr_dsr_known`, `::test_pbo_hand_matrix`, `::test_invalid_population_na`, `::test_dsr_uses_frozen_cohort`, `::test_pbo_zero_variance_rule`, `::test_psr_raw_kurtosis_convention` (G-60), `::test_pbo_common_dates_with_unequal_lookbacks`, `::test_purge_keeps_max_end_available`, `::test_iid_label_when_dependence_visible` (an AR(2) series with ρ1 = 0 is marked), `::test_mintrl_selection_adjusted_reference`, `::test_reality_check_not_supported` (2026-11-04, #197), `tests/docs/test_tool_cards.py::test_card[psr]`, `::test_card[dsr]`, `::test_card[pbo]` (D19, #219).

**T6.9 `feat(research): truncation probes with prioritized dates and coverage report`** · `M6` `research` · M · Blocked by: T6.4 · §6.5 [SC-05]
- Done means: for a function that takes the whole-period array of the snapshot through a closure, `nx.check(f, probes=4)` prints E1 and the limits paragraph, "nodes compared x/y", "finite cells a/b" and the date reasons; a function that uses `np.roll` only inside the window has no E1.
- Acceptance: `tests/unit/test_leaks.py::test_probe_catches_injected_future_reader`, `::test_bounded_roll_not_flagged`, `::test_probe_clean_function_passes`, `::test_probe_cached_per_graph`, `::test_probe_date_priority`, `::test_probe_coverage_report`.

**T6.13 `feat(research): start-date probe in nx.check`** · `M6` `research` · S · Blocked by: T6.9 · §6.5 start-date probe [SC-04]
- Done means: for a user function that uses a global cumulative value, `nx.check(f, start_probe=True)` prints E32 and the lowest node; a clean function passes.
- Acceptance: `tests/unit/test_leaks.py::test_start_probe_catches_global_state_E32`, `::test_start_probe_clean_passes`, `::test_start_probe_skips_targets_with_recursion`.

**T6.10 `feat(api): progress display for long work`** · `M6` `api` · S · Blocked by: T6.5 · R-41
- Done means: in a backtest longer than 2 seconds, a line on standard error with phase, date and remaining time (probes, scenarios and capacity separately, by phase name).
- Acceptance: `tests/unit/api/test_progress.py::test_progress_after_2s`.

**T6.11 `perf: compute-host gate run and evidence`** · `M6` `bench` · S · Blocked by: T6.3, T6.5, T6.8, T6.12, T6.26 (and T6.6 if it was done) · §7 — **run by the user on the compute machine**
- Done means: `bench/results/<date>-<sha>-<machine>.json` (summary only; `<machine>` a short label of the measuring machine's kind such as `8gb`, never a host name, 2.7; until 2026-11-24 this was `-m4`) is committed, the PR has a table of every workload's p50/p95 and USS beside the earlier measurement, with an alert for each worse one (chapter 7, "What the numbers mean"), and the P11 (a)(b)(c) results are reported against their first numbers. Together with the time and hit rate of workload P2b (yesterday's cache + screen on today's snapshot) and the two values with column chunking on/off. P2b hit rate > 0 (the watermark is not in the key, v3.2). An alerted item gets a bottleneck profile, and the regression is fixed (a rewrite in Rust follows ADR 0054's trigger only). (#270) A run of the `ml-factor` example reports its `fits` block, and the PR says whether the sum of `hash_seconds` exceeds 10% of the sum of `fit_seconds` (the fallback trigger of 5.3.11 Cost).
- Acceptance: `tests/unit/bench/test_results_present.py::test_measurement_file_for_release`.
- Notes:
  - owner decides at the cut (#752 Decisions, 2026-11-25): an alert's tolerance and what a measurement is compared with are set at the first measurement from the spread of repeated runs on one machine (20% the starting proposal), and whether to compare with chapter 7's reference number as well as with the previous measurement.

**T6.15 `chore(release): clean-install gate, independent producer acceptance, changelog and contributor docs`** · `M6` `release` · M · Blocked by: T2.17, T4.11, T5.4 · §2.3, §9.1 `engine / release`, R-70
- Context: `tests/repo/release_check.py` (installs only the two wheels in a clean virtual environment outside the working folder → runs the English quick start and the public examples), the independent producer test package `tds/conformance/producers/csv-minimal` (made in T1.22) and a hand-written second producer package passing `full` + the consumption test, `CHANGELOG.md` (engine and TDS separate), the bodies of `CONTRIBUTING.md` and `SECURITY.md`, the compatibility policy paragraph (TDS chapter 10 and the engine version rules), the condition sentence for the "KR/US verified" claim (only when a summary of real-data evidence exists). In the release evidence `release_evidence.json`, the list of applied rules (source, boundary, `verified`), the number of `verified = false` rows and the `off_grid_bar` numerator/denominator; the independent producer example ids in the TDS K1 recommended format `XNAS:AAPL_19801212`.
- Done means: `uv run python -m tests.repo.release_check` prints "clean install ok · quickstart ok · producers 2/2 full pass".
- Acceptance: `tests/repo/test_release.py::test_clean_wheel_runs_example`, `::test_ml_extra_runs_ml_example`, `::test_independent_producer_package_passes`, `::test_changelogs_present`, `::test_release_market_rules_have_verified_coverage`, `::test_k1_example_ids_valid`.

**T6.16 `ci(release): trusted-publishing workflow (dry run until the user decides)`** · `M6` `infra` · S · Blocked by: T6.15 · §2.1 — **pushed by the user** (workflow permission)
- Context: builds wheels and sdists on tags `v*` and `tds-v*` and does a dry run to TestPyPI; real PyPI publishing is switched on by the user after the chapter 12 OI-44 decision.
- Done means: the tag dry-run log shows a simulated upload of the two distributions.
- Acceptance: the workflow log (manual verification checklist).

**T6.17 `test(bridge): capability errors for reserved extension points`** · `M6` `bridge` · S · Blocked by: T0.4 · §11
- Done means: `nx.backtest(..., engine="nautilus")` and a strategy that, by the `Capabilities` comparison, requires a missing feature (intraday sequence, etc.) are E18 before the run.
- Acceptance: `tests/unit/bridge/test_capabilities.py::test_reserved_backends_E18`, `::test_capability_mismatch_E18`, `::test_backend_protocol_emits_fill_events_only`.

**T6.18 `feat(api): rebalance-date luck offsets and rolling-window table`** · `M6` `api` · M · Blocked by: T6.4, T4.12 · §3.8, §5.7, §6.2, §3.11 `[report]`
- Context: `backtest(offsets=k)` (the same Pipeline values; only the targets and the state machine again), `offsets.parquet`, a first-screen line, outside the attempt count and the cohort, HTML "rolling" (excess return quantiles over 1-year and 3-year windows).
- Done means: `uv run nexusbt backtest examples/strategies/mom_kr.py --offsets 5` prints "rebalance-date luck 5 offsets · CAGR min/median/max" and the elapsed time, and the study's candidate count is unchanged.
- Acceptance: `tests/unit/api/test_offsets.py::test_reuses_pipeline_values`, `::test_not_counted_as_candidates`, `::test_schedule_offsets_per_kind`, `tests/unit/research/test_rolling.py::test_rolling_excess_quantiles`, `tests/docs/test_tool_cards.py::test_card[offsets]` (D19, #219).

**T6.Gv `test(golden): validation, ML window, triple-barrier and pretrained-cutoff cases (G-88..G-93, G-106, G-116, G-126)`** *(R6: the G-106 pretrained cutoff first here)* *(2026-11-04: G-116, strict and approximate IS scores, #215)* · `M6` `golden` · M · Blocked by: T0.9 · §5.3.11, §5.8, §6.3a, §8.2
- Context: hand-calculated cases of split counting, purge and embargo (the label of a late-published delisting), chained account / fresh capital, the ML training window, and the four triple-barrier cases. Merged before the implementation PR.
- Done means: `uv run python tests/golden/check/G-89.py` prints the purged and embargoed samples per fold.
- Acceptance: `tests/golden/test_handcalc_self.py::test_case_G88_to_G93_expected_present`, `::test_case_G116_expected_present` (#215), `::test_case_G126_expected_present` (#873).
- Notes:
  - owner decides at the cut (#314 Findings, 2026-11-06; #314 Decision, 2026-11-10): whether an AR(1) closed-form correction of PSR and MinTRL comes as one diagnostic row, if this ticket can hand-compute it in a case, or stays a 12.1 row.

**T6.19 `feat(research): split value objects with label-availability purge and AFML embargo`** · `M6` `research` · M · Blocked by: T2.9, T6.Gv · §6.3a, §5.8
- Context: `nx.splits.holdout`, `walk_forward`, `cpcv`, `cscv`, `Split` (folds, paths, `split_hash`, `plot()`, `summary()`), purge (label interval = up to the availability time) and embargo, `n_purged` and `n_embargoed`, parsing of length strings.
- Done means: `nx.splits.cpcv(6, 2).summary()` prints 15 splits, 5 paths and the group table.
- Acceptance: `tests/golden/test_validation.py::test_G88`, `::test_G89`, `tests/property/test_validation.py::test_P_SPLIT_DET`, `tests/unit/research/test_splits.py::test_wf_step_less_than_test_E16`, `::test_embargo_differs_from_embargo_sessions`.

**T6.20 `feat(api): backtest(method="walk_forward") with a chained account, fold selection and linear side by side`** · `M6` `api` · M · Blocked by: T6.19, T6.7, T3.13a · §3.8, §6.3a, §6.2
- Context: `backtest(method=…, grid=, select=)`, CLI `--method`, `--method-opt` and `--grid`, IS selection on the fold's training data (for each grid point, the daily returns of one linear run over all of D are sliced to the training holding periods, purged and embargoed; sample counts in `selection.parquet`), `step == test` when chained (E16), comparison baseline `backtest(start=t_1)` (P-WF-STITCH), period shown on the linear line, one chained account (holdings, pending orders, exits, `risk_state`), diagnostic `account="per_fold"`, a linear run alongside, `Run.validation` and the `validation/` folder, counting (fold diagnostics, grid points as candidates).
- Done means: `uv run nexusbt backtest examples/strategies/value_mom.py --method walk_forward --grid n=10,20,30` prints the `primary` and `reference` lines (3.9, #216) and the fold table (chosen n, IS/OOS Sharpe), and the candidate count grows by the number of grid points.
- Acceptance: `tests/golden/test_validation.py::test_G90`, `::test_G126_select_under_one_year_and_E50` (#873), `tests/property/test_validation.py::test_P_WF_STITCH`, `tests/unit/api/test_method.py::test_folds_not_counted`, `::test_is_returns_sliced_from_full_run`, `::test_step_not_equal_test_E16`, `::test_linear_run_alongside`, `::test_scenarios_only_on_linear`, `tests/docs/test_tool_cards.py::test_card[walk-forward]` (D19, #219), `tests/unit/api/test_method.py::test_primary_and_reference_in_run_and_metrics_json` (no existing field changes meaning; 6.3a, #216).

**T6.21 `feat(research): CPCV paths with fresh capital per path, CSCV and sweep as a shorthand`** · `M6` `research` · M · Blocked by: T6.20, T6.8 · §6.3a, §6.3
- Context: per path, `TargetFrame` concatenation and a fresh-capital state machine, the path distribution, CPCV PBO (OOS rank of the IS best), `method="cscv"` = the 6.3 procedure, `sweep` = shorthand for `backtest(method="cscv", grid=)` (`SweepResult` compatible), E40 for a CPCV with nothing to select, the `[validate] max_fits` advance notice. (2026-11-04, #215) `splits.cpcv(is_scores=)` and `ValidationResult.is_scores`: the slice for a `grid` with no learned node (`slice`), the strict replay of each contiguous training block as its own account (6.3a rules 2 to 5; asked for explicitly here, since the learned node comes with T6.24), `selection.parquet.is_scores` and `n_blocks`, the mode and the planned passes in the E40 notice.
- Done means: `--method cpcv` prints the Sharpe distribution of 5 paths and the worst MDD on the `primary` line above the linear `reference` line (3.9, #216), and PBO (numerator/denominator).
- Acceptance: `tests/golden/test_validation.py::test_G91`, `tests/unit/research/test_cpcv.py::test_path_count_and_fresh_capital`, `::test_nothing_to_select_E40_one_path`, `::test_path_interpretation_line`, `tests/unit/api/test_sweep.py::test_sweep_equals_cscv_method`, `tests/docs/test_tool_cards.py::test_card[cpcv]` (D19, #219), `tests/unit/research/test_cpcv.py::test_best_path_never_representative` (6.3a, #216), `::test_is_scores_slice_without_learned_node`, `::test_strict_block_replay_equals_fresh_linear_run` (an empty book and K at each block start, entry costs in the IS returns, nothing charged at a block end), `::test_is_scores_without_grid_E16`, `::test_E40_names_is_scores_mode_and_planned_passes` (6.3a, #215).
- Notes:
  - owner decides at the cut (#314 Decision, 2026-11-10): which PBO warning lines print beside PBO (also T6.8). The builder's recommendation (#314 Findings) is two lines, warnings only, the probability of OOS loss (the share of combinations where the IS-best candidate's OOS Sharpe is below 0) and "N < 10 candidates: PBO is coarse", because with few candidates the logit distribution is degenerate.
  - owner decides at the cut (#43 Decisions, 2026-11-04, #202): whether a CPCV path's DSR may take V[SR] from the cohort's linear observations, and 6.3a says so (also T6.8).
  - owner decides at the cut (#43 Decisions, 2026-11-04, #205): whether stage B of `docs/design/statistics-verification-plan.md` becomes 8.3 property rows (the same DGPs as synthetic packages run through `evaluate` and `backtest(method=…)`), and which tickets test them (also T6.8 and T6.24).

**T6.22 `feat(report): hygiene panel on the first screen and ValidationResult report`** · `M6` `report` · S · Blocked by: T6.21, T2.10b · §6.3a report, §3.9
- Context: seven lines in the first-screen hygiene panel (attempt line, DSR/PSR/MinTRL, path band, PBO and slope, selection stability, leak ledger, pre-registration), the numerator/denominator rule, `ValidationResult.report()`.
- Done means: the first screen of report.html has the seven lines and no badges (structure test).
- Acceptance: `tests/unit/artifacts/test_report.py::test_hygiene_panel_lines`, `::test_ratios_have_counts`, `::test_no_pass_badges`, `tests/docs/test_tool_cards.py::test_report_explanations_match_cards` (D19, #219), `tests/unit/artifacts/test_report.py::test_primary_and_reference_lines`, `::test_failure_markers_not_nan`, `::test_csv_rows_carry_role` (6.3a, #216), `::test_is_scores_line` (the `IS scores` line in its four forms, with the assumption sentence unless strict, and no line for `cscv` or with no `grid`; 3.9, #215).
- Notes:
  - decided (#314 Decision, 2026-11-10): `N + m` is not a calibrated independent-trial count and is never silently fed to DSR (6.2).
  - owner decides at the cut (#314 Decision, 2026-11-10): how a composite signal built from evaluated factors counts as attempts (also T6.8). The builder's recommendation (#314 Findings) is that the hygiene line prints "candidates N = n; factors this graph reads that were evaluated in this family: k of m" and DSR at N and at N + m with the larger deflation first, with no new N rule, because the selection events already record it, and that a factor evaluated outside the family reads as 6.2 already labels it.

**T6.23 `feat(ml): ml.factor node with engine-enforced training window and fit/predict records`** · `M6` `ml` · M · Blocked by: T6.19, T2.10a, T1.12 · §5.3.11, §6.5 check 8
- Context: the `MLFactor` node, sample construction, `train=rolling|expanding`, the `refit` schedule, the training window rule (availability time + embargo ≤ τ), the E2 port, training a new object (2026-11-04, #195: a factory, `__sklearn_clone__` or `clone`, E16 otherwise), class probabilities matched by `classes_` and the required `score=` for three classes, a one-class training window not fitted (`ml_single_class`), fixed seed and threads, `fit_id` reuse, `predictions.parquet`, `fits.parquet` and manifest `ml`, sklearn as an optional dependency (no engine import).
- Done means: evaluate of the `ml-factor` example prints the IC table and "fits 24 · samples min 1,830", and there is no model file.
- Acceptance: `tests/golden/test_ml.py::test_G92`, `tests/property/test_ml.py::test_P_ML_REPRO`, `tests/unit/ml/test_factor.py::test_label_port_only_E2`, `::test_no_pickle_files`, `::test_engine_does_not_import_sklearn`, `::test_seed_from_run_seed_and_fit_id`, `::test_new_model_per_fit_factory_and_clone`, `::test_uncloneable_model_E16`, `::test_score_by_class_value_not_column`, `::test_three_classes_need_score_E16`, `::test_single_class_window_not_fitted`, `tests/unit/ml/test_sklearn_pipeline.py::test_pipeline_fit_ignores_held_out_features` (with `nexusbt[ml]`: a scaler and a model in one `Pipeline`; changing the features of decisions outside the training samples leaves the scaler's learned means the same, and no two fits share a step object), `tests/unit/ml/test_factor.py::test_provenance_level_per_fit_and_manifest_counts` (#216), `tests/property/test_ml.py::test_P_FUT_ml_fit_id` (rows added after τ in the same year partition: the same `fit_id`, seed, predictions and targets at or before τ), `tests/unit/ml/test_factor.py::test_corrected_training_value_new_fit_id` (a new `fit_id`, no reuse; predictions not compared), `::test_hash_seconds_beside_fit_seconds` (#270).
- Notes:
  - carried (#43 Decisions, 2026-11-20, #250): 5.9.4's "tier (3) was not compared" line and `--save-detail` are not built (`nexusbt rerun --save-detail` raises `NotImplementedError`); the ticket whose run kind first writes `detail/` adds both (also T6.24).

**T6.24 `feat(ml): ml.factor inside method folds, rerun refit hash check and determinism warnings`** · `M6` `ml` · S · Blocked by: T6.23, T6.21, T1.15 · §5.3.11, §6.3a
- Context: forward-only training in every method (no samples after τ; CPCV excludes that split's test blocks, purge and embargo; walk-forward does not cut to the fold range), the leak ledger line `ml fits: forward-only`, E29 for a setting that can overlap, `rerun` refit `pred_sha256` comparison (E15/tolerance), E44, reuse of the same `fit_id` (WF overlap, the same CPCV combination).
- Done means: running an ML strategy with `--method cpcv` prints the number of fits and of reuses, and `rerun` prints "predictions identical (n fits)". (2026-11-04, #197) `evaluate` of a classification factor prints the log-loss and Brier line of 5.7 with scored/total.
- Acceptance: `tests/unit/ml/test_folds.py::test_forward_only_in_every_method`, `::test_cpcv_excludes_test_groups`, `::test_overlap_setting_E29`, `tests/unit/api/test_rerun.py::test_ml_refit_hash_equal`, `::test_threads_warning_E44`, `tests/property/test_cache.py::test_P_CACHE_FIT` (2026-11-04: CPCV combinations and `run_seed` never share a learned L1 entry, cache on = off; #270: cold and warm give the same `fit_id`), `tests/unit/ml/test_scoring.py::test_multiclass_log_loss_over_declared_classes`, `::test_brier_on_chosen_score`, `::test_training_decision_not_scored` (2026-11-04, #197), `tests/docs/test_tool_cards.py::test_card[log-loss-brier]` (D19, #219), `tests/unit/ml/test_scoring.py::test_predict_proba_contract` (shape, [0, 1], row sums, duplicate `classes_` → E41; #310), `tests/unit/ml/test_folds.py::test_provenance_level_by_fold_use` (5.3.11, #216), `::test_online_refit_labelled`, `tests/property/test_validation.py::test_P_INCOMPLETE` (6.3a, #216; both need an ML factor inside folds), `tests/golden/test_validation.py::test_G116`, `tests/property/test_validation.py::test_P_IS_STRICT` (held-out labels, no carried account state, a later market feature from test-period prices still changes), `tests/unit/ml/test_folds.py::test_is_scores_strict_by_default_with_learned_node_and_grid`, `::test_approximate_is_labelled_and_caps_provenance_level`, `::test_strict_fits_counted_in_E40` (6.3a, 5.3.11, #215).
- Notes:
  - decided (#43 Decisions, 2026-11-18, #315): `nx.ml.factor(..., label_norm=)` normalises per decision date over a fit's own training samples, thin dates left out and counted, with no `feature_norm=`; the edit reaches 5.3.11, 3.8's signature, 6.3a, 12.1 V31-43 and this ticket's and T6.Gv's tests, and this ticket settles the partly present date. Put to the owner as a spec change.

**T6.24b `feat(ml): pretrained predict-only models with training cutoff leak guard`** · `M6` `ml` · S · Blocked by: T6.24, T6.Gv · §5.3.11, §6.2, §6.6
- Context: `nx.ml.pretrained(model, training_cutoff=, corpus=, allow_overlap=)`, `predict` only, decisions before cutoff + embargo E48 (failure), `allow_overlap` marked E49, report line, manifest assumption, validation path marking, model identity in `fit_id`, counted as a candidate.
- Done means: with a fake pretrained model (a fixed prediction function) the G-106 numbers (24 blocked, denominator 84) are printed, and the report header of an `allow_overlap=True` run shows the overlap line.
- Acceptance: `tests/golden/test_ml.py::test_G106`, `tests/unit/ml/test_pretrained.py::test_cutoff_required_E16`, `::test_leak_E48`, `::test_overlap_marked_E49`, `::test_counted_as_candidate`.

**T6.25 `feat(research): triple-barrier label sharing the exit fill rule`** · `M6` `research` · S · Blocked by: T3.33, T2.10a, T6.Gv · §5.8, §3.7 exits
- Context: `labels.triple_barrier(take_profit, stop_loss, max_sessions)`, reuse of the 5.6.4 decision function and the `time_stop` session count, `tb_ret` and `tb_side`, a different end time per label and purge, delisting terminal value.
- Done means: `nx.evaluate(f, target=nx.labels.triple_barrier(take_profit=0.05, stop_loss=0.03, max_sessions=10))` prints the IC and counts per barrier (upper/lower/time).
- Acceptance: `tests/golden/test_labels.py::test_G93`, `tests/unit/research/test_triple_barrier.py::test_same_fill_function_as_exits`, `::test_label_end_varies_and_purges`, `::test_dividend_on_end_session_is_cash` (2026-11-04: a barrier exit inside the ex-date bar adds the right as cash and reads no later price of that bar), `::test_time_exit_next_open_matches_time_stop` (#195: with `time_exit="next_open"`, `tb_ret` equals the zero-cost 1-share return of a strategy with the same `exits`, G-93 (e)).
- Notes:
  - owner decides at the cut (#43 Decisions, 2026-11-04, #201 and #200): whether a cash dividend moves a triple-barrier path's barriers (5.6.2a resizes for splits, consolidations and stock-dividend unlocks and is silent on cash dividends); the golden ticket adds the hand case for a barrier exit inside the ex-date bar (also T6.Gv).
  - carried (#752 Decisions, 2026-11-26): no engine code raises E2 `LabelLeakError` since `Panel` left; it returns with `labels.triple_barrier` (6.5).

**T6.26 `perf: P11 high-dimensional workload with decision-date-only evaluation, column pruning and batched reductions`** · `M6` `bench` · M · Blocked by: T2.24, T6.4, T6.5 · §7 P11, §5.3.2, §5.3.8 *(the generator and the fixture moved to T2.24 [#175])*
- Context: on the generator and `bench/fixtures/p11.json` of T2.24, computing decision rows only (row mask propagated backwards), column pruning, `evaluate` reduced per decision (the full value matrix is not held), one matrix per decision for the composite score, parallel by (market, year, node group); measurement JSON (time, USS, bytes read, decision rows, shared nodes).
- Done means: `uv run python bench/run.py --workload P11 --fixture bench/fixtures/p11.json --snapshot synth-full-0001` prints the (a)(b)(c) times, per-stage times, USS, `fixture_sha256` and the output value hash (both cold and warm, same hash), and the measured first numbers are written beside the targets (a measurement prototype; by the user on the measuring machine; no gate since 2026-11-24, ADR 0054).
- Acceptance: `tests/perf/test_p11_smoke.py::test_small_p11_runs_and_reports`, `tests/property/test_pipeline_invariants.py::test_decision_rows_only_equals_full`, `tests/unit/compute/test_memory.py::test_evaluate_does_not_hold_full_matrix`, `tests/perf/test_p11_smoke.py::test_cold_warm_output_hash_equal`.

**T6.27 `docs(examples): walk-forward/CPCV and ML factor templates`** · `M6` `docs` · S · Blocked by: T6.24, T5.18, T6.8, T6.9, T6.20, T6.21, T6.24b, T6.22 · §3.10 templates, §8.5 *(2026-11-04: the four M6 lessons and use scenarios 3, 4, 7, 8 and 9 of 8.5, D19, #219)*
- Context: the templates `walk-forward-cpcv` and `ml-factor` (a linear model for tests when the optional sklearn dependency is absent), output comparison; the 8.5 lessons `leaky-training`, `best-of-many`, `preprocessing-window` and `periodic-reselection` (script, page in English and Korean, decision-date table per split).
- Done means: both templates run under `init --demo` and their output blocks are the same; each of the four lessons runs on the synthetic `small` snapshot with its seed, prints the engine signals of its 8.5 row, and its page states the assumptions, seed, data and expected observation next to the output; use scenarios 3, 4, 7, 8 and 9 of 8.5 pass.
- Acceptance: `tests/docs/test_templates.py::test_template_runs[walk-forward-cpcv]`, `::test_template_runs[ml-factor]`, `tests/docs/test_lessons.py::test_lesson[leaky-training]`, `::test_lesson[best-of-many]`, `::test_lesson[preprocessing-window]`, `::test_lesson[periodic-reselection]`, `tests/docs/test_scenarios.py::test_scenario[3]`, `::test_scenario[4]` (the invariance up to the first moment a changed label is usable for training, embargo included, both halves; 6.3a, #271), `::test_scenario[7]` (strict by default and the `approximate` line; #215), `::test_scenario[8]`, `::test_scenario[9]`.

**T7.G `test(golden): hold-band edge cases (G-63)`** · `M6 (before T7.1)` `golden` · S · Blocked by: T0.9 · §5.5.3, §8.2
- Context: keeping on a missing score and the consecutive cap, skipping the buy of a hold band instrument with zero holding, one mirror case on the short side (`bottom(hold=)`). Merged before T7.1.
- Done means: `uv run python tests/golden/check/G-63.py` prints the target set, reasons and orders per decision.
- Acceptance: `test_handcalc_self.py::test_case_G63_expected_present`.

**T7.1 `feat(portfolio): target-state recursion and hold band`** · `M6 (last ticket, included in v1 — user 2026-10-28)` `portfolio` · M · Blocked by: T6.11, T6.18, T7.G, T4.14, T5.16, T6.22, T6.24, T6.25, T6.27 · §5.5.3 [SC-02, OQ-1]
- Context: implementation of `top(n, hold=m)` and `bottom(n, hold=m)`, `on_missing` and `max_missing_decisions`, `band_entries` at the execution step (`order_suppressed(band_entry)`), anchor (backtest, screen `anchor`, live ledger), passing `prior`/`target_state`, screen carrying over from the `targets.parquet` of a run on the same snapshot, the report anchor line, "count of differences between target set and holding set".
- Place: set again when stage (2) cuts its tickets (#725 Decisions 244); until then this entry keeps its place in the ticket graph.
- Done means: the turnover of a `hold=20, n=10` strategy is printed lower than with `hold=None`, and with the same anchor, screen targets = backtest targets.
- Acceptance: `tests/unit/portfolio/test_hold_band.py::test_keep_within_m`, `::test_fill_to_n_by_rank`, `::test_anchor_screen_equals_backtest`, `::test_missing_score_drop_default`, `::test_missing_score_hold`, `::test_bottom_hold_mirrors`, `tests/golden/test_portfolio.py::test_G63_band_edges`, `tests/property/test_execution_invariants.py::test_P_PARITY13_with_hold`, `tests/unit/portfolio/test_hold_band.py::test_held_missing_weight_uses_median_u`, `::test_hold_equals_n_keeps_missing_score`, `tests/docs/test_templates.py::test_template_runs[buffer-hold]`.

**T7.V `verify: post-T7.1 release re-verification (no features)`** · `M6 (verification step after T7.1, not a feature)` `release` · S · Blocked by: T7.1 · §7, §8, §9.1 `engine / release`, R-70
- Context: after T7.1 changes the target path, the release gates are run again: `engine / release` (clean install, quick start, independent producers), all of comparison L1 and L2, P-SHORT-OFF (differential + baseline), the property `deep` profile, the chapter 7 measurements, compared with the earlier ones (by the user on the measuring machine), rule verification evidence. No new features or spec changes (on failure, the ticket that caused it is reopened).
- Done means: `uv run python -m tests.repo.release_check --all` prints "release gate after T7.1: pass" and the pass count of each block, and the performance JSON is committed.
- Acceptance: `tests/repo/test_release.py::test_release_rerun_after_last_feature`.
- Notes:
  - carried (#43 Decisions, 2026-11-19, #252 and #612): spec 8.1's L1-b row names reverse splits; the compared range of the synthetic `small` package holds one in KR (KR:T00042) and none in US.

**T6.28 `perf: re-measure chapter 7 on a real snapshot (summary evidence)`** **[2026-11-11, #162]** · `M6 (release evidence after T7.V, not a feature)` `bench` · S · Blocked by: T7.V, T6.15 · §7, §2.7, chapter 12 OI-46 — **run by the user on the compute machine**
- Context: the public half of OI-46's release definition, first part; the end of M6 (synthetic conformance, 10.0) does not wait for it. The workloads P1 to P7 and P5-daily of chapter 7, with the same `bench/run.py` commands and measurement rules as T6.11, on a real snapshot that stays outside the repository. Public rule (2.7), restated: summary numbers only. The result JSON is the one of chapter 7's measurement rules (per workload p50/p95, RSS and USS, the cache state and the other fields listed there) with the snapshot's hash in place of `snapshot_id`, and nothing else of the snapshot: no path, host, account, producer or instrument name, and no row. `release_evidence.json` (T6.15) names this file under `real_data.measurement`.
- Done means: `bench/results/<YYYYMMDD>-<git sha>-<machine>-real.json` is committed (`<machine>` as T6.11's), and the PR has a short table with one row per workload: the synthetic p50/p95 and USS (the T7.V JSON) beside the real ones.
- Acceptance: `tests/unit/bench/test_results_present.py::test_real_snapshot_result_has_summary_fields_only` (a result file named `-real.json` has a snapshot hash, no `snapshot_id` and no key outside chapter 7's list), `tests/repo/test_release.py::test_release_summary_links_real_measurement`.
- Notes:
  - decided (#43 Decisions, 2026-11-01, #17): the documentation says KR real-data verification and long KR backtests start on or after 1999-01-04, and a producer may still supply earlier Saturday sessions; no engine rule changes.

**T6.29 `test(release): verify a real ledger event by event against the situation table`** **[2026-11-11, #162]** · `M6 (release evidence after T7.V, not a feature)` `release` · S · Blocked by: T7.V, T6.15, T5.11b · §8.4 (LV-01..LV-08), §5.9.7, §2.7, chapter 12 OI-46 — **run by the user on their own ledger**
- Context: the public half of OI-46's release definition, second part; as T6.28, the end of M6 does not wait for it. The owner's real ledger as a `manual:` book and the real snapshot, both outside the repository. For each row LV-01 to LV-08 of the 8.4 table, a session on which the situation occurred is reconciled with `reconcile` (5.9.7), a "statement" row is read by the owner as 8.4 says, and where it has a fill the fill-vs-decision bp is measured against the model's reference (next open; order time, type and quantity matched). The table is the criterion, not a length of ledger: a row the ledger does not cover is "not observed" with the reason. Public rule (2.7), restated: summary numbers only. `release_evidence.json` (T6.15) carries under `real_data.ledger_situations` one entry per row: the row id, `reconciled` or `not observed`, the number of sessions reconciled, whether the two values the 8.4 row compares were equal (the difference as a number when not), the median bp, and the reason when not observed; no date, instrument, quantity, price, path or name.
- Done means: `uv run python -m tests.repo.release_check --all` prints "real-data evidence: measurement linked (or `missing`) · ledger situations a reconciled, b not observed (of 8)", or "real-data evidence: none (synthetic conformance)" when the evidence is absent, and the PR has the eight-row table.
- Acceptance: `tests/repo/test_release.py::test_ledger_situation_entries_match_the_LV_rows` (one entry per row of 8.4, each `reconciled` with at least one session or `not observed` with a reason), `::test_ledger_situation_entries_have_summary_fields_only`, `::test_gate_summary_links_ledger_situations`, `::test_verified_claim_needs_measurement_and_ledger_situations` (the "KR/US verified" sentence of T6.15 only with both); the tests read the committed `release_evidence.json` when it has `real_data`, and otherwise one written from a paper book on the synthetic `small` snapshot (4.8).

#### v1.x — right after v1 (after M6)

**T7.2 `feat(research): effective number of trials and DSR(N_eff)`** · `v1.x` `research` · S · Blocked by: T6.8 · §5.7 [SC-10, OQ-6]
- Done means: in a study of 6 highly correlated candidates + 2 independent candidates, prints N = 8, N_eff ≈ 3 and records the method name. Cut only after 5.7's N_eff row defines the cluster-level return series, the Sharpe variance across clusters and the period alignment; the method is never named ONC (2026-11-04, #197).
- Acceptance: `tests/unit/research/test_neff.py::test_clustered_candidates`, `::test_method_recorded`, `::test_dsr_default_still_uses_N`.

**T7.3** → moved in v3.3 to **T3.29** (M3a) (group caps into v1).

**T7.4** → moved in v3.3 to **T3.33** (M3b) (`time_stop` into v1).

**T7.5 `feat(artifacts): Brinson sector attribution and first divergence`** · `v1.x` `artifacts` · M · Blocked by: T4.10, T5.5 · blueprint chapter 11 items 2 and 5 [SC-07]
- Done means: a per-sleeve allocation, selection and interaction table (comparison baseline `universe_ew`); `Comparison.first_divergence()` gives the first date, instrument and cause of divergence.
- Acceptance: `tests/unit/artifacts/test_brinson.py::test_effects_sum_to_active_return`, `tests/unit/api/test_compare.py::test_first_divergence_cause`.

**Later (P3; tickets are made once a semantic contract and fixed cases exist)** [RV 2.4]: linking the `rates` interest-rate data for cash interest (the fixed annual rate `[account] cash_rate_bps` went into v1 in v3.2), a T+n settlement model, benchmark regression metrics (α, β; tracking error and IR are v3.1 T4.12, the round-trip trades table is v3.1 T5.14), everything in 12.1 deferred in v3.1, MDA feature importance, clustered MDA, sample-uniqueness weighting, Hansen SPA, meta-labels (v1.x), correlation-shock and VaR overlays, the optional model `stop_limit_fill = close_confirmed`, an economic label variant holding cash (no reinvestment), a fast approximate mode (`fidelity="vector"`), Sharpe bootstrap intervals, widening the built-in factors (`Beta`, `Correlation`, `BollingerBands`), a separate `adjustment_factors` dataset (after measurement), more markets in the market rules packs, importing zipline, LEAN, Nautilus and DBN (TDS chapter 9), migrating ledger definitions (`nexusbt book migrate`).

### Work with no ticket yet

The lines below bind work that has no ticket in 10.1 yet. Each is written in the form of `README.md` in this folder. When a ticket for one of them is cut, its lines move under that ticket's entry, or into its issue, in the same pull request, and leave this section.

#### Stage (2)

The writing tool, the reader of value tables (`nx.Item`), the result's labels and the user-facing names.

- decided (#752 Decisions, 2026-11-27): N, the user-facing names `symbol`, `date` and `prices`, with a result table's `symbol` read from `instrument_symbols` on the row's date, is stage (2)'s first slice; the stored names stay (spec header "Identifier name", 3.1; #725 Decisions 248).
- owner decides at the cut (#752 Decisions, 2026-11-27): the `symbol` of an instrument with no `instrument_symbols` row on the date; whether `latest_symbol` comes from the start; the names and meanings of the `instrument_id` arguments of `Market.series`, `explain` and `override`; whether `Run.to_pyfolio()`'s `symbol` is the stored key or the symbol in use on the fill date.
- owner decides at the cut (#725 Decisions 96, 2026-11-23): whether stage (2)'s first slice also holds one path end to end: a first result from one table of closes, the calendar's source named, a key written twice shown by file and line, and the same command succeeding once fixed.
- decided (#705 Decisions A, 2026-11-21): when right, easy and light conflict, right comes first, then easy, then light; ease comes from a tool doing the work, and a tool never invents a fact the user did not supply.
- decided (#705 Decisions E, 2026-11-21): each label of the result says whether its fact was checked by the tool or attested by the producer, "attested" by default.
- decided (#705 Decisions E, L1 and H, 2026-11-21): TDS states the logical tables first and their layout on disk second; one writing part turns in-memory tables into a package and ships in `nexusbt-tds`, so another producer can use it as it is.
- decided (#705 Decisions E, I, 2026-11-21): the result carries one set of labels, built on E30 and the manifest's `assumptions` and `fallbacks`.
- decided (#705 Decisions 10, 2026-11-21): the label block's first lines (prices, calendar, rows, identity, universe, fallbacks) are built together with the writing part.
- decided (#705 Decisions picture 1, 2026-11-21): three ways in call one writing part with the same checks: a one-line command for a price file (file, market, price basis), a settings file, and one Python call that takes tables.
- decided (#705 Decisions picture 2, 2026-11-21; #725 Decisions 205): the user writes the market once (calendar, currency and time zone follow) and, for each kind they have, its file, in any order.
- decided (#705 Decisions 9, 2026-11-21; #752 Decisions, 2026-11-26): the user writes only facts they alone know; the tool picks the profile from the kinds given and writes each kind's conventions (`bar_time = session` for equity daily bars, the `ts_end` rule), lists each in what the tool decided, and what the user writes wins.
- owner decides at the cut (#705 Decisions 14 and 17(9), 2026-11-21; #725 Decisions 94, 2026-11-23; #752 Decisions, 2026-11-26): how the tool sets a package's declared profiles (TDS 4.2, 7) so that any kind can be added one at a time, in any order, and how #720 fits; the user picks no profile.
- decided (#725 Decisions 95, 2026-11-23): the tool makes an empty template whatever the profile answer is.
- builder's choice (#725 Decisions 95, 2026-11-23; recommended: ask rarely, because asking too often goes unread): from what percent or multiple suspect data is asked about, and how a user records "checked".
- decided (#705 Decisions picture 3, 2026-11-21): without a fact only the user knows (for prices, the price basis), the tool stops; it may say what is usual but never applies it.
- decided (#705 Decisions picture 4, 2026-11-21): the tool asks only what it cannot tell (which column is which, a date format that reads two ways, units and scale), stops, and the error says what to write.
- decided (#705 Decisions 16, 2026-11-21): what the tool cannot know is asked and stops the tool without it, or is recorded as unknown, read on the cautious side and labelled, or is given by the column name; it asks the price basis and kind, whether dividend amounts are on that day's share basis or adjusted for later splits, and an FX rate's time of day.
- decided (#705 Decisions picture 5, 2026-11-21): from a price file alone the tool makes `instruments` with `listed_on` = the first bar and `listed_on_censored = true`, labels identity "from tickers, renames and reuse not resolved", writes no `last_session` or delisting, and a given instrument list wins.
- decided (#705 Decisions picture 6, 2026-11-21): a kind given no file shows in the result's labels, saying what the result can and cannot do, why, and what to add.
- owner decides at the cut (#705 Decisions picture, 2026-11-21): the tool's settings keys, command arguments and function names.
- decided (#705 Decisions 13, 2026-11-21; #725 Decisions 216): the tool asks each price file's `asset_class` (shares or ETFs, or index values) and never guesses; a file that mixes them needs an instrument list, whose class wins over the default declared once.
- decided (#705 Decisions 15, 2026-11-21): two columns read as one meaning stop the tool.
- decided (#705 Decisions 16, 2026-11-21): a dividend's date is declared by mapping it to `ex_date` or `record_date`, and a delisting's to `last_trading_date` or `exit_date`; with no mapping the tool stops.
- owner decides at the cut (#752 Decisions and its user-file table, 2026-11-24): the user-file column names of `corporate_actions` and `delistings`. The table proposes `ex_date`; `split_to` → `ratio_num` and `split_from` → `ratio_den`, with `ratio_new_per_old` written by the tool; `kind` from the file a row comes from and the ratio's direction; `amount` → `cash_per_share` with `currency` and a declared `gross_or_net`; `last_trading_date`; `reason` → `delist_type`; an optional `final_price` turned into a return over `ref_price`; and the tool writes `event_id`, `ts_effective`, `affects`, `factor_method` and `status`.
- decided (#705 Decisions 17(7), 2026-11-21; #725 Decisions 206, 249): a symbol that would make an id outside K1's pattern stops the tool with the fix in the error, and the tool adds no prefix or suffix of its own to symbols.
- decided (#705 Decisions 17(8), 2026-11-21): one price file is one market; a file that mixes markets needs a market column, else the tool stops.
- decided (#705 Decisions 17, 2026-11-21; #725 Decisions 171, 2026-11-23): the tool always writes dense daily bars and stops when it is given `density`; until it exists, `tds import csv` keeps taking `density: dense`.
- decided (#705 Decisions 21, 2026-11-22): a result says so when the user names an index whose `index_kind` is null.
- decided (#705 Decisions E, G2, 2026-11-21): for a market without an exchange calendar the tool supplies a 24-hour calendar (`session_kind = continuous_24h`), never an empty `calendar_id`.
- decided (#725 Decisions 61, 2026-11-23): once the market declaration brings an exchange calendar, a calendar inferred from bar dates at declared hours is used only where no exchange calendar can be.
- owner decides at the cut (#705 Decisions, 2026-11-21; #725 Decisions 86): whether the tool's exchange-calendar library is an optional extra of `nexusbt-tds`; the tool adds no required dependency but pyarrow (#508).
- decided (#725 Decisions 74 and 75, 2026-11-23): the tool reads one shape per kind, a long table holding every instrument with `symbol` on each row, from CSV, Parquet or an in-memory table; a table that is not long stops, naming the missing `symbol` column and how to reshape.
- decided (#725 Decisions 76, 2026-11-23): the tool names an instrument by one `symbol` and takes no `ticker` column, not even as an alias; splits and dividends come as two user files into the one `corporate_actions`.
- decided (#725 Decisions 77, 2026-11-23): a column named as documented, ignoring only case and surrounding spaces, is read unmapped, and any other is mapped by the user, that column only; the tool reports what it read as what and what it left unused, and stops naming a missing required column.
- decided (#725 Decisions 78 and 120, 2026-11-23): what differs by market (price basis, volume unit, dividend tax, units) is declared once for the market, not given as a column; the report shows, where the mapping preview is, how many shares a source value was stored as.
- decided (#725 Decisions 81, 2026-11-23): the tool does not read a column by a guessed name, decide the price basis, fix a suspect value, or guess the market from the data.
- decided (#725 Decisions 84, 2026-11-23): one kind may come in several long files with the same columns, split by the rows' dates and never read for facts from file names; a key in two files stops the tool, which chooses neither.
- decided (#725 Decisions 85 and 86, 2026-11-23): the tool takes thousands of instruments over decades of daily rows on one 8 GB machine, reading in chunks with at most one partition (a year) held, with column types from the standard's schema and keys and order checked per partition; its docs name the in-memory table passed directly as the path for small data.
- decided (#725 Decisions 87, 88 and 114, 2026-11-23): an update is a new package with `parent_snapshot_id` that shares partition files of equal sha256 and has the same values as one built from scratch from the same input and settings; a parent row whose value changed is reported (key, from, to), and on adjusted-only prices the tool says that each update changes the past.
- decided (#725 Decisions 114 and 115, 2026-11-23): an input file is skipped unread only when it and the settings (market declaration, price basis, volume unit, column mapping, calendar) are unchanged; a volume unit corrected while the price file stays the same rewrites every partition, and a test holds it.
- decided (#725 Decisions 92, 2026-11-23): the tool reads set file names in a folder with no config, takes a table given to `run_pipeline` directly for small data (the same package built inside, and the result says so), and uses a drafted mapping only on lines a person confirmed.
- decided (#725 Decisions 93 and 260, 2026-11-23): the tool asks about suspect price data (a drop with no split, a volume that looks re-scaled, no instrument ending before the last day) and fixes no value; rows of the same key are not asked about, they stop.
- decided (#725 Decisions 99, 2026-11-23; #705 Decisions 44 and 46, 2026-11-22): the tool writes and checks in one step, its first line "N block saving, N to look at", and writes no package while a block remains; a key written twice shows both rows' file, line and values. #715 (a close-only file that imports, then M008 lines naming neither the instrument nor the fix; a skipped check that names its reason for the H codes only) is read when the tool is cut.
- decided (#725 Decisions 100, 2026-11-23; #705 Decisions E, H3, 2026-11-21): the tool says what can be done in three parts: the data read (rows, period per kind), that it cannot know whether the events are complete, and the computations this engine version offers; `nexusbt doctor` is widened the same way when its ticket is cut.
- decided (#725 Decisions 101, 2026-11-23; #764 Decisions, 2026-11-25): the mapping preview shows two or three source values and how each was read (type, unit) beside the names; a confirmed mapping is stored, and only new or changed columns are asked again. No separate preview of the input's first rows is made.
- decided (#725 Decisions 104, 2026-11-23): the tool's report (what it read, left unused, filled by default) is kept per package before updates are built, and two corrections with the same last session are told apart by `snapshot_id` too.
- decided (#725 Decisions 117, 2026-11-23): the whole hash tells packages apart; a short prefix shown on screen promises no uniqueness, and where two prefixes collide in one place more is shown (#733).
- decided (#725 Decisions 125, 2026-11-23): the last trading day of an exit the user gives is the instrument's `last_session`, and the tool's filling stops there.
- decided (#764 Decisions, 2026-11-25): the tool shows progress while it builds.
- decided (#764 Decisions, 2026-11-25): old packages are removed automatically, on by default, with four guards: never a package a saved run or a ledger names; never the newest few, the number a setting; a package is announced as removable at one update and removed at the next; each removal is reported with the space freed, with a dry run and a setting that turns it off.
- carried (#764 Decisions, 2026-11-25): how the tool learns what the engine's records name, the default number of packages kept, and the space accounting where file systems share files are the builder's to settle when the ticket is cut.
- decided (#725 Decisions 106 and 107, 2026-11-23): stage (3) adds a test showing that the same data as one file, several files and an in-memory table gives the same value hash and the same findings; #621's regression case is "a late-corrected dividend does not change a past decision day's return".
- decided (#725 Decisions 116, 2026-11-23): the tool's done-means holds a large CSV ordered by instrument whose dates go back many times (no re-sorting, a key written twice in far-apart chunks caught with both places, the same value hash as a date-ordered file) and a settings-only update.
- decided (#725 Decisions 133, 2026-11-23): a pull request that changes what `tds import csv` writes carries a test that opens the result with the engine and reads values.
- decided (#725 Decisions 97, 2026-11-23): a result's label names its calendar's source: for `inferred_from_bar_dates`, how many dates the prices gave, that no exchange calendar was compared and that a day all instruments lack cannot be known; for an exchange's, the period's sessions and those with no bar at all.
- decided (#705 Decisions 57, 2026-11-23): a result from a package holding `close` only, from a market where some files hold a column null in every row, or over a calendar inferred from bar dates says so in a label.
- decided (#752 Decisions, 2026-11-26): `nexusbt doctor`'s note that a snapshot's columns changed (spec 3.2) comes back with the step that builds `nx.Item`.
- decided (#752 Decisions, 2026-11-26): E7 with its "Did you mean" for a wrong name of a snapshot's own column (spec 3.2, 6.6), and the checks `test_schema_registry_injected_at_binding` held, come back when `nx.Item` is built.
- decided (#752 Decisions, 2026-11-27): when `nx.Item`'s reader is built, P-FUT's earlier snapshot (`cut_after` in `tests/property/_future.py`) cuts value tables by `date` against each market's watermark, since a value table writes no availability instant.
- carried (#43 Decisions, 2026-11-18; #752 Decisions, 2026-11-26): T-24's `nx.Item.sector.eq(1)` row runs through the executor once `nx.Item`'s reader is built; today `test_T24_filter_unknown` runs it through the kernels only.
- decided (#725 Decisions 226, 2026-11-24): the user documentation of value tables shows, with an example, that a value the vendor already restated takes no kind declaration (spec 5.3.5).
- decided (#725 Decisions 105, 2026-11-23): the user-side names of the price basis are the three of TDS 5.5 (`raw`, `split_adjusted`, `total_adjusted`).
- decided (#705 Decisions 23, 2026-11-22; #708 Question, 2026-11-21): until it has been run and shown on screen that the engine takes the strengths of other engines and solves their weaknesses, no README or document says it does, at most that it is designed to (T2.17 carries the same for the quick start).
- carried (#708 check table 1, 2026-11-21): the tool's tickets show, counted, one price file to a first result on both the one-line command and a table passed in Python (files prepared, lines written, commands typed), the user writing three things: market, price basis, kind.
- carried (#708 check table 2, 3 and 4, 2026-11-21): they show the stop screen when the price basis is not written; a file with an empty day in the middle, where the day stays `missing` and is labelled; and data with a market holiday, which runs with no error and the calendar's source recorded.
- carried (#708 check table 5 and 7, 2026-11-21): they show a stock with a split, whose values the engine computes from the event; and the same computation on prices-only and on complete data, with how the label blocks differ, what cannot be done and what to add.
- carried (#708 check table 8, 2026-11-21; #725 Decisions 77): they show that a date format that reads two ways, a missing required column and an unknown unit each stop the tool with what to write.
- carried (#708 check table 11, 12 and 13, 2026-11-21): they show that the same input by the three ways in gives the same value and semantic hashes; that every value the user did not state is in the list of what the tool decided and nothing stated is in it; and that instruments from a price file's codes get `listed_on` = the first bar with `listed_on_censored = true`, no `last_session`, no delisting and a null `lot_size` (T3.4).
- carried (#708 check table 15, 2026-11-22; #705 Decisions 48): a made-up file holding an instrument code, a date and `close` only is given to this engine and to other engines the same way, recording what each takes, refuses and says it cannot do.
- carried (#708 To look at in step 3, 2026-11-21): when the user's input carries an adjustment-factor column such as `cum_factor_*`, the tool says that the column is not used and that the engine computes adjustment from the split and dividend events.
- carried (#738 Decision, 2026-11-23): a stock dividend, a bonus issue or a capital reduction needs a `kind` the split and dividend files do not carry.
- owner decides at the cut (#738 Findings 18, 2026-11-23): whether a dividend's declaration date given by the user fills `ts_announced`; left null, the event is known from `ts_effective` (TDS 5.11).
- carried (#738 Decision, 2026-11-23): a calendar inferred from bar dates ends on the last bar, so a later ex-date or exit has no session; the tool says so.
- carried (#738 Decision, 2026-11-23): from price files alone the only honest `tradability_daily` content is `status_known = false`.

#### The next TDS revision

- decided (#705 Decisions E, K, 2026-11-21): a market declares since when its delistings are complete (absent = unknown); a warning names an "everything alive at the end" package, and a check names "no exits for some years, then exits"; with few instruments neither judges, and an implied start year is shown as an estimate, never written as a declaration. A new manifest field moves `tds_draft`.
- owner decides at the cut (#752 Decisions, 2026-11-27): whether the checker judges a value-table row whose instrument is of another market than its `market=` partition; it would need a new `full`-level R code and is not one of spec 5.3.5's five stops.
- owner decides at the cut (#725 Decisions 177, 2026-11-23): whether reading a missing bars `params.ready_delay` as 0 is a default of the standard; TDS 5.5 makes the key optional and the engine reads 0 (spec 5.1.2).
- owner decides at the cut (#705 Moved from #43, 2026-11-21): whether US daily volume as consolidated or primary-exchange is an optional `bars` declaration with no default.
- owner decides at the cut (#705 Moved from #43, 2026-11-21): whether TDS 4.4 lets a package hold one or several `dictionary/columns` datasets; today the checker refuses neither and the engine reads the marks of every dataset of that kind.
- builder's choice (#705 Moved from #43, 2026-11-21; recommended: compare each stored column with the rule of its column group, because each column is published by its own rule): TDS-T002's row says what is compared when one dataset declares several rules in `params.availability_by_column`.
- carried (#705 Moved from #43, 2026-11-21): #528's gaps have no ticket: no profile reported as passed (#720), no breakdown of the full level's time, no comparison between snapshots, no licence or source field; chapter 1's `[unverified]` cells can be checked against #528's sources.
- carried (#705 Moved from #43, 2026-11-21): before the value hash is next changed, #57's Outcome items 3 to 5 are read (#116, #120, #123; #609 is the weekly-bars key).

#### v1.x

- decided (#43 v1.x follow-ups, 2026-11-01, from #30): KR credit interest takes a 366-day denominator in a leap year, period by period.
- decided (#43 v1.x follow-ups, 2026-11-01, from #30): the US borrow fee is charged on 102% of the collateral rounded up to whole dollars, on a 360-day year; a market-wide primary source is still to find.
- decided (#43 v1.x follow-ups, 2026-11-01, from #32): the KR pack truncates each tax below 10 won (`[rounding] tax` with `unit = 10`), and the row turns `verified = true` only on a real broker contract note the owner supplies.
- carried (#43 v1.x follow-ups, 2026-11-01, from #30): KR `day_count = 365` is checked against the terms of the broker the owner uses, when the owner supplies them.
- decided (#43 Decisions, 2026-11-19, #587): V31-42, when cut, comes as pairwise rolling correlation, covariance and beta between columns, then a time-series rank, `argmax`/`argmin` and a linear-decay mean; `nx.ops.rolling` already has mean, sum, std, min, max and median (spec 3.3).
- owner decides at the cut (#43 Decisions, outside review of 2026-11-03): a data-delay scenario, 12.1 V31-65 `info_lag1` (the note's name: `exec_lag1`); whether the two names are one scenario is checked when its ticket is cut.
- carried (#43 Decisions, 2026-11-20, #253): the quantile hand calculation is V31-58's, recommended before T7.V.

#### Other

- owner decides at the cut (#752 Decisions, 2026-11-25): whether a `test(golden):` pull request removes `cum_factor_split` from the golden inputs of T-07 and T-15; T-15's shows that a package's old column changes no result.
- decided (#705 Decisions 33, 2026-11-22): a test holds that the generator's bars divided by the record's total product equal the path before the events within 1e-12 for US and ZZ, and not for KR, whose price limits and halts move bars on their own.
- carried (#705 Decisions 51, 2026-11-22; #725 Decisions 182): the engine's `Price` reads only `equity` rows, though TDS requires OHLCV of `etf` rows too; #745 builds it with B3's engine side.
- builder's choice (#705 Not sure yet, 2026-11-22; recommended: look again only when the generator revises such an event, because until then it cannot happen): if the generator revises an event dated after an instrument's last bar, `_recut` records a step the resolver does not apply.
- carried (#43 Decisions, 2026-11-05, #300): the generator refuses a halt injected into `tiny`, which writes no `tradability_daily` (4.8 (5)); a test that needs a halt uses `small`.
- carried (#43 Decisions, 2026-11-19, #300 and #302): the generator injects full-day KR halts only and refuses a limit close or an `admin_status` row with `NotImplementedError`, though 4.8 names `tradability_daily` among the `EventSpec` datasets; a test that needs one waits for a ticket that builds it.
- owner decides at the cut (#43 Decisions, 2026-11-19, #299): whether 4.8's generator values for an injected cash dividend (`record_date`, `pay_date`, `resolution_body`) stand as the owner's; #299's question has no answer on record.
- owner decides at the cut (#43 Decisions, 2026-11-20, #625): whether the 9.1 row or `testpaths` changes; the row says `tds` is the separate job `tds / conformance`, while `testpaths` runs `tds/tests` in `ci / test` too.
- owner decides at the cut (#43 Decisions, 2026-11-18, #513): whether a rank, `demean` or `winsorize` of a price level read through `shift` or a window is refused; today #499's check gives it "not known" (spec 5.3.3).
- owner decides at the cut (#43 Decisions, outside review of 2026-11-03): a fuller display of how much a result depends on the daily-bar path assumption (an extension of E11, beside 5.6.4's "x/n fills judged on daily bars"), and whether chapter 0's competitor table is updated for vectorbt, Qlib and LEAN.
- carried (#43 Decisions, 2026-11-02, #94): the E14 for `[data] root` names the wrong source in two cases.
- owner decides at the cut (#43 Decisions, 2026-11-04, #247 and #281): whether the run id's canonical JSON is `json.dumps(sort_keys=True, separators=(",", ":"))`, as the code writes it, or TDS 4.5's RFC 8785 form, said by the ticket that next touches the run id (spec 5.9).
- builder's choice (#43 Decisions, 2026-11-19, #101; recommended: one wrapper at the public entry points, because every user call passes through one of them): where an unexpected exception in engine code becomes E46 `EngineBugError`; nothing in `src/` converts one today, and the saved-run half of `bugreport` is #607.
- carried (#43 Decisions, 2026-11-02, #101 and #52): spec 6.6's bug bundle names the reproduction command and the manifest; the bundle's third file, `versions.json`, is named when 6.6 is next edited.
- carried (#43 Decisions, 2026-11-19, #248 and #306): `seal()` sorts a package table that raises `TypeError` when an installed distribution has no `Name` (not reproduced).
- carried (#43 Decisions, 2026-11-19, #252 and #595): at the end of M1 the parity evidence file `tests/parity/evidence/<date>-<sha>-all-small.json` is committed from an `engine / parity` run on `main`; a pull request's run does not upload it.
- carried (#43 Decisions, 2026-11-20, #253): `percentile_between` and `zscore` differ from zipline (ADR 0046) and have no golden hand calculation, only unit tests with hand-derived numbers.
- carried (#725 Decisions 150 and 151, 2026-11-23): a stage (3) candidate is a column or batch encoder for the value hash's canonical bytes, keeping `hash_spec` and the values; no speed-up of #732's first full check is stated before it is measured.
- carried (#708 To look at in step 3, 2026-11-21): the first line of `tds check --level full` reads `<profile>: declared, verified to schema, not_checked`; asked for `full`, it names `schema`, and its third part names neither what was not checked nor why.
- carried (#708 To look at in step 3, 2026-11-21): numpy's `DeprecationWarning` on the "generic" timedelta unit reached the user's screen twice in one `nx.run_pipeline` call (seen on that date, not rechecked).
- carried (#708 To look at in step 3, 2026-11-21; #705 Decisions 28): once, on the day the whole data is built on a server, the generator's record is run against the resolver over the whole `full` preset (`NEXUSBT_SYNTH_FULL=<empty folder> uv run pytest tests/unit/testing/test_synth.py -k full_record`).
- carried (#43 Decisions, 2026-11-18, #492): a golden case with a late cell read through `shift` (T-12's subject), hand-checked by a person under ADR 0044's time contract; no ticket holds it.
- owner decides at the cut (#705 Moved from #43, 2026-11-21, #500): whether spec 5.3.3 gets a sentence for `AverageDollarVolume` over an event whose `price_factor` and `share_factor` are not reciprocal; today the kernel computes it by the definition, on raw values.
- carried (#43 Decisions, 2026-11-19, #277 and #323): 8.2's T-25 line writes `decay=` where 3.4 and the golden factor file name `decay_rate`, and its T-20 line says "a late bar (`ts_end+PT5M`)" where the case uses the column availability rule with `params.ready_delay = PT5M`; the next edit of 8.2 brings both in step with the cases, no value changing.

### 10.2 Producer-side tickets (left out of the public edition)

This section is a private producer's work plan and was left out of the public edition. It has nothing to do with engine behaviour, and the engine's M0~M6 can be finished with the synthetic package (4.8). What the engine does with columns and datasets the producer has not filled is set by the fallback behaviour of 4.5.
