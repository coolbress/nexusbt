"""Run one of the engine and TDS check jobs of spec 9.1 (T0.10).

From the repository root: `uv run python tests/repo/ci_jobs.py "<check>"`.

Each check runs the local command of the 9.1 table, step by step, and prints each
command before it runs. A check with no tests yet passes with "no tests yet": a step
whose file or module does not exist yet is not run, and pytest collecting nothing
(exit 5) is not a failure. That pass is written as a `not yet confirmed:` line, because
the milestone that makes the check required asks that it run at least one test.
A pytest step whose `-m` expression names a marker `pyproject.toml` does not register
fails without running, so a misspelt marker cannot pass as "no tests yet".
"""

from __future__ import annotations

import importlib.util
import itertools
import os
import re
import subprocess
import sys
import tomllib
from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Step:
    command: str
    #: A repository path or an importable module the command needs; absent → not run.
    needs_path: str | None = None
    needs_module: str | None = None


PARITY = "tests/parity/pyproject.toml"

#: The "Checks the engine adds" table of spec 9.1, its local commands split at `&&`.
CHECKS: dict[str, tuple[Step, ...]] = {
    "engine / parity": (
        Step("uv sync --project tests/parity --locked", needs_path=PARITY),
        Step(
            "uv run --project tests/parity python -m parity.run --suite all --fixture small",
            needs_path=PARITY,
        ),
        Step("uv run pytest -m parity"),
    ),
    "engine / property-deep": (
        Step("uv run pytest -m property --hypothesis-profile=deep", needs_module="hypothesis"),
    ),
    "engine / perf-smoke": (Step("uv run pytest -m perf_smoke"),),
    "engine / docs-examples": (Step("uv run pytest tests/docs -m examples"),),
    "engine / golden-guard": (
        Step(
            "uv run pytest tests/repo/test_golden_guard.py",
            needs_path="tests/repo/test_golden_guard.py",
        ),
    ),
    "engine / release": (
        Step(
            "uv run python -m tests.repo.release_check",
            needs_path="tests/repo/release_check.py",
        ),
    ),
    "tds / conformance": (
        Step("uv run --package nexusbt-tds pytest tds/tests", needs_path="tds/tests"),
        Step(
            "uv run python -m nexusbt.testing.synth --preset small --out .scratch/snap --validate",
            needs_module="nexusbt.testing.synth",
        ),
    ),
    "tds / schemas": (
        Step(
            "uv run --package nexusbt-tds python -m nexusbt_tds.schemas.verify",
            needs_module="nexusbt_tds.schemas.verify",
        ),
    ),
}


#: pytest's exit status when it collected no tests.
NO_TESTS_COLLECTED = 5

#: The words of a pytest `-m` expression that are not marker names.
MARKER_OPERATORS = frozenset({"and", "or", "not"})


def registered_markers(pyproject: Path) -> set[str]:
    """The marker names `pyproject.toml` registers for pytest, without their descriptions."""
    config = tomllib.loads(pyproject.read_text())
    lines: list[str] = config["tool"]["pytest"]["ini_options"]["markers"]
    return {line.split(":", 1)[0].strip() for line in lines}


def marker_names(argv: Sequence[str]) -> set[str]:
    """The marker names in the `-m <expression>` arguments that follow `pytest` in `argv`.

    pytest's `--strict-markers` refuses an unregistered mark in code but not one in `-m`:
    there it deselects every test and exits 5, which would read as "no tests yet" (#88).
    """
    if "pytest" not in argv:
        return set()
    args = argv[argv.index("pytest") + 1 :]
    expressions = [expr for flag, expr in itertools.pairwise(args) if flag in ("-m", "--markexpr")]
    for arg in args:
        if arg.startswith("--markexpr="):
            expressions.append(arg.removeprefix("--markexpr="))
        elif arg.startswith("-m") and arg != "-m":
            expressions.append(arg.removeprefix("-m"))
    # pytest's own identifier: word characters and `:+-.[]`.
    names = {name for e in expressions for name in re.findall(r"[\w:+\-.\[\]]+", e)}
    return names - MARKER_OPERATORS


def no_tests_yet(name: str, step: Step, why: str, out: Callable[[str], None]) -> str:
    """Say in the log and as an annotation that `step` checked nothing; return the line."""
    out(f"no tests yet: {why}")
    line = (
        f"not yet confirmed: {name} runs no tests yet, `{step.command}`: {why}; the milestone "
        "that makes this check required needs it to run at least one test (spec 9.1)"
    )
    out(f"::warning::{line}")
    return line


def run_check(
    name: str,
    *,
    root: Path,
    run: Callable[[Sequence[str]], int],
    has_module: Callable[[str], bool],
    markers: Collection[str],
    out: Callable[[str], None],
    summary: Path | None,
) -> int:
    """Run the steps of check `name` in order, stopping at the first failure.

    `markers` are the registered pytest markers; a step whose `-m` names another fails unrun.
    """
    lines: list[str] = []
    code = 0
    for step in CHECKS[name]:
        out(f"$ {step.command}")
        argv = step.command.split()
        unknown = marker_names(argv) - set(markers)
        if unknown:
            code = 1
            line = (
                f"fail: {name}, `{step.command}` names a marker not registered in "
                f"pyproject.toml: {', '.join(sorted(unknown))}"
            )
            out(f"::error::{line}")
            lines.append(line)
            break
        if step.needs_path is not None and not (root / step.needs_path).exists():
            lines.append(no_tests_yet(name, step, f"{step.needs_path} does not exist yet", out))
            continue
        if step.needs_module is not None and not has_module(step.needs_module):
            why = f"module {step.needs_module} does not exist yet"
            lines.append(no_tests_yet(name, step, why, out))
            continue
        code = run(argv)
        if code == NO_TESTS_COLLECTED and "pytest" in argv:
            code = 0
            lines.append(no_tests_yet(name, step, "pytest collected no tests", out))
        elif code != 0:
            lines.append(f"fail: {name}, `{step.command}` exited {code}")
            break
        else:
            lines.append(f"pass: {name}, `{step.command}`")
    if summary is not None:
        with summary.open("a") as f:
            f.writelines(f"- {line}\n" for line in lines)
    return code


def module_exists(name: str) -> bool:
    """Whether `name` imports in this environment; a missing parent package counts as missing."""
    try:
        return importlib.util.find_spec(name) is not None
    except ModuleNotFoundError:
        return False


def main(args: Sequence[str]) -> int:
    if len(args) != 1 or args[0] not in CHECKS:
        print(f"usage: tests/repo/ci_jobs.py <check>, one of: {', '.join(CHECKS)}", file=sys.stderr)
        return 2
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    return run_check(
        args[0],
        root=Path.cwd(),
        # The commands are the constants of CHECKS, never input from outside.
        run=lambda argv: subprocess.run(argv, check=False).returncode,  # noqa: S603
        has_module=module_exists,
        markers=registered_markers(Path.cwd() / "pyproject.toml"),
        out=lambda line: print(line, flush=True),
        summary=Path(summary) if summary else None,
    )


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
