"""`check(path, *, level, ...) -> CheckResult`: the levels manifest, schema and full (TDS 8.2).

The `manifest` level reads `tds.json`, file sizes and the schema files' `status` (M001~M017);
the `schema` level adds the
Parquet footers and statistics and the `dictionary/` tables, no data rows (S001~S011, T006, part
of D002, and of M008 the columns a profile names); the `full` level adds, so far, S006, S007
and S009 from the rows (`cells`), the key
checks (K001~K004, K010, K011; `keys`), the
reference checks (R001~R009; `refs`), the adjustment and value checks (`adjustments`,
`values`), the interval checks (T003, T004, T012;
`times`), the instant checks (T001, T002, T005, T010, T011; `instants`), the
density checks (D001~D004;
`densities`) and the hashes (H001~H004, TDS 4.5); no profile is verified beyond `schema`.
None reports a profile as `pass`: the rules a level cannot see are listed in `unchecked`, and
the profile is `not_checked`.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import os
import re
from collections.abc import Callable, Collection, Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Literal

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from .manifest import (
    MANIFEST,
    MANIFEST_SCHEMA,
    TDS_DRAFT,
    Manifest,
    ManifestError,
    read_manifest,
    schema_violations,
)
from .profiles import PROFILES, TRADED, Need, describe, meets, profile_id

Level = Literal["manifest", "schema", "full"]
Severity = Literal["error", "warning"]

#: TDS 8.3, the codes the `manifest` level cannot see. M015 it judges from tds.json's kinds and
#: the schema files' `status` (#391).
_ROW_CODES = (
    "S001 S002 S003 S004 S005 S006 S007 S008 S009 S010 S011 K001 K002 K003 K004 K010 K011"
    " R001 R002 R003 R004 R005 R006 R008 R009 T001 T002 T003 T004 T005 T006"
    " T010 T011 T012 D001 D002 D003 D004 A003 A004 A005 A006 A007 A008 A009 A010 A011"
    " V001 V002 V004 V005 V010 V011 V012 V020 V040 H001 H002 H003 H004"
)
UNCHECKED_AT_MANIFEST = tuple(f"TDS-{c}" for c in _ROW_CODES.split())
#: What the `schema` level judges from footers. S006 and S007 see only a column's minimum and
#: maximum; S009 sees ±Inf in the statistics but never NaN, which writers leave out of them, so
#: it stays unchecked. The `full` level judges the three from the rows instead (`cells`).
#: TDS 4.4: the tables that describe the package; their schema files (`dictionary_schemas`) give
#: the value hash its types, and the schema level checks no S code on them, nor hides one.
DICTIONARIES = frozenset({"dictionary/columns", "dictionary/items", "dictionary/codes"})
#: TDS 8.2's range checks from file statistics: T006 here; D002's part stays `unchecked`, since
#: a non-session day between the minimum and the maximum is in the rows (#181).
T006, D002 = "TDS-T006", "TDS-D002"
SCHEMA_CODES = tuple(f"TDS-S{n:03}" for n in (1, 2, 3, 4, 5, 6, 7, 8, 10, 11))
UNCHECKED_AT_SCHEMA = tuple(c for c in UNCHECKED_AT_MANIFEST if c not in (*SCHEMA_CODES, T006))

#: The manifest schema's date pattern (4.2), which a `YYYY-MM-DD` that is no date also matches.
DATE: str = MANIFEST_SCHEMA["$defs"]["date"]["pattern"]
#: TDS 4.2: the fields marked ○ that are required unconditionally.
REQUIRED: tuple[str, ...] = ("tds_version", "name", "created", "snapshot_id", "producer")
REQUIRED += ("profiles", "id_namespaces", "markets", "datasets", "hashes", "writer")
REQUIRED += ("tds_draft",)  # no text is assumed (TDS 10.5; #705 C5)
#: 4.2 lists more fields without saying which are required; until #79 decides, the ones the
#: manifest-level checks need (#51, Decisions 2026-11-02). A file needs `path` and `bytes`.
DATASET_REQUIRED = ("name", "kind", "schema_version", "path", "files")
FILE_REQUIRED = ("path", "bytes")  # TDS 4.2; checked one by one in _check_dataset
MARKET_REQUIRED = ("calendar_id", "currency", "timezone")  # TDS 3.8, 4.2 (#567)
HASH_SPECS = frozenset({"tds-hash-2"})  # 4.5; -1 hashed a partitioned dataset otherwise
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
    #: Why codes in `unchecked` were not judged here, e.g. the dataset with no value hash; the
    #: text output prints them, TDS 8.4's JSON Lines do not carry them.
    notes: tuple[str, ...] = ()

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
    tmp_dir: Path | None = None,
) -> CheckResult:
    manifest: Manifest | None = None
    blind: set[str] = set()  # codes this package's files hide from the level (no statistics)
    notes: list[str] = []  # why, where the checker can say
    try:
        manifest = read_manifest(path)
        found = list(_check_manifest(manifest, datasets))
        if level != "manifest":
            found += _check_schema(manifest, datasets, blind, rows=level == "full")
            found += _check_ranges(manifest, datasets, blind)
        if level == "full":
            from .adjustments import check_actions
            from .cells import check_cells
            from .densities import check_densities
            from .hash import spilled_note
            from .instants import check_instants
            from .keys import check_keys
            from .refs import check_refs
            from .times import check_times
            from .values import check_values

            found += check_cells(manifest, datasets, blind)
            spilled: list[Path] = []
            try:
                found += check_keys(manifest, datasets, blind, tmp_dir, spilled, notes)
            finally:
                notes.extend([spilled_note(spilled, "key check")] if spilled else [])
            found += check_refs(manifest, datasets, blind)
            found += check_actions(manifest, datasets, blind)
            found += check_values(manifest, datasets, blind, notes)
            found += check_times(manifest, datasets, blind)
            found += check_instants(manifest, datasets, blind, notes)
            seen = {f.dataset for f in found if f.code == D002}  # by the statistics
            found += check_densities(manifest, datasets, blind, seen, notes)
            found += _check_hashes(manifest, datasets, blind, notes, tmp_dir)
    except ManifestError as exc:
        found = [Finding("TDS-M001", "error", str(exc))]
    declared = {profile_id(p) for p in manifest.profiles} if manifest else set()
    wanted = [profile_id(p) for p in profiles] if profiles is not None else sorted(declared)
    statuses: dict[str, ProfileStatus] = {}
    package_failed = any(f.severity == "error" for f in found)
    for name in dict.fromkeys(wanted):
        own = list(_check_profile(manifest, name, level, datasets, notes)) if manifest else []
        found += own
        # `full` checks only `FULL_CODES` so far: no profile is verified to it
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
            or (c in UNCHECKED_AT_SCHEMA and (level == "schema" or c not in FULL_CODES))
        ],
        notes=tuple(notes),
    )


#: The declared hashes against the computed ones (TDS 4.5); `full` checks these and the keys.
HASH_CODES = ("TDS-H001", "TDS-H002", "TDS-H003", "TDS-H004")
KEY_CODES = ("TDS-K001", "TDS-K002", "TDS-K003", "TDS-K004", "TDS-K010", "TDS-K011")  # `keys`
#: `refs` checks them; R007 is retired with the user-data kinds (#752).
REF_CODES = tuple(f"TDS-R{n:03}" for n in (1, 2, 3, 4, 5, 6, 8, 9))
#: `adjustments` checks them; A001 and A002 are retired with `cum_factor_*` (TDS 8.3, #705).
ACTION_CODES = tuple(f"TDS-A{n:03}" for n in range(3, 12))
#: `values` checks them; V030, V031, V032, V041 and V050 are retired with their kinds (#752).
VALUE_CODES = tuple(f"TDS-V{n:03}" for n in (1, 2, 4, 5, 10, 11, 12, 20, 40))
TIME_CODES = ("TDS-T003", "TDS-T004", "TDS-T012")  # `times` checks them (#225)
#: `instants` checks them (#225); T007 and T008 are retired with their kinds (#752).
INSTANT_CODES = tuple(f"TDS-T{n:03}" for n in (1, 2, 5, 10, 11))
DENSITY_CODES = ("TDS-D001", D002, "TDS-D003", "TDS-D004")  # `densities` (#225, #425)
CELL_CODES = ("TDS-S006", "TDS-S007", "TDS-S009")  # `cells`, from the rows (#391)
FULL_CODES = (*KEY_CODES, *REF_CODES, *ACTION_CODES, *VALUE_CODES, *TIME_CODES, *INSTANT_CODES,
              *DENSITY_CODES, *HASH_CODES, *CELL_CODES)  # fmt: skip


def _check_hashes(
    m: Manifest, only: Sequence[str] | None, blind: set[str], notes: list[str], tmp: Path | None
) -> list[Finding]:
    """H001 each declared file sha256, H002 each dataset value hash, H003 the package hashes,
    H004 (a warning: the field is advisory, TDS 4.2) each declared file value hash; `notes` gets
    the dataset that stopped the value hash, when one did, and where sorted runs went.
    With `only`, the named datasets' rows alone are read and H003 is not checked (#309)."""
    from .hash import (
        HashError,
        dataset_hashes,
        file_sha256,
        inside,
        package_hashes,
        spill_folder,
        spilled_note,
    )

    out, spilled, hashes = [], list[Path](), dict[str, Any]()
    seen: set[object] = set()  # a path listed twice is M013's; its H001, once
    datasets = [d for d in m.datasets if only is None or d.get("name") in only]
    for ds in datasets:
        for f in (f for f in ds.get("files") or [] if isinstance(f, dict) and "sha256" in f):
            if f.get("path") in seen:
                continue
            seen.add(f.get("path"))
            try:
                actual = file_sha256(inside(m.root, f.get("path")))
            except (HashError, OSError):
                continue  # outside the package or missing: the manifest level's (M004, M012)
            if actual != f["sha256"]:
                message = f"sha256 {actual}, declared {f['sha256']}"
                out.append(Finding("TDS-H001", "error", message, ds.get("name"), f["path"]))
    try:
        if only is None:
            hashes = package_hashes(m.root, tmp_dir=tmp, spilled=spilled)
        else:
            folder = spill_folder(m.root, tmp)
            hashes["partitions"] = {d.get("name"): [] for d in datasets if d.get("partitioning")}
            each = {d.get("name"): dataset_hashes(m.root, d, folder, spilled,
                                                  hashes["partitions"].get(d.get("name")))
                    for d in datasets}  # fmt: skip
            hashes["datasets"] = {name: whole for name, (whole, _) in each.items()}
            hashes["files"] = {path: {"value_sha256": value} for _, files in each.values()
                               for path, value in files.items()}  # fmt: skip
    except Exception as exc:  # no value hash for this package, whatever the cause: not judged
        blind.update(HASH_CODES[1:])
        notes.append(f"{', '.join(HASH_CODES[1:])} not checked: {str(exc) or repr(exc)}")
        return out
    finally:
        notes.extend([spilled_note(spilled)] if spilled else [])
    if only is not None:
        blind.add("TDS-H003")
        notes.append("TDS-H003 not checked: the package hashes need every dataset, not --datasets")
    for ds in datasets:
        declared, actual = ds.get("value_sha256"), hashes["datasets"].get(ds.get("name"))
        if declared is not None and declared != actual:
            which = _partitions_apart(
                ds.get("partitions"), hashes["partitions"].get(ds.get("name"))
            )
            out.append(Finding("TDS-H002", "error", f"value hash {actual}, declared {declared}"
                               f"{which}", dataset=ds.get("name")))  # fmt: skip
        for f in (f for f in ds.get("files") or [] if isinstance(f, dict)):
            actual = hashes["files"].get(f.get("path"), {}).get("value_sha256")
            if None not in (actual, f.get("value_sha256")) and actual != f["value_sha256"]:
                message = f"file value hash {actual}, declared {f['value_sha256']}"
                out.append(Finding("TDS-H004", "warning", message, ds.get("name"), f["path"]))
    declared_hashes = m.data.get("hashes")
    for key in ("physical_sha256", "value_sha256", "semantic_sha256") if only is None else ():
        declared = declared_hashes.get(key) if isinstance(declared_hashes, dict) else None
        if declared is not None and declared != hashes[key]:
            out.append(Finding("TDS-H003", "error", f"{key} {hashes[key]}, declared {declared}"))
    return out


