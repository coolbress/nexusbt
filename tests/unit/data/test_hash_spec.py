"""A package hashed by an earlier draft's method (`tds-hash-1`), met by the engine (#705 B4)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from nexusbt.contracts import SnapshotError
from nexusbt.data import DataConfig, open_snapshot
from nexusbt.testing.synth import make_snapshot
from nexusbt_tds.hash import HASH_SPEC, write_hashes

pytestmark = pytest.mark.unit


def test_an_earlier_hash_spec_is_e14_until_the_hashes_are_written_again(tmp_path: Path) -> None:
    root = make_snapshot(tmp_path / "snap", preset="tiny")
    manifest = root / "tds.json"
    data = json.loads(manifest.read_text())
    data["hashes"]["hash_spec"] = "tds-hash-1"
    manifest.write_text(json.dumps(data))
    with pytest.raises(SnapshotError) as raised:
        open_snapshot(DataConfig(path=root))
    assert "TDS-M014" in str(raised.value)
    assert "tds hash --write" in str(raised.value)
    write_hashes(root)  # `tds hash --write`
    assert json.loads(manifest.read_text())["hashes"]["hash_spec"] == HASH_SPEC
    open_snapshot(DataConfig(path=root))
