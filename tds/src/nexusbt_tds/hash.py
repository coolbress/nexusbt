"""`value_hash`, `semantic_hash`: canonical value serialisation and the package hashes (TDS 4.5).

`encode_table` writes a logical table's canonical bytes (header, rows in key order, cells);
`value_hash` builds one dataset's logical table, partition columns from the path, and hashes it."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import struct
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from .manifest import MANIFEST, read_manifest

#: (column name, TDS 3.2 type tag) in canonical column order.
Columns = Sequence[tuple[str, str]]

_INT = frozenset({"i8", "i16", "i32", "i64", "fixed"})
_TEXT = frozenset({"string", "id", "code", "json"})


class HashError(ValueError):
    """The dataset has no canonical value serialisation (a column with no declared type)."""


def _cell(tag: str, value: Any) -> bytes:
    if value is None:
        return b"\x00"
    if tag == "bool":
        return b"\x01" + bytes([bool(value)])
    if tag in _INT or tag.startswith("ts_"):
        return b"\x01" + struct.pack("<q", value)
    if tag == "f64":
        return b"\x01" + struct.pack("<d", value + 0.0)  # -0.0 + 0.0 is +0.0
    if tag == "date":
        return b"\x01" + struct.pack("<i", value)
    if tag in _TEXT:
        data: bytes = value.encode("utf-8")
        return b"\x01" + struct.pack("<I", len(data)) + data
    if tag.startswith("list<") and tag.endswith(">"):
        inner = tag[5:-1]
        return b"\x01" + struct.pack("<I", len(value)) + b"".join(_cell(inner, v) for v in value)
    raise HashError(f"type `{tag}` has no canonical bytes")


def _sort_key(tag: str, value: Any) -> Any:
    """Null first; numbers by magnitude, strings by UTF-8 bytes, lists element by element."""
    if value is None:
        return (0,)
    if tag in _TEXT:
        return (1, value.encode("utf-8"))
    if tag.startswith("list<"):
        return (1, tuple(_sort_key(tag[5:-1], v) for v in value))
    return (1, value + 0 if tag != "bool" else int(value))


def _values(column: pa.ChunkedArray, tag: str) -> list[Any]:
    """The column as Python values in the units the bytes use (days, the tag's time unit)."""
    if pa.types.is_dictionary(column.type):
        column = column.cast(column.type.value_type)
    if pa.types.is_timestamp(column.type):
        unit = {"ts_us": "us", "ts_ns": "ns"}.get(tag, column.type.unit)
        column = column.cast(pa.timestamp(unit, column.type.tz)).cast(pa.int64())
    elif pa.types.is_date32(column.type):
        column = column.cast(pa.int32())
    return list(column.to_pylist())


def encode_table(table: pa.Table, columns: Columns, key: Sequence[str]) -> bytes:
    """The canonical bytes of `table`: rows by `key`, ties by the other columns in order."""
    out = bytearray(b"TDSV1\n")
    for name, tag in columns:
        out += name.encode("utf-8") + b"\t" + tag.encode("utf-8") + b"\n"
    out += b"\n"
    tags = dict(columns)
    order = [*key, *(name for name, _ in columns if name not in key)]
    cols = {name: _values(table.column(name), tag) for name, tag in columns}
    rows = sorted(
        range(table.num_rows),
        key=lambda i: tuple(_sort_key(tags[n], cols[n][i]) for n in order),
    )
    for i in rows:
        for name, tag in columns:
            out += _cell(tag, cols[name][i])
    return bytes(out)


#: How a path value `key=value` reads, per partition type; any other type has no path rule.
_PARTITION: dict[str, Callable[[str], Any]] = {
    **dict.fromkeys(("i8", "i16", "i32", "i64"), int),
    **dict.fromkeys(_TEXT - {"json"}, str),
    "date": lambda v: (dt.date.fromisoformat(v) - dt.date(1970, 1, 1)).days,
}
_ARROW = {"i8": pa.int8(), "i16": pa.int16(), "i32": pa.int32(), "i64": pa.int64()}
_TAGS = {"bool", "f64", "date", "ts_us", "ts_ns", *_INT, *_TEXT}


def inside(root: Path, rel: object) -> Path:
    """`root/rel` when it is a regular file inside the package; else `HashError` (TDS-M012).

    Absolute paths, `..` and symbolic links leading out are never read, nor a device such as
    `/dev/zero`, which would not end."""
    path = (Path(root) / str(rel)).resolve()
    if not isinstance(rel, str) or not path.is_relative_to(Path(root).resolve()):
        raise HashError(f"{rel} is outside the package (TDS-M012); not read")
    if not path.is_file():
        raise HashError(f"{rel} is not a file in the package; not read")
    return path


def _read(root: Path, files: list[dict[str, Any]], partitioning: list[dict[str, Any]]) -> pa.Table:
    """The dataset's files as one table, dictionaries decoded, partition columns from the path."""
    tables = []
    for entry in files:
        table = pq.ParquetFile(inside(root, entry["path"])).read()
        table = table.cast(pa.schema(
            pa.field(f.name, f.type.value_type) if pa.types.is_dictionary(f.type) else f
            for f in table.schema
        ))  # fmt: skip
        parts = dict(p.split("=", 1) for p in Path(entry["path"]).parent.parts if "=" in p)
        for part in partitioning:
            name, tag = part["name"], part["type"]
            if name not in parts or name in table.column_names:
                raise HashError(f"{entry['path']}: partition {name} has no value in the path only")
            if tag not in _PARTITION:
                raise HashError(f"partition {name}: type `{tag}` has no path rule")
            value = _PARTITION[tag](parts[name])
            kind = pa.date32() if tag == "date" else _ARROW.get(tag, pa.string())
            table = table.append_column(part["name"], pa.array([value] * len(table), kind))
        tables.append(table)
    return pa.concat_tables(tables, promote_options="permissive")


def _columns(names: Sequence[str], dataset: Mapping[str, Any], schema: list[Any]) -> Columns:
    """Schema order, then partition columns the schema lacks, then `x_` columns (TDS 4.5 step 1).

    The tag is the type declared in `tds.json` (`columns`, `partitioning`), else the schema's.
    A column in none of the three groups is an unknown column, ignored (TDS 10.3, M011).
    """
    declared = {c["name"]: c.get("type") for c in dataset.get("columns", []) if "name" in c}
    declared |= {p["name"]: p["type"] for p in dataset.get("partitioning", [])}
    from_schema = {c.name: c.type for c in schema}
    order = [c.name for c in schema if c.name in names]
    order += [p["name"] for p in dataset.get("partitioning", []) if p["name"] not in order]
    order += sorted(n for n in names if n.startswith("x_"))
    out = []
    for name in order:
        tag = declared.get(name) or from_schema.get(name) or ""
        if tag not in _TAGS and not (tag.startswith("list<") and tag[5:-1] in _TAGS):
            raise HashError(f"{dataset['name']}: column {name} has no declared type (`{tag}`)")
        out.append((name, tag))
    return out


def _value(root: Path, entry: Mapping[str, Any], files: list[dict[str, Any]]) -> str:
    """The value hash of `files` of dataset `entry` (all its files: the dataset's)."""
    from .schemas.verify import load_schemas

    schema = load_schemas()[entry["kind"]]
    table = _read(root, files, entry.get("partitioning", []))
    columns = _columns(table.column_names, entry, list(schema.columns))
    key = entry.get("key", schema.key)
    if isinstance(key, dict):  # bars: the daily or the intraday key, by `params.freq`
        key = key["daily" if entry.get("params", {}).get("freq") == "1d" else "intraday"]
    key = key if isinstance(key, list) else []
    if missing := [k for k in key if k not in dict(columns)]:
        raise HashError(f"{entry['name']}: key column {', '.join(missing)} is not in the data")
    return hashlib.sha256(encode_table(table, columns, key)).hexdigest()


def value_hash(path: Path, dataset: str) -> str:
    """The dataset's `value_sha256` (TDS 4.5): sha256 of its canonical value serialisation."""
    root = Path(path)
    (entry,) = (d for d in read_manifest(root).datasets if d.get("name") == dataset)
    return _value(root, entry, entry["files"])


HASH_SPEC = "tds-hash-1"
#: The package-level keys of the semantic hash (TDS 4.5), each `null` when tds.json has none.
_PACKAGE_KEYS = ("markets", "id_namespaces", "editions", "policies", "currencies", "roll_rules")
_DATASET_KEYS = ("kind", "schema_version", "params", "availability", "pit_quality", "key")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _number(x: float) -> str:
    """RFC 8785 3.2.2.3: the ECMAScript Number-to-String form of the double `x`."""
    if x == 0:
        return "0"
    mantissa, _, exp = repr(abs(float(x))).partition("e")
    whole, _, frac = mantissa.partition(".")
    digits = (whole + frac).lstrip("0")
    point = int(exp or 0) + len(whole) - (len(whole + frac) - len(digits))  # value = 0.digits·10^n
    digits = digits.rstrip("0")
    k, n = len(digits), point
    if k <= n <= 21:
        text = digits + "0" * (n - k)
    elif 0 < n <= 21:
        text = f"{digits[:n]}.{digits[n:]}"
    elif -6 < n <= 0:
        text = "0." + "0" * -n + digits
    else:
        text = f"{digits[0]}{'.' + digits[1:] if k > 1 else ''}e{'+' if n > 0 else '-'}{abs(n - 1)}"
    return ("-" if x < 0 else "") + text


def canonical_json(value: Any) -> str:
    """RFC 8785 (JCS): keys by UTF-16 code units, its string escaping and number form."""
    if value is None or isinstance(value, bool):
        return json.dumps(value)
    if isinstance(value, int | float):
        return _number(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        return "[" + ",".join(canonical_json(v) for v in value) + "]"
    keys = sorted(value, key=lambda k: k.encode("utf-16-be"))
    return "{" + ",".join(f"{canonical_json(k)}:{canonical_json(value[k])}" for k in keys) + "}"


def _inventory(root: Path) -> tuple[dict[str, str], dict[str, dict[str, str]], list[Any]]:
    """Per dataset its value hash, per file its sha256 and value hash, and the semantic entries."""
    datasets: dict[str, str] = {}
    files: dict[str, dict[str, str]] = {}
    semantic = []
    for entry in read_manifest(root).datasets:
        name = str(entry.get("name"))  # required (TDS-M003); the manifest level reports its absence
        try:
            datasets[name] = _value(root, entry, entry["files"])
            for f in entry["files"]:
                if f["path"] in files:
                    raise HashError(f"{f['path']} is listed twice (TDS-M013)")
                sha = _sha256(inside(root, f["path"]).read_bytes())
                files[f["path"]] = {"sha256": sha, "value_sha256": _value(root, entry, [f])}
        except (OSError, KeyError, TypeError, pa.ArrowException) as exc:
            raise HashError(f"dataset {name}: {exc!r}") from exc
        units = {c["name"]: c["unit"] for c in entry.get("columns", []) if "unit" in c}
        semantic.append({"name": name, "value_sha256": datasets[name], "units": units,
                         **{k: entry.get(k) for k in _DATASET_KEYS},
                         "price_exponent": entry.get("price_exponent", -9),
                         "size_exponent": entry.get("size_exponent", 0)})  # fmt: skip
    return datasets, files, sorted(semantic, key=lambda d: d["name"])


def _semantic(root: Path, entries: list[Any]) -> str:
    data = read_manifest(root).data
    doc = {"tds_version": data.get("tds_version"), "hash_spec": HASH_SPEC, "datasets": entries,
           "profiles": data.get("profiles"), **{k: data.get(k) for k in _PACKAGE_KEYS}}  # fmt: skip
    return canonical_json(doc)


def semantic_json(path: Path) -> str:
    """The canonical JSON the semantic hash is taken over (TDS 4.5)."""
    return _semantic(Path(path), _inventory(Path(path))[2])


def package_hashes(path: Path) -> dict[str, Any]:
    """Every TDS 4.5 hash of the package: `physical_sha256`, `value_sha256`, `semantic_sha256`,
    `datasets` {name: value_sha256} and `files` {path: {sha256, value_sha256}}."""
    root = Path(path)
    datasets, files, entries = _inventory(root)
    return {
        "physical_sha256": _lines({p: f["sha256"] for p, f in files.items()}),
        "value_sha256": _lines(datasets),
        "semantic_sha256": _sha256(_semantic(root, entries).encode("utf-8")),
        "datasets": datasets,
        "files": files,
    }


def _lines(pairs: Mapping[str, str]) -> str:
    """sha256 of `"{key}\\t{value}\\n"` in ascending key order (the physical and value hashes)."""
    return _sha256("".join(f"{k}\t{pairs[k]}\n" for k in sorted(pairs)).encode("utf-8"))


def semantic_hash(path: Path) -> str:
    """The package's `semantic_sha256` (TDS 4.5): the canonical JSON of its resolved metadata."""
    return str(package_hashes(path)["semantic_sha256"])


def write_hashes(path: Path) -> dict[str, Any]:
    """`tds hash --write`: put every hash into tds.json, the rest of it unchanged (TDS 8.1)."""
    root = Path(path)
    hashes = package_hashes(root)
    data = json.loads((root / MANIFEST).read_text(encoding="utf-8"))
    for entry in (d for d in data["datasets"] if isinstance(d, dict)):  # as Manifest.datasets
        entry["value_sha256"] = hashes["datasets"][entry["name"]]
        for f in entry["files"]:
            f.update(hashes["files"][f["path"]])
    data["hashes"] = {k: hashes[k] for k in ("physical_sha256", "value_sha256", "semantic_sha256")}
    data["hashes"]["hash_spec"] = HASH_SPEC
    staged = root / f".{MANIFEST}.tmp"  # written whole, then swapped in: never a half tds.json
    staged.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    staged.replace(root / MANIFEST)
    return hashes
