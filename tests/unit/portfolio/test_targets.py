"""Spec 3.7, 5.5.1: `nx.top(n)` on one factor at equal weights, one stage (T3.1a, #908)."""

from __future__ import annotations

import datetime as dt
from typing import Any

import numpy as np
import pyarrow as pa
import pytest

import nexusbt as nx
from nexusbt.compute._executor import execute
from nexusbt.contracts import DecisionGrid, FactorFrame, TiebreakPolicy
from nexusbt.data._block import MarketBlock
from nexusbt.pipeline import BoundColumn, graph_hash
from nexusbt.portfolio import build_targets

pytestmark = pytest.mark.unit
NAN = float("nan")
DAY = dt.date(2019, 6, 28)
AT = dt.datetime(2019, 6, 28, 6, 30, tzinfo=dt.UTC)
GRID = DecisionGrid("KR", "XKRX", "KR_close", DAY, DAY, (DAY,), (AT,))
T27 = dict.fromkeys(("KR:T00001", "KR:T00002", "KR:T00003"), 1.0)  # hash order 2, 1, 3


def frame(scores: dict[str, float], days: int = 1, **more: list[Any]) -> FactorFrame:
    """`scores` at `days` decisions of KR, a day apart; `more` adds a column, a cell per name."""
    rows = [{"market": "KR", "session_date": DAY + dt.timedelta(d),
             "decision_ts": AT + dt.timedelta(d), "instrument_id": i, "score": s}
            | {name: cells[at] for name, cells in more.items()}
            for d in range(days) for at, (i, s) in enumerate(scores.items())]  # fmt: skip
    return FactorFrame(pa.Table.from_pylist(rows))


def picked(found: FactorFrame, n: int, tiebreak: Any = None) -> list[tuple[Any, ...]]:
    """(session, id, rank, weight) of each target row, in the frame's order."""
    table = build_targets(found, nx.top(n, tiebreak=tiebreak), GRID)[0].table
    names = ("session_date", "instrument_id", "selected_rank", "target_weight")
    return list(zip(*(table[name].to_pylist() for name in names), strict=True))


def test_top_n_equal_weights() -> None:
    """3.7: the n highest scores, 1/n each; 5.5.1's columns for a long-only target with no
    risk rule; a cell whose universe is false or unknown is not taken."""
    scores = {"A": 3.0, "B": 9.0, "C": 1.0, "D": 5.0, "E": 7.0}
    assert picked(frame(scores), 2) == [(DAY, "B", 1, 0.5), (DAY, "E", 2, 0.5)]
    row = build_targets(frame(scores), nx.top(2), GRID)[0].table.to_pylist()[0]
    assert row == {
        "decision_id": "KR:20190628:KR_close", "sleeve_id": "KR", "decision_ts": AT,
        "session_date": DAY, "instrument_id": "B", "score": 9.0, "selected_rank": 1,
        "stage": "risk", "pre_risk_weight": 0.5, "target_weight": 0.5, "decided_weight": None,
        "final_weight": 0.5, "side": "long", "reason": "selected",
    }  # fmt: skip
    universe = frame(scores, universe=[True, False, True, True, None])
    assert [r[1] for r in picked(universe, 2)] == ["D", "A"]
    assert picked(frame(scores), 0) == []
    with pytest.raises(NotImplementedError, match="max_weight"):
        nx.top(2, max_weight=0.1)
    with pytest.raises(ValueError, match="at least zero"):
        picked(frame(scores), -1)


def test_fewer_finite_scores_than_n_weigh_one_over_k() -> None:
    """3.7 `w_i = u_i / Σu` over the k taken (#875): 5 names with 2 NaN under `top(4)` are 3
    names at 1/3; 10 names with 4 finite are 0.25 each. The missing ones leave no cash."""
    five = frame({"A": 2.0, "B": NAN, "C": 4.0, "D": NAN, "E": 3.0})
    assert picked(five, 4) == [(DAY, "C", 1, 1 / 3), (DAY, "E", 2, 1 / 3), (DAY, "A", 3, 1 / 3)]
    ten = frame({f"N{i}": float(i) if i < 4 else NAN for i in range(10)})
    assert [(r[1], r[3]) for r in picked(ten, 10)] == [(f"N{i}", 0.25) for i in (3, 2, 1, 0)]


@pytest.mark.parametrize(("tiebreak", "order"), [(None, [2, 1, 3]), ("id", [1, 2, 3])])
def test_tiebreak_stable_across_decisions(tiebreak: str | None, order: list[int]) -> None:
    """3.7: the tie key reads the id alone, so three equal scores come in the same order at
    every decision (T-27's hash order by default), and `top(2)` holds the same two names."""
    found = picked(frame(T27, days=3), 3, tiebreak)
    expected = [(f"KR:T0000{i}", rank) for rank, i in enumerate(order, 1)]
    assert [(r[1], r[2]) for r in found] == expected * 3
    assert {r[1] for r in picked(frame(T27, days=3), 2, tiebreak)} == {e[0] for e in expected[:2]}


@pytest.mark.parametrize("policy", list(TiebreakPolicy))
def test_factor_top_matches_portfolio_top(policy: TiebreakPolicy) -> None:
    """3.7: `Factor.top(n)` through the executor and `nx.top(n)` take the same instruments
    under either `[portfolio] tiebreak`: ties across the cutoff, a NaN and an infinite score."""
    ids = tuple(f"I{i}" for i in range(8))
    close = np.array([[2.0, 5.0, 2.0, NAN, 2.0, 2.0, np.inf, 1.0]])
    dates = np.array(["2019-06-28"], dtype="datetime64[D]")
    ready = (dates + np.timedelta64(16, "h")).astype("datetime64[us]")
    block = MarketBlock("KR", dates, 0, ids, {"close": close}, np.ones((1, 8), bool),
                        np.zeros((1, 8), np.int8), ready[:, None].repeat(8, axis=1))  # fmt: skip
    term = BoundColumn.of("Price", "close").latest.top(3)
    cells = execute([term], [0], [(0, 0)], lambda a, b: block, ready, tiebreak=policy)
    kept = cells[graph_hash(term)]["value"].to_pylist()
    by_factor = {i for i, k in zip(ids, kept, strict=True) if k}
    found = frame(dict(zip(ids, close[0].tolist(), strict=True)))
    assert {r[1] for r in picked(found, 3, policy)} == by_factor
    assert len(by_factor) == 3


def test_unrelated_output_does_not_reshuffle() -> None:
    """INV-04, 3.7: the pick reads the scores and the ids only. Another column beside the
    score and another memory order of the rows give the same table, tied names included."""
    scores = {"KR:T00004": 3.0, **T27, "KR:T00005": 0.5}
    plain = build_targets(frame(scores, days=2), nx.top(3), GRID)[0]
    other = frame(scores, days=2, other=[9.0, 1.0, 7.0, 3.0, 5.0]).table
    shuffled = FactorFrame(other.take([7, 2, 9, 0, 5, 3, 8, 1, 6, 4]))
    again = build_targets(shuffled, nx.top(3), GRID)[0]
    assert again.table.equals(plain.table)
    assert again.coverage.equals(plain.coverage)
    assert plain.coverage["n_tied_at_cutoff"].to_pylist() == [3, 3]
