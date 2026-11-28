"""T-25 (spec 8.2, 3.4) for the built-in factors: each kernel over the windows of its
`tests/golden/factors/<name>.yaml`, row by row, against the hand-calculated values. T1.9's seven
read their registered kernel; T1.10's four read the kernel with the case's parameters, and
`Latest` is `Price.close.latest` through the reference executor."""

from __future__ import annotations

import ast
import math
import re
from collections.abc import Callable
from pathlib import Path

import numpy as np
import numpy.typing as npt
import pytest
import yaml

from nexusbt import factors
from nexusbt.compute import _factors, _kernels
from nexusbt.compute._executor import execute
from nexusbt.compute._kernels_ref import REGISTERED
from nexusbt.data._block import MarketBlock
from nexusbt.pipeline import Factor, Price, graph_hash

pytestmark = pytest.mark.golden

FACTORS = Path(__file__).parent / "factors"
#: The registered kernel of each factor, and the extra rows it reads beyond W (3.4 warm-up).
KERNEL = {
    "Returns": ("Returns", 0),
    "DailyReturns": ("Returns", 0),
    "SimpleMovingAverage": ("SimpleMovingAverage", 0),
    "AverageDollarVolume": ("AverageDollarVolume", 0),
    "AverageTradedValue": ("AverageTradedValue", 0),
    "AnnualizedVolatility": ("AnnualizedVolatility", 1),
    "RollingStd": ("RollingStd", 0),
}
F64 = npt.NDArray[np.float64]
#: T1.10's kernels, given the case's term and its input windows in the YAML's order.
CALL: dict[str, Callable[[str, list[F64]], F64]] = {
    "ExponentialWeightedMovingAverage": lambda term, w: _kernels.window_ewma(
        w[0], _kernels.ewma_weights(len(w[0]), float(term.split("decay_rate=")[1].rstrip(")")))
    ),
    "VWAP": lambda _, w: _kernels.window_vwap(w[0], w[1]),
    "RSI": lambda _, w: _kernels.window_rsi(w[0]),
    "MaxDrawdown": lambda _, w: _kernels.window_max_drawdown(w[0]),
    "Latest": lambda _, w: _latest(w[0][:, 0]),
}


def _latest(close: F64) -> F64:
    """`Price.close.latest` at the window's last row, through the reference executor."""
    n = len(close)
    dates = np.datetime64("2020-01-01") + np.arange(n).astype("timedelta64[D]")
    ready = (dates + np.timedelta64(16, "h")).astype("datetime64[us]")
    block = MarketBlock("XX", dates, 0, ("A",), {"close": close[:, None]}, np.ones((n, 1), bool),
                        np.zeros((n, 1), np.int8), ready[:, None])  # fmt: skip
    term = Price.close.latest
    found = execute([term], [n - 1], [(0, n - 1)], lambda a, b: block, ready)
    return np.array(found[graph_hash(term)]["value"].to_pylist(), dtype=np.float64)


#: #868: the factors that take `min_periods`. Each case's own term is built and read through
#: the engine's built-in path (`compute._factors.value`), which applies it; a kernel alone does
#: not.
TAKES = {"AnnualizedVolatility", "AverageTradedValue", "MaxDrawdown", "RSI", "RollingStd",
         "SimpleMovingAverage", "VWAP"}  # fmt: skip


def _term(text: str) -> Factor:
    """The case's term, built by its 3.4 constructor from its literal arguments."""
    call = ast.parse(text, mode="eval").body
    assert isinstance(call, ast.Call)
    assert isinstance(call.func, ast.Name)
    args = [ast.literal_eval(a) for a in call.args]
    keywords = {str(k.arg): ast.literal_eval(k.value) for k in call.keywords}
    built: Factor = getattr(factors, call.func.id)(*args, **keywords)
    return built


def check(name: str) -> None:
    doc = yaml.safe_load((FACTORS / f"{name}.yaml").read_text())
    op, extra = KERNEL.get(name, (name, 0))
    for case in doc["cases"]:
        term = _term(case["term"]) if name in TAKES else None
        found = re.search(r"\((\d+)", case["term"])
        window = int(found.group(1)) if found else 1 if name == "Latest" else 2
        columns = [np.array(v, dtype=np.float64) for v in case["inputs"].values()]
        x = math.prod(columns, start=np.ones(len(columns[0])))  # close * volume for ADV
        rows = window + extra
        for t, expected in enumerate(case["expected"]):
            if expected is None:
                assert t < rows - 1, (case["term"], t)  # warm-up: no full window yet
                continue
            assert t >= rows - 1, (case["term"], t)  # a value only once the window is full
            windows = [c[t - rows + 1 : t + 1, None] for c in columns]
            if term is not None:
                value = _factors.value(term, windows)[0]
            elif name in CALL:
                value = CALL[name](case["term"], windows)[0]
            else:
                value = REGISTERED[op].kernel(x[t - rows + 1 : t + 1, None])[0]
            assert value == pytest.approx(expected, abs=5e-7, nan_ok=True), (case["term"], t)


def test_T25_Returns() -> None:  # noqa: N802 - spec 10.1's name
    check("Returns")


def test_T25_DailyReturns() -> None:  # noqa: N802 - spec 10.1's name
    check("DailyReturns")


def test_T25_SimpleMovingAverage() -> None:  # noqa: N802 - spec 10.1's name
    check("SimpleMovingAverage")


def test_T25_AverageDollarVolume() -> None:  # noqa: N802 - spec 10.1's name
    check("AverageDollarVolume")


def test_T25_AverageTradedValue() -> None:  # noqa: N802 - spec 10.1's name
    check("AverageTradedValue")


def test_T25_AnnualizedVolatility() -> None:  # noqa: N802 - spec 10.1's name
    check("AnnualizedVolatility")


def test_T25_RollingStd() -> None:  # noqa: N802 - spec 10.1's name
    check("RollingStd")


def test_T25_ExponentialWeightedMovingAverage() -> None:  # noqa: N802 - spec 10.1's name
    check("ExponentialWeightedMovingAverage")


def test_T25_VWAP() -> None:  # noqa: N802 - spec 10.1's name
    check("VWAP")


def test_T25_RSI() -> None:  # noqa: N802 - spec 10.1's name
    check("RSI")


def test_T25_MaxDrawdown() -> None:  # noqa: N802 - spec 10.1's name
    check("MaxDrawdown")


def test_T25_Latest() -> None:  # noqa: N802 - spec 10.1's name
    check("Latest")
