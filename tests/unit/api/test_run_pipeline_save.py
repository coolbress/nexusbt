"""`nx.run_pipeline(..., save=True)` (spec 3.5; 3.8's `kind="pipeline"` row, 5.9.1, 5.9.3; #249
Decisions 2026-11-19): the sealed run, its tables, and the entry file the run started from
(#283, #304)."""

from __future__ import annotations

import hashlib
import importlib
import json
import math
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

import pyarrow.parquet as pq
import pytest

import nexusbt as nx
from nexusbt.artifacts import RunTxn
from nexusbt.factors import SMA
from nexusbt.testing.synth import make_snapshot
from nexusbt_tds.hash import encode_table

pytestmark = pytest.mark.unit


@pytest.fixture(scope="module")
def tiny(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return make_snapshot(tmp_path_factory.mktemp("tiny") / "pkg", preset="tiny")


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A project folder whose `m.py` is the run's entry file. Its `nexusbt.toml` pins in the
    index only: `tiny` has no data root, and the root pin's E30 is #157's, not this test's."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "nexusbt.toml").write_text('[data]\npins = "index"\n', encoding="utf-8")
    (tmp_path / "m.py").write_text("# the entry file\n", encoding="utf-8")
    monkeypatch.setattr(sys.modules["__main__"], "__file__", str(tmp_path / "m.py"), raising=False)
    return tmp_path


def test_save_seals_a_pipeline_run(tiny: Path, project: Path) -> None:
    """The sealed run is `kind="pipeline"`, named after the entry file; its `pipeline.parquet`
    and `term_diagnostics.parquet` are the result's tables; `source.entry` is the entry file,
    relative (5.9.3), and the entry file is in `source/`."""
    pipe = nx.Pipeline({"close": nx.Price.close.latest, "inv": 1 / (SMA(3) - SMA(3))})
    result = nx.run_pipeline(pipe, start="2020-01-06", end="2020-01-08", snapshot=str(tiny),
                             save=True)  # fmt: skip
    assert result.run_id is not None
    assert result.run_id.split("-")[2:4] == ["pipeline", "m"]
    folder = project / "runs" / result.run_id
    assert (folder / "SEALED").is_file()
    saved = pq.read_table(folder / "pipeline.parquet")
    assert saved.schema == result.table.schema
    assert saved.drop_columns(["inv"]).equals(result.table.drop_columns(["inv"]))
    assert all(math.isnan(v) for v in saved["inv"].to_pylist())  # x/0: NaN, never inf (5.4.1)
    assert pq.read_table(folder / "term_diagnostics.parquet").equals(result.term_diagnostics)
    assert result.term_diagnostics.num_rows  # x/0 in every cell: the file holds counts
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["source"]["entry"] == "m.py"  # `outside` holds this test's own modules
    assert (folder / "source" / "m.py").read_text(encoding="utf-8") == "# the entry file\n"
    assert manifest["kind"] == "pipeline"
    assert manifest["snapshot_semantic_hash"] == nx.open(tiny).semantic_hash


def test_outputs_record_the_value_hash_of_each_table(tiny: Path, project: Path) -> None:
    """5.9.2 `outputs{file: {physical_sha256, value_sha256}}` (#250 Decisions, 2026-11-20): each
    table's recorded value hash is TDS 4.5's hash of the table in the file, rows in 3.5's and
    5.4.1's sort order; a captured source file has a physical hash only."""
    pipe = nx.Pipeline({"close": nx.Price.close.latest, "inv": 1 / (SMA(3) - SMA(3))})
    result = nx.run_pipeline(pipe, start="2020-01-06", end="2020-01-08", snapshot=str(tiny),
                             save=True)  # fmt: skip
    folder = project / "runs" / str(result.run_id)
    outputs = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))["outputs"]
    tags = {
        "pipeline": [("market", "string"), ("session_date", "date"), ("decision_ts", "ts_us"),
                     ("instrument_id", "string"), ("close", "f64"), ("inv", "f64")],
        "term_diagnostics": [("market", "string"), ("session_date", "date"), ("term", "string"),
                             ("diagnostic", "string"), ("n", "i64")],
    }  # fmt: skip
    keys = {"pipeline": ("session_date", "market", "instrument_id"),
            "term_diagnostics": ("session_date", "market", "term", "diagnostic")}  # fmt: skip
    for name, columns in tags.items():
        table = pq.read_table(folder / f"{name}.parquet")
        expected = hashlib.sha256(encode_table(table, columns, keys[name])).hexdigest()
        assert outputs[f"{name}.parquet"]["value_sha256"] == expected
    assert outputs["source/m.py"].keys() == {"physical_sha256"}


