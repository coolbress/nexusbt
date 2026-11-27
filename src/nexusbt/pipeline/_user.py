"""The decorators that make a user term from a window function (3.3): `@nx.factor` here, and
`@nx.filter` and `@nx.classifier` next to it (#620). What a user function reads, for its hash
and E24, is in `_terms`; running it on its windows is in `_run`."""

from __future__ import annotations

import hashlib
import warnings
from collections.abc import Callable, Sequence
from types import FunctionType
from typing import Any, Literal

from nexusbt.contracts import ConfigError

from ._terms import BoundColumn, Classifier, Factor, Filter, _impure, _one_of, _readable, _reads


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
    _one_of("@nx.factor", "dtype", dtype, ("float64",))  # a Factor's values are float64 (#638)
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


def user_filter(
    window: int, inputs: Sequence[BoundColumn | Factor], *, mask: Filter | None = None
) -> Callable[[Callable[..., Any]], Filter]:
    """3.3 `@nx.filter`: a Filter from a window function returning bool `(n_alive,)`; its node,
    hash and checks are `@nx.factor`'s, less `dtype` and `adjustment` (#620)."""

    def wrap(fn: Callable[..., Any]) -> Filter:
        if not isinstance(fn, FunctionType):
            raise TypeError(f"@nx.filter decorates a function, not {type(fn).__name__}")
        reads = _reads(fn)
        source = "".join(f"\n{h.__qualname__}\n{_readable(h, 'filter')}" for h in reads.helpers)
        digest = hashlib.sha256((_readable(fn, "filter") + source).encode()).hexdigest()
        params = {"window": window, "mask": mask, "function": fn.__name__, "source": digest,
                  "captured": reads.captured}  # fmt: skip
        if reads.e24:
            warning = _impure(fn.__name__, reads.impure, reads.decorator, reads.under, reads.lost,
                              "filter")  # fmt: skip
            warnings.warn(str(warning), stacklevel=2)
        return Filter("user", tuple(inputs), tuple(params.items()), function=fn)

    return wrap


def user_classifier(
    window: int, inputs: Sequence[BoundColumn | Factor], *, mask: Filter | None = None
) -> Callable[[Callable[..., Any]], Classifier]:
    """3.3 `@nx.classifier`: a Classifier from a window function returning integer codes
    `(n_alive,)`, -1 the missing group; its node, hash and checks are `@nx.filter`'s (#620)."""

    def wrap(fn: Callable[..., Any]) -> Classifier:
        if not isinstance(fn, FunctionType):
            raise TypeError(f"@nx.classifier decorates a function, not {type(fn).__name__}")
        reads = _reads(fn)
        made = "classifier"
        source = "".join(f"\n{h.__qualname__}\n{_readable(h, made)}" for h in reads.helpers)
        digest = hashlib.sha256((_readable(fn, made) + source).encode()).hexdigest()
        params = {"window": window, "mask": mask, "function": fn.__name__, "source": digest,
                  "captured": reads.captured}  # fmt: skip
        if reads.e24:
            warning = _impure(fn.__name__, reads.impure, reads.decorator, reads.under, reads.lost,
                              made)  # fmt: skip
            warnings.warn(str(warning), stacklevel=2)
        return Classifier("user", tuple(inputs), tuple(params.items()), function=fn)

    return wrap
