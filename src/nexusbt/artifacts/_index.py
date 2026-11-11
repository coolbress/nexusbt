"""The run index `runs/index.sqlite`: the append-only tables of 5.9.5 and the canonical pins."""

from __future__ import annotations

import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import closing, contextmanager
from datetime import datetime
from pathlib import Path

_STATUS = "CHECK (status IN ('running', 'sealed', 'aborted', 'pruned'))"
_TABLES: dict[str, tuple[str, ...]] = {
    "families": ("family_id TEXT PRIMARY KEY", "parent_family_id TEXT", "reason TEXT NOT NULL",
                 "ts_created TEXT NOT NULL"),
    "studies": ("study_id TEXT PRIMARY KEY", "name TEXT NOT NULL UNIQUE", "family_id TEXT",
                "ts_created TEXT NOT NULL", "hypothesis TEXT"),
    "runs": ("run_id TEXT PRIMARY KEY", "kind TEXT NOT NULL", "run_kind TEXT", "family_id TEXT",
             "study_id TEXT", "name TEXT NOT NULL", "ts_created TEXT NOT NULL", "created_by TEXT",
             "snapshot_id TEXT", "snapshot_semantic_hash TEXT", "edition TEXT", "segment TEXT",
             "graph_hash TEXT", "params_json TEXT", "settings_hash TEXT", "candidate_key TEXT",
             "conditions_hash TEXT", "preregistration_id TEXT", "look_number INTEGER",
             f"status TEXT NOT NULL {_STATUS}",
             "detail_pruned INTEGER NOT NULL DEFAULT 0 CHECK (detail_pruned IN (0, 1))",
             "path TEXT NOT NULL", "metrics_json TEXT", "derived_from TEXT"),
    "candidates": ("candidate_key TEXT PRIMARY KEY", "study_id TEXT",
                   "kind TEXT NOT NULL CHECK (kind IN ('factor', 'strategy'))", "segment TEXT",
                   "graph_hash TEXT", "params_hash TEXT", "settings_hash TEXT",
                   "first_run_id TEXT"),
    "observations": ("observation_id TEXT PRIMARY KEY", "run_id TEXT NOT NULL",
                     "candidate_key TEXT NOT NULL", "snapshot_semantic_hash TEXT", "segment TEXT",
                     "start TEXT", '"end" TEXT', "target TEXT", "horizon INTEGER", "freq TEXT",
                     "n_obs INTEGER", "sr_daily REAL", "skew REAL", "kurt REAL", "nw_t REAL",
                     "method TEXT", "split_hash TEXT", "fidelity TEXT", "ts_created TEXT NOT NULL"),
    "cohorts": ("cohort_sha256 TEXT PRIMARY KEY", "study_id TEXT", "kind TEXT", "segment TEXT",
                "target TEXT", "horizon INTEGER", "freq TEXT", "members_json TEXT NOT NULL",
                "ts_frozen TEXT NOT NULL"),
    "exposures": ("run_id TEXT NOT NULL", "family_id TEXT", "study_id TEXT", "segment TEXT",
                  "start TEXT", '"end" TEXT'),
    "preregistrations": ("id TEXT PRIMARY KEY", "family_id TEXT", "study_id TEXT",
                         "graph_hash TEXT", "metric TEXT NOT NULL",
                         "direction TEXT NOT NULL CHECK (direction IN ('higher', 'lower'))",
                         "threshold REAL", "segment TEXT", "range_start TEXT", "range_end TEXT",
                         "judge_at TEXT", "benchmark_id TEXT", "conditions_hash TEXT",
                         "exposed_elsewhere TEXT", "note TEXT", "ts_created TEXT NOT NULL"),
    "selection_events": ("event_id TEXT PRIMARY KEY", "family_id TEXT", "run_id TEXT",
                         "source TEXT NOT NULL", "from_cohort_sha256 TEXT", "from_count INTEGER",
                         "chosen_candidate_key TEXT", "segment TEXT", "ts_created TEXT NOT NULL"),
    "pins": ("snapshot_id TEXT NOT NULL", "holder_id TEXT NOT NULL",
             "holder_kind TEXT NOT NULL CHECK (holder_kind IN ('run', 'book'))",
             "ts_created TEXT NOT NULL", "ts_released TEXT"),
    "books": ("book_id TEXT PRIMARY KEY", "kind TEXT NOT NULL CHECK (kind IN ('paper', 'manual'))",
              "ts_created TEXT NOT NULL", "base_ccy TEXT", "sleeves_json TEXT",
              "definition_sha256 TEXT"),
}  # fmt: skip


