"""The golden cases check themselves (spec 8.2, T0.9).

A case is `cases/<id>.yaml`: its expected numbers are literals a person checked by hand. Next
to it, `check/<id>.py` reaches the same numbers by plain arithmetic and rounding, with no loops,
classes or engine imports, so it cannot grow into a second engine whose errors follow the
engine's. T-25 is the exception in layout: one `factors/<name>.yaml` per built-in factor, all
checked by `check/T-25.py`. These tests hold the check files to that shape and each case to its
check.
"""

from __future__ import annotations

import ast
import math
import runpy
from pathlib import Path
from typing import Any

import pytest
import yaml

pytestmark = pytest.mark.golden

GOLDEN = Path(__file__).parent
CHECKS = sorted((GOLDEN / "check").glob("*.py"))
#: What a check file may not contain: loops of any kind, comprehensions among them, and classes.
LOOPS = (ast.For, ast.AsyncFor, ast.While, ast.comprehension, ast.ClassDef)
ENGINE = ("nexusbt", "nexusbt_tds")


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(), filename=str(path))


def loops(path: Path) -> list[str]:
    """The loop and class nodes in the file at `path`."""
    return [type(node).__name__ for node in ast.walk(_tree(path)) if isinstance(node, LOOPS)]


def engine_imports(path: Path) -> list[str]:
    """The modules of the engine or the checker that the file at `path` imports."""
    names: list[str] = []
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None and node.level == 0:
            names.append(node.module)
    return [name for name in names if name.split(".")[0] in ENGINE]


def _case(case_id: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """The case's yaml, and the rows its check file computes."""
    case = yaml.safe_load((GOLDEN / "cases" / f"{case_id}.yaml").read_text())
    rows = runpy.run_path(str(GOLDEN / "check" / f"{case_id}.py"), run_name="golden_check")["ROWS"]
    return case, list(rows)


def test_no_general_loops() -> None:
    assert CHECKS, "no check files under tests/golden/check"
    found = {path.name: loops(path) for path in CHECKS if loops(path)}
    assert not found, "check files are straight-line arithmetic (8.2)"


def test_checks_import_no_engine() -> None:
    assert CHECKS, "no check files under tests/golden/check"
    found = {path.name: engine_imports(path) for path in CHECKS if engine_imports(path)}
    assert not found, "a check computes its numbers without the engine (8.2)"


def test_case_G01_expected_present() -> None:  # noqa: N802 - the name spec 8.2 and T0.9 give
    case, rows = _case("G-01")
    assert case["id"] == "G-01"
    assert case["expected"], "G-01 has no expected rows"
    assert rows == case["expected"]


def nan_as_text(value: Any) -> Any:
    """`value` with every float NaN written "NaN", lists for tuples: NaN never equals itself."""
    if isinstance(value, float) and math.isnan(value):
        return "NaN"
    if isinstance(value, dict):
        return {k: nan_as_text(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [nan_as_text(v) for v in value]
    return value


#: The v3.1 cases M1 uses (T1.Gb): T-24 three-valued Filter, T-25 built-in factors, T-27 hash
#: tie-break. T-25 is one `factors/<name>.yaml` per built-in factor with `check/T-25.py`.
V31_M1 = ("T-24", "T-25", "T-27")
#: The 12 built-in factors of spec 3.4, each a file name under `factors/`.
BUILTIN_FACTORS = frozenset({
    "Returns", "DailyReturns", "SimpleMovingAverage", "ExponentialWeightedMovingAverage",
    "AverageDollarVolume", "AverageTradedValue", "AnnualizedVolatility", "RollingStd", "VWAP",
    "RSI", "MaxDrawdown", "Latest",
})  # fmt: skip


def _factor_cases() -> list[dict[str, Any]]:
    """T-25's expected rows: every case of every `factors/<name>.yaml`, its factor added."""
    rows: list[dict[str, Any]] = []
    for path in sorted((GOLDEN / "factors").glob("*.yaml")):
        doc = yaml.safe_load(path.read_text())
        assert doc["factor"] == path.stem, f"{path.name} names {doc['factor']}"
        rows.extend({"factor": doc["factor"], **case} for case in doc["cases"])
    return rows


def _by_term(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda row: (row["factor"], row["term"]))


@pytest.mark.parametrize("case_id", V31_M1)
def test_cases_v31_M1_expected_present(case_id: str) -> None:  # noqa: N802 - spec 10.1's name
    if case_id == "T-25":
        expected = _factor_cases()
        assert {row["factor"] for row in expected} == BUILTIN_FACTORS
        rows = runpy.run_path(str(GOLDEN / "check" / "T-25.py"), run_name="golden_check")["ROWS"]
        assert nan_as_text(_by_term(list(rows))) == nan_as_text(_by_term(expected))
        return
    case, rows = _case(case_id)
    assert case["id"] == case_id
    assert case["expected"], f"{case_id} has no expected rows"
    assert nan_as_text(rows) == nan_as_text(case["expected"])


#: The M1 time and pipeline cases (T1.G, spec 8.2): T-10 a start date on a holiday, T-20 a late
#: bar under `ready_delay`, T-23 the `every(n)` calendar anchor. T-07, T-09, T-11, T-12 and T-15
#: come in the next pull requests of #222.
TIME_M1 = ("T-10", "T-20", "T-23")


@pytest.mark.parametrize("case_id", TIME_M1)
def test_time_cases_M1_expected_present(case_id: str) -> None:  # noqa: N802 - spec 10.1's name
    case, rows = _case(case_id)
    assert case["id"] == case_id
    assert case["expected"], f"{case_id} has no expected rows"
    assert nan_as_text(rows) == nan_as_text(case["expected"])


def test_nan_as_text_tells_nan_apart() -> None:
    assert nan_as_text([{"v": (1.0, math.nan)}]) == [{"v": [1.0, "NaN"]}]
    assert nan_as_text([math.nan]) != nan_as_text([0.0])


def test_loop_and_engine_rules_catch_a_violation(tmp_path: Path) -> None:
    """The two AST rules refuse what they are for, so a pass above is not vacuous."""
    bad = tmp_path / "bad.py"
    bad.write_text("from nexusbt.accounting import x\nimport nexusbt_tds\ny = [i for i in x]\n")
    assert loops(bad) == ["comprehension"]
    assert engine_imports(bad) == ["nexusbt.accounting", "nexusbt_tds"]
