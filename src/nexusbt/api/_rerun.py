"""`nx.rerun` (3.8, 5.9.3, 5.9.4; T1.15, #250).

The run's `source/` runs again in a new Python process with `source/` first on `sys.path`, so
the captured helpers come before same-named files of the working folder. Inside that process
`ACTIVE` names the run reproduced: the snapshot opens with each file's sha256 and must have the
recorded semantic hash, the config is `source/nexusbt.toml`, and the run sealed is indexed as
`run_kind = rerun` with `derived_from`. A 6.6 error crosses back to the caller as its class.

A project module outside the project folder (an editable install, 6.5 (6), #577) is not kept in
`source/`: the run records its name and its file's sha256 (5.9.2 `source.outside`), and a rerun
whose module now hashes otherwise, or is gone, is E15 naming the module (#250 Decisions).
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import runpy
import subprocess
import sys
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from nexusbt import contracts
from nexusbt.contracts import NexusBTError, ReplayError, SnapshotError
from nexusbt.data import _package

if TYPE_CHECKING:
    from nexusbt.data import Snapshot


@dataclass(slots=True)
class Replay:
    run_id: str
    source: Path
    manifest: dict[str, Any]
    new_snapshot: bool
    sealed: list[str] = field(default_factory=list)


ACTIVE: Replay | None = None  # set only inside a rerun's new process
_H6 = re.compile(r"-([0-9a-f]{6})(?:-\d+)?$")  # 5.9.1: `…-<h6>`, or `-2`, `-3` after it
#: The new process: `-c`, so this module is imported once, as `api` reads it.
_CHILD = ("import sys; from pathlib import Path; from nexusbt.api import _rerun; a = sys.argv; "
          "sys.exit(_rerun.child(Path(a[1]), Path(a[2]), a[3:] == ['new']))")  # fmt: skip


def read(folder: Path) -> dict[str, Any]:
    return dict(json.loads((folder / "manifest.json").read_text(encoding="utf-8")))


def config_file() -> Path | None:
    return found if ACTIVE and (found := ACTIVE.source / "nexusbt.toml").is_file() else None


def project() -> Path:
    return ACTIVE.source if ACTIVE else Path.cwd().resolve()


def index_columns(kind: str, h6: str) -> dict[str, str]:
    """5.9.5: the run of the reproduced run's kind and inputs (h6) is `run_kind = rerun`; it,
    or with `new_snapshot` a run of that kind, names its origin. Other runs the entry file
    saves are plain runs."""
    if ACTIVE is None or kind != ACTIVE.manifest["kind"]:
        return {}
    if ACTIVE.new_snapshot:
        return {"derived_from": ACTIVE.run_id}
    same = (m := _H6.search(ACTIVE.run_id)) is not None and m[1] == h6
    return {"run_kind": "rerun", "derived_from": ACTIVE.run_id} if same else {}


def sealed(run_id: str) -> None:
    if ACTIVE is not None:
        ACTIVE.sealed.append(run_id)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def outside(modules: Mapping[str, Path], project: Path) -> dict[str, str]:
    """5.9.2 `source.outside`: module name → sha256 of each project module whose file is
    outside `project`, so not in `source/`; a name, never a path (5.9.3 "No local path")."""
    return {name: _sha256(path) for name, path in modules.items()
            if name != "__main__" and path.is_file()
            and not path.resolve().is_relative_to(project)}  # fmt: skip


def _check_outside(replay: Replay) -> None:
    """Each recorded outside module, found as the new process imports it, must hash the same."""
    for name, digest in replay.manifest["source"].get("outside", {}).items():
        failed = False
        try:
            spec = importlib.util.find_spec(name)
        except (ImportError, ValueError):
            spec = None
        except Exception:  # finding a submodule imports its package, whose changed code may raise
            spec, failed = None, True
        file = Path(spec.origin) if spec and spec.origin else None
        if failed:
            how = "changed"
        elif file is None or not file.is_file():
            how = "is missing"
        elif _sha256(file) != digest:
            how = "changed"
        else:
            continue
        raise ReplayError(
            what=f"helper module {name} {how} since run {replay.run_id} and is not kept in "
                 "source/: it is outside the project folder",
            where=f"module {name}", why="a rerun needs the exact code it ran",
            fix=f"restore {name} as it was at the run", more="spec 5.9.2 source.outside",
            subject=f"run {replay.run_id}", layer=f"data — run {replay.run_id} / source",
        )  # fmt: skip


def check_snapshot(opened: Snapshot) -> None:
    """3.8: a rerun reads the data it ran on, confirmed by the semantic hash (E15)."""
    recorded = ACTIVE.manifest.get("snapshot_semantic_hash") if ACTIVE else None
    if ACTIVE and not ACTIVE.new_snapshot and opened.semantic_hash != recorded:
        raise unavailable(ACTIVE.run_id, ACTIVE.manifest, "it has another semantic hash")


def _has_manifest(path: Path) -> bool:
    try:
        return (_package(path) / "tds.json").is_file()
    except (OSError, ValueError):  # `LATEST` unreadable, or naming a folder outside
        return False


def not_opened(error: SnapshotError, path: Path | None = None) -> None:
    """#636 Decisions: on an exact rerun, an E14 about the run's recorded snapshot is E15: its
    layer names that snapshot, or `path`, the package that did not open, has no `tds.json` to
    show it is another (the package moved). Any other E14, and each with `new_snapshot` (a new
    run, 3.8), stays the snapshot's own error."""
    if ACTIVE is None or ACTIVE.new_snapshot:
        return
    recorded = ACTIVE.manifest.get("snapshot_id", "-")
    named = error.layer.startswith(f"data — snapshot {recorded} /")
    if not named and (path is None or _has_manifest(path)):
        return  # another snapshot, or an error raised with no package to look at
    why = "it does not open or its files differ from tds.json (semantic·physical mismatch)"
    raise unavailable(ACTIVE.run_id, ACTIVE.manifest, why) from error


