"""Spec 2.4: every name of the "Public interface" column, importable from its module.

The names are copied from the 2.4 table (#61); `api` is "the functions of 3.8",
the top-level `nx.<name>(...)` lines. A function's body is
`NotImplementedError` until its own ticket; a test that calls one sees it.
"""

from __future__ import annotations

import importlib
import inspect
from collections.abc import Callable
from pathlib import Path

import pytest

PUBLIC = {
    "nexusbt_tds": "check read_manifest value_hash semantic_hash import_csv build_manifest"
    " PROFILES SCHEMAS CheckResult ProfileStatus Manifest",
    "nexusbt.contracts": "ID_COLUMN ENGINE_COLUMNS Unit Currency Phase RUN_SCHEMA EVENTS_SCHEMA"
    " CHECKPOINT_SCHEMA NexusBTError FactorFrame TargetFrame TargetState DecisionGrid"
    " DecisionContext DecisionInputs SchemaRegistry ResolvedActions SessionInputs MarketView"
    " EventSink DelistingPolicy RightsPolicy UnsupportedPolicy DecimalRatioPolicy"
    " MissingPayDatePolicy BonusSharesTradablePolicy UnknownInclusionPolicy EditionPolicy"
    " VerifyPolicy PinsPolicy FallbacksPolicy TiebreakPolicy BandEntriesPolicy AccountTypePolicy"
    " OrderTypePolicy ExecutionAtPolicy BandModePolicy LimitFillPolicy UnknownTradabilityPolicy"
    " CostProfilePolicy TaxesProfilePolicy TaxesPayPolicy TaxesBasisPolicy LabelEntryPolicy"
    " EvaluateTargetPolicy RoundingModePolicy",
    "nexusbt.config": "load_config Config",
    "nexusbt.data": "open_snapshot Snapshot",
    "nexusbt.pipeline": "Term Factor Filter Classifier Pipeline Price Fund Meta Panel Label"
    " factor filter classifier factors graph_hash static_check",
    "nexusbt.compute": "compute ComputePolicy TermCache",
    "nexusbt.portfolio": "build_targets PortfolioRule",
    "nexusbt.risk": "RiskRule none Sizer",
    "nexusbt.accounting": "AccountState apply_session_start value bridge",
    "nexusbt.execution": "simulate step_session SimConfig",
    "nexusbt.research": "forward_labels factor_stats psr dsr min_trl pbo_cscv bhy_adjust"
    " lo_sharpe newey_west_t signal_weight_corr Segments TrialRegistry probe_truncation"
    " probe_start LabelFrame EvalConfig",
    "nexusbt.artifacts": "RunStore RunTxn Index BookStore BookTxn derive_tables render_report",
    "nexusbt.api": "evaluate backtest screen live fill reconcile sweep compare explain check"
    " describe runs rerun book override record_fills cash_flow preregister config open",
}

#: Classes whose public members are stubs too, each called through the class.
STUB_CLASSES = [
    "nexusbt.data.Snapshot",
    "nexusbt.artifacts.RunTxn",
    "nexusbt.artifacts.RunStore",
    "nexusbt.artifacts.BookStore",
]
#: Functions whose ticket has landed: no longer stubs (T0.13a, #51; T0.5a, #53).
BUILT = {
    "nexusbt_tds.read_manifest",
    "nexusbt_tds.check",
    "nexusbt.config.load_config",
    "nexusbt.api.config",
}

#: 6.6, the classes whose kind is block or fail: the sub-errors of `NexusBTError`. The warnings
#: and notices are checked with every E1~E39 code in `contracts/test_errors.py`.
ERRORS = (
    "LookAheadError LabelLeakError PointInTimeError UnitError ColumnNameError WindowError"
    " UnsupportedCorporateActionError AccountingDataError SnapshotError ReplayError ConfigError"
    " TermDomainError CapabilityError DataAvailabilityError FxStaleError CostTableError"
    " FitLeakError UntrustedRunError BookConflictError BlockOutputError EngineBugError"
    " DatasetShapeError PretrainedLeakError"
)

NAMES = [(module, name) for module, names in PUBLIC.items() for name in names.split()]


@pytest.mark.parametrize(("module", "name"), NAMES)
def test_public_name_importable(module: str, name: str) -> None:
    assert hasattr(importlib.import_module(module), name), f"{module} has no {name}"


def stub_functions() -> list[tuple[str, Callable[..., object]]]:
    found: list[tuple[str, Callable[..., object]]] = []
    for module, name in NAMES:
        obj = getattr(importlib.import_module(module), name, None)
        if inspect.isfunction(obj) and f"{module}.{name}" not in BUILT:
            found.append((f"{module}.{name}", obj))
    for path in STUB_CLASSES:
        module, _, cls = path.rpartition(".")
        for name, member in vars(getattr(importlib.import_module(module), cls)).items():
            if not name.startswith("_"):  # a property is called through its getter
                found.append((f"{path}.{name}", getattr(member, "fget", member)))
    return found


@pytest.mark.parametrize(("label", "function"), stub_functions())
def test_stub_raises_not_implemented(label: str, function: Callable[..., object]) -> None:
    params = inspect.signature(function).parameters.values()
    args = [None for p in params if p.kind in {p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD}]
    kwargs = {p.name: None for p in params if p.kind == p.KEYWORD_ONLY}
    with pytest.raises(NotImplementedError):
        function(*args, **kwargs)


@pytest.mark.parametrize("name", ERRORS.split())
def test_errors_are_nexusbt_errors(name: str) -> None:
    contracts = importlib.import_module("nexusbt.contracts")
    assert issubclass(getattr(contracts, name), contracts.NexusBTError)


def test_column_name_error_is_an_attribute_error() -> None:
    from nexusbt.contracts import ColumnNameError  # 6.6, E7: "subclass of `AttributeError`"

    assert issubclass(ColumnNameError, AttributeError)


@pytest.mark.parametrize("name", ["RunStore", "Index", "BookStore"])
def test_store_constructor_raises_not_implemented(name: str, tmp_path: Path) -> None:
    with pytest.raises(NotImplementedError):  # 2.4 `RunStore(root)`, `Index(root)`, ...
        getattr(importlib.import_module("nexusbt.artifacts"), name)(tmp_path)
