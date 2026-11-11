"""`value_hash`, `semantic_hash`: canonical value serialisation and the package hashes (TDS 4.5).

`encode_table` writes a logical table's canonical bytes (header, rows in key order, cells);
`value_hash` builds one dataset's logical table, partition columns from the path, and hashes it."""

from __future__ import annotations

import datetime as dt
import hashlib
import heapq
import json
import os
import struct
import tempfile
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from operator import itemgetter
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pyarrow as pa
import pyarrow.parquet as pq

from .manifest import MANIFEST, read_manifest

if TYPE_CHECKING:  # at run time imported inside functions, like `load_schemas` in `_value`
    from .schemas.verify import Column

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


def _sort_key(tag: str, value: Any) -> bytes:
    """Bytes that compare as TDS 4.5 orders values: null first, numbers by magnitude, strings by
    UTF-8 bytes, lists element by element. Self-delimiting, so a row's keys concatenate."""
    if value is None:
        return b"\x00"
    if tag in _TEXT:  # 0x00 escaped, then a 0x00 0x00 end: a prefix sorts first
        text: bytes = value.encode("utf-8")
        return b"\x01" + text.replace(b"\x00", b"\x00\xff") + b"\x00\x00"
    if tag.startswith("list<"):
        return b"\x01" + b"".join(b"\x01" + _sort_key(tag[5:-1], v) for v in value) + b"\x00"
    if tag == "f64":  # IEEE-754 bits made unsigned-comparable; -0.0 + 0.0 is +0.0
        bits = int.from_bytes(struct.pack(">d", value + 0.0))
        return b"\x01" + (bits ^ (2**64 - 1 if bits >> 63 else 2**63)).to_bytes(8)
    return b"\x01" + (int(value) + 2**63).to_bytes(8)  # bool, integers, days, instants


def _holds_time(kind: pa.DataType) -> bool:
    """Whether an Arrow type is, or holds in a list, struct, map or dictionary, a time type."""
    inner = [kind.field(i).type for i in range(kind.num_fields)]
    inner += [kind.value_type] if pa.types.is_dictionary(kind) else []
    return pa.types.is_temporal(kind) or any(_holds_time(t) for t in inner)


#: TDS 3.2: the time types and the Arrow types a column of one is read as: pyarrow makes another
#: time type, such as a `time64[ns]`, a Python value only with pandas (#389). An instant is a
#: timestamp; a date is a `date32`, or a type with no time in it, which the codes that need a
#: date skip (a text `session_date` leaves the other V codes judged, #366).
TIME_TYPES: dict[str, Callable[[pa.DataType], bool]] = {
    **dict.fromkeys(("ts_us", "ts_ns", "ts_us/ns"), pa.types.is_timestamp),
    "date": lambda kind: pa.types.is_date32(kind) or not _holds_time(kind),
}


def _values(column: pa.ChunkedArray, tag: str, name: str = "") -> list[Any]:
    """The column as Python values in the units the bytes use (days, the tag's time unit); a
    time column of another Arrow type (S002's) raises `HashError` before a value is made."""
    if tag in TIME_TYPES and not TIME_TYPES[tag](column.type):
        raise HashError(f"{name} is {column.type}, TDS type {tag}")
    if pa.types.is_dictionary(column.type):
        column = column.cast(column.type.value_type)
    if pa.types.is_timestamp(column.type):
        unit = {"ts_us": "us", "ts_ns": "ns"}.get(tag, column.type.unit)
        column = column.cast(pa.timestamp(unit, column.type.tz)).cast(pa.int64())
    elif pa.types.is_date32(column.type):
        column = column.cast(pa.int32())
    return list(column.to_pylist())


def _header(columns: Columns) -> bytes:
    lines = (name.encode("utf-8") + b"\t" + tag.encode("utf-8") + b"\n" for name, tag in columns)
    return b"TDSV1\n" + b"".join(lines) + b"\n"


