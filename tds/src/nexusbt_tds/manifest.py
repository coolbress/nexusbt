"""`read_manifest`: tds.json read (TDS 4); `draft.build_manifest` drafts one (TDS 8.1)."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

MANIFEST = "tds.json"


class ManifestError(Exception):
    """tds.json is missing, unreadable or not a JSON object (TDS-M001)."""


@dataclass(frozen=True, slots=True)
class Manifest:
    """tds.json as read (TDS 4.2): the package folder and the parsed object, unchanged."""

    root: Path
    data: Mapping[str, Any]

    @property
    def profiles(self) -> list[str]:
        value = self.data.get("profiles")
        return [p for p in value if isinstance(p, str)] if isinstance(value, list) else []

    @property
    def datasets(self) -> list[Mapping[str, Any]]:
        value = self.data.get("datasets")
        return [d for d in value if isinstance(d, dict)] if isinstance(value, list) else []

    @property
    def hints(self) -> Mapping[str, str]:
        """`producer.hints` (4.2): a sentence per TDS code or `fallback:<id>`, shown as is."""
        producer = self.data.get("producer")
        hints = producer.get("hints") if isinstance(producer, dict) else None
        if not isinstance(hints, dict):
            return {}
        return {k: v for k, v in hints.items() if isinstance(v, str)}


def read_manifest(path: Path) -> Manifest:
    """Read `<path>/tds.json`; `path` is the package folder."""
    root = Path(path)
    try:
        data = json.loads((root / MANIFEST).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ManifestError(f"{MANIFEST} not found in {root}") from None
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ManifestError(f"{MANIFEST} is unreadable: {exc}") from None
    if not isinstance(data, dict):
        raise ManifestError(f"{MANIFEST} is not a JSON object")
    return Manifest(root, data)
