# Verification plan for the research statistics (false positives and power)

> Korean translation: [statistics-verification-plan.ko.md](statistics-verification-plan.ko.md) (this English file is canonical). In short: before the engine's DSR, PBO, BHY, PSR and MinTRL are trusted to say how often a procedure finds something that is not there, they are run on data-generating processes (DGPs) where the answer is known. This file fixes those DGPs, the scenarios, the error criteria and the repetition counts. It is a plan; nothing here is a result about NexusBT or about markets.

Written 2026-11-04 by design session B (review item D12). Spec sections it serves: 5.7, 5.8, 6.2, 6.3, 6.3a, 8.3 (P-STAT).

## 1. Two kinds of synthetic data

| | Accounting fixtures | Research DGPs (this file) |
|---|---|---|
| Purpose | the engine computes fills, cash, corporate actions and labels exactly | a statistical procedure has the error rate it claims, under stated conditions |
| Source | the synthetic TDS generator (spec 4.8) and the golden cases (8.2) | return or score processes with a known null or a known effect |
| Expected value | a literal number per session | a rate with a Monte Carlo interval |
| A pass means | the arithmetic is right | under this DGP and this selection process, the rate is within the interval |

A research DGP may be fed through the 4.8 generator once the engine exists (stage B below), but a passing research scenario says nothing about accounting, and a passing golden case says nothing about error rates.

## 2. Defined before any run

Each scenario states, before it is run:

1. **Null hypothesis** and, for power, **the alternative** (an effect size, for example an annualised Sharpe of 0.5 or 1.0 for one candidate).
2. **The selection process**: how many candidates, how they are chosen, on which data, and what is reported.
3. **The error criterion**: false positive rate of the reported claim, familywise error, or false discovery rate; and the nominal level.
4. **Repetitions and Monte Carlo error**: with R repetitions a rate p has standard error √(p(1 − p)/R); R = 10,000 gives about 0.22 percentage points at p = 5 %. Every rate is reported with its Wilson 95 % interval, the seed and the library versions.
5. **What the scenario cannot show**: the DGP's limits, written next to the result.

No common 5 % threshold is attached to DSR or PBO across scenarios; each scenario names its own criterion.

## 3. Data-generating processes

Daily returns of T = 252 × years observations, candidates K ∈ {1, 10, 100, 1,000}.

| id | Process | Why |
|---|---|---|
| N0 | IID normal, mean 0 | the baseline every formula assumes |
| N1 | IID Student t (ν = 4) and a skewed variant, mean 0 | PSR uses skewness and kurtosis |
| N2 | AR(1), φ = 0.2 | serial dependence the Lo line can see |
| N3 | AR(2) with φ1 = 0, φ2 = 0.3 (so ρ1 = 0, ρ2 = 0.3) | dependence the `ρ1` trigger misses |
| N4 | overlapping holdings: sums of h = 5 IID days (an MA(4)) | the label overlap of 5.8 |
| N5 | two-state regime switch in volatility, mean 0 | non-stationarity |
| N6 | GARCH(1,1) with α = 0.1, β = 0.85, mean 0: returns serially uncorrelated, squared returns dependent | changing volatility without dependence in the returns |
| C1 | K candidates with one common factor, pairwise correlation ρ ∈ {0, 0.5, 0.9}; and exact duplicates | the cohort's N against effectively fewer trials |
| A1 | one candidate of K with a true mean (annualised Sharpe 0.5 and 1.0) on top of N0–N5 | power |

Panel rows are not independent evidence: a scenario with many instruments per date counts dates (and clusters of correlated instruments), not rows.

## 4. Scenarios

