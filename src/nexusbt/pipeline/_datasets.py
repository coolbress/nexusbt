"""The datasets of 3.2: namespaces whose attributes are column terms.

A fixed column (`Price`, `Meta`) is checked where it is written. A snapshot's columns (`Panel`,
`Label`) are not known there, as `pipeline` reads no data (2.5): `bind` checks them against the
`SchemaRegistry` that `api` builds from the opened snapshot. Both raise E7 with similar names.
"""

from __future__ import annotations

import difflib
from collections.abc import Collection, Iterator, Mapping
from keyword import iskeyword
from types import MappingProxyType
from typing import Any, ClassVar

from nexusbt.contracts import ENGINE_COLUMNS, ColumnNameError, LabelLeakError, SchemaRegistry

from ._terms import BoundColumn, Classifier, Filter, Pipeline, Term, _node, _user_line

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


class Panel(metaclass=_Dataset): ...


class Label(metaclass=_Dataset): ...


def bind(graph: Term | Pipeline, registry: SchemaRegistry) -> None:
    """2.5: check the graph's `Panel` and `Label` columns against the snapshot's registry (E7).

    A label read through `Panel` is E2 (8.4)."""
    names, leaks = _snapshot_columns(registry)
    for term in _terms(graph):
        params = dict(term.params)
        known = names.get(params["dataset"]) if term.op == "column" else None
        if known is not None and params["column"] not in known:
            if params["dataset"] == "Panel" and params["column"] in leaks:
                raise _label_leak(params["column"])
            raise _no_column(params["dataset"], params["column"], known)


_STUB = """\
# Written by `nexusbt stubs` from the snapshot's dictionary (spec 3.2); not edited by hand.
from nexusbt.pipeline._terms import BoundColumn, Classifier, Filter

class _Snapshot(type):  # another snapshot holds other columns: any name is one
    def __getattr__(cls, name: str) -> BoundColumn: ...
"""


def stub_source(registry: SchemaRegistry | None = None) -> str:
    """`_stubs/datasets.pyi`: the fixed columns and aliases, and the snapshot's `Panel` and
    `Label` columns when a registry names them, for the editor and the type checker (3.2)."""
    names = _snapshot_columns(registry)[0] if registry else {}
    text = _STUB
    for cls in (Price, Meta, Panel, Label):
        columns = names.get(cls.__name__, [*(cls._fixed or ()), *cls._aliases])
        kinds = {c: cls._kinds.get(cls._aliases.get(c, c), cls._kind).__name__ for c in columns}
        body = [f"    {c}: {k}" for c, k in kinds.items() if _writable(c)]
        head = f"class {cls.__name__}" + ("" if cls._fixed else "(metaclass=_Snapshot)")
        # the formatter's shape: no blank line between two classes without a body
        gap = "\n" if body or not text.endswith("): ...\n") else ""
        text += gap + "\n".join([f"{head}:" if body else f"{head}: ...", *body]) + "\n"
    return text


def _writable(name: str) -> bool:
    """A column the stub can list: a name Python reads after a dot, that the dataset gives
    (not `_x`) and that does not hide a type the stub names."""
    hides = name in ("BoundColumn", "Classifier", "Filter")
    return name.isidentifier() and not (iskeyword(name) or name.startswith("_") or hides)


def _snapshot_columns(registry: SchemaRegistry) -> tuple[dict[str, list[str]], frozenset[str]]:
    """`Panel`'s and `Label`'s columns in the registry, and the names that are labels.

    `Panel` holds the feature columns of the dataset `registry.feature`, `Label` the columns of
    `registry.label` that `dictionary/columns` marks `is_label`. A label is in `Label` only: a
    name marked in either dataset is not a `Panel` column."""
    features = registry.columns.get(registry.feature, ())
    labels = registry.columns.get(registry.label, ())
    marked = registry.labels.get(registry.label, frozenset())
    leaks = marked | registry.labels.get(registry.feature, frozenset())
    hidden = ENGINE_COLUMNS["feature_panels"] | leaks
    names = {
        "Panel": [name for name, _ in features if name not in hidden],
        "Label": [name for name, _ in labels if name in marked],
    }
    return names, leaks


def _terms(graph: Term | Pipeline) -> Iterator[Term]:
    """Every node once; a loop, as a long chain of operators is deeper than the call stack."""
    todo = [graph] if isinstance(graph, Term) else [*graph.columns.values()]
    if isinstance(graph, Pipeline) and graph.screen is not None:
        todo.append(graph.screen)
    seen: set[str] = set()
    while todo:
        term = todo.pop()
        if term._key not in seen:
            seen.add(term._key)
            yield term
            todo += [*term.inputs, *(v for _, v in term.params if isinstance(v, Term))]


def _label_leak(name: str) -> LabelLeakError:
    line = _user_line()
    return LabelLeakError(
        what=f"Panel.{name} is a label (forward-looking)", where="dataset Panel",
        why="a label is known only after the decision, so it is a column of Label only",
        fix=f"test it with nx.evaluate(f, target=Label.{name})",
        more="spec 3.2 (Label) and 6.5 check 2", layer=f"your code — {line}",
        at=line.split(" in ")[0], subject=f"Panel.{name}",
    )  # fmt: skip


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