def _rows(table: pa.Table, columns: Columns, key: Sequence[str]) -> list[tuple[bytes, bytes]]:
    """(sort key, cell bytes) per row: by `key`, ties by the other columns in order. A column
    the table lacks is null (a file without a column the dataset has)."""
    tags = dict(columns)
    order = [*key, *(name for name, _ in columns if name not in key)]
    none = [None] * table.num_rows
    cols = {n: _values(table.column(n), t, n) if n in table.column_names else none
            for n, t in columns}  # fmt: skip
    return [
        (b"".join(_sort_key(tags[n], cols[n][i]) for n in order),
         b"".join(_cell(t, cols[n][i]) for n, t in columns))
        for i in range(table.num_rows)
    ]  # fmt: skip


def encode_table(table: pa.Table, columns: Columns, key: Sequence[str]) -> bytes:
    """The canonical bytes of `table`: rows by `key`, ties by the other columns in order."""
    rows = sorted(_rows(table, columns, key), key=itemgetter(0))
    return _header(columns) + b"".join(row for _, row in rows)


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


#: Rows sorted in memory at a time (#309): a dataset of more is sorted batch by batch, each
#: sorted batch (a run) written to one temporary file, and the runs merged; memory stays
#: bounded by a batch, the disk takes about the dataset's encoded rows twice.
BATCH_ROWS = 65_536
_RECORD = struct.Struct("<IIII")  # a run's record: key, row, file row lengths; file number
_BLOCK = 1 << 15  # bytes read from each run at a time while merging, when there are few runs
_MERGE_BYTES = 1 << 23  # the read buffers of all runs together, down to 4 KiB a run (#309)

#: (sort key, cell bytes, file number, the file's own cell bytes or b"" when the same)
Record = tuple[bytes, bytes, int, bytes]


def _partitions(rel: str, partitioning: list[dict[str, Any]], names: list[str]) -> dict[str, Any]:
    """A file's partition values from its path (TDS 4.5 step 1), as Arrow scalars."""
    parts = dict(p.split("=", 1) for p in Path(rel).parent.parts if "=" in p)
    out = {}
    for part in partitioning:
        name, tag = part["name"], part["type"]
        if name not in parts or name in names:
            raise HashError(f"{rel}: partition {name} has no value in the path only")
        if tag not in _PARTITION:
            raise HashError(f"partition {name}: type `{tag}` has no path rule")
        kind = pa.date32() if tag == "date" else _ARROW.get(tag, pa.string())
        out[name] = pa.scalar(_PARTITION[tag](parts[name]), kind)
    return out


def resolved_columns(dataset: Mapping[str, Any], schema: Sequence[Column]) -> tuple[Column, ...]:
    """The dataset's full schema: the schema file's columns, then those its `tds.json` `columns`
    declares that the file lacks, in declaration order (TDS 4.5 step 1; 5.25's panels).

    The one place a dataset's column set is resolved: the value hash and the schema-level checks
    read it. A declared column keeps its declared type and is not required (`null` unknown); a
    partition or `x_` column declared there keeps its own place after these."""
    from .schemas.verify import Column

    known = {c.name for c in schema}
    known |= {str(p.get("name")) for p in _entries(dataset.get("partitioning"))}
    extra = [
        Column(str(c["name"]), c.get("type"), None)
        for c in _entries(dataset.get("columns"))
        if "name" in c and c["name"] not in known and not str(c["name"]).startswith("x_")
    ]
    return (*schema, *{c.name: c for c in extra}.values())


def _entries(value: object) -> list[Mapping[str, Any]]:
    return [e for e in value if isinstance(e, Mapping)] if isinstance(value, list) else []


