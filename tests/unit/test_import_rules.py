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
from collections.abc import Callable
from itertools import pairwise
from pathlib import Path

import pytest

Check = Callable[[tuple[str, ...], str], list[str]]
ROOT = Path(__file__).resolve().parents[2]
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
