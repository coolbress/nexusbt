"""The key of an L0 entry, a market block's (market, column, year) partition (spec 5.3.9).

T1.4 (#236) fixes the key; the cache that stores and reuses entries is T6.12."""

from __future__ import annotations

import datetime as dt
import hashlib
from collections.abc import Mapping
from importlib import metadata
from typing import TYPE_CHECKING, Any

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from nexusbt.contracts import ID_COLUMN as ID
from nexusbt.data._block import partition_values
from nexusbt_tds.actions import chain_digest
from nexusbt_tds.hash import canonical_json, encode_table
from nexusbt_tds.schemas.verify import load_schemas

if TYPE_CHECKING:
    from nexusbt_tds.manifest import Manifest

BLOCK_VERSION = "l0-v4"
#: The resolution metadata of the dataset (5.3.9), as tds.json declares it.
_DATASET_KEYS = ("kind", "schema_version", "params", "availability", "pit_quality", "key")
#: `markets` fields in the key: the stable ones; the watermark changes on every publish.
_MARKET_KEYS = ("calendar_id", "currency", "timezone")
#: The `instruments` fields the block reads for its shape (5.3.9 (a)).
_AXIS = (ID, "listed_on", "delisted_on", "asset_class", "is_synthetic")


def l0_key(manifest: Manifest, market: str, column: str, year: int, edition: str) -> str:
    """sha256 of the canonical JSON of what the block of `column` in (`market`, `year`) depends
    on and nothing else (INV-05): the bars' resolution metadata with the package `policies`
    and the market's stable fields, the sha256 of the partition's files, the market's
    corporate-action chain digest to the year's end, the hash of the axis rows, and the
    market, column, year, edition, block version and engine version."""
    kinds = {d["kind"]: d for d in reversed(manifest.datasets)}  # the first of each kind
    bars, entry = kinds["bars"], manifest.data["markets"][market]
    units = {c["name"]: c["unit"] for c in bars.get("columns", []) if "unit" in c}
    files = sorted(
        (f["path"], f.get("sha256"))
        for f in bars["files"]
        if _holds(partition_values(f["path"], bars.get("partitioning", [])), market, year)
    )
    instruments = _rows(manifest, kinds["instruments"])
    instruments = instruments.filter(pc.equal(instruments["market"], market))
    doc = {
        "resolution": {**{k: bars.get(k) for k in _DATASET_KEYS}, "units": units,
                       "policies": manifest.data.get("policies"),
                       "market": {k: entry[k] for k in _MARKET_KEYS if k in entry}},
        "files": [list(f) for f in files],
        "chains": _chains(manifest, kinds.get("corporate_actions"), instruments, year),
        "axis": _axis(manifest, kinds, instruments, str(entry["calendar_id"]), year),
        "market": market, "column": column, "year": year, "edition": edition,
        "block": BLOCK_VERSION, "engine": metadata.version("nexusbt"),  # = nexusbt.__version__
    }  # fmt: skip
    return hashlib.sha256(canonical_json(doc).encode("utf-8")).hexdigest()


def _holds(parts: Mapping[str, Any], market: str, year: int) -> bool:
    """A file of the (market, year) partition, by its path (4.6)."""
    return parts.get("market", market) == market and int(parts.get("year", year)) == year


def _rows(manifest: Manifest, entry: Mapping[str, Any] | None) -> pa.Table:
    tables = [pq.read_table(manifest.root / f["path"]) for f in (entry or {}).get("files", [])]
    return pa.concat_tables(tables) if tables else pa.table({})


def _chains(
    manifest: Manifest, entry: Mapping[str, Any] | None, instruments: pa.Table, year: int
) -> str:
    """The digest of every version of the market's chains effective by the year's end."""
    events = _rows(manifest, entry)
    if events.num_rows:
        events = events.filter(pc.is_in(events[ID], instruments[ID]))
    return chain_digest(events, dt.date(year, 12, 31)) if events.num_rows else ""


def _axis(
    manifest: Manifest, kinds: Mapping[str, Any], instruments: pa.Table, calendar: str, year: int
) -> str:
    """5.3.9's axis-row hash: (a) the market's `instruments` rows whose `[listed_on,
    delisted_on]` meets the year's sessions, over the fields the block reads; (b) the
    calendar's `calendar_sessions` rows of the year and the whole year before, over every
    column but `calendar_version`; each in TDS 4.5's canonical bytes."""
    schemas = load_schemas()
    sessions = _rows(manifest, kinds["calendar_sessions"])
    sessions = sessions.filter(pc.equal(sessions["calendar_id"], calendar))
    years = pc.year(sessions["session_date"])
    own = sessions.filter(pc.equal(years, year))["session_date"]
    if len(own):
        first, last = pc.min(own), pc.max(own)
        meets = pc.and_(pc.less_equal(instruments["listed_on"], last),
                        pc.invert(pc.fill_null(pc.less(instruments["delisted_on"], first),
                                               False)))  # fmt: skip
        instruments = instruments.filter(meets)
    else:
        instruments = instruments.slice(0, 0)
    sessions = sessions.filter(pc.is_in(years, pa.array([year - 1, year], years.type)))

    def encoded(table: pa.Table, kind: str, names: list[str], key: str) -> str:
        tags = {c.name: str(c.type) for c in schemas[kind].columns}
        return hashlib.sha256(encode_table(table, [(n, tags[n]) for n in names], [key])).hexdigest()

    held = [c.name for c in schemas["calendar_sessions"].columns
            if c.name in sessions.column_names and c.name != "calendar_version"]  # fmt: skip
    return encoded(instruments, "instruments", list(_AXIS), ID) + encoded(
        sessions, "calendar_sessions", held, "session_date"
    )
