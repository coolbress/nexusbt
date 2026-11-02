"""Spec 2.5, the dependency rules, read from every import and call through the AST.

The graph is copied from 2.5 as drawn; `X ← Y` reads "Y imports X". The import
rule is four lines (#41 D2), quoted from 2.5 as written:

(1) `contracts` imports nothing, and every module may import it (it is the root
    of every chain and is not drawn as an arrow).
(2) Any other module imports only the modules its own **direct** arrows point
    to; an indirect path does not allow an import (`compute` → `data`,
    `pipeline`; `portfolio` → `risk`; `execution` → `accounting`; `data` →
    `config`, `nexusbt_tds`).
(3) `api` may import every engine module (it is the composer); `cli` imports
    only `api`.
(4) `compute` sits on the `data` and `pipeline` chains as the graph draws it;
    apart from that, only `api` joins chains.

A module is a package directly under `src/nexusbt/`; one the graph does not draw has
no arrow, so by rule 2 it imports only `contracts`. The root `nexusbt/__init__.py`
re-exports the 3.1 surface (2.3) and is outside the graph; the ban still applies.
"""

from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
from collections.abc import Callable
from itertools import pairwise
from pathlib import Path

import pytest

Check = Callable[[tuple[str, ...], str], list[str]]

#: 3.1 names a fresh `import nexusbt` does not bind yet, by the table's row (#47). A name
#: leaves this list in the change that exports it; the spec names no single ticket for many.
PENDING_3_1 = {
    "Terms": "Factor Filter Classifier Pipeline factor filter classifier ops",
    "Data": "Price Fund Meta Panel Label Trad Market Macro MacroTerm Events dataset Dataset"
    " universe",
    "Strategy": "Strategy param monthly weekly daily quarterly annually every on_event top bottom"
    " long_short portfolio size sizer risk risk_rule PortfolioContext SizingContext"
    " RiskContext TargetView RiskDecision Scalar execution exits ExitRule costs ml labels"
    " LabelTerm splits",
    "Functions": "open evaluate backtest screen live fill reconcile sweep compare run_pipeline"
    " explain check describe runs rerun book override record_fills cash_flow preregister config",
    "Results": "FactorReport Run Screen Orders BookUpdate ReconcileReport SweepResult Comparison"
    " ValidationResult Split PipelineResult Explanation DecisionExplanation CheckReport"
    " RunTable Description Preregistration Config Snapshot Book",
    "Errors (6.6, E40~E49)": "ValidationNotice BlockOutputError AccountNotEvaluatedNotice"
    " SolverFallbackNotice MLDeterminismWarning SkippedWorkNotice EngineBugError"
    " DatasetShapeError PretrainedLeakError PretrainedOverlapWarning",
    "Types": "Term BoundColumn Param Schedule PortfolioRule Sizer RiskRule ExecutionRule"
    " CostModel Window DecisionContext",
    "Modules": "compat testing __version__",
}
ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "docs" / "spec" / "engine-spec-v3.4.md"
TREES = (ROOT / "src", ROOT / "tds" / "src")

GRAPH = """
contracts ← config ← data ← compute ← api ← cli
nexusbt_tds ← data
contracts ← pipeline ← compute
contracts ← risk ← portfolio ← api
contracts ← accounting ← execution ← api
contracts ← research ← api
contracts ← artifacts ← api
"""

#: 2.5, second bullet: imported nowhere under `src/nexusbt/**` or `tds/src/nexusbt_tds/**`.
BAN = {"zipline", "nautilus_trader", "duckdb", "pickle", "dill", "cloudpickle", "joblib", "shelve"}


def direct_arrows() -> dict[str, set[str]]:
    """Module → the modules its own direct arrows point to; `contracts` is rule 1, not an arrow."""
    arrows: dict[str, set[str]] = {}
    for line in GRAPH.strip().splitlines():
        for target, importer in pairwise(part.strip() for part in line.split("←")):
            if target != "contracts":
                arrows.setdefault(importer, set()).add(target)
    return arrows


