"""E8, your code: a user function reading a row before its window (3.3, 5.3.7), refused by the
dry run when the graph is checked (6.5 (5))."""

# ruff: noqa: N999 - spec 8.4b names the file `<code>-<condition>.py`; it is run, not imported

from typing import Any

import nexusbt as nx
from nexusbt.contracts import SchemaRegistry
from nexusbt.pipeline import Price, bind


def mom(close: Any) -> Any:
    return close[-22] / close[-273] - 1


def case() -> None:
    bind(nx.factor(window=253, inputs=[Price.close])(mom), SchemaRegistry(columns={}))
