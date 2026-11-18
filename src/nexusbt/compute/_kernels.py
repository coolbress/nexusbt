"""The 2.4 `nx.compute._kernels` seam: window and cross-section kernels, arrays in, arrays out.

Arguments and results are numpy arrays (or Arrow arrays sharing their buffers), int and float
scalars and integer codes: no Python objects, callbacks or dicts, so another implementation, a
Numba fast kernel or a Rust crate, replaces a kernel with the same signature (R3-26, ADR-0016).

These are the reference. A sum is the left fold in ascending row order, `acc = acc + x[r]` from
0.0 (5.3.10 (1), ADR-0019 definition A), as an explicit loop: never numpy's pairwise `np.sum`,
whose order changes with the array's length and alignment (5.3.10 (4)). A transcendental
function is the compiled element function of `_elem` (5.3.10 2a).
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

from nexusbt.compute import _elem

F64 = npt.NDArray[np.float64]
I64 = npt.NDArray[np.int64]
Mask = npt.NDArray[np.bool_]
Codes = npt.NDArray[np.int32]

#: Integer codes of the one-argument transcendental functions, for `elementwise`: each code is
#: its function's position in `_UNARY`.
LOG, LOG1P, EXP = 0, 1, 2
_UNARY = ("log", "log1p", "exp")


def fold_sum(x: F64) -> float:
    """The left fold of `x` in order, from 0.0."""
    acc = 0.0
    for value in x.tolist():
        acc = acc + value
    return acc


def window_sum(values: F64, window: int, rows: npt.NDArray[np.int64]) -> F64:
    """For each row r of `rows`, the left fold of `values[r-window+1 .. r]` per column; NaN
    where the window starts before row 0, as nothing is there to read."""
    if window < 1:
        raise ValueError(f"a window has at least one row, not {window}")
    if rows.size and int(rows.max()) >= len(values):
        raise ValueError(f"rows must lie before row {len(values)}, not {rows.max()}")
    out = np.full((len(rows), values.shape[1]), np.nan)
    for i, r in enumerate(rows.tolist()):
        if r - window + 1 < 0:
            continue
        acc = np.zeros(values.shape[1])
        for s in range(r - window + 1, r + 1):
            acc = acc + values[s]  # each column is its own left fold
        out[i] = acc
    return out


# The built-in factors' window kernels (3.4) take one `(W, N)` window, row t last, and return
# `(N,)`. `nanmean`, `nanstd` and `nansum` are "the sum of the non-NaN values added from the left
# in ascending row order" (3.4); a variance is two passes, the mean first (5.3.10 (2)).


def _finite_fold(x: F64) -> tuple[F64, npt.NDArray[np.int64]]:
    """Per column, the left fold of the finite cells and their count."""
    seen = np.isfinite(x)
    acc, n = np.zeros(x.shape[1]), np.zeros(x.shape[1], dtype=np.int64)
    for r in range(len(x)):
        acc = acc + np.where(seen[r], x[r], 0.0)
        n = n + seen[r]
    return acc, n


def window_returns(x: F64) -> F64:
    """`Returns`: `x[-1]/x[0] - 1`, NaN when either end is NaN."""
    found: F64 = x[-1] / x[0] - 1.0
    return found


def window_nanmean(x: F64) -> F64:
    """`SimpleMovingAverage`, `AverageTradedValue`: the mean of the finite cells; NaN when none."""
    acc, n = _finite_fold(x)
    found: F64 = np.where(n > 0, acc / np.maximum(n, 1), np.nan)
    return found


def window_nansum_mean(x: F64) -> F64:
    """`AverageDollarVolume`: the finite cells' sum over all W rows, a NaN counting as 0."""
    acc, _ = _finite_fold(x)
    found: F64 = acc / len(x)
    return found


