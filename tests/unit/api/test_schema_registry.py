"""Spec 2.5, #331: the schema registry `api` builds from an opened snapshot (synthetic, 2.7)."""

from __future__ import annotations

from pathlib import Path

import pytest

import nexusbt as nx
from nexusbt import api
from nexusbt.api import schema_registry, stubs_current
from nexusbt.config import load_config
from nexusbt.testing.synth import make_snapshot
from nexusbt_tds import read_manifest
from nexusbt_tds.hash import resolved_columns
from nexusbt_tds.schemas.verify import load_schemas


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


def test_stubs_current_without_a_snapshot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """#469: with no snapshot the comparison is against the fixed columns alone, without an
    error; the tracked stub holds exactly those (#469, Decisions 2026-11-16)."""
    assert stubs_current(None, load_config(None))
    changed = tmp_path / "d.pyi"
    changed.write_text("class Price:\n    momentum: BoundColumn\n")
    monkeypatch.setattr(api, "_STUBS", changed)
    assert not stubs_current(None, load_config(None))
    monkeypatch.setattr(api, "_STUBS", tmp_path / "missing.pyi")
    assert not stubs_current(None, load_config(None))  # stale, not an error