def _by_values(parts: object) -> dict[str, object]:
    """`partitions[]` as `values` (JSON) → `value_sha256`; entries of another shape are M001's."""
    entries = [p for p in parts if isinstance(p, dict)] if isinstance(parts, list) else []
    return {json.dumps(p.get("values")): p.get("value_sha256") for p in entries}


def _partitions_apart(declared: object, actual: list[dict[str, Any]] | None) -> str:
    """H002's words for a partitioned dataset (TDS 4.5 step 6): which partitions differ from,
    or are missing from, the declared `partitions[]`."""
    if actual is None:
        return ""
    said, found = _by_values(declared), _by_values(actual)
    apart = sorted(k for k in said.keys() | found.keys() if said.get(k) != found.get(k))
    return f"; partitions apart: {', '.join(apart)}" if apart else ""


def _check_partitions(ds: Mapping[str, Any], name: str | None) -> Iterable[Finding]:
    """A partitioned dataset's `partitions[]` (TDS 4.2), without reading its rows: present
    (M003), and joined by 4.5 step 6 into its `value_sha256` when that is declared (H005)."""
    from .hash import joined, name_of, partition_values

    partitioning = ds.get("partitioning")
    if not partitioning or not isinstance(partitioning, list):
        return
    if "partitions" not in ds:
        msg = "partitions is missing: a partitioned dataset lists each partition's value hash"
        yield Finding("TDS-M003", "error", f"{msg} (TDS 4.2)", dataset=name)
        return
    listed, declared = _by_values(ds["partitions"]), ds.get("value_sha256")
    if declared is None:  # nothing to join to; H002 compares the rows at `full`
        return
    try:
        digests = {name_of(json.loads(v)): bytes.fromhex(str(h)) for v, h in listed.items()}
        paths = {json.dumps(partition_values(f["path"], partitioning)) for f in ds["files"]
                 if isinstance(f, dict) and f.get("rows") != 0}  # fmt: skip
        same = hashlib.sha256(joined(partitioning, digests)).hexdigest() == declared
    except (ValueError, TypeError, KeyError, LookupError, AttributeError) as exc:  # M001's shape
        yield Finding("TDS-H005", "error", f"partitions not read: {exc!r}", dataset=name)
        return
    if same:
        return
    unlisted, unseen = sorted(paths - listed.keys()), sorted(listed.keys() - paths)
    where = "".join(
        f"; {w}: {', '.join(v)}"
        for w, v in (
            ("in a file's path, not listed", unlisted),
            ("listed, in no file's path", unseen),
        )
        if v
    )
    msg = f"partitions joined do not give value_sha256 {declared} (TDS 4.5 step 6){where}"
    yield Finding("TDS-H005", "error", msg, dataset=name)


