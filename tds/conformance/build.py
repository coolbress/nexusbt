"""The conformance packages: per check code, a package raising only that code (TDS 8.5, 8.4a).

They are generated, never edited by hand. These are manifest-level packages: a data file holds
placeholder bytes, since that level reads only sizes; the schema level (T0.13c) writes Parquet.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

Files = dict[str, bytes]
Package = tuple[dict[str, Any], Files]
Change = Callable[[dict[str, Any], Files], object]

INSTRUMENTS = "instruments/part-00000.parquet"
BARS = "bars/freq=1d/market=US/year=2024/part-00000.parquet"


def base() -> Package:
    """A package that passes the manifest level: `tds:minimal-daily@1.0`, two datasets."""
    files = {INSTRUMENTS: b"placeholder instruments\n", BARS: b"placeholder bars 1d\n"}
    bars_1d = {"params": {"freq": "1d", "price_basis": "raw"}, "availability": {"rule": "ts_end"}}
    datasets: list[tuple[str, str, str, str, dict[str, Any]]] = [
        ("instruments", "instruments", "instruments", INSTRUMENTS, {}),
        ("bars_1d", "bars", "bars/freq=1d", BARS, bars_1d),
    ]
    manifest = {
        "tds_version": "1.0",
        "name": "conformance",
        "created": "2026-11-02T00:00:00Z",
        "snapshot_id": "20261102-000000",
        "producer": {"name": "nexusbt-tds conformance", "hints": {}},
        "profiles": ["tds:minimal-daily@1.0"],
        "id_namespaces": {"XNYS": "synthetic test ids"},
        "markets": {
            "US": {"calendar_id": "XNYS", "currency": "USD", "timezone": "America/New_York"}
        },
        "datasets": [
            {"name": name, "kind": kind, "schema_version": "1.0", "path": path, **extra}
            | {"files": [{"path": file, "rows": 1, "bytes": len(files[file])}]}
            for name, kind, path, file, extra in datasets
        ],
        "hashes": {"hash_spec": "tds-hash-1"},
        "writer": {"name": "nexusbt-tds conformance", "row_group_rows": 1},
    }
    return manifest, files


def bars(m: dict[str, Any]) -> dict[str, Any]:
    dataset: dict[str, Any] = m["datasets"][1]
    return dataset


def _set(key: str, value: Any) -> Change:
    """Set a top-level field of tds.json."""

    def change(m: dict[str, Any], files: Files) -> None:
        m[key] = value

    return change


#: Code → (pass change, fail change); a pass change of `None` keeps the base package.
CASES: dict[str, tuple[Change, Change]] = {
    "TDS-M001": (lambda m, f: None, lambda m, f: m.clear()),  # `[]` is written, see write()
    "TDS-M002": (_set("tds_version", "1.4"), _set("tds_version", "2.0")),
    "TDS-M003": (lambda m, f: None, lambda m, f: m.pop("snapshot_id")),
    "TDS-M007": (
        _set("profiles", ["tds:minimal-daily"]),
        _set("profiles", ["tds:no-such-profile@1.0"]),
    ),
    "TDS-M008": (
        _set("profiles", ["tds:minimal-daily@1.0", "tds:fx@1.0"]),
        _set("profiles", ["tds:minimal-daily@1.0", "tds:alt-events@1.0"]),
    ),
}


def package(code: str, side: str) -> Package:
    manifest, files = base()
    CASES[code][side == "fail"](manifest, files)
    return manifest, files


def write(root: Path, manifest: dict[str, Any], files: Files) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    text = json.dumps(manifest, sort_keys=True) if manifest else "[]"  # one line: a small diff
    (root / "tds.json").write_text(text + "\n", encoding="utf-8")
    for rel, content in sorted(files.items()):
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_bytes(content)
    return root
