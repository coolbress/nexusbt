"""Spec 3.3, 6.6 E16 (#602): an argument of 3.3's Factor tables that takes one of a closed set
of values is refused when the term is built, with the argument, the value and what it allows."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

import numpy as np
import pytest

from nexusbt.contracts import ConfigError
from nexusbt.factors import SMA
from nexusbt.pipeline import Term, graph_hash

RANK_METHODS = ("ordinal", "average", "min", "max", "dense")  # spec 3.3, `rank`'s row


def test_rank_method_bogus_is_refused_at_build() -> None:
    with pytest.raises(ConfigError) as caught:
        SMA(3).rank(method="bogus")
    error = caught.value
    assert error.code == "E16"
    assert "method='bogus'" in error.parts["what"]
    assert all(f"'{name}'" in error.parts["fix"] for name in RANK_METHODS), error.parts["fix"]


def refused(build: Callable[[], object], argument: str, allowed: Sequence[str]) -> None:
    """E16 at build, naming the argument and the value (what) and every allowed value (fix)."""
    with pytest.raises(ConfigError) as caught:
        build()
    error = caught.value
    assert error.code == "E16"
    assert f"{argument}=" in error.parts["what"], error.parts["what"]
    assert error.parts["fix"].startswith(f"{argument}="), error.parts["fix"]
    assert all(word in error.parts["fix"] for word in allowed), error.parts["fix"]


@pytest.mark.parametrize("na", ["zero", "DROP", None])
def test_pct_rank_na_outside_its_three_is_refused_at_build(na: Any) -> None:
    refused(lambda: SMA(3).pct_rank(na=na), "na", ["'drop'", "'bottom'", "'middle'"])


#: Not `True` or `False`: `1` and `0` hash apart from them (`_canon` keeps the type), so taking
#: them would give one computation two graph hashes; numpy's are not term parameters at all.
NOT_BOOLS = ["False", 1, 0, np.True_, np.False_, None]
X = SMA(3)
CROSS_SECTION: list[Callable[..., object]] = [
    X.rank, X.zscore, X.demean, lambda **k: X.winsorize(0.1, 0.9, **k), lambda **k: X.top(3, **k),
    lambda **k: X.bottom(3, **k), lambda **k: X.percentile_between(10, 90, **k), X.pct_rank,
    lambda **k: X.quantiles(4, **k), X.quartiles, X.quintiles, X.deciles,
]  # fmt: skip


@pytest.mark.parametrize("value", NOT_BOOLS, ids=repr)
def test_rank_ascending_not_a_bool_is_refused_at_build(value: Any) -> None:
    """Before #602, `ascending="False"` built and ranked ascending, as the string is truthy."""
    refused(lambda: X.rank(ascending=value), "ascending", ["True", "False"])


@pytest.mark.parametrize("value", NOT_BOOLS, ids=repr)
def test_pct_rank_higher_is_better_not_a_bool_is_refused_at_build(value: Any) -> None:
    refused(lambda: X.pct_rank(higher_is_better=value), "higher_is_better", ["True", "False"])


@pytest.mark.parametrize("value", NOT_BOOLS, ids=repr)
@pytest.mark.parametrize("method", CROSS_SECTION)
def test_across_markets_not_a_bool_is_refused_at_build(method: Any, value: Any) -> None:
    refused(lambda: method(across_markets=value), "across_markets", ["True", "False"])


@pytest.mark.parametrize("bins", [0, -1, 2.5, 4.0, True, np.int64(4), "4", None], ids=repr)
def test_quantiles_bins_not_a_whole_number_of_one_or_more_is_refused_at_build(bins: Any) -> None:
    """#602 "Not sure yet", decided with the owner: E16 at build, not the kernel's ValueError
    at run (which stays, as the kernel's own guard)."""
    refused(lambda: X.quantiles(bins), "bins", ["whole number", "1 or more"])


#: Graph hashes on main at 0349edd, before #602: the checks refuse, they do not rewrite a value.
PINNED: dict[str, tuple[Callable[[], Term], str]] = {
    "rank": (X.rank, "3c9ca76329f9686a3ef557431cefd5bc2b521ba9f2699cdbbead430fcb90382b"),
    "rank_dense_descending": (
        lambda: X.rank("dense", False),
        "b4eb33f0c6e54561978b0ad65b2de38c11bb33f2ad3846bcaddfbd1384526780",
    ),
    "pct_rank_middle": (
        lambda: X.pct_rank(False, na="middle"),
        "9ac74e34d1727e6624034b028ccf51d3c1cb8f663eda08bd1ff30207996d79a9",
    ),
    "quantiles_4": (
        lambda: X.quantiles(4),
        "621a832480388f1e918b90d4a45aafdd148fb0e1273c77e5b9691c12d05d59a7",
    ),
    "zscore_across_markets": (
        lambda: X.zscore(across_markets=True),
        "0ffe6394e7f0076ec0b7b07af0fc5dc925b8446dc337b3a1a170370d21c84338",
    ),
}


@pytest.mark.parametrize("name", PINNED)
def test_allowed_values_build_with_their_graph_hash_unchanged(name: str) -> None:
    build, pinned = PINNED[name]
    assert graph_hash(build()) == pinned