def test_the_root_pin_goes_beside_the_snapshot_opened(
    tmp_path: Path, project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """4.2, R3-17: a `Snapshot` opened from data root B is pinned under B's `PINS/`, not under
    the root `[data] path` names (A), and the run says `retention: managed` for B's pin."""
    roots = {}
    for name in ("a", "b"):
        roots[name] = tmp_path / f"root_{name}"
        make_snapshot(roots[name] / f"snap_{name}", preset="tiny", snapshot_id=f"snap_{name}")
        (roots[name] / "LATEST").write_text(f"snap_{name}\n", encoding="utf-8")
    (project / "nexusbt.toml").write_text(f'[data]\npath = "{roots["a"]}"\n', encoding="utf-8")
    pipe = nx.Pipeline({"close": nx.Price.close.latest})
    result = nx.run_pipeline(pipe, start="2020-01-06", end="2020-01-06",
                             snapshot=nx.open(roots["b"]), save=True)  # fmt: skip
    assert (roots["b"] / "PINS" / "snap_b" / str(result.run_id)).is_file()
    assert not (roots["a"] / "PINS").exists()
    manifest = json.loads((project / "runs" / str(result.run_id) / "manifest.json").read_text())
    assert manifest["retention"] == "managed"


def test_imported_project_modules_are_captured(
    tiny: Path, project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """5.9.3: a project module the run imported is in `source/`, its path kept; the engine's
    own modules, installed or in this repository, are outside the project and are not."""
    (project / "helpers").mkdir()
    (project / "helpers" / "momentum.py").write_text("WINDOW = 3\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(project))
    importlib.import_module("helpers.momentum")
    pipe = nx.Pipeline({"close": nx.Price.close.latest})
    result = nx.run_pipeline(pipe, start="2020-01-06", end="2020-01-06", snapshot=str(tiny),
                             save=True)  # fmt: skip
    source = project / "runs" / str(result.run_id) / "source"
    assert (source / "helpers" / "momentum.py").read_text(encoding="utf-8") == "WINDOW = 3\n"
    assert not list(source.rglob("_pipeline.py"))


def test_a_failure_while_saving_aborts_the_run(
    tiny: Path, project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """5.9.1: a write that fails before the seal comes out as raised, leaves no run folder, and
    the index says `aborted`."""
    written = RunTxn.write_table

    def full(txn: RunTxn, name: str, table: object, **hashes: str) -> None:
        if name == "term_diagnostics":
            raise OSError(28, "No space left on device")
        written(txn, name, table, **hashes)

    monkeypatch.setattr(RunTxn, "write_table", full)
    pipe = nx.Pipeline({"close": nx.Price.close.latest})
    with pytest.raises(OSError, match="No space left"):
        nx.run_pipeline(pipe, start="2020-01-06", end="2020-01-06", snapshot=str(tiny),
                        save=True)  # fmt: skip
    runs = project / "runs"
    assert [p.name for p in runs.iterdir() if p.is_dir()] == []
    with closing(sqlite3.connect(runs / "index.sqlite")) as db:  # `with` alone does not close
        assert db.execute("SELECT kind, status FROM runs").fetchall() == [("pipeline", "aborted")]


def test_the_manifest_records_the_fallbacks_the_run_used(
    tmp_path_factory: pytest.TempPathFactory, project: Path
) -> None:
    """4.4 step 5 (#687): the snapshot's fallbacks are kept in the manifest's `data.fallbacks`,
    each as `FallbackRecord` holds it (`column` too), with `data.profiles`,
    `data.capabilities`, `data.unchecked`, and the fallback's sentence in `assumptions` (1.2);
    none of it names the package's or the project's folder (5.9.3)."""
    pkg = make_snapshot(  # F-18 in F-01's place, retired (#705)
        tmp_path_factory.mktemp("no_volume") / "pkg", preset="tiny", degrade=["no_volume"]
    )
    pipe = nx.Pipeline({"c": nx.Price.close.latest})
    with pytest.warns(UserWarning, match=r"\[E30\] F-18"):
        result = nx.run_pipeline(pipe, start="2020-01-06", end="2020-01-08", snapshot=str(pkg),
                                 save=True)  # fmt: skip
    manifest = json.loads((project / "runs" / str(result.run_id) / "manifest.json").read_text())
    data = manifest["data"]
    assert data["fallbacks"] == [
        {"id": "F-18", "dataset": "bars_1d", "market": m, "count": 341, "column": c}
        for m in ("KR", "US") for c in ("volume", "value_traded")
    ]  # fmt: skip
    assert set(data) == {"profiles", "capabilities", "unchecked", "fallbacks"}
    assert data["profiles"]["tds:minimal-daily@1.0"] == {  # the checker reports no `pass`
        "declared": True, "verified_level": "manifest", "result": "not_checked"}  # fmt: skip
    assert "price" in data["capabilities"]["features"]
    assert isinstance(data["unchecked"], list)
    assert [a for a in manifest["assumptions"] if "F-18" in a] == [
        "fallback F-18 used: Price.volume/value_traded = NaN, bars without them or null in every "
        "row for KR, US"
    ]
    said = json.dumps([data, manifest["assumptions"]])
    assert not [p for p in (pkg.parent, project, Path.home()) if str(p) in said]


def test_a_fallback_with_its_own_sentence_is_said_once(
    tmp_path_factory: pytest.TempPathFactory, project: Path
) -> None:
    """4.5 F-02 names its `assumptions` sentence; the run's manifest says it once, not again
    as an E30 line (#687 review)."""
    pkg = make_snapshot(tmp_path_factory.mktemp("no_sessions") / "pkg", preset="tiny",
                        degrade=["no_sessions"])  # fmt: skip
    pipe = nx.Pipeline({"c": nx.Price.close.latest})
    with pytest.warns(UserWarning, match=r"\[E30\] F-02"):
        result = nx.run_pipeline(pipe, start="2020-01-06", end="2020-01-06", snapshot=str(pkg),
                                 save=True)  # fmt: skip
    manifest = json.loads((project / "runs" / str(result.run_id) / "manifest.json").read_text())
    assert {f["id"] for f in manifest["data"]["fallbacks"]} == {"F-02"}
    assert [a for a in manifest["assumptions"] if "sessions synthesized" in a] == [
        "sessions synthesized from exchange_calendars 4.13.2"
    ]


def test_a_run_without_fallbacks_records_an_empty_list(tiny: Path, project: Path) -> None:
    """#687 Decisions: no fallback is `data.fallbacks = []`, never an absent key, so a manifest
    without the key reads as "not recorded"."""
    pipe = nx.Pipeline({"c": nx.Price.close.latest})
    result = nx.run_pipeline(pipe, start="2020-01-06", end="2020-01-06", snapshot=str(tiny),
                             save=True)  # fmt: skip
    manifest = json.loads((project / "runs" / str(result.run_id) / "manifest.json").read_text())
    assert manifest["data"]["fallbacks"] == []
    assert not [a for a in manifest["assumptions"] if a.startswith("fallback ")]


def test_without_save_no_run(tiny: Path, project: Path) -> None:
    """`save=False`, the default, seals nothing and gives no run id."""
    pipe = nx.Pipeline({"close": nx.Price.close.latest})
    result = nx.run_pipeline(pipe, start="2020-01-06", end="2020-01-06", snapshot=str(tiny))
    assert result.run_id is None
    assert not (project / "runs").exists()


def test_an_interactive_session_records_no_entry(
    tiny: Path, project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`__main__` without a file (an interactive session): the run is sealed with a warning
    and `source.entry = null`, as #304 built `capture_sources`."""
    monkeypatch.delattr(sys.modules["__main__"], "__file__")
    pipe = nx.Pipeline({"close": nx.Price.close.latest})
    with pytest.warns(UserWarning, match="no entry file"):
        result = nx.run_pipeline(pipe, start="2020-01-06", end="2020-01-06",
                                 snapshot=str(tiny), save=True)  # fmt: skip
    assert result.run_id is not None
    assert result.run_id.split("-")[2:4] == ["pipeline", "interactive"]
    manifest = json.loads((project / "runs" / result.run_id / "manifest.json").read_text())
    assert manifest["source"]["entry"] is None  # `outside` holds this test's own modules
