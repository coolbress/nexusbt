"""`check(path, *, level, ...) -> CheckResult`: the levels manifest, schema and full (TDS 8.2).

The `manifest` level reads `tds.json` (M001~M003, M007, M008 so far; #51 adds the rest). It
never reports a profile as `pass`: the rules it cannot see are listed in `unchecked`, and the
profile is `not_checked`.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any, Literal

from .manifest import Manifest, ManifestError, read_manifest
from .profiles import PROFILES, profile_id

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

#: TDS 4.2: the fields marked ○ that are required unconditionally.
REQUIRED: tuple[str, ...] = ("tds_version", "name", "created", "snapshot_id", "producer")
REQUIRED += ("profiles", "id_namespaces", "markets", "datasets", "hashes", "writer")
#: 4.2 lists more fields without saying which are required; until #79 decides, the ones the
#: manifest-level checks need (#51, Decisions 2026-11-02).
DATASET_REQUIRED = ("name", "kind", "schema_version", "path", "files")
FILE_REQUIRED = ("path", "bytes")
_OBJECTS = ("producer", "id_namespaces", "markets", "hashes", "writer")
SUPPORTED_MAJOR = 1  # 10.3
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

    def summary(self) -> dict[str, object]:
        return {
            "errors": len(self.errors),
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
    if level != "manifest":
        raise NotImplementedError(f"check level {level!r}: not built yet (T0.13c, T0.14a)")
    manifest: Manifest | None = None
    try:
        manifest = read_manifest(path)
        found = list(_check_manifest(manifest, datasets))
    except ManifestError as exc:
        found = [Finding("TDS-M001", "error", str(exc))]
    declared = {profile_id(p) for p in manifest.profiles} if manifest else set()
    wanted = [profile_id(p) for p in profiles] if profiles is not None else sorted(declared)
    statuses: dict[str, ProfileStatus] = {}
    package_failed = any(f.severity == "error" for f in found)
    for name in dict.fromkeys(wanted):
        own = list(_check_profile(manifest, name)) if manifest else []
        found += own
        statuses[name] = ProfileStatus(
            declared=name in declared,
            verified_level=level if name in PROFILES else "none",
            result="fail" if package_failed or own else "not_checked",
        )
    hints = manifest.hints if manifest else {}
    found = [f if f.hint or f.code not in hints else replace(f, hint=hints[f.code]) for f in found]
    return CheckResult(
        level=level,
        errors=tuple(f for f in found if f.severity == "error")[:max_errors],
        warnings=tuple(f for f in found if f.severity == "warning"),
        profiles=statuses,
        unchecked=list(UNCHECKED_AT_MANIFEST),
    )


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
    for ds in m.datasets:
        name = ds["name"] if isinstance(ds.get("name"), str) else None
        if only is None or name in only:
            yield from _check_dataset(ds, name)


def _check_dataset(ds: Mapping[str, Any], name: str | None) -> Iterable[Finding]:
    for key in DATASET_REQUIRED:
        if key not in ds:
            yield Finding("TDS-M003", "error", f"dataset field {key!r} is missing", dataset=name)
    files = ds.get("files")
    for entry in files if isinstance(files, list) else []:
        for key in FILE_REQUIRED:
            if not isinstance(entry, dict) or key not in entry:
                msg = f"a files[] entry has no {key!r}"
                yield Finding("TDS-M003", "error", msg, dataset=name)


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
        if not any(_has(m.datasets, kind, params) for kind, params in group):
            wanted = " or ".join(kind for kind, _ in group)
            yield Finding("TDS-M008", "error", f"{name} requires dataset {wanted}")


def _has(
    datasets: Iterable[Mapping[str, Any]], kind: str, params: Sequence[tuple[str, str]]
) -> bool:
    for ds in datasets:
        own = ds.get("params")
        own = own if isinstance(own, dict) else {}
        if kind in (ds.get("kind"), ds.get("path")) and all(own.get(k) == v for k, v in params):
            return True
    return False


def _major(version: object) -> int | None:
    match = _VERSION.fullmatch(version) if isinstance(version, str) else None
    return int(match[1]) if match else None