def _names(table: str) -> list[str]:
    return [c.split()[0].strip('"') for c in _TABLES[table]]


def _unchanged(table: str, *changing: str) -> str:
    return " AND ".join(f'NEW."{c}" IS OLD."{c}"' for c in _names(table) if c not in changing)


#: The only updates 5.9.5 allows; every other UPDATE and every DELETE is refused.
_ALLOWED = {
    "runs": f"""{_unchanged("runs", "status", "path", "detail_pruned")}
        AND (NEW.status IS OLD.status
             OR (OLD.status = 'running' AND NEW.status IN ('sealed', 'aborted'))
             OR (OLD.status = 'sealed' AND NEW.status = 'pruned'))
        AND (NEW.path IS OLD.path
             OR (OLD.status = 'running' AND NEW.status = 'aborted'
                 AND substr(NEW.path, -length(OLD.run_id) - 10) = '/.aborted-' || OLD.run_id))
        AND (NEW.detail_pruned IS OLD.detail_pruned
             OR (OLD.detail_pruned = 0 AND NEW.detail_pruned = 1))""",
    "pins": f"{_unchanged('pins', 'ts_released')} AND OLD.ts_released IS NULL",
}


_MIGRATED = "linked at migration"


def _is_uuid(text: str) -> bool:
    try:
        return str(uuid.UUID(text)) == text
    except ValueError:
        return False


def _tables(db: sqlite3.Connection) -> set[str]:
    return {n for (n,) in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}


def _before_families(db: sqlite3.Connection) -> bool:
    """An index an earlier engine wrote: it has `runs` and no `families` (5.9.5)."""
    return {"runs", "families"} & _tables(db) == {"runs"}


def _copy_beside(path: Path) -> None:
    """`index.sqlite.before-families`: the index as it is, to go back to (#305).

    Called inside the migration's write transaction, so one process writes it and no row
    arrives after it; a migration that fails leaves the copy of the state it failed on.
    """
    copy = path.with_name(path.name + ".before-families")
    partial = copy.with_name(copy.name + ".tmp")
    partial.unlink(missing_ok=True)
    with closing(sqlite3.connect(path)) as index, closing(sqlite3.connect(partial)) as to:
        index.backup(to)
    partial.replace(copy)


def _migrate(db: sqlite3.Connection, family_id: str) -> None:
    """5.9.5 "Migration to families": every existing row is carried into the 5.9.5 tables.

    Each table is rebuilt with its rows and the family (decision 2026-11-11, #305); the
    append-only triggers are created after it, in the same transaction, so they see no update.
    """
    for table in _tables(db) & set(_TABLES):
        old = [r[1] for r in db.execute(f"PRAGMA table_info({table})")]
        if unknown := sorted(set(old) - set(_names(table))):
            raise RuntimeError(f"index table {table!r} has columns {unknown} that 5.9.5 has not")
        kept = ", ".join(f'"{c}"' for c in old if c != "family_id")
        link = (", family_id", ", ?", (family_id,)) if "family_id" in _names(table) else ("",) * 2
        db.execute(f"ALTER TABLE {table} RENAME TO {table}_before_families")
        db.execute(f"CREATE TABLE {table} ({', '.join(_TABLES[table])})")
        db.execute(
            f"INSERT INTO {table} ({kept}{link[0]})"  # noqa: S608 - names from `_TABLES`
            f" SELECT {kept}{link[1]} FROM {table}_before_families",
            *link[2:],
        )
        db.execute(f"DROP TABLE {table}_before_families")
    db.execute(f"CREATE TABLE families ({', '.join(_TABLES['families'])})")
    db.execute(
        "INSERT INTO families (family_id, reason, ts_created) VALUES (?, ?, ?)",
        (family_id, _MIGRATED, datetime.now().astimezone().isoformat()),
    )


