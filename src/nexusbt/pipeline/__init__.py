"""Term value objects, datasets, operators, built-in factors, Pipeline, hashes, static checks."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from . import factors as factors  # the 2.4 "`factors` module"


@dataclass(frozen=True, slots=True)
class Term: ...


@dataclass(frozen=True, slots=True)
class Factor: ...


@dataclass(frozen=True, slots=True)
class Filter: ...


@dataclass(frozen=True, slots=True)
class Classifier: ...


@dataclass(frozen=True, slots=True)
class BoundColumn: ...


@dataclass(frozen=True, slots=True)
class Pipeline: ...


@dataclass(frozen=True, slots=True)
class Finding: ...


# The datasets of 3.2: namespaces of columns, not values, so plain classes; the
# columns come with their tickets.
class Price: ...


class Fund: ...


class Meta: ...


class Panel: ...


class Label: ...


def factor(
    window: int,
    inputs: Sequence[BoundColumn | Factor],
    *,
    mask: Filter | None = None,
    dtype: Literal["float64"] = "float64",
) -> Callable[[Callable[..., Any]], Factor]:
    raise NotImplementedError


def filter(  # noqa: A001 - the 3.1 name `nx.filter`
    window: int, inputs: Sequence[BoundColumn | Factor], *, mask: Filter | None = None
) -> Callable[[Callable[..., Any]], Filter]:
    raise NotImplementedError


def classifier(
    window: int, inputs: Sequence[BoundColumn | Factor], *, mask: Filter | None = None
) -> Callable[[Callable[..., Any]], Classifier]:
    raise NotImplementedError


def graph_hash(term: Term) -> str:
    raise NotImplementedError


def static_check(graph: object, ctx: object) -> list[Finding]:
    raise NotImplementedError
