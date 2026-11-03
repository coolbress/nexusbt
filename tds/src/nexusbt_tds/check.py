"""`check(path, *, level, ...) -> CheckResult`: the levels manifest, schema and full (TDS 8.2).

The `manifest` level reads `tds.json` and file sizes (M001~M014); the `schema` level adds the
Parquet footers and statistics and the `dictionary/` tables, no data rows (S001~S010); the `full`
level adds, so far, the hashes (H001~H003, TDS 4.5) and verifies no profile beyond `schema`. None
reports a profile as `pass`: the rules a level cannot see are listed in `unchecked`, and the
profile is `not_checked`.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import os
import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Literal

import pyarrow as pa
import pyarrow.parquet as pq

from .manifest import MANIFEST, Manifest, ManifestError, read_manifest
from .profiles import PROFILES, Need, describe, meets, profile_id

Level = Literal["manifest", "schema", "full"]
Severity = Literal["error", "warning"]

#: TDS 8.3, the codes the `manifest` level cannot see (M015 comes with the schema files, T0.13b).
_ROW_CODES = (
    "M015 S001 S002 S003 S004 S005 S006 S007 S008 S009 S010 K001 K002 K003 K004 K010 K011"
    " R001 R002 R003 R004 R005 R006 R007 R008 R009 T001 T002 T003 T004 T005 T006 T007 T008"
    " T010 T011 T012 D001 D002 D004 A001 A002 A003 A004 A005 A006 A007 A008 A009 A010 A011"
    " V001 V002 V004 V005 V010 V011 V012 V020 V030 V031 V032 V040 V041 V050 H001 H002 H003 H004"
)
UNCHECKED_AT_MANIFEST = tuple(f"TDS-{c}" for c in _ROW_CODES.split())
#: What the `schema` level judges from footers. S006 and S007 see only a column's minimum and
#: maximum; S009 sees ±Inf in the statistics but never NaN, which writers leave out of them, so
#: it stays unchecked.
SCHEMA_CODES = tuple(f"TDS-S{n:03}" for n in (1, 2, 3, 4, 5, 6, 7, 8, 10))
UNCHECKED_AT_SCHEMA = tuple(c for c in UNCHECKED_AT_MANIFEST if c not in SCHEMA_CODES)

#: TDS 4.2: the fields marked ○ that are required unconditionally.
REQUIRED: tuple[str, ...] = ("tds_version", "name", "created", "snapshot_id", "producer")
REQUIRED += ("profiles", "id_namespaces", "markets", "datasets", "hashes", "writer")
#: 4.2 lists more fields without saying which are required; until #79 decides, the ones the
#: manifest-level checks need (#51, Decisions 2026-11-02). A file needs `path` and `bytes`.
DATASET_REQUIRED = ("name", "kind", "schema_version", "path", "files")
FILE_REQUIRED = ("path", "bytes")  # TDS 4.2; checked one by one in _check_dataset
_OBJECTS = ("producer", "id_namespaces", "markets", "hashes", "writer")
HASH_SPECS = frozenset({"tds-hash-1"})  # 4.5
SUPPORTED_MAJOR = 1  # 10.3
#: The newest dataset `schema_version` MINOR this checker knows; per kind with T0.13b's files.
KNOWN_MINOR = 0

# TDS 6.2: the availability rule names. An unknown one is M014, never ignored.
_DUR = r"P(?=\d|T\d)(\d+Y)?(\d+M)?(\d+W)?(\d+D)?(T(?=\d)(\d+H)?(\d+M)?(\d+(\.\d+)?S)?)?"
_COL = r"[a-z_][a-z0-9_]*"
RULE = re.compile(
    rf"column|ts_end|ts_end\+{_DUR}|session_open|session_close|next_session_open(\({_COL}\))?"
    rf"|ts_recv|ts_recv\+{_DUR}|ts_recv_else\({_COL}\+{_DUR}\)"
)
#: TDS 5.5's `params` lists, closed and affecting execution: a value outside them is M014. TDS
#: does not mark them closed or open; chosen with the maintainer (#80 Decisions, 2026-11-03).
CLOSED_PARAMS: Mapping[str | None, Mapping[str, tuple[str, ...]]] = {
    "bars": {
        "price_basis": ("raw", "split_adjusted", "total_adjusted"),
        "density": ("dense", "sparse"),
        "bar_time": ("session", "utc_day", "interval"),
    }
}
_VERSION = re.compile(r"(\d+)\.(\d+)")
_PROFILE = re.compile(r"tds:[a-z0-9-]+@\d+\.\d+")


@dataclass(frozen=True, slots=True)
class ProfileStatus:
    declared: bool
    verified_level: Literal["none"] | Level
    result: Literal["pass", "fail", "not_checked"]


@dataclass(frozen=True, slots=True)
class Finding:
    """One line of TDS 8.4's JSON Lines output."""

    code: str
    severity: Severity
    message: str
    dataset: str | None = None
    file: str | None = None
    key: Mapping[str, object] | None = None
    count: int | None = None
    hint: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass(frozen=True, slots=True)
