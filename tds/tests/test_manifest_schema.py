"""TDS 4.2, 8.3: tds.json against `tds/schemas/manifest/1.0.json`; a violation is M001 (#417)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from nexusbt_tds import check
from nexusbt_tds.check import _IS, DATASET_REQUIRED, FILE_REQUIRED, MARKET_REQUIRED, REQUIRED
from nexusbt_tds.manifest import MANIFEST_SCHEMA

from .conformance_build import build

SCHEMAS = Path(__file__).resolve().parents[1] / "schemas"
NAMES: list[str] = MANIFEST_SCHEMA["$defs"]["type"]["enum"]
FUNDING = {"name": "funding_rates", "kind": "funding_rates", "schema_version": "1.0",
           "path": "funding_rates", "files": []}  # fmt: skip


def findings(tmp_path: Path, change: Any) -> list[tuple[str, str]]:
    manifest, files = build.base()
    change(manifest)
    result = check(build.write(tmp_path, manifest, files), level="manifest")
    return [(f.code, f.message) for f in (*result.errors, *result.warnings) if f.code != "TDS-M015"]


def columns(*cols: dict[str, Any], dataset: dict[str, Any] | None = None) -> Any:
    def change(m: dict[str, Any]) -> None:
        if dataset is not None:
            m["datasets"].append(dataset)
        # the bars, not the base's last dataset, its calendar since #705
        (m["datasets"][-1] if dataset is not None else build.bars(m))["columns"] = list(cols)

    return change


@pytest.mark.parametrize(
    ("change", "path"),
    [
        (columns({"name": "close", "type": "bogus"}), "$.datasets[1].columns[0].type"),  # typed
        (columns({"name": "x_note", "type": "list<i64>"}), "$.datasets[1].columns[0].type"),
        (columns({"name": "source", "type": "bogus"}, dataset=FUNDING),  # untyped in its file
         "$.datasets[3].columns[0].type"),  # after the base's three (#705)
        (columns({"name": "ts_end", "type": "ts_us/ns"}), "$.datasets[1].columns[0].type"),  # 4.5
        (lambda m: build.bars(m).update(partitioning=[{"name": "year", "type": "int"}]),
         "$.datasets[1].partitioning[0].type"),
    ],
)  # fmt: skip
def test_a_type_that_is_not_a_tds_type_name_is_M001(change: Any, path: str, tmp_path: Path) -> None:
    [(code, message)] = findings(tmp_path, change)
    assert code == "TDS-M001"
    assert message.startswith(f"{path}: ")


def test_every_type_name_is_accepted(tmp_path: Path) -> None:
    declared = [{"name": f"x_{n}", "type": t} for n, t in enumerate(NAMES)]
    assert findings(tmp_path, columns(*declared)) == []


def test_every_type_the_schema_files_use_is_a_name_or_ts_us_ns() -> None:
    used = {c["type"] for p in SCHEMAS.rglob("1.0.json") if p.parent.name != "manifest"
            for c in json.loads(p.read_text(encoding="utf-8"))["columns"]}  # fmt: skip
    assert {"ts_us/ns", "list<code>"} <= used
    assert used - {None, "ts_us/ns"} <= set(NAMES)
    assert set(NAMES) == _IS.keys() - {"ts_us/ns"}  # what S002 knows


def test_tds_draft_is_a_date(tmp_path: Path) -> None:
    """TDS 4.2 (#529): the conformance packages name the text; a value that is no date is M001."""
    assert build.base()[0]["tds_draft"] == "2026-11-19"
    assert findings(tmp_path, lambda m: m.update(tds_draft="v1.4")) == [
        ("TDS-M001", '$.tds_draft: "v1.4" does not match ^[0-9]{4}-[0-9]{2}-[0-9]{2}$')
    ]


def test_a_column_name_twice_in_a_dataset_is_M001(tmp_path: Path) -> None:
    twice = columns({"name": "close", "type": "f64"}, {"name": "close"})
    assert findings(tmp_path, twice) == [
        ("TDS-M001", "$.datasets[1].columns[1].name: 'close' is listed twice")
    ]


@pytest.mark.parametrize(
    "change",
    [lambda m: m.update(producer="x"), lambda m: m["markets"].update(US="x"),
     lambda m: m.update(datasets=[*m["datasets"], "x"]),
     columns({"name": ["close"]}, {"name": "close"})],  # a list name: no crash
)  # fmt: skip
def test_a_field_of_another_shape_is_M001(change: Any, tmp_path: Path) -> None:
    assert [code for code, _ in findings(tmp_path, change)] == ["TDS-M001"]


def test_the_schema_requires_what_M003_checks() -> None:
    dataset = MANIFEST_SCHEMA["properties"]["datasets"]["items"]
    market = MANIFEST_SCHEMA["properties"]["markets"]["additionalProperties"]
    assert MANIFEST_SCHEMA["required"] == list(REQUIRED)
    assert dataset["required"] == list(DATASET_REQUIRED)
    assert dataset["properties"]["files"]["items"]["required"] == list(FILE_REQUIRED)
    assert market["required"] == list(MARKET_REQUIRED)


@pytest.mark.parametrize("field", ["calendar_id", "currency", "timezone"])
def test_a_market_entry_without_a_field_is_M003_naming_both(field: str, tmp_path: Path) -> None:
    """TDS 3.8, 4.2 (#567): each `markets` entry holds the three; one missing is M003."""
    said = findings(tmp_path, lambda m: m["markets"]["US"].pop(field))
    assert said == [("TDS-M003", f"markets.US: field {field!r} is missing")]


@pytest.mark.parametrize("value", ["", None, 1])
def test_a_market_field_that_is_no_non_empty_string_is_M001(value: Any, tmp_path: Path) -> None:
    said = findings(tmp_path, lambda m: m["markets"]["US"].update(timezone=value))
    assert [code for code, _ in said] == ["TDS-M001"]
    assert "$.markets.US.timezone" in said[0][1]
