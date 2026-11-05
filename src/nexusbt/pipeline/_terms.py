"""Spec 3.3 terms as value objects and the 5.3.9 node structural hash.

A term is a node: its kind, an operator name, its input terms in order and its parameters. Building
one reads no data (2.5); its hash is fixed when it is built, so `a - b` and `b - a` differ.
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any

from nexusbt.contracts import LookAheadError


@dataclass(frozen=True, slots=True, eq=False)
class Term:
    op: str
    inputs: tuple[Term, ...] = ()
    params: tuple[tuple[str, Any], ...] = ()
    _key: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        body: list[Any] = [type(self).__name__, self.op, [t._key for t in self.inputs]]
        body.append([[name, _canon(value)] for name, value in self.params])
        text = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
        object.__setattr__(self, "_key", hashlib.sha256(text.encode()).hexdigest())

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Term) and other._key == self._key

    def __hash__(self) -> int:
        return int(self._key[:16], 16)


def _node[T: Term](kind: type[T], op: str, *inputs: Term, **params: Any) -> T:
    return kind(op, inputs, tuple(params.items()))


def _canon(value: Any) -> Any:
    """A parameter as JSON that keeps its type: `1`, `1.0`, `True` and `"1"` differ."""
    if isinstance(value, Term):
        return {"term": value._key}
    if value is None or isinstance(value, str):
        return value
    if isinstance(value, bool | int | float):
        return [type(value).__name__, repr(value)]
    raise TypeError(f"{type(value).__name__} cannot be a term parameter")


def _operand(value: object) -> Factor:
    if isinstance(value, Factor):
        return value
    if isinstance(value, int | float) and not isinstance(value, bool):
        return _node(Factor, "constant", value=float(value))
    raise TypeError(f"a Factor operand is a Factor or a number, not {type(value).__name__}")


class Factor(Term):
    """`==` builds a Filter (3.3), so `in` and `.index` on Factors do not compare them: code that
    finds shared nodes compares `graph_hash`."""

    __slots__ = ()
    __hash__ = Term.__hash__

    def _op(self, op: str, other: object, swap: bool = False) -> Factor:
        a, b = (_operand(other), self) if swap else (self, _operand(other))
        return _node(Factor, op, a, b)

    def _cmp(self, op: str, other: object) -> Filter:
        return _node(Filter, op, self, _operand(other))

    # fmt: off
    def __add__(self, o: Factor | float) -> Factor: return self._op("add", o)
    def __radd__(self, o: float) -> Factor: return self._op("add", o, swap=True)
    def __sub__(self, o: Factor | float) -> Factor: return self._op("sub", o)
    def __rsub__(self, o: float) -> Factor: return self._op("sub", o, swap=True)
    def __mul__(self, o: Factor | float) -> Factor: return self._op("mul", o)
    def __rmul__(self, o: float) -> Factor: return self._op("mul", o, swap=True)
    def __truediv__(self, o: Factor | float) -> Factor: return self._op("div", o)
    def __rtruediv__(self, o: float) -> Factor: return self._op("div", o, swap=True)
    def __pow__(self, o: Factor | float) -> Factor: return self._op("pow", o)
    def __rpow__(self, o: float) -> Factor: return self._op("pow", o, swap=True)
    def __neg__(self) -> Factor: return _node(Factor, "neg", self)
    def __abs__(self) -> Factor: return _node(Factor, "abs", self)
    def log(self) -> Factor: return _node(Factor, "log", self)
    def log1p(self) -> Factor: return _node(Factor, "log1p", self)
    def exp(self) -> Factor: return _node(Factor, "exp", self)
    def sqrt(self) -> Factor: return _node(Factor, "sqrt", self)
    def __lt__(self, o: Factor | float) -> Filter: return self._cmp("lt", o)
    def __le__(self, o: Factor | float) -> Filter: return self._cmp("le", o)
    def __gt__(self, o: Factor | float) -> Filter: return self._cmp("gt", o)
    def __ge__(self, o: Factor | float) -> Filter: return self._cmp("ge", o)
    def __eq__(self, o: object) -> Filter: return self._cmp("eq", o)  # type: ignore[override]
    def __ne__(self, o: object) -> Filter: return self._cmp("ne", o)  # type: ignore[override]
    def isnan(self) -> Filter: return _node(Filter, "isnan", self)
    def notnan(self) -> Filter: return _node(Filter, "notnan", self)
    def isfinite(self) -> Filter: return _node(Filter, "isfinite", self)
    def isnull(self) -> Filter: return _node(Filter, "isnull", self)
    def notnull(self) -> Filter: return _node(Filter, "notnull", self)
    # fmt: on

    def shift(self, k: int) -> Factor:
        """3.3: the value k sessions earlier; `k < 0` reads the future (E1, 6.5 check 1)."""
        if not isinstance(k, int) or isinstance(k, bool):
            raise TypeError(f"shift(k) takes a whole number of sessions, not {k!r}")
        if k < 0:
            raise _look_ahead(k)
        return self if k == 0 else _node(Factor, "shift", self, k=k)


class Filter(Term):
    """Three-valued (3.3); its methods come with the second part of T1.5."""

    __slots__ = ()


class Classifier(Term):
    """int32 codes and a code table (3.3); its methods come with the second part of T1.5."""

    __slots__ = ()


class BoundColumn(Term):
    """A dataset column (3.2); the datasets bind theirs with T1.6."""

    __slots__ = ()

    @classmethod
    def of(cls, dataset: str, column: str) -> BoundColumn:
        return _node(cls, "column", dataset=dataset, column=column)

    @property
    def latest(self) -> Factor:
        return _node(Factor, "latest", self)


@dataclass(frozen=True, slots=True, eq=False)
class Pipeline:
    """3.5 `nx.Pipeline(columns, screen=None)`: named output terms and an optional row filter."""

    columns: Mapping[str, Term]
    screen: Filter | None = None

    def __post_init__(self) -> None:
        if bad := [name for name, term in self.columns.items() if not isinstance(term, Term)]:
            raise TypeError(f"Pipeline columns must be terms: {bad}")
        if self.screen is not None and not isinstance(self.screen, Filter):
            raise TypeError(f"Pipeline screen must be a Filter, not {type(self.screen).__name__}")
        object.__setattr__(self, "columns", MappingProxyType(dict(self.columns)))


def graph_hash(term: Term) -> str:
    """5.3.9 node structural hash: kind, operator, parameters and input hashes, in order."""
    return term._key


def describe_term(term: Term) -> str:
    """The node tree, one node a line with its parameters, then the structural hash."""
    return "\n".join([*_tree(term, ""), f"graph hash: {graph_hash(term)}"])


def _tree(term: Term, indent: str, role: str = "") -> Iterator[str]:
    params = dict(term.params)
    if isinstance(term, BoundColumn):
        label = f"BoundColumn {params['dataset']}.{params['column']}"
    else:
        shown = [f"{n}={v}" for n, v in params.items() if not isinstance(v, Term | None)]
        label = " ".join([type(term).__name__, term.op, *shown])
    yield f"{indent}{role}{label}"
    for child in term.inputs:
        yield from _tree(child, indent + "  ")
    for name, value in term.params:
        if isinstance(value, Term):
            yield from _tree(value, indent + "  ", f"{name}=")


def _look_ahead(k: int) -> LookAheadError:
    line = _user_line()
    return LookAheadError(
        what=f"shift({k}) reads a value from after the computation day ({-k} session(s) later)",
        where=f"term shift({k})",
        why="a term may read only values known on its own day; a later value is not known yet",
        fix="use .shift(k) with k ≥ 1, nx.ops.rolling(...), or window style",
        more="spec 3.3 shift and 6.5 check 1",
        layer=f"your code — {line}",
        at=line.split(" in ")[0],
        subject=f"shift({k})",
    )


def _user_line() -> str:
    """`file:line in function` of the first frame outside this module (6.6 header)."""
    frame = sys._getframe(1)
    while frame.f_code.co_filename == __file__ and frame.f_back is not None:
        frame = frame.f_back
    name = frame.f_code.co_name
    where = f"{Path(frame.f_code.co_filename).name}:{frame.f_lineno}"
    return f"{where} in {name if name.isidentifier() else 'module'}"
