"""`nx.rerun` (spec 3.8, 2.6, 5.9.3, 5.9.4; T1.15, #250).

A project saves a pipeline run from its entry file in a process of its own, once per module;
each test reruns a copy of that project folder, which starts one more process. Where
`uuid.getnode()` is random per process (#635), the copy's recorded `machine_id` is taken as this
machine's, so only the E31 test compares a real one.
"""

from __future__ import annotations

import hashlib
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

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

import nexusbt as nx
from nexusbt.artifacts import _environment
from nexusbt.cli.main import main
from nexusbt.contracts import ReplayError, UntrustedRunError
from nexusbt.data import table_value_hash
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
    assert _manifest(project / "runs" / run_id)["source"]["outside"] == {}  # 5.9.2: none


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


def _edit(path: Path, text: str | None = None) -> Path:
    """Make a sealed run's file writable (a read-only seal, 5.9.1); write `text` if given."""
    path.chmod(path.stat().st_mode | stat.S_IWUSR)
    if text is not None:
        path.write_text(text, encoding="utf-8")
    return path


def test_a_snapshot_with_another_semantic_hash_is_refused(copied: tuple[Path, str]) -> None:
    """3.8: the snapshot is confirmed by the semantic hash. `pkg` replaced by a package that
    opens and passes its own sha256s but holds other data (a split injected) is E15."""
    project, run_id = copied
    shutil.rmtree(project / "pkg")
    split = {"dataset": "corporate_actions", "kind": "split", "instrument_id": "KR:T00001",
             "ex_date": "2020-01-08", "ratio_new_per_old": 2.0}  # fmt: skip
    make_snapshot(project / "pkg", preset="tiny", events=[split])
    with pytest.raises(ReplayError, match="it has another semantic hash"):
        nx.rerun(run_id)


@pytest.mark.parametrize(("changed", "line"), [
    (True, "outputs differ: pipeline.parquet (value, physical)"),
    (False, "outputs differ: pipeline.parquet (physical)"),
])  # fmt: skip
def test_outputs_that_differ_are_named_with_the_hash_that_differs(
    copied: tuple[Path, str], changed: bool, line: str
) -> None:
    """5.9.4: the reproduced run's `pipeline.parquet` is rewritten as another run would have
    written it, its recorded hashes with it: one value changed (both hashes differ), or the
    same values with another compression (only the bytes differ)."""
    project, run_id = copied
    _another_table(project / "runs" / run_id, changed=changed)
    assert nx.rerun(run_id).comparison == line


def _another_table(folder: Path, *, changed: bool, drop: str | None = None) -> None:
    """Rewrite the run's `pipeline.parquet` and its recorded hashes, as another run would have
    written them: one `sma` value changed, or the same values with another compression.
    `drop` removes that key of the manifest's `source` too (an older engine's manifest)."""
    table = pq.read_table(folder / "pipeline.parquet")
    if changed:
        sma = table["sma"].to_pylist()
        table = table.set_column(table.schema.get_field_index("sma"), "sma",
                                 pa.array([sma[0] + 1.0, *sma[1:]]))  # fmt: skip
    pq.write_table(table, _edit(folder / "pipeline.parquet"), compression="snappy")
    found = _manifest(folder)
    found["outputs"]["pipeline.parquet"] = {
        "physical_sha256": hashlib.sha256((folder / "pipeline.parquet").read_bytes()).hexdigest(),
        "value_sha256": table_value_hash(table, ("session_date", "market", "instrument_id")),
    }
    if drop is not None:
        found["source"].pop(drop)
    _edit(folder / "manifest.json", json.dumps(found, sort_keys=True, indent=2) + "\n")


def test_an_id_that_is_no_sealed_run_is_refused(copied: tuple[Path, str]) -> None:
    with pytest.raises(ReplayError, match="run nope is not a sealed run folder"):
        nx.rerun("nope")
    project, run_id = copied  # a sealed run reached through a path, not a run id
    with pytest.raises(ReplayError, match="is not a sealed run folder"):
        nx.rerun(f"../{project.name}/runs/{run_id}")


def test_a_run_whose_entry_file_is_gone_is_refused(copied: tuple[Path, str]) -> None:
    """E15 (6.6: a rerun dependency, here the source, is missing), before any process starts."""
    project, run_id = copied
    (project / "runs" / run_id / "source" / "scripts" / "m.py").unlink()
    with pytest.raises(ReplayError, match=f"run {run_id} kept no entry file in source/"):
        nx.rerun(run_id)


