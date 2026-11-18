"""Print ranks of equal scores under both tie-break keys, and `zscore` under a shuffled memory
order (spec 5.4.2, 3.7, INV-04).

Run it: `uv run python examples/dev/show_ties.py`. It shows the two things of T1.11:

1. three instruments with the same score, held out of `instrument_id` order, ranked by
   `rank(method="ordinal")`: 1, 2, 3 in `instrument_id` order with `tiebreak="id"` (T-11), and
   in T-27's order with the default `"hash"` (KR:T00002, KR:T00001, KR:T00003);
2. `zscore` of 500 cells, once with the columns in `instrument_id` order and once shuffled:
   the same bits, since its mean and variance are summed in sorted `instrument_id` order
   (5.3.10 (3), ADR-0019), whatever order memory holds the columns in.
"""

from __future__ import annotations

import hashlib

import numpy as np

from nexusbt.compute import _crosssection as xs
from nexusbt.compute import _kernels as k
from nexusbt.contracts import TiebreakPolicy

TIED = ["KR:T00003", "KR:T00001", "KR:T00002"]  # equal scores, held out of id order


def everyone(n: int) -> tuple[np.ndarray, np.ndarray]:
    """No mask and no groupby: every cell in, one group."""
    return np.ones(n, dtype=bool), np.zeros(n, dtype=np.int32)


def zscore(ids: list[str], x: np.ndarray) -> np.ndarray:
    found, _ = k.zscore(x, *everyone(len(x)), xs.sorted_order(ids))
    return found


def main() -> None:
    for policy in (TiebreakPolicy.ID, TiebreakPolicy.HASH):
        tie = xs.tie_order(TIED, policy)
        ranks, _ = k.rank(np.ones(3), *everyone(3), tie, k.ORDINAL, k.ASCENDING)
        cells = "  ".join(f"{i} {int(ranks[TIED.index(i)])}" for i in sorted(TIED))
        print(f'rank(method="ordinal"), tiebreak="{policy}":  {cells}')

    rng = np.random.default_rng(11)
    ids = [f"KR:T{i:05d}" for i in range(1, 501)]
    # five 1e16 and five -1e16 among small values: where each small value falls between them
    # decides whether it is lost, so a sum in memory order moves with the order
    x = rng.permutation(np.r_[[1e16] * 5, [-1e16] * 5, rng.uniform(0, 10, 490)]).astype(float)
    shuffle = rng.permutation(500)
    held = [k.fold_sum(x), k.fold_sum(x[shuffle])]
    print(f"left fold in memory order: in id order {held[0]!r}, shuffled {held[1]!r}")
    in_order = zscore(ids, x)
    back = np.empty(500)
    back[shuffle] = zscore([ids[i] for i in shuffle], x[shuffle])  # each cell to its id's place
    digests = [hashlib.sha256(z.tobytes()).hexdigest() for z in (in_order, back)]
    print(f"zscore sha256, columns in instrument_id order: {digests[0]}")
    print(f"zscore sha256, columns shuffled: {digests[1]}")
    print(f"zscore bit-identical under the shuffle: {in_order.tobytes() == back.tobytes()}")


if __name__ == "__main__":
    main()
