"""Spec 2.5's "No sources of non-determinism", read through the AST of the decision-path
modules (INV-09; T1.27, #256).

The decision-path modules (`data`, `compute`, `pipeline`, `portfolio`, `risk`, `accounting`,
`execution`, `research`) use no wall clock, no random numbers, no `uuid1`/`uuid4`, no
`os.urandom` and no `secrets`; a `numpy.random.Generator` is taken as an argument, so the name
may appear in an annotation only. Ruff's `banned-api` bans in every module of `src/**` what no
module uses; this test bans the whole list in the decision modules, as one ruff table cannot be
scoped by module (#256's Decisions, 2026-11-26).

Where iteration over a `set` or `frozenset` sets an order, it goes through `sorted(...)`. Read
from the code as written (#256's Decisions, 2026-11-26): in a function, an iteration (a `for`,
a list, generator or dict comprehension, `list(...)`, `tuple(...)`) over a set literal or set
comprehension, a `set(...)` or `frozenset(...)` call, a `|`, `&`, `-` or `^` of one, or a name
the function binds to one or annotates as `set`/`frozenset` (its parameters included), unless
its result goes straight into `set`, `frozenset`, `any`, `all`, `len`, `sorted`, `min` or
`max`, which do not depend on the order (`sum` does, for floats). A dict keeps its insertion
order and is not read; a set whose type the code does not show (an attribute, another
function's return) is not seen.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DECISION = ("data", "compute", "pipeline", "portfolio", "risk", "accounting", "execution",
            "research")  # fmt: skip
#: Spec 2.5's list, as qualified names; a name below one of them is banned too.
BANNED = ("datetime.datetime.now", "datetime.datetime.utcnow", "datetime.datetime.today",
          "datetime.date.today", "time.time", "time.monotonic", "time.perf_counter", "random",
          "numpy.random", "uuid.uuid1", "uuid.uuid4", "os.urandom", "secrets")  # fmt: skip
#: Taken as an argument (2.5): allowed in an annotation and in its import.
ARGUMENT = "numpy.random.Generator"
ORDERLESS = {"set", "frozenset", "any", "all", "len", "sorted", "min", "max"}


def decision_files() -> list[Path]:
    return sorted(f for m in DECISION for f in (ROOT / "src" / "nexusbt" / m).rglob("*.py"))


def banned(name: str) -> bool:
    return any(name == b or name.startswith(b + ".") for b in BANNED)


def aliases(tree: ast.AST) -> dict[str, str]:
    """Each name an import binds, with the qualified name it stands for."""
    found = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:  # `import a.b` binds `a`; `import a.b as c` binds `c`
                top = a.name.split(".")[0]
                found[a.asname or top] = a.name if a.asname else top
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            for a in node.names:
                found[a.asname or a.name] = f"{node.module}.{a.name}"
    return found


def qualified(node: ast.AST, names: dict[str, str]) -> str | None:
    if isinstance(node, ast.Name):
        return names.get(node.id)
    if isinstance(node, ast.Attribute) and (base := qualified(node.value, names)):
        return f"{base}.{node.attr}"
    return None


def annotated(tree: ast.AST) -> set[ast.AST]:
    """Every node inside an annotation."""
    roots: list[ast.AST] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = node.args
            every = [*args.posonlyargs, *args.args, *args.kwonlyargs, args.vararg, args.kwarg]
            roots += [a.annotation for a in every if a is not None and a.annotation is not None]
            roots += [node.returns] if node.returns else []
        elif isinstance(node, ast.AnnAssign):
            roots.append(node.annotation)
    return {n for r in roots for n in ast.walk(r)}


def wallclock_or_rng(where: str, source: str) -> list[str]:
    """The uses of spec 2.5's sources of non-determinism, one per line."""
    tree = ast.parse(source)
    names, typed = aliases(tree), annotated(tree)
    hits: dict[int, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            bound = aliases(ast.Module(body=[node], type_ignores=[]))
            used = [q for q in bound.values() if banned(q) and q != ARGUMENT]
        elif isinstance(node, (ast.Name, ast.Attribute)) and (q := qualified(node, names)):
            argument = node in typed and (q == ARGUMENT or ARGUMENT.startswith(q + "."))
            used = [q] if banned(q) and not argument else []
        else:
            continue
        if used:
            hits.setdefault(node.lineno, f"{where}:{node.lineno} uses {used[0]}")
    return [hits[k] for k in sorted(hits)]


def is_set(node: ast.AST, sets: set[str]) -> bool:
    if isinstance(node, (ast.Set, ast.SetComp)):
        return True
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        return node.func.id in {"set", "frozenset"}
    if isinstance(node, ast.BinOp) and isinstance(
        node.op, (ast.BitOr, ast.BitAnd, ast.Sub, ast.BitXor)
    ):
        return is_set(node.left, sets) or is_set(node.right, sets)
    return isinstance(node, ast.Name) and node.id in sets


def set_typed(annotation: ast.AST | None) -> bool:
    text = ast.unparse(annotation) if annotation is not None else ""
    return text.split("[")[0] in {"set", "frozenset"}


def unsorted_set_iteration(where: str, source: str) -> list[str]:
    """Each iteration over a set, read as the module docstring says."""
    hits = []
    tree = ast.parse(source)
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        args = fn.args
        sets = {a.arg for a in [*args.posonlyargs, *args.args, *args.kwonlyargs]
                if set_typed(a.annotation)}  # fmt: skip
        for node in ast.walk(fn):
            if isinstance(node, ast.Assign) and is_set(node.value, set()):
                sets |= {t.id for t in node.targets if isinstance(t, ast.Name)}
            elif (isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
                  and set_typed(node.annotation)):  # fmt: skip
                sets.add(node.target.id)
        parent = {c: p for p in ast.walk(fn) for c in ast.iter_child_nodes(p)}
        for node in ast.walk(fn):
            over: list[ast.expr] = []
            if isinstance(node, ast.For):
                over = [node.iter]
            elif isinstance(node, (ast.ListComp, ast.GeneratorExp, ast.DictComp)):
                over = [g.iter for g in node.generators]
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                over = node.args[:1] if node.func.id in {"list", "tuple"} else []
            if not any(is_set(it, sets) for it in over):
                continue
            up = parent.get(node)
            if isinstance(up, ast.Call) and getattr(up.func, "id", None) in ORDERLESS:
                continue
            hits.append(f"{where}:{over[0].lineno} iterates over a set without sorted(...)")
    return sorted(set(hits))


def relative(file: Path) -> str:
    return str(file.relative_to(ROOT))


def test_no_wallclock_or_rng_in_decision_modules() -> None:
    files = decision_files()
    assert len({f.parts[len(ROOT.parts) + 2] for f in files}) == len(DECISION)
    assert [h for f in files for h in wallclock_or_rng(relative(f), f.read_text())] == []


def test_no_unsorted_set_iteration_in_event_paths() -> None:
    files = decision_files()
    assert [h for f in files for h in unsorted_set_iteration(relative(f), f.read_text())] == []


@pytest.mark.parametrize(
    "source",
    [
        "from datetime import datetime\ndef f():\n    return datetime.now()",
        "import datetime\nx = datetime.datetime.utcnow()",
        "import datetime as dt\nx = dt.date.today()",
        "from time import perf_counter",
        "import time\nx = time.monotonic()",
        "import random",
        "import numpy as np\nx = np.random.default_rng(0)",
        "from numpy.random import default_rng",
        "import numpy as np\nx = np.random.Generator(np.random.PCG64(1))",
        "import uuid\nx = uuid.uuid4()",
        "import os\nx = os.urandom(8)",
        "from secrets import token_hex",
    ],
)
def test_wallclock_or_rng_caught(source: str) -> None:
    assert len(wallclock_or_rng("accounting/_x.py", source)) == 1


@pytest.mark.parametrize(
    "source",
    [
        "import numpy as np\ndef f(rng: np.random.Generator) -> None: ...",
        "from numpy.random import Generator\ndef f(rng: Generator) -> None: ...",
        "import datetime as dt\nx = dt.datetime(2020, 1, 1, tzinfo=dt.UTC)",
        "import time\ntime.sleep(0)",
        "import uuid\nx = uuid.UUID(int=0)",
    ],
)
def test_wallclock_or_rng_allowed(source: str) -> None:
    assert wallclock_or_rng("accounting/_x.py", source) == []


@pytest.mark.parametrize(
    "body",
    [
        "for x in {1, 2}: out.append(x)",
        "out = [x for x in set(xs)]",
        "s = frozenset(xs)\nout = tuple(s)",
        "out = list(set(a) | set(b))",
        "out = sum(x for x in set(xs))",
        "s: set[int] = set()\nfor x in s: out.append(x)",
        "out = {x: 1 for x in {y for y in xs}}",
    ],
)
def test_unsorted_set_iteration_caught(body: str) -> None:
    source = "def f(xs, a, b, out):\n" + "".join(f"    {line}\n" for line in body.split("\n"))
    assert len(unsorted_set_iteration("accounting/_x.py", source)) == 1


def test_unsorted_set_iteration_caught_on_a_set_parameter() -> None:
    source = "def f(xs: frozenset[str]) -> list[str]:\n    return [x for x in xs]\n"
    assert len(unsorted_set_iteration("accounting/_x.py", source)) == 1


@pytest.mark.parametrize(
    "body",
    [
        "out = [x for x in sorted(set(xs))]",
        "out = sorted(x for x in set(xs))",
        "out = any(x > 0 for x in set(xs))",
        "out = {x for x in set(xs)}",
        "out = max(x for x in frozenset(xs))",
        "for k in {'a': 1}: out.append(k)",
        "out = [x for x in xs]",
    ],
)
def test_unsorted_set_iteration_allowed(body: str) -> None:
    source = "def f(xs, out):\n" + "".join(f"    {line}\n" for line in body.split("\n"))
    assert unsorted_set_iteration("accounting/_x.py", source) == []
