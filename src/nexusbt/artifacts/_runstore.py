"""Run folders: temporary write, rename, read-only, `SEALED` last (5.9.1-5.9.2, 2.6)."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import stat
import uuid
from collections.abc import Iterable, Iterator, Mapping
from contextlib import closing, contextmanager, suppress
from dataclasses import dataclass
from datetime import datetime
from itertools import count
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

_LOGICAL_EXCLUDED = ("created_at", "created_by")  # 5.9.2, R-31
_RUNS = """CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY, kind TEXT NOT NULL, name TEXT NOT NULL, ts_created TEXT NOT NULL,
    status TEXT NOT NULL, path TEXT NOT NULL)"""  # the columns #248 (T1.14b) completes


def canonical_json(value: object) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def value_hash(manifest: Mapping[str, object]) -> str:
    """The manifest's logical hash: canonical JSON without `created_at` and `created_by`."""
    kept = {k: v for k, v in manifest.items() if k not in _LOGICAL_EXCLUDED}
    return hashlib.sha256(canonical_json(kept).encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class RunRecord:
    run_id: str
    path: Path
    manifest_sha256: str  # the content of `SEALED`
    value_sha256: str


def _files(folder: Path) -> dict[str, Path]:
    return {p.relative_to(folder).as_posix(): p for p in sorted(folder.rglob("*")) if p.is_file()}


class RunStore:
    """`root` is the `runs/` folder, with the index `index.sqlite` in it."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        with self._db() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute(_RUNS)

    @contextmanager
    def _db(self) -> Iterator[sqlite3.Connection]:
        with closing(sqlite3.connect(self.root / "index.sqlite")) as db, db:
            yield db

    def _set(self, run_id: str, status: str) -> None:
        with self._db() as db:
            db.execute("UPDATE runs SET status = ? WHERE run_id = ?", (status, run_id))

    def begin(
        self,
        kind: str,
        name: str,
        study: str | None,
        *,
        graph_hash: str | None = None,
        params: Mapping[str, object] | None = None,
        settings: Mapping[str, object] | None = None,
        snapshot_semantic_hash: str | None = None,
    ) -> RunTxn:
        """5.9.1: `run_id` = local time, kind, name, h6; `-2`, `-3` when it already exists."""
        for part in (kind, name):
            if not part or part.startswith(".") or "/" in part or "\\" in part:
                raise ValueError(f"{part!r}: a run kind or name is one folder-name part")
        key = {"graph_hash": graph_hash, "params": dict(params or {})}
        key |= {"settings": dict(settings or {}), "snapshot_semantic_hash": snapshot_semantic_hash}
        h6 = hashlib.sha256(canonical_json(key).encode()).hexdigest()[:6]
        now = datetime.now().astimezone()  # the computing machine's local time
        base = f"{now:%Y%m%d-%H%M%S}-{kind}-{name}-{h6}"
        with self._db() as db:
            for n in count(1):
                run_id = base if n == 1 else f"{base}-{n}"
                if (self.root / run_id).exists():
                    continue
                with suppress(sqlite3.IntegrityError):
                    db.execute(
                        "INSERT INTO runs (run_id, kind, name, ts_created, status, path)"
                        " VALUES (?, ?, ?, ?, 'running', ?)",
                        (run_id, kind, name, now.isoformat(), str(self.root / run_id)),
                    )
                    break
        tmp = self.root / f".tmp-{uuid.uuid4().hex}"
        tmp.mkdir()
        return RunTxn(self, run_id, tmp, now)


class RunTxn:
    """One run being written in `runs/.tmp-<uuid>/`; `seal()` or `abort()` ends it."""

    def __init__(self, store: RunStore, run_id: str, tmp: Path, created: datetime) -> None:
        self.run_id, self._store, self._tmp, self._created = run_id, store, tmp, created
        self._manifest: dict[str, object] = {}
        self._state = "open"  # open → renamed → sealed, or open → aborted

    def write_table(self, name: str, table: object) -> None:
        """Parquet as 5.9.4 says; anything but an Arrow table is refused (no pickle, 2.6)."""
        if not isinstance(table, pa.Table):
            raise TypeError(f"{name}: run tables are pyarrow Tables, not {type(table).__name__}")
        if not name or Path(name).is_absolute() or ".." in Path(name).parts:
            raise ValueError(f"table name {name!r} must stay inside the run folder")
        path = self._tmp / f"{name}.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(
            table,
            path,
            compression="zstd",
            compression_level=3,
            row_group_size=131_072,
            write_statistics=True,
            use_dictionary=[f.name for f in table.schema if pa.types.is_string(f.type)],
        )

    def capture_sources(self, paths: Iterable[Path]) -> None:
        raise NotImplementedError  # 5.9.3, the second pull request of #247

    def set_manifest(self, fields: Mapping[str, object]) -> None:
        self._manifest.update(fields)

    def seal(self) -> RunRecord:
        """Manifest, rename, read-only, `SEALED` last; a failure before the rename aborts."""
        if self._state != "open":
            raise RuntimeError(f"run {self.run_id} is already {self._state}")
        final = self._store.root / self.run_id
        try:
            outputs = {k: {"physical_sha256": _sha256(p)} for k, p in _files(self._tmp).items()}
            manifest = {**self._manifest, "schema_version": "nexusbt-run/2", "outputs": outputs}
            value = value_hash(manifest)  # a NaN in the manifest fails here, before the rename
            manifest["created_at"] = self._created.isoformat()
            text = json.dumps(manifest, sort_keys=True, indent=2, ensure_ascii=False)
            with (self._tmp / "manifest.json").open("w", encoding="utf-8") as f:
                f.write(text + "\n")
                f.flush()
                os.fsync(f.fileno())
            self._tmp.rename(final)
        except BaseException:
            self.abort()
            raise
        self._state = "renamed"  # from here a failure is left to seal recovery, not aborted
        for path in _files(final).values():  # `chmod a-w`
            path.chmod(path.stat().st_mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))
        digest = _sha256(final / "manifest.json")
        (final / "SEALED").write_text(digest, encoding="utf-8")
        (final / "SEALED").chmod(0o444)
        self._store._set(self.run_id, "sealed")
        self._state = "sealed"
        return RunRecord(self.run_id, final, digest, value)

    def abort(self) -> None:
        """5.9.1: the temporary folder is deleted and the index says `aborted`.

        A no-op once the folder was renamed: a sealed run stays sealed, and a run stopped
        between the rename and the seal is left `running` for seal recovery.
        """
        if self._state != "open":
            return
        shutil.rmtree(self._tmp, ignore_errors=True)
        self._store._set(self.run_id, "aborted")
        self._state = "aborted"