def window_nanstd(x: F64, ddof: int) -> F64:
    """`RollingStd` (ddof 1): the finite cells' standard deviation; NaN with `ddof` or fewer.
    Equal cells have 0 even when the folded mean misses them by a rounding, as in `zscore`."""
    acc, n = _finite_fold(x)
    deviation = x - acc / np.maximum(n, 1)
    squares, _ = _finite_fold(deviation * deviation)
    low, high = np.full(x.shape[1], np.inf), np.full(x.shape[1], -np.inf)
    for r in range(len(x)):  # NaN is skipped by fmin and fmax; an infinite cell is not finite
        finite = np.where(np.isfinite(x[r]), x[r], np.nan)
        low, high = np.fmin(low, finite), np.fmax(high, finite)
    equal = low == high
    found: F64 = np.where(n > ddof, np.sqrt(squares / np.maximum(n - ddof, 1)), np.nan)
    return np.where(equal & (n > ddof), 0.0, found)


def window_annualized_volatility(x: F64, annualization_factor: float) -> F64:
    """`AnnualizedVolatility` over W + 1 prices: the W daily returns' standard deviation with
    ddof 0, times `sqrt(annualization_factor)`; NaN when no return is finite."""
    daily: F64 = x[1:] / x[:-1] - 1.0
    found: F64 = window_nanstd(daily, 0) * np.sqrt(annualization_factor)
    return found


def ewma_weights(window: int, decay_rate: float) -> F64:
    """`EWMA`'s weights `decay_rate ** (W-1-i)` for rows i = 0..W-1, row t last with weight 1;
    computed once with the compiled `pow` and passed to `window_ewma` as a constant (3.4)."""
    if window < 1:
        raise ValueError(f"a window has at least one row, not {window}")
    exponents = np.arange(window - 1, -1, -1, dtype=np.float64)
    found: F64 = _elem.power(np.full(window, float(decay_rate)), exponents)
    found.flags.writeable = False
    return found


def window_ewma(x: F64, weights: F64) -> F64:
    """`EWMA`: `sum(x * w) / sum(w)`, each a left fold in row order; NaN when any cell is NaN."""
    acc, total = np.zeros(x.shape[1]), fold_sum(weights)
    for r in range(len(x)):
        acc = acc + x[r] * weights[r]
    found: F64 = acc / total
    return found


def window_vwap(close: F64, volume: F64) -> F64:
    """`VWAP`: `sum(close * volume) / sum(volume)` over the rows whose close and volume are both
    finite; NaN with no such pair or when their volume sums to 0 (3.4, #278)."""
    pair = np.isfinite(close) & np.isfinite(volume)
    paid, n = _finite_fold(np.where(pair, close * volume, np.nan))
    traded, _ = _finite_fold(np.where(pair, volume, np.nan))
    some = (n > 0) & (traded != 0)
    found: F64 = np.where(some, paid / np.where(some, traded, 1.0), np.nan)
    return found


def window_rsi(x: F64) -> F64:
    """`RSI`: with `d` the W - 1 differences, `up` the mean of `max(d, 0)` and `dn` that of
    `-min(d, 0)`, each over the finite differences (a clipped 0 counts); `100 - 100/(1 + up/dn)`,
    as zipline: 100 when only `dn` is 0, NaN when both are."""
    d = x[1:] - x[:-1]
    up, dn = window_nanmean(np.maximum(d, 0.0)), np.abs(window_nanmean(np.minimum(d, 0.0)))
    with np.errstate(divide="ignore", invalid="ignore"):
        found: F64 = 100.0 - 100.0 / (1.0 + up / dn)
    return found


def window_max_drawdown(x: F64) -> F64:
    """`MaxDrawdown`: the largest `(peak - x) / peak` over the finite cells, `peak` the running
    maximum of the finite cells up to the row; NaN when no cell is finite."""
    peak, worst = np.full(x.shape[1], np.nan), np.full(x.shape[1], np.nan)
    for r in range(len(x)):  # fmax skips NaN; an infinite cell is not finite
        finite = np.where(np.isfinite(x[r]), x[r], np.nan)
        peak = np.fmax(peak, finite)
        worst = np.fmax(worst, (peak - finite) / peak)
    return worst


