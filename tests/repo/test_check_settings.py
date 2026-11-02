"""The check settings of spec 2.5 and 9.1, read where the tools read them.

ruff's `banned-api` table refuses the 2.5 list under `src/**` and leaves the
test trees to the AST test; pytest carries 9.1's nine markers, its default
deselection and the hypothesis `ci` profile, with `deep` registered beside it.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from hypothesis import settings

ROOT = Path(__file__).resolve().parents[2]
MARKERS = {"unit", "golden", "property", "docs", "examples", "parity", "perf_smoke", "slow", "repo"}
RUFF = "ruff check --no-cache --select=TID251 --output-format=concise"
#: Each is one 2.5 ban: an imported module, an import from one, and the one banned call.
SOURCES = ["import pickle\n", "from joblib import dump\n", "import pandas\npandas.read_pickle(p)\n"]


def banned_hits(filename: str, source: str) -> str:
    """ruff's TID251 lines for `source` as if it were `filename`, with this repository's config."""
    done = subprocess.run(  # noqa: S603
        [sys.executable, "-m", *RUFF.split(), f"--stdin-filename={filename}", "-"],
        input=source,
        capture_output=True,
        text=True,
        check=False,
        cwd=ROOT,
    )
    return done.stdout


@pytest.mark.parametrize("source", SOURCES)
def test_ruff_bans_the_2_5_list_under_src(source: str) -> None:
    assert "TID251" in banned_hits("src/nexusbt/data/_probe.py", source)
    assert "TID251" in banned_hits("tds/src/nexusbt_tds/_probe.py", source)
    for elsewhere in ("tests/unit/_probe.py", "tds/tests/_probe.py", "conftest.py", "bench/x.py"):
        assert "TID251" not in banned_hits(elsewhere, source), elsewhere


def test_pytest_has_the_nine_markers(pytestconfig: pytest.Config) -> None:
    lines = pytestconfig.getini("markers")  # pytest's own (`xfail`, ...) come with them
    assert {line.split(":", 1)[0] for line in lines} >= MARKERS


def test_default_run_deselects_the_job_markers(pytestconfig: pytest.Config) -> None:
    addopts = pytestconfig.getini("addopts")
    assert "not parity and not perf_smoke and not examples and not slow" in addopts
    assert "--hypothesis-profile=ci" in addopts


def test_hypothesis_profiles_ci_and_deep() -> None:
    ci, deep = settings.get_profile("ci"), settings.get_profile("deep")
    for profile in (ci, deep):  # hypothesis's own `ci`, not replaced, and `deep` built on it
        assert profile.derandomize
        assert profile.deadline is None
    assert deep.max_examples == 500