def _check_manifest(m: Manifest, only: Sequence[str] | None) -> Iterable[Finding]:
    data = m.data
    for message in schema_violations(data):  # TDS 4.2's fields, shapes and type names (#417)
        yield Finding("TDS-M001", "error", message)
    for key in REQUIRED:
        if key not in data:
            yield Finding("TDS-M003", "error", f"required manifest field {key!r} is missing")
    if "tds_version" in data and _major(data["tds_version"]) != SUPPORTED_MAJOR:
        msg = f"tds_version {data['tds_version']!r} is not supported (MAJOR {SUPPORTED_MAJOR})"
        yield Finding("TDS-M002", "error", msg)
    hashes = data.get("hashes")
    spec = hashes.get("hash_spec") if isinstance(hashes, dict) else None
    if spec is not None and not (isinstance(spec, str) and spec in HASH_SPECS):
        again = " (an earlier draft's; write the hashes again, `tds hash --write`)"
        old = again if spec == "tds-hash-1" else ""
        yield Finding("TDS-M014", "error", f"unknown hash_spec {spec!r}{old}")
    draft = data.get("tds_draft")  # TDS 10.5 (#529); a value that is no date is M001's
    dated = isinstance(draft, str) and re.fullmatch(DATE, draft) is not None
    if dated and draft != TDS_DRAFT:  # a missing one is M003's (#705 C5)
        msg = f"tds_draft {draft}; this checker implements {TDS_DRAFT}"
        yield Finding("TDS-M017", "warning", msg)
    markets, editions = data.get("markets"), data.get("editions")
    for code, entry in sorted(markets.items()) if isinstance(markets, dict) else []:
        for key in MARKET_REQUIRED if isinstance(entry, dict) else ():  # else M001's
            if key not in entry:
                yield Finding("TDS-M003", "error", f"markets.{code}: field {key!r} is missing")
    values = editions.get("values") if isinstance(editions, dict) else None
    declared: dict[str, set[str]] = {
        "market": set(markets) if isinstance(markets, dict) else set(),
        "edition": set(values) if isinstance(values, dict) else set(),
    }

    from .schemas.verify import load_schemas

    root, schemas = m.root.resolve(), load_schemas()
    listed: set[str] = set()
    for ds in m.datasets:
        name = ds["name"] if isinstance(ds.get("name"), str) else None
        if only is not None and name not in only:
            continue
        schema = schemas.get(str(ds.get("kind")))
        if schema is not None and schema.status == "experimental":  # TDS 5.6's note, 8.3
            msg = f"kind {ds['kind']} has an experimental schema (outside the 1.x promise)"
            yield Finding("TDS-M015", "warning", msg, dataset=name)
        coverage = ds.get("coverage")
        by_market = coverage.get("by_market") if isinstance(coverage, dict) else None
        for market, said in sorted(by_market.items()) if isinstance(by_market, dict) else []:
            if market not in declared["market"]:
                msg = f"coverage.by_market names market {market!r}, not declared in tds.json"
                yield Finding("TDS-M010", "error", msg, dataset=name)
            watermark = markets.get(market) if isinstance(markets, dict) else None
            yield from _processed(said, watermark, market, name)
        yield from _check_dataset(root, ds, name, listed, declared)
        yield from _check_partitions(ds, name)
    if only is None:
        for rel in _walk(root):
            if rel not in listed and rel != MANIFEST:
                yield Finding("TDS-M005", "warning", "file is not listed in tds.json", file=rel)