@pytest.mark.parametrize(("entry", "message"), [
    ("raise SystemExit(3)\n", "the new process ended 3"),
    ("print('saves nothing')\n", "it sealed no pipeline run"),
])  # fmt: skip
def test_an_entry_file_that_stops_or_saves_nothing_is_said(
    copied: tuple[Path, str], entry: str, message: str
) -> None:
    """The captured entry file stops before it saves, or saves no run of the reproduced run's
    kind: the caller is told so, and nothing is compared."""
    project, run_id = copied
    _edit(project / "runs" / run_id / "source" / "scripts" / "m.py", entry)
    with pytest.raises(RuntimeError, match=f"rerun of {run_id}: {message}"):
        nx.rerun(run_id)


def test_a_manifest_without_outside_is_not_recorded_and_runs(copied: tuple[Path, str]) -> None:
    """#250 Decisions: a run saved before `source.outside` is read as "not recorded", not as
    `{}`: it runs, and when its outputs differ the line says the helpers were not recorded."""
    project, run_id = copied
    _another_table(project / "runs" / run_id, changed=True, drop="outside")
    assert nx.rerun(run_id).comparison == (
        "outputs differ: pipeline.parquet (value, physical); "
        "this run's outside helpers were not recorded"
    )


_OUTSIDE = """\
import nexusbt as nx
import mylib.helpers
nx.run_pipeline(nx.Pipeline({"c": nx.Price.close.latest}), start="2020-01-06",
                end="2020-01-06", snapshot="pkg", save=True)
"""


