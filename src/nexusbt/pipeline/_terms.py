"""Spec 3.3 terms as value objects, the 5.3.9 node structural hash, the 6.5 (6) captured constants.

A term is a node: its kind, an operator name, its input terms in order and its parameters. Building
one reads no data (2.5); its hash is fixed when it is built, so `a - b` and `b - a` differ.
"""

from __future__ import annotations

import ast
import dis
import functools
import hashlib
import importlib.util
import inspect
import json
import re
import sys
import sysconfig
import textwrap
import traceback
import warnings
from collections.abc import Callable, Collection, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from types import CodeType, FunctionType, MappingProxyType, ModuleType
from typing import Any, Literal, TypeGuard

import numpy as np
import numpy.typing as npt

from nexusbt.contracts import (
    CapabilityError,
    ConfigError,
    ImpureFunctionWarning,
    LookAheadError,
    SkippedWorkNotice,
    TermDomainError,
    WindowError,
)


@dataclass(frozen=True, slots=True, eq=False)
class Term:
    op: str
    inputs: tuple[Term, ...] = ()
    params: tuple[tuple[str, Any], ...] = ()
    #: A user term's function (3.3 `@nx.factor`); its source and constants are in `params`, so
    #: it is not hashed again.
    function: Callable[..., Any] | None = field(default=None, kw_only=True, repr=False)
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
    _one_of("a cross-section method", "across_markets", across_markets, (True, False))
    return {"mask": mask, "groupby": groupby, "across_markets": across_markets}


