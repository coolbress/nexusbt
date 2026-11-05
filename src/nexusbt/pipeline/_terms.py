"""Spec 3.3 terms as value objects, the 5.3.9 node structural hash, the 6.5 (6) captured constants.

A term is a node: its kind, an operator name, its input terms in order and its parameters. Building
one reads no data (2.5); its hash is fixed when it is built, so `a - b` and `b - a` differ.
"""

from __future__ import annotations

import ast
import hashlib
import inspect
import json
import sys
import textwrap
from collections.abc import Callable, Collection, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from types import CodeType, FunctionType, MappingProxyType
from typing import Any, Literal

from nexusbt.contracts import CapabilityError, LookAheadError


@dataclass(frozen=True, slots=True, eq=False)
class Term:
    op: str
    inputs: tuple[Term, ...] = ()
    params: tuple[tuple[str, Any], ...] = ()
    _key: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if bad := [type(t).__name__ for t in self.inputs if not isinstance(t, Term)]:
            raise TypeError(f"a term's inputs are terms (a column or a Factor), not {bad}")
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
    if isinstance(value, tuple):
        return ["tuple", [_canon(v) for v in value]]
    if isinstance(value, frozenset):
        return ["frozenset", sorted((_canon(v) for v in value), key=json.dumps)]
    raise TypeError(f"{type(value).__name__} cannot be a term parameter")


def _xs(
    mask: Filter | None = None, groupby: Classifier | None = None, across_markets: bool = False
) -> dict[str, Any]:
    """The 3.3 cross-section keywords: `mask`, `groupby`, `across_markets`."""
    return {"mask": mask, "groupby": groupby, "across_markets": across_markets}


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
    # `*a, **k`: the 3.3 `mask=None, groupby=None, across_markets=False`, in that order.
    def rank(self, method: str = "ordinal", ascending: bool = True, *a: Any, **k: Any) -> Factor:
        return _node(Factor, "rank", self, method=method, ascending=ascending, **_xs(*a, **k))
    def zscore(self, *a: Any, **k: Any) -> Factor: return _node(Factor, "zscore", self, **_xs(*a, **k))  # noqa: E501
    def demean(self, *a: Any, **k: Any) -> Factor: return _node(Factor, "demean", self, **_xs(*a, **k))  # noqa: E501
    def winsorize(self, min_percentile: float, max_percentile: float, *a: Any, **k: Any) -> Factor:
        return _node(Factor, "winsorize", self, min=min_percentile, max=max_percentile, **_xs(*a, **k))  # noqa: E501
    def top(self, N: int, *a: Any, **k: Any) -> Filter: return _node(Filter, "top", self, N=N, **_xs(*a, **k))  # noqa: N803, E501
    def bottom(self, N: int, *a: Any, **k: Any) -> Filter: return _node(Filter, "bottom", self, N=N, **_xs(*a, **k))  # noqa: N803, E501
    def percentile_between(self, min_percentile: float, max_percentile: float, mask: Filter | None = None, across_markets: bool = False) -> Filter:  # noqa: E501
        return _node(Filter, "percentile_between", self, min=min_percentile, max=max_percentile, **_xs(mask, None, across_markets))  # noqa: E501
    def pct_rank(self, higher_is_better: bool = True, mask: Filter | None = None, groupby: Classifier | None = None, na: Literal["drop", "bottom", "middle"] = "drop", across_markets: bool = False) -> Factor:  # noqa: E501
        return _node(Factor, "pct_rank", self, higher_is_better=higher_is_better, na=na, **_xs(mask, groupby, across_markets))  # noqa: E501
    def quantiles(self, bins: int, *a: Any, **k: Any) -> Classifier:
        return _node(Classifier, "quantiles", self, bins=bins, **_xs(*a, **k))
    def quartiles(self, *a: Any, **k: Any) -> Classifier: return self.quantiles(4, *a, **k)
    def quintiles(self, *a: Any, **k: Any) -> Classifier: return self.quantiles(5, *a, **k)
    def deciles(self, *a: Any, **k: Any) -> Classifier: return self.quantiles(10, *a, **k)
    def fillna(self, value: float | Factor) -> Factor: return _node(Factor, "fillna", self, _operand(value))  # noqa: E501
    def clip(self, lower: float | None = None, upper: float | None = None) -> Factor:
        return _node(Factor, "clip", self, lower=lower, upper=upper)
    def to(self, ccy: str) -> Factor: return _node(Factor, "to", self, ccy=ccy)
    # fmt: on

    def downsample(self, freq: str) -> Factor:
        raise CapabilityError(
            what=f"downsample({freq!r}) is not in v1",
            where=f"term downsample({freq!r})",
            why="v1 computes every term on the daily session axis",
            fix="compute on the daily axis and pick the decision dates with run_pipeline(freq=...)",
            more="spec 3.3 Factor methods",
            layer=f"your code — {_user_line()}",
        )

    def shift(self, k: int) -> Factor:
        """3.3: the value k sessions earlier; `k < 0` reads the future (E1, 6.5 check 1)."""
        if not isinstance(k, int) or isinstance(k, bool):
            raise TypeError(f"shift(k) takes a whole number of sessions, not {k!r}")
        if k < 0:
            raise _look_ahead(k)
        return self if k == 0 else _node(Factor, "shift", self, k=k)