def engine_modules() -> set[str]:
    """The packages directly under `src/nexusbt/`: the modules of the 2.3 tree."""
    return {p.name for p in (ROOT / "src" / "nexusbt").iterdir() if (p / "__init__.py").is_file()}


def module_of(file: Path) -> tuple[str, ...]:
    """A file as its dotted module, in parts; `__init__` stays, so `module[:-1]` is the package."""
    tree = next(t for t in TREES if file.is_relative_to(t))
    return file.relative_to(tree).with_suffix("").parts


def imports_of(module: tuple[str, ...], source: str) -> list[tuple[str, ...]]:
    """Every module path the source imports, relative imports resolved against `module`."""
    package = module[:-1]
    found: list[tuple[str, ...]] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found.extend(tuple(alias.name.split(".")) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = package[: len(package) - (node.level - 1)] if node.level else ()
            base += tuple(node.module.split(".")) if node.module else ()
            if base in {("nexusbt",), ("nexusbt_tds",)}:
                # `from nexusbt import data` names a module, not an attribute of the root
                found.extend((*base, alias.name) for alias in node.names)
            else:
                found.append(base)
    return found


def layer_violations(module: tuple[str, ...], source: str) -> list[str]:
    """Imports the four-line rule forbids for this file; the cli arrow keeps api off cli."""
    if module[:1] != ("nexusbt",) or len(module) < 3:
        return []  # a file of the root package is outside the graph
    importer = module[1]
    allowed = (
        engine_modules() - {"cli"} if importer == "api" else direct_arrows().get(importer, set())
    )
    out = []
    for path in imports_of(module, source):
        if path[0] == "nexusbt_tds":
            target = "nexusbt_tds"
        elif path[0] == "nexusbt":
            target = path[1] if len(path) > 1 else "nexusbt"  # the root re-exports everything
        else:
            continue
        if target not in {importer, "contracts", *allowed}:
            out.append(f"{'.'.join(module)} imports {'.'.join(path)}")
    return out


def banned_uses(module: tuple[str, ...], source: str) -> list[str]:
    """Banned imports, and the `allow_pickle=True` and `read_pickle` calls, in the source."""
    name = ".".join(module)
    out = [f"{name} imports {'.'.join(p)}" for p in imports_of(module, source) if p[0] in BAN]
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call):
            if "read_pickle" in {getattr(node.func, "attr", None), getattr(node.func, "id", None)}:
                out.append(f"{name} calls read_pickle")
            pickled = [k for k in node.keywords if k.arg == "allow_pickle"]
            if any(isinstance(k.value, ast.Constant) and k.value.value is True for k in pickled):
                out.append(f"{name} calls with allow_pickle=True")
    return out


def findings(check: Check, files: list[Path]) -> list[str]:
    return [hit for f in files for hit in check(module_of(f), f.read_text())]


def test_layer_graph_respected() -> None:
    missing = set(GRAPH.split()) - {"←", "nexusbt_tds"} - engine_modules()
    assert not missing, f"modules the 2.5 graph draws are not packages under src/nexusbt: {missing}"
    assert findings(layer_violations, sorted(TREES[0].rglob("*.py"))) == []


def test_tds_does_not_import_nexusbt() -> None:
    files = sorted(TREES[1].rglob("*.py"))
    assert files, "tds/src/nexusbt_tds has no Python files"
    assert findings(lambda m, s: [p[0] for p in imports_of(m, s) if p[0] == "nexusbt"], files) == []


def test_banned_imports_absent_in_src() -> None:
    files = sorted(f for tree in TREES for f in tree.rglob("*.py"))
    assert {module_of(f)[0] for f in files} == {"nexusbt", "nexusbt_tds"}
    assert findings(banned_uses, files) == []