def _one_of(op: str, name: str, value: object, allowed: tuple[object, ...]) -> None:
    """3.3, 6.6 E16 (#602): an argument with a closed set of values takes one of them, by type
    as well as value, so `1` is not `True`: one computation, one graph hash. A `str` subclass
    is a `str` here, as `_canon` hashes it as its plain string."""
    if any(isinstance(value, type(a)) and value == a for a in allowed):
        return
    raise ConfigError(
        what=f"{name}={value!r} is not a value {op} takes",
        where=f"{op}({name}=...)",
        why=f"{op}'s {name} is one of a closed set of values (spec 3.3)",
        fix=f"{name}= one of {', '.join(map(repr, allowed))}",
        more="spec 3.3 (Factor methods)",
        layer=f"config — argument {name}={value!r}",
    )


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
    def abs(self) -> Factor: return _node(Factor, "abs", self)
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
        _one_of("rank", "method", method, ("ordinal", "average", "min", "max", "dense"))
        _one_of("rank", "ascending", ascending, (True, False))
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
        _one_of("pct_rank", "na", na, ("drop", "bottom", "middle"))
        _one_of("pct_rank", "higher_is_better", higher_is_better, (True, False))
        return _node(Factor, "pct_rank", self, higher_is_better=higher_is_better, na=na, **_xs(mask, groupby, across_markets))  # noqa: E501
    def quantiles(self, bins: int, *a: Any, **k: Any) -> Classifier:
        if type(bins) is not int or bins < 1:  # #602: E16 at build, not the kernel's at run
            raise ConfigError(
                what=f"bins={bins!r} is not a number of bins quantiles takes",
                where="quantiles(bins=...)", why="a cross-section is cut into 1 or more bins",
                fix="bins= a whole number, 1 or more (quartiles() is quantiles(4))",
                more="spec 3.3 (Factor methods), 5.4.3", layer=f"config — argument bins={bins!r}",
            )  # fmt: skip
        return _node(Classifier, "quantiles", self, bins=bins, **_xs(*a, **k))
    def quartiles(self, *a: Any, **k: Any) -> Classifier: return self.quantiles(4, *a, **k)
    def quintiles(self, *a: Any, **k: Any) -> Classifier: return self.quantiles(5, *a, **k)
    def deciles(self, *a: Any, **k: Any) -> Classifier: return self.quantiles(10, *a, **k)
    def fillna(self, value: float | Factor) -> Factor: return _node(Factor, "fillna", self, _operand(value))  # noqa: E501
    def clip(self, lower: float | None = None, upper: float | None = None) -> Factor:
        return _node(Factor, "clip", self, lower=lower, upper=upper)
    def to(self, ccy: str) -> Factor: return _node(Factor, "to", self, ccy=ccy)
    # fmt: on

    def __call__(self, *arrays: Any, **values: Any) -> Factor:
        """3.3: a user function with keyword parameters bound, `f(n=63)`, a new Factor; the
        values are in its graph hash and are passed to the function when it runs. A call with
        an array is E16 naming `.function`, the plain function, unbound (#582)."""
        fn = self.function
        if self.op != "user" or fn is None:
            raise TypeError(f"only a user function's Factor takes keyword values, not {self.op}")
        named = (inspect.Parameter.KEYWORD_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
        windows = len(self.inputs)  # the first parameters are the inputs' windows
        if arrays:  # the keywords of this call too, as binding them would keep them
            bound = {**dict(dict(self.params).get("bound", ())), **values}
            raise _called_with_arrays(fn, windows, tuple(sorted(bound.items())))
        listed = list(inspect.signature(fn).parameters.values())[windows:]
        taken = {p.name for p in listed if p.kind in named}
        for name, value in values.items():
            if name not in taken:
                raise TypeError(f"{fn.__name__} takes no keyword {name!r}")
            if not _constant(value):
                raise TypeError(f"{name}={value!r}: a bound value is constant-like (6.5 (6))")
        params = dict(self.params)
        params["bound"] = tuple(sorted({**dict(params.get("bound", ())), **values}.items()))
        return Factor(self.op, self.inputs, tuple(params.items()), function=fn)

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


def _called_with_arrays(
    fn: Callable[..., Any], windows: int, bound: tuple[tuple[str, Any], ...]
) -> ConfigError:
    """3.3 (#582): E16 for `f(prices)`, its fix the `.function` call with the bound values."""
    name = fn.__name__
    args = [*list(inspect.signature(fn).parameters)[:windows], *(f"{k}={v!r}" for k, v in bound)]
    return ConfigError(
        what=f"{name} was called with an array; a call binds keyword values and makes a Factor",
        where=f"{name}(...)",
        why="the decorated name is a Factor: f(n=63) binds n, and the engine runs the function",
        fix=f"{name}.function({', '.join(args)}) on the arrays, one for each input",
        more="spec 3.3 (user window functions)",
        layer=f"config — a positional argument to {name}",
        at=_user_line().split(" in ")[0],
        subject=name,
    )


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
    adjustment: Literal["degree 0", "degree 1"] | None = None,
) -> Callable[[Callable[..., Any]], Factor]:
    """3.3 `@nx.factor`: the node, its hash (source, captured constants and the declared
    `adjustment`) and the function the executor runs on its windows (5.3.7)."""
    if adjustment not in (None, "degree 0", "degree 1"):
        raise ConfigError(
            what=f"adjustment={adjustment!r} is not a declaration @nx.factor takes",
            where="@nx.factor(adjustment=...)",
            why="a declaration says what the result is when one instrument's inputs are scaled",
            fix='adjustment="degree 0" for a ratio or a return, "degree 1" for a level,'
            " or no adjustment",
            more="spec 3.3 (adjustment) and 3.4",
            layer=f"config — argument adjustment={adjustment!r}",
        )

    def wrap(fn: Callable[..., Any]) -> Factor:
        if not isinstance(fn, FunctionType):
            raise TypeError(f"@nx.factor decorates a function, not {type(fn).__name__}")
        reads = _reads(fn)
        source = "".join(f"\n{h.__qualname__}\n{_readable(h)}" for h in reads.helpers)
        digest = hashlib.sha256((_readable(fn) + source).encode()).hexdigest()
        params = {"window": window, "mask": mask, "dtype": dtype, "function": fn.__name__,
                  "source": digest, "captured": reads.captured}  # fmt: skip
        if adjustment is not None:  # absent when not declared: the hash stays as it was
            params["adjustment"] = adjustment
        if reads.e24:
            warning = _impure(fn.__name__, reads.impure, reads.decorator, reads.under, reads.lost)
            warnings.warn(str(warning), stacklevel=2)
        return Factor("user", tuple(inputs), tuple(params.items()), function=fn)

    return wrap


