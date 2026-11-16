"""The reference executor: a graph's values at the decision rows, computed chunk by chunk.

Each chunk plans its own decisions (5.3.2) and reads its block from the plan's first row, so what
it reads before its first row is the rows the plan gives, which may reach past the previous chunk
(5.3.1; decision 2026-11-16, #486), not a fixed `W_max - 1`. Each node is computed once on each
row the plan gives it (5.3.2 (5)), and its value at row s is the value of row s: a term that
reads column cells sees a cell only when its `ts_available <= ready(s)` (5.1.2); a term that
reads another term's values reads them as that term gave them at each row (3.3 `shift`, "the
value k sessions earlier"), so a row's values, once frozen, are not changed by data that arrives
late (5.1.2). A value depends on its own window of the block alone, so the values do not depend
on the chunking (INV-03).

A user window function (5.3.7) gets, for each input, the `(W, N_alive)` window of the instruments
listed at the row, and returns `(N_alive,)`. The caller gives each user node's function by its
graph hash; how `@nx.factor` binds it, and its errors, are T1.12's.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import Any

import numpy as np
import numpy.typing as npt
import pyarrow as pa

from nexusbt.compute import _kernels
from nexusbt.compute._plan import _top_down, plan
from nexusbt.contracts import ID_COLUMN
from nexusbt.data._block import MarketBlock
from nexusbt.pipeline import Term, graph_hash

F64 = npt.NDArray[np.float64]
#: The block of the axis rows `first..last`, both included.
Read = Callable[[int, int], MarketBlock]

#: The arithmetic class with numpy's element-wise functions; the transcendental class with the
#: compiled element functions of the kernels (5.3.10 2a).
_BINARY: Mapping[str, Callable[[F64, F64], F64]] = {
    "add": np.add,
    "sub": np.subtract,
    "mul": np.multiply,
    "div": np.divide,
    "pow": _kernels.power,
}
_UNARY: Mapping[str, Callable[[F64], F64]] = {
    "neg": np.negative,
    "abs": np.abs,
    "sqrt": np.sqrt,
    "log": lambda x: _kernels.elementwise(_kernels.LOG, x),
    "log1p": lambda x: _kernels.elementwise(_kernels.LOG1P, x),
    "exp": lambda x: _kernels.elementwise(_kernels.EXP, x),
}


def execute(
    terms: Sequence[Term],
    decisions: Iterable[int],
    spans: Sequence[tuple[int, int]],
    read: Read,
    ready: npt.NDArray[np.datetime64],
    functions: Mapping[str, Callable[..., Any]] | None = None,
) -> dict[str, pa.Table]:
    """Each term's values at the decision rows, as `(row, instrument_id, value)` sorted by row
    and instrument, for the instruments listed at the row; keyed by the term's graph hash.
    `spans` are the chunks, `(first, last)` axis rows in order and apart, holding every
    decision; `ready[r]` is row r's freeze time."""
    wanted = np.unique(np.fromiter(decisions, dtype=np.int64))
    _check(spans, wanted)
    terms = list({graph_hash(t): t for t in terms}.values())  # a term listed twice is one node
    if columns := [dict(t.params)["column"] for t in terms if t.op == "column"]:
        raise ValueError(f"a column is read through a term, such as `.latest`: {columns}")
    order = [t for t in _top_down(terms)[::-1] if t.op != "column"]  # inputs first
    parts: dict[str, list[pa.Table]] = {graph_hash(t): [] for t in terms}
    for first, last in spans:
        mine = wanted[(wanted >= first) & (wanted <= last)]
        if not mine.size:
            continue
        rows = plan(terms, mine, sessions=len(ready)).rows
        low = min([first, *(int(r[0]) for r in rows.values() if r.size)])
        chunk = _Chunk(read(low, last), low, ready, functions or {})
        with np.errstate(all="ignore"):  # IEEE results (inf, NaN), as numpy gives them
            for term in order:
                chunk.compute(term, rows[graph_hash(term)])
        for term in terms:
            parts[graph_hash(term)].append(chunk.frame(term, mine))
    empty = _frame([], [], [])
    return {key: pa.concat_tables(found) if found else empty for key, found in parts.items()}


