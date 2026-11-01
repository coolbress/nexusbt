"""Orders (columnar order table), fill models, costs, sizing, the daily state machine, presets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nexusbt.accounting import AccountState
    from nexusbt.contracts import EventSink, MarketView, SessionInputs, TargetFrame


@dataclass(frozen=True, slots=True)
class SimConfig:
    """Every knob of appendix C, with its ticket."""


@dataclass(frozen=True, slots=True)
class SimResult: ...


@dataclass(frozen=True, slots=True)
class StepResult: ...


def simulate(
    targets: TargetFrame,
    market: MarketView,
    config: SimConfig,
    initial: AccountState,
    sink: EventSink,
) -> SimResult:
    raise NotImplementedError


def step_session(
    state: AccountState, orders: object, session: SessionInputs, config: SimConfig
) -> StepResult:
    raise NotImplementedError
