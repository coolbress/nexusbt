"""The engine. Re-exports only the public surface of spec 3.1 (2.3), each name with its ticket.

`config` names both the 2.3 subpackage and the 3.1 function: the subpackage loads first, then
the name is bound to `api.config`, so only attribute access such as `nexusbt.config.load_config`
(and `import nexusbt.config as c`, which resolves through it) stops working (#53 Decisions).
"""

import typing as _typing
from importlib import metadata as _metadata

# Modules (3.1): `__version__`, T1.4 (#236): the installed distribution's, in L0 keys (5.3.9).
__version__ = _metadata.version("nexusbt")

# Results (3.1): `PipelineResult` and `Screen`, of `run_pipeline` and `screen` below, T1.13 (#249).
from nexusbt.api import PipelineResult as PipelineResult
from nexusbt.api import Screen as Screen

# Functions (3.1): `config`, T0.5a (#53). `api` loads the subpackage `nexusbt.config` (2.4) first,
# so the 3.1 function holds the name; `import nexusbt.config` still finds the module.
from nexusbt.api import config as config

# `describe` of a term, T1.5 (#237); the Terms row (3.1) of T1.5 is bound after the errors.
from nexusbt.api import describe as describe

# `open` [V31-PUB-03], T1.1a (#232): one package path, or a parent folder with `LATEST`.
from nexusbt.api import open as open  # noqa: A004 - the 3.1 name; `builtins.open` is untouched

# `rerun`, T1.15 (#250): a saved run again in a new process, its outputs compared.
from nexusbt.api import rerun as rerun

# `run_pipeline` and its result `PipelineResult`, T1.13 (#249).
from nexusbt.api import run_pipeline as run_pipeline

# `screen(factor, top=n)`, T1.13 (#249).
from nexusbt.api import screen as screen

# `top(n)` at equal weights (3.7), T3.1a (#908).
from nexusbt.api import top as top

# Errors (3.1): `NexusBTError` and the 6.6 classes E1~E39, T0.4 (#49); E40~E49, T0.4b (#52);
# E50 with its rule (#873).
from nexusbt.contracts import AccountingDataError as AccountingDataError
from nexusbt.contracts import AccountNotEvaluatedNotice as AccountNotEvaluatedNotice
from nexusbt.contracts import BlockOutputError as BlockOutputError
from nexusbt.contracts import BookConflictError as BookConflictError
from nexusbt.contracts import CapabilityError as CapabilityError
from nexusbt.contracts import CollateralWarning as CollateralWarning
from nexusbt.contracts import ColumnNameError as ColumnNameError
from nexusbt.contracts import ConfigError as ConfigError
from nexusbt.contracts import CostTableError as CostTableError
from nexusbt.contracts import CoverageWarning as CoverageWarning
from nexusbt.contracts import DataAvailabilityError as DataAvailabilityError
from nexusbt.contracts import DataProfileWarning as DataProfileWarning
from nexusbt.contracts import EngineBugError as EngineBugError
from nexusbt.contracts import FillWarning as FillWarning
from nexusbt.contracts import FitLeakError as FitLeakError
from nexusbt.contracts import FxStaleError as FxStaleError
from nexusbt.contracts import IdempotencyNotice as IdempotencyNotice
from nexusbt.contracts import ImpureFunctionWarning as ImpureFunctionWarning
from nexusbt.contracts import LabelLeakError as LabelLeakError
from nexusbt.contracts import LookAheadError as LookAheadError
from nexusbt.contracts import LotRoundingWarning as LotRoundingWarning
from nexusbt.contracts import MLDeterminismWarning as MLDeterminismWarning
from nexusbt.contracts import NexusBTError as NexusBTError
from nexusbt.contracts import OrderSanityWarning as OrderSanityWarning
from nexusbt.contracts import PayDateEstimatedWarning as PayDateEstimatedWarning
from nexusbt.contracts import PretrainedLeakError as PretrainedLeakError
from nexusbt.contracts import PretrainedOverlapWarning as PretrainedOverlapWarning
from nexusbt.contracts import ProvisionalCostWarning as ProvisionalCostWarning
from nexusbt.contracts import ReconcileMismatch as ReconcileMismatch
from nexusbt.contracts import ReplayError as ReplayError
from nexusbt.contracts import SegmentNotice as SegmentNotice
from nexusbt.contracts import SelectionUndefinedError as SelectionUndefinedError
from nexusbt.contracts import SessionNotice as SessionNotice
from nexusbt.contracts import SkippedWorkNotice as SkippedWorkNotice
from nexusbt.contracts import SnapshotError as SnapshotError
from nexusbt.contracts import SolverFallbackNotice as SolverFallbackNotice
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
from nexusbt.contracts import ValidationNotice as ValidationNotice
from nexusbt.contracts import WindowError as WindowError
from nexusbt.pipeline import BoundColumn as BoundColumn
from nexusbt.pipeline import Classifier as Classifier
from nexusbt.pipeline import Factor as Factor
from nexusbt.pipeline import Filter as Filter
from nexusbt.pipeline import Pipeline as Pipeline
from nexusbt.pipeline import Term as Term
from nexusbt.pipeline import classifier as classifier
from nexusbt.pipeline import factor as factor
from nexusbt.pipeline import filter as filter  # noqa: A004 - the 3.1 name `nx.filter`

# `ops` of the Terms row (3.1), T1.10 (#243): `nx.ops.rolling`, `where`, `coalesce`.
from nexusbt import ops as ops  # isort: skip

# `factors` of the Terms row (3.1), T1.10 (#243): `nx.describe(nx.factors)` (2.5).
from nexusbt import factors as factors

# Datasets (3.1, 3.2), T1.6 (#238): the editor and the type checker read their columns from
# the stubs `nexusbt stubs` writes; the classes themselves are `pipeline`'s.
if _typing.TYPE_CHECKING:
    from nexusbt._stubs.datasets import Meta as Meta
    from nexusbt._stubs.datasets import Price as Price
else:
    from nexusbt.pipeline import Meta as Meta
    from nexusbt.pipeline import Price as Price
