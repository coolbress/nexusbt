"""Cross-sectional kernels of 5.4.2 and 5.4.3, reduced in sorted `instrument_id` order (5.3.10
(3), ADR-0019), T1.11 (#244)."""

from __future__ import annotations

import numpy as np
import pytest

from nexusbt.compute import _crosssection as xs
from nexusbt.compute import _kernels as k
from nexusbt.contracts import TiebreakPolicy

pytestmark = pytest.mark.unit

NAN = np.nan


def everyone(n: int) -> tuple[np.ndarray, np.ndarray]:
    """No mask and no groupby: every cell in, one group."""
    return np.ones(n, dtype=bool), np.zeros(n, dtype=np.int32)


def test_reduction_in_instrument_id_order() -> None:
    """The mean folds in id order whatever the memory order: in id order the 1 is lost in 1e16
    (mean 0); folded in this memory order the 1e16s cancel first (mean 1/3)."""
    ids = ["A", "C", "B"]
    x = np.array([1e16, -1e16, 1.0])  # by id: A 1e16, B 1, C -1e16
    mask, groups = everyone(3)
    out, unknown = k.demean(x, mask, groups, xs.sorted_order(ids))
    assert out.tolist() == [1e16, -1e16, 1.0]  # mean 0.0 exactly
    assert unknown == 0
    shuffled = [2, 0, 1]
    again, _ = k.demean(x[shuffled], mask, groups, xs.sorted_order([ids[i] for i in shuffled]))
    assert again.tobytes() == out[shuffled].tobytes()


def test_zscore_ddof0_zero_var_nan() -> None:
    """Population std (ddof=0): 1, 2, 3, 6 has mean 3 and variance 14/4. Group 1 has no spread,
    so all its cells are NaN; group 2 has one cell, NaN; outside the mask and NaN cells stay NaN.
    Shuffling the memory order gives the same bits."""
    ids = ["A", "B", "C", "D", "E", "F", "G", "H", "I"]
    x = np.array([1.0, 2.0, 3.0, 6.0, 5.0, 5.0, 7.0, 100.0, NAN])
    mask = np.array([True] * 7 + [False, True])
    groups = np.array([0, 0, 0, 0, 1, 1, 2, 0, 0], dtype=np.int32)
    out, _ = k.zscore(x, mask, groups, xs.sorted_order(ids))
    sd = np.sqrt(14 / 4)
    assert out[:4].tolist() == [-2 / sd, -1 / sd, 0.0, 3 / sd]
    assert np.isnan(out[4:]).all()
    # 0.1 * 3 / 3 is not 0.1: the deviations are rounding, not spread, and still std = 0
    out, _ = k.zscore(np.full(3, 0.1), *everyone(3), xs.sorted_order(list("ABC")))
    assert np.isnan(out).all()
    rng = np.random.default_rng(7)
    x = rng.standard_normal(500) * 1e6
    ids = [f"KR:T{i:05d}" for i in range(500)]
    mask, groups = everyone(500)
    out, _ = k.zscore(x, mask, groups, xs.sorted_order(ids))
    p = rng.permutation(500)
    again, _ = k.zscore(x[p], mask, groups, xs.sorted_order([ids[i] for i in p]))
    assert again.tobytes() == out[p].tobytes()


def test_unknown_group_counted() -> None:
    """3.3, 5.4.2: cells in group -1 are left out, NaN, and counted; a cell outside the mask or
    without a value is not in the cross-section, so it is not counted."""
    x = np.array([1.0, 2.0, 3.0, 4.0, 5.0, NAN])
    mask = np.array([True, True, True, True, False, True])
    groups = np.array([0, -1, 0, -1, -1, -1], dtype=np.int32)
    out, unknown = k.demean(x, mask, groups, xs.sorted_order(list("ABCDEF")))
    assert unknown == 2
    assert out[[0, 2]].tolist() == [-1.0, 1.0]
    assert np.isnan(out[[1, 3, 4, 5]]).all()