def unavailable(run_id: str, manifest: Mapping[str, Any], why: str) -> ReplayError:
    snapshot = manifest.get("snapshot_id", "-")
    return ReplayError(
        what=f"snapshot {snapshot} is not available: {why}", where=f"run {run_id}",
        why="a rerun needs the exact data it ran on", subject=f"run {run_id}",
        fix="nx.rerun(id, new_snapshot=True) creates a new run",
        more="nx.runs(); tds check snap --level full",
        layer=f"data — snapshot {snapshot} / tds.json / column - / producer -",
    )  # fmt: skip


def child(folder: Path, out: Path, new_snapshot: bool) -> int:
    """The new process: run `folder`'s entry file from its `source/`; write what it sealed."""
    global ACTIVE
    ACTIVE = replay = Replay(folder.name, folder / "source", read(folder), new_snapshot)
    sys.argv = [str(entry := replay.source / replay.manifest["source"]["entry"])]
    # 5.9.3 (1): captured helpers first: the entry's folder, as `python <entry>` puts it, then
    # `source/` and its copy of each import folder inside the project (a `src/` layout)
    here = Path.cwd().resolve()
    found = [Path(p).resolve() for p in sys.path if Path(p).is_absolute()]
    kept = [replay.source / p.relative_to(here) for p in found if p.is_relative_to(here)]
    sys.path[:0] = [str(entry.parent), str(replay.source), *map(str, kept)]
    try:
        if not new_snapshot:  # a new run is not a reproduction: its code is today's (3.8)
            _check_outside(replay)
        try:
            runpy.run_path(str(entry), run_name="__main__")
        except SnapshotError as unread:  # E15 when it is about the run's snapshot (#636)
            not_opened(unread)
            raise
    except NexusBTError as error:
        fields = {"at": error.at, "subject": error.subject, "layer": error.layer, **error.parts}
        out.write_text(json.dumps({"error": {"code": error.code, **fields}}), encoding="utf-8")
        return 1
    out.write_text(json.dumps({"sealed": replay.sealed}), encoding="utf-8")
    return 0


def _error(found: dict[str, Any]) -> NexusBTError:
    code, named = found.pop("code"), vars(contracts).values()
    errors = [c for c in named if isinstance(c, type) and issubclass(c, NexusBTError)]
    return next((c for c in errors if c.code == code), NexusBTError)(**found)


def compare(old: Mapping[str, Any], new: Mapping[str, Any]) -> str:
    """5.9.4: each table of the reproduced run against the new run's, by value and bytes."""
    tables = {k: v for k, v in old["outputs"].items() if not k.startswith("source/")}
    kinds = [h for h in ("value", "physical") if any(f"{h}_sha256" in v for v in tables.values())]
    differ = []
    for name, hashes in sorted(tables.items()):
        got = new["outputs"].get(name, {})
        if which := [h for h in kinds if hashes.get(f"{h}_sha256") != got.get(f"{h}_sha256")]:
            differ.append(f"{name} ({', '.join(which)})")
    if not differ:
        return f"outputs identical ({', '.join(kinds)})"
    # #250 Decisions: a manifest saved before `source.outside` is "not recorded", never `{}`
    unrecorded = "outside" not in old.get("source", {})
    note = "; this run's outside helpers were not recorded" if unrecorded else ""
    return "outputs differ: " + "; ".join(differ) + note


def rerun(folder: Path, *, new_snapshot: bool) -> tuple[str, str]:
    """The new run's id and the comparison line (5.9.4) once `folder`'s run ran again."""
    manifest = read(folder)
    entry = (manifest.get("source") or {}).get("entry")
    if not entry or not (folder / "source" / entry).is_file():
        raise unavailable(folder.name, manifest, f"run {folder.name} kept no entry file in source/")
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "result.json"
        args = [sys.executable, "-c", _CHILD, str(folder), str(out), *(["new"] * new_snapshot)]
        done = subprocess.run(args, check=False)  # noqa: S603 - this interpreter, no shell
        if not out.is_file():
            raise RuntimeError(f"rerun of {folder.name}: the new process ended {done.returncode}")
        result = json.loads(out.read_text(encoding="utf-8"))
    if "error" in result:
        raise _error(result["error"])
    h6 = _H6.search(folder.name)
    runs = [(r, read(folder.parent / r)) for r in result["sealed"]]
    same = [(r, m) for r, m in runs if m["kind"] == manifest["kind"]]
    match = [(r, m) for r, m in same if h6 and (s := _H6.search(r)) and s[1] == h6[1]] or same
    if not match:
        raise RuntimeError(f"rerun of {folder.name}: it sealed no {manifest['kind']} run")
    return match[0][0], compare(manifest, match[0][1])
