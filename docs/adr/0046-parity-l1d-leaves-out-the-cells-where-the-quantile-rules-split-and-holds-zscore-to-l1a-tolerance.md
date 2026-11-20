# 46. L1-d parity: the cells where zipline's cross-section rules answer differently are left out, `zscore` is held to L1-a's tolerance

- Status: Accepted (2026-11-20, #253, the owner's approval)
- Date: 2026-11-20
- Spec: §8.1, §3.3, §5.4.2, §5.4.3, §9.7 (3), §10.1 (T1.18), V31-58

## Context

8.1's L1-d compares `top(N, mask=)`, `rank(ordinal, groupby=)`, `zscore`, `percentile_between` and `quantiles` with zipline 3.2.1, "sets and ranks exact". Read against zipline's source and run on synthetic `small` (#253), they differ in these ways, none an error of either engine:

- `quantiles(q)`. The engine (5.4.3, [11.4.5]): with the cell's mean rank r among the n finite cells, `min(q, max(1, ceil(r q / n)))`, labels 1..q. zipline: `pandas.qcut(row, q, labels=False)`, edges at numpy's linear quantiles of the values, right-closed, labels 0..q-1; when two edges are equal it raises `ValueError` and the pipeline stops. On distinct values the edge j of q moves a cell to the lower bucket in zipline when an integer lies in `((jn - q)/q, (jn - j)/q]`, an interval of length (q - j)/q: for q = 5, about 80%, 60%, 40% and 20% of cross-sections at the four edges. On distinct values 1..n, 473 of 695 (n, q) pairs with n up to 120 give some cell another bucket.
- `percentile_between(a, b)`. The engine (5.4.2): `p = 100 (r_average - 1) / (n - 1)`, `a <= p <= b`. zipline: `nanpercentile(a) <= x <= nanpercentile(b)` on the values. A tie group straddling a bound goes by its mean rank in the engine and by its value in zipline (1, 2, 2, 3 between 0 and 40: the engine takes 1, zipline 1, 2, 2); on distinct values numpy's interpolation can put a bound a rounding below a value whose p equals it (n = 91 between 30 and 70).
- `zscore`. Both are `(x - mean) / std` with ddof 0, but the engine adds in the 5.3.10 order (instrument_id order, left to right, two passes) and numpy adds pairwise. On 2000 random rows of 300 cells, 53 were bit-identical; the largest relative difference was 7.9e-12.
- `rank(groupby=)`. zipline passes each group to `scipy.stats.rankdata`, which (scipy 1.18.1) returns NaN for the whole group when one of its cells is NaN; the engine ranks the finite cells (5.4.2).
- A Filter outside its domain. The engine's cross-section Filter is unknown outside its mask (3.3); zipline's is false. At the final use both are not selected (5.4.1).
- The last session of an instrument. The engine's row holds it; zipline's D, the next session, does not (#252's `ENGINE_ONLY`), so the two cross-sections differ by that instrument.
- The input's last bits. zipline reads a price as its stored uint32 times 0.001 (`zipline/data/bcolz_daily_bars.py`), which is not always the nearest double of the 3-decimal price (16,643 of 122,501 US opens on `small`); 75 KR closes of the package carry the 1-ULP wobble the generator puts in on purpose to test grid snapping (4.8 (5), V31-05; 526000.0000000001). So `close / open` differs in its last bit on 125 KR and 17,691 US shared cells, and two values a rounding apart can change order: 3 pairs (5 cells) in KR, none in US.

## Decision

- L1-d's input is a ratio within one bar, `x = close.latest / open.latest`, and its groups `(high.latest / low.latest).quantiles(5)`: an adjustment multiplies every price of a bar, so ADR 0045's (A) and (B) do not reach them. `tiebreak = "id"` (8.1). The cases: `x.top(20, mask=x > 1)`, `x.rank("ordinal", mask=x.notnan(), groupby=groups)` (the mask keeps NaN out of zipline's groups and leaves the engine's result as it is), `x.zscore()`, `x.percentile_between(10, 90)`, `x.quantiles(5)`.
- Each left-out set is computed from the input alone: the test computes both rules from the input values, the engine's by the spec's formulas (5.4.3's bucket, 5.4.2's percentile, 3.7's order) over the engine's cross-section and zipline's over zipline's (the engine's without the instruments on their last session). Neither the engine's output nor zipline's is used to choose the cells left out, so a cell the engine gets wrong is compared, not left out:
  - `quantiles`: the cells whose 5.4.3 bucket and `qcut` bucket differ.
  - `percentile_between`: the cells the mean-rank rule and the value rule put on different sides of a bound.
  - `top`: the cells that the top 20 of the engine's cross-section and of zipline's do not share. It is compared as the set of true cells: unknown is not true.
  - `rank(groupby=)`: the cells whose ordinal rank in their group (by value, then `instrument_id`) differs between 5.4.3's groups over the engine's cross-section and `qcut`'s over zipline's. A member leaving the group ahead of a cell and another entering cancel out, so a cell after a moved one can keep its rank.
  - `zscore`: a session where zipline lacks an instrument with a finite x (on its last session) is left out: the mean and the deviation move every cell. A missing cell with NaN x is in neither cross-section.
  - Every case but `zscore`: a cell within `1e-14 |x|` of another cell's value and not equal to it (a near tie, which the last bits can reorder: the two sides' x differ by at most about 4e-16, relative). The test checks that x and high / low agree within L1-a's tolerance, the premise of this rule.
- The rest is compared: sets and ranks exactly (zipline's quantile label + 1 against the engine's), `zscore` within L1-a's `|a - b| <= 1e-9 + 1e-9 |b|`, NaN on both sides agreeing.
- The test fixes, for each case and market, the cells compared and left out; a change in any count fails it. The evidence file carries them.

## Considered options

- Leave out a whole group of `rank(groupby=)` when its members differ (58% of KR cells, 54% of US), or every cell after a moved one (34%, 32%), against 27% and 25%. Not taken: a member below the moved cell, or one whose leaving and entering members cancel out, keeps its rank under both rules.
- Leave out a whole session with an instrument on its last session, in every case: 8.4% (KR) and 12.0% (US) of the cells. Not taken: for the others zipline's rule on its own cross-section gives the cells that differ, and for `zscore` a missing cell with NaN x moves nothing.
- Hold `zscore` exactly. Not taken: it would need numpy's summation order, and 5.3.10 fixes the engine's.
- Use a classifier both sides compute alike for `groupby`. Not available: the engine's only classifier from a Factor is `quantiles` (`@nx.classifier` is not built), and the engine's `Meta` classifiers have no zipline column.
- Leave `quantiles` out of L1-d until V31-58. Not taken: T1.18 names it, and where the rules agree the comparison checks the masks and the alignment.

## Consequences

- On `small`, from the input values (`L1D_EXPECTED` fixes them; the rest agrees): `quantiles` leaves out 1,965 of 58,259 KR cells (3.4%) and 1,941 of 98,622 US cells (2.0%); `percentile_between` 19 and 18; `top` 22 and 10; `rank(groupby=)` 15,811 (27.1%) and 24,939 (25.3%); `zscore` 2,382 (4.1%) and 5,808 (5.9%).
- Ties are not tested here where they move a bucket edge or a percentile bound; they are tested by `tests/unit/compute/test_crosssection.py::test_quantiles_preserve_ties` (5.4.3) and `::test_percentile_between_includes_both_ends` (5.4.2), and `rank` and `top` ties by T-11 and T-27; ties of the input that no rule moves (291 tied KR cells, 3 US) are compared here. No golden hand calculation (`tests/golden/cases/`) covers `quantiles`, `percentile_between` or `zscore`: the quantile one is V31-58's remaining work (v1.x, before T7.V); the other two have no item.
- 8.1's L1-d row reads "sets and ranks exact; `zscore` values `|a−b| ≤ 1e-9 + 1e-9·|b|`", and T1.18's done-means "the L1-d cases agree as 8.1's table says": T1.18's "exactly equal" cannot be implemented as written for `zscore`, a defect under #43's M1 spec freeze (2026-11-04).

Relation to ADR 0045: 0045 names where L1-a and L1-b's semantics are not equal; this record does it for L1-d.
