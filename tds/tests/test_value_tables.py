"""TDS 5.28: the value tables are judged by the checks every kind takes (#752's V1), and by
M018, M019 and M014 at the `manifest` level (#752's V2a, the owner's decisions of 2026-11-27).

Engine specification 5.3.5's five stops: an unknown symbol (R001), a key given twice (K001), an
empty key cell (S003), an item name outside the rule (M018), an item in two tables (M019).
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
    """5.28: two items of each kind pass, each item in one table (M019); the hashes cover them;
    the checker takes no instant from them, so T006 stays `unchecked` (never passed)."""
    items = {
        "per": "values",
        "pbr": "values",
        "base_rate": "market_values",
        "cpi": "market_values",
        "sector": "symbol_values",
        "industry": "symbol_values",
    }
    path = package(tmp_path, {item: {kind: TABLES[kind]} for item, kind in items.items()})
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


def manifest_codes(root: Path, *changes: Any) -> list[tuple[str, str | None]]:
    """The `manifest` level's findings on the base package after `changes`."""
    manifest, files = build.base()
    for change in changes:
        change(manifest, files)
    result = check(build.write(root, manifest, files), level="manifest")
    return [(f.code, f.dataset) for f in (*result.errors, *result.warnings)]


@pytest.mark.parametrize(
    ("item", "ok"),
    [("per", True), ("per_ttm", True), ("x1", True), ("match", True),  # a soft keyword reads
     ("PER", False), ("1st", False), ("_per", False), ("per-ttm", False), ("class", False),
     ("pér", False)],
)  # fmt: skip
def test_M018_item_names(item: str, ok: bool, tmp_path: Path) -> None:
    """5.28: 3.1's column-name rule, starting with a letter, not a Python keyword."""
    want = [] if ok else [("TDS-M018", "values")]
    assert manifest_codes(tmp_path, build._valued(("values", item))) == want


def test_M019_one_item_in_two_tables(tmp_path: Path) -> None:
    """5.28: an item lives in one value table, also across two datasets of one kind."""
    twice = build._valued(("values", "per"), ("symbol_values", "per"), ("market_values", "per"))
    assert manifest_codes(tmp_path / "a", twice) == [  # named on each later table
        ("TDS-M019", "symbol_values"), ("TDS-M019", "market_values")]  # fmt: skip

    def second_values(m: dict[str, Any], files: Any) -> None:
        other = dict(m["datasets"][-1], name="values_b")
        m["datasets"].append(other)  # the same files under a second name: M013 too

    found_b = manifest_codes(tmp_path / "b", build._valued(("values", "per")), second_values)
    assert ("TDS-M019", "values_b") in found_b


def _declare(**fields: Any) -> Any:
    def change(m: dict[str, Any], files: Any) -> None:
        (values,) = (d for d in m["datasets"] if d["kind"] == "values")
        values.update(fields)

    return change


@pytest.mark.parametrize(
    ("fields", "bad"),
    [
        ({"params": {"items": {"per": {"kind": "per_share"}}}}, 0),
        ({"params": {"items": {"per": {"kind": "share_count", "carry": "next_listing"}}}}, 0),
        ({"params": {"items": {"per": {"carry": 5}, "eps": {"carry": "none"}}}}, 0),
        ({"params": {"items": {"per": {}, "absent": {"carry": "to_end"}}}}, 0),  # not judged
        ({"params": {"items": {"per": {"kind": "per-share"}}}}, 1),
        ({"params": {"items": {"per": {"carry": "forever"}}}}, 1),
        ({"params": {"items": {"per": {"carry": 0}}}}, 1),
        ({"params": {"items": {"per": {"carry": 2.5}}}}, 1),
        ({"params": {"items": {"per": {"carry": "3"}}}}, 1),
        ({"params": {"items": {"per": {"carry": True}}}}, 1),
        ({"params": {"items": {"per": {"carr": 3}}}}, 1),  # a misspelt field
        ({"params": {"items": {"per": {"kind": "x", "carry": -1}}}}, 2),
        ({"params": {"items": {"per": "per_share"}}}, 1),
        ({"params": {"items": ["per"]}}, 1),
        ({"availability": {"rule": "session_close"}}, 1),  # 5.28 fixes it
    ],
)  # fmt: skip
def test_M014_declarations(fields: dict[str, Any], bad: int, tmp_path: Path) -> None:
    """5.28's `params.items` words and shape, and no `availability`, are M014 otherwise."""
    found_ = manifest_codes(tmp_path, build._valued(("values", "per")), _declare(**fields))
    assert found_ == [("TDS-M014", "values")] * bad


def test_symbol_values_carry_is_not_judged(tmp_path: Path) -> None:
    """The owner, 2026-11-27: a `carry` on `symbol_values` is not judged."""

    def carry(m: dict[str, Any], files: Any) -> None:
        m["datasets"][-1]["params"] = {"items": {"sector": {"carry": "none"}}}

    assert manifest_codes(tmp_path, build._valued(("symbol_values", "sector")), carry) == []