class CheckResult:
    level: Level
    errors: tuple[Finding, ...]
    warnings: tuple[Finding, ...]
    profiles: dict[str, ProfileStatus] = field(default_factory=dict)
    unchecked: list[str] = field(default_factory=list)
    #: Every error found; `errors` holds at most `max_errors` of them (TDS 8.4 summary, #80).
    error_count: int = 0

    @property
    def failed(self) -> bool:
        return self.error_count > 0 or bool(self.errors)

    def summary(self) -> dict[str, object]:
        return {
            "errors": max(self.error_count, len(self.errors)),
            "warnings": len(self.warnings),
            "level": self.level,
            "profiles": {name: asdict(status) for name, status in self.profiles.items()},
            "unchecked": self.unchecked,
        }

    def to_jsonl(self) -> str:
        """TDS 8.4: one object per finding, then the summary line."""
        lines = [f.to_dict() for f in (*self.errors, *self.warnings)]
        lines.append({"summary": self.summary()})
        return "".join(json.dumps(line, ensure_ascii=False) + "\n" for line in lines)


def check(
    path: Path,
    *,
    level: Level,
    profiles: Sequence[str] | None = None,
    datasets: Sequence[str] | None = None,
    max_errors: int = 1000,
) -> CheckResult:
    manifest: Manifest | None = None
    blind: set[str] = set()  # codes this package's files hide from the level (no statistics)
    try:
        manifest = read_manifest(path)
        found = list(_check_manifest(manifest, datasets))
        if level != "manifest":
            found += _check_schema(manifest, datasets, blind)
        if level == "full":
            found += _check_hashes(manifest, datasets, blind)
    except ManifestError as exc:
        found = [Finding("TDS-M001", "error", str(exc))]
    declared = {profile_id(p) for p in manifest.profiles} if manifest else set()
    wanted = [profile_id(p) for p in profiles] if profiles is not None else sorted(declared)
    statuses: dict[str, ProfileStatus] = {}
    package_failed = any(f.severity == "error" for f in found)
    for name in dict.fromkeys(wanted):
        own = list(_check_profile(manifest, name)) if manifest else []
        found += own
        # `full` checks only H001~H003 so far (#57): no profile is verified to it (spec 8.2)
        verified: Level = "schema" if level == "full" else level
        statuses[name] = ProfileStatus(
            declared=name in declared,
            verified_level=verified if name in PROFILES else "none",
            result="fail" if package_failed or own else "not_checked",
        )
    hints = manifest.hints if manifest else {}
    found = [f if f.hint or f.code not in hints else replace(f, hint=hints[f.code]) for f in found]
    errors = tuple(f for f in found if f.severity == "error")
    return CheckResult(
        level=level,
        error_count=len(errors),
        errors=errors[: max(max_errors, 0)],
        warnings=tuple(f for f in found if f.severity == "warning"),
        profiles=statuses,
        unchecked=list(UNCHECKED_AT_MANIFEST)
        if level == "manifest"
        else [
            c
            for c in UNCHECKED_AT_MANIFEST
            if c in blind
            or (c in UNCHECKED_AT_SCHEMA and (level == "schema" or c not in HASH_CODES))
        ],
    )


