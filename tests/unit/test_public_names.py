"""Spec 2.4: every name of the "Public interface" column, importable from its module.

The names are copied from the 2.4 table, one module at a time as its stubs land
(#61); `api` will be "the functions of 3.8", the top-level `nx.<name>(...)`
lines. A function's body is `NotImplementedError` until its own ticket; a test
that calls one sees it.
"""

from __future__ import annotations

import importlib
import inspect
from collections.abc import Callable

import pytest

PUBLIC = {
    "nexusbt_tds": "check read_manifest value_hash semantic_hash import_csv build_manifest"
    " PROFILES SCHEMAS CheckResult ProfileStatus Manifest",
    # ID_COLUMN, ENGINE_COLUMNS, Unit, Currency, Phase and the schema constants: #48 (T0.3)
    "nexusbt.contracts": "NexusBTError FactorFrame TargetFrame TargetState DecisionGrid"
    " DecisionContext DecisionInputs SchemaRegistry ResolvedActions SessionInputs MarketView"
    " EventSink",
    "nexusbt.config": "load_config Config",
}

#: 6.6, the classes whose kind is block or fail: the sub-errors of `NexusBTError`.
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
        if inspect.isfunction(obj):
            found.append((f"{module}.{name}", obj))
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
