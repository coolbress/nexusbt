"""`read_manifest`: tds.json read (TDS 4); `draft.build_manifest` drafts one (TDS 8.1)."""

from __future__ import annotations

import json
import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .schemas.verify import SCHEMA_DIR

MANIFEST = "tds.json"
#: TDS 4.2's fields as a JSON Schema (8.3's M001, #417), read by `schema_violations`.
MANIFEST_SCHEMA: Mapping[str, Any] = json.loads(
    (SCHEMA_DIR / "manifest" / "1.0.json").read_text(encoding="utf-8")
)
_JSON = {"object": dict, "array": list, "string": str}


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


def schema_violations(value: Any, schema: Mapping[str, Any] = MANIFEST_SCHEMA, at: str = "$"
                      ) -> Iterator[str]:  # fmt: skip
    """`<JSON path>: <message>` for each place `value` breaks the manifest schema. Only the
    keywords that file uses; `required` is left out, a missing field being M003's (8.3)."""
    if "$ref" in schema:
        schema = MANIFEST_SCHEMA["$defs"][schema["$ref"].rpartition("/")[2]]
    if "type" in schema and not isinstance(value, _JSON[schema["type"]]):
        yield f"{at}: {json.dumps(value)} is not a JSON {schema['type']}"
        return
    if "enum" in schema and value not in schema["enum"]:
        yield f"{at}: {json.dumps(value)} is not one of {', '.join(schema['enum'])}"
    if "pattern" in schema and not re.search(schema["pattern"], value):
        yield f"{at}: {json.dumps(value)} does not match {schema['pattern']}"
    if isinstance(value, dict):
        named = schema.get("properties", {})
        for key, item in value.items():
            if (sub := named.get(key, schema.get("additionalProperties"))) is not None:
                yield from schema_violations(item, sub, f"{at}.{key}")
    if isinstance(value, list) and "items" in schema:
        seen: set[object] = set()
        for n, item in enumerate(value):
            yield from schema_violations(item, schema["items"], f"{at}[{n}]")
            key = schema.get("x-unique")
            name = item.get(key) if key and isinstance(item, dict) else None
            if isinstance(name, str) and name in seen:
                yield f"{at}[{n}].{key}: {name!r} is listed twice"
            if isinstance(name, str):
                seen.add(name)