| id | Scenario | Compared | Expected under the null |
|---|---|---|---|
| S1 | one candidate chosen on research data, tested once on independent final data | rejection rate of the final test | the nominal level, whatever K was (the research-data search does not count in N) |
| S2 | K predeclared candidates evaluated on the same final data, the best reported | unadjusted, DSR (N = K), BHY over K | unadjusted grows with K; DSR and BHY near their nominal criteria under N0, measured under C1 and N2–N5 |
| S3 | the final result is seen, the candidate is changed, the final data is used again | rejection rate of the last reported test | inflated; a cumulative N shown as a diagnostic does not restore the nominal level, and the report must say the data was reused |
| S4 | feature selection or preprocessing on all data, then a validation split; versus the same steps inside each training fold | estimated OOS performance with pure-noise features | the global version is optimistic; the in-fold version is not |
| S5 | one fixed candidate judged once at a fixed end date; versus checked every 21 days and stopped at the first nominal significance | false positive rate | the fixed date holds the level; stopping at the first significance does not |
| S6 | k metrics (Sharpe, IC, Sortino, …) computed and the best one reported | false positive rate | inflated with k |
| S7 | candidates or periods that failed (no returns, or a large drawdown) removed before the statistic | false positive rate and reported coverage | inflated, and the coverage line must show the removal |
| S8 | PSR(0) and MinTRL under N1–N5 for one candidate | rejection rate | measured; the IID assumption's cost under N2–N4 is the point |
| S9 | PBO under N0 with K noise candidates; and with one A1 candidate | PBO distribution | near 0.5 under the null (the IS winner's OOS rank is uniform); lower with a real candidate |
| S10 | tuning on a 2 % subsample of rows versus all rows, inside the allowed training range | agreement of parameter ranks, tail metrics, rare-event coverage | measured; no claim that a subsample preserves ranks or tails |
| S11 | the "dependence visible" rule of spec 5.7 (Ljung–Box Q over lags 1–10, p < 0.05) on one return series, T = 252 and 252 × 5 | how often the label appears under N0 and N6, and how often it catches N2 and N3 | near the nominal 5 % under N0; measured, likely higher, under N6 (the label text says it may reflect changing volatility); the 5 % is checked here, not assumed (#197) |

A scenario fails the procedure, not the strategy: a final test that does not reject is not proof that a strategy is false. Low power, a small economic effect, a violated assumption and a regime change are reported as separate possibilities.

## 5. Stages

**Stage A, now (outside the repository).** Small independent scripts with NumPy only, run on the maintainer's machine; their results are labelled "independent example, not NexusBT". Two exist from the 2026-11-04 review and were re-run by design session B on 2026-11-04 with the same seed (20261104) and NumPy 2.3.3, giving the same numbers:

- S5 under N0 (20,000 repetitions, 252 days, 12 looks, one-sided α = 0.05): fixed end date 4.825 % (965); stop at the first significance 18.095 % (3,619); 12 predeclared looks with Bonferroni 2.145 % (429). IID normal with known variance; not Sharpe inference and not dependent returns.
- S1 and S2 under N0 (20,000 repetitions, z-scores): choose on research data and test once, K = 1, 10, 1,000 → 5.2 %, 4.9 %, 5.1 %; choose the best on the test data → 5.2 %, 40.3 %, 100 % (exact familywise error 1 − 0.95^K = 5 %, 40.1 %, 100 %).
- Interaction input (D11): x1 and x2 each −1 or +1 with equal probability, y = x1·x2: both marginal correlations are 0, the product predicts Y exactly. A single-IC gate would drop both inputs; the spec has none (gates are display only).

**Stage B, after M6 (the engine).** The same DGPs written as synthetic TDS packages (4.8) and run through `evaluate` and `backtest(method=…)`, so that the engine's DSR, PBO and BHY, and its cohort and selection records, are what is measured. These become 8.3 property rows when the M6 statistics tickets are cut; this file proposes them and does not edit the spec.

## 6. Not covered

Real market data, the engine's own error rates (stage B does not exist yet), sequential procedures (confidence sequences, alpha spending) and reality-check tests (SPA, White), which wait for the scope decision in the statistics record, and any claim of usability.