def _ensure(db: sqlite3.Connection) -> None:
    for table, columns in _TABLES.items():
        db.execute(f"CREATE TABLE IF NOT EXISTS {table} ({', '.join(columns)})")
        found = [r[1] for r in db.execute(f"PRAGMA table_info({table})")]
        if found != _names(table):
            raise RuntimeError(f"index table {table!r} has columns {found}, not those of 5.9.5")
        db.execute(
            f"CREATE TRIGGER IF NOT EXISTS {table}_no_delete BEFORE DELETE ON {table}"
            f" BEGIN SELECT RAISE(ABORT, 'the run index is append-only: {table}'); END"
        )
        when = f" WHEN NOT ({_ALLOWED[table]})" if table in _ALLOWED else ""
        db.execute(
            f"CREATE TRIGGER IF NOT EXISTS {table}_no_update BEFORE UPDATE ON {table}{when}"
            f" BEGIN SELECT RAISE(ABORT, 'the run index is append-only: {table}'); END"
        )


@contextmanager
def connect(root: Path) -> Iterator[sqlite3.Connection]:
    """One transaction on `root/index.sqlite`: committed on success, rolled back on error."""
    with closing(sqlite3.connect(Path(root) / "index.sqlite")) as db, db:
        yield db


def insert_pin(db: sqlite3.Connection, snapshot_id: str, holder_id: str, holder_kind: str) -> None:
    db.execute(
        "INSERT INTO pins (snapshot_id, holder_id, holder_kind, ts_created) VALUES (?, ?, ?, ?)",
        (snapshot_id, holder_id, holder_kind, datetime.now().astimezone().isoformat()),
    )


class Index:
    """`root` is the `runs/` folder; its `pins` table is the canonical record of pins (4.2)."""

    def __init__(self, root: Path, *, family_id: str | None = None) -> None:
        """`family_id` is the project's `[research] family_id`, `None` when the toml has none."""
        if family_id is not None and not _is_uuid(family_id):
            raise ValueError(f"family_id {family_id!r} is not a UUID as `nexusbt init` writes it")
        self.root, self._family_id = Path(root), family_id
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.root / "index.sqlite"
        with closing(sqlite3.connect(path)) as db:
            db.execute("PRAGMA journal_mode=WAL")
            if _before_families(db):
                db.execute("BEGIN IMMEDIATE")  # one writer: another open waits, finds families
            with db:
                if _before_families(db):
                    _copy_beside(path)
                    _migrate(db, family_id or str(uuid.uuid4()))
                _ensure(db)

    @property
    def warnings(self) -> tuple[str, ...]:
        """The line every run carries until the toml names the family of the migration (5.9.5)."""
        if self._family_id is not None:
            return ()
        with connect(self.root) as db:
            rows = db.execute("SELECT family_id FROM families WHERE reason = ?", (_MIGRATED,))
            return tuple(f'add `[research] family_id = "{f}"` to nexusbt.toml' for (f,) in rows)

    def pin(self, snapshot_id: str, holder_id: str, holder_kind: str = "run") -> None:
        with connect(self.root) as db:
            insert_pin(db, snapshot_id, holder_id, holder_kind)

    def release(self, snapshot_id: str, holder_id: str) -> None:
        """Fills `ts_released`; the row stays, as the append-only index keeps every pin."""
        with connect(self.root) as db:
            db.execute(
                "UPDATE pins SET ts_released = ? WHERE snapshot_id = ? AND holder_id = ?"
                " AND ts_released IS NULL",
                (datetime.now().astimezone().isoformat(), snapshot_id, holder_id),
            )

    def pinned(self) -> frozenset[str]:
        """The snapshot ids that at least one unreleased pin holds."""
        with connect(self.root) as db:
            rows = db.execute("SELECT snapshot_id FROM pins WHERE ts_released IS NULL")
            return frozenset(s for (s,) in rows)
