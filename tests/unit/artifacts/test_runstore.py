"""Spec T1.14a: sealed run folders, seal recovery and captured sources (5.9.1-5.9.3, 2.6)."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import stat
import subprocess
import sys
from contextlib import closing
from pathlib import Path

import pyarrow as pa
import pytest

from nexusbt.artifacts import RunStore, RunTxn

TABLE = pa.table({"instrument_id": ["A", "B"], "value": [1.5, -2.0]})


def row(runs: Path, run_id: str) -> tuple[str, str]:
    """The run's index `status` and `path`."""
    with closing(sqlite3.connect(runs / "index.sqlite")) as db:
        found = db.execute("SELECT status, path FROM runs WHERE run_id = ?", (run_id,)).fetchone()
    return str(found[0]), str(found[1])


def status(runs: Path, run_id: str) -> str:
    return row(runs, run_id)[0]


def begin(runs: Path) -> RunTxn:
    return RunStore(runs).begin("backtest", "mom", None, graph_hash="g1", params={"n": 10})


def test_seal_only_on_success(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    txn = begin(runs)
    txn.write_table("daily", TABLE)
    txn.set_manifest({"clock": "close"})
    record = txn.seal()

    folder = runs / record.run_id
    assert record.path == folder
    assert record.run_id.split("-")[2:4] == ["backtest", "mom"]
    assert {p.name for p in folder.iterdir()} == {"daily.parquet", "manifest.json", "SEALED"}
    manifest = (folder / "manifest.json").read_bytes()
    assert (folder / "SEALED").read_text() == hashlib.sha256(manifest).hexdigest()
    daily = hashlib.sha256((folder / "daily.parquet").read_bytes()).hexdigest()
    assert json.loads(manifest)["outputs"] == {"daily.parquet": {"physical_sha256": daily}}
    write = stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH
    assert all(not p.stat().st_mode & write for p in folder.iterdir())
    assert status(runs, record.run_id) == "sealed"
    txn.abort()  # a late abort does not undo the seal
    assert status(runs, record.run_id) == "sealed"
    with pytest.raises(RuntimeError, match="already sealed"):
        txn.seal()
    with pytest.raises(ValueError, match="folder-name part"):
        RunStore(runs).begin("backtest", "../outside", None)

    failed = begin(runs)  # the same inputs in the same second get `-2`
    failed.write_table("daily", TABLE)
    failed.abort()
    assert [p.name for p in runs.iterdir() if not p.name.startswith("index.")] == [record.run_id]
    assert status(runs, failed.run_id) == "aborted"


def test_failed_seal_leaves_no_folder(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    txn = begin(runs)
    txn.write_table("daily", TABLE)
    txn.set_manifest({"sharpe": float("nan")})  # not JSON: the manifest cannot be written
    with pytest.raises(ValueError, match="JSON"):
        txn.seal()
    assert [p.name for p in runs.iterdir() if not p.name.startswith("index.")] == []
    assert status(runs, txn.run_id) == "aborted"


def test_value_hash_ignores_created_at(tmp_path: Path) -> None:
    sealed = []
    for user in ["a", "b"]:
        txn = begin(tmp_path / "runs")
        txn.write_table("daily", TABLE)
        txn.set_manifest({"clock": "close", "created_by": user})
        record = txn.seal()
        sealed.append((json.loads((record.path / "manifest.json").read_text()), record))
    (first, one), (second, two) = sealed
    assert first["created_at"] != second["created_at"]  # microseconds apart at least
    assert first["outputs"] == second["outputs"]  # the same Parquet bytes: no time in metadata
    assert one.manifest_sha256 != two.manifest_sha256
    assert one.value_sha256 == two.value_sha256


def test_no_pickle_files_written(tmp_path: Path) -> None:
    txn = begin(tmp_path / "runs")
    with pytest.raises(TypeError, match="pyarrow Tables"):
        txn.write_table("daily", {"value": [1.5]})  # a dict would need pickle; refused
    with pytest.raises(ValueError, match="inside the run folder"):
        txn.write_table("../escape", TABLE)
    txn.write_table("scenarios/gross", TABLE)
    folder = txn.seal().path
    files = [p for p in folder.rglob("*") if p.is_file()]
    assert sorted(p.relative_to(folder).as_posix() for p in files) == [
        "SEALED",
        "manifest.json",
        "scenarios/gross.parquet",
    ]
    assert all(not p.read_bytes().startswith(b"\x80") for p in files)  # the pickle opcode PROTO


CHILD = """
import sys
from pathlib import Path
import pyarrow as pa
from nexusbt.artifacts import RunStore, _runstore
_runstore._CRASH_AT = sys.argv[2]
txn = RunStore(Path(sys.argv[1])).begin("backtest", "mom", None)
txn.write_table("daily", pa.table({"x": [1]}))
txn.seal()
"""


def killed_run(runs: Path, boundary: str) -> str:
    """Runs one backtest in a new process that exits at `boundary`; returns its run id."""
    args = [sys.executable, "-c", CHILD, str(runs), boundary]
    done = subprocess.run(args, capture_output=True, text=True, check=False)  # noqa: S603
    assert done.returncode == 70, done.stderr
    with closing(sqlite3.connect(runs / "index.sqlite")) as db:
        return str(db.execute("SELECT run_id FROM runs").fetchone()[0])  # the only run


@pytest.mark.parametrize(
    ("boundary", "expected"),
    [
        ("inserted", "aborted"),  # the index row exists, no temporary folder yet
        ("written", "aborted"),  # a table in `.tmp-<uuid>/`, no manifest yet
        ("manifest", "aborted"),  # manifest written, not yet renamed
        ("renamed", "sealed"),  # renamed; files still writable, no `SEALED`
        ("readonly", "sealed"),  # read-only, no `SEALED`
        ("sealed", "sealed"),  # `SEALED` written, the index still says running
    ],
)
def test_interrupted_seal_recovers(tmp_path: Path, boundary: str, expected: str) -> None:
    runs = tmp_path / "runs"
    run_id = killed_run(runs, boundary)
    assert status(runs, run_id) == "running"

    RunStore(runs)
    folder = runs / run_id
    assert row(runs, run_id) == (expected, str(folder))
    assert not [p for p in runs.iterdir() if p.name.startswith(".tmp-")]
    assert folder.is_dir() == (expected == "sealed")
    if expected == "sealed":
        manifest = (folder / "manifest.json").read_bytes()
        assert (folder / "SEALED").read_text() == hashlib.sha256(manifest).hexdigest()
        assert not os.access(folder / "daily.parquet", os.W_OK)


@pytest.mark.parametrize(
    ("boundary", "changed"),
    [
        ("renamed", "daily.parquet"),  # a table that no longer matches its manifest hash
        ("renamed", "manifest.json"),  # a manifest that is no longer JSON
        ("sealed", "SEALED"),  # a seal that no longer matches the manifest
    ],
)
def test_interrupted_seal_with_changed_content_moves_to_aborted(
    tmp_path: Path, boundary: str, changed: str
) -> None:
    runs = tmp_path / "runs"
    run_id = killed_run(runs, boundary)
    (path := runs / run_id / changed).chmod(0o644)
    path.write_bytes(b"not what the manifest or the seal says")

    RunStore(runs)
    moved = runs / f".aborted-{run_id}"
    assert row(runs, run_id) == ("aborted", str(moved))
    assert not (runs / run_id).exists()
    assert (moved / changed).read_bytes() == b"not what the manifest or the seal says"


def test_open_deletes_a_temporary_folder_with_no_lock(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    (runs / ".tmp-left-behind").mkdir(parents=True)  # its lock file is already gone
    RunStore(runs)
    assert not (runs / ".tmp-left-behind").exists()


def test_open_leaves_a_live_run_alone(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    live = begin(runs)
    live.write_table("daily", TABLE)
    RunStore(runs)  # another open while `live` is still writing
    assert status(runs, live.run_id) == "running"
    assert live.seal().path.is_dir()
    with pytest.raises(RuntimeError, match="already sealed"):
        live.write_table("late", TABLE)


def test_open_right_after_the_index_row_leaves_the_run_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runs = tmp_path / "runs"
    seen: list[str] = []

    def other_open(name: str) -> None:  # another process opens the store at this boundary
        if name == "inserted":
            RunStore(runs)
            seen.append(status(runs, txn_id()))

    def txn_id() -> str:
        with closing(sqlite3.connect(runs / "index.sqlite")) as db:
            return str(db.execute("SELECT run_id FROM runs").fetchone()[0])

    RunStore(runs)
    monkeypatch.setattr("nexusbt.artifacts._runstore._boundary", other_open)
    txn = begin(runs)
    assert seen == ["running"]
    assert txn.seal().path.is_dir()


def test_sources_captured_with_helpers(tmp_path: Path) -> None:
    project, elsewhere = tmp_path / "project", tmp_path / "site-packages"
    imported = [project / "strategy.py", project / "lib" / "helpers.py", elsewhere / "dep.py"]
    for path in imported:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# {path.name}\n", encoding="utf-8")
    (project / "nexusbt.toml").write_text('[data]\nroot = "data"\n', encoding="utf-8")
    (project / "uv.lock").write_text("version = 1\n", encoding="utf-8")

    txn = begin(tmp_path / "runs")
    txn.write_table("daily", TABLE)
    txn.capture_sources(imported, project=project, entry=imported[0])
    folder = txn.seal().path

    assert {"manifest.json", "SEALED", "source"} <= {p.name for p in folder.iterdir()}
    source = folder / "source"
    assert (source / "lib" / "helpers.py").read_text() == "# helpers.py\n"  # path kept
    assert (source / "strategy.py").is_file()
    assert not (source / "dep.py").exists()  # outside the project: not captured
    assert {"nexusbt.toml", "uv.lock"} <= {p.name for p in source.iterdir()}
    assert json.loads((source / "params.json").read_text()) == {"n": 10}
    assert json.loads((source / "git.json").read_text()) == {"head": None, "status": None}
    manifest = json.loads((folder / "manifest.json").read_text())
    assert "source/lib/helpers.py" in manifest["outputs"]  # the seal pins the source too
    assert not os.access(source / "strategy.py", os.W_OK)
    assert manifest["source"] == {"entry": "strategy.py"}
    checkout_lock = Path(__file__).resolve().parents[3] / "uv.lock"  # a source checkout's
    assert (source / "engine-uv.lock").read_bytes() == checkout_lock.read_bytes()


def test_sources_record_git_state(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "strategy.py").write_text("a = 1\n", encoding="utf-8")
    git = ["git", "-C", str(project), "-c", "user.name=t", "-c", "user.email=t@example.com"]
    for args in (["init", "-q"], ["add", "."], ["commit", "-qm", "c"]):
        subprocess.run([*git, *args], check=True)  # noqa: S603
    (project / "strategy.py").write_text("a = 2\n", encoding="utf-8")  # changed, not staged

    txn = begin(tmp_path / "runs")
    txn.capture_sources([], project=project, entry=project / "strategy.py")
    recorded = json.loads((txn.seal().path / "source" / "git.json").read_text())
    assert len(recorded["head"]) == 40
    assert recorded["status"] == " M strategy.py"  # the leading space says "not staged"


def test_an_entry_file_outside_the_project_is_captured(tmp_path: Path) -> None:
    project, scratch = tmp_path / "project", tmp_path / "scratch"
    for folder in (project, scratch):
        folder.mkdir()
    entry = scratch / "my.py"
    entry.write_text("# run me\n", encoding="utf-8")

    txn = begin(tmp_path / "runs")
    txn.capture_sources([entry], project=project, entry=entry)
    folder = txn.seal().path

    assert (folder / "source" / "_entry" / "my.py").read_text() == "# run me\n"
    manifest = json.loads((folder / "manifest.json").read_text())
    assert manifest["source"] == {"entry": "_entry/my.py"}  # the path under `source/`
    assert "source/_entry/my.py" in manifest["outputs"]  # the seal pins it


def test_an_entry_file_inside_the_project_is_captured_though_not_imported(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    (project / "strategies").mkdir(parents=True)
    (project / "strategies" / "mom.py").write_text("# mom\n", encoding="utf-8")

    txn = begin(tmp_path / "runs")
    txn.capture_sources([], project=project, entry=project / "strategies" / "mom.py")
    folder = txn.seal().path

    assert (folder / "source" / "strategies" / "mom.py").read_text() == "# mom\n"
    assert not (folder / "source" / "_entry").exists()
    manifest = json.loads((folder / "manifest.json").read_text())
    assert manifest["source"] == {"entry": "strategies/mom.py"}


def test_a_run_with_no_entry_file_seals_with_a_warning(tmp_path: Path) -> None:
    txn = begin(tmp_path / "runs")
    with pytest.warns(UserWarning, match="no entry file"):
        txn.capture_sources([], project=tmp_path, entry=None)
    folder = txn.seal().path
    assert json.loads((folder / "manifest.json").read_text())["source"] == {"entry": None}


@pytest.mark.parametrize("case", ["missing", "unreadable", "taken"])
def test_an_entry_file_that_cannot_be_captured_fails_the_run(tmp_path: Path, case: str) -> None:
    project, runs, entry = tmp_path / "project", tmp_path / "runs", tmp_path / "my.py"
    (project / "_entry").mkdir(parents=True)
    taken = project / "_entry" / "my.py"  # a project file at the outside entry's path
    taken.write_text("# not the entry\n", encoding="utf-8")
    if case != "missing":
        entry.write_text("# entry\n", encoding="utf-8")
    if case == "unreadable":
        entry.chmod(0)
    txn = begin(runs)
    with pytest.raises(OSError, match=r"my\.py"):
        txn.capture_sources([taken] if case == "taken" else [], project=project, entry=entry)
    assert status(runs, txn.run_id) == "aborted"
    assert list(runs.glob(".tmp-*")) == []


def test_a_run_without_the_engine_lock_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("nexusbt.artifacts._runstore._ENGINE_LOCK", None)  # not a checkout
    monkeypatch.setattr("nexusbt.artifacts._runstore._SHIPPED_LOCK", "resources/missing.lock")
    runs, entry = tmp_path / "runs", tmp_path / "s.py"
    entry.write_text("", encoding="utf-8")
    txn = begin(runs)
    with pytest.raises(FileNotFoundError, match=r"engine uv\.lock"):
        txn.capture_sources([], project=tmp_path, entry=entry)
    assert status(runs, txn.run_id) == "aborted"
    assert list(runs.glob(".tmp-*")) == []


def test_an_installed_engine_captures_the_lock_its_package_ships(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("nexusbt.artifacts._runstore._ENGINE_LOCK", None)  # not a checkout
    shipped = "resources/__init__.py"  # stands in for the wheel's `resources/uv.lock`
    monkeypatch.setattr("nexusbt.artifacts._runstore._SHIPPED_LOCK", shipped)
    entry = tmp_path / "s.py"
    entry.write_text("", encoding="utf-8")
    txn = begin(tmp_path / "runs")
    txn.capture_sources([], project=tmp_path, entry=entry)
    captured = (txn.seal().path / "source" / "engine-uv.lock").read_bytes()
    package = Path(__file__).resolve().parents[3] / "src" / "nexusbt"
    assert captured == (package / shipped).read_bytes()