#: What the `full` level checks so far: the declared hashes against the computed ones (TDS 4.5).
HASH_CODES = ("TDS-H001", "TDS-H002", "TDS-H003")


def _check_hashes(m: Manifest, only: Sequence[str] | None, blind: set[str]) -> list[Finding]:
    """H001 each declared file sha256, H002 each dataset value hash, H003 the package hashes."""
    from .hash import HashError, inside, package_hashes

    out = []
    seen: set[object] = set()  # a path listed twice is M013's; its H001, once
    datasets = [d for d in m.datasets if only is None or d.get("name") in only]
    for ds in datasets:
        for f in (f for f in ds.get("files") or [] if isinstance(f, dict) and "sha256" in f):
            if f.get("path") in seen:
                continue
            seen.add(f.get("path"))
            try:
                actual = hashlib.sha256(inside(m.root, f.get("path")).read_bytes()).hexdigest()
            except (HashError, OSError):
                continue  # outside the package or missing: the manifest level's (M004, M012)
            if actual != f["sha256"]:
                message = f"sha256 {actual}, declared {f['sha256']}"
                out.append(Finding("TDS-H001", "error", message, ds.get("name"), f["path"]))
    try:
        hashes = package_hashes(m.root)
    except Exception:  # no value hash for this package, whatever the cause: H002, H003 not judged
        blind.update(("TDS-H002", "TDS-H003"))
        return out
    for ds in datasets:
        declared, actual = ds.get("value_sha256"), hashes["datasets"].get(ds.get("name"))
        if declared is not None and declared != actual:
            out.append(Finding("TDS-H002", "error", f"value hash {actual}, declared {declared}",
                               dataset=ds.get("name")))  # fmt: skip
    declared_hashes = m.data.get("hashes")
    for key in ("physical_sha256", "value_sha256", "semantic_sha256"):
        declared = declared_hashes.get(key) if isinstance(declared_hashes, dict) else None
        if declared is not None and declared != hashes[key]:
            out.append(Finding("TDS-H003", "error", f"{key} {hashes[key]}, declared {declared}"))
    return out


def _check_manifest(m: Manifest, only: Sequence[str] | None) -> Iterable[Finding]:
    data = m.data
    for key in REQUIRED:
        if key not in data:
            yield Finding("TDS-M003", "error", f"required manifest field {key!r} is missing")
    for key in _OBJECTS:
        if key in data and not isinstance(data[key], dict):
            yield Finding("TDS-M001", "error", f"{key!r} is not a JSON object")
    for key in ("profiles", "datasets"):
        if key in data and not isinstance(data[key], list):
            yield Finding("TDS-M001", "error", f"{key!r} is not a JSON array")
    if isinstance(data.get("profiles"), list) and len(m.profiles) != len(data["profiles"]):
        yield Finding("TDS-M001", "error", "'profiles' holds a value that is not a string")
    if "tds_version" in data and _major(data["tds_version"]) != SUPPORTED_MAJOR:
        msg = f"tds_version {data['tds_version']!r} is not supported (MAJOR {SUPPORTED_MAJOR})"
        yield Finding("TDS-M002", "error", msg)
    hashes = data.get("hashes")
    spec = hashes.get("hash_spec") if isinstance(hashes, dict) else None
    if spec is not None and not (isinstance(spec, str) and spec in HASH_SPECS):
        yield Finding("TDS-M014", "error", f"unknown hash_spec {spec!r}")
    markets, editions = data.get("markets"), data.get("editions")
    values = editions.get("values") if isinstance(editions, dict) else None
    declared: dict[str, set[str]] = {
        "market": set(markets) if isinstance(markets, dict) else set(),
        "edition": set(values) if isinstance(values, dict) else set(),
    }

    root = m.root.resolve()
    listed: set[str] = set()
    for ds in m.datasets:
        name = ds["name"] if isinstance(ds.get("name"), str) else None
        if only is not None and name not in only:
            continue
        coverage = ds.get("coverage")
        by_market = coverage.get("by_market") if isinstance(coverage, dict) else None
        for market in sorted(by_market) if isinstance(by_market, dict) else []:
            if market not in declared["market"]:
                msg = f"coverage.by_market names market {market!r}, not declared in tds.json"
                yield Finding("TDS-M010", "error", msg, dataset=name)
        yield from _check_dataset(root, ds, name, listed, declared)
    if only is None:
        for rel in _walk(root):
            if rel not in listed and rel != MANIFEST:
                yield Finding("TDS-M005", "warning", "file is not listed in tds.json", file=rel)