def _processed(
    said: object, market: object, code: str, name: str | None
) -> Iterable[Finding]:  # fmt: skip
    """M016 (TDS 4.3, #192): a dataset's `processed_through_session` in market `code`, when
    present, is neither before its `last` there nor after the market's watermark session (3.8).
    A value that is not a date is M001's (the manifest schema)."""
    said = said if isinstance(said, dict) else {}
    value = said.get("processed_through_session")
    through = _day(value)
    last = _day(said.get("last"))
    watermark = _day(market.get("complete_through_session")) if isinstance(market, dict) else None
    at = f"coverage.by_market.{code}.processed_through_session {through}"
    if isinstance(value, str) and through is None and re.search(DATE, value):  # 2024-02-30
        msg = f"coverage.by_market.{code}.processed_through_session {value!r} is not a date"
        yield Finding("TDS-M001", "error", msg, dataset=name)  # what the pattern lets through
    if through and last and through < last:
        yield Finding("TDS-M016", "error", f"{at}, before its last {last}", dataset=name)
    if through and watermark and through > watermark:
        msg = f"{at}, after the market's complete_through_session {watermark}"
        yield Finding("TDS-M016", "error", msg, dataset=name)


def _day(value: object) -> dt.date | None:
    """A `YYYY-MM-DD` calendar date; None for anything else (`20240102` included)."""
    try:
        return dt.date.fromisoformat(value) if isinstance(value, str) and len(value) == 10 else None
    except ValueError:
        return None


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
    availability = ds.get("availability")  # a rule, `{"rule": …}`, or a 6.2 form (#276)
    if availability is None and ds.get("kind") == "bars":  # no default rule (#705 C5)
        msg = "availability is missing: no default is read (TDS 5.5, 6.2); write its rule"
        yield Finding("TDS-M003", "error", msg, dataset=name)
    known = availability is None or isinstance(availability, str) or _named(ds)
    if not known and not (isinstance(availability, dict) and "rule" in availability):
        msg = f"availability {availability!r} is neither a 6.2 rule nor a 6.2 column form"
        yield Finding("TDS-M014", "error", msg, dataset=name)
    params = ds["params"] if isinstance(ds.get("params"), dict) else {}
    kind = ds.get("kind") if isinstance(ds.get("kind"), str) else None  # `["bars"]`: no crash
    for key, values in CLOSED_PARAMS.get(kind, {}).items():
        if params.get(key) is None:  # absent and null: no value, and none is assumed (#705 C5)
            msg = f"params.{key} is missing: no default is read (TDS 5.5); write one of"
            yield Finding("TDS-M003", "error", f"{msg} {', '.join(values)}", dataset=name)
        elif params[key] not in values:
            msg = f"params.{key} {params[key]!r} is not one of {', '.join(values)}"
            yield Finding("TDS-M014", "error", msg, dataset=name)
    if kind == "bars" and params.get("freq") == "1d" and params.get("density") == "sparse":
        msg = "params.density 'sparse' on daily bars, which are dense (TDS 5.5)"
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
#: Columns every file holds though a cell may be null: S001 without them. TDS 5.27's key column
#: `price_from` (null = 0), which the key and the value hash read (#705 C5, #725 Decisions 176);
#: TDS 5.13's range and policy, null only on an `unobserved` row (V040; #705 Decisions 8).
PRESENT: Mapping[str, tuple[str, ...]] = {
    "market_rules": ("price_from",),
    "delistings": ("ret_lo", "ret_hi", "policy_id"),
}


def _required(null: object, params: Mapping[str, Any]) -> bool:
    """A schema `null` cell as "may not be null"; its conditions read `params` (rule of #56)."""
    if null == "daily yes / intraday no":
        return params.get("freq") != "1d"
    return null is False  # a profile's own (`every_row`) is added by `_check_file`


def _fits(tag: str, value: str) -> bool:
    """TDS 3.6: a partition path value read as its type (S008)."""
    if tag in _BITS:  # ASCII digits, no leading zero: one spelling per value (#121)
        bound = 2 ** (_BITS[tag] - 1)
        return re.fullmatch(r"0|-?[1-9][0-9]*", value) is not None and -bound <= int(value) < bound
    if tag == "date":
        try:
            return dt.date.fromisoformat(value).isoformat() == value
        except ValueError:
            return False
    return value != ""


def _check_schema(
    m: Manifest, only: Sequence[str] | None, blind: set[str], *, rows: bool = False
) -> list[Finding]:
    """S001~S011 from each listed, readable Parquet file's footer (TDS 8.2); with `rows` (the
    `full` level) S006, S007 and S009 are left to the rows (`cells`)."""
    from .schemas.verify import load_schemas

    schemas, root, out = load_schemas(), m.root.resolve(), []
    codes = _dictionary_codes(m, root)
    declared = [PROFILES[i] for i in map(profile_id, m.profiles) if i in PROFILES]
    read: set[str] = set()  # a path listed twice is M013's; its S findings, once
    for ds in m.datasets:
        schema = schemas.get(str(ds.get("kind")))
        version = _VERSION.fullmatch(str(ds.get("schema_version")))
        if only is not None and ds.get("name") not in only:
            continue
        if not version or int(version[1]) == SUPPORTED_MAJOR:  # M009's: not read as 1.0
            out += _same_columns(root, ds, schema)  # S011 needs no schema file: every kind
        if schema is None and ds.get("kind") not in DICTIONARIES:  # `x_custom`: not checked
            blind.update(c for c in SCHEMA_CODES if c != "TDS-S011")
        if schema is None or not version or int(version[1]) != SUPPORTED_MAJOR:  # M009
            continue
        out += _check_declared(ds, schema)
        files = ds.get("files")
        rowed = {c for p in declared for need, cols in p.every_row if _has([ds], need)
                 for c in cols}  # fmt: skip
        for entry in files if isinstance(files, list) else []:
            rel = entry.get("path") if isinstance(entry, dict) else None
            if not isinstance(rel, str) or (norm := str(PurePosixPath(rel))) in read:
                continue
            read.add(norm)
            if not _unsafe(root, rel) and (root / rel).is_file():
                found = [*_check_file(root, rel, ds, schema, blind, codes, entry.get("bytes"),
                                      rowed)]  # fmt: skip
                if ds.get("kind") == "instruments":
                    found += _undeclared_markets(root / rel, m.data)
                out += [replace(f, dataset=ds.get("name"), file=rel) for f in found
                        if not rows or f.code not in CELL_CODES]  # fmt: skip
    return out


