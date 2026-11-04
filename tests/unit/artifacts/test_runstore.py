"""Spec T1.14a: sealed run folders (5.9.1-5.9.2, 2.6)."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import stat
from contextlib import closing
from pathlib import Path

import pyarrow as pa
import pytest

from nexusbt.artifacts import RunStore, RunTxn

TABLE = pa.table({"instrument_id": ["A", "B"], "value": [1.5, -2.0]})


def status(runs: Path, run_id: str) -> str:
    with closing(sqlite3.connect(runs / "index.sqlite")) as db:
        row = db.execute("SELECT status FROM runs WHERE run_id = ?", (run_id,)).fetchone()
    return str(row[0])


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
