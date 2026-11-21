"""The transformations of spec 8.3's metamorphic table, each done in place on a copy of a
synthetic package that the test made with `shutil.copytree` (#255's Decisions, 2026-11-21:
`test_fixtures_are_synthetic` traces a snapshot's path inside one module, so the copy is the
test's and the change is this module's). The generator has no argument that makes them.

Each transformation gives the package its own `snapshot_id` (it is opened beside the original
in one process) and rewrites the file sizes and the hashes.
"""

from __future__ import annotations

import json
import math
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from nexusbt.testing import _synth_package as pk
from nexusbt_tds.hash import write_hashes

#: M-SCALE's "all raw prices of one instrument times k, volume times 1/k, factors unchanged":
#: each dataset's columns and the power of k each is multiplied by. A cash amount per share is
#: a raw price too, and with its reference price times k a dividend's `price_factor` stays as
#: it is; `cum_factor_*`, `price_factor`, `value_traded` (price times volume) and
#: `share_counts` are not changed (8.3 names prices and volume).
PRICES = {
    "bars_1d": {"open": 1, "high": 1, "low": 1, "close": 1, "volume": -1},
    "tradability_daily": {"up_limit_price": 1, "down_limit_price": 1, "reference_price": 1},
    "corporate_actions": {"cash_per_share": 1, "factor_ref_price": 1},
    "delistings": {"ref_price": 1},
}


def scale_prices(root: Path, instrument: str, k: float) -> None:
    """M-SCALE on `instrument` with `k`, a power of two, so that every product is exact."""
    if not (k > 0 and math.log2(k).is_integer()):
        raise ValueError(f"k is a power of two, not {k}")

    def change(columns: Mapping[str, int]) -> Callable[[pa.Table], pa.Table]:
        def scaled(rows: pa.Table) -> pa.Table:
            hit = pc.equal(rows["instrument_id"], instrument)
            for column, power in columns.items():
                at, old = rows.schema.get_field_index(column), rows[column]
                new = pc.multiply(old, pa.scalar(k**power, old.type))
                rows = rows.set_column(at, rows.schema.field(at), pc.if_else(hit, new, old))
            return rows

        return scaled

    _rewrite(root, {name: change(columns) for name, columns in PRICES.items()},
             f"scaled-{instrument.replace(':', '_')}-2e{int(math.log2(k))}")  # fmt: skip


def rows_of(root: Path, name: str) -> list[dict[str, Any]]:
    """Every row of dataset `name`, its files in the manifest's order."""
    manifest = json.loads((root / "tds.json").read_text(encoding="utf-8"))
    (entry,) = (d for d in manifest["datasets"] if d["name"] == name)
    return [r for f in entry["files"] for r in pq.read_table(root / f["path"]).to_pylist()]


def _rewrite(root: Path, changes: Mapping[str, Callable[[pa.Table], pa.Table]], tag: str) -> None:
    """Apply `changes[name]` to each file of dataset `name`, write back the files it changed with
    their rows and sizes, read a changed dataset's coverage again (keeping each market's
    `processed_through_session`), and give the package the id `<id>-<tag>` and new hashes."""
    manifest = json.loads((root / "tds.json").read_text(encoding="utf-8"))
    for entry in manifest["datasets"]:
        if entry["name"] not in changes:
            continue
        changed = False
        for f in entry["files"]:
            rows = pq.read_table(part := root / f["path"])
            new = changes[entry["name"]](rows)
            if new.equals(rows):
                continue
            pq.write_table(new, part)
            f.update(rows=new.num_rows, bytes=part.stat().st_size)
            changed = True
        if changed:
            _cover(root, entry)
    manifest["snapshot_id"] = f"{manifest['snapshot_id']}-{tag}"
    (root / "tds.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    write_hashes(root)


def _cover(root: Path, entry: dict[str, Any]) -> None:
    """`entry`'s coverage read again from its files, as the generator writes it."""
    if "coverage" not in entry:
        return
    parts: dict[str | None, list[pa.Table]] = {}
    for f in entry["files"]:
        market = next((p[7:] for p in Path(f["path"]).parts if p.startswith("market=")), None)
        parts.setdefault(market, []).append(pq.read_table(root / f["path"]))
    new = pk._coverage({m: pa.concat_tables(t) for m, t in parts.items()}).get("coverage", {})
    for market, held in entry["coverage"].get("by_market", {}).items():
        if "processed_through_session" in held:
            new.setdefault("by_market", {}).setdefault(market, {})["processed_through_session"] = (
                held["processed_through_session"]
            )
    entry["coverage"] = new
