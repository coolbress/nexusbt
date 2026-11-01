"""ID constant, column sets, units, policies, errors, shared frame and context types; no deps.

The 2.4 shared types, declared empty, and the 6.6 error classes. `ID_COLUMN`,
`ENGINE_COLUMNS`, `Unit`, `Currency`, `Phase`, `Policy*` and the schema version
constants are T0.3's (#48); the error messages and `layer` lines are T0.4's.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class FactorFrame: ...


@dataclass(frozen=True, slots=True)
class TargetFrame: ...


@dataclass(frozen=True, slots=True)
class TargetState: ...


@dataclass(frozen=True, slots=True)
class DecisionGrid: ...


@dataclass(frozen=True, slots=True)
class DecisionContext: ...


@dataclass(frozen=True, slots=True)
class DecisionInputs: ...


@dataclass(frozen=True, slots=True)
class SchemaRegistry: ...


@dataclass(frozen=True, slots=True)
class ResolvedActions: ...


@dataclass(frozen=True, slots=True)
class SessionInputs: ...


@dataclass(frozen=True, slots=True)
class MarketView: ...


class EventSink(Protocol): ...


class NexusBTError(Exception):
    """The root of the 6.6 errors."""


# 6.6, the codes whose kind is block or fail, in code order; kept as a table.
# fmt: off
class LookAheadError(NexusBTError): ...  # E1
class LabelLeakError(NexusBTError): ...  # E2
class PointInTimeError(NexusBTError): ...  # E3
class UnitError(NexusBTError): ...  # E5
class ColumnNameError(NexusBTError, AttributeError): ...  # E7
class WindowError(NexusBTError): ...  # E8
class UnsupportedCorporateActionError(NexusBTError): ...  # E12
class AccountingDataError(NexusBTError): ...  # E13
class SnapshotError(NexusBTError): ...  # E14
class ReplayError(NexusBTError): ...  # E15
class ConfigError(NexusBTError): ...  # E16
class TermDomainError(NexusBTError): ...  # E17
class CapabilityError(NexusBTError): ...  # E18
class DataAvailabilityError(NexusBTError): ...  # E19
class FxStaleError(NexusBTError): ...  # E20
class CostTableError(NexusBTError): ...  # E23
class FitLeakError(NexusBTError): ...  # E29
class UntrustedRunError(NexusBTError): ...  # E31
class BookConflictError(NexusBTError): ...  # E35
class BlockOutputError(NexusBTError): ...  # E41
class EngineBugError(NexusBTError): ...  # E46
class DatasetShapeError(NexusBTError): ...  # E47
class PretrainedLeakError(NexusBTError): ...  # E48
# fmt: on
