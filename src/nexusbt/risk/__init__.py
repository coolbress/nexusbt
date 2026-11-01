"""Money management `size.*` and risk rules `risk.*` (reserved `ledoit_wolf`)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from nexusbt.contracts import DecisionInputs, TargetFrame


class RiskRule(Protocol):
    def apply(self, targets: TargetFrame, inputs: DecisionInputs) -> TargetFrame: ...


class Sizer(Protocol): ...


def none() -> RiskRule:
    raise NotImplementedError