def _impure(
    name: str,
    globals_: Sequence[str],
    decorator: str = "",
    under: Sequence[tuple[str, str, str]] = (),
    lost: Sequence[tuple[str, str, str]] = (),
) -> ImpureFunctionWarning:
    """E24 for the globals `name` reads, for the library decorator it is under whose wrapper
    holds what the hash cannot read (#645), for each helper read under one (#676), and for each
    class or module read that cannot be found by its name (#690): what the user wrote, never a
    name inside the library."""
    line = _user_line()
    shown = ", ".join(repr(g) for g in globals_)
    what, fix = [], []
    if globals_:
        what.append(f"{name} reads global {shown}; the engine cannot check what it contains")
        fix.append(f"pass {shown} as an input, or as a constant (int, float, str, bool, None, or a"
                   " tuple or frozenset of them), whose value goes into the hash; a library's"
                   " object, read it through its module (`lib.thing`)")  # fmt: skip
    if decorator:
        what.append(f"{name} is under {decorator}, whose wrapper holds what the engine cannot"
                    " check")  # fmt: skip
        fix.append(f"apply @nx.factor to a function that is not under @{decorator}; the engine"
                   f" hashes {name}'s own code and the helpers it calls, not what the decorator's"
                   " wrapper holds")  # fmt: skip
    for reader, helper, held in under:
        what.append(f"{reader} reads {helper}, which is under {held}, whose wrapper holds what the"
                    " engine cannot check")  # fmt: skip
        fix.append(f"read a function that is not under @{held} in place of {helper}; the engine"
                   f" hashes {helper}'s own code and the helpers it calls, not what the"
                   " decorator's wrapper holds")  # fmt: skip
    for read, cls, module in lost:
        whose = f"class {cls} as '{read}', whose module" if cls else "module"
        how = f"'{module}'" if cls else f"'{module}' as '{read}', which"
        what.append(f"{name} reads {whose} {how} cannot be found by its name; the engine cannot"
                    " check what it contains")  # fmt: skip
        fix.append(f"load the file that defines {cls or f'module {module!r}'} with an import"
                   " statement, which puts it in sys.modules under its name, and read it from"
                   " there; runpy.run_path, exec and a spec loaded without registering it leave it"
                   " out")  # fmt: skip
    return ImpureFunctionWarning(
        what="; ".join(what),
        where=f"function {name}",
        why=f"a hidden input breaks reruns and checks; L1 cache disabled for node {name} and the"
        " nodes that read it",
        fix="; ".join(fix),
        more="spec 3.7, 5.3.7 and 6.5 (6)",
        layer=f"your code — {line}",
        at=line.split(" in ")[0],
        subject=name,
    )


def l1_disabled(term: Term) -> bool:
    """5.3.9, 6.5 (6): whether the L1 cache is off for `term`: it, or a node it reads, is a user
    function that reads a non-constant global or a file (E24)."""
    todo, seen = [term], set[str]()
    while todo:
        node = todo.pop()
        if node._key in seen:
            continue
        seen.add(node._key)
        if isinstance(node.function, FunctionType) and _reads(node.function).e24:
            return True
        todo += [*node.inputs, *(v for _, v in node.params if isinstance(v, Term))]
    return False


_OUT_OF_WINDOW = re.compile(r"index (-?\d+) is out of bounds for axis 0 with size (\d+)")


def call_user(
    term: Term, windows: Sequence[Any], n: int, fn: Callable[..., Any] | None = None
) -> npt.NDArray[np.float64]:
    """A user term's function (`fn`, else the one it was built from) on its input windows
    (5.3.7), its result as float64 `(n,)`. A row before the window is `WindowError` (E8)
    suggesting the window it needs, as is a result of another shape or of a non-numeric dtype;
    any other exception is the user's, as raised, through frames hidden from its traceback
    (`__tracebackhide__`, R-42), as the executor's on the way here are."""
    __tracebackhide__ = True
    params, fn = dict(term.params), fn or term.function
    if fn is None:
        raise ValueError(f"no function given for the user term {params['function']}")
    name, window = params["function"], params["window"]
    try:
        got = np.asarray(fn(*windows, **dict(params.get("bound", ()))))
    except IndexError as error:
        found = _OUT_OF_WINDOW.fullmatch(str(error))
        if found is None or int(found[2]) != window:
            raise
        k = int(found[1])
        needed = -k if k < 0 else k + 1
        frame = traceback.extract_tb(error.__traceback__)[-1]
        at = f"{Path(frame.filename).name}:{frame.lineno}"
        names = list(inspect.signature(fn).parameters)
        column = names[0] if len(term.inputs) == 1 and names else "an input"
        raise _window_error(name, at, f"reads {column}[{k}] but window={window}",
                            f"@nx.factor(window={needed}, ...)") from error  # fmt: skip
    if got.shape != (n,) or got.dtype != np.float64:
        at = _user_line().split(" in ")[0]
        raise _window_error(name, at, f"returned {got.dtype} {got.shape}, not float64 ({n},)",
                            "return one float64 number for each column of the window")  # fmt: skip
    return got