def _check_dataset(
    root: Path,
    ds: Mapping[str, Any],
    name: str | None,
    listed: set[str],
    declared: Mapping[str, set[str]],
) -> Iterable[Finding]:
    for key in DATASET_REQUIRED:
        if key not in ds:
            yield Finding("TDS-M003", "error", f"dataset field {key!r} is missing", dataset=name)
    if "schema_version" in ds:
        version = _VERSION.fullmatch(str(ds["schema_version"]))
        if version is None or int(version[1]) != SUPPORTED_MAJOR:
            msg = f"schema_version {ds['schema_version']!r} is not supported"
            yield Finding("TDS-M009", "error", msg, dataset=name)
        elif int(version[2]) > KNOWN_MINOR:
            msg = f"schema_version {ds['schema_version']} is newer than this checker"
            yield Finding("TDS-M011", "warning", msg, dataset=name)
    for rule in _rules(ds):
        if not isinstance(rule, str) or not RULE.fullmatch(rule):
            yield Finding("TDS-M014", "error", f"unknown availability rule {rule!r}", dataset=name)
    params = ds["params"] if isinstance(ds.get("params"), dict) else {}
    kind = ds.get("kind") if isinstance(ds.get("kind"), str) else None  # `["bars"]`: no crash
    for key, values in CLOSED_PARAMS.get(kind, {}).items():
        if key in params and params[key] not in values:  # absent is no value; null is one
            msg = f"params.{key} {params[key]!r} is not one of {', '.join(values)}"
            yield Finding("TDS-M014", "error", msg, dataset=name)
    if isinstance(ds.get("path"), str) and (why := _unsafe(root, ds["path"])):
        yield Finding("TDS-M012", "error", f"dataset path {why}", dataset=name, file=ds["path"])
    files = ds.get("files")
    for entry in files if isinstance(files, list) else []:
        rel = entry.get("path") if isinstance(entry, dict) else None
        if not isinstance(rel, str):
            yield Finding("TDS-M003", "error", "a files[] entry has no 'path'", dataset=name)
            continue
        if why := _unsafe(root, rel):
            yield Finding("TDS-M012", "error", f"file path {why}; not read", dataset=name, file=rel)
            continue
        norm = str(PurePosixPath(rel))
        if norm in listed:
            yield Finding("TDS-M013", "error", "file path listed twice", dataset=name, file=rel)
            continue
        listed.add(norm)
        for part in PurePosixPath(norm).parts[:-1]:
            column, eq, value = part.partition("=")
            if eq and column in declared and value not in declared[column]:
                msg = f"{column} {value!r} is not declared in tds.json"
                yield Finding("TDS-M010", "error", msg, dataset=name, file=rel)
        target = root / norm
        if not target.is_file():
            yield Finding("TDS-M004", "error", "listed file is missing", dataset=name, file=rel)
        elif "bytes" not in entry:
            yield Finding(
                "TDS-M003", "error", "files[] entry has no 'bytes'", dataset=name, file=rel
            )
        elif target.stat().st_size != entry["bytes"]:
            msg = f"file has {target.stat().st_size} bytes, tds.json says {entry['bytes']}"
            yield Finding("TDS-M006", "error", msg, dataset=name, file=rel)