def elementwise(code: int, x: F64) -> F64:
    """`log`, `log1p` or `exp` of each element, by its code, with the compiled function."""
    if not 0 <= code < len(_UNARY):
        raise ValueError(f"no element function has code {code}")
    found: F64 = getattr(_elem, _UNARY[code])(x)  # looked up at the call: the one compiled ufunc
    return found


def power(base: F64, exponent: F64) -> F64:
    """`base ** exponent` element by element, with the compiled function."""
    found: F64 = _elem.power(base, exponent)
    return found


# Three-valued kernels (3.3, 5.4.1, V31-21): a Filter is two boolean arrays of one shape, its
# `value` and its `valid` mask; a cell is unknown where it is not valid, and its value there is
# false, so a result's value is true only where the cell is known to be true.

#: The comparison codes of `compare`: `<`, `<=`, `>`, `>=`, `==`, `!=`.
LT, LE, GT, GE, EQ, NE = range(6)
_COMPARE = (np.less, np.less_equal, np.greater, np.greater_equal, np.equal, np.not_equal)


def compare(code: int, x: F64, y: F64) -> tuple[Mask, Mask]:
    """`x <op> y` by its code; unknown where either side is NaN."""
    if not 0 <= code < len(_COMPARE):
        raise ValueError(f"no comparison has code {code}")
    valid = ~(np.isnan(x) | np.isnan(y))
    value: Mask = _COMPARE[code](x, y) & valid
    return value, valid


def codes_in(codes: Codes, wanted: Codes) -> tuple[Mask, Mask]:
    """A Classifier's codes in `wanted` (`eq`, `element_of`); unknown on the missing code -1."""
    valid = codes != -1
    value: Mask = np.isin(codes, wanted) & valid
    return value, valid


def kleene_and(a: Mask, a_ok: Mask, b: Mask, b_ok: Mask) -> tuple[Mask, Mask]:
    """`a & b`: false when either is known false, true when both are known true, else unknown."""
    true = a & a_ok & b & b_ok
    return true, true | (a_ok & ~a) | (b_ok & ~b)


def kleene_or(a: Mask, a_ok: Mask, b: Mask, b_ok: Mask) -> tuple[Mask, Mask]:
    """`a | b`: true when either is known true, false when both are known false, else unknown."""
    true = (a & a_ok) | (b & b_ok)
    return true, true | (a_ok & ~a & b_ok & ~b)


def kleene_all(value: Mask, valid: Mask) -> tuple[Mask, Mask]:
    """`kleene_and` of a `(W, N)` window's rows, per column: `Filter.all(W)`."""
    out, ok = np.ones(value.shape[1], dtype=bool), np.ones(value.shape[1], dtype=bool)
    for r in range(value.shape[0]):
        out, ok = kleene_and(out, ok, value[r], valid[r])
    return out, ok


def kleene_any(value: Mask, valid: Mask) -> tuple[Mask, Mask]:
    """`kleene_or` of a `(W, N)` window's rows, per column: `Filter.any(W)`."""
    out, ok = np.zeros(value.shape[1], dtype=bool), np.ones(value.shape[1], dtype=bool)
    for r in range(value.shape[0]):
        out, ok = kleene_or(out, ok, value[r], valid[r])
    return out, ok


# Cross-section kernels (5.4.2, 5.4.3) take one market's (or `across_markets`') cells at one
# decision in memory order: the values `x`, the `mask` (true where the cell is in the term's
# domain), the group codes `groups` (all 0 without a `groupby`, -1 where the group is unknown)
# and either `order`, the memory positions in ascending `instrument_id` order, or `tie`, each
# cell's place in the tie-break key's order (`_crosssection` builds both from the ids). A cell
# is in its group's cross-section when its mask is true, its value finite and its group known.
# Reductions gather the cells in `order` and left-fold them (5.3.10 (3), ADR-0019), so a
# shuffled memory order gives the same bits (INV-04). Each kernel also returns how many cells
# it left out for an unknown group (`UnknownGroup`, 3.3).

