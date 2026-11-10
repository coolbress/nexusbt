"""`build_manifest(path) -> Manifest`: a tds.json draft for a folder of Parquet files (TDS 8.1).

The draft holds what the files say: the datasets (the folder above the first `key=value` part,
named by the files' `tds.dataset` when they agree), each file's rows, bytes and sha256, the
physical hash, and a dataset's value hash where its kind and key are known. What the files do
not say is a person's (#258 Decisions): `profiles`, `id_namespaces`, `markets` and a `kind` no
schema file names are left out, so `tds check` reports each as TDS-M003; `availability` is
written `"TODO"`, which is TDS-M014; `TODO`, the first field, lists these with the parameters
and descriptions to add. A tds.json that is already there is never replaced.
"""

from __future__ import annotations

import datetime as dt
import json
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


def build_manifest(path: Path) -> Manifest:
    """Write `<path>/tds.json` as a draft and return it; `ManifestError` when one is there, the
    folder has no Parquet file or a file cannot be read."""
    root = Path(path)
    if (root / MANIFEST).exists():
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
    datasets, sha256, created_by = [], {}, ""
    for folder, paths in groups.items():
        files, said = [], set()
        for rel in paths:
            try:
                meta = pq.read_metadata(root / rel)
            except (OSError, pa.ArrowException) as exc:
                raise ManifestError(f"{rel} is not read as Parquet: {exc}") from None
            keys = {k.decode(): v.decode() for k, v in (meta.metadata or {}).items()}
            said.add((keys.get("tds.dataset"), keys.get("tds.schema_version")))
            created_by = created_by or meta.created_by
            sha256[rel] = file_sha256(root / rel)
            files.append({"path": rel, "rows": meta.num_rows,
                          "bytes": (root / rel).stat().st_size, "sha256": sha256[rel]})  # fmt: skip
        name, schema_version = said.pop() if len(said) == 1 else (None, None)  # 3.7, when one
        name = name or folder.replace("/", "_")
        kind = next((k for k in (folder, name) if k in schemas), None)
        entry: dict[str, Any] = {"name": name, "kind": kind, "path": folder,
                                 "schema_version": schema_version or "1.0"}  # fmt: skip
        if kind is None:
            del entry["kind"]
            was = todo.get("datasets[].kind", "one of the TDS 5 kinds, for")
            todo = {"datasets[].kind": f"{was} {name}", **todo}
        if kind not in TIMELESS:
            entry["availability"] = "TODO"
        entry |= {"rows": sum(f["rows"] for f in files), "files": files}
        try:
            spill = spill_folder(root, None)
            entry["value_sha256"], values = dataset_hashes(root, entry, spill, [])
            for f in files:
                f["value_sha256"] = values[f["path"]]
        except (HashError, OSError, KeyError, TypeError, ValueError, pa.ArrowException):
            pass  # no kind or params yet, or rows that are not the kind's: `tds hash --write`
        datasets.append(entry)
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
