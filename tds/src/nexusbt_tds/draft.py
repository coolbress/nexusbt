"""`build_manifest(path) -> Manifest`: a tds.json draft for a folder of Parquet files (TDS 8.1).

The draft holds what the files say: the datasets (the folder above the first `key=value` part;
in it one dataset per `tds.dataset` the files state, and among the files that state none, or
state the kind and are under several `freq=` values, one per
`freq=` value, named `<folder>_<value>` with `params.freq`, as TDS 4.2 lists `bars_1d` (#371);
`schema_version` theirs or else `1.0`, the only one there is), each file's rows, bytes and
sha256, the physical hash, and a dataset's value hash where its kind and key are known. What the
files do not say is a person's (#258 Decisions): `profiles`, `id_namespaces`, `markets` and a
`kind` no schema file names are left out, so `tds check` reports each as TDS-M003;
`availability` is written `"TODO"`, which is TDS-M014; `TODO`, the first field, lists these with
the parameters and descriptions to add, and a folder that mixes partition keys, to split by hand.
A tds.json that is already there is never replaced.
"""

from __future__ import annotations

import datetime as dt
import json
import struct
from importlib.metadata import version
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from .check import TIMELESS
from .hash import HASH_SPEC, HashError, _lines, dataset_hashes, file_sha256, spill_folder
from .manifest import MANIFEST, Manifest, ManifestError
from .schemas.verify import dictionary_schemas, load_schemas

_TODO = {
    "profiles": "the profiles this package follows, such as [\"tds:minimal-daily@1.0\"] (TDS 7)",
    "id_namespaces": "each id namespace used, with a description (TDS 4.2)",
    "markets": "each market's calendar_id, currency and timezone (TDS 3.8)",
    "datasets[].availability": "replace each \"TODO\" with the dataset's 6.2 rule or form",
    "datasets[].params": "the kind's parameters, such as freq and price_basis for bars (TDS 5)",
    "datasets[].columns": "optional: each column's unit and description (TDS 4.2)",
    "hashes": "run `tds hash --write` once the fields above are in: a dataset's value hash "
              "needs its kind and params, the semantic hash covers every field above",
}  # fmt: skip


def _own(folder: str, files: list[dict[str, Any]], others: list[str]) -> str:
    """The path of a dataset the files name: `folder`, or when it holds another dataset's files
    too, the first folder below it that holds all of `files` and none of `others`."""
    dirs = files[0]["path"].split("/")[:-1]
    for depth in range(folder.count("/") + 2, len(dirs) + 1 if others else 0):
        below = "/".join(dirs[:depth]) + "/"
        if not all(f["path"].startswith(below) for f in files):
            break
        if not any(other.startswith(below) for other in others):
            return below[:-1]
    return folder


