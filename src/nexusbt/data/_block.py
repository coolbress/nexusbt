"""A market's dense block of daily bars (spec 5.3.1, 4.6), T1.4 (#236)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from nexusbt.contracts import ID_COLUMN as ID
from nexusbt.data._calendar import bars_availability

if TYPE_CHECKING:
    from numpy.typing import NDArray

    from nexusbt.data._calendar import Calendar
    from nexusbt_tds.manifest import Manifest

#: `obs_status` codes of a block's cells, by position (TDS 5.5); -1, the last, has no bar.
OBS_STATUS = np.array(["traded", "no_trade", "halted", "missing", "absent"])
#: Price cells NaN in a halted or missing session (3.2); `no_trade` keeps its reference close.
_PRICES = frozenset({"open", "high", "low", "close"})
_INTEGER = frozenset({"i8", "i16", "i32", "i64"})
#: Columns a bars file may lack: the block reads them when present (TDS 5.5, F-03).
_OPTIONAL = ("obs_status", "ts_end", "ts_available")


@dataclass(frozen=True, slots=True, eq=False)
class MarketBlock:
    """Rows = sessions, columns = the market's equity, non-synthetic instruments listed in the
    chunk (5.3.1). Every array is `(rows, columns)`: `values[field]` float64, `exists` the
    listing mask, `obs_status` codes into `OBS_STATUS`, `ts_available` each cell's availability
    instant (NaT without a bar), which a reader compares with `ready(t)` (5.1.2); a late bar
    stays in its session's row. The first `overlap` rows are the previous chunk's tail."""

    market: str
    dates: NDArray[np.datetime64]
    overlap: int
    instrument_ids: tuple[str, ...]
    values: Mapping[str, NDArray[np.float64]]
    exists: NDArray[np.bool_]
    obs_status: NDArray[np.int8]
    ts_available: NDArray[np.datetime64]


def partition_values(path: str, partitioning: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """A file's partition values, read from its path (4.6; they are not in the file): integer
    types as `int`, every other value as its text."""
    types = {p.get("name"): p.get("type") for p in partitioning}
    parts = dict(p.split("=", 1) for p in Path(path).parent.parts if "=" in p)
    return {k: int(v) if types.get(k) in _INTEGER else v for k, v in parts.items()}


def build_block(
    manifest: Manifest, calendar: Calendar, fields: Sequence[str], sessions: object, overlap: int
) -> MarketBlock:
    """The block of `fields` over the calendar rows from the first to the last of `sessions`,
    after up to `overlap` rows before them, the previous chunk's tail (5.3.1). The columns
    are the instruments listed in `sessions`; the overlap rows show those columns."""
    given = np.asarray(sessions, dtype="datetime64[D]")
    ends = np.searchsorted(calendar.dates, given[[0, -1]]) if len(given) else (-1, -1)
    first, last = (int(e) for e in ends)
    if not 0 <= first <= last < len(calendar.dates) or (
        (calendar.dates[[first, last]] != given[[0, -1]]).any()
    ):
        raise ValueError(f"sessions {given[:1]}..{given[-1:]} are not {calendar.market} sessions")
    start = max(0, first - overlap)
    dates = calendar.dates[start : last + 1]
    kinds = {d["kind"]: d for d in reversed(manifest.datasets)}  # the first of each kind
    ids, listed, delisted = _axis(manifest, kinds["instruments"], calendar.market, given)
    n, shape = len(ids), (len(dates), len(ids))
    exists = (listed[None, :] <= dates[:, None]) & ~(delisted[None, :] < dates[:, None])
    values = {f: np.full(shape, np.nan) for f in fields}
    status = np.full(shape, -1, dtype=np.int8)
    available = np.full(shape, np.datetime64("NaT", "us"))
    bars = kinds["bars"]
    source, _ = bars_availability(bars, str(manifest.data["snapshot_id"]))
    wanted = [ID, "session_date", "close", *fields, *_OPTIONAL]
    wanted += [source] if source != "ts_close" else []  # ts_close is the calendar's
    for path in _files(bars, calendar.market, dates) if n else ():
        rows, cols, table = _cells(manifest.root / path, ids, dates, wanted)
        for f in fields:
            values[f][rows, cols] = table[f].to_numpy(zero_copy_only=False).astype(np.float64)
        if "obs_status" in table.column_names:
            codes = pc.index_in(table["obs_status"], pa.array(OBS_STATUS[:-1])).fill_null(-1)
            status[rows, cols] = codes.to_numpy().astype(np.int8)
        else:  # F-03: traded with a price, else no_trade
            status[rows, cols] = np.where(pc.is_valid(table["close"]).to_numpy(), 0, 1)
        available[rows, cols] = _available(source, table, calendar, start + rows)
    status[exists & (status == -1)] = 3  # a listed session without a bar is missing (F-03)
    hidden = (status == 2) | (status == 3)  # halted, missing
    for f in fields:
        values[f][hidden & (f in _PRICES)] = np.nan
        values[f][~exists] = np.nan
    if "volume" in values:
        values["volume"][status == 1] = 0.0  # no_trade (3.2)
    status[~exists] = -1
    return MarketBlock(calendar.market, dates, first - start, ids, values, exists, status,
                       available)  # fmt: skip


def _files(entry: Mapping[str, Any], market: str, dates: NDArray[np.datetime64]) -> list[str]:
    """The bars files that can hold rows of `market` on `dates`, chosen by the path's partition
    values and `files[].stats` alone, no footer opened (4.6, P1)."""
    low, high = str(dates[0]), str(dates[-1])
    chosen = []
    for f in entry["files"]:
        parts = partition_values(f["path"], entry.get("partitioning", []))
        if parts.get("market", market) != market:
            continue
        if "year" in parts and not int(low[:4]) <= int(parts["year"]) <= int(high[:4]):
            continue
        span = f.get("stats", {}).get("session_date")
        if span and (str(span[1]) < low or str(span[0]) > high):
            continue
        chosen.append(f["path"])
    return chosen


def _axis(
    manifest: Manifest, entry: Mapping[str, Any], market: str, given: NDArray[np.datetime64]
) -> tuple[tuple[str, ...], NDArray[np.datetime64], NDArray[np.datetime64]]:
    """The block's columns: `equity ∧ not synthetic` of `market` whose listing period
    `[listed_on, delisted_on]` meets the chunk's own sessions, by `instrument_id` (5.3.1)."""
    tables = [pq.read_table(manifest.root / f["path"]) for f in entry["files"]]
    t = pa.concat_tables(tables)
    keep = pc.and_(pc.equal(t["market"], market), pc.equal(t["asset_class"], "equity"))
    keep = pc.and_(keep, pc.invert(pc.fill_null(t["is_synthetic"], False)))
    t = t.filter(keep).sort_by(ID)
    listed = t["listed_on"].to_numpy(zero_copy_only=False).astype("datetime64[D]")
    delisted = t["delisted_on"].to_numpy(zero_copy_only=False).astype("datetime64[D]")
    meets = (listed <= given[-1]) & ~(delisted < given[0])
    ids = tuple(str(i) for i in np.array(t[ID].to_pylist(), dtype=object)[meets])
    return ids, listed[meets], delisted[meets]


