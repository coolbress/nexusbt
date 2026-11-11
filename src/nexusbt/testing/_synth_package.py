"""The synthetic generator's package writer (spec 4.8): the generated tables written as TDS
files with their tds.json fields, coverage and watermarks, and the `tds` command that hashes
and checks the package.

`synth` hands it each market's tables once every stage has run; nothing here draws a random
number, so moving it out of `synth` changed no byte of any preset.
"""

from __future__ import annotations

import subprocess
import sysconfig
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from nexusbt.contracts import ID_COLUMN as ID

ROW_GROUP = 100_000
_TS = pa.timestamp("us", tz="UTC")
Table = dict[str, Any]  # column name → values, in schema order
#: The `tradability_daily` columns known before the open, and the day's results.
LIMIT_PRICES = ("price_limit_ratio", "up_limit_price", "down_limit_price", "reference_price")
DAY_FLAGS = ("halted_full_day", "limit_up_close", "limit_down_close", "locked_up", "locked_down")
#: TDS 5.10's availability per column group: known before the open, or the day's results.
BY_COLUMN = dict.fromkeys((*LIMIT_PRICES, "admin_status"), "session_open")
BY_COLUMN |= dict.fromkeys((*DAY_FLAGS, "halt_count"), "session_close")
_TYPES = {
    "listed_on": pa.date32(), "session_date": pa.date32(), "valid_from": pa.date32(),
    "valid_to": pa.date32(), "last_session": pa.date32(), "delisted_on": pa.date32(),
    "ts_known_from": _TS,
    "ts_known_to": _TS, "ts_start": _TS, "ts_end": _TS, "ts_open": _TS, "ts_close": _TS,
    "session_ord": pa.int32(), "venue_mic": pa.string(), "listed_on_censored": pa.bool_(),
    "halt_count": pa.int32(), "admin_status": pa.string(), "ts_available": _TS,
    "reason": pa.string(), "tick_rule_id": pa.string(),
    **dict.fromkeys(DAY_FLAGS, pa.bool_()), **dict.fromkeys(LIMIT_PRICES, pa.float64()),
}  # fmt: skip


def _typed(*pairs: tuple[str, str]) -> list[dict[str, str]]:
    """tds.json `columns` for types a TDS kind leaves out."""
    return [{"name": c, "type": t} for c, t in pairs]


#: Each dataset's tds.json fields besides its name, kind, path and files.
FIELDS: dict[str, dict[str, Any]] = {
    "bars_1d": {
        "kind": "bars", "path": "bars/freq=1d", "availability": {"rule": "ts_end"},
        "params": {"freq": "1d", "price_basis": "raw", "density": "dense", "bar_time": "session"},
        "columns": _typed(("ts_start", "ts_us"), ("ts_end", "ts_us"))},
    "instrument_xref": {"columns": _typed(
        (ID, "id"), ("id_type", "code"), ("link_quality", "code"), ("source", "string"))},
    # TDS 4.2, 6.2: availability as the columns that hold it (#276)
    "instrument_symbols": {"availability": {"column": "ts_known_from"}},
    "corporate_actions": {
        "availability": {"effect": "ts_effective", "terms": "ts_terms_available"}},
    "delistings": {"availability": {"exit": "ts_exit_known", "value": "ts_value_available"}},
    "tradability_daily": {
        "path": "tradability_daily/freq=1d", "params": {"availability_by_column": BY_COLUMN},
        "columns": _typed((ID, "id"), ("session_date", "date"))},
    "eligibility_daily": {  # TDS 5.20: the rule is session_close, a missing row means false
        "availability": {"rule": "session_close"}, "params": {"missing_means": False},
        "columns": _typed(("rule_id", "id"), (ID, "id"), ("session_date", "date"),
                          ("is_eligible", "bool"), ("ts_available", "ts_us"))},
    "share_counts": {"availability": {"column": "ts_available"}, "columns": _typed(
        (ID, "id"), ("count_kind", "code"), ("ts_available", "ts_us"), ("source", "string"))},
}  # fmt: skip
#: TDS 5.3 `instrument_xref`, written empty (4.8 (2)).
XREF = {c: pa.string() for c in (ID, "id_type", "id_value", "link_quality", "source")}
XREF |= {"valid_from": pa.date32(), "valid_to": pa.date32()}