def same_function(a: Callable[..., Any] | None, b: Callable[..., Any] | None) -> bool:
    """Whether two user terms of one graph hash run the same computation. The hash holds their
    source and constants (6.5 (6)), so what can differ is what they read that is not constant:
    their module's globals, closures and defaults, each the same object here."""
    if a is b or not (isinstance(a, FunctionType) and isinstance(b, FunctionType)):
        return a is b

    def read(f: FunctionType) -> list[Any]:
        cells = [c.cell_contents for c in f.__closure__ or ()]
        return [f.__globals__, *cells, *(f.__defaults__ or ()), *(f.__kwdefaults__ or {}).values()]

    pairs = zip(read(a), read(b), strict=True)
    return all(x is y or (_constant(x) and x == y) for x, y in pairs)


#: 3.3 `adjustment`: one instrument's input windows are multiplied by this fixed constant.
SCALE = 2.0


def check_adjustment(
    term: Term, windows: Sequence[Any], got: npt.NDArray[np.float64], ids: Sequence[str],
    scales: Sequence[float], fn: Callable[..., Any] | None = None,
) -> bool:  # fmt: skip
    """3.3: test a user term's declared `adjustment` on the `windows` (unchanged copies of the
    ones the function was given) and its result `got`, on the first column whose result is
    finite and not 0, each input's column multiplied by its scale (`_degree.input_scales`):
    E17 when the declaration does not hold; False when no column could tell (NaN and 0 are the
    same under any scaling), True once checked."""
    params = dict(term.params)
    declared = params["adjustment"]
    found = np.flatnonzero(np.isfinite(got) & (got != 0))
    if not found.size:
        return False
    j = int(found[0])
    scaled = [np.array(w, dtype=np.float64) for w in windows]
    for window, scale in zip(scaled, scales, strict=True):
        window[:, j] *= scale
    again = call_user(term, scaled, len(got), fn)[j]
    expected = got[j] * (SCALE if declared == "degree 1" else 1.0)
    if abs(again - expected) <= 1e-12 * max(1.0, abs(expected)):
        return True
    name, at = params["function"], def_line(fn or term.function)
    other = "degree 1" if declared == "degree 0" else "degree 0"
    return_ = "change" if declared == "degree 0" else f"scale by {SCALE:g}"
    raise TermDomainError(
        what=f"{name} is declared adjustment='{declared}' but its result for {ids[j]} went from"
        f" {got[j]!r} to {again!r} when {ids[j]}'s prices were scaled by {SCALE:g}",
        where=f"factor {name}",
        why=f"a declared '{declared}' result does not {return_} under that scaling, and the"
        " refusal of shift and window inputs (3.4) reads the declaration",
        fix=f"remove adjustment=..., or declare '{other}' if that is what {name} is",
        more="spec 3.3 (adjustment), 3.4 and 6.6 (E17)",
        layer=f"your code — {at} in {name}",
        at=at,
        subject=name,
    )


def def_line(fn: object) -> str:
    """`file:line` of a function's `def`; `-` for a callable that is not a plain function."""
    code = getattr(fn, "__code__", None)
    return f"{Path(code.co_filename).name}:{code.co_firstlineno}" if code else "-"


#: Why a declaration was not checked, by whether its inputs' degrees are known (E45).
UNCHECKED = {
    True: ("every result it gave in this run was NaN or 0, which any scaling leaves as it is,"
           " so it cannot tell degree 0 from degree 1",
           "run it over rows where it gives finite, non-zero values, or remove adjustment=..."),
    False: ("an input has no known degree in the price factor (3.4), so the engine cannot say"
            " what that input is when prices are scaled", "remove adjustment=..."),
}  # fmt: skip


def unchecked(name: str, declared: str, at: str, scalable: bool) -> SkippedWorkNotice:
    """6.6 no silent failure: a declaration the run could not check (E45)."""
    why, fix = UNCHECKED[scalable]
    return SkippedWorkNotice(
        what=f"skipped 1 declaration check for reason declaration_unchecked: {name}'s"
        f" adjustment='{declared}' was not checked",
        where=f"factor {name}",
        why=why,
        fix=fix,
        more="spec 3.3 (adjustment) and 6.6 (no silent failure)",
        layer=f"your code — {at} in {name}",
        at=at,
        subject=name,
    )


