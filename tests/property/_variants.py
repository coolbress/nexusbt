"""The transformations of spec 8.3's metamorphic table, each done in place on a copy of a
synthetic package that the test made with `shutil.copytree` (#255's Decisions, 2026-11-21:
`test_fixtures_are_synthetic` traces a snapshot's path inside one module, so the copy is the
test's and the change is this module's). The generator cannot make these packages itself:
an injected ratio-1 split also halts the instrument on its ex-date, and a ninth instrument
draws other rows for the first eight (#255's Decisions, facts 3 and 4).

Each transformation gives the package its own `snapshot_id` (it is opened beside the original
in one process) and rewrites the file sizes and the hashes.
"""

from __future__ import annotations

import datetime as dt
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


def append_action(root: Path, row: Mapping[str, Any]) -> None:
    """One row more in `corporate_actions`, in its schema's sort order (`instrument_id`,
    `ex_date`, `event_id`; TDS-K002), every other row and dataset as it was. The dataset is in
    one file, as the generator writes it; with more, the row would be added to each."""
    manifest = json.loads((root / "tds.json").read_text(encoding="utf-8"))
    (entry,) = (d for d in manifest["datasets"] if d["name"] == "corporate_actions")
    if len(entry["files"]) != 1:
        raise ValueError(f"corporate_actions is in {len(entry['files'])} files, not one")

    def change(rows: pa.Table) -> pa.Table:
        added = pa.concat_tables([rows, pa.Table.from_pylist([dict(row)], schema=rows.schema)])
        return added.sort_by([(c, "ascending") for c in ("instrument_id", "ex_date", "event_id")])

    _rewrite(root, {"corporate_actions": change}, f"action-{row['event_id'].replace(':', '_')}")


def neutral_split(root: Path, instrument: str, ex_date: dt.date) -> dict[str, Any]:
    """M-SPLIT-NEUTRAL's fake split of ratio 1.0 on `instrument` at `ex_date`, with the columns
    the generator writes for an injected split (4.8 `EventSpec`): declared and announced 14
    days before (06:30 UTC), effective at the ex-date's midnight UTC, the reference price the
    close of the session before, and an `event_id` no row of the package has."""
    actions = rows_of(root, "corporate_actions")
    bars = [r for r in rows_of(root, "bars_1d")
            if r["instrument_id"] == instrument and r["session_date"] < ex_date]  # fmt: skip
    before = max(bars, key=lambda r: r["session_date"])
    declared = ex_date - dt.timedelta(days=14)
    taken = {r["event_id"] for r in actions}
    free = (f"{instrument.split(':')[0]}:E9{n:05d}" for n in range(100_000))
    event_id = next(e for e in free if e not in taken)
    return {
        "event_id": event_id, "instrument_id": instrument, "kind": "split", "ex_date": ex_date,
        "ts_effective": dt.datetime.combine(ex_date, dt.time(), dt.UTC), "record_date": None,
        "declared_date": declared, "pay_date": ex_date, "pay_date_status": "observed",
        "resolution_date": None, "resolution_body": None,
        "ts_announced": dt.datetime.combine(declared, dt.time(6, 30), dt.UTC),
        "ts_terms_available": None, "ratio_num": 1, "ratio_den": 1, "ratio_new_per_old": 1.0,
        "cash_per_share": None, "currency": None, "gross_or_net": None, "price_factor": 1.0,
        "share_factor": 1.0, "affects": "split_and_total", "factor_method": "ratio",
        "factor_ref_price": before["close"], "revision_of": None, "status": "effective",
        "source": "nexusbt-synth",
    }  # fmt: skip


def drop_instrument(root: Path, instrument: str) -> None:
    """M-DUMMY read backwards: every row of `instrument` deleted from each dataset that has an
    `instrument_id` column, every other row as it was (the generator cannot add a ninth name to
    eight without drawing other rows for them; #255's Decisions, fact 3)."""
    manifest = json.loads((root / "tds.json").read_text(encoding="utf-8"))
    schemas = {d["name"]: pq.read_schema(root / d["files"][0]["path"])
               for d in manifest["datasets"] if d["files"]}  # fmt: skip
    names = [name for name, schema in schemas.items() if "instrument_id" in schema.names]

    def kept(rows: pa.Table) -> pa.Table:
        return rows.filter(pc.not_equal(rows["instrument_id"], instrument))

    _rewrite(root, dict.fromkeys(names, kept), f"without-{instrument.replace(':', '_')}")


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
