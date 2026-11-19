"""The zipline shim (spec 3.4, 10.1 T1.16; #251): zipline's `CustomFactor` code runs with only
its import changed to `nexusbt.compat.zipline`."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np
import pytest

from nexusbt.compat.zipline import CustomFactor, USEquityPricing
from nexusbt.compute._executor import execute
from nexusbt.data._block import MarketBlock
from nexusbt.pipeline import BoundColumn, Term, graph_hash


class Mom(CustomFactor):
    """zipline's 12-1 momentum as zipline code writes it; only the import above is changed."""

    inputs = [USEquityPricing.close]  # noqa: RUF012 - zipline's spelling
    window_length = 253

    def compute(self, today, assets, out, close):  # type: ignore[no-untyped-def]
        out[:] = close[-21] / close[0] - 1


def run(terms: Sequence[Term], row: int, n: int) -> dict[str, list[float]]:
    """Each term's values at `row` over `n` sessions of two instruments whose total-return closes
    are 100 + row and 1000 + row."""
    dates = np.datetime64("2020-01-01") + np.arange(n).astype("timedelta64[D]")
    ready = (dates + np.timedelta64(16, "h")).astype("datetime64[us]")
    close = np.arange(n)[:, None] + np.array([[100.0, 1000.0]])
    block = MarketBlock("KR", dates, 0, ("KR:T00001", "KR:T00002"), {"close_tr": close},
                        np.ones((n, 2), bool), np.zeros((n, 2), np.int8),
                        np.repeat(ready[:, None], 2, axis=1))  # fmt: skip
    found = execute(terms, [row], [(0, n - 1)], lambda a, b: block, ready)
    return {key: [v["value"] for v in table.to_pylist()] for key, table in found.items()}


def test_compute_signature() -> None:
    """10.1 T1.16: zipline's `compute(self, today, assets, out, *inputs)` runs on the 253-row
    window, its last row the computation day, and what it writes into `out` is the value. At
    row 260 the window is rows 8..260: close[0] is row 8, close[-21] row 240."""
    mom = Mom()
    [values] = run([mom], 260, 261).values()
    assert values == pytest.approx([232 / 108, 232 / 1008], rel=1e-12)


def test_today_or_assets_read_stops_with_an_error() -> None:
    """#251: `today` and `assets` are None, so a compute that reads them stops with an error,
    never a quiet wrong value."""

    class Count(CustomFactor):
        inputs = (USEquityPricing.close,)
        window_length = 2

        def compute(self, today: Any, assets: Any, out: Any, *inputs: Any) -> None:
            out[:] = len(assets)

    class Year(CustomFactor):
        inputs = (USEquityPricing.close,)
        window_length = 2

        def compute(self, today: Any, assets: Any, out: Any, *inputs: Any) -> None:
            out[:] = today.year

    with pytest.raises(TypeError, match="object of type 'NoneType' has no len"):
        run([Count()], 5, 6)
    with pytest.raises(AttributeError, match="'NoneType' object has no attribute 'year'"):
        run([Year()], 5, 6)


def test_window_safe_is_taken_and_means_nothing() -> None:
    """#251 Decisions 2026-11-19: `window_safe` is taken, gives no meaning; the term is the one
    the same class without it makes."""

    class Safe(Mom):
        window_safe = True

    assert list(run([Safe()], 260, 261).values()) == list(run([Mom()], 260, 261).values())


@pytest.mark.parametrize(
    ("name", "value"),
    [("outputs", ("a", "b")), ("params", ("n",)), ("domain", object()),
     ("dtype", np.int64), ("missing_value", 0.0), ("ndim", 1)],
)  # fmt: skip
def test_an_attribute_that_would_change_the_result_stops_the_class(name: str, value: Any) -> None:
    """#251: an attribute the shim does not carry out, and whose silent loss would change the
    result, stops the class where it is defined."""
    with pytest.raises(TypeError, match=name):
        type("Bad", (Mom,), {name: value})


def test_domain_error_says_how_to_choose_markets() -> None:
    """#251 Decisions 2026-11-19: the markets are run_pipeline's."""
    with pytest.raises(TypeError, match=r"run_pipeline\(markets=\.\.\.\).*remove the domain"):
        type("Bad", (Mom,), {"domain": object()})


def test_default_values_are_taken() -> None:
    """zipline's defaults (float64, NaN, two dimensions) change nothing and are taken."""
    type("Fine", (Mom,), {"dtype": np.float64, "missing_value": np.nan, "ndim": 2})


def test_two_classes_make_two_terms() -> None:
    """Each class's compute is in its term's hash, so two classes never share one."""

    class Other(CustomFactor):
        inputs = (USEquityPricing.close,)
        window_length = 253

        def compute(self, today: Any, assets: Any, out: Any, *inputs: Any) -> None:
            out[:] = inputs[0][-1] / inputs[0][0] - 1

    assert graph_hash(Other()) != graph_hash(Mom())
    assert graph_hash(Mom()) == graph_hash(Mom())


def test_usequitypricing_close_is_close_tr() -> None:
    """3.4, A-39: zipline's close carries the adjustment DB (splits and dividends), so the
    shim's close is the total-return close, not the split-only `Price.close`."""
    assert graph_hash(USEquityPricing.close) == graph_hash(BoundColumn.of("Price", "close_tr"))
    assert graph_hash(USEquityPricing.close) != graph_hash(BoundColumn.of("Price", "close"))
