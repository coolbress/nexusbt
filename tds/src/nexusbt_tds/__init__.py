"""The TDS conformance checker: check, hash, manifest, describe, import_csv; imports no nexusbt."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from .check import CheckResult, ProfileStatus, check
from .hash import semantic_hash, value_hash
from .import_csv import import_csv
from .manifest import Manifest, build_manifest, read_manifest
from .profiles import PROFILES

#: TDS 10.3 schemas by name; filled by T0.13b.
SCHEMAS: Mapping[str, object] = MappingProxyType({})

__all__ = [
    "PROFILES",
    "SCHEMAS",
    "CheckResult",
    "Manifest",
    "ProfileStatus",
    "build_manifest",
    "check",
    "import_csv",
    "read_manifest",
    "semantic_hash",
    "value_hash",
]
