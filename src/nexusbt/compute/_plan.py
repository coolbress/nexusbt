"""The 5.3.2 plan: the rows each node of a graph computes, from the decision rows down.

Rows are session rows of one market axis (5.3.1). A window-W term needed at rows R reads its
inputs on the union over r in R of `[r-W+1, r]`; a node shared by several parents computes the
union of what they need, once. The rows come from the decisions and the graph, never from a
chunk's edges, so a chunk reads before its first row exactly what the plan says (INV-03).
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from nexusbt.pipeline import Term, graph_hash

Rows = npt.NDArray[np.int64]

_log = logging.getLogger("nexusbt.compute")


@dataclass(frozen=True, slots=True)
class Plan:
    """Each node's rows, keyed by its structural hash (shared nodes appear once, 5.3.2 (5))."""

    rows: Mapping[str, Rows]

    def rows_of(self, term: Term) -> list[int]:
        return [int(r) for r in self.rows[graph_hash(term)]]


def plan(terms: Iterable[Term], rows: Iterable[int], sessions: int) -> Plan:
    """Propagate the decision rows `rows` from `terms` down to the columns (5.3.2 (1) to (3))."""
    wanted = np.unique(np.fromiter(rows, dtype=np.int64))
    if wanted.size and (wanted[0] < 0 or wanted[-1] >= sessions):
        raise ValueError(f"decision rows must lie in [0, {sessions}), not {wanted.tolist()}")
    roots = list(terms)
    order = _top_down(roots)
    need: dict[str, Rows] = {graph_hash(t): wanted for t in roots}
    for term in order:
        mine = need[graph_hash(term)]
        for child, theirs in _inputs(term, mine):
            key = graph_hash(child)
            need[key] = np.union1d(need[key], theirs) if key in need else theirs
    found = Plan({graph_hash(t): need[graph_hash(t)] for t in order})
    computed = sum(r.size for r in found.rows.values())
    _log.debug("rows computed: %d of %d", computed, len(found.rows) * sessions)
    return found


def _inputs(term: Term, rows: Rows) -> Iterator[tuple[Term, Rows]]:
    """Each input with the rows it is needed at; a mask or groupby keeps the node's own rows."""
    params = dict(term.params)
    window = params.get("window")
    read = _cover(rows, window) if isinstance(window, int) and window > 1 else rows
    if term.op == "shift":
        read = rows - params["k"]
        read = read[read >= 0]  # before the axis there is nothing to read; the value is NaN
    for child in term.inputs:
        yield child, read
    for value in params.values():
        if isinstance(value, Term):
            yield value, rows


def _cover(rows: Rows, window: int) -> Rows:
    """The union over r in `rows` of `[r-window+1, r]`, clipped at row 0 where the axis starts."""
    if not rows.size:
        return rows
    low = max(int(rows[0]) - window + 1, 0)
    edges = np.zeros(int(rows[-1]) - low + 2, dtype=np.int64)
    np.add.at(edges, np.maximum(rows - window + 1, low) - low, 1)
    np.add.at(edges, rows + 1 - low, -1)
    return np.flatnonzero(np.cumsum(edges)[:-1] > 0).astype(np.int64) + low


def _top_down(roots: list[Term]) -> list[Term]:
    """Every node once, each after all the nodes that use it (a reversed post-order, walked with
    a stack: a graph may be deeper than Python's recursion limit)."""
    seen: set[str] = set()
    post: list[Term] = []
    stack: list[tuple[Term, bool]] = [(root, False) for root in reversed(roots)]
    while stack:
        term, done = stack.pop()
        if done:
            post.append(term)
            continue
        if (key := graph_hash(term)) in seen:
            continue
        seen.add(key)
        stack.append((term, True))
        children = (*term.inputs, *(v for _, v in term.params if isinstance(v, Term)))
        stack.extend((child, False) for child in reversed(children))
    return post[::-1]
