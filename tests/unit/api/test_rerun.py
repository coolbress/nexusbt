"""`nx.rerun` (spec 3.8, 2.6, 5.9.3, 5.9.4; T1.15, #250).

A project saves a pipeline run from its entry file in a process of its own, once per module;
each test reruns a copy of that project folder, which starts one more process. Where
`uuid.getnode()` is random per process (#635), the copy's recorded `machine_id` is taken as this
machine's, so only the E31 test compares a real one.
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import stat
import subprocess
import sys
from contextlib import closing
from pathlib import Path
from typing import Any

import pytest

import nexusbt as nx
from nexusbt.artifacts import _environment
from nexusbt.contracts import ReplayError, UntrustedRunError
from nexusbt.testing.synth import make_snapshot

pytestmark = pytest.mark.unit

_ENTRY = """\
import nexusbt as nx
from nexusbt.factors import SMA
from helpers import N
from lib.extra import M
pipe = nx.Pipeline({"close": nx.Price.close.latest * M, "sma": SMA(N)})
nx.run_pipeline(pipe, start="2020-01-06", end="2020-01-10", snapshot="pkg", save=True)
nx.run_pipeline(nx.Pipeline({"c": nx.Price.close.latest}), start="2020-01-06",
                end="2020-01-06", snapshot="pkg", save=True)
"""
_SAME = "outputs identical (value, physical)"
_ROW = "SELECT run_kind, derived_from FROM runs WHERE run_id = ?"
_FILES = {"scripts/helpers.py": "N = 3\n", "src/lib/__init__.py": "", "src/lib/extra.py": "M = 1\n"}


@pytest.fixture(scope="module")
def saved(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A project with a `tiny` snapshot `pkg`, the entry `scripts/m.py`, its sibling helper
    and `lib` of a `src/` layout on `PYTHONPATH`, as an editable install puts it; the entry
    saves two runs, with `python scripts/m.py`."""
    root = tmp_path_factory.mktemp("saved") / "proj"
    make_snapshot(root / "pkg", preset="tiny")
    (root / "nexusbt.toml").write_text('[data]\npins = "index"\n', encoding="utf-8")
    for name, text in {**_FILES, "scripts/m.py": _ENTRY}.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text, encoding="utf-8")
    env = {**os.environ, "PYTHONPATH": str(root / "src")}
    subprocess.run([sys.executable, "scripts/m.py"], cwd=root, env=env, check=True)
    return root


@pytest.fixture
def copied(saved: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, str]:
    """A copy of the project as the working folder, and the id of its run with `sma`."""
    project = shutil.copytree(saved, tmp_path / "proj")
    monkeypatch.chdir(project)
    monkeypatch.setenv("PYTHONPATH", str(project / "src"))
    with closing(sqlite3.connect(project / "runs" / "index.sqlite")) as db:
        (run_id,) = db.execute("SELECT run_id FROM runs WHERE params_json LIKE '%sma%'").fetchone()
    recorded = _manifest(project / "runs" / run_id)["environment"]["machine_id"]
    monkeypatch.setattr(_environment, "machine_id", lambda: recorded)
    return project, run_id


def _manifest(folder: Path) -> dict[str, Any]:
    return dict(json.loads((folder / "manifest.json").read_text(encoding="utf-8")))


def _index_row(project: Path, run_id: str) -> tuple[Any, ...]:
    """The run's 5.9.5 `run_kind` and `derived_from`."""
    with closing(sqlite3.connect(project / "runs" / "index.sqlite")) as db:
        return tuple(db.execute(_ROW, (run_id,)).fetchone())


def test_rerun_identical(copied: tuple[Path, str]) -> None:
    """Done-means: "outputs identical (value, physical)"; the rerun is a new record beside the
    run it reproduces, which is untouched (INV-07), indexed `run_kind = rerun` (5.9.5); the
    entry's other run is saved again as a plain run, not as a rerun of this one."""
    project, run_id = copied
    before = (project / "runs" / run_id / "manifest.json").read_bytes()
    runs = {p.name for p in (project / "runs").iterdir()}
    run = nx.rerun(run_id)
    assert run.comparison == _SAME
    assert run.run_id != run_id
    assert run.path == project / "runs" / str(run.run_id)
    assert (project / "runs" / run_id / "manifest.json").read_bytes() == before
    (other,) = {p.name for p in (project / "runs").iterdir()} - runs - {run.run_id}
    assert _index_row(project, str(run.run_id)) == ("rerun", run_id)
    assert _index_row(project, other) == (None, None)


def test_missing_snapshot_E15(copied: tuple[Path, str]) -> None:  # noqa: N802 - the ticket's name
    project, run_id = copied
    (project / "pkg").rename(project / "pkg-moved")
    with pytest.raises(ReplayError, match="is not available"):
        nx.rerun(run_id)


def test_tampered_parquet_detected(copied: tuple[Path, str]) -> None:
    """A changed Parquet byte: each file's sha256 against tds.json (semantic·physical), E15."""
    project, run_id = copied
    victim = sorted((project / "pkg").rglob("*.parquet"))[0]
    data = bytearray(victim.read_bytes())
    data[len(data) // 2] ^= 0xFF
    victim.write_bytes(bytes(data))
    with pytest.raises(ReplayError, match="semantic·physical mismatch"):
        nx.rerun(run_id)


def test_archived_helpers_override_local(copied: tuple[Path, str]) -> None:
    """5.9.3 (1): the working folder's edited helpers (the entry's sibling, N = 5, and `lib` of
    the `src/` layout, M = 2) do not reach the rerun, which reads the captured ones."""
    project, run_id = copied
    (project / "scripts" / "helpers.py").write_text("N = 5\n", encoding="utf-8")
    (project / "src" / "lib" / "extra.py").write_text("M = 2\n", encoding="utf-8")
    assert nx.rerun(run_id).comparison == _SAME


def test_new_snapshot_is_new_run(copied: tuple[Path, str]) -> None:
    """3.8: `new_snapshot=True` is not a rerun: a new run of the same kind, `derived_from`."""
    project, run_id = copied
    run = nx.rerun(run_id, new_snapshot=True)
    assert run.manifest is not None
    assert run.manifest["kind"] == "pipeline"
    assert _index_row(project, str(run.run_id)) == (None, run_id)


def test_foreign_run_requires_trust_E31(  # noqa: N802 - the ticket's name
    copied: tuple[Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """2.6: a manifest `machine_id` of another machine is E31; `trust=True` runs it. Both
    values are fixed, so the result does not hang on this host's own `machine_id()` (#635);
    an equal one is not refused (here and in every test above)."""
    project, run_id = copied
    manifest = project / "runs" / run_id / "manifest.json"
    manifest.chmod(manifest.stat().st_mode | stat.S_IWUSR)
    found = _manifest(manifest.parent)
    found["environment"]["machine_id"] = "0" * 16
    manifest.write_text(json.dumps(found, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    monkeypatch.setattr(_environment, "machine_id", lambda: "1" * 16)
    with pytest.raises(UntrustedRunError, match="another machine"):
        nx.rerun(run_id)
    assert nx.rerun(run_id, trust=True).comparison == _SAME