def _cells(
    path: Path, ids: tuple[str, ...], dates: NDArray[np.datetime64], wanted: Sequence[str]
) -> tuple[NDArray[np.intp], NDArray[np.intp], pa.Table]:
    """A file's rows that fall in the block, with their row and column numbers. The
    dictionary of `instrument_id` is mapped to column numbers once, then each row's
    index is looked up in that small table (5.3.1, A-05). `ids` is sorted and not empty."""
    names = set(pq.read_schema(path).names)
    columns = list(dict.fromkeys(c for c in wanted if c in names or c not in _OPTIONAL))
    table = pq.read_table(path, columns=columns, read_dictionary=[ID])
    sorted_ids = np.array(ids, dtype=object)
    cols = []
    for chunk in table[ID].chunks:
        words = np.array(chunk.dictionary.to_pylist(), dtype=object)
        at = np.minimum(np.searchsorted(sorted_ids, words), len(ids) - 1)
        lookup = np.where(sorted_ids[at] == words, at, -1)
        cols.append(lookup[chunk.indices.to_numpy(zero_copy_only=False)])
    col = np.concatenate(cols) if cols else np.zeros(0, np.intp)
    days = table["session_date"].to_numpy(zero_copy_only=False).astype("datetime64[D]")
    row = np.minimum(np.searchsorted(dates, days), len(dates) - 1)
    keep = (col >= 0) & (dates[row] == days)
    picked = np.flatnonzero(keep)
    return row[keep], col[keep], table.take(pa.array(picked))


def _available(
    source: str, table: pa.Table, calendar: Calendar, rows: NDArray[np.intp]
) -> NDArray[np.datetime64]:
    """Each bar's `ts_available` from `bars_availability`'s source (4.6, TDS 6.2): the
    session's `ts_close`, the column as it is, or `ts_end` (a null one is the session close,
    TDS 5.5) plus 5.1.2's delay."""
    close = calendar.ts_close[rows]
    if source == "ts_close":
        return close
    if source == "ts_end" and source not in table.column_names:
        return close + calendar.ready_delay
    stamps: NDArray[np.datetime64] = table[source].to_numpy(zero_copy_only=False)
    stamps = stamps.astype("datetime64[us]")
    if source != "ts_end":
        return stamps
    ended: NDArray[np.datetime64] = np.where(np.isnat(stamps), close, stamps)
    return ended + calendar.ready_delay
