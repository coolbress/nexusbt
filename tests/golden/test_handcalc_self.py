"""The golden cases check themselves (spec 8.2, T0.9).

A case is `cases/<id>.yaml`: its expected numbers are literals a person checked by hand. Next
to it, `check/<id>.py` reaches the same numbers by plain arithmetic and rounding, with no loops,
classes or engine imports, so it cannot grow into a second engine whose errors follow the
engine's. These tests hold the check files to that shape and each case to its check.
"""

from __future__ import annotations

import ast
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


def test_loop_and_engine_rules_catch_a_violation(tmp_path: Path) -> None:
    """The two AST rules refuse what they are for, so a pass above is not vacuous."""
    bad = tmp_path / "bad.py"
    bad.write_text("from nexusbt.accounting import x\nimport nexusbt_tds\ny = [i for i in x]\n")
    assert loops(bad) == ["comprehension"]
    assert engine_imports(bad) == ["nexusbt.accounting", "nexusbt_tds"]