#: The `rank` methods of 3.3, and the two directions of `rank` and of a selection.
ORDINAL, AVERAGE, MIN, MAX, DENSE = _METHODS = (0, 1, 2, 3, 4)
ASCENDING, DESCENDING = 0, 1


def _sections(x: F64, mask: Mask, groups: Codes, order: I64) -> tuple[list[I64], int]:
    """Each known group's cross-section, its memory positions in `order`; and the number of
    cells left out for an unknown group."""
    seq = order[(mask & np.isfinite(x))[order]]
    codes = groups[seq]
    unknown = int(np.count_nonzero(codes < 0))
    return [seq[codes == g] for g in np.unique(codes[codes >= 0])], unknown


def _mean(values: F64) -> float:
    return fold_sum(values) / len(values)


def _ordered(x: F64, seq: I64, tie: I64, direction: int) -> tuple[I64, I64, I64, I64]:
    """The cells of `seq` by score in `direction`, equal scores by ascending tie place; and for
    each, the first and last place (1-based) of its run of equal scores and the run's number."""
    if direction not in (ASCENDING, DESCENDING):
        raise ValueError(f"no direction has code {direction}")
    scores = -x[seq] if direction == DESCENDING else x[seq]
    found = seq[np.lexsort((tie[seq], scores))]
    sorted_scores = x[found]
    starts = np.flatnonzero(np.r_[True, sorted_scores[1:] != sorted_scores[:-1]])
    run = np.searchsorted(starts, np.arange(len(found)), side="right") - 1
    ends = np.r_[starts[1:], len(found)]
    return found, starts[run] + 1, ends[run], run


def demean(x: F64, mask: Mask, groups: Codes, order: I64) -> tuple[F64, int]:
    """`x - mean` within each group (5.4.2); NaN outside the cross-section."""
    out = np.full(len(x), np.nan)
    sections, unknown = _sections(x, mask, groups, order)
    for seq in sections:
        out[seq] = x[seq] - _mean(x[seq])
    return out, unknown


def zscore(x: F64, mask: Mask, groups: Codes, order: I64) -> tuple[F64, int]:
    """`(x - mean) / std` within each group, std with ddof=0 by two passes (5.3.10 (2)); all NaN
    where std is 0 or the group has fewer than two cells (5.4.2). Equal values have std 0 even
    when the folded mean misses them by a rounding (0.1 three times)."""
    out = np.full(len(x), np.nan)
    sections, unknown = _sections(x, mask, groups, order)
    for seq in sections:
        if len(seq) < 2 or x[seq].min() == x[seq].max():
            continue
        deviation = x[seq] - _mean(x[seq])
        std = np.sqrt(_mean(deviation * deviation))
        if std > 0:
            out[seq] = deviation / std
    return out, unknown


def winsorize(x: F64, mask: Mask, groups: Codes, low: float, high: float) -> tuple[F64, int]:
    """`clip(x, q_low, q_high)` within each group, q numpy's linear quantiles (5.4.2), `low`
    and `high` fractions with `0 <= low <= high <= 1`; NaN outside the cross-section. A
    quantile sums nothing, so the memory order does not move it."""
    if not 0 <= low <= high <= 1:
        allowed = "fractions 0 <= min <= max <= 1 (1% is 0.01)"
        raise ValueError(f"winsorize takes {allowed}, not {low}, {high}")
    out = np.full(len(x), np.nan)
    sections, unknown = _sections(x, mask, groups, np.arange(len(x)))
    for seq in sections:
        bounds = np.quantile(x[seq], [low, high], method="linear")
        out[seq] = np.clip(x[seq], bounds[0], bounds[1])
    return out, unknown