def _same_columns(root: Path, ds: Mapping[str, Any], schema: Any) -> list[Finding]:
    """S011 (TDS 8.3, #705 Decisions 40): each file of `ds` holds each column once, and every
    file the same columns, partition columns left out, `x_` columns counted, order not read; a
    column neither the schema file nor `columns[].type` types, the same type in each (S002 types
    the others)."""
    from .hash import resolved_columns

    declared = {str(c.get("name")) for c in ds.get("columns") or [] if isinstance(c, dict)
                and c.get("type")}  # fmt: skip
    typed = {c.name for c in resolved_columns(ds, schema.columns if schema else ()) if c.type}
    out, first, seen = [], None, set()
    for rel, meta in _footers(root, ds):
        if meta is None or rel in seen:
            continue  # S010's; a path listed twice is M013's, read once
        seen.add(rel)
        try:
            arrow = meta.schema.to_arrow_schema()
        except (pa.ArrowException, ValueError):  # a type Arrow does not read: S010's
            continue
        parts = {p.split("=")[0] for p in Path(rel).parts if "=" in p}
        stored = [(f.name, None if f.name in typed | declared else _same(f.type)) for f in arrow]
        stored = [(n, t) for n, t in stored if n not in parts]
        if twice := sorted({n for n, _ in stored if [s for s, _ in stored].count(n) > 1}):
            message = f"column(s) stored twice in one file: {', '.join(twice)}"
            out.append(Finding("TDS-S011", "error", message, dataset=ds.get("name"), file=rel))
        shape = dict(stored)
        if first is None:
            first = (rel, shape)
        elif shape != first[1]:
            names = sorted(set(shape) ^ set(first[1]))
            names += sorted(n for n in set(shape) & set(first[1]) if shape[n] != first[1][n])
            message = f"columns unlike {first[0]}'s: {', '.join(names)}"
            out.append(Finding("TDS-S011", "error", message, dataset=ds.get("name"), file=rel))
    return out


_UTC = frozenset({"UTC", "Etc/UTC", "+00:00", "Z"})


def _same(t: pa.DataType) -> str:
    """S011's type of an untyped column: dictionary encoding, `large_` strings and binaries and
    the spellings of UTC are no difference (TDS 3.6, 3.7)."""
    if pa.types.is_dictionary(t):
        t = t.value_type
    if pa.types.is_large_string(t) or pa.types.is_large_binary(t):
        t = pa.string() if pa.types.is_large_string(t) else pa.binary()
    if pa.types.is_timestamp(t) and t.tz in _UTC:
        t = pa.timestamp(t.unit, "UTC")
    return str(t)


def _undeclared_markets(path: Path, data: Mapping[str, Any]) -> list[Finding]:
    """M010 (TDS 3.8, 8.2, #567): each `instruments.market` not declared in `markets`, once,
    with its first instrument. A missing column is S001's, an unreadable file S010's."""
    markets = data.get("markets")
    declared = set(markets) if isinstance(markets, dict) else set()
    try:
        rows = pq.ParquetFile(path).read(columns=["instrument_id", "market"]).to_pylist()
    except (OSError, KeyError, pa.ArrowException):
        return []
    first: dict[str, Any] = {}
    for row in rows:  # a column the file lacks is not in the row
        if (market := row.get("market")) is not None and market not in declared:
            first.setdefault(market, row.get("instrument_id"))
    return [Finding("TDS-M010", "error",
                    f"instrument {i!r} names market {m!r}, not declared in tds.json")
            for m, i in sorted(first.items())]  # fmt: skip


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


def _check_declared(ds: Mapping[str, Any], schema: Any) -> list[Finding]:
    """S002 of each tds.json `columns[].type` that differs from the type the schema file states.

    The schema file decides a typed column's type and timestamp unit (#373); a declaration only
    names the one unit of a `ts_us/ns` column. One finding per column, for the dataset."""
    declared, out = _by_name(ds.get("columns")), []
    for column in schema.columns:
        said, tag = declared.get(column.name), column.type
        narrows = tag == "ts_us/ns" and said in ("ts_us", "ts_ns")
        if said and tag is not None and said != tag and not narrows:  # "": none, as the hash reads
            message = f"tds.json declares {column.name} as {said}, schema type {tag}"
            out.append(Finding("TDS-S002", "error", message, dataset=ds.get("name")))
    return out


def _check_file(
    root: Path,
    rel: str,
    ds: Mapping[str, Any],
    schema: Any,
    blind: set[str],
    codes: set[tuple[str, str]],
    size: object,
    rowed: Collection[str] = (),
) -> Iterable[Finding]:
    """S001~S010 of one file; `size`: its tds.json `bytes`; `rowed`: the columns a declared
    profile requires on every row of its dataset (chapter 7), not null whatever 5.5 says."""
    try:
        meta = pq.ParquetFile(root / rel).metadata
        arrow = meta.schema.to_arrow_schema()
    except (OSError, pa.ArrowException):  # 3.7 requires Parquet: no key-value metadata (#121)
        said = (root / rel).stat().st_size == size  # a changed size is M006's: one cause, one code
        if said:
            yield Finding("TDS-S010", "error", "not a Parquet file, so no tds.dataset metadata")
        blind.update(c for c in SCHEMA_CODES if c != "TDS-S010" or not said)  # the rest: unread
        return
    params: dict[str, Any] = ds["params"] if isinstance(ds.get("params"), dict) else {}
    declared, typed = _by_name(ds.get("columns")), _by_name(ds.get("partitioning"))
    kv = {k: v.decode(errors="replace") for k, v in (meta.metadata or {}).items()}
    version = kv.get(b"tds.schema_version") == ds.get("schema_version")
    if kv.get(b"tds.dataset") != ds.get("name") or not version:  # 3.7: the name, not the kind
        yield Finding("TDS-S010", "error", "tds.dataset/tds.schema_version missing or different")
    parts = dict(p.split("=", 1) for p in PurePosixPath(rel).parent.parts if "=" in p)  # 3.6
    for key, value in parts.items():
        tag = typed.get(key) or _PARTITION_TYPE.get(key, "code")
        if not _fits(str(tag), value):
            yield Finding("TDS-S008", "error", f"partition {key}={value!r} is not a {tag}")
        if key in arrow.names:
            yield Finding("TDS-S008", "error", f"partition column {key} is also inside the file")
    from .hash import resolved_columns

    columns = resolved_columns(ds, schema.columns)  # the value hash's set too (#144)
    known, absent = {c.name for c in columns}, set[str]()
    for column in columns:
        required = _required(column.null, params) or column.name in rowed
        if column.name not in arrow.names:
            present = column.name in PRESENT.get(str(ds.get("kind")), ())  # its cells may be null
            if column.name not in parts and (required or present):
                absent.add(column.name)
                yield Finding("TDS-S001", "error", f"required column {column.name} is missing")
            continue
        yield from _check_column(meta, arrow, column, required, declared.get(column.name), blind)
        yield from _check_values(meta, arrow, column, codes, blind)
    from .schemas.verify import Column

    for name in [n for n in arrow.names if n.startswith("x_") and n not in parts]:  # #403
        if isinstance(tag := declared.get(name), str) and tag:
            yield from _check_column(meta, arrow, Column(name, None, None), False, tag, blind)
    newer = int(str(ds["schema_version"]).split(".")[1]) > KNOWN_MINOR  # M011: ignore unknown
    for name in [] if newer else arrow.names:
        if name not in known and name not in parts and not name.startswith("x_"):
            yield Finding("TDS-S005", "warning", f"unknown column {name} (not `x_`)")