def _columns(names: Sequence[str], dataset: Mapping[str, Any], schema: list[Any]) -> Columns:
    """The resolved columns present in the data, then partition columns they lack, then `x_`
    columns (TDS 4.5 step 1).

    The tag is the type declared in `tds.json` (`columns`, `partitioning`), else the schema's.
    A column in none of these groups is an unknown column, ignored (TDS 10.3, M011).
    """
    declared = {c["name"]: c.get("type") for c in dataset.get("columns", []) if "name" in c}
    declared |= {p["name"]: p["type"] for p in dataset.get("partitioning", [])}
    resolved = resolved_columns(dataset, schema)
    resolved_types = {c.name: c.type for c in resolved}
    order = [c.name for c in resolved if c.name in names]
    order += [p["name"] for p in dataset.get("partitioning", []) if p["name"] not in order]
    order += sorted(n for n in names if n.startswith("x_"))
    out = []
    for name in order:
        tag = declared.get(name) or resolved_types.get(name) or ""
        if tag not in _TAGS and not (tag.startswith("list<") and tag[5:-1] in _TAGS):
            raise HashError(f"{dataset['name']}: column {name} has no declared type (`{tag}`)")
        out.append((name, tag))
    return out


def _runs(
    root: Path, entry: Mapping[str, Any], own: list[Columns], columns: Columns, key: list[str]
) -> Iterator[list[Record]]:
    """The rows in runs of `BATCH_ROWS` or more (up to two batches), each sorted by the dataset's
    row order. A file's own rows in that order are in its own: a column it lacks is all null."""
    run: list[Record] = []
    for i, f in enumerate(entry["files"]):
        source = pq.ParquetFile(inside(root, f["path"]))
        parts = _partitions(f["path"], entry.get("partitioning", []), source.schema_arrow.names)
        for batch in source.iter_batches(batch_size=BATCH_ROWS):
            table = pa.Table.from_batches([batch])
            for name, value in parts.items():
                table = table.append_column(name, pa.repeat(value, table.num_rows))
            rows = _rows(table, columns, key)
            mine = [r for _, r in _rows(table, own[i], key)] if own[i] != columns else None
            run += ((k, r, i, mine[j] if mine else b"") for j, (k, r) in enumerate(rows))
            if len(run) >= BATCH_ROWS:
                yield sorted(run, key=itemgetter(0))
                run = []
    if run:
        yield sorted(run, key=itemgetter(0))


def _run(fd: int, start: int, end: int, block: int = _BLOCK) -> Iterator[Record]:
    """One run of the temporary file, read `block` bytes at a time; a read that returns fewer
    bytes (a network file system may) is followed by another, until the run's end."""
    buf, pos, at = b"", 0, start

    def fill(n: int) -> None:
        nonlocal buf, pos, at
        while len(buf) - pos < n:
            if not (more := os.pread(fd, min(max(n, block), end - at), at)):
                raise HashError("a temporary sort file ended early")
            buf, pos, at = buf[pos:] + more, 0, at + len(more)

    while pos < len(buf) or at < end:
        fill(_RECORD.size)
        k, r, i, m = _RECORD.unpack_from(buf, pos)
        fill(_RECORD.size + k + r + m)
        s = pos + _RECORD.size
        yield buf[s : s + k], buf[s + k : s + k + r], i, buf[s + k + r : s + k + r + m]
        pos = s + k + r + m


