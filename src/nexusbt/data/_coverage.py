"""The daily bars' extent per market: what F-02 bounds its sessions by and what the F-03 and
F-15 records count (spec 4.5). TDS 4.3's `coverage` block is optional and may hold
`processed_through_session` alone, so a market whose entry lacks a key, or a package with no
`by_market`, is read from the bars themselves (#564): F-02 is "from the first to the last day
of `bars`", and a file's market is its `market=` partition (4.6), else its instrument's."""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from nexusbt.contracts import ID_COLUMN

#: The keys of a `by_market` entry the engine reads (TDS 4.2's example, D004's keys).
KEYS = frozenset({"first", "last", "rows", "instruments"})


def bars_by_market(
    root: Path, bars: Mapping[str, Any] | None, instruments: Mapping[str, Any] | None
) -> dict[str, dict[str, Any]]:
    """Market → `first`, `last` (`YYYY-MM-DD`), `rows` and `instruments` of the daily bars:
    the declared `coverage.by_market` when every entry has them, else counted from the files."""
    if bars is None:
        return {}
    declared = (bars.get("coverage") or {}).get("by_market") or {}
    if declared and all(e.keys() >= KEYS for e in declared.values()):
        return {m: dict(e) for m, e in declared.items()}
    of: dict[str, str] = {}  # read once, and only for a file without a `market=` partition
    tables = [_with_market(root, f["path"], instruments, of) for f in bars.get("files", [])]
    if not tables:
        return {}
    rows = pa.concat_tables(tables)
    rows = rows.filter(pc.is_valid(rows["market"]))
    grouped = rows.group_by("market").aggregate([
        ("session_date", "min"), ("session_date", "max"), (ID_COLUMN, "count"),
        (ID_COLUMN, "count_distinct")])  # fmt: skip
    return {str(r["market"]): {"first": str(r["session_date_min"]),
                               "last": str(r["session_date_max"]),
                               "rows": int(r[f"{ID_COLUMN}_count"]),
                               "instruments": int(r[f"{ID_COLUMN}_count_distinct"])}
            for r in grouped.to_pylist()}  # fmt: skip


def schedule(calendar_id: str, period: Mapping[str, Any]) -> Any:
    """F-02's sessions of `calendar_id` from `first` to `last`, both included, as the library's
    schedule: it refuses an `end` that is not after `start`, so bars of one day ask it for a day
    more and that day is cut off (#564)."""
    import exchange_calendars as xcals  # only a package without sessions pays its import

    last = dt.date.fromisoformat(str(period["last"]))
    cal = xcals.get_calendar(calendar_id, start=period["first"], end=last + dt.timedelta(days=1))
    return cal.schedule.loc[: str(last)]


def _with_market(
    root: Path, path: str, instruments: Mapping[str, Any] | None, of: dict[str, str]
) -> pa.Table:
    """A bars file's ids and dates with a `market` column: its partition's, else per row from
    `instruments` into `of` (null where neither says)."""
    table = pq.read_table(root / path, columns=[ID_COLUMN, "session_date"])
    parts = dict(p.split("=", 1) for p in Path(path).parent.parts if "=" in p)
    if "market" in parts:
        return table.append_column("market", pa.array([parts["market"]] * len(table), pa.string()))
    for f in (instruments or {}).get("files", []) if not of else ():
        t = pq.read_table(root / f["path"], columns=[ID_COLUMN, "market"])
        of.update(zip(map(str, t[ID_COLUMN].to_pylist()), t["market"].to_pylist(), strict=True))
    ids = table[ID_COLUMN].to_pylist()
    return table.append_column("market", pa.array([of.get(str(i)) for i in ids], pa.string()))
