"""Scores → canonical target (pure functions: construction → sizing → risk) + the account layer."""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from itertools import groupby
from typing import TYPE_CHECKING, Any

import pyarrow as pa

from nexusbt.contracts import ID_COLUMN, TargetFrame, TargetState, TiebreakPolicy

if TYPE_CHECKING:
    from nexusbt.contracts import DecisionGrid, FactorFrame
    from nexusbt.risk import RiskRule

_SALT = b"nexusbt-tiebreak-v1"
_WEIGHTS = ("pre_risk_weight", "target_weight", "decided_weight", "final_weight")


@dataclass(frozen=True, slots=True)
class PortfolioRule:
    """3.7 `top(n)`: at most the `n` highest finite scores of each sleeve, weighted equally.
    `tiebreak` None is the hash key, the value `[portfolio] tiebreak` has by default:
    `build_targets` reads no config, so the caller that has one passes the project's key."""

    n: int
    tiebreak: TiebreakPolicy | None = None


def tie_key(instrument_id: str, policy: TiebreakPolicy) -> tuple[int, str]:
    """3.7's tie-break key, ascending: `"hash"` = the first 8 bytes of
    sha256(salt || 0x1F || id) as a big-endian unsigned integer, then the id; `"id"` = the id.
    It reads nothing but the id, so the order is the same at every decision."""
    if policy is TiebreakPolicy.ID:
        return (0, instrument_id)
    digest = hashlib.sha256(_SALT + b"\x1f" + instrument_id.encode()).digest()
    return (int.from_bytes(digest[:8], "big"), instrument_id)


def build_targets(
    scores: FactorFrame,
    rule: PortfolioRule,
    grid: DecisionGrid,
    *,
    risk: RiskRule | None = None,
    prior: TargetState | None = None,
) -> tuple[TargetFrame, TargetState]:
    """The canonical target of each decision in `scores` (5.5.1), from the information at the
    decision alone: within a sleeve, the first `rule.n` cells whose score is finite and whose
    universe is true, by descending score then ascending tie key (3.7), each at 1/k of the k
    taken, so fewer finite scores than n leave no cash behind (#875). One stage: the rows are
    the canonical final ones; sizing slots, caps, `risk` and `prior` come with T3.1."""
    if risk is not None or prior is not None:
        raise NotImplementedError("build_targets takes no risk rule and no prior state yet")
    if rule.n < 0:
        raise ValueError(f"a selection takes at least zero cells, not {rule.n}")
    policy = TiebreakPolicy(rule.tiebreak or TiebreakPolicy.HASH)
    rows: list[dict[str, Any]] = []
    tied: dict[str, int] = {}

    def decision(cell: dict[str, Any]) -> tuple[str, Any]:
        return cell["market"], cell["session_date"]

    for (sleeve, day), cells in groupby(sorted(scores.table.to_pylist(), key=decision), decision):
        found = [c for c in cells if c.get("universe", True) is True
                 and c["score"] is not None and math.isfinite(c["score"])]  # fmt: skip
        found.sort(key=lambda c: (-c["score"], tie_key(c[ID_COLUMN], policy)))
        taken = found[: rule.n]
        decision_id = f"{sleeve}:{day:%Y%m%d}:{grid.clock}"
        straddles = len(found) > len(taken) > 0 and found[len(taken)]["score"] == taken[-1]["score"]
        tied[decision_id] = sum(c["score"] == taken[-1]["score"] for c in found) if straddles else 0
        for rank, cell in enumerate(taken, 1):
            weights = dict.fromkeys(_WEIGHTS, 1 / len(taken)) | {"decided_weight": None}
            rows.append({"decision_id": decision_id, "sleeve_id": sleeve,
                         "decision_ts": cell["decision_ts"], "session_date": day,
                         ID_COLUMN: cell[ID_COLUMN], "score": cell["score"],
                         "selected_rank": rank, "stage": "risk", **weights,
                         "side": "long", "reason": "selected"})  # fmt: skip
    rows.sort(key=lambda r: (r["decision_id"], r["selected_rank"], r[ID_COLUMN]))
    text = ("decision_id", "sleeve_id", ID_COLUMN, "stage", "side", "reason")
    kinds = {"decision_ts": scores.table.schema.field("decision_ts").type,
             "session_date": pa.date32(), "selected_rank": pa.int32()}  # fmt: skip
    names = ("decision_id", "sleeve_id", "decision_ts", "session_date", ID_COLUMN, "score",
             "selected_rank", "stage", *_WEIGHTS, "side", "reason")  # fmt: skip
    schema = pa.schema(
        [(n, kinds.get(n, pa.string() if n in text else pa.float64())) for n in names]
    )
    counts = pa.array([tied[d] for d in sorted(tied)], pa.int32())
    coverage = pa.table({"decision_id": pa.array(sorted(tied), pa.string()),
                         "n_tied_at_cutoff": counts})  # fmt: skip
    return TargetFrame(pa.Table.from_pylist(rows, schema=schema), coverage), TargetState()
