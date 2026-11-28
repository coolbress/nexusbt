"""Spec 5.1.3: the DecisionContext a strategy's decision is taken on (T3.2a, #909)."""

from __future__ import annotations

import dataclasses
import datetime as dt
from typing import Any

import pytest

import nexusbt as nx
from nexusbt import contracts

pytestmark = pytest.mark.unit


def test_decision_context_anchor_field() -> None:
    """5.1.3, INV-08: the DecisionContext has the spec's fields in its order, the anchor of
    the target-state recursion last and always said (None when the recursion is not used);
    two contexts that differ in the anchor alone are not the same value."""
    assert nx.DecisionContext is contracts.DecisionContext
    assert [f.name for f in dataclasses.fields(nx.DecisionContext)] == [
        "decision_id", "snapshot_id", "snapshot_semantic_hash", "sleeve_id", "calendar_id",
        "session_date", "decision_ts", "clock", "availability_policy", "scheduled",
        "anchor_decision_id",
    ]  # fmt: skip
    day, clock = dt.date(2019, 6, 28), "KR_close"
    said: dict[str, Any] = {"decision_id": f"KR:{day:%Y%m%d}:{clock}", "snapshot_id": "synth-0001",
            "snapshot_semantic_hash": "0" * 64, "sleeve_id": "KR", "calendar_id": "XKRX",
            "session_date": day, "decision_ts": dt.datetime(2019, 6, 28, 6, 30, tzinfo=dt.UTC),
            "clock": clock, "availability_policy": "ts_end", "scheduled": True}  # fmt: skip
    free = nx.DecisionContext(**said, anchor_decision_id=None)
    anchored = dataclasses.replace(free, anchor_decision_id="KR:20190131:KR_close")
    assert free.anchor_decision_id is None
    assert anchored != free
    assert dataclasses.replace(anchored, anchor_decision_id=None) == free
    with pytest.raises(TypeError, match="anchor_decision_id"):
        nx.DecisionContext(**said)
