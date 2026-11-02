"""The engine and TDS check jobs of spec 9.1 run their commands, or say "no tests yet" (T0.10, #50).

A fake runner stands in for the commands; the folder is a temporary one.
"""

from __future__ import annotations

import re
from collections.abc import Collection, Sequence
from pathlib import Path

from ci_jobs import CHECKS, run_check


class FakeRunner:
    """Records the commands it is given and answers each with an exit code."""

    def __init__(self, codes: dict[str, int] | None = None) -> None:
        self.codes = codes or {}
        self.ran: list[str] = []

    def __call__(self, argv: Sequence[str]) -> int:
        line = " ".join(argv)
        self.ran.append(line)
        return self.codes.get(line, 0)


def run_one(
    name: str, root: Path, fake: FakeRunner, modules: Collection[str] = ()
) -> tuple[int, str, str]:
    """Run one check; return its exit code, its log and its job-summary lines."""
    log: list[str] = []
    summary = root / "summary.md"
    code = run_check(
        name,
        root=root,
        run=fake,
        has_module=lambda m: m in modules,
        out=log.append,
        summary=summary,
    )
    return code, "\n".join(log), summary.read_text() if summary.exists() else ""


def test_a_passing_check_shows_its_command_and_passes(tmp_path: Path) -> None:
    fake = FakeRunner()
    code, log, summary = run_one("engine / perf-smoke", tmp_path, fake)
    assert code == 0
    assert fake.ran == ["uv run pytest -m perf_smoke"]
    assert "$ uv run pytest -m perf_smoke" in log
    assert summary == "- pass: engine / perf-smoke, `uv run pytest -m perf_smoke`\n"


def test_pytest_collecting_nothing_passes_as_no_tests_yet(tmp_path: Path) -> None:
    fake = FakeRunner({"uv run pytest -m perf_smoke": 5})
    code, log, summary = run_one("engine / perf-smoke", tmp_path, fake)
    assert code == 0
    assert "no tests yet" in log
    assert "::warning::not yet confirmed: engine / perf-smoke runs no tests yet" in log
    assert summary.startswith("- not yet confirmed: engine / perf-smoke runs no tests yet")
    assert "pytest collected no tests" in summary


CONFORMANCE = (
    "uv run --package nexusbt-tds pytest tds/tests",
    "uv run python -m nexusbt.testing.synth --preset small --out .scratch/snap --validate",
)


def test_a_step_whose_path_or_module_is_missing_is_shown_but_not_run(tmp_path: Path) -> None:
    fake = FakeRunner()
    code, log, summary = run_one("tds / conformance", tmp_path, fake)
    assert code == 0
    assert fake.ran == []
    assert f"$ {CONFORMANCE[0]}" in log
    assert f"$ {CONFORMANCE[1]}" in log
    assert "tds/tests does not exist yet" in summary
    assert "module nexusbt.testing.synth does not exist yet" in summary


def test_the_step_runs_once_its_path_and_module_exist(tmp_path: Path) -> None:
    (tmp_path / "tds" / "tests").mkdir(parents=True)
    fake = FakeRunner()
    code, _, summary = run_one("tds / conformance", tmp_path, fake, {"nexusbt.testing.synth"})
    assert code == 0
    assert fake.ran == list(CONFORMANCE)
    assert "not yet confirmed" not in summary


def test_a_failing_step_fails_the_check_and_stops_it(tmp_path: Path) -> None:
    (tmp_path / "tds" / "tests").mkdir(parents=True)
    fake = FakeRunner({CONFORMANCE[0]: 1})
    code, _, summary = run_one("tds / conformance", tmp_path, fake, {"nexusbt.testing.synth"})
    assert code == 1
    assert fake.ran == [CONFORMANCE[0]]
    assert summary == f"- fail: tds / conformance, `{CONFORMANCE[0]}` exited 1\n"


def test_exit_5_from_a_command_that_is_not_pytest_is_a_failure(tmp_path: Path) -> None:
    (tmp_path / "tests" / "repo").mkdir(parents=True)
    (tmp_path / "tests" / "repo" / "release_check.py").touch()
    fake = FakeRunner({"uv run python -m tests.repo.release_check": 5})
    code, _, summary = run_one("engine / release", tmp_path, fake)
    assert code == 5
    assert summary.startswith("- fail: engine / release")


def test_the_checks_are_the_spec_table_with_its_commands() -> None:
    """Row `| `<check>` | <content> | `<command>` | <required from> |` of 9.1's second table."""
    spec = Path(__file__).parents[2] / "docs" / "spec" / "engine-spec-v3.4.md"
    rows = [
        [cell.strip().strip("`") for cell in line.split("|")[1:4]]
        for line in spec.read_text().splitlines()
        if re.match(r"\| `(engine|tds) / ", line)
    ]
    table = {name: command for name, _, command in rows}
    assert len(table) == 8
    assert {name: " && ".join(s.command for s in steps) for name, steps in CHECKS.items()} == table
