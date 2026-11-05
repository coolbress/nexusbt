"""Spec T1.14b: the append-only run index `runs/index.sqlite` and its canonical pins (5.9.5)."""

from __future__ import annotations

import re
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from nexusbt.artifacts import Index, RunStore

SPEC = Path(__file__).resolve().parents[3] / "docs" / "spec" / "engine-spec-v3.4.md"


def spec_tables() -> dict[str, list[str]]:
    """The table of 5.9.5 as the spec writes it: table name → column names in order."""
    text = SPEC.read_text(encoding="utf-8").split("#### 5.9.5", 1)[1].split("####", 1)[0]
    tables = {}
    for name, columns in re.findall(r"^\| `(\w+)` \| (.+) \|$", text, re.MULTILINE):
        bare, notes = columns.split(" — ")[0], r"\([^()]*\)|\[[^\]]*\]"  # prose after a dash
        while re.search(notes, bare):  # drop (notes) innermost first, and [references]
            bare = re.sub(notes, "", bare)
        tables[name] = [part.split()[0] for part in bare.split(",")]
    return tables


def connect(runs: Path) -> closing[sqlite3.Connection]:
    return closing(sqlite3.connect(runs / "index.sqlite"))


def test_tables_match_spec(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    RunStore(runs)
    expected = spec_tables()
    minimum = "studies runs candidates observations cohorts exposures preregistrations pins books"
    assert set(minimum.split()) | {"families", "selection_events"} <= set(expected)  # + #196
    with connect(runs) as db:
        names = {n for (n,) in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert names == set(expected)
        for table, columns in expected.items():
            found = [r[1] for r in db.execute(f"PRAGMA table_info({table})")]
            assert found == columns, table
        assert db.execute("PRAGMA journal_mode").fetchone() == ("wal",)


#: Values for the columns a CHECK limits; every other column of a probe row is the text "x".
#: The probes' table and column names come from the spec's table, not from input (S608).
CHECKED = {"status": "sealed", "detail_pruned": 0, "holder_kind": "run", "direction": "higher"}
CHECKED["ts_released"] = None  # an open pin, so the one allowed update can be tried
KINDS = {"candidates": "factor", "books": "paper"}


def refused(db: sqlite3.Connection, sql: str, *args: object) -> None:
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        db.execute(sql, args)


def test_append_only_triggers(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    store = RunStore(runs)
    with connect(runs) as db, db:
        for table, columns in spec_tables().items():
            row = [CHECKED.get(c, KINDS.get(table, "x") if c == "kind" else "x") for c in columns]
            marks = ", ".join("?" * len(row))
            db.execute(f"INSERT INTO {table} VALUES ({marks})", row)  # noqa: S608
            refused(db, f"DELETE FROM {table}")  # noqa: S608
            refused(db, f'UPDATE {table} SET "{columns[0]}" = ?', "y")  # noqa: S608
        db.execute("UPDATE pins SET ts_released = '2026-11-05'")  # filling it is allowed, once
        refused(db, "UPDATE pins SET ts_released = '2026-11-06'")

    sealed = store.begin("backtest", "mom", None).seal().run_id
    txn = store.begin("backtest", "mom", None)
    running, moved = txn.run_id, str(runs / f".aborted-{txn.run_id}")
    with connect(runs) as db, db:
        for to in ("running", "aborted"):  # a sealed run never goes back
            refused(db, "UPDATE runs SET status = ? WHERE run_id = ?", to, sealed)
        refused(db, "UPDATE runs SET name = 'other' WHERE run_id = ?", sealed)
        refused(db, "UPDATE runs SET path = ? WHERE run_id = ?", moved, sealed)
        db.execute("UPDATE runs SET detail_pruned = 1 WHERE run_id = ?", (sealed,))
        refused(db, "UPDATE runs SET detail_pruned = 0 WHERE run_id = ?", sealed)
        db.execute("UPDATE runs SET status = 'pruned' WHERE run_id = ?", (sealed,))
        refused(db, "UPDATE runs SET status = 'sealed' WHERE run_id = ?", sealed)
        both = "UPDATE runs SET status = ?, path = ? WHERE run_id = ?"
        refused(db, both, "sealed", moved, running)  # the folder moves only with an abort
        refused(db, both, "aborted", "/elsewhere", running)  # and only to `.aborted-<id>`
        db.execute(both, ("aborted", f"/other/spelling/.aborted-{running}", running))  # symlink
        assert db.execute("SELECT count(*) FROM runs").fetchone() == (3,)
    txn.abort()  # its row is already `aborted`; rewriting the same status is no change


def test_pins_canonical_in_index(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    txn = RunStore(runs).begin("backtest", "mom", None, snapshot_id="20261027-143144")
    with connect(runs) as db:
        assert db.execute("SELECT snapshot_id FROM runs").fetchall() == [("20261027-143144",)]
        pins = db.execute("SELECT snapshot_id, holder_id, holder_kind, ts_released FROM pins")
        assert pins.fetchall() == [("20261027-143144", txn.run_id, "run", None)]  # at start
    txn.abort()
    index = Index(runs)
    assert index.pinned() == {"20261027-143144"}  # only a release ends a pin
    index.pin("20261103-090000", "paper-kr", "book")
    index.release("20261027-143144", txn.run_id)
    index.release("20261027-143144", txn.run_id)  # a second release changes nothing
    assert index.pinned() == {"20261103-090000"}  # the released row stays (append-only)
    with pytest.raises(sqlite3.IntegrityError):
        index.pin("20261103-090000", "x", "dataset")  # holder_kind is run or book


def test_preregistration_claim_and_look_columns(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    RunStore(runs).begin("backtest", "mom", None).abort()
    tables = spec_tables()
    claim = {"range_start", "range_end", "judge_at", "benchmark_id", "conditions_hash"}
    assert claim <= set(tables["preregistrations"])  # 6.4, #269
    assert {"conditions_hash", "preregistration_id", "look_number"} <= set(tables["runs"])
    with connect(runs) as db, db:
        looks = "SELECT conditions_hash, preregistration_id, look_number FROM runs"
        assert db.execute(looks).fetchall() == [(None, None, None)]  # null: nothing matched
        insert = (
            "INSERT INTO preregistrations (id, metric, direction, judge_at, ts_created)"
            " VALUES (?, 'sharpe', ?, 'end', '2026-11-05')"
        )
        db.execute(insert, ("p1", "higher"))
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(insert, ("p2", "sideways"))  # direction is higher or lower
