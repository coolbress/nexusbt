"""Spec 3.8, the two keywords #82 settled: `evaluate`'s `save_signal` and what `snapshot=` takes."""

from __future__ import annotations

import inspect

import pytest

from nexusbt import api


def test_evaluate_has_save_signal_off_by_default() -> None:
    parameter = inspect.signature(api.evaluate).parameters["save_signal"]
    assert parameter.kind is parameter.KEYWORD_ONLY
    assert parameter.default is False


@pytest.mark.parametrize("name", ["live", "fill", "reconcile", "explain"])
def test_snapshot_takes_what_open_returns(name: str) -> None:
    # 3.8's `nx.open` line: its `Snapshot` "can be given to `snapshot=` of every function".
    parameter = inspect.signature(getattr(api, name)).parameters["snapshot"]
    assert parameter.annotation == "str | Snapshot | None"
    assert parameter.default is None
