"""The cross-section kernels of the 2.4 seam (5.4.2, 5.4.3): one decision's cells, arrays in.

Each kernel takes one market's (or `across_markets`') cells in memory order: the values `x`, the
`mask` (true where the cell is in the term's domain), the group codes `groups` (all 0 without a
`groupby`, -1 where the group is unknown) and `order`, the memory positions in ascending
`instrument_id` order. A cell is in its group's cross-section when its mask is true, its value is
finite and its group is known. Every reduction gathers the cells in `order` and left-folds them
(5.3.10 (3), ADR-0019), so shuffling the memory order gives the same bits (INV-04). Each kernel
also returns how many cells it left out for an unknown group (`UnknownGroup`, 3.3).

`sorted_order` and `tie_order` turn instrument ids into those integer arrays outside the kernels.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence

import numpy as np
import numpy.typing as npt

from nexusbt.compute._kernels import fold_sum
from nexusbt.contracts import TiebreakPolicy

F64 = npt.NDArray[np.float64]
I64 = npt.NDArray[np.int64]
Mask = npt.NDArray[np.bool_]
Codes = npt.NDArray[np.int32]

#: The `rank` methods of 3.3, as integer codes for the seam.
ORDINAL, AVERAGE, MIN, MAX, DENSE = _METHODS = (0, 1, 2, 3, 4)
_SALT = b"nexusbt-tiebreak-v1"


def sorted_order(ids: Sequence[str]) -> I64:
    """The memory positions of `ids` in ascending `instrument_id` order."""
    found: I64 = np.argsort(np.asarray(ids, dtype=object), kind="stable").astype(np.int64)
    return found


def tie_order(ids: Sequence[str], policy: TiebreakPolicy) -> I64:
    """Each cell's place (0 first) in the order of the `[portfolio] tiebreak` key (3.7): `"hash"`
    ascending (the first 8 bytes of sha256(salt || 0x1F || id), big-endian, then the id), `"id"`
    ascending `instrument_id`. The key reads nothing but the id, so it is the same at every
    decision."""

    def key(i: int) -> tuple[int, str]:
        if policy is TiebreakPolicy.ID:
            return (0, ids[i])
        digest = hashlib.sha256(_SALT + b"\x1f" + ids[i].encode()).digest()
        return (int.from_bytes(digest[:8], "big"), ids[i])

    place = np.empty(len(ids), dtype=np.int64)
    place[sorted(range(len(ids)), key=key)] = np.arange(len(ids))
    return place


def _sections(x: F64, mask: Mask, groups: Codes, order: I64) -> tuple[list[I64], int]:
    """Each known group's cross-section, its memory positions in id order; and the number of
    cells left out for an unknown group."""
    seq = order[(mask & np.isfinite(x))[order]]
    codes = groups[seq]
    unknown = int(np.count_nonzero(codes < 0))
    return [seq[codes == g] for g in np.unique(codes[codes >= 0])], unknown


def _mean(values: F64) -> float:
    return fold_sum(values) / len(values)


def demean(x: F64, mask: Mask, groups: Codes, order: I64) -> tuple[F64, int]:
    """`x - mean` within each group (5.4.2); NaN outside the cross-section."""
    out = np.full(len(x), np.nan)
    sections, unknown = _sections(x, mask, groups, order)
    for seq in sections:
        out[seq] = x[seq] - _mean(x[seq])
    return out, unknown


def _ordered(x: F64, seq: I64, tie: I64, descending: bool) -> tuple[I64, I64, I64, I64]:
    """The cells of `seq` by score (descending or not), equal scores by ascending tie place; and
    for each, the first and last place (1-based) of its run of equal scores and the run's
    number (0 first)."""
    scores = -x[seq] if descending else x[seq]
    found = seq[np.lexsort((tie[seq], scores))]
    sorted_scores = x[found]
    starts = np.flatnonzero(np.r_[True, sorted_scores[1:] != sorted_scores[:-1]])
    run = np.searchsorted(starts, np.arange(len(found)), side="right") - 1
    ends = np.r_[starts[1:], len(found)]
    return found, starts[run] + 1, ends[run], run


def rank(
    x: F64, mask: Mask, groups: Codes, tie: I64, method: int, ascending: bool
) -> tuple[F64, int]:
    """Ranks 1..n within each group (5.4.2), 1 the smallest, or the largest when not
    `ascending`. `ORDINAL` breaks ties by the tie place (`tie_order`); `AVERAGE`, `MIN`, `MAX`
    and `DENSE` are scipy's `rankdata`."""
    if method not in _METHODS:
        raise ValueError(f"no rank method has code {method}")
    out = np.full(len(x), np.nan)
    sections, unknown = _sections(x, mask, groups, np.argsort(tie))
    for seq in sections:
        found, lo, hi, run = _ordered(x, seq, tie, descending=not ascending)
        if method == ORDINAL:
            out[found] = np.arange(1, len(found) + 1)
        elif method == AVERAGE:
            out[found] = (lo + hi) / 2
        else:
            out[found] = {MIN: lo, MAX: hi, DENSE: run + 1}[method]
    return out, unknown


def select(
    x: F64, mask: Mask, groups: Codes, tie: I64, n: int, largest: bool
) -> tuple[Mask, int, int]:
    """`top(n)` when `largest`, else `bottom(n)` (5.4.2, 3.7): the first n of each group by
    score, equal scores by ascending tie place, all of them when fewer are finite. Also
    `n_tied_at_cutoff`: the size of each tie group straddling a cutoff (the score of the last one
    taken, when one with that score is left out), summed over the groups."""
    if n < 0:
        raise ValueError(f"a selection takes at least zero cells, not {n}")
    picked, tied = np.zeros(len(x), dtype=bool), 0
    sections, unknown = _sections(x, mask, groups, np.argsort(tie))
    for seq in sections:
        found, lo, hi, _ = _ordered(x, seq, tie, descending=largest)
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
        found, lo, hi, _ = _ordered(x, seq, np.argsort(order), descending=False)
        twice_r, twice_n = lo + hi, 2 * len(found)
        out[found] = np.clip(-(-twice_r * bins // twice_n), 1, bins)
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
