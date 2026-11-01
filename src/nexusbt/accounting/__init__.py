"""Columnar account state, integer minor-unit booking, corporate actions, valuation, NAV bridge."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nexusbt.contracts import ResolvedActions, SessionInputs


@dataclass(frozen=True, slots=True)
class AccountState: ...


@dataclass(frozen=True, slots=True)
class AccountingPolicy: ...


@dataclass(frozen=True, slots=True)
class Event: ...


@dataclass(frozen=True, slots=True)
class Marks: ...


@dataclass(frozen=True, slots=True)
class FxView: ...


@dataclass(frozen=True, slots=True)
class Valuation: ...


@dataclass(frozen=True, slots=True)
class BridgeRows: ...


def apply_session_start(
    state: AccountState,
    session: SessionInputs,
    actions: ResolvedActions,
    policy: AccountingPolicy,
) -> tuple[AccountState, list[Event]]:
    raise NotImplementedError


def value(state: AccountState, marks: Marks, fx: FxView, *, asof: datetime) -> Valuation:
    raise NotImplementedError


def bridge(prev: Valuation, cur: Valuation, events: Sequence[Event]) -> BridgeRows:
    raise NotImplementedError
