"""T-25 (spec 8.2, 3.4) for T1.9's seven factors: each registered kernel over the windows of its
`tests/golden/factors/<name>.yaml`, row by row, against the hand-calculated values."""

from __future__ import annotations

import math
import re
from pathlib import Path

import numpy as np
import pytest
import yaml

from nexusbt.compute._kernels_ref import REGISTERED

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


def check(name: str) -> None:
    doc = yaml.safe_load((FACTORS / f"{name}.yaml").read_text())
    op, extra = KERNEL[name]
    for case in doc["cases"]:
        window = int(m.group(1)) if (m := re.search(r"\((\d+)", case["term"])) else 2
        columns = [np.array(v, dtype=np.float64) for v in case["inputs"].values()]
        x = math.prod(columns, start=np.ones(len(columns[0])))  # close * volume for ADV
        rows = window + extra
        for t, expected in enumerate(case["expected"]):
            if expected is None:
                assert t < rows - 1, (case["term"], t)  # warm-up: no full window yet
                continue
            assert t >= rows - 1, (case["term"], t)  # a value only once the window is full
            found = REGISTERED[op].kernel(x[t - rows + 1 : t + 1, None])[0]
            assert found == pytest.approx(expected, abs=5e-7, nan_ok=True), (case["term"], t)


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
