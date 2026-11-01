"""TDS 4.2: `read_manifest` reads `<package>/tds.json`; unreadable is `ManifestError` (TDS-M001)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from nexusbt_tds import read_manifest
from nexusbt_tds.manifest import ManifestError


def write(root: Path, text: str) -> Path:
    (root / "tds.json").write_text(text, encoding="utf-8")
    return root


def test_reads_the_object_unchanged(tmp_path: Path) -> None:
    data = {
        "name": "p",
        "profiles": ["tds:minimal-daily@1.0", 7],
        "datasets": [{"name": "bars_1d"}, "not a dataset"],
        "producer": {"hints": {"TDS-M004": "re-run the export", "TDS-M006": ["not a sentence"]}},
    }
    manifest = read_manifest(write(tmp_path, json.dumps(data)))
    assert (manifest.root, manifest.data) == (tmp_path, data)
    assert manifest.profiles == ["tds:minimal-daily@1.0"]
    assert manifest.datasets == [{"name": "bars_1d"}]
    assert manifest.hints == {"TDS-M004": "re-run the export"}


def test_missing_parts_read_as_empty(tmp_path: Path) -> None:
    manifest = read_manifest(write(tmp_path, '{"producer": "x", "datasets": {}}'))
    assert (manifest.profiles, manifest.datasets, manifest.hints) == ([], [], {})


@pytest.mark.parametrize(
    ("content", "says"),
    [
        (None, "not found"),
        (b"{not json", "unreadable"),
        (b"\xff", "unreadable"),  # not UTF-8
        (b"[]", "not a JSON object"),
    ],
)
def test_unreadable_is_a_manifest_error(content: bytes | None, says: str, tmp_path: Path) -> None:
    if content is not None:
        (tmp_path / "tds.json").write_bytes(content)
    with pytest.raises(ManifestError, match=says):
        read_manifest(tmp_path)