def _check(spans: Sequence[tuple[int, int]], wanted: npt.NDArray[np.int64]) -> None:
    previous, covered = -1, np.zeros(wanted.shape, dtype=bool)
    for first, last in spans:
        if not previous < first <= last:
            raise ValueError(f"chunks are axis rows in order and apart, not {list(spans)}")
        previous = last
        covered |= (wanted >= first) & (wanted <= last)
    if not covered.all():
        raise ValueError(f"decision rows outside every chunk: {wanted[~covered].tolist()}")


class _Chunk:
    """One chunk's block, from axis row `low`, and the values computed on it so far."""

    def __init__(
        self,
        block: MarketBlock,
        low: int,
        ready: npt.NDArray[np.datetime64],
        functions: Mapping[str, Callable[..., Any]],
    ) -> None:
        self.block, self.low, self.ready, self.functions = block, low, ready, functions
        self.values: dict[str, F64] = {}

    def window(self, term: Term, t: int, size: int) -> F64:
        """`term` on rows `t-size+1..t` as row t reads it: column cells seen by `ready(t)`, a
        term's values as it gave them at each row; a new array."""
        a, b = t - size + 1 - self.low, t + 1 - self.low
        if term.op != "column":
            return self.values[graph_hash(term)][a:b].copy()
        cells = self.block.values[dict(term.params)["column"]][a:b]
        seen = self.block.ts_available[a:b] <= self.ready[t]  # NaT, no bar, is never seen
        found: F64 = np.where(seen, cells, np.nan)
        return found

    def cell(self, term: Term, t: int) -> F64:
        found: F64 = self.window(term, t, 1)[0]
        return found

    def compute(self, term: Term, rows: npt.NDArray[np.int64]) -> None:
        out = np.full((len(self.block.dates), len(self.block.instrument_ids)), np.nan)
        for t in rows.tolist():
            out[t - self.low] = self.row(term, t)
        self.values[graph_hash(term)] = out

    def row(self, term: Term, t: int) -> F64:
        params, inputs, n = dict(term.params), term.inputs, len(self.block.instrument_ids)
        if term.op == "constant":
            return np.full(n, params["value"])
        if term.op == "latest":
            return self.cell(inputs[0], t)
        if term.op == "shift":
            k: int = params["k"]
            return self.cell(inputs[0], t - k) if t - k >= 0 else np.full(n, np.nan)
        if term.op in _BINARY:
            return _BINARY[term.op](self.cell(inputs[0], t), self.cell(inputs[1], t))
        if term.op in _UNARY:
            return _UNARY[term.op](self.cell(inputs[0], t))
        if term.op == "user":
            return self.user(term, t)
        raise NotImplementedError(f"the reference executor has no `{term.op}` term yet")

    def user(self, term: Term, t: int) -> F64:
        params, out = dict(term.params), np.full(len(self.block.instrument_ids), np.nan)
        if params["mask"] is not None:
            raise NotImplementedError("a user function's mask comes with T1.12")
        fn = self.functions.get(graph_hash(term))
        if fn is None:
            raise ValueError(f"no function given for the user term {params['function']}")
        size = params["window"]
        if t - size + 1 < 0:
            return out  # the window starts before the axis: nothing is there to read
        alive = self.block.exists[t - self.low]
        got = np.asarray(fn(*(self.window(i, t, size)[:, alive] for i in term.inputs)), np.float64)
        if got.shape != (int(alive.sum()),):
            raise ValueError(f"{params['function']} returned {got.shape}, not ({alive.sum()},)")
        out[alive] = got
        return out

    def frame(self, term: Term, rows: npt.NDArray[np.int64]) -> pa.Table:
        local = rows - self.low
        r, c = np.nonzero(self.block.exists[local])
        ids = np.asarray(self.block.instrument_ids, dtype=object)[c]
        return _frame(rows[r], ids, self.values[graph_hash(term)][local[r], c])


def _frame(rows: Any, ids: Any, values: Any) -> pa.Table:
    row, instrument = pa.array(rows, pa.int64()), pa.array(ids, pa.string())
    return pa.table({"row": row, ID_COLUMN: instrument, "value": pa.array(values, pa.float64())})
