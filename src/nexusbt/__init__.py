"""The engine. Re-exports only the public surface of spec 3.1 (2.3), each name with its ticket."""

# Functions (3.1): `config`, T0.5a (#53). `api` loads the subpackage `nexusbt.config` (2.4) first,
# so the 3.1 function holds the name; `import nexusbt.config` still finds the module.
from nexusbt.api import config as config

# Errors (3.1): `NexusBTError` and the 6.6 classes E1~E39, T0.4 (#49).
from nexusbt.contracts import AccountingDataError as AccountingDataError
from nexusbt.contracts import BookConflictError as BookConflictError
from nexusbt.contracts import CapabilityError as CapabilityError
from nexusbt.contracts import CollateralWarning as CollateralWarning
from nexusbt.contracts import ColumnNameError as ColumnNameError
from nexusbt.contracts import ConfigError as ConfigError
from nexusbt.contracts import CostTableError as CostTableError
from nexusbt.contracts import CoverageWarning as CoverageWarning
from nexusbt.contracts import DataAvailabilityError as DataAvailabilityError
from nexusbt.contracts import DataProfileWarning as DataProfileWarning
from nexusbt.contracts import FillWarning as FillWarning
from nexusbt.contracts import FitLeakError as FitLeakError
from nexusbt.contracts import FxStaleError as FxStaleError
from nexusbt.contracts import IdempotencyNotice as IdempotencyNotice
from nexusbt.contracts import ImpureFunctionWarning as ImpureFunctionWarning
from nexusbt.contracts import LabelLeakError as LabelLeakError
from nexusbt.contracts import LookAheadError as LookAheadError
from nexusbt.contracts import LotRoundingWarning as LotRoundingWarning
from nexusbt.contracts import NexusBTError as NexusBTError
from nexusbt.contracts import OrderSanityWarning as OrderSanityWarning
from nexusbt.contracts import PayDateEstimatedWarning as PayDateEstimatedWarning
from nexusbt.contracts import PointInTimeError as PointInTimeError
from nexusbt.contracts import ProvisionalCostWarning as ProvisionalCostWarning
from nexusbt.contracts import ReconcileMismatch as ReconcileMismatch
from nexusbt.contracts import ReplayError as ReplayError
from nexusbt.contracts import SegmentNotice as SegmentNotice
from nexusbt.contracts import SessionNotice as SessionNotice
from nexusbt.contracts import SnapshotError as SnapshotError
from nexusbt.contracts import StaleMarkWarning as StaleMarkWarning
from nexusbt.contracts import StartDependenceWarning as StartDependenceWarning
from nexusbt.contracts import StatisticUnavailable as StatisticUnavailable
from nexusbt.contracts import SurvivorshipWarning as SurvivorshipWarning
from nexusbt.contracts import TermDomainError as TermDomainError
from nexusbt.contracts import TradabilityUnknownWarning as TradabilityUnknownWarning
from nexusbt.contracts import UnitError as UnitError
from nexusbt.contracts import UnknownFilterNotice as UnknownFilterNotice
from nexusbt.contracts import UnmaskedCrossSectionNotice as UnmaskedCrossSectionNotice
from nexusbt.contracts import UnsupportedCorporateActionError as UnsupportedCorporateActionError
from nexusbt.contracts import UntrustedRunError as UntrustedRunError
from nexusbt.contracts import WindowError as WindowError
