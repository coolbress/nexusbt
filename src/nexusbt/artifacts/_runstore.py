"""Run folders: temporary write, rename, read-only, `SEALED` last, recovery at open (5.9.1-3)."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import shutil
import sqlite3
import stat
import subprocess
import uuid
import warnings
from collections.abc import Iterable, Mapping
from contextlib import AbstractContextManager, suppress
from dataclasses import dataclass
from datetime import datetime
from importlib import resources
from itertools import count
from pathlib import Path
from typing import IO

import pyarrow as pa
import pyarrow.parquet as pq

from ._environment import environment
from ._index import Index, connect, insert_pin

#: Test-only injection point: the boundary name at which the process exits (`os._exit`), so a
#: test can kill a real run between two commit steps. `None` on every production path.
_CRASH_AT: str | None = None
_HERE = Path(__file__).resolve()
#: The engine lock of a source checkout (`src/nexusbt/artifacts/` → the repository root);
#: an installed copy uses the one the wheel ships as package data, `_SHIPPED_LOCK` (#283).
_ENGINE_LOCK: Path | None = _HERE.parents[3] / "uv.lock" if _HERE.parents[2].name == "src" else None
_SHIPPED_LOCK = "resources/uv.lock"
_LOGICAL_EXCLUDED = ("created_at", "created_by")  # 5.9.2, R-31


def _boundary(name: str) -> None:
    if name == _CRASH_AT:
        os._exit(70)  # pragma: no cover - runs only in the tests' child process


def canonical_json(value: object) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


def _hash_json(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def _engine_lock() -> bytes:
    """5.9.3, INV-03: the engine's `uv.lock`; with neither copy the install is broken."""
    if _ENGINE_LOCK is not None and _ENGINE_LOCK.is_file():
        return _ENGINE_LOCK.read_bytes()
    shipped = resources.files("nexusbt").joinpath(_SHIPPED_LOCK)
    if shipped.is_file():
        return shipped.read_bytes()
    raise FileNotFoundError(
        f"no engine uv.lock beside the source tree or at nexusbt/{_SHIPPED_LOCK}"
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


def _try_lock(path: Path) -> IO[str] | None:
    """An exclusive lock on `path`, or `None` while a live process holds it."""
    handle = path.open("a+", encoding="utf-8")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        return None
    return handle


class RunStore:
    """`root` is the `runs/` folder; every open recovers the runs whose process is gone."""

    def __init__(self, root: Path) -> None:
        self.root = Index(root).root  # creates the folder and the tables of 5.9.5
        self._recover()

    def _db(self) -> AbstractContextManager[sqlite3.Connection]:
        return connect(self.root)

    def _set(self, run_id: str, status: str, path: Path | None = None) -> None:
        with self._db() as db:
            db.execute(
                "UPDATE runs SET status = ?, path = coalesce(?, path) WHERE run_id = ?",
                (status, None if path is None else str(path), run_id),
            )

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
        snapshot_id: str | None = None,
    ) -> RunTxn:
        """5.9.1: `run_id` = local time, kind, name, h6; `-2`, `-3` when it already exists.

        With `snapshot_id`, the pin (snapshot_id, run_id) goes into the index with the run row.
        """
        for part in (kind, name):
            if not part or part.startswith(".") or "/" in part or "\\" in part:
                raise ValueError(f"{part!r}: a run kind or name is one folder-name part")
        key = {"graph_hash": graph_hash, "params": dict(params or {})}
        key |= {"settings": dict(settings or {}), "snapshot_semantic_hash": snapshot_semantic_hash}
        h6 = _hash_json(key)[:6]
        now = datetime.now().astimezone()  # the computing machine's local time
        base = f"{now:%Y%m%d-%H%M%S}-{kind}-{name}-{h6}"
        tmp = self.root / f".tmp-{uuid.uuid4().hex}"
        lock = _try_lock(tmp.with_name(tmp.name + ".lock"))  # held while this process lives
        if lock is None:  # pragma: no cover - a fresh uuid is never locked
            raise RuntimeError(f"{tmp} is locked")
        with self._db() as db:
            for n in count(1):
                run_id = base if n == 1 else f"{base}-{n}"
                if (self.root / run_id).exists():
                    continue
                lock.truncate(0)  # the id is in the lock before its row: an open never sees
                lock.write(run_id)  # a `running` row whose live process it cannot name
                lock.flush()
                with suppress(sqlite3.IntegrityError):
                    db.execute(
                        "INSERT INTO runs (run_id, kind, study_id, name, ts_created, snapshot_id,"
                        " snapshot_semantic_hash, graph_hash, params_json, settings_hash, status,"
                        " path) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'running', ?)",
                        (run_id, kind, study, name, now.isoformat(), snapshot_id,
                         snapshot_semantic_hash, graph_hash, canonical_json(key["params"]),
                         _hash_json(key["settings"]), str(self.root / run_id)),
                    )  # fmt: skip
                    break
            if snapshot_id is not None:
                insert_pin(db, snapshot_id, run_id, "run")
        _boundary("inserted")
        tmp.mkdir()
        return RunTxn(self, run_id, tmp, lock, dict(params or {}), now)

    def _recover(self) -> None:
        """5.9.1 seal recovery: runs whose lock no process holds are aborted or sealed."""
        live: set[str] = set()
        for lock_path in sorted(self.root.glob(".tmp-*.lock")):
            handle = _try_lock(lock_path)
            if handle is None:
                live.add(lock_path.read_text(encoding="utf-8"))
                continue
            with handle:
                shutil.rmtree(lock_path.with_suffix(""), ignore_errors=True)
                lock_path.unlink()
        for orphan in self.root.glob(".tmp-*"):  # a temporary folder whose lock file is gone
            if orphan.is_dir() and not orphan.with_name(orphan.name + ".lock").exists():
                shutil.rmtree(orphan)
        with self._db() as db:
            running = [r for (r,) in db.execute("SELECT run_id FROM runs WHERE status = 'running'")]
        for run_id in sorted(set(running) - live):
            folder = self.root / run_id
            if not folder.is_dir():
                self._set(run_id, "aborted")
            elif _verified(folder):
                _seal_folder(folder)
                self._set(run_id, "sealed")
            else:  # decision 2026-11-04, #247: kept for inspection, never read as a result
                moved = folder.rename(self.root / f".aborted-{run_id}")
                self._set(run_id, "aborted", moved)


