"""The daily bars' extent per market: what F-02 bounds its sessions by and what the F-03 and
F-15 records count (spec 4.5). TDS 4.3's `coverage` block is optional and may hold
`processed_through_session` alone, so a market whose entry lacks a key, or a package with no
`by_market`, is read from the bars themselves (#564): F-02 is "from the first to the last day
of `bars`", and a file's market is its `market=` partition (4.6), else its instrument's."""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from nexusbt.contracts import ID_COLUMN

#: The keys of a `by_market` entry the engine reads (TDS 4.2's example, D004's keys).
KEYS = frozenset({"first", "last", "rows", "instruments"})


class BarsExtent:
    """The daily bars' extent of one open, read from the files on the first ask and kept
    (#568): only F-02, F-03, F-15 and an undeclared market of an unpartitioned file use it."""

    def __init__(
        self, root: Path, bars: Mapping[str, Any] | None, instruments: Mapping[str, Any] | None
    ) -> None:
        self._root, self._bars, self._instruments = root, bars, instruments
        declared = ((bars or {}).get("coverage") or {}).get("by_market") or {}
        whole = declared and all(e.keys() >= KEYS for e in declared.values())
        #: the declared `coverage.by_market` when every entry has `KEYS`, else None
        self.declared = {m: dict(e) for m, e in declared.items()} if whole else None
        self._tables: list[pa.Table] | None = None
        self._counted: dict[str, dict[str, Any]] | None = None

    @property
    def partitioned(self) -> bool:
        """Every bars file names its market in a `market=` partition (4.6), which the checker
        holds to `markets` at every level (TDS-M010)."""
        files = (self._bars or {}).get("files", [])
        return all("market" in _partitions(f["path"]) for f in files)

    def tables(self) -> Iterator[pa.Table]:
        """Each bars file's ids (as strings) and dates with a `market` column: the ones kept
        from counting the extent, else read one file at a time and not kept."""
        if self._tables is not None:
            yield from self._tables
            return
        of: dict[str, str] = {}  # read once, and only for a file without `market=`
        for f in (self._bars or {}).get("files", []):
            yield _with_market(self._root, f["path"], self._instruments, of)

    def release(self) -> None:
        """Drop the rows kept for the open's checks; the counted extent stays."""
        self._tables = None

    def by_market(self) -> dict[str, dict[str, Any]]:
        """Market → `first`, `last` (`YYYY-MM-DD`), `rows` and `instruments` of the daily
        bars: the declared ones, else counted from the files once (none without bars)."""
        if self.declared is not None:
            return self.declared
        if self._counted is None:
            self._tables = list(self.tables())  # kept for F-02's off-calendar check
            self._counted = _counted(self._tables)
        return self._counted


def _counted(tables: list[pa.Table]) -> dict[str, dict[str, Any]]:
    """The extent counted from the bars' rows, in market code order (Arrow's threaded grouping
    gives no order of its own)."""
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
            for r in sorted(grouped.to_pylist(), key=lambda r: str(r["market"]))}  # fmt: skip


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
    # one type across files: TDS 3.2 reads a dictionary-encoded string as the string
    table = table.set_column(0, ID_COLUMN, pc.cast(table[ID_COLUMN], pa.string()))
    parts = _partitions(path)
    if "market" in parts:
        return table.append_column("market", pa.array([parts["market"]] * len(table), pa.string()))
    for f in (instruments or {}).get("files", []) if not of else ():
        t = pq.read_table(root / f["path"], columns=[ID_COLUMN, "market"])
        of.update(zip(map(str, t[ID_COLUMN].to_pylist()), t["market"].to_pylist(), strict=True))
    ids = table[ID_COLUMN].to_pylist()
    return table.append_column("market", pa.array([of.get(str(i)) for i in ids], pa.string()))


def _partitions(path: str) -> dict[str, str]:
    """A file path's `column=value` folders (4.6)."""
    return dict(p.split("=", 1) for p in Path(path).parent.parts if "=" in p)