_string = pa.types.is_string
#: TDS 3.2: whether an Arrow type is the TDS type (a timestamp's unit and zone are S004's).
_IS: dict[str, Callable[[pa.DataType], bool]] = {
    **dict.fromkeys(("id", "code"), lambda t: _string(t) or (
        pa.types.is_dictionary(t) and _string(t.value_type))),  # 3.2, 3.7: dictionary strings
    **dict.fromkeys(("string", "json"), _string),
    **dict.fromkeys(("ts_us", "ts_ns", "ts_us/ns"), pa.types.is_timestamp),
    "date": pa.types.is_date32, "f64": pa.types.is_float64, "fixed": pa.types.is_int64,
    "i8": pa.types.is_int8, "i16": pa.types.is_int16, "i32": pa.types.is_int32,
    "i64": pa.types.is_int64, "bool": pa.types.is_boolean,
    "list<code>": lambda t: pa.types.is_list(t) and _string(t.value_type),
}  # fmt: skip
_UNITS = {"ts_us": {"us"}, "ts_ns": {"ns"}, "ts_us/ns": {"us", "ns"}}  # K2; `ts_us/ns`: #56
_BITS = {"i8": 8, "i16": 16, "i32": 32, "i64": 64}
#: Without tds.json `partitioning`: 3.6's examples, any other a code (rule chosen in #56).
_PARTITION_TYPE = {"year": "i16", "date": "date"}


def _required(null: object, params: Mapping[str, Any]) -> bool:
    """A schema `null` cell as "may not be null"; its conditions read `params` (rule of #56)."""
    if null == "daily yes / intraday no":
        return params.get("freq") != "1d"
    if null == "no if dense":
        return params.get("density") == "dense"
    return null is False


def _fits(tag: str, value: str) -> bool:
    """TDS 3.6: a partition path value read as its type (S008)."""
    if tag in _BITS:
        bound = 2 ** (_BITS[tag] - 1)
        return re.fullmatch(r"-?\d+", value) is not None and -bound <= int(value) < bound
    if tag == "date":
        try:
            return dt.date.fromisoformat(value).isoformat() == value
        except ValueError:
            return False
    return value != ""


def _check_schema(m: Manifest, only: Sequence[str] | None, blind: set[str]) -> list[Finding]:
    """S001~S010 from each listed, readable Parquet file's footer (TDS 8.2)."""
    from .schemas.verify import load_schemas

    schemas, root, out = load_schemas(), m.root.resolve(), []
    codes = _dictionary_codes(m, root)
    for ds in m.datasets:
        schema = schemas.get(str(ds.get("kind")))
        version = _VERSION.fullmatch(str(ds.get("schema_version")))
        skip = only is not None and ds.get("name") not in only
        if skip or schema is None or not version or int(version[1]) != SUPPORTED_MAJOR:  # M009
            continue
        files = ds.get("files")
        for entry in files if isinstance(files, list) else []:
            rel = entry.get("path") if isinstance(entry, dict) else None
            if isinstance(rel, str) and not _unsafe(root, rel) and (root / rel).is_file():
                found = _check_file(root, rel, ds, schema, blind, codes)
                out += [replace(f, dataset=ds.get("name"), file=rel) for f in found]
    return out


def _dictionary_codes(m: Manifest, root: Path) -> set[tuple[str, str]]:
    """TDS 4.4 `dictionary/codes` as (`field`, `code`); `field` is a column name (#117)."""
    out: set[tuple[str, str]] = set()
    for ds in m.datasets:
        files = ds.get("files") if "dictionary/codes" in (ds.get("kind"), ds.get("path")) else []
        for entry in files if isinstance(files, list) else []:
            rel = entry.get("path") if isinstance(entry, dict) else None
            if not isinstance(rel, str) or _unsafe(root, rel) or not (root / rel).is_file():
                continue
            try:
                rows = pq.ParquetFile(root / rel).read(columns=["field", "code"]).to_pylist()
            except (OSError, pa.ArrowException):  # unreadable: it excuses nothing
                continue
            pairs = ((row.get("field"), row.get("code")) for row in rows)  # a column may be absent
            out.update((str(f), str(c)) for f, c in pairs if f is not None and c is not None)
    return out


def _by_name(entries: object) -> dict[str, Any]:  # tds.json `columns`, `partitioning`: name → type
    items = entries if isinstance(entries, list) else []
    return {str(e["name"]): e.get("type") for e in items if isinstance(e, dict) and "name" in e}


