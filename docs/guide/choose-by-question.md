# Choose a tool by your question

> **Draft** (design review item D19, #219). The engine does not exist yet, so no
> code on this page has been run; none of it carries the `<!-- test -->` mark of
> spec 8.5, and the ticket that turns on each feature adds the mark with its
> output block. Where a line rests on a decision that is not yet in the spec, it
> says **not yet in the spec** and names the issue. The spec
> (`docs/spec/engine-spec-v3.4.md`) is the source of truth; when this page and
> the spec differ, the spec is right. The order of the questions, the choice of
> no guide command in v1 (this document and `--help` only) and the `next` line
> on the Run first screen were decided 2026-11-04 in #218.

You do not need to know the name of a statistical method to use NexusBT. Start
from what you want to know. Each entry below says which evaluation or
diagnostic fits, why, what it needs, and what it **cannot** tell you. You can
skip entries, come back to them in any order, or go straight to the expert
setting named at the end of each one.

The plain call is always enough to start, and nothing on this page is
required:

```python
import nexusbt as nx

run = nx.backtest(strategy, start="2010-01-01", end="2020-12-31")  # method="linear"
```

A user who never runs a final test is a normal user. The eight steps of a
research loop (question, data and evaluation boundaries, free exploration, the
full procedure, an outside evaluation of that procedure, costs and risk, a final
test of a fixed policy, paper trading) are a map, not an order the engine
enforces.

**What this page never does.** It does not recommend a method because it gave
the best number: choosing the metric, the method or the period after seeing the
results is itself a choice made on the data. It gives no "safe strategy" badge
and no general probability of overfitting. Every diagnostic answers one narrow
question about one series and one comparison set (spec 6.3), and none has a pass
threshold.

## Contents

1. [I just want to see how this rule did in the past](#replay)
2. [Is this signal worth anything before I build on it?](#signal)
3. [I compared several settings on the same data](#compared)
4. [I will retrain or re-choose periodically](#periodic)
5. [I want to check on data I have not looked at](#unseen)
6. [I want to raise the costs or the capital](#costs)
7. [I need many test paths from limited history](#paths)
8. [A number says n/a, or something could not be computed](#na)
9. [Which number is the one I asked for?](#which)

<a id="replay"></a>
## 1. I just want to see how this rule did in the past

- **Use**: `nx.backtest(strategy, start=, end=)`, `method="linear"` (the default). CLI: `nexusbt backtest FILE`.
- **Why**: one account, one pass, real fills and costs. The first screen already says which data, period, execution, costs and assumptions the result rests on (spec 3.9), and the run is saved so it can be rerun (5.9).
- **Needs**: a strategy and a snapshot. No study, plan or hypothesis object.
- **Cannot tell you**: that the result will repeat, or that the rule was not shaped by looking at this same data. The `evaluation` line says `research data` for that reason.
- **Read first**: the `period`, `execution`, `costs` and `assumptions` lines, then CAGR, maximum drawdown and the cost lines. **Not yet in the spec** (#150): the line counting hypothetical exits at a past close and their P&L share.
- **Next**: tried several versions of the rule? Go to 3. Want the same rule under higher costs? Go to 6.

<a id="signal"></a>
## 2. Is this signal worth anything before I build on it?

- **Use**: `nx.evaluate(factor)`. CLI: `nexusbt evaluate FILE`.
- **Why**: it measures the signal against a forward return without building a portfolio: the information coefficient (IC) per decision, its Newey–West t, the quantile spread, turnover and coverage (5.8).
- **Needs**: a factor; the default label is the holding return from the next open to the next decision's open (the `label` line says which return, over what interval, and when it became known).
- **Cannot tell you**: profit after costs (an IC is not a P&L); whether the signal will hold. The BHY-adjusted p counts only the factor candidates recorded in this cohort. The `gates` line is display only: a weak IC alone does not bar a factor from a composite or from an ML model, and `evaluate` is never a required step before either.
- **Next**: `.to_strategy("strategies/x.py")` and entry 1.

<a id="compared"></a>
## 3. I compared several settings on the same data

- **Use**: put the settings in one `grid`: `nx.sweep(strategy, grid=)`, the same as `nx.backtest(strategy, method="cscv", grid=)`. CLI: `nexusbt sweep FILE --grid k=v1,v2`.
- **Why**: the best of many settings on the same data usually looks better than it will be. With a `grid` the engine knows the comparison set and reports PBO (CSCV) on it, and the DSR line names the N candidates of the cohort (6.2, 6.3).
- **Needs**: at least 2 settings and enough common dates (an even block count S ≥ 4 and at least 2S dates); otherwise the line says `n/a` with the reason.
- **Cannot tell you**: PBO is how often the in-sample best falls at or below the out-of-sample median when choosing on this matrix; it is not the probability that the strategy is real. The best score stays an exploration result. Runs that failed or were stopped count in the denominator of `with returns a/b`. Choices made outside the engine (another tool, an external optimizer's own search) are not seen: the line says "recorded by the engine". An external optimizer that calls `nx.backtest` makes one candidate per call; a protocol for external optimizers is v1.x (spec 12.1 DR16-1).
- **Next**: want each period's choice tested on the period after it? Go to 4.

<a id="periodic"></a>
## 4. I will retrain or re-choose periodically

- **Use**: `method="walk_forward"`, with a `grid` to re-choose settings and an `nx.ml.factor` to retrain a model. CLI: `--method walk_forward`.
- **Why**: each window chooses on its training range and is applied to the test range after it, with one account carried across windows, as live trading would (6.3a). ML training is forward-only (5.3.11).
- **Needs**: history for at least one training and one test window (default 5 years and 1 year).
- **Cannot tell you**: the stitched out-of-sample series is one history, not many. Each `grid` point is a candidate.
- **Not yet in the spec** (#216): the label "online" for a refit on labels confirmed inside a test window, and the provenance level of each fit.
- **Expert setting**: `splits.walk_forward(train=, test=, step=, anchored=, embargo=)`; `account="per_fold"` as a diagnostic.

<a id="unseen"></a>
## 5. I want to check on data I have not looked at

- **Use**: keep a segment back (`[split] segments`, run with `segment="test"`) and record what you will test before you look, with `nx.preregister(strategy, metric=, threshold=, segment=)`.
- **Why**: the `evaluation` line says `independent final test (look n)` only when this graph was preregistered before the segment was first shown in the research family, and every earlier look came from a preregistered graph (6.2, 6.4).
- **Needs**: a segment not yet run in this family, and your statement whether you saw it elsewhere (`exposed_elsewhere=`).
- **Cannot tell you**: once a segment has been seen, no statistic makes it unseen again; each further look raises the look number. Checking every day and stopping on a good day is a different procedure from one check at a fixed time (see the example "watch daily vs declare on a good day", spec 8.5).

<a id="costs"></a>
## 6. I want to raise the costs or the capital

- **Use**: the scenarios: the `cost sensitivity` line (0x, 1x, 2x), `--scenarios cost2x`, the `capacity` scenario.
- **Why**: the same canonical targets are run again through the account rules and execution under other costs or capital (5.7). A scenario is not a new candidate.
- **Cannot tell you**: whether you would have chosen another setting had costs been higher; the choice is not redone. For that, put the cost setting in a `grid` (entry 3).

<a id="paths"></a>
## 7. I need many test paths from limited history

- **Use**: `method="cpcv"`. CLI: `--method cpcv`.
- **Why**: it tests every group of the history several times with the other groups as training, giving a distribution of out-of-sample paths (6.3a).
- **Needs**: a decision grid long enough for `n_groups` groups (default 6 groups, 2 tested: 15 splits, 5 paths).
- **Cannot tell you**: the paths share data and fits, so their quantiles are not a confidence interval and the path count is not a sample size; the best path is never the result. A path is synthetic: holdings carry across group boundaries while the model that made them changes.
- **Not yet in the spec**: the purging interval covering every label in a test block (#149); strict in-sample scores for a `grid` with an ML factor (#215).
- **Expert setting**: `splits.cpcv(n_groups=, k_test=, embargo=)`.

<a id="na"></a>
## 8. A number says n/a, or something could not be computed

- **Read**: the reason after `n/a` (the E21 reasons of the 6.3 table, such as `T < 30` or `V[SR] needs ≥ 2 candidates`) and the `skipped:` line, which counts every row the engine processed less than planned, by reason (6.6).
- **Models and inputs from outside**: a pretrained model or an external input is shown as declared, not audited (ADR-0041); a model trained past the run's start fails with E48 unless you allow the overlap, and then the overlapping decisions are marked (E49).
- **Not yet in the spec** (#216): one marker per failure type instead of a single NaN (incomplete path, missing prediction, fit failure, ruin, unfilled, statistic unavailable), with the evaluation period and the denominator of valid samples; cash held for lack of a signal counts as cash return, not as a failure.

<a id="which"></a>
## 9. Which number is the one I asked for?

**Not yet in the spec** (#216 is decided; these names are from its decision,
before the spec edit). When you run a method other than `linear`, the result
keeps `Run.metrics` as the linear run with the strategy's default parameters,
labelled `reference`; the evaluation you asked for is `Run.primary`, the
statistics with their series and comparison set are `Run.diagnostics`, and what
the data exposure, preregistration, approximations and assumptions were is
`Run.provenance`. `metrics.json` gains an `evaluation_context` block, and the
CLI, HTML and CSV carry the same labels. Until that edit lands, spec 6.3a says
the headline metrics are the linear run and the method's results are in
`Run.validation`.
