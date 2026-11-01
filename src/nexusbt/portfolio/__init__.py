"""Scores → canonical target (pure functions: construction → sizing → risk) + the account layer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nexusbt.contracts import DecisionGrid, FactorFrame, TargetFrame, TargetState
    from nexusbt.risk import RiskRule


@dataclass(frozen=True, slots=True)
class PortfolioRule: ...


def build_targets(
    scores: FactorFrame,
    rule: PortfolioRule,
    grid: DecisionGrid,
    *,
    risk: RiskRule | None = None,
    prior: TargetState | None = None,
) -> tuple[TargetFrame, TargetState]:
    raise NotImplementedError