def spec_3_1_names() -> set[str]:
    """The 3.1 table's names, a parenthesis's examples left out; "the subclasses of 6.6" read."""
    text = SPEC.read_text(encoding="utf-8")
    table = text[text.index("Every public name under `nexusbt.`") : text.index("**Identifier**")]
    names: set[str] = set()
    for cell in re.findall(r"^\| (?!Kind |---)[^|]+\|([^|]+)\|", table, flags=re.MULTILINE):
        while (bare := re.sub(r"\([^()]*\)", "", cell)) != cell:
            cell = bare
        names |= {token.split(".")[0] for token in re.findall(r"`([^`]+)`", cell)}
    return names | set(re.findall(r"^\| E\d+ \| `(\w+)`", text, flags=re.MULTILINE))


def root_names() -> dict[str, bool]:
    """What a fresh `import nexusbt` binds: public name → is it the submodule `nexusbt.<name>`."""
    code = (
        "import json, types, nexusbt as m; print(json.dumps({n: isinstance(v, types.ModuleType)"
        " and v.__name__ == 'nexusbt.' + n for n, v in vars(m).items()"
        " if not n.startswith('_') or n == '__version__'}))"
    )
    command = [sys.executable, "-c", code]  # this interpreter, the literal above
    done = subprocess.run(command, capture_output=True, text=True, check=True)  # noqa: S603
    found: dict[str, bool] = json.loads(done.stdout)
    return found


def outside_3_1(bound: dict[str, bool], table: set[str], packages: set[str]) -> list[str]:
    """Bound names not in 3.1; a package of the 2.3 tree bound by importing it is layout."""
    layout = {n for n, module in bound.items() if module and n in packages}
    return sorted(set(bound) - table - layout)


def test_public_names_match_spec_3_1() -> None:
    """3.1: "a name outside this list starts with `_`"; the rest are exported or pending.

    Read in a fresh interpreter: another test's import of `nexusbt.config` would bind it.
    """
    table, bound = spec_3_1_names(), root_names()
    outside = outside_3_1(bound, table, engine_modules())
    assert outside == [], f"nexusbt exports names outside the 3.1 table: {outside}"
    pending = {n for names in PENDING_3_1.values() for n in names.split()}
    assert pending <= table, f"PENDING_3_1 names that are not in 3.1: {pending - table}"
    assert sorted(pending & set(bound)) == [], "exported now: take these out of PENDING_3_1"
    assert sorted(table - set(bound) - pending) == [], "neither exported nor pending"


def test_outside_3_1_excuses_only_a_bound_package() -> None:
    bound = {"contracts": True, "util": True, "contracts_x": False, "open": False}
    assert outside_3_1(bound, {"open"}, {"contracts"}) == ["contracts_x", "util"]


@pytest.mark.parametrize(
    ("module", "source", "check"),
    [
        (("nexusbt", "config", "_x"), "import nexusbt.data", layer_violations),
        (("nexusbt", "cli", "__init__"), "from .. import contracts, data", layer_violations),
        (("nexusbt", "contracts", "_x"), "from nexusbt import config", layer_violations),
        (("nexusbt", "api", "_x"), "import nexusbt.cli", layer_violations),
        (("nexusbt", "ml", "_x"), "from nexusbt.pipeline import Term", layer_violations),
        (("nexusbt", "data", "_x"), "import pickle", banned_uses),
        (("nexusbt_tds", "hash"), "from duckdb import connect", banned_uses),
        (("nexusbt", "data", "_x"), "np.load(p, allow_pickle=True)", banned_uses),
        (("nexusbt", "compat", "_x"), "read_pickle(p)", banned_uses),
    ],
)
def test_rules_catch_a_violation(module: tuple[str, ...], source: str, check: Check) -> None:
    assert len(check(module, source)) == 1


@pytest.mark.parametrize(
    ("module", "source"),
    [
        (("nexusbt", "compute", "_plan"), "from nexusbt import data, pipeline, contracts"),
        (
            ("nexusbt", "data", "__init__"),
            "import nexusbt_tds\nfrom . import _l0\nfrom .. import config",
        ),
        (("nexusbt", "api", "_run"), "from nexusbt import ml, testing, data\nimport argparse"),
        (("nexusbt", "__init__"), "from nexusbt.api import evaluate"),
    ],
)
def test_rules_allow_a_direct_arrow(module: tuple[str, ...], source: str) -> None:
    assert layer_violations(module, source) == []