def _window_error(name: str, at: str, what: str, fix: str) -> WindowError:
    return WindowError(
        what=f"{name} {what}",
        where=f"factor {name}",
        why="the function's window is the rows and shape the engine loads for it",
        fix=fix,
        more="spec 3.3 and 5.3.7 (windows)",
        layer=f"your code — {at} in {name}",
        at=at,
        subject=name,
    )


def _readable(fn: FunctionType) -> str:
    """`fn`'s canonical source; a function a library decorator made is read as the project
    function it keeps (#596), as a helper is."""
    try:
        return _source(_helper(fn) or fn)
    except (OSError, SyntaxError) as error:
        what = f"@nx.factor cannot read the source of {fn.__name__}; its source goes into the"
        raise TypeError(f"{what} term's hash, so define it with `def` in a file") from error


def _source(fn: FunctionType) -> str:
    """5.3.9 canonical source: the AST dump of the function's own node, so comments and spacing do
    not count. A lambda's source line may hold other lambdas: its node is the innermost Lambda
    whose body holds the code's first real position (the first, `RESUME`, has column 0; a lambda
    nested in the body starts inside the body, never inside its own). The source is read from the
    function's own code, never through `__wrapped__` (#596): a `functools.wraps` decorator's inner
    function is hashed as the code that runs, and the function it wraps as a helper of its own."""
    raw = inspect.getsource(fn.__code__)
    tree = ast.parse(textwrap.dedent(raw))
    spots = [(n, c) for n, _, c, e in fn.__code__.co_positions() if n and c is not None and e]
    if fn.__name__ != "<lambda>" or not spots:
        return ast.dump(tree)
    first = raw.splitlines()[0]
    line = spots[0][0] - fn.__code__.co_firstlineno + 1
    at = (line, spots[0][1] - (len(first) - len(first.lstrip())))
    found = [node for node in ast.walk(tree) if isinstance(node, ast.Lambda) and _holds(node, at)]
    return ast.dump(max(found, key=lambda n: (n.lineno, n.col_offset))) if found else ast.dump(tree)


def _holds(node: ast.Lambda, at: tuple[int, int]) -> bool:
    body = node.body
    end = (body.end_lineno or body.lineno, body.end_col_offset or 0)
    return (body.lineno, body.col_offset) <= at < end


@dataclass(frozen=True, slots=True)
class _Reads:
    """What a user function reads (6.5 (6)): its project helpers, to any depth; the constant-like
    values (a helper's as `module.qualname:name`, #673), hashed; the rest and file reads, E24's;
    the library decorator whose wrapper holds what the hash cannot read, E24's too (#645), and
    for a helper under one, the function reading it, the name it reads and the decorator (#676);
    a class or module read that cannot be found by its name, as the name it is read by, the
    class's qualified name (empty for a module) and the module's name, E24's too (#690)."""

    helpers: tuple[FunctionType, ...]
    captured: tuple[tuple[str, Any], ...]
    impure: tuple[str, ...]
    decorator: str = ""
    under: tuple[tuple[str, str, str], ...] = ()
    lost: tuple[tuple[str, str, str], ...] = ()

    @property
    def e24(self) -> bool:
        """Whether what was read holds anything the hash cannot (6.5 (6)): E24, L1 off."""
        return bool(self.impure or self.decorator or self.under or self.lost)


@functools.cache
def _real(path: str | Path) -> Path:
    """`path` with its links followed, once per path: `_OUTSIDE`'s folders are resolved the first
    time a file is compared, not for each user function."""
    return Path(path).resolve()


def _stdlib_zips(path: Sequence[str], base: str) -> tuple[Path, ...]:
    """The `.zip` entries of `path` that lie under the interpreter's folder `base`, as written or
    with links followed (#573): a standard library shipped as `lib/pythonXY.zip` (#577). Decided
    by where the file is, never by module name: a project file named `random.py` stays inside."""
    roots = (Path(base), _real(base))
    zips = (Path(p) for p in path if p.endswith(".zip"))
    return tuple(z for z in zips if any(n.is_relative_to(r) for n in (z, _real(z)) for r in roots))


def _engine_package(name: str) -> tuple[Path, ...]:
    """The folder of the engine's package `name`, found without importing it."""
    spec = importlib.util.find_spec(name)
    return () if spec is None or spec.origin is None else (Path(spec.origin).parent,)


