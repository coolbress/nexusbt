"""TDS 5.28 (#752's V1): the value tables are judged by the checks every kind takes.

The stops of engine specification 5.3.5 that these checks do not cover (an item name outside
5.28's rule, an item in two kinds) come with their own checks in a later pull request.
"""

from __future__ import annotations

import datetime as dt
import tempfile
from pathlib import Path
from typing import Any

import pyarrow as pa
import pytest

from nexusbt_tds import check
from nexusbt_tds.hash import package_hashes

from .conformance_build import build

D, SATURDAY = dt.date(2024, 1, 2), dt.date(2024, 1, 6)
PARTITIONING = [{"name": "market", "type": "code"}, {"name": "item", "type": "code"}]


def _values(ids: list[Any], dates: list[Any], values: list[Any]) -> dict[str, pa.Array]:
    return {"instrument_id": pa.array(ids, pa.string()), "date": pa.array(dates, pa.date32()),
            "value": pa.array(values, pa.float64())}  # fmt: skip


#: One row of each kind, for US:AAA, the base package's instrument.
TABLES = {
    "values": _values(["US:AAA"], [D], [12.5]),
    "market_values": {"date": pa.array([D]), "value": pa.array([3.5])},
    "symbol_values": {"instrument_id": pa.array(["US:AAA"]), "value": pa.array([1.0])},
}


def package(root: Path, items: dict[str, dict[str, dict[str, pa.Array]]]) -> Path:
    """The base package plus, per item, its tables at `<kind>/market=US/item=<item>/`, with
    `partitions[]` and `value_sha256` from the checker's own hashes (TDS 4.2)."""
    manifest, files = build.base()
    entries: dict[str, dict[str, Any]] = {}
    for item, tables in items.items():
        for kind, columns in tables.items():
            rel, table = f"{kind}/market=US/item={item}/part-00000.parquet", pa.table(columns)
            files[rel] = build.parquet(table, kind)
            entry = entries.setdefault(kind, {
                "name": kind, "kind": kind, "schema_version": "1.0", "path": kind,
                "partitioning": PARTITIONING, "files": []})  # fmt: skip
            entry["files"].append({"path": rel, "rows": table.num_rows, "bytes": len(files[rel])})
    manifest["datasets"] += entries.values()
    with tempfile.TemporaryDirectory() as tmp:
        hashes = package_hashes(build.write(Path(tmp), manifest, files))
    for entry in entries.values():
        entry["partitions"] = hashes["partitions"][entry["name"]]
        entry["value_sha256"] = hashes["datasets"][entry["name"]]
    return Path(build.write(root, manifest, files))


def found(path: Path) -> list[tuple[str, str | None]]:
    result = check(path, level="full")
    return [(f.code, f.dataset) for f in (*result.errors, *result.warnings)]


def test_three_tables_pass_every_level(tmp_path: Path) -> None:
    """5.28: two items of each kind pass; the hashes cover them; the checker takes no instant
    from them, so T006 stays `unchecked` (never passed)."""
    path = package(tmp_path, {"per": TABLES, "sector": TABLES})
    for level in ("manifest", "schema", "full"):
        result = check(path, level=level)
        assert (result.errors, result.warnings) == ((), ())
    assert "TDS-T006" in check(path, level="full").unchecked
    hashes = package_hashes(path)
    assert {k: len(hashes["partitions"][k]) for k in TABLES} == dict.fromkeys(TABLES, 2)


@pytest.mark.parametrize(
    ("rows", "codes"),
    [
        (_values(["US:AAA", "US:AAA"], [D, D], [1.0, 2.0]), [("TDS-K001", "values")]),
        (_values(["US:ZZZ"], [D], [1.0]), [("TDS-R001", "values")]),  # 5.3.5: unknown symbol
        (_values([None], [D], [1.0]), [("TDS-S003", "values")]),  # an empty key cell
        (_values(["US:AAA"], [None], [1.0]), [("TDS-S003", "values")]),
        (_values(["US:AAA"], [D], [None]), []),  # an empty value ends the carry: no finding
        (_values(["US:AAA"], [SATURDAY], [1.0]), []),  # a date need not be a session
        (_values(["US:AAA", "US:AAA"], [D, SATURDAY], [1.0, 2.0]), []),
    ],
)  # fmt: skip
def test_values_rows(rows: dict[str, pa.Array], codes: list[Any], tmp_path: Path) -> None:
    assert found(package(tmp_path, {"per": {"values": rows}})) == codes


def test_the_key_is_compared_with_its_item(tmp_path: Path) -> None:
    """3.5: the same instrument and date under two items are two keys, no K001."""
    rows = {"values": _values(["US:AAA"], [D], [1.0])}
    assert found(package(tmp_path, {"per": rows, "pbr": rows})) == []
