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
from nexusbt.contracts import ReplayError, SnapshotError, UntrustedRunError
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
    """An exact rerun whose recorded snapshot does not open: E15 with 6.6's fix line."""
    project, run_id = copied
    (project / "pkg").rename(project / "pkg-moved")
    with pytest.raises(ReplayError, match="is not available") as raised:
        nx.rerun(run_id)
    assert "nx.rerun(id, new_snapshot=True) creates a new run" in str(raised.value)


def _flip(package: Path) -> None:
    """Flip one byte in the middle of the package's first Parquet file."""
    victim = sorted(package.rglob("*.parquet"))[0]
    data = bytearray(victim.read_bytes())
    data[len(data) // 2] ^= 0xFF
    victim.write_bytes(bytes(data))


def test_tampered_parquet_detected(copied: tuple[Path, str]) -> None:
    """A changed Parquet byte: each file's sha256 against tds.json (semantic·physical), E15."""
    project, run_id = copied
    _flip(project / "pkg")
    with pytest.raises(ReplayError, match="semantic·physical mismatch"):
        nx.rerun(run_id)


@pytest.mark.parametrize("how", ["moved", "a byte flipped"])
def test_new_snapshot_that_does_not_open_is_its_own_E14(  # noqa: N802 - the code's name
    copied: tuple[Path, str], how: str
) -> None:
    """#636 Decisions 1 and 3: `new_snapshot=True` is a new run (3.8), so a snapshot that does
    not open is its own E14, with no line telling the person to pass `new_snapshot=True`; it
    still opens with each file's sha256 (3.11 `[data] verify`), which a flipped byte fails
    under this project's `verify = "manifest"` default."""
    project, run_id = copied
    if how == "moved":
        (project / "pkg").rename(project / "pkg-moved")
    else:
        _flip(project / "pkg")
    with pytest.raises(SnapshotError) as raised:
        nx.rerun(run_id, new_snapshot=True)
    assert "new_snapshot" not in str(raised.value)
    if how != "moved":  # the file's sha256 against tds.json (TDS 11 `TDS-H001`)
        assert "TDS-H001" in str(raised.value)


def test_a_snapshot_whose_latest_names_a_folder_outside_is_E15(  # noqa: N802 - the code's name
    copied: tuple[Path, str],
) -> None:
    """#636 Decisions 2: `pkg` replaced by a folder whose `LATEST` names one outside it (4.2):
    no `tds.json` can be reached to show it is another snapshot, so on an exact rerun it is
    the run's own, E15 (`_has_manifest`'s refusal of that `LATEST`)."""
    project, run_id = copied
    shutil.rmtree(project / "pkg")
    (project / "pkg").mkdir()
    (project / "pkg" / "LATEST").write_text("../elsewhere\n", encoding="utf-8")
    with pytest.raises(ReplayError, match="is not available"):
        nx.rerun(run_id)


def test_an_E14_naming_the_run_s_snapshot_raised_by_the_entry_file_is_E15(  # noqa: N802
    copied: tuple[Path, str],
) -> None:
    """#636 Decisions 2: an E14 the entry file raises outside any opening, whose layer names
    the run's recorded snapshot, is E15 on an exact rerun and stays E14 with `new_snapshot`."""
    project, run_id = copied
    recorded = _manifest(project / "runs" / run_id)["snapshot_id"]
    layer = f"data — snapshot {recorded} / prices / column - / producer -"
    entry = ("from nexusbt.contracts import SnapshotError\n"
             "raise SnapshotError(what='a file is unreadable', where='-', why='-', fix='-',"
             f" more='-', layer='{layer}')\n")  # fmt: skip
    _edit(project / "runs" / run_id / "source" / "scripts" / "m.py", entry)
    with pytest.raises(ReplayError, match=f"snapshot {recorded} is not available"):
        nx.rerun(run_id)
    with pytest.raises(SnapshotError, match="a file is unreadable"):
        nx.rerun(run_id, new_snapshot=True)


def test_a_moved_snapshot_the_entry_file_opens_itself_is_E15(  # noqa: N802 - the code's name
    copied: tuple[Path, str],
) -> None:
    """#636 Decisions 2: the recorded snapshot opened by `nx.open` in the entry file, not by
    `run_pipeline`, and moved: still the run's snapshot, E15 on an exact rerun."""
    project, run_id = copied
    entry = _ENTRY.replace("import nexusbt as nx\n", 'import nexusbt as nx\nnx.open("pkg")\n')
    _edit(project / "runs" / run_id / "source" / "scripts" / "m.py", entry)
    (project / "pkg").rename(project / "pkg-moved")
    with pytest.raises(ReplayError, match="is not available"):
        nx.rerun(run_id)


@pytest.mark.parametrize("new_snapshot", [False, True])
def test_an_error_about_another_snapshot_keeps_its_E14(  # noqa: N802 - the code's name
    copied: tuple[Path, str], new_snapshot: bool
) -> None:
    """#636 Decisions 2: the entry file opens `other`, a package of its own id that does not
    open; its E14 is not the run's snapshot being unavailable, in either mode."""
    project, run_id = copied
    make_snapshot(project / "other", preset="tiny", snapshot_id="other-0001")
    _flip(project / "other")
    entry = _ENTRY.replace('snapshot="pkg", save=True)\nnx', 'snapshot="other", save=True)\nnx')
    _edit(project / "runs" / run_id / "source" / "scripts" / "m.py", entry)
    with pytest.raises(SnapshotError, match="snapshot check failed") as raised:
        nx.rerun(run_id, new_snapshot=new_snapshot)
    assert "snapshot other-0001" in str(raised.value)
    assert "new_snapshot" not in str(raised.value)


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


def test_a_manifest_without_the_data_block_reruns(copied: tuple[Path, str]) -> None:
    """#687 Decisions: a run saved before `data` and `assumptions` is "not recorded", never
    "no fallback": nothing reads the missing keys, the rerun gives its comparison line, and
    the new run records the block, `data.fallbacks = []` on this package."""
    project, run_id = copied
    found = _manifest(project / "runs" / run_id)
    assert found["data"]["fallbacks"] == []
    del found["data"], found["assumptions"]
    _edit(project / "runs" / run_id / "manifest.json",
          json.dumps(found, sort_keys=True, indent=2) + "\n")  # fmt: skip
    run = nx.rerun(run_id)
    assert run.comparison == _SAME
    assert run.manifest is not None
    assert run.manifest["data"]["fallbacks"] == []


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


@pytest.mark.parametrize(("file", "text", "said"), [
    ("helpers.py", "SCALE = 2\n", "mylib.helpers changed since run"),
    ("helpers.py", "SCALE = 1 / 0\n", "mylib.helpers changed since run"),  # raises on import
    ("__init__.py", None, "mylib is missing since run"),  # `mylib` resolves, to no file
    ("helpers.py", None, "mylib.helpers cannot be found by its name"),
])  # fmt: skip
def test_a_changed_or_missing_outside_helper_is_refused(
    outside: tuple[Path, Path, str], tmp_path: Path, file: str, text: str | None, said: str
) -> None:
    """E15 naming the module, with no absolute path or home folder (#250 Decisions). A name
    that resolves to no file is "missing"; a name no finder resolves cannot be found by it,
    with nothing to restore (#644 Decisions 2)."""
    ext, _, run_id = outside
    helper = ext / "mylib" / file
    if text is None:
        helper.unlink()
    else:
        helper.write_text(text, encoding="utf-8")
    with pytest.raises(ReplayError) as refused:
        nx.rerun(run_id)
    text = str(refused.value)
    assert f"helper module {said}" in text
    assert ("restore" in text) is ("cannot be found" not in text)
    assert str(tmp_path.parent) not in text
    assert str(Path.home()) not in text


_LOADED = """\
import importlib.util
import sys
import nexusbt as nx
spec = importlib.util.spec_from_file_location("cfg", "../elsewhere/cfg.py")
cfg = sys.modules["cfg"] = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cfg)
"""
_ALIAS = """\
import sys
import nexusbt as nx
import mylib.helpers
sys.modules["alias"] = mylib.helpers
"""
_BESIDE = "import nexusbt as nx\nimport side\n"
_RUN = """\
nx.run_pipeline(nx.Pipeline({"c": nx.Price.close.latest}), start="2020-01-06",
                end="2020-01-06", snapshot="pkg", save=True)
"""


def test_an_entry_outside_the_project_that_imports_multiprocessing_reruns(
    outside: tuple[Path, Path, str],
) -> None:
    """#644 Decisions (2026-11-27, A): `import multiprocessing` names the entry module
    `__mp_main__` too. An entry outside the project folder is kept in `source/_entry/`, so
    that name is not recorded as an outside module, and the unchanged run reruns. A run saved
    before the fix records it; it is skipped when read, and that run reruns too."""
    _, project, first = outside
    elsewhere = project.parent / "elsewhere"
    elsewhere.mkdir()
    entry = "import multiprocessing\nimport nexusbt as nx\n" + _RUN
    (elsewhere / "m2.py").write_text(entry, encoding="utf-8")
    subprocess.run([sys.executable, "../elsewhere/m2.py"], check=True)
    sealed = {p.name for p in (project / "runs").iterdir() if (p / "SEALED").is_file()}
    (run_id,) = sealed - {first}
    folder = project / "runs" / run_id
    assert _manifest(folder)["source"]["outside"] == {}
    assert nx.rerun(run_id, trust=True).comparison == _SAME  # `machine_id`: the first run's
    found = _manifest(folder)  # as a run saved before the fix records it
    found["source"]["outside"] = {"__mp_main__": hashlib.sha256(entry.encode()).hexdigest()}
    _edit(folder / "manifest.json", json.dumps(found, sort_keys=True, indent=2) + "\n")
    assert nx.rerun(run_id, trust=True).comparison == _SAME


@pytest.mark.parametrize(("beside", "text", "name", "recorded"), [
    (False, _LOADED, "cfg", ["cfg"]),  # loaded from a file path under a name
    (False, _ALIAS, "alias", ["alias", "mylib", "mylib.helpers"]),  # another name in sys.modules
    (True, _BESIDE, "side", ["side"]),  # beside an entry outside the project folder
])  # fmt: skip
def test_an_unchanged_outside_helper_not_found_by_its_name_is_refused_as_such(
    outside: tuple[Path, Path, str], beside: bool, text: str, name: str, recorded: list[str]
) -> None:
    """#644 Decisions 1: nothing changed, but the recorded name resolves to nothing in the new
    process, so the code is not shown to be the same: E15 saying it cannot be found by its
    name, not that it is missing and must be restored. The run records only the modules the
    entry imported from outside the project folder, so the refusal is about `name`."""
    _, project, first = outside
    elsewhere = project.parent / "elsewhere"
    elsewhere.mkdir()
    if name in ("cfg", "side"):
        (elsewhere / f"{name}.py").write_text("SCALE = 1\n", encoding="utf-8")
    ((elsewhere if beside else project) / "m2.py").write_text(text + _RUN, encoding="utf-8")
    if beside:  # run from the project folder, as `python ../elsewhere/m2.py`
        subprocess.run([sys.executable, "../elsewhere/m2.py"], check=True)
    else:
        subprocess.run([sys.executable, "m2.py"], check=True)
    sealed = {p.name for p in (project / "runs").iterdir() if (p / "SEALED").is_file()}
    (run_id,) = sealed - {first}
    assert sorted(_manifest(project / "runs" / run_id)["source"]["outside"]) == recorded
    with pytest.raises(ReplayError) as refused:
        nx.rerun(run_id, trust=True)  # this process's `machine_id` is the first run's (#635)
    said = str(refused.value)
    assert f"helper module {name} cannot be found by its name from the rerun's process" in said
    assert f"make {name} importable by its name" in said
    assert "is missing" not in said
    assert "restore" not in said


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


#: #637 Decisions: L1-a's tolerance (8.1), the one a run without NAV is compared within when
#: the environment differs.
L1_A_ABS = L1_A_REL = 1e-9
_WITHIN = f"environment differs; outputs within tolerance (|a{chr(0x2212)}b| ≤ 1e-9 + 1e-9·|b|)"
_BEYOND = "environment differs; outputs differ beyond tolerance: pipeline.parquet"


def _nudge(folder: Path, times: float) -> None:
    """Move the run's first `close` by `times` L1-a's tolerance for it, as a run sealed in
    another environment would hold it: the file and its recorded physical hash."""
    table = pq.read_table(folder / "pipeline.parquet")
    close = table["close"].to_pylist()
    close[0] += times * (L1_A_ABS + L1_A_REL * abs(close[0]))
    table = table.set_column(table.schema.get_field_index("close"), "close", pa.array(close))
    pq.write_table(table, _edit(folder / "pipeline.parquet"))
    found = _manifest(folder)
    digest = hashlib.sha256((folder / "pipeline.parquet").read_bytes()).hexdigest()
    found["outputs"]["pipeline.parquet"]["physical_sha256"] = digest
    _edit(folder / "manifest.json", json.dumps(found, sort_keys=True, indent=2) + "\n")


def _another_lock(folder: Path) -> None:
    """The run's captured engine `uv.lock` as another environment's (#637 Decisions 1)."""
    lock = folder / "source" / "engine-uv.lock"
    _edit(lock, lock.read_text(encoding="utf-8") + "# another environment\n")


def test_the_tolerance_is_l1_a(copied: tuple[Path, str]) -> None:
    """#637 Decisions 2: the tolerance used is 8.1's L1-a, 1e-9 absolute and relative."""
    from nexusbt.api import _rerun

    assert (_rerun.ABS_TOL, _rerun.REL_TOL) == (L1_A_ABS, L1_A_REL)


@pytest.mark.parametrize(("times", "line", "code"), [
    (0.5, _WITHIN, 0),  # half the tolerance: within, though the bytes differ
    (2.0, _BEYOND, 4),  # twice the tolerance: beyond it
])  # fmt: skip
def test_another_engine_lock_compares_within_l1_a(
    copied: tuple[Path, str], capsys: pytest.CaptureFixture[str], times: float, line: str,
    code: int,
) -> None:  # fmt: skip
    """#637 Decisions: a captured engine lock that is not the current one says "environment
    differs" and compares the values within L1-a's tolerance, not the bytes; the CLI exits
    0 within it and 4 beyond it."""
    project, run_id = copied
    folder = project / "runs" / run_id
    _another_lock(folder)
    _nudge(folder, times)
    assert main(["rerun", run_id]) == code
    assert capsys.readouterr().out.splitlines()[1] == line


_NAN, _INF = float("nan"), float("inf")
_F64 = pa.float64()


def _table(values: list[Any], kind: pa.DataType | None = _F64) -> pa.Table:
    """Keys 0, 1, … and one column `v` of `values`, as `kind` (inferred when `None`)."""
    return pa.table({"k": list(range(len(values))), "v": pa.array(values, type=kind)})


@pytest.mark.parametrize(("old", "new", "beyond"), [
    (_table([1.0, _NAN, None, _INF]), _table([1.0, _NAN, None, _INF]), False),  # each its own
    (_table([1.0]), _table([1.0 + 0.5 * (L1_A_ABS + L1_A_REL)]), False),
    (_table([_NAN]), _table([None]), True),  # a null is not a NaN, in a float64 column
    (_table([1.0, None]), _table([None, 1.0]), True),  # the nulls in other cells
    (_table([_INF]), _table([-_INF]), True),
    (_table([1.0]), _table([_INF]), True),  # the tolerance of an infinite `b` is no tolerance
    (_table([1.0]), _table([1], None), True),  # float64 against int64, though the same value
    (_table([1], None), _table([2], None), True),  # not a float: exactly, no tolerance
    (_table([1.0]), pa.table({"k": [1], "v": [1.0]}), True),  # another key
    (_table([1.0]), _table([1.0, 1.0]), True),  # another number of rows
])  # fmt: skip
def test_cells_within_l1_a(old: pa.Table, new: pa.Table, beyond: bool) -> None:
    """#637 Decisions 2: cell by cell on the same keys, NaN agreeing with NaN; a null only
    with a null in the same cell, an infinity only with itself, a column only with one of its
    own type, a key or a cell that is not a float only with an equal one."""
    from nexusbt.api import _rerun

    assert _rerun._beyond(old, new, ["k"]) is beyond


def _outputs(folder: Path, tables: dict[str, pa.Table], value: str | None = "v1") -> Path:
    """A run folder holding `tables` and a manifest naming each with its file's sha256 and
    the value hash `value` (none recorded when `None`)."""
    folder.mkdir()
    outputs: dict[str, dict[str, str]] = {}
    for name, table in tables.items():
        pq.write_table(table, folder / name)
        digest = hashlib.sha256((folder / name).read_bytes()).hexdigest()
        outputs[name] = {"physical_sha256": digest}
        if value is not None:
            outputs[name]["value_sha256"] = value
    (folder / "manifest.json").write_text(json.dumps({"outputs": outputs}), encoding="utf-8")
    return folder


def test_a_reproduced_table_that_no_longer_matches_its_record_is_beyond(tmp_path: Path) -> None:
    """#637: the reproduced run's file, rewritten after it was sealed, is not compared as if
    it were the run's: its sha256 is not the recorded one, so it is not within."""
    from nexusbt.api import _rerun

    old = _outputs(tmp_path / "old", {"pipeline.parquet": _table([1.0])})
    new = _outputs(tmp_path / "new", {"pipeline.parquet": _table([2.0])})
    pq.write_table(_table([2.0]), old / "pipeline.parquet")  # the same values as the new run
    assert _rerun.within(old, new) == _BEYOND


def test_a_table_the_new_run_lacks_is_beyond_tolerance(tmp_path: Path) -> None:
    """#637: a table of the reproduced run that the new run did not write is not within."""
    from nexusbt.api import _rerun

    old = _outputs(tmp_path / "old", {"pipeline.parquet": _table([1.0])})
    new = _outputs(tmp_path / "new", {})
    assert _rerun.within(old, new) == _BEYOND


_EXTRA = "environment differs; outputs differ beyond tolerance: extra.parquet"


@pytest.mark.parametrize(("value", "cells", "line"), [
    ("v1", [1.0], _WITHIN),
    ("v2", [1.0], _EXTRA),  # the cells are the same; only the recorded value hash moves
    (None, [1.0], _WITHIN),  # no value hash recorded: its bytes, which are the same
    (None, [1.0 + 1e-12], _EXTRA),  # within L1-a, but bytes are compared exactly
])  # fmt: skip
def test_a_table_of_no_known_key_is_compared_by_its_hash(
    tmp_path: Path, value: str | None, cells: list[float], line: str
) -> None:
    """#637: a table whose key the comparison does not know is compared exactly, by its value
    hash, or by its bytes when no value hash is recorded; never within the tolerance."""
    from nexusbt.api import _rerun

    recorded = None if value is None else "v1"
    old = _outputs(tmp_path / "old", {"extra.parquet": _table([1.0])}, recorded)
    new = _outputs(tmp_path / "new", {"extra.parquet": _table(cells)}, value)
    assert _rerun.within(old, new) == line


def test_a_project_lock_on_one_side_only_is_another_environment(
    copied: tuple[Path, str],
) -> None:
    """#637 Decisions 1: the run kept no project `uv.lock`; the working folder has one now."""
    project, run_id = copied
    assert not (project / "runs" / run_id / "source" / "uv.lock").exists()
    (project / "uv.lock").write_text("version = 1\n", encoding="utf-8")
    assert nx.rerun(run_id).comparison == _WITHIN


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