def build_manifest(path: Path) -> Manifest:
    """Write `<path>/tds.json` as a draft and return it; `ManifestError` when one is there, the
    folder has no Parquet file or a file cannot be read."""
    root = Path(path)
    if (root / MANIFEST).exists() or (root / MANIFEST).is_symlink():  # a link to nowhere too
        raise ManifestError(f"{MANIFEST} is already there in {root}; it is not replaced")
    groups: dict[str, list[str]] = {}
    for file in sorted(p for p in root.rglob("*.parquet") if p.is_file() and not p.is_symlink()):
        parts = file.relative_to(root).parts
        above = [p for p in parts[:-1] if "=" not in p]
        whole = len(above) == len(parts) - 1 or "=" in parts[len(above)]
        if not above or not whole:  # at the top, or a plain folder under a `key=value` one
            raise ManifestError(f"{'/'.join(parts)}: a dataset's files are in a folder of its own,"
                                " `key=value` partition folders below it (TDS 3.6)")  # fmt: skip
        groups.setdefault("/".join(above), []).append("/".join(parts))
    if not groups:
        raise ManifestError(f"no Parquet file under {root}")
    schemas, todo = load_schemas() | dictionary_schemas(), dict(_TODO)
    datasets, sha256, created_by, mixed = [], {}, "", []
    versions: dict[str, str | None] = {}
    split: list[tuple[str, str | None, str, dict[str, str], list[dict[str, Any]]]] = []
    for folder, paths in groups.items():
        named: dict[str | None, list[dict[str, Any]]] = {}
        for rel in paths:
            try:
                meta = pq.read_metadata(root / rel)
            except (OSError, pa.ArrowException) as exc:
                raise ManifestError(f"{rel} is not read as Parquet: {exc}") from None
            keys = meta.metadata or {}  # only these two are read; any other may be bytes
            name, versions[rel] = (keys.get(k, b"").decode("utf-8", "replace") or None
                                   for k in (b"tds.dataset", b"tds.schema_version"))  # fmt: skip
            created_by = created_by or meta.created_by
            sha256[rel] = file_sha256(root / rel)
            named.setdefault(name, []).append({"path": rel, "rows": meta.num_rows,
                "bytes": (root / rel).stat().st_size, "sha256": sha256[rel]})  # fmt: skip
        # #371 Decisions: (1) each name the files state is a dataset; among the files with none,
        # (2) `freq=` first is one dataset per value, (3) any other mix of first keys, or (4) of
        # files in the folder itself with partition folders, stays one and is said in `TODO`;
        # (5) the kind as the name says no more than the folder, so over several `freq=` it is (2)
        depth = folder.count("/") + 1
        kind_named = {f["path"].split("/")[depth] for f in named.get(folder, [])}
        if len(kind_named) > 1 and all(p.startswith("freq=") for p in kind_named):
            named[None] = sorted(named.pop(None, []) + named.pop(folder), key=lambda f: f["path"])
        rest = named.pop(None, [])
        first = [f["path"].split("/")[depth:-1][:1] for f in rest]  # [] in the folder itself
        first = [p[0] if p else "" for p in first]
        keys = sorted({p.split("=")[0] for p in first if "=" in p})
        mix = ["files directly in it"] * ("" in first and bool(keys))
        mix += [f"the partition key{'s' * (len(keys) > 1)} {', '.join(keys)}"] * bool(keys)
        if rest and all(p.startswith("freq=") and p != "freq=" for p in first):
            for part in sorted(set(first)):
                files = [f for f, p in zip(rest, first, strict=True) if p == part]
                value = part.split("=", 1)[1]
                split.append((folder, f"{folder.replace('/', '_')}_{value}", f"{folder}/{part}",
                              {"freq": value}, files))  # fmt: skip
        elif rest:
            split.append((folder, None, folder, {}, rest))
            mixed += [f"{folder} mixes {' and '.join(mix)}"] * (len(keys) > 1 or len(mix) > 1)
        for name, files in named.items():
            others = [rel for rel in paths if rel not in {f["path"] for f in files}]
            split.append((folder, name, _own(folder, files, others), {}, files))
    for folder, stated, own, params, files in split:
        name = stated or folder.replace("/", "_")
        kind = next((k for k in (folder, name) if k in schemas), None)
        said = {versions[f["path"]] for f in files}
        schema_version = said.pop() if len(said) == 1 else None  # 3.7, when the files agree
        entry: dict[str, Any] = {"name": name, "kind": kind, "path": own,
                                 "schema_version": schema_version or "1.0"}  # fmt: skip
        if kind is None:
            del entry["kind"]
            was = todo.get("datasets[].kind", "one of the TDS 5 kinds, for")
            todo = {"datasets[].kind": f"{was} {name}", **todo}
        if params:
            entry["params"] = params
        if kind not in TIMELESS:
            entry["availability"] = "TODO"
        entry |= {"rows": sum(f["rows"] for f in files), "files": files}
        try:
            spill = spill_folder(root, None)
            entry["value_sha256"], values = dataset_hashes(root, entry, spill, [])
            for f in files:
                f["value_sha256"] = values[f["path"]]
        except (HashError, OSError, LookupError, TypeError, ValueError, AttributeError,
                ArithmeticError, struct.error, pa.ArrowException):  # fmt: skip
            pass  # no kind or params yet, or rows that are not the kind's: `tds hash --write`
        datasets.append(entry)
    if mixed:  # first in the list: the entry is to be split before its other fields are filled
        todo = {"datasets[] to split": f"{'; '.join(mixed)}; a dataset has one layout (TDS 3.6),"
                " so list each layout's files as a dataset of its own", **todo}  # fmt: skip
    names = [d["name"] for d in datasets]
    if twice := sorted({n for n in names if names.count(n) > 1}):
        raise ManifestError(f"two folders give the dataset name {', '.join(twice)}; a dataset's"
                            " files are in one folder, under one name")  # fmt: skip
    created = dt.datetime.now(dt.UTC).replace(microsecond=0)
    draft = {
        "TODO": [f"{field}: {what}" for field, what in todo.items()],
        "tds_version": "1.0", "name": root.resolve().name,
        "created": created.isoformat().replace("+00:00", "Z"),
        "snapshot_id": created.strftime("%Y%m%d-%H%M%S"),
        "producer": {"name": "nexusbt-tds manifest build", "version": version("nexusbt-tds")},
        "datasets": sorted(datasets, key=lambda d: d["name"]),
        "hashes": {"hash_spec": HASH_SPEC, "physical_sha256": _lines(sha256)},
        "writer": {"name": created_by},
    }  # fmt: skip
    (root / MANIFEST).write_text(json.dumps(draft, indent=2, ensure_ascii=False) + "\n", "utf-8")
    return Manifest(root, draft)