def _check_column(
    meta: Any, arrow: pa.Schema, column: Any, required: bool, unit: Any, blind: set[str]
) -> Iterable[Finding]:
    """S002, S003, S004, S009 of one column; `unit`: its tds.json `columns[].type`, the type
    S002 and S004 check a column the schema file leaves untyped against (#403)."""
    name, kind = column.name, arrow.types[arrow.names.index(column.name)]
    tag = column.type or (unit if isinstance(unit, str) else None)
    paths = [meta.schema.column(i).path for i in range(meta.num_columns)]
    index = paths.index(name) if name in paths else None  # None: a nested column
    if index is not None and meta.schema.column(index).physical_type == "INT96":
        yield Finding("TDS-S004", "error", f"{name} is written as INT96 (TDS 3.7)")
        return
    if tag in _IS and not _IS[tag](kind):
        yield Finding("TDS-S002", "error", f"{name} is {kind}, TDS type {tag}")
        return
    if tag in _UNITS:  # the schema's unit; tds.json names one of a `ts_us/ns` column's (#57, #373)
        units = _UNITS.get(str(unit), _UNITS[tag]) if tag == "ts_us/ns" else _UNITS[tag]
        if kind.tz != "UTC" or kind.unit not in units:
            yield Finding("TDS-S004", "error", f"{name} is {kind}, wants UTC {'/'.join(units)}")
    if index is None:  # its statistics are its leaves': a list's own null count is in none
        if required:
            blind.add("TDS-S003")
        return
    stats = [meta.row_group(g).column(index).statistics for g in range(meta.num_row_groups)]
    if required and any(s is None or not s.has_null_count for s in stats):
        blind.add("TDS-S003")
    elif required and (nulls := sum(s.null_count for s in stats)):
        yield Finding("TDS-S003", "error", f"{name} may not be null", count=nulls)
    # an f64's only: without pandas pyarrow gives no nanosecond instant's as a Python value (#382)
    seen = [s for s in stats if column.type == "f64" and s is not None and s.has_min_max]
    if any(math.isinf(v) for s in seen for v in (s.min, s.max)):
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


Stat = tuple[Any, Any, int]  # a row group's minimum, maximum (None: all null) and null count
_EPOCH, _MICRO = dt.datetime(1970, 1, 1, tzinfo=dt.UTC), dt.timedelta(microseconds=1)
#: The kinds with no availability instant to hold against a watermark (5.1, 5.3, 5.4, 4.4;
#: `instrument_xref` has no known time in v1, 8.2, #332); any other kind without a rule
#: leaves T006 unchecked, never passed (#181 review).
TIMELESS = frozenset({"instruments", "instrument_xref", "calendar_sessions", *DICTIONARIES})


def _check_ranges(m: Manifest, only: Sequence[str] | None, blind: set[str]) -> list[Finding]:
    """T006 and D002's part from file statistics (TDS 8.2; rules: #181 Decisions)."""
    from .keys import Instant

    root, out, seen = m.root.resolve(), [], set()
    markets = m.data["markets"] if isinstance(m.data.get("markets"), dict) else {}
    calendars = _reference(m, root, "calendar_sessions", ("calendar_id", "session_date"))
    listings = _reference(m, root, "instruments", ("instrument_id", "listed_on", "delisted_on"))
    for ds in (d for d in m.datasets if only is None or d.get("name") in only):
        kind, named = ds.get("kind"), _named(ds)
        # (rule, the column rule `column` reads): a 6.2 form, each availability column it names;
        # `effect` is when a corporate action takes effect, not when it became available (#276)
        instants = [n for k, n in ds["availability"].items() if k != "effect"] if named else []
        rules = [(r, "ts_available") for r in _rules(ds)] + [("column", n) for n in instants]
        if not rules:  # bars default to `ts_end` (5.5); a kind not timeless: rule unknown
            rules = [("ts_end", "")] if kind == "bars" else [] if kind in TIMELESS else [(None, "")]
        params = ds["params"] if isinstance(ds.get("params"), dict) else {}
        daily = kind == "bars" and params.get("freq") == "1d"
        for rel, meta in _footers(root, ds):
            if rel in seen:
                continue
            seen.add(rel)
            parts = dict(p.split("=", 1) for p in PurePosixPath(rel).parent.parts if "=" in p)
            market = markets.get(parts.get("market"))
            market = market if isinstance(market, dict) else {}
            through = _instant(market.get("complete_through"))
            have = [meta.schema.column(i).path for i in range(meta.num_columns)] if meta else []
            for name in named if meta else []:  # T002's part: the footer has the column (#276)
                if name not in have and name not in parts:
                    msg = f"availability names column {name}, which the file does not have"
                    out.append(Finding("TDS-T002", "error", msg, ds.get("name"), rel))
            for rule, column in rules:
                last = _available(meta, rule, column) if meta is not None else None
                if through is None or last is None:
                    blind.add(T006)  # no watermark, no statistics, or a rule they cannot apply
                elif last > (through - _EPOCH) // _MICRO * 1000:  # both in nanoseconds
                    msg = f"available until {Instant(last).iso()}, after the market's"
                    msg += f" complete_through {market['complete_through']}"
                    out.append(Finding(T006, "error", msg, ds.get("name"), rel))
            if daily and meta:
                found = _outside(meta, market.get("calendar_id"), calendars, listings)
                out += [Finding(D002, "error", msg, ds.get("name"), rel) for msg in found]
    return out


