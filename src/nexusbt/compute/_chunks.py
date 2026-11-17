"""Chunk sizes from the memory budget (5.3.8).

A chunk is the largest session range whose estimate fits `memory_budget_gb`: a calendar year is
tried first; a year that does not fit is split into its quarters, a quarter into its months, and
a month by halving its sessions until each part fits. Estimated bytes = rows x columns x 8 x
(the most nodes alive at once + 2), the rows being the chunk's own and the rows the plan reads
before its first (5.3.1), which its block holds too. One session row that does not fit is E16.
Dividing the budget among `workers > 1` is T6.5's.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import numpy.typing as npt

from nexusbt.compute._plan import _top_down, children, plan
from nexusbt.contracts import ConfigError
from nexusbt.pipeline import Term, graph_hash

#: `memory_budget_gb` counts gigabytes of 10^9 bytes.
GB = 10**9


def estimate(rows: int, columns: int, nodes: int) -> int:
    """5.3.8's estimated bytes of a chunk."""
    return rows * columns * 8 * (nodes + 2)


def schedule(terms: Sequence[Term]) -> list[tuple[Term, tuple[str, ...]]]:
    """Each computed node, inputs first, with the nodes dropped once it is computed: those every
    reader of which is computed; the outputs are kept (5.3.2 (5)). Columns are read from the
    block, not computed."""
    order = [t for t in _top_down(list(terms))[::-1] if t.op != "column"]
    readers: dict[str, int] = {}
    for term in order:
        for child in _inputs(term):
            readers[child] = readers.get(child, 0) + 1
    kept, out = {graph_hash(t) for t in terms}, []
    for term in order:
        dropped = []
        for child in _inputs(term):
            readers[child] -= 1
            if not readers[child] and child not in kept:
                dropped.append(child)
        out.append((term, tuple(dropped)))
    return out


def most_alive(terms: Sequence[Term]) -> int:
    """The most computed nodes held at once along `schedule(terms)`."""
    alive = most = 0
    for _, dropped in schedule(terms):
        alive += 1
        most = max(most, alive)
        alive -= len(dropped)
    return most


def lookback(terms: Sequence[Term]) -> int:
    """The most rows the graph reads before a decision row: what a chunk reads before its first
    row, by the plan (5.3.1), so a chunk's block is its rows plus these."""
    last = 1 << 20  # far enough from row 0 that nothing is clipped at the axis start
    rows = plan(terms, [last], sessions=last + 1).rows.values()
    return last - min([last, *(int(r[0]) for r in rows if r.size)])


def _inputs(term: Term) -> set[str]:
    return {graph_hash(t) for t in children(term) if t.op != "column"}


def spans(
    dates: npt.NDArray[np.datetime64],
    columns: int,
    nodes: int,
    budget_gb: float,
    lookback: int = 0,
) -> list[tuple[int, int]]:
    """The chunks of the session axis `dates`, as `(first, last)` rows, in order. A chunk's
    block also holds the `lookback` rows read before its first row, so they count."""
    if not budget_gb > 0:  # NaN too: no chunk could ever fit
        raise ValueError(f"memory_budget_gb is a positive number, not {budget_gb}")
    budget = budget_gb * GB
    if (least := estimate(1 + lookback, columns, nodes)) > budget:
        raise ConfigError(
            what=f"memory_budget_gb too small for {columns} instruments",
            where="nexusbt.toml [compute] memory_budget_gb",
            why=f"one session row, with the {lookback} rows read before it, needs {least} bytes",
            fix="raise [compute] memory_budget_gb, or compute fewer markets or terms at once",
            more="spec 5.3.8",
            layer=f"config — nexusbt.toml [compute] memory_budget_gb = {budget_gb}",
        )
    if not len(dates):
        return []
    days = dates.astype("datetime64[D]")
    months = days.astype("datetime64[M]").astype(np.int64)
    keys = (days.astype("datetime64[Y]").astype(np.int64), months // 3, months)
    out: list[tuple[int, int]] = []

    def split(first: int, last: int, level: int) -> None:
        if estimate(last - first + 1 + lookback, columns, nodes) <= budget:
            out.append((first, last))
        elif level < len(keys) - 1:
            for a, b in _runs(keys[level + 1], first, last):
                split(a, b, level + 1)
        else:  # a month that does not fit: halve its sessions
            middle = (first + last) // 2
            split(first, middle, level)
            split(middle + 1, last, level)

    for a, b in _runs(keys[0], 0, len(days) - 1):
        split(a, b, 0)
    return out


def _runs(key: npt.NDArray[np.int64], first: int, last: int) -> list[tuple[int, int]]:
    """The runs of equal `key` within rows `first..last`."""
    edges = [first, *(np.flatnonzero(np.diff(key[first : last + 1])) + first + 1).tolist()]
    return list(zip(edges, [*(e - 1 for e in edges[1:]), last], strict=True))
