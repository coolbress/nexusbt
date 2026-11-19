"""The zipline shim (spec 3.4, 10.1 T1.16; #251): zipline's `CustomFactor` code runs with only
its import changed to `nexusbt.compat.zipline`."""

from __future__ import annotations

import warnings
from collections.abc import Sequence
from typing import Any

import numpy as np
import pytest

from nexusbt.compat.zipline import CustomFactor, USEquityPricing
from nexusbt.compute._executor import execute
from nexusbt.data._block import MarketBlock
from nexusbt.pipeline import BoundColumn, Term, graph_hash
from nexusbt.pipeline._terms import l1_disabled


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

    passed = "nexusbt.compat.zipline does not pass today and assets to compute"
    with pytest.raises(TypeError, match=passed):
        run([Count()], 5, 6)
    with pytest.raises(TypeError, match=passed):
        run([Year()], 5, 6)


def test_a_class_without_compute_stops_naming_it() -> None:
    """#251: a class that defines no compute stops when it is called, naming the class."""

    class NoCompute(CustomFactor):
        inputs = (USEquityPricing.close,)
        window_length = 2

    with pytest.raises(TypeError, match="NoCompute defines no compute"):
        NoCompute()


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


def test_a_class_constant_compute_reads_is_in_the_hash() -> None:
    """Two classes of one name and one compute that differ only in a constant compute reads
    through `self` make two terms (review of #251)."""

    def compute(self: Any, today: Any, assets: Any, out: Any, *inputs: Any) -> None:
        out[:] = inputs[0][-self.skip] / inputs[0][0] - 1

    body = {"inputs": (USEquityPricing.close,), "window_length": 253, "compute": compute}
    a = type("Skip", (CustomFactor,), {**body, "skip": 21})
    b = type("Skip", (CustomFactor,), {**body, "skip": 5})
    assert graph_hash(a()) != graph_hash(b())


def _two(self: Any) -> float:
    return 2.0


def _five(self: Any) -> float:
    return 5.0


def test_a_method_compute_calls_is_in_the_hash() -> None:
    """The source of a method compute may call through `self` is in the hash too."""

    def compute(self: Any, today: Any, assets: Any, out: Any, *inputs: Any) -> None:
        out[:] = self.scale()

    body = {"inputs": (USEquityPricing.close,), "window_length": 2, "compute": compute}
    a = type("Scaled", (CustomFactor,), {**body, "scale": _two})
    b = type("Scaled", (CustomFactor,), {**body, "scale": _five})
    assert graph_hash(a()) != graph_hash(b())


@pytest.mark.parametrize("weights", [[2.0], np.array([2.0])], ids=["list", "array"])
def test_data_compute_reads_through_self_warns_e24(weights: Any) -> None:
    """6.5 (6), as for a function reading a non-constant global (#561): a class attribute the
    hash cannot hold is E24, and the L1 cache is off for the term."""

    def compute(self: Any, today: Any, assets: Any, out: Any, *inputs: Any) -> None:
        out[:] = self.weights[0]

    body = {"inputs": (USEquityPricing.close,), "window_length": 2, "compute": compute}
    cls = type("Weighted", (CustomFactor,), {**body, "weights": weights})
    with pytest.warns(UserWarning, match=r"\[E24\]") as caught:
        term = cls()
    [text] = [str(w.message) for w in caught]
    assert "Weighted reads global 'weights'" in text
    assert l1_disabled(term)


def test_constant_class_attributes_raise_no_warning() -> None:
    """zipline's own attributes and constants are hashed, not warned; inputs and mask are
    the term's own."""
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert not l1_disabled(Mom())


def test_usequitypricing_close_is_close_tr() -> None:
    """3.4, A-39: zipline's close carries the adjustment DB (splits and dividends), so the
    shim's close is the total-return close, not the split-only `Price.close`."""
    assert graph_hash(USEquityPricing.close) == graph_hash(BoundColumn.of("Price", "close_tr"))
    assert graph_hash(USEquityPricing.close) != graph_hash(BoundColumn.of("Price", "close"))
