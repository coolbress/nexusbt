"""The conformance packages: per check code, a package raising only that code (TDS 8.5, 8.4a).

`python tds/conformance/build.py [OUT]` writes them to `OUT/<code>/{pass,fail}/` (default: this
folder). They are generated, never edited by hand. These are manifest-level packages: a data file
holds placeholder bytes, since that level reads only sizes; the schema level (T0.13c) writes
Parquet.
"""

from __future__ import annotations

import copy
import json
import shutil
import sys
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


def _set(key: str, value: Any, *, in_bars: bool = False) -> Change:
    """Set a top-level field of tds.json, or with `in_bars` a field of the bars dataset."""

    def change(m: dict[str, Any], files: Files) -> None:
        (bars(m) if in_bars else m)[key] = value

    return change


def _move_bars(path: str) -> Change:
    """List the bars file at `path`; the file moves with it unless `path` leaves the package."""

    def change(m: dict[str, Any], files: Files) -> None:
        bars(m)["files"][0]["path"] = path
        content = files.pop(BARS)
        if not path.startswith(("/", "..")):
            files[path] = content

    return change


def _keep(m: dict[str, Any], files: Files) -> None:
    """The base package, unchanged."""


#: Code → (pass change, fail change). M005 and M011 are warnings: their fail package warns.
CASES: dict[str, tuple[Change, Change]] = {
    "TDS-M001": (_keep, lambda m, f: m.clear()),  # `[]` is written, see write()
    "TDS-M002": (_set("tds_version", "1.4"), _set("tds_version", "2.0")),
    "TDS-M003": (_keep, lambda m, f: m.pop("snapshot_id")),
    "TDS-M004": (_keep, lambda m, f: f.pop(BARS)),
    "TDS-M005": (_keep, lambda m, f: f.update({"notes.txt": b"not listed\n"})),
    "TDS-M006": (_keep, lambda m, f: f.update({BARS: f[BARS] + b"!"})),
    "TDS-M007": (
        _set("profiles", ["tds:minimal-daily"]),
        _set("profiles", ["tds:no-such-profile@1.0"]),
    ),
    "TDS-M008": (
        _set("profiles", ["tds:minimal-daily@1.0", "tds:fx@1.0"]),
        _set("profiles", ["tds:minimal-daily@1.0", "tds:alt-events@1.0"]),
    ),
    "TDS-M009": (
        _set("schema_version", "1.0", in_bars=True),
        _set("schema_version", "2.0", in_bars=True),
    ),
    "TDS-M010": (_keep, _move_bars(BARS.replace("market=US", "market=ZZ"))),
    "TDS-M011": (
        _set("schema_version", "1.0", in_bars=True),
        _set("schema_version", "1.9", in_bars=True),
    ),
    "TDS-M012": (_move_bars(BARS.replace("year=", "./year=")), _move_bars("../outside.parquet")),
    "TDS-M013": (_keep, lambda m, f: bars(m)["files"].append(dict(bars(m)["files"][0]))),
    "TDS-M014": (
        _set("availability", {"rule": "ts_end+PT15M"}, in_bars=True),
        _set("availability", {"rule": "ts_end_when_ready"}, in_bars=True),
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


def build(out: Path) -> None:
    for code in CASES:
        for side in ("pass", "fail"):
            shutil.rmtree(out / code / side, ignore_errors=True)
            write(out / code / side, *copy.deepcopy(package(code, side)))


if __name__ == "__main__":
    build(Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent)
