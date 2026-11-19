"""E17, your code: a user function declared degree 0 whose result changes when one
instrument's prices are scaled (3.3 `adjustment`), refused when it runs."""

# ruff: noqa: N999 - spec 8.4b names the file `<code>-<condition>.py`; it is run, not imported

from typing import Any

import numpy as np

import nexusbt as nx
from nexusbt.compute._executor import execute
from nexusbt.data._block import MarketBlock
from nexusbt.pipeline import Price


def level(close: Any) -> Any:
    return close[-1]


def case() -> None:
    dates = np.datetime64("2020-01-01") + np.arange(3).astype("timedelta64[D]")
    ready = (dates + np.timedelta64(16, "h")).astype("datetime64[us]")
    close = {"close": np.array([[100.0], [101.0], [102.0]])}
    block = MarketBlock("KR", dates, 0, ("KR:A",), close, np.ones((3, 1), bool),
                        np.zeros((3, 1), np.int8), ready[:, None])  # fmt: skip
    term = nx.factor(window=2, inputs=[Price.close], adjustment="degree 0")(level)
    execute([term], [2], [(0, 2)], lambda a, b: block, ready)