class Filter(Term):
    """Three-valued (3.3): true, false and unknown."""

    __slots__ = ()

    # fmt: off
    def __and__(self, o: Filter) -> Filter: return _node(Filter, "and", self, _filter(o))
    def __or__(self, o: Filter) -> Filter: return _node(Filter, "or", self, _filter(o))
    def __invert__(self) -> Filter: return _node(Filter, "not", self)
    def if_else(self, if_true: Factor, if_false: Factor) -> Factor:
        return _node(Factor, "if_else", self, if_true, if_false)
    def all(self, window: int) -> Filter: return _node(Filter, "all", self, window=window)
    def any(self, window: int) -> Filter: return _node(Filter, "any", self, window=window)
    def as_factor(self) -> Factor: return _node(Factor, "as_factor", self)
    def fillna(self, value: bool) -> Filter:
        if not isinstance(value, bool):
            raise TypeError(f"a Filter's fillna takes True or False, not {value!r}")
        return _node(Filter, "fillna", self, value=value)
    # fmt: on


def _filter(value: object) -> Filter:
    if isinstance(value, Filter):
        return value
    raise TypeError(f"`&` and `|` combine Filters, not {type(value).__name__}")


class Classifier(Term):
    """int32 codes and a code table (3.3)."""

    __slots__ = ()

    # fmt: off
    def eq(self, value: int | str) -> Filter: return _node(Filter, "eq", self, value=value)
    def element_of(self, values: Collection[int | str]) -> Filter:
        if isinstance(values, str):
            raise TypeError(f"element_of takes a list of codes, not the string {values!r}")
        unordered = isinstance(values, set | frozenset)  # a set's order changes between runs
        return _node(Filter, "element_of", self, values=(frozenset if unordered else tuple)(values))
    def isnull(self) -> Filter: return _node(Filter, "isnull", self)
    def notnull(self) -> Filter: return _node(Filter, "notnull", self)
    def startswith(self, prefix: str) -> Filter: return _node(Filter, "startswith", self, prefix=prefix)  # noqa: E501
    # fmt: on


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


def factor(
    window: int,
    inputs: Sequence[BoundColumn | Factor],
    *,
    mask: Filter | None = None,
    dtype: Literal["float64"] = "float64",
) -> Callable[[Callable[..., Any]], Factor]:
    """3.3 `@nx.factor`: the node and its hash (source and captured constants); running it is
    T1.12's."""

    def wrap(fn: Callable[..., Any]) -> Factor:
        if not isinstance(fn, FunctionType):
            raise TypeError(f"@nx.factor decorates a function, not {type(fn).__name__}")
        try:
            source = ast.dump(ast.parse(textwrap.dedent(inspect.getsource(fn))))
        except (OSError, SyntaxError) as error:
            what = f"@nx.factor cannot read the source of {fn.__name__}; its source goes into the"
            raise TypeError(f"{what} term's hash, so define it with `def` in a file") from error
        return _node(
            Factor, "user", *inputs, window=window, mask=mask, dtype=dtype, function=fn.__name__,
            source=hashlib.sha256((source + _code_key(fn.__code__)).encode()).hexdigest(),
            captured=_captured(fn),
        )  # fmt: skip

    return wrap


def _code_key(code: CodeType) -> str:
    """The compiled body: the source line alone is the same for two lambdas on one line."""
    consts = [_code_key(c) if isinstance(c, CodeType) else repr(c) for c in code.co_consts]
    return json.dumps([code.co_code.hex(), consts, code.co_names, code.co_varnames])


def _captured(fn: FunctionType) -> tuple[tuple[str, Any], ...]:
    """6.5 (6): the constant-like globals, closure cells and defaults the function reads."""
    found = {n: fn.__globals__[n] for n in _names(fn.__code__) if n in fn.__globals__}
    params = inspect.signature(fn).parameters.values()
    found |= {f"{p.name}=": p.default for p in params if p.default is not p.empty}
    for name, cell in zip(fn.__code__.co_freevars, fn.__closure__ or (), strict=True):
        try:
            found[name] = cell.cell_contents
        except ValueError:  # an empty cell: its value would be missing from the hash
            raise TypeError(f"{name}, read by {fn.__name__}, has no value yet") from None
    return tuple(sorted((n, v) for n, v in found.items() if _constant(v)))


def _names(code: CodeType) -> Iterator[str]:
    yield from code.co_names
    for const in code.co_consts:
        if isinstance(const, CodeType):
            yield from _names(const)


def _constant(value: object) -> bool:
    """int, float, str, bool, None, and tuples and frozensets of them, exactly (6.5 (6))."""
    if value is None or type(value) in (int, float, str, bool):
        return True
    if isinstance(value, tuple | frozenset) and type(value) in (tuple, frozenset):
        return all(_constant(v) for v in value)
    return False


def describe_term(term: Term) -> str:
    """The node tree, one node a line with its parameters, then the structural hash."""
    return "\n".join([*_tree(term, ""), f"graph hash: {graph_hash(term)}"])


def _tree(term: Term, indent: str, role: str = "") -> Iterator[str]:
    params = dict(term.params)
    if isinstance(term, BoundColumn):
        label = f"BoundColumn {params['dataset']}.{params['column']}"
    else:
        shown = [f"{n}={v}" for n, v in params.get("captured", ())]
        shown += [f"{n}={v}" for n, v in params.items() if _shown(n, v)]
        label = " ".join([type(term).__name__, term.op, *shown])
    yield f"{indent}{role}{label}"
    for child in term.inputs:
        yield from _tree(child, indent + "  ")
    for name, value in term.params:
        if isinstance(value, Term):
            yield from _tree(value, indent + "  ", f"{name}=")


def _shown(name: str, value: object) -> bool:
    return name not in ("captured", "source") and not isinstance(value, Term | None)


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