TIED = ["KR:T00003", "KR:T00001", "KR:T00002"]  # equal scores, memory order shuffled


@pytest.mark.parametrize(
    ("policy", "expected"),
    [(TiebreakPolicy.HASH, [3, 2, 1]), (TiebreakPolicy.ID, [3, 1, 2])],  # T-27's two orders
)
def test_rank_ordinal_uses_tiebreak_key(policy: TiebreakPolicy, expected: list[int]) -> None:
    """3.7, 5.4.2: ordinal ties follow the tie key, ascending or not (T-27: hash order T00002,
    T00001, T00003; id order T00001, T00002, T00003)."""
    x = np.ones(3)
    mask, groups = everyone(3)
    tie = xs.tie_order(TIED, policy)
    for direction in (k.ASCENDING, k.DESCENDING):
        out, _ = k.rank(x, mask, groups, tie, k.ORDINAL, direction)
        assert out.tolist() == expected


def test_top_stable_ties() -> None:
    """5.4.2, 3.7: `top(N)` takes score descending, tie place ascending; `bottom(N)` ascending.
    The pick does not move when the memory order does, and `n_tied_at_cutoff` counts the tie
    group that straddles the cutoff, summed over groups; fewer finite scores than N: all."""
    ids = ["E", "B", "D", "A", "C", "F", "G", "H"]
    x = np.array([9.0, 4.0, 4.0, 4.0, 1.0, NAN, 3.0, 2.0])
    mask = np.ones(8, dtype=bool)
    groups = np.array([0, 0, 0, 0, 0, 0, 1, 1], dtype=np.int32)
    tie = xs.tie_order(ids, TiebreakPolicy.ID)
    picked, tied, _ = k.select(x, mask, groups, tie, 3, k.DESCENDING)
    assert sorted(ids[i] for i in np.flatnonzero(picked)) == ["A", "B", "E", "G", "H"]
    assert tied == 3  # A, B taken, D (4.0) left out; group 1 has two, both taken
    picked, tied, _ = k.select(x, mask, groups, tie, 4, k.DESCENDING)
    assert sorted(ids[i] for i in np.flatnonzero(picked)) == ["A", "B", "D", "E", "G", "H"]
    assert tied == 0  # the cutoff falls between 4.0 and 1.0
    picked, tied, _ = k.select(x, mask, groups, tie, 1, k.ASCENDING)
    assert sorted(ids[i] for i in np.flatnonzero(picked)) == ["C", "H"]
    assert tied == 0
    p = np.array([3, 7, 0, 5, 1, 6, 2, 4])
    again, tied, _ = k.select(x[p], mask, groups[p], tie[p], 3, k.DESCENDING)
    assert again.tolist() == k.select(x, mask, groups, tie, 3, k.DESCENDING)[0][p].tolist()
    assert tied == 3
    with pytest.raises(ValueError, match="at least zero"):
        k.select(x, mask, groups, tie, -1, k.DESCENDING)


def test_quantiles_preserve_ties() -> None:
    """5.4.3: bucket = min(q, max(1, ceil(r q / n))) with the mean rank r. Scores 1, 2, 2, 2, 5,
    6 have mean ranks 1, 3, 3, 3, 5, 6; with q = 3, n = 6: ceil(r / 2) = 1, 2, 2, 2, 3, 3. The
    three 2.0 share a bucket, so the buckets hold 1, 3 and 2 cells; missing is -1."""
    x = np.array([2.0, 6.0, 1.0, 2.0, NAN, 5.0, 2.0])
    mask, groups = everyone(7)
    codes, _ = k.quantiles(x, mask, groups, xs.sorted_order(list("ABCDEFG")), 3)
    assert codes.tolist() == [2, 3, 1, 2, -1, 3, 2]
    assert codes.dtype == np.int32


