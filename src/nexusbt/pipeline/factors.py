"""The built-in factors of 3.4 (`nexusbt.factors`); each comes with its ticket."""

from __future__ import annotations

from collections.abc import Sequence

from ._terms import BoundColumn, Factor, Filter, _node


def Returns(  # noqa: N802 - the 3.4 name
    window: int, inputs: Sequence[BoundColumn | Factor] | None = None, *, mask: Filter | None = None
) -> Factor:
    """3.4 `Returns(W, inputs=[Price.close_tr])`: the node only; its computation is T1.9's."""
    found = [BoundColumn.of("Price", "close_tr")] if inputs is None else inputs
    return _node(Factor, "Returns", *found, window=window, mask=mask)
