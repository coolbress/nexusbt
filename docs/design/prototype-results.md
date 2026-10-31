# Throwaway prototype results, summary (2026-10-28)

> Korean translation: [prototype-results.ko.md](prototype-results.ko.md) (this English file is canonical). In short: a throwaway prototype (not product code, not in this repository) measured the performance budgets P5 and P11, ran 32 hand-computed accounting cases, and checked that "compute decision rows only" equals "compute everything". All gates held. Section 5 lists spec wording to fix; section 6 lists what the synthetic generator must add. The spec cites this file in chapter 7 ([R4H-05]~[R4H-08]).

Purpose: measured evidence for three of the spec's "10 points of evidence": performance (P5, P11), running the hand-computed accounting cases, and Pipeline "decision rows only = full compute". The prototype code and the raw measurements (JSON) are not in the repository. The numbers here are summaries only.

## 0. Measurement conditions

- Two machines: a **laptop, M1 8 GB** (it used 6.5 GB of swap during the runs; read it as the worse case) and the **compute machine, M4 16 GB** (the reference machine of spec chapter 7). The gate verdict is taken again on the compute machine in T6.11.
- Environment: Python 3.12, numpy 2.5.4, numba 0.68.1, pyarrow 26.0.0, polars 2.1.0, psutil 7.2.2.
- "cold" = a new process with the Numba cache and the L0 cache (.npy blocks) deleted. "warm" = both present. The OS file cache is warm even in cold runs (the same as the spec's P1 definition).
- Repetitions: 5 per workload, each in a new process; p50/p95 are over the 5 (p95 ≈ the maximum). The output value hashes were equal across all 5, and between cold and warm.
- Memory: macOS does not let one process read another's USS (psutil AccessDenied). Each work process measured its own USS and RSS every 50 ms and recorded `ru_maxrss` at the end → the spec's P7 "sum of USS over the tree" needs a probe inside each worker ([R4H-07]).

## 1. Synthetic TDS v1.4 generator and a minimal checker

- Preset `tiny`: 6 KR and 6 US instruments, 2020-01-02 to 03-31. A split during a halt, a dividend during a halt, a 1:3 reverse split, a dividend event with D=500.
- Preset `full` (seed 0): 2,700 KR + 8,000 US instruments, 1995–2024, with listings and delistings inside the period. Generation 245 s, peak RSS 1.4 GB, 7.7 GB on disk.

| Dataset | Rows | Files | Size |
|---|---|---|---|
| bars (1d, raw, dense, market=/year=) | 48,790,452 (about 6,450 instruments a day on average) | 60 | 1.5 GB |
| feature_panels (300 factor columns) | 2,317,405 | 60 | 6.1 GB |
| fundamentals_state (intervals, 3 items) | 2,323,716 | 2 | 24 MB |
| corporate_actions | 187,616 (1,848 share-changing events) | 1 | 3 MB |
| delistings / instruments / calendar_sessions | 5,290 / 10,700 / 15,119 | 1 each | small |

- What the checker looked at: required manifest fields, file sha256 (127 files), Parquet `tds.*` metadata, required columns, types and non-null, K001, K002, A010, A005, R001, R008, V001, V004, V040, D002, closed enumerations, partition values matching, T003/T004, panel `ts_available > as_of_date`.
- Result: `full` passed 194 checks with 0 failures (19 s), `tiny` passed 68. On a copy with ratios deliberately blanked, A010 FAILED (the checker really catches it).
- Differences from spec 4.8: the calendar is weekdays minus approximate holidays (`exchange_calendars` not used). `tradability_daily`, `share_counts`, `label_panels` and the tds-hash-1 value hash were not produced.

## 2. Measured performance (against the budgets)

| Workload | Machine | cold p50 / p95 | warm p50 / p95 | Peak USS | Budget |
|---|---|---|---|---|---|
| **P5** monthly top-50 per sleeve, costs, KR+US 30 years, 5 scenarios × 2 sleeves, save and hash | M4 16 GB | **5.8 / 6.8 s** | **1.6 / 3.7 s** | 2.1 GiB | gate p95 ≤ 30 s, target 10 s, ≤ 4 GB |
| P5 (same workload) | M1 8 GB | 15.9 / 19.6 s | 9.2 / 11.6 s | 1.11 GiB | same |
| **P11 (a)** IC + quintiles for 300 factors, 716 decisions | M1 | 44.9 / 50.1 s | 30.3 / 31.8 s | 1.09 GiB | ≤ 300 s |
| **P11 (b)** 300 → composite score → top-50 backtest | M1 | 31.0 / 34.2 s | 21.6 / 23.0 s | 1.25 GiB | ≤ 60 s |
| **P11 (c)** grid n∈{20,50,100} + walk-forward 10y/1y/1y (simplified) | M1 | 28.2 / 29.6 s | 22.6 / 26.6 s | 1.32 GiB | ≤ 180 s |
| P11 (a) variant: read only 40 base columns and build the 300 on decision rows | M1 | – | 28.5 / 32.8 s | 0.41 GiB | reference |

- Verdict: P5 is inside the gate on both machines and meets the 10 s target on the compute machine. The three P11 targets have more than 5× headroom. Memory stays under 2.1 GiB everywhere.
- **P5 by stage (M1 cold, seconds)**: block read 4.3 + L0 write 1.3 + events 0.2 + Pipeline on decision rows only 2.1 + state machine ×10 5.7 + save 0.04. Warm, the block read takes 0.04 s (L0 hit). Inside the spec's stage budgets. One state-machine run (30 years, one sleeve) takes about 0.6 s with a Numba session loop.
- **P11 (a) by stage (cold)**: panel read 14.6 + lookup and decision rows 2.9 + IC and quintile reduction 19.0 + block read and L0 6.4. Only 2,294,161 decision rows were computed (all daily rows would be about 48.8M).
- **Row-group statistics pruning**: skipping the other market's files by the `instrument_id` min/max statistics → P11 (a) 122 s → 45 s ([R4H-06], spec chapter 7 design means 8).
- **Had it been a daily forward fill (ffill) (computed)**: 300 × 8 B × (KR 7,526 sessions × 2,700 + US 7,593 × 8,000) = 194.6 GB, 117.1 GB for listed cells only. Measured peak 1.1 GiB (read in year blocks and reduce at each decision). Interval lookup is `searchsorted` on the sort key `(instrument<<40)+ts`.
- **Reproducibility**: the 10 output value hashes were bit-identical on the M1 and the M4.

## 3. Decision rows only = full compute

mom_12_1 (split and dividend adjustment by interval lookup in the events table) computed on every session and then cut to the decision rows was **bit-identical** to computing it on the decision rows only (543,193 finite values in KR, 1,644,656 in US).

## 4. Running the hand-computed accounting cases: 32/32 passed

| Golden | Case | Result |
|---|---|---|
| G-53 | (a)(b)(c)(d)(e)(g)(h)(i)(j) integer ratios, `floor_shares`, E13, literal | passed ((d) 57 shares; a plain floor gives 56) |
| G-53 (f) | 7 shares 1:3, previous close 1,000 → 2 shares + 1,000 cash in lieu (simulator kernel) | passed (cash 8,000, NAV 14,000) |
| G-54 (i)(ii)(iv) | 2:1 split during a halt → 20×50 = 1,000; dividend during a halt → 900 + 100 receivable; decision V 2,000, T=20, 0 orders | passed |
| G-68 (a) | −10 shares, D=500: obligation −5,000 on the ex-date, NAV change 0, cash −5,000 on the pay date | passed |
| G-69 | −7 shares 1:3 → −2 shares, cash −1,000; −16 shares 1:8 → −2; 2:1 −10 → −20 | passed (stop prices not snapped to the grid) |
| G-99 | 130/30 margin: IM 80,000, loan 30,000, 3 days' interest 1,233 cents; cash account 1.45 > 1 → E16 | passed |
| G-100 | close 60: shortfall 10,000, f = 2/3, reduce by 667 shares → 1,333 shares, E 20,000 ≥ MM 19,995 | passed |
| G-104 | (a) E −10,000 → f 0, full liquidation, ruined; (b) f 0.6667, 667 shares | passed |
| G-81 | vol_target (a)~(d): 0.141421/0.707107/0.353553/0.292893 | passed |

## 5. Where the spec's numbers were wrong or ambiguous (whether the spec takes them is up to the spec, which is canonical)

1. G-53 (g) "125/1000" is unreduced while the 5.6.1 literal example "1.000004 → 250001/250000" is reduced → use one notation for ratios in event records (reduced recommended).
2. G-81 (c) writes only three terms. By the 5.5.1a formula, with no shorts the fourth term `1/Σw⁺ = 1.25` is also included (k stays 1).
3. G-54 (iv) "10 shares held on the day of (i)" is the pre-split quantity → "20 shares after the split".
4. G-104 (b) does not state the cash (−75,000).
5. Prototype simplifications (not spec problems): raw volume for ADV, late KR dividend terms booked straight at the ex-date, rights issues as a price factor only, long only.

## 6. Engine and synthetic-generator work from comparing real data's shape

A working copy of the reference producer's real snapshot was skimmed read-only to compare its shape with the synthetic data and TDS v1.4 (data values and row counts are private and are not written here). Fixes on the producer side are the producer's own. Only what concerns the engine repository:

- Shapes the synthetic generator (4.8, [R4H-08]) must include: `obs_status` `no_trade` and `missing`, event types `symbol_change` and `other`, status `announced`, amendments (`revision_of`), events with empty announcement times (`ts_announced` and `ts_terms_available` null), prices off the 0.0001 grid (float32 traces), and a performance preset with 2.5× the instruments.
- In the real data, many share-changing events have an empty exact ratio (`ratio_num/ratio_den`) → the engine does not open them, E13 (A010 = error, user decision R4F-01). A cash capital reduction is not a share event, so its type must be split out.
- Even when the cumulative factor columns of the real bars are empty, the engine recomputes them from the events table (F-04): no problem.
- Parquet files may declare every column nullable → checker S003 judges by the values, not the declaration.

## 7. "10 points of evidence" verdict (prototype scope)

| Item | Verdict |
|---|---|
| Performance P1~P11 measured | Partly met: P5 measured on the compute machine (p95 6.8 s), P11 (a)(b)(c) measured on the laptop. P1~P4 and P6 not measured |
| Reproducibility | Partly met: P5 output hashes equal on two machines |
| Risk/accounting hand computation | Partly met: 32/32 passed. "A person reproduces three months" and comparing shorts against real data remain |
| Decision rows only = full | Met (mom_12_1, 2.19M values) |
| Two TDS producers pass `full` and hash vectors match | Not met: one synthetic producer passed a partial checker only; tds-hash-1 not implemented |
| Real-data shape comparison | Met (first pass): section 6 |