def _verified(folder: Path) -> bool:
    """The folder holds exactly the outputs its manifest lists, with their physical hashes."""
    try:
        manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
        outputs = {k: v["physical_sha256"] for k, v in manifest["outputs"].items()}
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return False
    files = _files(folder)
    sealed = files.pop("SEALED", None)
    if sealed is not None and sealed.read_text(encoding="utf-8") != _sha256(
        folder / "manifest.json"
    ):
        return False
    files.pop("manifest.json")
    files.pop(".SEALED.tmp", None)  # a seal killed while it was written
    return outputs == {k: _sha256(p) for k, p in files.items()}


def _seal_folder(folder: Path) -> str:
    """Files read-only (`chmod a-w`), then `SEALED` = sha256 of `manifest.json`, written last."""
    for path in _files(folder).values():
        path.chmod(path.stat().st_mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))
    _boundary("readonly")
    digest = _sha256(folder / "manifest.json")
    seal = folder / "SEALED"
    if not seal.exists():
        tmp = folder / ".SEALED.tmp"
        tmp.unlink(missing_ok=True)
        tmp.write_text(digest, encoding="utf-8")
        tmp.chmod(0o444)
        tmp.rename(seal)
    _boundary("sealed")
    return digest


class RunTxn:
    """One run being written in `runs/.tmp-<uuid>/`; `seal()` or `abort()` ends it."""

    def __init__(
        self,
        store: RunStore,
        run_id: str,
        tmp: Path,
        lock: IO[str],
        params: dict[str, object],
        created: datetime,
    ) -> None:
        self.run_id, self._store, self._tmp, self._lock = run_id, store, tmp, lock
        self._params, self._created = params, created
        self._manifest: dict[str, object] = {}
        self._state = "open"  # open → renamed → sealed, or open → aborted

    def _out(self, rel: str) -> Path:
        if self._state != "open":
            raise RuntimeError(f"run {self.run_id} is already {self._state}")
        if not rel or Path(rel).is_absolute() or ".." in Path(rel).parts:
            raise ValueError(f"output name {rel!r} must stay inside the run folder")
        path = self._tmp / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def write_table(self, name: str, table: object) -> None:
        """Parquet as 5.9.4 says; anything but an Arrow table is refused (no pickle, 2.6)."""
        if not isinstance(table, pa.Table):
            raise TypeError(f"{name}: run tables are pyarrow Tables, not {type(table).__name__}")
        pq.write_table(
            table,
            self._out(f"{name}.parquet"),
            compression="zstd",
            compression_level=3,
            row_group_size=131_072,
            write_statistics=True,
            use_dictionary=[f.name for f in table.schema if pa.types.is_string(f.type)],
        )
        _boundary("written")

    def capture_sources(
        self, paths: Iterable[Path], *, project: Path | None = None, entry: Path | None
    ) -> None:
        """5.9.3: the files inside `project` (paths kept), its toml and lock, params, git state.

        `entry` is the file the run started from (#283): one outside `project` goes to
        `source/_entry/<name>`, and the manifest's `source.entry` is its path under `source/`.
        `None` (an interactive session) warns; an entry file or engine lock that cannot be
        copied aborts the run.
        """
        try:
            self._capture(paths, Path(project or Path.cwd()).resolve(), entry)
        except OSError:
            self.abort()
            raise

    def _capture(self, paths: Iterable[Path], project: Path, entry: Path | None) -> None:
        lock = _engine_lock()
        if entry is not None and not Path(entry).is_file():
            raise FileNotFoundError(f"{entry}: the run's entry file is not a file")
        source = self._out("source/params.json").parent
        found = {Path(p).resolve() for p in paths}
        rel_entry = outside = None
        if entry is not None:
            entry = Path(entry).resolve()
            found.add(entry)
            if entry.is_relative_to(project):
                rel_entry = entry.relative_to(project).as_posix()
            else:
                outside, rel_entry = entry, f"_entry/{entry.name}"
        else:
            warnings.warn(
                f"run {self.run_id}: no entry file, so `rerun` cannot run it", stacklevel=3
            )
        self._manifest["source"] = {"entry": rel_entry}
        for path in sorted(found):
            if path.is_relative_to(project) and path.is_file():  # installed packages stay out
                shutil.copy2(path, self._out(f"source/{path.relative_to(project).as_posix()}"))
        if outside is not None:
            if (source / str(rel_entry)).exists():  # a project file of that path was copied
                raise FileExistsError(f"{outside}: source/{rel_entry} is a project file already")
            shutil.copy2(outside, self._out(f"source/{rel_entry}"))
        for name in ("nexusbt.toml", "uv.lock"):
            if (project / name).is_file():
                shutil.copy2(project / name, source / name)
        (source / "engine-uv.lock").write_bytes(lock)
        (source / "params.json").write_text(canonical_json(self._params), encoding="utf-8")
        git = {"head": _git(project, "rev-parse", "HEAD")}
        git["status"] = _git(project, "status", "--porcelain")
        (source / "git.json").write_text(canonical_json(git), encoding="utf-8")

    def set_manifest(self, fields: Mapping[str, object]) -> None:
        self._manifest.update(fields)

    def seal(self) -> RunRecord:
        """Manifest, rename, read-only, `SEALED` last; a failure before the rename aborts."""
        if self._state != "open":
            raise RuntimeError(f"run {self.run_id} is already {self._state}")
        final = self._store.root / self.run_id
        try:
            outputs = {k: {"physical_sha256": _sha256(p)} for k, p in _files(self._tmp).items()}
            manifest = {"environment": environment(_engine_lock()), **self._manifest}
            manifest |= {"schema_version": "nexusbt-run/2", "outputs": outputs}
            value = value_hash(manifest)  # a NaN in the manifest fails here, before the rename
            manifest["created_at"] = self._created.isoformat()
            text = json.dumps(manifest, sort_keys=True, indent=2, ensure_ascii=False)
            with (self._tmp / "manifest.json").open("w", encoding="utf-8") as f:
                f.write(text + "\n")
                f.flush()
                os.fsync(f.fileno())
            _boundary("manifest")
            self._tmp.rename(final)
        except BaseException:
            self.abort()
            raise
        self._state = "renamed"  # from here a failure is left to seal recovery, not aborted
        _boundary("renamed")
        digest = _seal_folder(final)
        self._store._set(self.run_id, "sealed")
        self._state = "sealed"
        self._release()
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
        self._release()

    def _release(self) -> None:
        Path(self._lock.name).unlink(missing_ok=True)
        self._lock.close()


def _git(project: Path, *args: str) -> str | None:
    try:
        done = subprocess.run(  # noqa: S603 - fixed arguments, no shell
            ["git", "-C", str(project), *args],  # noqa: S607 - git from PATH, as 5.9.3 runs it
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    # rstrip only: the first `status --porcelain` line starts with a meaningful space
    return done.stdout.rstrip("\n") if done.returncode == 0 else None