def _outside(meta: Any, calendar: object, calendars: list[Any], listings: list[Any]) -> list[str]:
    """D002: a daily bars file's session dates outside its calendar's first and last session,
    or, holding one instrument, outside its `listed_on`..`delisted_on` (TDS 5.1, 5.4)."""
    days, ids = _span(meta, "session_date", dt.date), _span(meta, "instrument_id", str)
    out: list[str] = []
    if not days:
        return out
    shown = f"session_date {days[0]}..{days[1]}"
    sessions = _lookup(calendars, "calendar_id", calendar, "session_date")
    if sessions and sessions[0] is not None and (days[0] < sessions[0] or days[1] > sessions[1]):
        out.append(f"{shown} outside calendar {calendar}'s {sessions[0]}..{sessions[1]}")
    one = ids[0] if ids and ids[0] == ids[1] else None
    listed = _lookup(listings, "instrument_id", one, "listed_on")
    if listed and listed[0] is not None and days[0] < listed[0]:
        out.append(f"{shown} begins before {one}'s listed_on {listed[0]}")
    delisted = _lookup(listings, "instrument_id", one, "delisted_on")
    if delisted and delisted[2] == 0 and days[1] > delisted[1]:  # null: still listed
        out.append(f"{shown} ends after {one}'s delisted_on {delisted[1]}")
    return out


def _footers(root: Path, ds: Mapping[str, Any]) -> Iterable[tuple[str, Any]]:
    """Each listed, readable file of `ds` with its Parquet footer, None when it has none."""
    files = ds.get("files")
    for entry in files if isinstance(files, list) else []:
        rel = entry.get("path") if isinstance(entry, dict) else None
        if isinstance(rel, str) and not _unsafe(root, rel) and (root / rel).is_file():
            try:
                yield str(PurePosixPath(rel)), pq.ParquetFile(root / rel).metadata
            except (OSError, pa.ArrowException):
                yield str(PurePosixPath(rel)), None


def _stat(meta: Any, g: int, name: str, want: type) -> Stat | None:
    """Row group `g`'s statistics of the top-level column `name` holding `want` values, or None
    when the footer does not say. A timestamp counts only with a time zone (S004) and where
    `want` is a datetime, and comes as `keys.Instant`s from the stored integers: pyarrow makes
    a nanosecond one a Python value only with pandas (#382). Of the other time types only a
    `date32` where `want` is a date is read; any other is S002's and not made a value (#389)."""
    from .keys import _NS, Instant

    paths = [meta.schema.column(i).path for i in range(meta.num_columns)]
    s = meta.row_group(g).column(paths.index(name)).statistics if name in paths else None
    if s is None or not s.has_null_count or (s.num_values and not s.has_min_max):
        return None
    if not s.has_min_max:
        return None, None, s.null_count
    try:
        arrow = meta.schema.to_arrow_schema()
    except pa.ArrowException:  # a type Arrow does not read: S010's
        return None
    kind = arrow.types[arrow.names.index(name)]  # the first of a name stored twice, as `paths`
    if pa.types.is_timestamp(kind):
        if want is not dt.datetime or not kind.tz or s.physical_type != "INT64":  # INT96: S004's
            return None
        first, last = (Instant(v * _NS[kind.unit]) for v in (s.min_raw, s.max_raw))
        return first, last, s.null_count
    if pa.types.is_temporal(kind) and not (want is dt.date and pa.types.is_date32(kind)):
        return None  # S002's: pyarrow makes a `time64[ns]` a Python value only with pandas
    low, high = (_text(v) if want is str else v for v in (s.min, s.max))
    fits = type(low) is want and type(high) is want  # a datetime is a date, not a `date`
    return (low, high, s.null_count) if fits else None


def _span(meta: Any, name: str, want: type) -> tuple[Any, ...] | None:
    """A file's (minimum, maximum) of `name`; `()` with no rows; None when unknown or null."""
    stats = [_stat(meta, g, name, want) for g in range(meta.num_row_groups)]
    if any(s is None or s[2] for s in stats):
        return None
    values = [v for s in stats if s for v in s[:2]]
    return (min(values), max(values)) if values else ()


def _reference(m: Manifest, root: Path, kind: str, names: Sequence[str]) -> list[Any]:
    """Each row group of the `kind` files as {column: `_stat`}; an unreadable file, all None."""
    want = {"calendar_id": str, "instrument_id": str}
    out = []
    for ds in (d for d in m.datasets if d.get("kind") == kind):
        for _, meta in _footers(root, ds):
            groups = range(meta.num_row_groups) if meta else [None]
            out += [
                {n: _stat(meta, g, n, want.get(n, dt.date)) if g is not None else None
                 for n in names} for g in groups
            ]  # fmt: skip
    return out


def _lookup(groups: list[Any], key: str, value: object, column: str) -> Stat | None:
    """`column`'s (minimum, maximum, nulls) over the row groups that may hold `key` = `value`;
    None when one may hold another key too, or when none holds it (R001, R002: the rows')."""
    hits = []
    for g in groups if isinstance(value, str) else []:
        k = g[key]
        if k is None or (k[0] is not None and k[0] <= value <= k[1] and k[0] != k[1]):
            return None
        if k[0] == value:
            if g[column] is None:
                return None
            hits.append(g[column])
    lows, highs = [h[0] for h in hits if h[0] is not None], [h[1] for h in hits if h[1] is not None]
    nulls = sum(h[2] for h in hits)
    return (min(lows), max(highs), nulls) if lows else (None, None, nulls) if hits else None


_DELAY = re.compile(r"P(?:(\d+)W)?(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?)?")


def _delay(text: str | None) -> int | None:
    """An ISO 8601 delay without years or months, in nanoseconds; None for one with them."""
    delay = _DELAY.fullmatch(text or "P")
    if delay is None:
        return None
    w, d, h, minutes, s = (x or "0" for x in delay.groups())
    whole = (((int(w) * 7 + int(d)) * 24 + int(h)) * 60 + int(minutes)) * 60
    return whole * 10**9 + round(float(s) * 10**9)