def _arrow(table: Table | pa.Table) -> pa.Table:
    if isinstance(table, pa.Table):
        return table.cast(pa.schema([(c, _TYPES.get(c, t)) for c, t in zip(
            table.column_names, table.schema.types, strict=True)]))  # fmt: skip
    return pa.table({c: pa.array(v, _TYPES.get(c)) for c, v in table.items()})


def _write(root: Path, rel: str, name: str, table: pa.Table) -> dict[str, Any]:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    table = table.replace_schema_metadata({"tds.dataset": name, "tds.schema_version": "1.0"})
    if table.num_rows:
        pq.write_table(table, path, row_group_size=ROW_GROUP)
    else:  # no row group: an empty one has no statistics, so S003 and S006 would go unchecked
        pq.ParquetWriter(path, table.schema).close()
    return {"path": rel, "rows": table.num_rows, "bytes": path.stat().st_size}


def _span(table: pa.Table) -> dict[str, Any]:
    """`table`'s distinct instruments and its first and last `session_date`, each when it has
    the column, and its rows: the values D004 reads from the files (TDS 8.3)."""
    out: dict[str, Any] = {}
    if ID in table.column_names:
        out["instruments"] = pa.compute.count_distinct(table[ID]).as_py()
    if "session_date" in table.column_names and table.num_rows:
        low, high = pa.compute.min_max(table["session_date"]).as_py().values()
        out |= {"first": low.isoformat(), "last": high.isoformat()}
    return out | {"rows": table.num_rows}


def _coverage(parts: Mapping[str | None, pa.Table]) -> dict[str, Any]:
    """A dataset's tds.json `coverage` (TDS 4.3), from its `market=` partitions `parts` (key
    None: it has none, so no `by_market`): the keys of 4.2's example it has a column for, and
    no block when it has neither column."""
    slim = {m: t.select([c for c in (ID, "session_date") if c in t.column_names])
            for m, t in parts.items()}  # fmt: skip
    whole = _span(pa.concat_tables(list(slim.values())))
    keys = {"instruments": "instruments", "ts_min": "first", "ts_max": "last"}
    out: dict[str, Any] = {k: whole[v] for k, v in keys.items() if v in whole}
    if out and None not in slim:
        out["by_market"] = {m: _span(t) for m, t in slim.items()}
    return {"coverage": out} if out else {}


def _watermark(sessions: Table) -> dict[str, str]:
    """TDS 3.8's watermark of the market whose calendar rows are `sessions`: a synthetic
    package is complete through its period's last session, to that session's close (4.8)."""
    last = _arrow(sessions).slice(len(sessions["session_date"]) - 1).to_pylist()[0]
    return {"complete_through_session": last["session_date"].isoformat(),
            "complete_through": f"{last['ts_close']:%Y-%m-%dT%H:%M:%SZ}"}  # fmt: skip


def _daily(
    root: Path, tables: Mapping[str, Mapping[str, Any]], files: dict[str, list[Any]],
    cover: dict[str, Any],
) -> None:  # fmt: skip
    """Writes the datasets partitioned by market and year, of the markets that have them
    (tiny: the bars only so far), adding their `files` entries and their coverage."""
    for name in ("bars_1d", "tradability_daily", "eligibility_daily"):
        path = FIELDS[name].get("path", name)
        parts: dict[str | None, pa.Table]
        parts = {m: _arrow(tables[m][name]) for m in tables if name in tables[m]}
        for m, rows in parts.items():
            files.setdefault(name, []).extend(_by_year(root, f"{path}/market={m}", name, rows))
        if parts:
            cover[name] = _coverage(parts)


def _by_year(root: Path, rel: str, name: str, rows: pa.Table) -> list[dict[str, Any]]:
    """A daily dataset's rows written in `rel/year=Y/` partitions (TDS 3.6)."""
    years = pa.compute.year(rows["session_date"]).to_numpy()
    return [_write(root, f"{rel}/year={y}/part-00000.parquet", name, rows.filter(years == y))
            for y in sorted(set(years.tolist()))]  # fmt: skip


def _tds(*args: str) -> subprocess.CompletedProcess[str]:
    """The `tds` command beside this interpreter, as its own process (a development dependency
    until T1.1a: without nexusbt-tds installed, FileNotFoundError)."""
    command = [str(Path(sysconfig.get_path("scripts")) / "tds"), *args]
    return subprocess.run(command, capture_output=True, text=True, check=False)  # noqa: S603