#: Code outside the project (6.5 (6), #577): the engine's own packages (`nexusbt`, `nexusbt_tds`,
#: editable in development too), the standard library, zipped or not, and the packages installed
#: into the library folders. A package installed in editable mode elsewhere is inside.
_INSTALLED = ("stdlib", "platstdlib", "purelib", "platlib")
_OUTSIDE = (
    Path(__file__).parents[1],
    *_engine_package("nexusbt_tds"),
    *(Path(p) for k, p in sysconfig.get_paths().items() if k in _INSTALLED),
    *_stdlib_zips(sys.path, sys.base_prefix),
)
#: Names that open a file (6.5 (6)): `open`, `np.load` and the like, `pd.read_*`, `pl.read_*`.
_FILE_READS = frozenset({"open", "load", "loadtxt", "genfromtxt", "fromfile", "memmap"})


def _in_project(value: object) -> TypeGuard[FunctionType]:
    return isinstance(value, FunctionType) and _project_file(value.__code__.co_filename)


def _project_file(file: str) -> bool:
    """Outside when the path as written or where it leads is under a folder of `_OUTSIDE` as
    written or where it leads (#573): a library reached through a link (a Homebrew Python's
    `opt/` folder) holds files named by the link's target, and an installed file can itself be a
    link into a store (`uv`'s symlink link mode)."""
    path = Path(file)
    if not path.is_absolute():
        return False
    folders = [f for p in _OUTSIDE for f in (Path(p), _real(p))]
    return not any(n.is_relative_to(f) for n in (path, _real(file)) for f in folders)


def _reads(fn: FunctionType) -> _Reads:
    """What `fn` reads; for a library's function keeping a project function in `__wrapped__`
    (`functools.singledispatch`), both (#645): the project function's reads as if undecorated,
    and the wrapper's by `_wrapper`, not again through the project function."""
    inner = _helper(fn)
    if inner is None or inner is fn:
        return _walk(fn, set())
    own = _walk(inner, set())
    held = _wrapper(fn, "", {id(inner), *map(id, own.helpers)})
    helpers = sorted((*own.helpers, *held.helpers), key=lambda h: h.__qualname__)
    captured = sorted((*own.captured, *held.captured), key=lambda c: c[0])
    return _Reads(tuple(helpers), tuple(captured), own.impure, held.decorator, own.under, own.lost)


def _wrapper(fn: FunctionType, prefix: str, seen: set[int]) -> _Reads:
    """A library's function `fn` keeping a project function in `__wrapped__`, judged by #589's
    rule without walking the functions in `seen` (the project function, #645), wherever the
    project function is read: the term's own function or a helper (#676). The wrapper's own
    constants go in under `prefix` and the decorator's name (a decorator's argument passed by name
    is not in the source); the defaults it shows are the project function's, already in. What the
    wrapper holds that the hash cannot read is E24, naming the decorator."""
    held = _walk(fn, seen)
    decorator = _decorator(fn)
    theirs = [(n if ":" in n else f"{prefix}{decorator}:{n}", v) for n, v in held.captured
              if not n.endswith("=")]  # fmt: skip
    unread = held.impure or held.under or held.lost
    return _Reads(held.helpers, tuple(theirs), (), decorator if unread else "")


def _decorator(wrapper: FunctionType) -> str:
    """`module.name` of the library decorator that made `wrapper` (`functools.singledispatch`):
    its code's qualified name up to the decorator's locals, in the module of its globals."""
    home = wrapper.__globals__.get("__name__", "?")
    return f"{home}.{wrapper.__code__.co_qualname.split('.<locals>')[0]}"


def _walk(fn: FunctionType, seen: set[int]) -> _Reads:
    """What `fn` and the project helpers it reaches read, skipping the functions in `seen`."""
    found = _defaults(fn)
    helpers: list[FunctionType] = []
    impure: set[str] = set()
    under: set[tuple[str, str, str]] = set()
    lost: set[tuple[str, str, str]] = set()
    todo = [fn]
    while todo:
        f = todo.pop()
        if id(f) in seen:
            continue
        seen.add(id(f))
        names, attrs = _loads(f.__code__)
        values = _values(f, names)
        prefix = "" if f is fn else _prefix(f)
        judged = _judge(sorted(values.items()), attrs, prefix, found, impure, lost)
        for name, value, helper in judged:
            todo.append(helper)
            if isinstance(value, FunctionType) and value is not helper:  # a library's wrapper
                held = _wrapper(value, _prefix(helper), {*seen, id(helper)})
                helpers += held.helpers
                found.update(held.captured)
                if held.decorator and f is not helper:  # not again by itself, calling itself
                    under.add((f.__name__, name, held.decorator))
        impure.update(_opens(names, values, attrs))
        helpers += [] if f is fn else [f]
    ordered = sorted(dict.fromkeys(helpers), key=lambda h: h.__qualname__)  # once each, in order
    return _Reads(tuple(ordered), tuple(sorted(found.items())), tuple(sorted(impure)),
                  under=tuple(sorted(under)), lost=tuple(sorted(lost)))  # fmt: skip


