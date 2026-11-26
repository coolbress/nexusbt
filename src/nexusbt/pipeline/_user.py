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

from ._terms import BoundColumn, Factor, Filter, _impure, _one_of, _readable, _reads


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