def percentile_between(x: F64, mask: Mask, low: float, high: float) -> Mask:
    """True where `low <= p <= high` (5.4.2), p = `100 (r - 1) / (n - 1)` with r the cell's
    mean rank among the n cells, 100 when n = 1; `0 <= low <= high <= 100`. False outside the
    cross-section."""
    if not 0 <= low <= high <= 100:
        raise ValueError(f"percentiles are 0 <= min <= max <= 100, not {low}, {high}")
    out = np.zeros(len(x), dtype=bool)
    every = np.zeros(len(x), dtype=np.int32)
    for seq in _sections(x, mask, every, np.arange(len(x)))[0]:
        found, lo, hi, _ = _ordered(x, seq, every.astype(np.int64), ASCENDING)
        n = len(found)
        p = 100 * (lo + hi - 2) / (2 * (n - 1)) if n > 1 else np.full(n, 100.0)
        out[found] = (low <= p) & (p <= high)
    return out


def rank(
    x: F64, mask: Mask, groups: Codes, tie: I64, method: int, direction: int
) -> tuple[F64, int]:
    """Ranks 1..n within each group (5.4.2), 1 the smallest, or the largest when `DESCENDING`.
    `ORDINAL` breaks ties by ascending tie place; `AVERAGE`, `MIN`, `MAX` and `DENSE` are
    scipy's `rankdata`."""
    if method not in _METHODS:
        raise ValueError(f"no rank method has code {method}")
    out = np.full(len(x), np.nan)
    sections, unknown = _sections(x, mask, groups, np.argsort(tie))
    for seq in sections:
        found, lo, hi, run = _ordered(x, seq, tie, direction)
        if method == ORDINAL:
            out[found] = np.arange(1, len(found) + 1)
        elif method == AVERAGE:
            out[found] = (lo + hi) / 2
        else:
            out[found] = {MIN: lo, MAX: hi, DENSE: run + 1}[method]
    return out, unknown


def select(
    x: F64, mask: Mask, groups: Codes, tie: I64, n: int, direction: int
) -> tuple[Mask, int, int]:
    """`top(n)` when `DESCENDING`, `bottom(n)` when `ASCENDING` (5.4.2, 3.7): the first n of each
    group by score, equal scores by ascending tie place, all of them when fewer are finite. Also
    `n_tied_at_cutoff`: the size of each tie group straddling a cutoff (the score of the last one
    taken, when one with that score is left out), summed over the groups."""
    if n < 0:
        raise ValueError(f"a selection takes at least zero cells, not {n}")
    picked, tied = np.zeros(len(x), dtype=bool), 0
    sections, unknown = _sections(x, mask, groups, np.argsort(tie))
    for seq in sections:
        found, lo, hi, _ = _ordered(x, seq, tie, direction)
        picked[found[:n]] = True
        if 0 < n < len(found) and hi[n - 1] > n:
            tied += int(hi[n - 1] - lo[n - 1] + 1)
    return picked, tied, unknown


def quantiles(x: F64, mask: Mask, groups: Codes, order: I64, bins: int) -> tuple[Codes, int]:
    """Tie-preserving quantiles (5.4.3): for each cell, with its mean rank r among the group's
    n cells, `min(bins, max(1, ceil(r * bins / n)))`, 1..bins; -1 outside the cross-section.
    Integer arithmetic on 2r, so no rounding moves a cell across a bucket edge."""
    if bins < 1:
        raise ValueError(f"quantiles need at least one bin, not {bins}")
    out = np.full(len(x), -1, dtype=np.int32)
    sections, unknown = _sections(x, mask, groups, order)
    for seq in sections:
        found, lo, hi, _ = _ordered(x, seq, np.argsort(order), ASCENDING)
        twice_r, twice_n = lo + hi, 2 * len(found)
        out[found] = np.clip(-(-twice_r * bins // twice_n), 1, bins)
    return out, unknown