def _prefix(f: FunctionType) -> str:
    """The key a helper's constants go in under, `module.qualname:` (#673)."""
    return f"{f.__globals__.get('__name__', '?')}.{f.__qualname__}:"


def _defaults(fn: FunctionType) -> dict[str, Any]:
    """The constant-like defaults of `fn`'s parameters, as `name=`."""
    params = inspect.signature(fn).parameters.values()
    return {f"{p.name}=": p.default for p in params
            if p.default is not p.empty and _constant(p.default)}  # fmt: skip


def _values(f: FunctionType, names: set[str]) -> dict[str, Any]:
    """The values `f` reads by name: the globals it loads, then its closure's cells."""
    values = {n: f.__globals__[n] for n in names if n in f.__globals__}
    for name, cell in zip(f.__code__.co_freevars, f.__closure__ or (), strict=True):
        try:
            values[name] = cell.cell_contents
        except ValueError:  # an empty cell: its value would be missing from the hash
            raise TypeError(f"{name}, read by {f.__name__}, has no value yet") from None
    return values


def _judge(
    reads: list[tuple[str, Any]],
    attrs: set[str],
    prefix: str,
    found: dict[str, Any],
    impure: set[str],
    lost: set[tuple[str, str, str]],
) -> list[tuple[str, Callable[..., Any], FunctionType]]:
    """Sort what one function reads, last name first: a constant into `found` (under `prefix`),
    a class or module that cannot be found by its name into `lost` (#690), a project namespace
    into the attributes read of it, data or a callable not found again by reference into
    `impure`; the project helpers it reaches are returned, in the order met, each with the name
    and the value it is read by (a library's wrapper keeping it, #676)."""
    helpers: list[tuple[str, Callable[..., Any], FunctionType]] = []
    spaces = set[int]()
    while reads:
        name, value = reads.pop()
        if _constant(value):
            found[prefix + name] = value
        elif isinstance(value, ModuleType | type) and (gone := _unnamed(value)):
            lost.add((name, *gone))
        elif isinstance(value, ModuleType | type):  # `cfg.LIMIT`: a project namespace's
            if _project_space(value) and id(value) not in spaces:
                spaces.add(id(value))
                reads += [(f"{name}.{a}", getattr(value, a)) for a in sorted(attrs)
                          if hasattr(value, a)]  # fmt: skip
        elif _held(value):  # an array, a list, a dict, a DataFrame, an object holding one,
            impure.add(name)  # also when it keeps a function in `__wrapped__`
        elif helper := _helper(value):
            helpers.append((name, value, helper))
        elif not _found(value, name.rpartition(".")[2]):  # built while the program ran
            impure.add(name)
    return helpers


def _opens(names: set[str], values: dict[str, Any], attrs: set[str]) -> set[str]:
    """The names that open a file (`open`, `np.load`, `pd.read_csv`): a builtin not shadowed by
    a value of the function, or an attribute."""
    opened = {n for n in names if n not in values and n in _FILE_READS}
    return opened | {a for a in attrs if a in _FILE_READS or a.startswith("read_")}


def _helper(value: Callable[..., Any]) -> FunctionType | None:
    """The project function `value` is, or the first one it keeps along the standard
    `__wrapped__` chain (#572): `functools.lru_cache`, a `functools.wraps` decorator,
    `numba.njit`. A plain function of the project is taken as it is: a `wraps` decorator's inner
    function is hashed from its own code (#596), and the function it wraps is reached through its
    closure."""
    try:
        inner = inspect.unwrap(value, stop=_in_project)
    except ValueError:  # a `__wrapped__` cycle
        return None
    return inner if _in_project(inner) else None


