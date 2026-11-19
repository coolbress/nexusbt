"""`nx.run_pipeline(..., save=True)` (spec 3.5; 3.8's `kind="pipeline"` row, 5.9.1, 5.9.3; #249
Decisions 2026-11-19): the sealed run, its tables, and the entry file the run started from
(#283, #304)."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pyarrow.parquet as pq
import pytest

import nexusbt as nx
from nexusbt.factors import SMA
from nexusbt.testing.synth import make_snapshot

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
    assert manifest["source"] == {"entry": "m.py"}
    assert (folder / "source" / "m.py").read_text(encoding="utf-8") == "# the entry file\n"
    assert manifest["kind"] == "pipeline"
    assert manifest["snapshot_semantic_hash"] == nx.open(tiny).semantic_hash


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
    assert manifest["source"] == {"entry": None}