def _check_file(
    root: Path,
    rel: str,
    ds: Mapping[str, Any],
    schema: Any,
    blind: set[str],
    codes: set[tuple[str, str]],
) -> Iterable[Finding]:
    try:
        meta = pq.ParquetFile(root / rel).metadata
        arrow = meta.schema.to_arrow_schema()
    except (OSError, pa.ArrowException):  # not Parquet: nothing this level can read
        blind.update(SCHEMA_CODES)
        return
    params: dict[str, Any] = ds["params"] if isinstance(ds.get("params"), dict) else {}
    declared, typed = _by_name(ds.get("columns")), _by_name(ds.get("partitioning"))
    kv = {k: v.decode(errors="replace") for k, v in (meta.metadata or {}).items()}
    names = [str(ds.get("name")), str(ds.get("kind"))]  # either names the dataset (rule of #56)
    version = kv.get(b"tds.schema_version") == ds.get("schema_version")
    if kv.get(b"tds.dataset") not in names or not version:
        yield Finding("TDS-S010", "error", "tds.dataset/tds.schema_version missing or different")
    parts = dict(p.split("=", 1) for p in PurePosixPath(rel).parent.parts if "=" in p)  # 3.6
    for key, value in parts.items():
        tag = typed.get(key) or _PARTITION_TYPE.get(key, "code")
        if not _fits(str(tag), value):
            yield Finding("TDS-S008", "error", f"partition {key}={value!r} is not a {tag}")
        if key in arrow.names:
            yield Finding("TDS-S008", "error", f"partition column {key} is also inside the file")
    known = {c.name for c in schema.columns}
    for column in schema.columns:
        if column.name not in arrow.names:
            if column.name not in parts and _required(column.null, params):
                yield Finding("TDS-S001", "error", f"required column {column.name} is missing")
            continue
        required = _required(column.null, params)
        yield from _check_column(meta, arrow, column, required, declared.get(column.name), blind)
        yield from _check_values(meta, arrow, column, codes, blind)
    newer = int(str(ds["schema_version"]).split(".")[1]) > KNOWN_MINOR  # M011: ignore unknown
    for name in [] if newer else arrow.names:
        if name not in known and name not in parts and not name.startswith("x_"):
            yield Finding("TDS-S005", "warning", f"unknown column {name} (not `x_`)")


def _check_column(
    meta: Any, arrow: pa.Schema, column: Any, required: bool, unit: Any, blind: set[str]
) -> Iterable[Finding]:
    """S002, S003, S004, S009 of one column; `unit`: its tds.json `columns[].type`."""
    name, tag, kind = column.name, column.type, arrow.types[arrow.names.index(column.name)]
    paths = [meta.schema.column(i).path for i in range(meta.num_columns)]
    index = paths.index(name) if name in paths else None  # None: a nested column
    if index is not None and meta.schema.column(index).physical_type == "INT96":
        yield Finding("TDS-S004", "error", f"{name} is written as INT96 (TDS 3.7)")
        return
    if tag in _IS and not _IS[tag](kind):
        yield Finding("TDS-S002", "error", f"{name} is {kind}, TDS type {tag}")
        return
    if tag in _UNITS:  # tds.json `columns[].type` names the unit of a `ts_us/ns` column (#57)
        units = _UNITS.get(str(unit), _UNITS[tag])
        if kind.tz != "UTC" or kind.unit not in units:
            yield Finding("TDS-S004", "error", f"{name} is {kind}, wants UTC {'/'.join(units)}")
    if index is None:  # its statistics are its leaves'
        return
    stats = [meta.row_group(g).column(index).statistics for g in range(meta.num_row_groups)]
    if required and any(s is None or not s.has_null_count for s in stats):
        blind.add("TDS-S003")
    elif required and (nulls := sum(s.null_count for s in stats)):
        yield Finding("TDS-S003", "error", f"{name} may not be null", count=nulls)
    seen = [v for s in stats if s is not None and s.has_min_max for v in (s.min, s.max)]
    if tag == "f64" and any(math.isinf(v) for v in seen):
        yield Finding("TDS-S009", "error", f"{name} holds ±Inf (statistics; NaN is not visible)")


