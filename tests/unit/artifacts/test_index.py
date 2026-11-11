"""Spec T1.14b: the append-only run index `runs/index.sqlite` and its canonical pins (5.9.5)."""

from __future__ import annotations

import json
import re
import sqlite3
import uuid
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


FAMILY = "3f2b8c1e-9d4a-4e6f-8a1b-5c7d9e0f1a2b"
#: `runs` as T1.14a (#281, #284) created it; the other three never existed without `family_id`
#: and stand for "every existing study, exposure and preregistration" of 5.9.5.
BEFORE_FAMILIES = """
CREATE TABLE runs (
    run_id TEXT PRIMARY KEY, kind TEXT NOT NULL, name TEXT NOT NULL, ts_created TEXT NOT NULL,
    status TEXT NOT NULL, path TEXT NOT NULL);
INSERT INTO runs VALUES ('r1', 'backtest', 'mom', '2026-11-01T09:00:00+09:00', 'sealed', '/r/r1');
INSERT INTO runs VALUES ('r2', 'factor', 'val', '2026-11-02T09:00:00+09:00', 'aborted', '/r/r2');
CREATE TABLE studies (study_id TEXT PRIMARY KEY, name TEXT, ts_created TEXT);
INSERT INTO studies VALUES ('s1', 'momentum', '2026-11-01');
CREATE TABLE exposures (run_id TEXT, segment TEXT);
INSERT INTO exposures VALUES ('r1', 'train');
CREATE TABLE preregistrations (id TEXT PRIMARY KEY, metric TEXT, direction TEXT, ts_created TEXT);
INSERT INTO preregistrations VALUES ('p1', 'sharpe', 'higher', '2026-11-01');
"""
OLD_RUNS = [
    ("r1", "backtest", "mom", "2026-11-01T09:00:00+09:00", "sealed", "/r/r1"),
    ("r2", "factor", "val", "2026-11-02T09:00:00+09:00", "aborted", "/r/r2"),
]


def index_before_families(runs: Path) -> None:
    runs.mkdir()
    with connect(runs) as db, db:
        db.executescript(BEFORE_FAMILIES)


def test_index_before_families_is_migrated_once(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    index_before_families(runs)
    assert RunStore(runs, family_id=FAMILY).warnings == ()  # the toml carries the family
    six = "SELECT run_id, kind, name, ts_created, status, path FROM runs ORDER BY run_id"
    with connect(runs) as db:
        for table, columns in spec_tables().items():
            found = [r[1] for r in db.execute(f"PRAGMA table_info({table})")]
            assert found == columns, table
        assert db.execute(six).fetchall() == OLD_RUNS  # the rows keep their values
        families = db.execute("SELECT family_id, parent_family_id, reason FROM families")
        assert families.fetchall() == [(FAMILY, None, "linked at migration")]
        linked = (
            "SELECT family_id FROM runs UNION ALL SELECT family_id FROM studies UNION ALL"
            " SELECT family_id FROM exposures UNION ALL SELECT family_id FROM preregistrations"
        )
        assert db.execute(linked).fetchall() == [(FAMILY,)] * 5
        refused(db, "DELETE FROM runs")  # the triggers are in place afterwards
        refused(db, "UPDATE runs SET family_id = 'other'")
        refused(db, "UPDATE studies SET family_id = 'other'")
        before = list(db.iterdump())
    copy = runs / "index.sqlite.before-families"
    with closing(sqlite3.connect(copy)) as db:  # the file as it was, to go back to
        assert db.execute("SELECT * FROM runs ORDER BY run_id").fetchall() == OLD_RUNS
        assert db.execute("SELECT name FROM sqlite_master WHERE name = 'families'").fetchall() == []
    copied = copy.read_bytes()

    Index(runs, family_id="0b9e7a55-1c7e-4b0a-9a3f-2f4d6c8e0a1b")  # another id, a second open
    RunStore(runs)
    with connect(runs) as db:
        assert list(db.iterdump()) == before  # the migration runs once
    assert copy.read_bytes() == copied


def test_migration_without_family_id_warns_until_the_toml_has_it(tmp_path: Path) -> None:
    runs, toml = tmp_path / "runs", tmp_path / "nexusbt.toml"
    toml.write_text("[research]\n", encoding="utf-8")
    index_before_families(runs)
    store = RunStore(runs)
    with connect(runs) as db:
        ((family, reason),) = db.execute("SELECT family_id, reason FROM families").fetchall()
        assert db.execute("SELECT DISTINCT family_id FROM runs").fetchall() == [(family,)]
    assert (uuid.UUID(family).version, reason) == (4, "linked at migration")
    line = f'add `[research] family_id = "{family}"` to nexusbt.toml'
    assert store.warnings == (line,)
    sealed = store.begin("backtest", "mom", None)
    sealed.set_manifest({"warnings": ["E11 daily-bar fills"]})
    manifest = json.loads((sealed.seal().path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["warnings"] == [line, "E11 daily-bar fills"]  # every run carries the line
    assert RunStore(runs).warnings == (line,)  # the same family at every later open
    assert Index(runs).warnings == (line,)

    written = RunStore(runs, family_id=family)  # until it is written
    assert written.warnings == ()
    record = written.begin("backtest", "mom", None).seal()
    assert "warnings" not in json.loads((record.path / "manifest.json").read_text("utf-8"))
    assert toml.read_text(encoding="utf-8") == "[research]\n"  # the engine never edits it


def test_migration_refuses_what_it_cannot_carry(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    index_before_families(runs)
    with pytest.raises(ValueError, match="family_id"):
        RunStore(runs, family_id="my-study")  # not a UUID: nothing is written under it
    with connect(runs) as db, db:
        db.execute("ALTER TABLE runs ADD COLUMN owner TEXT")
    with pytest.raises(RuntimeError, match="owner"):
        RunStore(runs, family_id=FAMILY)  # a column 5.9.5 does not have would be lost
    with connect(runs) as db:  # refused whole: the index is as it was
        assert db.execute("SELECT name FROM sqlite_master WHERE name = 'families'").fetchall() == []
        assert db.execute("SELECT * FROM runs ORDER BY run_id").fetchall() == [
            (*row, None) for row in OLD_RUNS
        ]