class SortedRuns:
    """Runs of records, each sorted by its key, added one at a time; `merged` gives them all in
    key order. One run stays in memory; from a second on, every run goes to one temporary file
    in `folder`, listed in `spilled` and removed on leaving its `with`."""

    def __init__(self, folder: Path, spilled: list[Path]) -> None:
        self.folder, self.spilled = folder, spilled
        self.first: list[Record] = []
        self.out: Any = None  # the temporary file and its name, once a second run comes
        self.name = ""
        self.spans: list[tuple[int, int]] = []

    def add(self, run: list[Record]) -> None:
        if not run:
            return
        if self.out is None and not self.first:
            self.first = run
            return
        if self.out is None:
            try:
                fd, self.name = tempfile.mkstemp(".tmp", ".tds-hash-", self.folder)
            except OSError as exc:  # not "a file Parquet cannot read": say which folder
                raise HashError(f"no temporary file in {self.folder}: {exc.strerror}") from exc
            self.spilled.append(Path(self.name))
            self.out = open(fd, "w+b")  # noqa: SIM115 - closed by `__exit__`
            self._write(self.first)
            self.first = []
        self._write(run)

    def _write(self, run: list[Record]) -> None:
        start = self.out.tell()
        self.out.writelines(_RECORD.pack(len(k), len(r), i, len(m)) + k + r + m
                            for k, r, i, m in run)  # fmt: skip
        self.spans.append((start, self.out.tell()))

    def merged(self) -> Iterator[Record]:
        if self.out is None:
            return iter(self.first)
        self.out.flush()
        fd, block = self.out.fileno(), min(_BLOCK, max(_MERGE_BYTES // len(self.spans), 4096))
        return heapq.merge(*(_run(fd, a, b, block) for a, b in self.spans), key=itemgetter(0))

    def __enter__(self) -> SortedRuns:
        return self

    def __exit__(self, *exc: object) -> None:  # the temporary file goes, an exception included
        if self.out is not None:
            self.out.close()
            os.unlink(self.name)


@contextmanager
def _merged(runs: Iterator[list[Record]], folder: Path, spilled: list[Path]) -> Iterator[Any]:
    """The runs' records in key order (`SortedRuns`)."""
    with SortedRuns(folder, spilled) as sink:
        for run in runs:
            sink.add(run)
        yield sink.merged()


def dataset_hashes(
    root: Path, entry: Mapping[str, Any], folder: Path, spilled: list[Path]
) -> tuple[str, dict[str, str]]:
    """The dataset's value hash and each file's, in one read of its rows (TDS 4.5); sorted runs
    go to `folder` when the dataset is more than one batch."""
    from .schemas.verify import dictionary_schemas, load_schemas

    schemas = load_schemas() | dictionary_schemas()
    if (schema := schemas.get(entry["kind"])) is None:
        raise HashError(f"{entry['name']}: kind {entry['kind']} has no schema file, no types")
    if not entry["files"]:
        raise HashError(f"{entry['name']}: no files, no rows to hash")
    if len({f["path"] for f in entry["files"]}) < len(entry["files"]):
        raise HashError(f"{entry['name']}: a file is listed twice (TDS-M013)")
    names = []
    for f in entry["files"]:
        stored = pq.read_schema(inside(root, f["path"])).names
        names.append([*stored, *_partitions(f["path"], entry.get("partitioning", []), stored)])
    own = [_columns(n, entry, list(schema.columns)) for n in names]
    columns = _columns(sorted({c for n in names for c in n}), entry, list(schema.columns))
    key = entry.get("key", schema.key)
    if isinstance(key, dict):  # bars: the daily or the intraday key, by `params.freq`
        key = key["daily" if entry.get("params", {}).get("freq") == "1d" else "intraday"]
    key = key if isinstance(key, list) else []
    for cols in (columns, *own):
        if missing := [k for k in key if k not in dict(cols)]:
            raise HashError(f"{entry['name']}: key column {', '.join(missing)} is not in the data")
    whole, each = hashlib.sha256(_header(columns)), [hashlib.sha256(_header(c)) for c in own]
    with _merged(_runs(root, entry, own, columns, key), folder, spilled) as records:
        for _, row, i, mine in records:
            whole.update(row)
            each[i].update(mine or row)
    paths = [f["path"] for f in entry["files"]]
    return whole.hexdigest(), {p: h.hexdigest() for p, h in zip(paths, each, strict=True)}


def value_hash(path: Path, dataset: str) -> str:
    """The dataset's `value_sha256` (TDS 4.5): sha256 of its canonical value serialisation."""
    root = Path(path)
    (entry,) = (d for d in read_manifest(root).datasets if d.get("name") == dataset)
    return dataset_hashes(root, entry, spill_folder(root, None), [])[0]


def spill_folder(root: Path, tmp_dir: Path | None) -> Path:
    """Where sorted runs go: the folder named, else the package's own parent folder (never the
    system's temporary folder: the runs hold the producer's rows)."""
    return Path(tmp_dir) if tmp_dir is not None else Path(root).resolve().parent


def spilled_note(spilled: list[Path], what: str = "value hash") -> str:
    """The one line saying where the sorted runs were written."""
    where = ", ".join(sorted({str(p.parent) for p in spilled}))
    return f"{what}: {len(spilled)} temporary file(s) of sorted rows in {where}, removed"


HASH_SPEC = "tds-hash-1"
#: The package-level keys of the semantic hash (TDS 4.5), each `null` when tds.json has none.
_PACKAGE_KEYS = ("markets", "id_namespaces", "editions", "policies", "currencies", "roll_rules")
_DATASET_KEYS = ("kind", "schema_version", "params", "availability", "pit_quality", "key")
#: The stable fields of a `markets` entry, the only ones the semantic hash takes (TDS 4.5): the
#: watermark fields of 4.2 change on every publish (spec 5.3.9 keys its L0 cache on these three).
_MARKET_KEYS = ("calendar_id", "currency", "timezone")


def _markets(markets: Any) -> Any:
    """Each entry of `markets` cut to its stable fields; absent ones stay absent.

    A `markets` that is not an object, or an entry that is not one, is kept as it is: the
    manifest level reports that shape, and the hash still sees it."""
    if not isinstance(markets, dict):
        return markets
    return {
        name: {k: e[k] for k in _MARKET_KEYS if k in e} if isinstance(e, dict) else e
        for name, e in markets.items()
    }


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


def file_sha256(path: Path) -> str:
    """sha256 of a file's bytes, read in blocks."""
    with open(path, "rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def _inventory(
    root: Path, folder: Path, spilled: list[Path]
) -> tuple[dict[str, str], dict[str, dict[str, str]], list[Any]]:
    """Per dataset its value hash, per file its sha256 and value hash, and the semantic entries."""
    datasets: dict[str, str] = {}
    files: dict[str, dict[str, str]] = {}
    semantic = []
    for entry in read_manifest(root).datasets:
        name = str(entry.get("name"))  # required (TDS-M003); the manifest level reports its absence
        try:
            for f in entry["files"]:
                if f["path"] in files:
                    raise HashError(f"{f['path']} is listed twice (TDS-M013)")
                files[f["path"]] = {"sha256": file_sha256(inside(root, f["path"]))}
            datasets[name], values = dataset_hashes(root, entry, folder, spilled)
            for path, value in values.items():
                files[path]["value_sha256"] = value
        except HashError:
            raise  # already says which dataset or file
        except (OSError, KeyError, TypeError, ValueError, struct.error, pa.ArrowException) as exc:
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
    doc["markets"] = _markets(doc["markets"])
    return canonical_json(doc)


def semantic_json(path: Path) -> str:
    """The canonical JSON the semantic hash is taken over (TDS 4.5)."""
    return _semantic(Path(path), _inventory(Path(path), spill_folder(path, None), [])[2])


def package_hashes(
    path: Path, *, tmp_dir: Path | None = None, spilled: list[Path] | None = None
) -> dict[str, Any]:
    """Every TDS 4.5 hash of the package: `physical_sha256`, `value_sha256`, `semantic_sha256`,
    `datasets` {name: value_sha256} and `files` {path: {sha256, value_sha256}}. `spilled` gets
    each temporary file of sorted runs written (in `tmp_dir`, else beside the package), each
    already removed."""
    root = Path(path)
    spilled = [] if spilled is None else spilled
    datasets, files, entries = _inventory(root, spill_folder(root, tmp_dir), spilled)
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


def write_hashes(
    path: Path, *, tmp_dir: Path | None = None, spilled: list[Path] | None = None
) -> dict[str, Any]:
    """`tds hash --write`: put every hash into tds.json, the rest of it unchanged (TDS 8.1)."""
    root = Path(path)
    hashes = package_hashes(root, tmp_dir=tmp_dir, spilled=spilled)
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