@pytest.fixture(scope="module")
def saved_outside(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A project whose entry imports `mylib.helpers` from `ext/`, outside the project folder
    and on `PYTHONPATH`, as an editable install of another package puts it (#577)."""
    base = tmp_path_factory.mktemp("outside")
    (base / "ext" / "mylib").mkdir(parents=True)
    (base / "ext" / "mylib" / "__init__.py").write_text("from . import helpers\n", encoding="utf-8")
    (base / "ext" / "mylib" / "helpers.py").write_text("SCALE = 1\n", encoding="utf-8")
    make_snapshot(base / "proj" / "pkg", preset="tiny")
    (base / "proj" / "nexusbt.toml").write_text('[data]\npins = "index"\n', encoding="utf-8")
    (base / "proj" / "m.py").write_text(_OUTSIDE, encoding="utf-8")
    env = {**os.environ, "PYTHONPATH": str(base / "ext")}
    subprocess.run([sys.executable, "m.py"], cwd=base / "proj", env=env, check=True)
    return base


@pytest.fixture
def outside(
    saved_outside: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, Path, str]:
    """Copies of `ext/` and the project, the working folder the project, and the run's id."""
    ext = shutil.copytree(saved_outside / "ext", tmp_path / "ext")
    project = shutil.copytree(saved_outside / "proj", tmp_path / "proj")
    monkeypatch.chdir(project)
    monkeypatch.setenv("PYTHONPATH", str(ext))
    (run_id,) = [p.name for p in (project / "runs").iterdir() if (p / "SEALED").is_file()]
    recorded = _manifest(project / "runs" / run_id)["environment"]["machine_id"]
    monkeypatch.setattr(_environment, "machine_id", lambda: recorded)
    return ext, project, run_id


def test_an_outside_helper_is_recorded_by_name_and_reruns(
    outside: tuple[Path, Path, str], tmp_path: Path
) -> None:
    """5.9.2 `source.outside`: each module's name and its file's sha256, not its file; the
    manifest names no absolute path or home folder (5.9.3 "No local path")."""
    ext, project, run_id = outside
    folder = project / "runs" / run_id
    recorded = _manifest(folder)["source"]["outside"]
    assert recorded == {n: hashlib.sha256((ext / f).read_bytes()).hexdigest()
                        for n, f in [("mylib", "mylib/__init__.py"),
                                     ("mylib.helpers", "mylib/helpers.py")]}  # fmt: skip
    assert not (folder / "source" / "mylib").exists()
    text = (folder / "manifest.json").read_text(encoding="utf-8")
    assert str(tmp_path.parent) not in text
    assert str(Path.home()) not in text
    assert nx.rerun(run_id).comparison == _SAME


@pytest.mark.parametrize(("text", "how"), [
    ("SCALE = 2\n", "changed"),
    ("SCALE = 1 / 0\n", "changed"),  # raises when `mylib` imports it during the check
    (None, "is missing"),
])  # fmt: skip
def test_a_changed_or_missing_outside_helper_is_refused(
    outside: tuple[Path, Path, str], tmp_path: Path, text: str | None, how: str
) -> None:
    """E15 naming the module, with no absolute path or home folder (#250 Decisions)."""
    ext, _, run_id = outside
    helper = ext / "mylib" / "helpers.py"
    if text is None:
        helper.unlink()
    else:
        helper.write_text(text, encoding="utf-8")
    with pytest.raises(ReplayError) as refused:
        nx.rerun(run_id)
    text = str(refused.value)
    assert f"helper module mylib.helpers {how} since run {run_id}" in text
    assert str(tmp_path.parent) not in text
    assert str(Path.home()) not in text


def test_the_cli_prints_the_comparison(
    copied: tuple[Path, str], capsys: pytest.CaptureFixture[str]
) -> None:
    """Done-means: `nexusbt rerun <id>` gives "outputs identical (value, physical)" (3.10)."""
    _, run_id = copied
    assert main(["rerun", run_id]) == 0
    first, line = capsys.readouterr().out.splitlines()
    assert first.startswith("run ")
    assert first.endswith(f" from {run_id}")
    assert line == _SAME


def test_the_cli_refuses_a_foreign_run_until_trust(
    copied: tuple[Path, str], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """3.10: another machine's run is E31 without `--trust` (a user error, exit code 1);
    `--trust --new-snapshot` runs it as a new run with `derived_from` (3.8)."""
    project, run_id = copied
    manifest = _edit(project / "runs" / run_id / "manifest.json")
    found = _manifest(manifest.parent)
    found["environment"]["machine_id"] = "0" * 16
    manifest.write_text(json.dumps(found, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    monkeypatch.setattr(_environment, "machine_id", lambda: "1" * 16)
    assert main(["rerun", run_id]) == 1
    assert "UntrustedRunError [E31]" in capsys.readouterr().err
    assert main(["rerun", run_id, "--trust", "--new-snapshot"]) == 0
    new_id = capsys.readouterr().out.split()[1]
    assert _index_row(project, new_id) == (None, run_id)


@pytest.mark.parametrize("changed", [True, False])
def test_the_cli_exits_4_when_the_outputs_differ(
    copied: tuple[Path, str], capsys: pytest.CaptureFixture[str], changed: bool
) -> None:
    """3.10 (#655 Decisions): the exit code follows the comparison line, 4 when it starts
    `outputs differ` (both hashes, or the bytes only); the two lines are as before."""
    project, run_id = copied
    _another_table(project / "runs" / run_id, changed=changed)
    assert main(["rerun", run_id]) == 4
    first, line = capsys.readouterr().out.splitlines()
    assert first.endswith(f" from {run_id}")
    assert line.startswith("outputs differ: pipeline.parquet")


def test_the_cli_new_snapshot_exits_0_when_the_outputs_differ(
    copied: tuple[Path, str], capsys: pytest.CaptureFixture[str]
) -> None:
    """3.10 (#655 Decisions): `--new-snapshot` is a new run (3.8), and a difference is what it
    is run to see: exit code 0 whatever its comparison line says."""
    project, run_id = copied
    _another_table(project / "runs" / run_id, changed=True)
    assert main(["rerun", run_id, "--new-snapshot"]) == 0
    assert capsys.readouterr().out.splitlines()[1].startswith("outputs differ: ")


def test_the_cli_missing_snapshot_is_still_exit_code_1(
    copied: tuple[Path, str], capsys: pytest.CaptureFixture[str]
) -> None:
    """E15 stays a user error, exit code 1 (3.10), not the comparison's code 4."""
    project, run_id = copied
    (project / "pkg").rename(project / "pkg-moved")
    assert main(["rerun", run_id]) == 1
    assert "ReplayError [E15]" in capsys.readouterr().err


def test_the_cli_save_detail_is_not_built_yet(copied: tuple[Path, str]) -> None:
    """5.9.4's tier-(3) outputs: no run kind writes `detail/` yet."""
    with pytest.raises(NotImplementedError, match="--save-detail"):
        main(["rerun", copied[1], "--save-detail"])
