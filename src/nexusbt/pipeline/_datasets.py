"""The datasets of 3.2: namespaces whose attributes are column terms.

A fixed column (`Price`, `Meta`) is checked where it is written, E7 with similar names. A
snapshot's own names (`Item`, 5.3.5) come with the value tables' code; `Panel` and `Label` were
removed 2026-11-24 (#752). `bind` takes the `SchemaRegistry` `api` builds from the opened
snapshot, as `pipeline` reads no data (2.5).
"""

from __future__ import annotations

import difflib
from collections.abc import Collection, Iterator, Mapping
from types import MappingProxyType
from typing import Any, ClassVar

import numpy as np

from nexusbt.contracts import ColumnNameError, SchemaRegistry

from ._degree import check_degrees
from ._terms import BoundColumn, Classifier, Filter, Pipeline, Term, _node, _user_line, call_user

#: `instruments` columns known only after the fact (3.2, RV-C08, INV-01): never a `Meta` column.
_HINDSIGHT = ("delisted_on", "last_session", "name")


class _Dataset(type):
    """A dataset's class. `_fixed` are its columns, None when the snapshot names them; `_kinds`
    the term kind of a column that is not `_kind`; `_aliases` the v1 names kept (3.2)."""

    _fixed: ClassVar[tuple[str, ...] | None] = None
    _kind: ClassVar[type[Term]] = BoundColumn
    _kinds: ClassVar[Mapping[str, type[Term]]] = MappingProxyType({})
    _aliases: ClassVar[Mapping[str, str]] = MappingProxyType({})

    def __getattr__(cls, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        column = cls._aliases.get(name, name)
        if cls._fixed is not None and column not in cls._fixed:
            raise _no_column(cls.__name__, name, (*cls._fixed, *cls._aliases))
        kind = cls._kinds.get(column, cls._kind)
        return _node(kind, "column", dataset=cls.__name__, column=column)

    def __setattr__(cls, name: str, value: object) -> None:
        raise AttributeError(f"{cls.__name__} is a dataset: its columns are not assigned")

    def __dir__(cls) -> list[str]:
        return [*(cls._fixed or ()), *cls._aliases]


class Price(metaclass=_Dataset):
    _fixed = ("open", "high", "low", "close", "close_tr", "close_unadjusted", "volume",
              "volume_unadjusted", "value_traded", "shares_out", "market_cap")  # fmt: skip


class Meta(metaclass=_Dataset):
    """`Meta.<scheme>(level=)` and the scheme `sector` and `industry` read come with T2.3."""

    _fixed = ("market", "currency", "asset_class", "venue_mic", "category", "sector", "industry",
              "is_financial")  # fmt: skip
    _kind = Classifier
    _kinds = MappingProxyType({"is_financial": Filter})
    _aliases = MappingProxyType({"country": "market", "exchange": "venue_mic"})


def bind(graph: Term | Pipeline, registry: SchemaRegistry) -> None:
    """2.5: check the graph before any data is read. A term of known non-zero degree fed to
    `shift` or a window is E17 (3.3, 3.4); a user function is called once on `(W, 3)` windows
    of 1.0, so a row before its window or a result of another shape is E8 (6.5 (5)). No column
    of the graph is the snapshot's own until `Item` (5.3.5): `registry` is not read yet."""
    __tracebackhide__ = True  # down to a user function (R-42)
    check_degrees(_roots(graph))
    for term in _terms(graph):
        params = dict(term.params)
        if term.op == "user":
            call_user(term, [np.ones((params["window"], 3))] * len(term.inputs), 3)


_STUB = """\
# Written by `nexusbt stubs` from the snapshot's dictionary (spec 3.2); not edited by hand.
from nexusbt.pipeline._terms import BoundColumn, Classifier, Filter
"""


def stub_source(registry: SchemaRegistry | None = None) -> str:
    """`_stubs/datasets.pyi`: the fixed columns and aliases, for the editor and the type
    checker (3.2). No class holds a snapshot's own columns until `Item` (5.3.5), so a registry
    adds nothing yet."""
    text = _STUB
    for cls in (Price, Meta):
        columns = [*(cls._fixed or ()), *cls._aliases]
        kinds = {c: cls._kinds.get(cls._aliases.get(c, c), cls._kind).__name__ for c in columns}
        body = [f"    {c}: {k}" for c, k in kinds.items()]
        text += "\n" + "\n".join([f"class {cls.__name__}:", *body]) + "\n"
    return text


def _terms(graph: Term | Pipeline) -> Iterator[Term]:
    """Every node once; a loop, as a long chain of operators is deeper than the call stack."""
    todo = _roots(graph)
    seen: set[str] = set()
    while todo:
        term = todo.pop()
        if term._key not in seen:
            seen.add(term._key)
            yield term
            todo += [*term.inputs, *(v for _, v in term.params if isinstance(v, Term))]


def _roots(graph: Term | Pipeline) -> list[Term]:
    if isinstance(graph, Term):
        return [graph]
    return [*graph.columns.values(), *([] if graph.screen is None else [graph.screen])]


def _no_column(dataset: str, name: str, names: Collection[str]) -> ColumnNameError:
    close = difflib.get_close_matches(name, names, n=3, cutoff=0.6)
    line = _user_line()
    why = "the column is not in this snapshot's dictionary"
    if dataset in ("Price", "Meta"):
        why = f"{dataset}'s columns are fixed (spec 3.2)"
    if dataset == "Meta" and name in _HINDSIGHT:
        why = f"instruments.{name} is known only after the fact, so Meta does not expose it"
    return ColumnNameError(
        what=f"{dataset} has no column '{name}'."
        + (f" Did you mean: {', '.join(close)}?" if close else ""),
        where=f"dataset {dataset}", why=why,
        fix=f"use one of: {', '.join(names)}" if names else "nexusbt doctor lists the datasets",
        more="spec 3.2 (dataset columns)", layer=f"your code — {line}",
        at=line.split(" in ")[0], subject=f"{dataset}.{name}",
    )  # fmt: skip