def _available(meta: Any, rule: object, column: str) -> float | None:
    """The latest availability instant under 6.2 `rule` from the statistics, in nanoseconds
    since the epoch, rule `column` reading `column`; None when they cannot say: a rule on the
    calendar or with a fallback, a null in its column (a daily bar's null `ts_end` is its
    session close; a null in a named column has its dataset's fallback, 5.2, 5.11, 5.13), a
    delay in years or months."""
    match = re.fullmatch(rf"(column|ts_end|ts_recv)(?:\+({_DUR}))?", str(rule))
    delay = _delay(match[2]) if match and RULE.fullmatch(str(rule)) else None
    if match is None or delay is None:
        return None
    span = _span(meta, column if match[1] == "column" else match[1], dt.datetime)
    if span is None:
        return None
    return span[1] + delay if span else -math.inf  # no rows: nothing after any watermark


def _instant(value: object) -> dt.datetime | None:
    """TDS 3.8 `complete_through`, an instant with a zone; None when absent or unreadable."""
    try:
        when = dt.datetime.fromisoformat(value) if isinstance(value, str) else None
    except ValueError:
        return None
    return when if when and when.tzinfo else None


def _check_profile(
    m: Manifest, name: str, level: Level, only: Sequence[str] | None, notes: list[str]
) -> Iterable[Finding]:
    """M007, and M008: the profile's datasets and, above `manifest`, the columns chapter 7
    names in each dataset that meets it (of `only`, when datasets are named)."""
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
    root, traded = m.root.resolve(), None  # the `TRADED` instruments, read when a row needs them
    rows = [(*c, "") for c in profile.columns]
    rows += [(*c, " (equity or etf rows)") for c in profile.traded]
    for need, columns, why in rows if level != "manifest" else ():
        for ds in m.datasets:
            if (only is not None and ds.get("name") not in only) or not _has([ds], need):
                continue
            if why:
                traded = _traded(m, root) if traded is None else traded
                if not _names(root, ds, traded):
                    continue
            for column in columns:
                lack = _lacks(root, ds, column)
                if lack is None:
                    said = f"column {column} of {ds.get('name')} ({name}): no statistics"
                    notes.append(f"TDS-M008 not checked for {said}")
                elif lack:
                    message = f"{name} requires column {column} in {need[0]}{why}: {lack}"
                    yield Finding("TDS-M008", "error", message, dataset=ds.get("name"))


def _column(root: Path, ds: Mapping[str, Any], name: str) -> Iterable[pa.ChunkedArray]:
    """Column `name` of each listed, readable file of `ds` that holds it; no other column."""
    for rel, meta in _footers(root, ds):
        if meta is not None and name in meta.schema.names:
            try:
                yield pq.ParquetFile(root / rel).read(columns=[name])[name]
            except (OSError, KeyError, pa.ArrowException):  # a name twice: S011's, unread here
                continue


def _traded(m: Manifest, root: Path) -> set[Any]:
    """The instruments whose `asset_class` is in `TRADED` (chapter 7, #705 Decisions 37)."""
    out: set[Any] = set()
    for ds in (d for d in m.datasets if d.get("kind") == "instruments"):
        for rel, meta in _footers(root, ds):
            if meta is not None and {"instrument_id", "asset_class"} <= set(meta.schema.names):
                try:
                    t = pq.ParquetFile(root / rel).read(columns=["instrument_id", "asset_class"])
                except (OSError, KeyError, pa.ArrowException):
                    continue
                pairs = zip(*t.to_pydict().values(), strict=True)
                out.update(i for i, a in pairs if a in TRADED and isinstance(i, str))  # else S's
    return out


def _names(root: Path, ds: Mapping[str, Any], ids: set[Any]) -> bool:
    """Whether `ds`'s `instrument_id` column names one of `ids`, reading that column only."""
    want = pa.array(sorted(ids), pa.string())
    for ids_of_file in _column(root, ds, "instrument_id") if ids else ():
        try:
            if pc.any(pc.is_in(ids_of_file.cast(pa.string()), value_set=want)).as_py():
                return True
        except pa.ArrowException:  # an id column of another type: S002's, not this check's
            continue
    return False


def _lacks(root: Path, ds: Mapping[str, Any], column: str) -> str | None:
    """Why no listed file of `ds` holds a value of `column`: "missing" from every footer, or
    "null in every row"; "" when one holds a value, when the dataset has no row (an empty table
    lacks nothing) or no readable footer, or when the column is a partition's; None when a
    footer has the column without its null count."""
    rows = 0  # of every listed file, with the column or without
    held = unknown = False
    for rel, meta in _footers(root, ds):
        if meta is None or any(p.startswith(f"{column}=") for p in PurePosixPath(rel).parts):
            return ""
        rows += meta.num_rows
        paths = [meta.schema.column(i).path for i in range(meta.num_columns)]
        if column not in {p.split(".")[0] for p in paths}:
            continue
        held = True
        for g in range(meta.num_row_groups if column in paths else 0):
            s = meta.row_group(g).column(paths.index(column)).statistics
            if not meta.row_group(g).num_rows:
                continue  # a row group without rows has no null count and no value
            if s is None or not s.has_null_count:
                unknown = True
            elif s.null_count < meta.row_group(g).num_rows:
                return ""
        # a nested column: its leaves' counts only
        unknown = unknown or (column not in paths and meta.num_rows > 0)
    if unknown:
        return None
    if not rows:
        return ""
    return "null in every row" if held else "missing"


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


#: TDS 4.2, 6.2: the availability objects that name columns instead of a rule, by their keys:
#: one column, `corporate_actions`' effect and terms, `delistings`' exit and value (#276).
FORMS = ({"column"}, {"effect", "terms"}, {"exit", "value"})


def _named(ds: Mapping[str, Any]) -> list[str]:
    """The columns a dataset's availability names in one of the FORMS; [] for any other."""
    availability = ds.get("availability")
    if not isinstance(availability, dict) or set(availability) not in FORMS:
        return []
    names = list(availability.values())
    return names if all(isinstance(n, str) and re.fullmatch(_COL, n) for n in names) else []


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