def test_unknown_codes_refused() -> None:
    """A direction, a rank method or a bin count no kernel defines is refused, not guessed."""
    x = np.array([1.0, 2.0])
    mask, groups = everyone(2)
    tie = np.arange(2, dtype=np.int64)
    with pytest.raises(ValueError, match="no direction has code 2"):
        k.select(x, mask, groups, tie, 1, 2)
    with pytest.raises(ValueError, match="no rank method has code 5"):
        k.rank(x, mask, groups, tie, 5, k.ASCENDING)
    with pytest.raises(ValueError, match="at least one bin, not 0"):
        k.quantiles(x, mask, groups, tie, 0)


def test_winsorize_clips_at_linear_quantiles() -> None:
    """5.4.2: `clip(x, q_a, q_b)` with numpy's linear quantiles, a and b fractions of 0..1
    (#244, Decisions 2026-11-18). Of 1, 2, 3, 4, 100 the 0.1 quantile sits 0.4 of the way from
    1 to 2, 1.4, and the 0.9 one 0.6 of the way from 4 to 100, 61.6; per group, NaN outside."""
    x = np.array([100.0, 3.0, NAN, 1.0, 4.0, 2.0, 7.0, 5.0])
    mask = np.array([True, True, True, True, True, True, True, False])
    groups = np.array([0, 0, 0, 0, 0, 0, -1, 1], dtype=np.int32)
    found, unknown = k.winsorize(x, mask, groups, 0.1, 0.9)
    assert found.tolist()[:6] == pytest.approx([61.6, 3.0, NAN, 1.4, 4.0, 2.0], nan_ok=True)
    assert np.isnan(found[6:]).all()  # unknown group; masked out
    assert unknown == 1
    middle, _ = k.winsorize(x, mask, groups, 0.5, 0.5)  # min == max: all to the median
    assert middle.tolist()[:6] == pytest.approx([3.0, 3.0, NAN, 3.0, 3.0, 3.0], nan_ok=True)
    shuffle = np.array([5, 2, 7, 0, 3, 6, 1, 4])
    again, _ = k.winsorize(x[shuffle], mask[shuffle], groups[shuffle], 0.1, 0.9)
    assert again.tobytes() == found[shuffle].tobytes()


@pytest.mark.parametrize(("low", "high"), [(1.0, 99.0), (0.01, 1.5), (-0.1, 0.5), (0.6, 0.4)])
def test_winsorize_refuses_bounds_outside_fractions(low: float, high: float) -> None:
    mask, groups = everyone(2)
    with pytest.raises(ValueError, match=r"fractions 0 <= min <= max <= 1 \(1% is 0.01\)"):
        k.winsorize(np.array([1.0, 2.0]), mask, groups, low, high)


def test_percentile_between_includes_both_ends() -> None:
    """5.4.2: `p = 100 (r - 1) / (n - 1)` with the mean rank r, `a <= p <= b`, a and b on
    0..100. Scores 10, 20, 20, 40, 50 have r = 1, 2.5, 2.5, 4, 5 and p = 0, 37.5, 37.5, 75,
    100; a single cell has p = 100; outside the cross-section, never between."""
    x = np.array([40.0, 20.0, NAN, 10.0, 50.0, 20.0, 30.0])
    mask = np.array([True, True, True, True, True, True, False])
    assert k.percentile_between(x, mask, 37.5, 75.0).tolist() == [
        True, True, False, False, False, True, False]  # fmt: skip
    assert k.percentile_between(x, mask, 0.0, 0.0).tolist() == [
        False, False, False, True, False, False, False]  # fmt: skip
    one = np.array([5.0])
    assert k.percentile_between(one, np.array([True]), 100.0, 100.0).tolist() == [True]
    assert k.percentile_between(one, np.array([True]), 0.0, 99.0).tolist() == [False]
    for low, high in [(10.0, 101.0), (-1.0, 50.0), (60.0, 50.0)]:
        with pytest.raises(ValueError, match="0 <= min <= max <= 100"):
            k.percentile_between(x, mask, low, high)
