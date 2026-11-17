"""Spec 2.5, #331: the schema registry `api` builds from an opened snapshot (synthetic, 2.7)."""

from __future__ import annotations

import datetime as dt
import json
import shutil
from pathlib import Path

import pyarrow as pa
import pytest

import nexusbt as nx
from nexusbt import Label, Panel, api
from nexusbt.api import schema_registry, stubs, stubs_current
from nexusbt.config import load_config
from nexusbt.pipeline import bind, stub_source
from nexusbt.testing._synth_package import _write
from nexusbt.testing.synth import make_snapshot, read
from nexusbt_tds import read_manifest
from nexusbt_tds.hash import resolved_columns, write_hashes
from nexusbt_tds.schemas.verify import load_schemas

DAY, KNOWN = dt.date(2020, 1, 31), dt.datetime(2020, 2, 3, tzinfo=dt.UTC)


@pytest.fixture(scope="module")
def panels(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """`tiny` with a feature panel and a label panel whose value columns are declared in
    tds.json only (TDS 5.25), and the `dictionary/columns` rows that describe them."""
    root = make_snapshot(tmp_path_factory.mktemp("panels") / "snap", preset="tiny")
    keys = {"instrument_id": read(root, "instruments")["instrument_id"].slice(0, 1),
            "period": [DAY], "as_of_date": [DAY],
            "ts_available": pa.array([KNOWN], pa.timestamp("us", "UTC"))}  # fmt: skip
    described = {"dataset": ["factor_pit_monthly", "factor_pit_monthly", "label_monthly"],
                 "column": ["momentum", "leak", "ret_fwd_1m"], "type": ["f64"] * 3,
                 "is_label": [False, True, True]}  # fmt: skip
    tables = {
        ("factor_pit_monthly", "feature_panels"): {**keys, "momentum": [0.5], "leak": [0.1]},
        ("label_monthly", "label_panels"): {**keys, "ret_fwd_1m": [0.1]},
        ("dictionary_columns", "dictionary/columns"): described,
    }
    data = json.loads((root / "tds.json").read_text(encoding="utf-8"))
    for (name, kind), columns in tables.items():
        entry = _write(root, f"{name}/part-00000.parquet", name, pa.table(columns))
        declared = [{"name": c, "type": "f64"} for c in columns if c not in (*keys, *described)]
        data["datasets"].append({"name": name, "kind": kind, "path": name, "files": [entry],
                                 "schema_version": "1.0", "columns": declared})  # fmt: skip
    (root / "tds.json").write_text(json.dumps(data), encoding="utf-8")
    write_hashes(root)
    return root


def test_declared_panel_column_is_in_the_engine_column_set(
    panels: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """#331: a column `feature_panels` declares outside its schema file is the engine's, with
    its type, after the schema file's own; the labels are the dictionary's `is_label` rows."""
    registry = schema_registry(nx.open(panels), load_config(None))
    assert registry.columns["factor_pit_monthly"] == (
        ("instrument_id", "id"), ("period", "date"), ("as_of_date", "date"),
        ("ts_available", "ts_us"), ("momentum", "f64"), ("leak", "f64"),
    )  # fmt: skip
    assert registry.labels == {"factor_pit_monthly": frozenset({"leak"}),
                               "label_monthly": frozenset({"ret_fwd_1m"})}  # fmt: skip
    assert (registry.feature, registry.label) == ("factor_pit_monthly", "label_monthly")
    bind(Panel.momentum.latest, registry)
    bind(Label.ret_fwd_1m, registry)
    with pytest.raises(nx.LabelLeakError):
        bind(Panel.leak.latest, registry)
    stub = stub_source(registry)
    assert "(metaclass=_Snapshot):\n    momentum: BoundColumn\n\nclass Label" in stub
    assert stub.endswith("class Label(metaclass=_Snapshot):\n    ret_fwd_1m: BoundColumn\n")
    (tmp_path / "nexusbt.toml").write_text(f'[data]\npath = "{panels}"\n', encoding="utf-8")
    monkeypatch.chdir(tmp_path)  # `nexusbt stubs` reads the snapshot `[data]` names
    assert stubs(tmp_path / "d.pyi").read_text(encoding="utf-8") == stub


def test_labels_are_read_from_every_dictionary(panels: Path, tmp_path: Path) -> None:
    """A second `dictionary/columns` marks labels too; one without `is_label` marks none."""
    root = shutil.copytree(panels, tmp_path / "two")
    data = json.loads((root / "tds.json").read_text(encoding="utf-8"))
    more = {"dataset": ["factor_pit_monthly"], "column": ["momentum"], "is_label": [True]}
    for name, columns in (("more", more), ("bare", {"dataset": ["x"], "column": ["y"]})):
        entry = _write(root, f"{name}/part-00000.parquet", name, pa.table(columns))
        data["datasets"].append({"name": name, "kind": "dictionary/columns", "path": name,
                                 "files": [entry], "schema_version": "1.0"})  # fmt: skip
    (root / "tds.json").write_text(json.dumps(data), encoding="utf-8")
    write_hashes(root)
    registry = schema_registry(nx.open(root), load_config(None))
    assert registry.labels["factor_pit_monthly"] == frozenset({"leak", "momentum"})
    with pytest.raises(nx.LabelLeakError):
        bind(Panel.momentum.latest, registry)


def test_column_sets_are_the_checkers_resolved_columns(tmp_path: Path) -> None:
    """#331: for every dataset of `small`, the engine's column set is `resolved_columns`, in
    order: one resolution, the value hash's and the checker's."""
    root = make_snapshot(tmp_path / "small", preset="small")
    registry, schemas = schema_registry(nx.open(root), load_config(None)), load_schemas()
    datasets = read_manifest(root).datasets
    assert sorted(registry.columns) == sorted(d["name"] for d in datasets)
    for ds in datasets:
        resolved = resolved_columns(ds, schemas[ds["kind"]].columns)
        assert registry.columns[ds["name"]] == tuple((c.name, c.type) for c in resolved)
    assert ("close", "f64") in registry.columns["bars_1d"]
    assert registry.labels == {}  # no `dictionary/columns` in the package


def test_stubs_current_without_a_snapshot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """#469: with no snapshot the comparison is against the fixed columns alone, without an
    error; the tracked stub holds exactly those (#469, Decisions 2026-11-16)."""
    assert stubs_current(None, load_config(None))
    changed = tmp_path / "d.pyi"
    changed.write_text("class Panel(metaclass=_Snapshot):\n    momentum: BoundColumn\n")
    monkeypatch.setattr(api, "_STUBS", changed)
    assert not stubs_current(None, load_config(None))
