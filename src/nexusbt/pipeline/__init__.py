"""Term value objects, datasets, operators, built-in factors, Pipeline, hashes, static checks."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from ._datasets import Meta as Meta
from ._datasets import Price as Price
from ._datasets import bind as bind
from ._datasets import stub_source as stub_source
from ._terms import BoundColumn as BoundColumn
from ._terms import Classifier as Classifier
from ._terms import Factor as Factor
from ._terms import Filter as Filter
from ._terms import Pipeline as Pipeline
from ._terms import Term as Term
from ._terms import describe_term as describe_term
from ._terms import graph_hash as graph_hash
from ._user import factor as factor

from . import factors as factors  # the 2.4 "`factors` module"  # isort: skip


@dataclass(frozen=True, slots=True)
class Finding: ...


def filter(  # noqa: A001 - the 3.1 name `nx.filter`
    window: int, inputs: Sequence[BoundColumn | Factor], *, mask: Filter | None = None
) -> Callable[[Callable[..., Any]], Filter]:
    raise NotImplementedError


def classifier(
    window: int, inputs: Sequence[BoundColumn | Factor], *, mask: Filter | None = None
) -> Callable[[Callable[..., Any]], Classifier]:
    raise NotImplementedError


def static_check(graph: object, ctx: object) -> list[Finding]:
    raise NotImplementedError
