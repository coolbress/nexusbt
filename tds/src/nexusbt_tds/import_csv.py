"""`import_csv(mapping, out) -> Path`: CSV files to a TDS package (TDS 9, 9.5; #257).

The mapping file names the package's `profiles` (default `tds:minimal-daily@1.0`), its one
`market` and, under `datasets`, one block per dataset: `file` (the CSV, beside the mapping),
`kind` (default the name), `params`, `columns` (`{from, template, format, timezone}` per TDS
column; a CSV column with a TDS name is taken as is), `missing_values`, `availability` and
`pit_quality` (default `backfilled`: no availability time is invented, TDS 9). A value that
cannot be read stops the import with its file and line, so every row read is kept or the import
fails. The `tds import csv` command, `import_report.json`, `values` constants and the
`instruments` fills (#257 decisions 3, 4) come in the next part of #257.
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import math
from importlib.metadata import version
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pyarrow as pa
import pyarrow.parquet as pq

from ._mapping import read_mapping
from .hash import write_hashes
from .manifest import MANIFEST
from .schemas.verify import SCHEMA_DIR

_TOP = {"name", "snapshot_id", "profiles", "market", "id_namespaces", "datasets"}
_DATASET = {"file", "kind", "params", "columns", "missing_values", "availability", "pit_quality"}
_RULE = {"from", "template", "format", "timezone"}
_ARROW = {
    **dict.fromkeys(("id", "code", "string"), pa.string()), "f64": pa.float64(),
    "i8": pa.int8(), "i16": pa.int16(), "i32": pa.int32(), "i64": pa.int64(),
    "bool": pa.bool_(), "date": pa.date32(), "ts_us": pa.timestamp("us", tz="UTC"),
    "ts_us/ns": pa.timestamp("us", tz="UTC"), "ts_ns": pa.timestamp("ns", tz="UTC"),
}  # fmt: skip


class CsvImportError(ValueError):
    """The mapping file or a CSV cannot be imported as written; nothing is guessed."""


def import_csv(mapping: Path, out: Path) -> Path:
    mapping, out = Path(mapping), Path(out)
    try:
        spec = read_mapping(mapping.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        raise CsvImportError(f"{mapping.name}: {exc}") from None
    _keys(spec, _TOP, mapping.name)
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        raise CsvImportError(f"{out} is not empty; choose a new folder")
    market = spec.get("market")
    if not isinstance(market, dict) or not isinstance(market.get("code"), str):
        raise CsvImportError(f"{mapping.name}: `market` needs at least a `code`")
    code = market["code"]
    datasets, tables = [], []
    for name, ds in _items(spec.get("datasets"), "datasets"):
        _keys(ds, _DATASET, f"datasets.{name}")
        table, entry = _read(mapping.parent / str(ds.get("file")), name, ds, market)
        datasets.append(entry)
        tables.append((entry, table))
    profiles = spec.get("profiles") or ["tds:minimal-daily@1.0"]
    created = dt.datetime.now(dt.UTC).replace(microsecond=0)
    manifest = {
        "tds_version": "1.0", "name": spec.get("name", out.name),
        "created": created.isoformat().replace("+00:00", "Z"),
        "snapshot_id": spec.get("snapshot_id", created.strftime("%Y%m%d-%H%M%S")),
        "producer": {"name": "nexusbt-tds import csv", "version": version("nexusbt-tds")},
        "profiles": profiles,
        "id_namespaces": spec.get("id_namespaces", {code: "instrument ids as the CSV files give"}),
        "markets": {code: {k: v for k, v in market.items() if k != "code"}},
        "datasets": datasets, "hashes": {"hash_spec": "tds-hash-1"},
        "writer": {"name": "pyarrow", "version": pa.__version__},
    }  # fmt: skip
    out.mkdir(parents=True, exist_ok=True)
    for entry, table in tables:
        entry["files"] = _write(out, entry, table, code)
    (out / MANIFEST).write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", "utf-8")
    write_hashes(out)
    return out


def _items(value: object, where: str) -> list[tuple[str, dict[str, Any]]]:
    if not isinstance(value, dict) or not value:
        raise CsvImportError(f"`{where}` needs one or more named blocks")
    for name, block in value.items():
        if not isinstance(block, dict):
            raise CsvImportError(f"{where}.{name} is not a block of `key: value` lines")
    return list(value.items())


def _keys(block: object, allowed: set[str], where: str) -> None:
    if not isinstance(block, dict):
        raise CsvImportError(f"{where} is not a block of `key: value` lines")
    if extra := sorted(set(block) - allowed):
        raise CsvImportError(f"{where}: unknown {', '.join(extra)} (known: {sorted(allowed)})")


def _schema(kind: str) -> dict[str, Any]:
    path = SCHEMA_DIR / kind / "1.0.json"
    if not path.is_file():
        raise CsvImportError(f"kind {kind!r} has no TDS schema file")
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def _variant(value: Any, params: dict[str, Any]) -> Any:  # bars: daily or intraday (TDS 5.5)
    if isinstance(value, dict):
        return value["daily" if params.get("freq") == "1d" else "intraday"]
    return value


def _read(
    path: Path, name: str, ds: dict[str, Any], market: dict[str, Any]
) -> tuple[pa.Table, dict[str, Any]]:
    kind = str(ds.get("kind", name))
    schema, params = _schema(kind), ds.get("params") or {}
    types = {c["name"]: c["type"] for c in schema["columns"]}
    rules = ds.get("columns") or {}
    for column, rule in rules.items():
        _keys(rule, _RULE, f"datasets.{name}.columns.{column}")
        if column not in types:
            raise CsvImportError(f"datasets.{name}.columns: {column} is not a {kind} column")
    missing = {str(v) for v in ds.get("missing_values") or []}
    try:
        with path.open(encoding="utf-8-sig", newline="") as f:  # a spreadsheet's BOM dropped
            reader = csv.reader(f)
            header = next(reader, [])
            source = {c: header.index(r.get("from", c)) for c, r in rules.items()
                      if r.get("from", c) in header}  # fmt: skip
            if absent := sorted(set(rules) - set(source)):
                raise CsvImportError(f"{path.name}: no column for {', '.join(absent)}")
            taken = {header[i] for i in source.values()}
            source |= {h: i for i, h in enumerate(header) if h in types and h not in source
                       and h not in taken}  # fmt: skip
            values: dict[str, list[Any]] = {c: [] for c in source}
            for row in reader:
                if len(row) != len(header):
                    where = f"{path.name} line {reader.line_num}: {len(row)} fields"
                    raise CsvImportError(f"{where}, the header has {len(header)}")
                for c, i in source.items():
                    where = f"{path.name} line {reader.line_num}: {c}"
                    text = row[i]
                    value = None if text == "" or text in missing else text
                    values[c].append(_value(value, types[c], rules.get(c, {}), market, where))
    except OSError as exc:
        raise CsvImportError(f"datasets.{name}: {exc}") from None
    order = [c["name"] for c in schema["columns"] if c["name"] in values]
    table = pa.table({c: pa.array(values[c], _ARROW[types[c]]) for c in order})
    table = table.sort_by([(k, "ascending") for k in _variant(schema["sort"], params)])
    entry: dict[str, Any] = {"name": name, "kind": kind, "schema_version": "1.0", "path": name}
    entry |= {"params": params} if params else {}
    if either := [c for c in order if types[c] == "ts_us/ns"]:  # written in us; said so (4.5)
        entry["columns"] = [{"name": c, "type": "ts_us"} for c in either]
    availability = ds.get("availability")
    if availability is None and kind == "bars":  # the source gives none (TDS 9, 5.5)
        availability = {"rule": "ts_end"}
    entry |= {"availability": availability} if availability else {}
    entry["pit_quality"] = ds.get("pit_quality", "backfilled")
    return table, entry


def _value(text: str | None, tag: str, rule: dict[str, Any], market: dict[str, Any],
           where: str) -> Any:  # fmt: skip
    if text is None:
        return None
    text = str(rule["template"]).replace("{value}", text) if "template" in rule else text
    try:
        if tag in ("id", "code", "string"):
            return text
        if tag == "f64" and math.isfinite(number := float(text)):
            return number
        if tag in ("i8", "i16", "i32", "i64"):
            return int(text)
        if tag == "bool" and text in ("true", "false"):
            return text == "true"
        if tag == "date":
            fmt = rule.get("format")
            return dt.datetime.strptime(text, fmt).date() if fmt else dt.date.fromisoformat(text)
        if tag in ("ts_us", "ts_ns", "ts_us/ns"):
            return _instant(text, rule.get("format"), rule.get("timezone", market.get("timezone")),
                            where)  # fmt: skip
    except CsvImportError:
        raise
    except ValueError:
        pass
    if tag not in _ARROW:
        raise CsvImportError(f"{where}: a {tag} column is not imported from CSV; leave it out")
    raise CsvImportError(f"{where} {text!r} is not a {tag}")


def _instant(text: str, fmt: str | None, zone: str | None, where: str) -> dt.datetime:
    """TDS 9.5: RFC 3339 with `Z` or an offset; without one, read in `zone` (the column's, else
    the market's), and an hour that a daylight-saving change repeats or skips is an error."""
    value = dt.datetime.strptime(text, fmt) if fmt else dt.datetime.fromisoformat(text)
    if value.tzinfo is None:
        if zone is None:
            raise CsvImportError(f"{where} {text!r} has no offset and needs a timezone "
                                 "(the column's `timezone` or the market's)")  # fmt: skip
        first, second = (value.replace(tzinfo=ZoneInfo(zone), fold=f) for f in (0, 1))
        if first.utcoffset() != second.utcoffset():
            gap = first.astimezone(dt.UTC) > second.astimezone(dt.UTC)
            what = "a daylight-saving gap: no such time" if gap else (
                "a daylight-saving overlap (TDS-S004)")  # fmt: skip
            raise CsvImportError(f"{where} {text!r} in {zone} falls in {what}")
        value = first
    return value.astimezone(dt.UTC)


def _write(root: Path, entry: dict[str, Any], table: pa.Table, market: str) -> list[dict[str, Any]]:
    """Files under TDS 3.6's partitions from the schema: `market=` the market, `year=` the
    `session_date` year; a kind with another partition is not imported yet."""
    parts = _variant(_schema(entry["kind"])["partitions"], entry.get("params", {})) or ""
    fixed = [p for p in parts.split("/") if p and not p.endswith("=")]
    open_ = [p[:-1] for p in parts.split("/") if p.endswith("=")]
    if set(open_) - {"market", "year"}:
        raise CsvImportError(f"{entry['name']}: partition {parts} is not imported from CSV yet")
    entry["path"] = "/".join([entry["name"], *fixed])
    groups: dict[str, pa.Table] = {"": table}
    if "market" in open_:
        groups = {f"/market={market}": table}
    if "year" in open_:
        years = pa.compute.year(table["session_date"]).to_pylist()
        groups = {f"{k}/year={y}": t.filter(pa.array([x == y for x in years]))
                  for k, t in groups.items() for y in sorted(set(years))}  # fmt: skip
    files = []
    meta = {"tds.dataset": entry["name"], "tds.schema_version": "1.0"}
    for suffix, rows in groups.items():
        rel = f"{entry['path']}{suffix}/part-00000.parquet"
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        rows = rows.replace_schema_metadata(meta)
        if rows.num_rows:
            pq.write_table(rows, root / rel)
        else:  # no row group: an empty one has no statistics (as the synthetic generator)
            pq.ParquetWriter(root / rel, rows.schema).close()
        files.append({"path": rel, "rows": rows.num_rows, "bytes": (root / rel).stat().st_size})
    return files
