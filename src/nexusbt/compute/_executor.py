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

A user window function (5.3.7) gets, for each input, the `(W, N)` window of the instruments in
its domain at the row (listed, and its `mask` true), and returns `(N,)`. It is the function the
term was built from, unless the caller gives another by its graph hash.
"""

from __future__ import annotations

import warnings
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from functools import cached_property
from typing import Any

import numpy as np
import numpy.typing as npt
import pyarrow as pa

from nexusbt.compute import _factors, _kernels
from nexusbt.compute._chunks import schedule
from nexusbt.compute._crosssection import sorted_order, tie_order
from nexusbt.compute._kernels_ref import REGISTERED, AdjustmentClass, adjusted_window
from nexusbt.compute._plan import plan
from nexusbt.contracts import (
    ID_COLUMN,
    NexusBTError,
    ResolvedActions,
    TiebreakPolicy,
    _note_user_exception,
)
from nexusbt.data._block import MarketBlock
from nexusbt.pipeline import Classifier, Factor, Filter, Term, graph_hash
from nexusbt.pipeline._degree import input_scales
from nexusbt.pipeline._terms import (
    call_user,
    check_adjustment,
    def_line,
    same_function,
    unchecked,
)

#: 5.4.1's counts: `(row, graph hash, diagnostic)` to the cells counted there.
Counts = dict[tuple[int, str, str], int]

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
    "fillna": lambda x, y: np.where(np.isnan(x), y, x),  # 3.3: a Factor's only explicit fill
}
_UNARY: Mapping[str, Callable[[F64], F64]] = {
    "neg": np.negative,
    "abs": np.abs,
    "sqrt": np.sqrt,
    "log": lambda x: _kernels.elementwise(_kernels.LOG, x),
    "log1p": lambda x: _kernels.elementwise(_kernels.LOG1P, x),
    "exp": lambda x: _kernels.elementwise(_kernels.EXP, x),
}
_COMPARE = {"lt": _kernels.LT, "le": _kernels.LE, "gt": _kernels.GT, "ge": _kernels.GE,
            "eq": _kernels.EQ, "ne": _kernels.NE}  # fmt: skip
_KLEENE = {"and": _kernels.kleene_and, "or": _kernels.kleene_or}
#: The cross-section terms (3.3, 5.4.2), computed over one market's block at a row.
_SECTION = frozenset({"rank", "zscore", "demean", "winsorize", "top", "bottom",
                      "percentile_between", "quantiles"})  # fmt: skip
_RANK = {"ordinal": _kernels.ORDINAL, "average": _kernels.AVERAGE, "min": _kernels.MIN,
         "max": _kernels.MAX, "dense": _kernels.DENSE}  # fmt: skip
#: A Factor's tests that are never unknown at a listed cell (5.4.1); a float's null is NaN.
_TESTS: Mapping[str, Callable[[F64], npt.NDArray[np.bool_]]] = {
    "isnan": np.isnan,
    "isnull": np.isnan,
    "notnan": lambda x: ~np.isnan(x),
    "notnull": lambda x: ~np.isnan(x),
    "isfinite": np.isfinite,
}
#: Each `Price` column's adjustment basis, the table of 3.2 (5.3.3); None, the value as stored.
_BASIS: Mapping[str, str | None] = {
    **dict.fromkeys(("open", "high", "low", "close"), "split"),
    "close_tr": "total",
    "volume": "volume",
    **dict.fromkeys(("close_unadjusted", "volume_unadjusted", "value_traded", "market_cap")),
}


@dataclass(frozen=True, slots=True)
class Actions:
    """A market's corporate actions as the executor reads them (5.3.3, 5.3.3a): `at(c)` is
    `Snapshot.actions(market, c)`, called with row t's `ready[t]` (5.3.4); `ts_open` the axis's
    session opens, indexed as `ready` is, placing each event at its first session."""

    at: Callable[[np.datetime64], ResolvedActions]
    ts_open: npt.NDArray[np.datetime64]


def execute(
    terms: Sequence[Term],
    decisions: Iterable[int],
    spans: Sequence[tuple[int, int]],
    read: Read,
    ready: npt.NDArray[np.datetime64],
    functions: Mapping[str, Callable[..., Any]] | None = None,
    tiebreak: TiebreakPolicy = TiebreakPolicy.HASH,
    *,
    actions: Actions | None = None,
    counts: Counts | None = None,
    gone: frozenset[str] = frozenset(),
) -> dict[str, pa.Table]:
    """Each term's values at the decision rows, as `(row, instrument_id, value)` sorted by row
    and instrument, for the instruments listed at the row; keyed by the term's graph hash.
    `spans` are the chunks, `(first, last)` axis rows in order and apart, holding every
    decision; `ready[r]` is row r's freeze time; `tiebreak` the `[portfolio] tiebreak` key of
    an ordinal `rank`, `top` and `bottom` (3.7). A window over a column is adjusted as of its
    row with `actions` (5.3.3). `actions=None` is the caller's statement that this axis has no
    corporate actions, not a switch that turns the adjustment off. `counts`, when given, gets
    5.4.1's counts of every row each term is computed at, as `(row, graph hash, diagnostic):
    n`: the rows the plan gives, decisions or not, whatever the chunks (a row two chunks
    compute is counted once). `gone` are the bars columns the market's F-18 records name
    (4.5): a factor `_factors.WITHOUT` ties to one of them is NaN in a column whose window
    reads a cell the block marks for it (`MarketBlock.gone`, #688). A user function's
    exception comes out as raised, the frames down to it hidden (`__tracebackhide__`, 6.6, R-42)."""
    __tracebackhide__ = True
    wanted = np.unique(np.fromiter(decisions, dtype=np.int64))
    _check(spans, wanted)
    _one_function_per_hash(terms, functions or {})
    terms = list({graph_hash(t): t for t in terms}.values())  # a term listed twice is one node
    if columns := [dict(t.params)["column"] for t in terms if t.op == "column"]:
        raise ValueError(f"a column is read through a term, such as `.latest`: {columns}")
    order = schedule(terms)  # inputs first, with the nodes each one's computing lets go
    if any(dict(t.params).get("across_markets") for t, _ in order):
        why = "it gathers several markets' blocks, and the executor computes one market's"
        raise NotImplementedError(f"across_markets=True comes with T4.3: {why}")
    parts: dict[str, list[pa.Table]] = {graph_hash(t): [] for t in terms}
    pending = {graph_hash(t): (t, input_scales(t)) for t, _ in order
               if "adjustment" in dict(t.params)}  # fmt: skip
    for first, last in spans:
        mine = wanted[(wanted >= first) & (wanted <= last)]
        if not mine.size:
            continue
        rows = plan(terms, mine, sessions=len(ready)).rows
        low = min([first, *(int(r[0]) for r in rows.values() if r.size)])
        chunk = _Chunk(read(low, last), low, ready, functions or {}, tiebreak, actions, pending,
                       counts, gone)  # fmt: skip
        with np.errstate(all="ignore"):  # IEEE results (inf, NaN), as numpy gives them
            for term, dropped in order:
                chunk.compute(term, rows[graph_hash(term)])
                for key in dropped:  # 5.3.2 (5): no reader left, so the estimate's count holds
                    del chunk.values[key]
        for term in terms:
            parts[graph_hash(term)].append(chunk.frame(term, mine))
    for term, scales in pending.values():  # 6.6 no silent failure: E45, never a silent pass
        params, at = dict(term.params), def_line(term.function)
        notice = unchecked(params["function"], params["adjustment"], at, scales is not None)
        warnings.warn(str(notice), stacklevel=2)
    empty = _frame([], [], [])
    return {key: pa.concat_tables(found) if found else empty for key, found in parts.items()}


def _one_function_per_hash(terms: Sequence[Term], given: Mapping[str, Any]) -> None:
    """A node is computed once for its graph hash, so two user terms of one hash whose functions
    differ in a value the hash does not hold (6.5 (6)) are refused, not given one's values.
    The walk goes below a hash it has seen, as one hash can hold two such terms at any depth
    (#562), and skips only an object it has already walked."""
    seen: dict[str, Term] = {}
    walked: set[int] = set()
    todo = list(terms)
    while todo:
        term = todo.pop()
        if id(term) in walked:
            continue
        walked.add(id(term))
        key = graph_hash(term)
        first = seen.setdefault(key, term).function
        if key not in given and not same_function(first, term.function):
            name = dict(term.params)["function"]
            why = "read different non-constant values; pass them as inputs or constants"
            raise ValueError(f"two user terms {name} share one graph hash but {why}")
        todo += [*term.inputs, *(v for _, v in term.params if isinstance(v, Term))]


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
        tiebreak: TiebreakPolicy,
        actions: Actions | None,
        pending: dict[str, tuple[Term, list[float] | None]],
        counts: Counts | None,
        gone: frozenset[str] = frozenset(),
    ) -> None:
        self.block, self.low, self.ready, self.functions = block, low, ready, functions
        self.gone = gone  # the bars columns F-18 records for the market (4.5)
        self.pending = pending  # user terms whose `adjustment` is not checked yet, their scales
        self.tiebreak, self.counts = tiebreak, counts
        self.unknown = 0  # `UnknownGroup` cells of the row computed
        self.zero: npt.NDArray[np.bool_] | None = None  # a division's `DivisionByZero` cells
        self.infinite: npt.NDArray[np.bool_] | None = None  # a kernel's `InfiniteResult` cells
        self.values: dict[str, F64] = {}
        self.actions, self.resolved = actions, dict[int, ResolvedActions]()

    @cached_property
    def tie(self) -> npt.NDArray[np.int64]:
        """Each column's place in the tie-break key's order (3.7)."""
        return tie_order(self.block.instrument_ids, self.tiebreak)

    @cached_property
    def order(self) -> npt.NDArray[np.int64]:
        """The columns in ascending `instrument_id` order (5.3.10 (3))."""
        return sorted_order(self.block.instrument_ids)

    def window(self, term: Term, t: int, size: int, raw: bool = False) -> F64:
        """`term` on rows `t-size+1..t` as row t reads it: column cells seen by `ready(t)` and
        adjusted as of t (5.3.3), a term's values as it gave them at each row, never adjusted
        again (5.1.2); a new array. `raw`, for an invariant kernel (3.4): the cells as traded,
        NaN where the adjustment leaves them NaN (4.6)."""
        a, b = t - size + 1 - self.low, t + 1 - self.low
        if term.op != "column":
            return self.values[graph_hash(term)][a:b].copy()
        params = dict(term.params)
        cells = self.block.values[params["column"]][a:b]
        seen = self.block.ts_available[a:b] <= self.ready[t]  # NaT, no bar, is never seen
        found: F64 = np.where(seen, cells, np.nan)
        if size == 1 or self.actions is None:  # no event e has t < e <= t
            return found
        basis = _basis(params)
        if basis is None:
            return found
        if t not in self.resolved:  # the actions as known at row t's reference time (5.3.4)
            self.resolved[t] = self.actions.at(self.ready[t])
        ts_open = self.actions.ts_open[a + self.low : b + self.low]
        adjusted, _ = adjusted_window(found, size - 1, size, self.resolved[t],  # 4.6's count: #249
                                      self.block.instrument_ids, ts_open, basis)  # fmt: skip
        if raw:
            as_traded: F64 = np.where(np.isnan(adjusted), np.nan, found)
            return as_traded
        return adjusted

    def cell(self, term: Term, t: int) -> F64:
        found: F64 = self.window(term, t, 1)[0]
        return found

    def compute(self, term: Term, rows: npt.NDArray[np.int64]) -> None:
        __tracebackhide__ = True  # down to a user function (R-42)
        out = np.full((len(self.block.dates), len(self.block.instrument_ids)), np.nan)
        key = graph_hash(term)
        for t in rows.tolist():  # 5.4.1: a value is finite or NaN, at the term that produced it
            self.unknown, self.zero, self.infinite = 0, None, None
            found = self.row(term, t)  # 5.3.1: absent where not listed, for any later reader
            listed = self.block.exists[t - self.low]
            out[t - self.low] = term_value(found, listed)
            if self.counts is not None:  # each cell once, at this term and row (5.4.1)
                zero = listed & self.zero if self.zero is not None else np.zeros_like(listed)
                kernel_inf = self.infinite if self.infinite is not None else False
                found_inf = listed & (np.isinf(found) | kernel_inf) & ~zero
                for name, n in (("DivisionByZero", int(zero.sum())),
                                ("InfiniteResult", int(found_inf.sum())),
                                ("UnknownGroup", self.unknown)):  # fmt: skip
                    if n:  # a row two chunks compute is the same row: set, never added
                        self.counts[t, key, name] = n
        self.values[key] = out

    def row(self, term: Term, t: int) -> F64:
        __tracebackhide__ = True  # down to a user function (R-42)
        inputs = term.inputs
        if term.op in ("constant", "latest", "shift"):
            return self.read(term, t)
        if term.op in _BINARY and isinstance(term, Factor):  # a Filter's `fillna` is `filter`
            return self.binary(term, t)
        if term.op in _UNARY:
            return _UNARY[term.op](self.cell(inputs[0], t))
        if term.op == "user":
            return self.user(term, t)
        if term.op in _factors.KERNELS:
            return self.kernel(term, t)
        if term.op in _SECTION:
            return self.section(term, t)
        if isinstance(term, Filter):
            return self.filter(term, t)
        if term.op == "as_factor":  # true 1.0, false 0.0, unknown NaN: the cells as held
            return self.cell(inputs[0], t)
        if term.op == "if_else":  # NaN where the condition is unknown
            value, valid = _truth(self.cell(inputs[0], t))
            picked = np.where(value, self.cell(inputs[1], t), self.cell(inputs[2], t))
            return np.where(valid, picked, np.nan)
        raise NotImplementedError(f"the reference executor has no `{term.op}` term yet")

    def read(self, term: Term, t: int) -> F64:
        """A constant, or its input's cells at row t (`latest`) or k rows before (`shift`)."""
        params, n = dict(term.params), len(self.block.instrument_ids)
        if term.op == "constant":
            return np.full(n, params["value"])
        if term.op == "latest":
            return self.cell(term.inputs[0], t)
        k: int = params["k"]  # `shift`
        return self.cell(term.inputs[0], t - k) if t - k >= 0 else np.full(n, np.nan)

    def binary(self, term: Term, t: int) -> F64:
        """A Factor's arithmetic of two terms at row t."""
        x, y = self.cell(term.inputs[0], t), self.cell(term.inputs[1], t)
        if term.op == "div":  # 5.4.1 `DivisionByZero`: a divisor 0, a dividend not NaN
            self.zero = (y == 0) & ~np.isnan(x)
        return _BINARY[term.op](x, y)

    def kernel(self, term: Term, t: int) -> F64:
        """A built-in factor's kernel at row t over its domain (3.4); NaN while the window
        starts before the axis, and in a column whose window reads a seen cell (5.1.2) of a
        file without the column `_factors.WITHOUT` names, in a market F-18 records it for
        (#667, #688): a missing input, counted nowhere (5.4.1)."""
        if t - (size := _factors.rows(term)) + 1 < 0:
            return np.full(len(self.block.instrument_ids), np.nan)
        kernel = REGISTERED.get(term.op)  # `rolling` reads only terms, so it has no class
        raw = kernel is not None and kernel.adjustment is AdjustmentClass.INVARIANT
        windows = [self.window(i, t, size, raw) for i in term.inputs]
        found, zero, infinite = _factors.diagnosed(term, windows)
        inside = self.domain(term, t)
        column = _factors.WITHOUT.get(term.op)
        if column in self.gone and (covered := self.block.gone.get(str(column))) is not None:
            a, b = t - size + 1 - self.low, t + 1 - self.low
            seen = self.block.ts_available[a:b] <= self.ready[t]
            inside = inside & ~(covered[a:b] & seen).any(axis=0)
        self.zero, self.infinite = zero & inside, infinite & inside  # 5.4.1, inside the kernel
        return np.where(inside, found, np.nan)

    def domain(self, term: Term, t: int) -> npt.NDArray[np.bool_]:
        """The term's cells at row t: the listed ones (3.3's default domain, the block's), and of
        those the ones its `mask` is known true at, as unknown is false there (5.4.1)."""
        inside: npt.NDArray[np.bool_] = self.block.exists[t - self.low]
        if (mask := dict(term.params).get("mask")) is not None:
            inside = inside & _truth(self.cell(mask, t))[0]  # the value is false where unknown
        return inside

    def section(self, term: Term, t: int) -> F64:
        """A cross-section term at row t over the market's block (5.4.2), held as a Factor's,
        a Filter's (unknown outside the domain, 3.3) or a Classifier's cells (`_codes`)."""
        p, k, x = dict(term.params), _kernels, self.cell(term.inputs[0], t)
        inside = self.domain(term, t)
        by = p.get("groupby")
        groups = _codes(self.cell(by, t)) if by is not None else np.zeros(len(x), np.int32)
        if term.op in ("top", "bottom"):
            way = k.DESCENDING if term.op == "top" else k.ASCENDING
            picked, _, n = k.select(x, inside, groups, self.tie, p["N"], way)
            self.unknown += n
            return _cells(picked, inside)
        if term.op == "percentile_between":
            return _cells(k.percentile_between(x, inside, p["min"], p["max"]), inside)
        if term.op == "rank":
            way = k.ASCENDING if p["ascending"] else k.DESCENDING
            out, n = k.rank(x, inside, groups, self.tie, _RANK[p["method"]], way)
        elif term.op == "winsorize":
            out, n = k.winsorize(x, inside, groups, p["min"], p["max"])
        elif term.op == "quantiles":
            codes, n = k.quantiles(x, inside, groups, self.order, p["bins"])
            out = codes.astype(np.float64)
        else:
            out, n = getattr(k, term.op)(x, inside, groups, self.order)
            if term.op == "zscore":  # 5.4.1 `DivisionByZero`: a std of 0 (#632)
                self.zero = k.zscore_zero(x, inside, groups, self.order)
        self.unknown += n
        return out

    def user(self, term: Term, t: int) -> F64:
        __tracebackhide__ = True  # down to a user function (R-42)
        out, size = np.full(len(self.block.instrument_ids), np.nan), dict(term.params)["window"]
        if t - size + 1 < 0:
            return out  # the window starts before the axis: nothing is there to read
        inside = self.domain(term, t)  # 3.3 `mask`: the columns the function computes on
        windows = [self.window(i, t, size)[:, inside] for i in term.inputs]
        key = graph_hash(term)
        fn = self.functions.get(key, term.function)
        ids = np.asarray(self.block.instrument_ids, dtype=object)[inside]
        scales = self.pending[key][1] if key in self.pending else None
        pristine = None if scales is None else [w.copy() for w in windows]  # 3.3: copies
        try:
            out[inside] = got = call_user(term, windows, int(inside.sum()), fn)
            if pristine and check_adjustment(term, pristine, got, ids.tolist(), scales or [], fn):
                del self.pending[key]  # once for each user term in a run
        except Exception as error:  # 6.6: the user's exception, noted and re-raised as it is
            if not isinstance(error, NexusBTError) and fn is not None:
                first, date = str(ids[0]) if ids.size else "-", str(self.block.dates[t - self.low])
                _note_user_exception(error, fn, instrument_id=first, date=date)
            raise
        return out

    def filter(self, term: Term, t: int) -> F64:
        """A Filter's cells at row t, held as 1.0, 0.0 and NaN for unknown (`_cells`)."""
        inputs = term.inputs
        if isinstance(inputs[0], Classifier):
            return self.codes_test(term, t)
        if term.op in _COMPARE and isinstance(inputs[0], Factor):
            x, y = self.cell(inputs[0], t), self.cell(inputs[1], t)
            return _cells(*_kernels.compare(_COMPARE[term.op], x, y))
        if term.op in _KLEENE:
            a, b = _truth(self.cell(inputs[0], t)), _truth(self.cell(inputs[1], t))
            return _cells(*_KLEENE[term.op](*a, *b))
        if term.op in _TESTS and isinstance(inputs[0], Factor):
            value = _TESTS[term.op](self.cell(inputs[0], t))
            return _cells(value, np.ones_like(value))
        if term.op in ("all", "any"):
            size, fold = dict(term.params)["window"], getattr(_kernels, f"kleene_{term.op}")
            if t - size + 1 < 0:  # the window starts before the axis: nothing is known there
                return np.full(len(self.block.instrument_ids), np.nan)
            return _cells(*fold(*_truth(self.window(inputs[0], t, size))))
        if term.op == "not":
            value, valid = _truth(self.cell(inputs[0], t))
            return _cells(~value & valid, valid)
        if term.op == "fillna":  # the only explicit fill (INV-12): unknown cells take the value
            value, valid = _truth(self.cell(inputs[0], t))
            return _cells(value | (~valid & dict(term.params)["value"]), np.ones_like(valid))
        raise NotImplementedError(f"the reference executor has no `{term.op}` term yet")

    def codes_test(self, term: Term, t: int) -> F64:
        """A Filter of a Classifier's codes at row t (3.3, R3-13): `isnull` and `notnull` are
        always valid at a listed cell; `eq` and `element_of` are unknown on the missing code -1."""
        codes = _codes(self.cell(term.inputs[0], t))
        if term.op in ("isnull", "notnull"):
            missing = codes == -1
            return _cells(missing if term.op == "isnull" else ~missing, np.ones_like(missing))
        if term.op not in ("eq", "element_of"):
            raise NotImplementedError(f"the reference executor has no `{term.op}` term yet")
        p = dict(term.params)
        wanted = (p["value"],) if term.op == "eq" else tuple(p["values"])
        if not all(type(v) is int for v in wanted):  # names (T2.3) and bools are no codes
            raise NotImplementedError(f"Classifier names come with its code table: {wanted}")
        return _cells(*_kernels.codes_in(codes, np.array(wanted, dtype=np.int32)))

    def frame(self, term: Term, rows: npt.NDArray[np.int64]) -> pa.Table:
        local = rows - self.low
        r, c = np.nonzero(self.block.exists[local])
        ids = np.asarray(self.block.instrument_ids, dtype=object)[c]
        cells = self.values[graph_hash(term)][local[r], c]
        if isinstance(term, Filter):  # null where unknown: Arrow's validity bitmap is the mask
            value, valid = _truth(cells)
            return _frame(rows[r], ids, pa.array(value, pa.bool_(), mask=~valid))
        if isinstance(term, Classifier):
            return _frame(rows[r], ids, pa.array(_codes(cells), pa.int32()))
        return _frame(rows[r], ids, cells)


def term_value(found: F64, listed: npt.NDArray[np.bool_]) -> F64:
    """A term's cells at a row as it holds them (5.4.1): NaN where not listed or ±inf, +0.0 for
    a zero of either sign (#648), every other cell's bits as found."""
    out: F64 = np.where(listed & ~np.isinf(found), np.where(found == 0, 0.0, found), np.nan)
    return out


def _basis(params: Mapping[str, Any]) -> str | None:
    """The column's basis in the table of 3.2; a column of another dataset is not a price."""
    if params["dataset"] != "Price":
        return None
    if params["column"] not in _BASIS:  # `shares_out`: n·Q[t]/Q[a] from its `as_of_date` a
        raise NotImplementedError(f"a window of Price.{params['column']} comes with 5.3.5a")
    return _BASIS[params["column"]]


def _truth(cells: F64) -> tuple[npt.NDArray[np.bool_], npt.NDArray[np.bool_]]:
    """A Filter's held cells as the kernels' value and validity mask."""
    return cells == 1.0, ~np.isnan(cells)


def _codes(cells: F64) -> npt.NDArray[np.int32]:
    """A Classifier's held cells as its int32 codes, -1 the missing code (3.3); a Classifier is
    held as its codes in a float array, as a Filter is (`_cells`)."""
    return np.where(np.isnan(cells), -1, cells).astype(np.int32)


def _cells(value: npt.NDArray[np.bool_], valid: npt.NDArray[np.bool_]) -> F64:
    """A Filter's value and validity mask held as one float array, so its windows, `shift` and
    the chunk's release of values work as a Factor's do."""
    found: F64 = np.where(valid, value.astype(np.float64), np.nan)
    return found


def _frame(rows: Any, ids: Any, values: Any) -> pa.Table:
    row, instrument = pa.array(rows, pa.int64()), pa.array(ids, pa.string())
    value = values if isinstance(values, pa.Array) else pa.array(values, pa.float64())
    return pa.table({"row": row, ID_COLUMN: instrument, "value": value})