def _found(value: object, read: str) -> bool:
    """A callable found again by reference, the test cloudpickle uses to pickle by reference
    (#589 Decisions 2): the module outside the project that `value` names as its `__module__`
    holds that very object under its qualified name, its name (`np.random.rand`, qualified
    `RandomState.rand`) or the name `read` it is read by (a library's instance with no name,
    Decisions 5); or it is a method bound to an object found so (`np.add.reduce`). A method that
    names no `__module__` (`str.upper`, `random.random`) is looked for in the module of its class.
    Any other callable, a project's included (#572 Decisions 2), cannot have what it holds in the
    hash; so is a chain of bound objects longer than a few steps (a lazy proxy)."""
    for _ in range(4):
        bound = getattr(value, "__self__", None)
        home = getattr(value, "__module__", None)
        if not isinstance(home, str):
            cls = getattr(value, "__objclass__", None) or (None if bound is None else type(bound))
            home = getattr(cls, "__module__", None)
        module = sys.modules.get(home) if isinstance(home, str) else None
        if module is not None and not _project_space(module):
            names = (getattr(value, "__qualname__", None), getattr(value, "__name__", None), read)
            if any(isinstance(n, str) and _lookup(module, n) is value for n in names):
                return True
        if isinstance(bound, ModuleType | None):
            return False
        value, read = bound, ""
    return False


def _lookup(module: ModuleType, dotted: str) -> object:
    """What `module` holds under the dotted name, or `None`."""
    found: object = module
    for part in dotted.split("."):
        found = getattr(found, part, None)
    return found


def _loads(code: CodeType) -> tuple[set[str], set[str]]:
    """The global names the code (and the code nested in it) loads, and the attribute names;
    `co_names` holds both together."""
    names, attrs = set[str](), set[str]()
    for op in dis.get_instructions(code):
        if op.opname in ("LOAD_GLOBAL", "LOAD_NAME"):
            names.add(op.argval)
        elif op.opname in ("LOAD_ATTR", "LOAD_METHOD"):
            attrs.add(op.argval)
    for const in code.co_consts:
        if isinstance(const, CodeType):
            inner = _loads(const)
            names |= inner[0]
            attrs |= inner[1]
    return names, attrs


def _unnamed(value: ModuleType | type) -> tuple[str, str] | None:
    """The class's qualified name (empty for a module) and its module's name when `sys.modules`
    cannot give it back by name (#690, decision 2026-11-26): a class whose `__module__` is not
    there, a module not held there as itself (`module_from_spec` with no entry). A class whose
    module is there but does not hold it (`__main__` under `runpy`, a class in a function) is
    judged by that module, as before. A library's, whose top package is loaded from outside the
    project, is left as before: a submodule it loads lazily (`numpy.rec`) or never registers
    (`sys.monitoring`) is the library's, not a file the user loaded."""
    cls = "" if isinstance(value, ModuleType) else value.__qualname__
    home = getattr(value, "__name__" if not cls else "__module__", None)
    if not isinstance(home, str):
        return None
    found = sys.modules.get(home) is value if not cls else home in sys.modules
    top = sys.modules.get(home.partition(".")[0])
    return None if found or (top is not None and not _project_space(top)) else (cls, home)


def _project_space(value: ModuleType | type) -> bool:
    """A module or a class defined in a file of the project."""
    module = value if isinstance(value, ModuleType) else sys.modules.get(value.__module__)
    file = getattr(module, "__file__", None)
    return file is not None and _project_file(file)


def _held(value: object) -> bool:
    """Data a function reads that the hash cannot hold: anything not callable, and a callable that
    carries data, an instance of a project class or a `functools.partial`, also when it keeps a
    function in `__wrapped__` (#246). The rule of `_found` makes a partial E24 too, but not one
    given a `__wrapped__` (`functools.update_wrapper`): `_helper` would follow that to the
    function and leave the partial's arguments out of the hash (#589 Decisions 3)."""
    carries = isinstance(value, functools.partial) or _project_space(type(value))
    return not callable(value) or carries


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
        fix="use .shift(k) with k ≥ 1 or nx.ops.rolling(...) on a return or a ratio; for a price"
        " level, a built-in factor such as Returns(...) or @nx.factor(window=...,"
        " inputs=[Price.close]), which read the column on today's basis",
        more="spec 3.3 shift and 6.5 check 1",
        layer=f"your code — {line}",
        at=line.split(" in ")[0],
        subject=f"shift({k})",
    )


def _user_line() -> str:
    """`file:line in function` of the first frame outside the engine (6.6 header)."""
    frame, engine = sys._getframe(1), Path(__file__).parents[1]
    while Path(frame.f_code.co_filename).is_relative_to(engine) and frame.f_back is not None:
        frame = frame.f_back
    name = frame.f_code.co_name
    where = f"{Path(frame.f_code.co_filename).name}:{frame.f_lineno}"
    return f"{where} in {name if name.isidentifier() else 'module'}"
