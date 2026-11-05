"""`import_csv(mapping, out) -> Path`: CSV files to a TDS package (TDS 9, 9.5; #257).

The mapping file names the package's `profiles` (default `tds:minimal-daily@1.0`), its one
`market` and, under `datasets`, one block per dataset: `file` (the CSV, beside the mapping),
`kind` (default the name), `params`, `columns` (`{from, template, format, timezone}` per TDS
column; a CSV column with a TDS name is taken as is), `values` (a constant per column, over the
CSV and over the `instruments` fills of `_FILLS`), `missing_values`, `availability` and
`pit_quality` (default `backfilled`: no availability time is invented, TDS 9). A value that
cannot be read stops the import with its file and line, so every row read is kept or the import
fails; nothing is written until every dataset is read and checked. `import_report.json`, next to
the package, says what was kept and every default and fill assumed (#257 decisions 3 to 5, 7).
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import math
import re
from importlib.metadata import version
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pyarrow as pa
import pyarrow.parquet as pq

from ._mapping import read_mapping
from .hash import write_hashes
from .manifest import MANIFEST
from .schemas.verify import SCHEMA_DIR

_TOP = {"name", "snapshot_id", "profiles", "market", "id_namespaces", "datasets"}
_DATASET = {"file", "kind", "params", "columns", "values", "missing_values", "availability",
            "pit_quality"}  # fmt: skip
REPORT = "import_report.json"
_RULE = {"from", "template", "format", "timezone"}
_NUMBER = re.compile(r"[+-]?([0-9]+\.?[0-9]*|\.[0-9]+)([eE][+-]?[0-9]+)?")  # no `1_000`, ` 5`
_BITS = {"i8": 8, "i16": 16, "i32": 32, "i64": 64}
#: RFC 3339 date-time (TDS 9.5), to the microsecond; the offset may be left to `timezone`.
_RFC3339 = re.compile(r"\d{4}-\d\d-\d\d[Tt]\d\d:\d\d:\d\d(\.\d{1,6})?([Zz]|[+-]\d\d:\d\d)?")
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
    if not isinstance(market.get("timezone", ""), str):
        raise CsvImportError(f"{mapping.name}: the market's `timezone` is text")
    code = market["code"]
    datasets, tables, report = [], [], {}
    for name, ds in _items(spec.get("datasets"), "datasets"):
        _keys(ds, _DATASET, f"datasets.{name}")
        if not isinstance(ds.get("file"), str):
            raise CsvImportError(f"datasets.{name}: `file` is missing")
        table, entry, report[name] = _read(mapping.parent / ds["file"], name, ds, market)
        datasets.append(entry)
        tables.append((entry, _groups(entry, table, code)))  # every check before any write
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
    for entry, groups in tables:
        entry["files"] = _write(out, entry, groups)
    (out / MANIFEST).write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", "utf-8")
    write_hashes(out)
    given = ("name", "snapshot_id", "profiles", "id_namespaces")  # decision 7: each one used
    assumed = [f"{k}: {json.dumps(manifest[k], ensure_ascii=False)} (the mapping gives none)"
               for k in given if k not in spec]  # fmt: skip
    text = {"package": out.name, "mapping": mapping.name, "assumed": assumed, "datasets": report}
    (out.parent / REPORT).write_text(json.dumps(text, indent=2, ensure_ascii=False) + "\n", "utf-8")
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
        if params.get("freq") != "1d":  # absent included: no key or sort is guessed
            freq = params.get("freq")
            raise CsvImportError(f"the sort and partitions for params.freq {freq!r} are not"
                                 " imported from CSV (only 1d yet)")  # fmt: skip
        return value["daily"]
    return value


def _read(
    path: Path, name: str, ds: dict[str, Any], market: dict[str, Any]
) -> tuple[pa.Table, dict[str, Any], dict[str, Any]]:
    kind = str(ds.get("kind", name))
    schema, params = _schema(kind), ds.get("params") or {}
    if not isinstance(params, dict):
        raise CsvImportError(f"datasets.{name}.params is not a block of `key: value` lines")
    types = {c["name"]: c["type"] for c in schema["columns"]}
    rules = ds.get("columns") or {}
    _keys(rules, set(types), f"datasets.{name}.columns")
    for column, rule in rules.items():
        _keys(rule, _RULE, f"datasets.{name}.columns.{column}")
        if odd := sorted(k for k, v in rule.items() if not isinstance(v, str)):  # JSON: `5`
            raise CsvImportError(f"datasets.{name}.columns.{column}: {', '.join(odd)} is text")
        if "{value}" not in str(rule.get("template", "{value}")):
            raise CsvImportError(f"datasets.{name}.columns.{column}: template needs {{value}}")
    if not isinstance(listed := ds.get("missing_values") or [], list):  # `NA`: not N and A
        raise CsvImportError(f"datasets.{name}: missing_values is a list, such as [NA]")
    missing = {str(v) for v in listed}
    constants = ds.get("values") or {}
    _keys(constants, set(types), f"datasets.{name}.values")
    count = 0
    try:
        with path.open(encoding="utf-8-sig", newline="") as f:  # a spreadsheet's BOM dropped
            reader = csv.reader(f)
            header = next(reader, [])
            if twice := sorted({h for h in header if header.count(h) > 1}):
                raise CsvImportError(f"{path.name}: column {', '.join(twice)} given twice")
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
                count += 1
                for c, i in source.items():
                    where = f"{path.name} line {reader.line_num}: {c}"
                    text = row[i]
                    value = None if text == "" or text in missing else text
                    values[c].append(_value(value, types[c], rules.get(c, {}), market, where))
    except OSError as exc:
        raise CsvImportError(f"datasets.{name}: {exc}") from None
    assumed: list[str] = []
    for column, constant in constants.items():  # over the CSV's column (TDS 9.5)
        text = str(constant).lower() if isinstance(constant, bool) else str(constant)  # JSON
        where = f"datasets.{name}.values: {column}"
        values[column] = [_value(text, types[column], {}, market, where)] * count
    for column, why in _FILLS.items() if kind == "instruments" and count else ():
        filled = [_fill(column, a) for a in values.get("asset_class") or [None] * count]
        if column not in values and None not in filled:
            values[column] = filled
            assumed.append(f"{column} {sorted({str(v) for v in filled})} for every row ({why})")
    order = [c["name"] for c in schema["columns"] if c["name"] in values]
    table = pa.table({c: pa.array(values[c], _ARROW[types[c]]) for c in order})
    sort = _variant(schema["sort"], params) or []
    if absent := [k for k in sort if k not in values]:
        raise CsvImportError(f"{path.name}: no column for {', '.join(absent)}, the sort key")
    table = table.sort_by([(k, "ascending") for k in sort]) if sort else table
    entry: dict[str, Any] = {"name": name, "kind": kind, "schema_version": "1.0", "path": name}
    entry |= {"params": params} if params else {}
    if either := [c for c in order if types[c] == "ts_us/ns"]:  # written in us; said so (4.5)
        entry["columns"] = [{"name": c, "type": "ts_us"} for c in either]
    availability = ds.get("availability")
    if availability is None and kind == "bars":  # the source gives none (TDS 9, 5.5)
        availability = {"rule": "ts_end"}
        assumed.append("availability rule ts_end (the source gives none, TDS 9)")
    entry |= {"availability": availability} if availability else {}
    entry["pit_quality"] = ds.get("pit_quality", "backfilled")
    if "pit_quality" not in ds:
        assumed.append("pit_quality = backfilled (availability times not in the source, TDS 9)")
    kept = {c: header[i] for c, i in source.items() if c not in constants}
    said = {"file": path.name, "rows_read": count, "rows_kept": table.num_rows,
            "rows_dropped": count - table.num_rows, "columns_kept": kept,
            "columns_dropped": [h for h in header if h not in kept.values()],
            "values": constants, "assumed": assumed}  # fmt: skip
    return table, entry, said


_PLAIN = ("equity", "etf", "fund")
#: Required `instruments` columns filled when neither the CSV nor `values` gives them (#257).
_FILLS = {
    "lot_size": "TDS 5.1: default 1",
    "multiplier": "TDS 5.1: equities 1.0; equity, etf, fund only",
    "is_synthetic": "importer rule, 5.1 states none: equity, etf, fund false, index true",
}


def _fill(column: str, asset_class: str | None) -> float | bool | None:
    """The fill of one row, or None: the column is then left out and stays TDS-S001."""
    if column == "lot_size":
        return 1.0
    if column == "multiplier":
        return 1.0 if asset_class in _PLAIN else None
    return {**dict.fromkeys(_PLAIN, False), "index": True}.get(str(asset_class))


def _value(text: str | None, tag: str, rule: dict[str, Any], market: dict[str, Any],
           where: str) -> Any:  # fmt: skip
    if text is None:
        return None
    text = str(rule["template"]).replace("{value}", text) if "template" in rule else text
    try:
        if tag in ("id", "code", "string"):
            return text
        if tag == "f64" and _NUMBER.fullmatch(text) and math.isfinite(number := float(text)):
            return number
        if tag in _BITS and re.fullmatch("[+-]?[0-9]+", text):
            half = 1 << (_BITS[tag] - 1)
            if -half <= (whole := int(text)) < half:
                return whole
        if tag == "bool" and text in ("true", "false"):
            return text == "true"
        if tag == "date":
            fmt = rule.get("format")
            if fmt:
                return _strptime(text, fmt, f"{where} {text!r} is not a {tag}").date()
            if re.fullmatch("[0-9]{4}-[0-9]{2}-[0-9]{2}", text):  # not `20240102`, `2024-W01-2`
                return dt.date.fromisoformat(text)
        if tag in ("ts_us", "ts_ns", "ts_us/ns"):
            return _instant(text, rule.get("format"), rule.get("timezone", market.get("timezone")),
                            where, tag)  # fmt: skip
    except CsvImportError:
        raise
    except ValueError:
        pass
    if tag not in _ARROW:
        raise CsvImportError(f"{where}: a {tag} column is not imported from CSV; leave it out")
    raise CsvImportError(f"{where} {text!r} is not a {tag}")


def _instant(text: str, fmt: str | None, zone: str | None, where: str, tag: str) -> dt.datetime:
    """TDS 9.5: RFC 3339 with `Z` or an offset; without one, read in `zone` (the column's, else
    the market's), and an hour that a daylight-saving change repeats or skips is an error."""
    if not fmt and not _RFC3339.fullmatch(text):  # finer than us would be cut: not read either
        raise ValueError(text)
    value = (_strptime(text, fmt, f"{where} {text!r} is not a {tag}") if fmt
             else dt.datetime.fromisoformat(text.upper()))  # fmt: skip  # RFC 3339's `t`, `z`
    if value.tzinfo is None:
        if zone is None:
            raise CsvImportError(f"{where} {text!r} has no offset and needs a timezone "
                                 "(the column's `timezone` or the market's)")  # fmt: skip
        try:
            tz = ZoneInfo(zone)
        except (ZoneInfoNotFoundError, ValueError):
            raise CsvImportError(f"{where}: unknown timezone {zone!r}") from None
        first, second = (value.replace(tzinfo=tz, fold=f) for f in (0, 1))
        if first.utcoffset() != second.utcoffset():
            gap = first.astimezone(dt.UTC) > second.astimezone(dt.UTC)
            what = "a daylight-saving gap: no such time" if gap else (
                "a daylight-saving overlap (TDS-S004)")  # fmt: skip
            raise CsvImportError(f"{where} {text!r} in {zone} falls in {what}")
        value = first
    return value.astimezone(dt.UTC)


def _strptime(text: str, fmt: str, where: str) -> dt.datetime:  # alone: `2024013` is 2024-01-03
    """`where` ends in the column's type, as `_value` writes it: `... 'x' is not a date`."""
    value = dt.datetime.strptime(text, fmt)
    if (back := value.strftime(fmt)) != text:  # TDS 9.5: a format writes the value back as read
        raise CsvImportError(
            f"{where}: format {fmt!r} writes it back as {back!r}; write the value in RFC 3339"
            " (a date as YYYY-MM-DD) and drop `format`, or give a `format` that writes it back"
            " character for character"
        )
    return value


def _groups(entry: dict[str, Any], table: pa.Table, market: str) -> dict[str, pa.Table]:
    """Files under TDS 3.6's partitions from the schema: `market=` the market, `year=` the
    `session_date` year; a kind with another partition is not imported yet."""
    parts = _variant(_schema(entry["kind"])["partitions"], entry.get("params", {})) or ""
    parts = "/".join(parts) if isinstance(parts, list) else parts
    fixed = [p for p in parts.split("/") if p and not p.endswith("=")]
    open_ = [p[:-1] for p in parts.split("/") if p.endswith("=")]
    if set(open_) - {"market", "year"}:
        raise CsvImportError(f"{entry['name']}: partition {parts} is not imported from CSV yet")
    entry["path"] = "/".join([entry["name"], *fixed])
    groups: dict[str, pa.Table] = {"": table}
    if "market" in open_:
        groups = {f"/market={market}": table}
    if "year" in open_:
        has = "session_date" in table.column_names
        years = pa.compute.year(table["session_date"]).to_pylist() if has else [None]
        if not years or None in years:
            raise CsvImportError(f"{entry['name']}: the year= partition needs one or more rows,"
                                 " each with a session_date")  # fmt: skip
        groups = {f"{k}/year={y}": t.filter(pa.array([x == y for x in years]))
                  for k, t in groups.items() for y in sorted(set(years))}  # fmt: skip
    return {f"{entry['path']}{k}/part-00000.parquet": t for k, t in groups.items()}


def _write(root: Path, entry: dict[str, Any], groups: dict[str, pa.Table]) -> list[dict[str, Any]]:
    files = []
    meta = {"tds.dataset": entry["name"], "tds.schema_version": "1.0"}
    for rel, rows in groups.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        rows = rows.replace_schema_metadata(meta)
        if rows.num_rows:
            pq.write_table(rows, root / rel)
        else:  # no row group: an empty one has no statistics (as the synthetic generator)
            pq.ParquetWriter(root / rel, rows.schema).close()
        files.append({"path": rel, "rows": rows.num_rows, "bytes": (root / rel).stat().st_size})
    return files