def _check_values(
    meta: Any, arrow: pa.Schema, column: Any, codes: set[tuple[str, str]], blind: set[str]
) -> Iterable[Finding]:
    """S006 (closed) and S007 (open, unless in `dictionary/codes`) of one enum column.

    A row group's minimum and maximum are values it holds; they are all its values only when
    equal. Any other row group leaves the code unchecked: what lies between is not in a footer.
    pyarrow does not say whether a writer truncated a statistic; one read here is taken as exact.
    """
    name, values = column.name, column.values
    paths = [meta.schema.column(i).path for i in range(meta.num_columns)]
    kind = arrow.types[arrow.names.index(name)]
    if values is None or name not in paths or not _IS["code"](kind):  # S002 names a wrong type
        return
    code, closed = ("TDS-S006", True) if column.enum == "closed" else ("TDS-S007", False)
    index, seen = paths.index(name), set()
    for g in range(meta.num_row_groups):
        s = meta.row_group(g).column(index).statistics
        if s is not None and s.has_min_max:
            seen |= {_text(s.min), _text(s.max)}
        if s is None or (s.min != s.max if s.has_min_max else s.num_values):
            blind.add(code)
    for value in sorted(seen):
        if not _listed(value, values) and (closed or (name, value) not in codes):
            msg = f"{name} holds {value!r}, not in its {column.enum} list"
            yield Finding(code, "error" if closed else "warning", msg)


def _text(value: object) -> str:
    return value.decode(errors="replace") if isinstance(value, bytes) else str(value)


def _listed(value: str, values: Sequence[str]) -> bool:
    """`<name>` in a listed value stands for any non-empty text (`vendor:<name>`, #117)."""
    return any(re.fullmatch(re.sub(r"<\w+>", ".+", re.escape(v)), value) for v in values)


def _check_profile(m: Manifest, name: str) -> Iterable[Finding]:
    profile = PROFILES.get(name)
    if profile is None:
        why = "unknown profile" if _PROFILE.fullmatch(name) else "not a profile name"
        yield Finding("TDS-M007", "error", f"{why}: {name!r}")
        return
    markets = m.data.get("markets")
    needs = profile.requires
    if isinstance(markets, dict) and len(markets) > 1:
        needs += profile.requires_multi_market
    for group in needs:
        if not any(all(_has(m.datasets, need) for need in alt) for alt in group):
            wanted = " or ".join(describe(alt) for alt in group)
            yield Finding("TDS-M008", "error", f"{name} requires dataset {wanted}")


def _has(datasets: Iterable[Mapping[str, Any]], need: Need) -> bool:
    kind, conditions = need
    for ds in datasets:
        own = ds.get("params")
        own = own if isinstance(own, dict) else {}
        if kind in (ds.get("kind"), ds.get("path")) and all(meets(own, *c) for c in conditions):
            return True
    return False


def _rules(ds: Mapping[str, Any]) -> Iterable[object]:
    """The rule names a dataset declares: `availability.rule`, `params.availability_by_column`."""
    availability = ds.get("availability")
    if isinstance(availability, str):  # 4.2: "a 6.2 rule", written bare
        yield availability
    elif isinstance(availability, dict) and "rule" in availability:
        yield availability["rule"]
    params = ds.get("params")
    by_column = params.get("availability_by_column") if isinstance(params, dict) else None
    if isinstance(by_column, dict):
        yield from by_column.values()


def _unsafe(root: Path, rel: str) -> str | None:
    """TDS 4.2 path safety (M012): why `rel` may not be read, or None."""
    if not rel or PurePosixPath(rel).is_absolute() or PureWindowsPath(rel).anchor:
        return "is absolute"
    if ".." in PurePosixPath(rel).parts or "\\" in rel:
        return "leaves the package folder ('..', or a backslash that may hide one)"
    try:
        inside = (root / rel).resolve().is_relative_to(root)
    except (OSError, RuntimeError, ValueError):  # a loop, a NUL byte: not a readable path
        inside = False
    return None if inside else "leads outside the package folder through a symbolic link"


def _walk(root: Path) -> list[str]:
    out = []
    for folder, dirs, names in os.walk(root):
        dirs.sort()
        for n in sorted(names):
            out.append((Path(folder) / n).relative_to(root).as_posix())
    return out


def _major(version: object) -> int | None:
    match = _VERSION.fullmatch(version) if isinstance(version, str) else None
    return int(match[1]) if match else None
