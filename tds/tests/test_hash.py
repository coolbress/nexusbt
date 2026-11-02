"""TDS 4.5: the canonical value serialisation, its reference encoder and the published vectors."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from nexusbt_tds.hash import HashError, encode_table, value_hash

from . import ref_encoder

VECTORS = json.loads((Path(__file__).parents[1] / "conformance" / "hash-vectors.json").read_text())
ARROW = {
    "bool": pa.bool_(), "i8": pa.int8(), "i16": pa.int16(), "i32": pa.int32(), "i64": pa.int64(),
    "fixed": pa.int64(), "f64": pa.float64(), "date": pa.date32(), "string": pa.string(),
    "id": pa.string(), "code": pa.string(), "ts_us": pa.timestamp("us", "UTC"),
    "ts_ns": pa.timestamp("ns", "UTC"), "list<code>": pa.list_(pa.string()), "json": pa.string(),
}  # fmt: skip


def arrow_table(vector: dict[str, Any]) -> pa.Table:
    """A vector's rows as the Arrow table a Parquet file of that dataset would read back."""
    columns: dict[str, pa.Array] = {}
    for i, col in enumerate(vector["columns"]):
        values = [row[i] for row in vector["rows"]]
        if col["type"] == "date":
            values = [v and dt.date.fromisoformat(v) for v in values]
        columns[col["name"]] = pa.array(values, ARROW[col["type"]])
    return pa.table(columns)


def spec(vector: dict[str, Any]) -> list[tuple[str, str]]:
    return [(c["name"], c["type"]) for c in vector["columns"]]


@pytest.mark.parametrize("vector", VECTORS["vectors"], ids=lambda v: v["name"])
def test_vectors_match_published(vector: dict[str, Any]) -> None:
    data = encode_table(arrow_table(vector), spec(vector), vector["key"])
    assert data.hex() == vector["bytes"]
    assert hashlib.sha256(data).hexdigest() == vector["sha256"]
    assert not [n for n in vector.get("absent", []) if f"\n{n}\t".encode() in data]


@pytest.mark.parametrize("vector", VECTORS["vectors"], ids=lambda v: v["name"])
def test_reference_encoder_matches_pyarrow_path(vector: dict[str, Any]) -> None:
    reference = ref_encoder.encode(spec(vector), vector["key"], vector["rows"])
    assert reference == encode_table(arrow_table(vector), spec(vector), vector["key"])


def package(root: Path, dataset: dict[str, Any], parts: dict[str, pa.Table], **write: Any) -> Path:
    """A package of one dataset, its files written with the Parquet options in `write`."""
    for rel, table in parts.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(table, root / rel, **write)
    dataset = {**dataset, "files": [{"path": rel} for rel in parts]}
    (root / "tds.json").write_text(json.dumps({"tds_version": "1.0", "datasets": [dataset]}))
    return root


INSTRUMENTS = {"name": "instruments", "kind": "instruments", "path": "instruments"}


def instruments(lot: float = 1.0) -> pa.Table:
    return pa.table({
        "instrument_id": ["US:B", "KR:A", "US:C"], "asset_class": ["equity", "etf", "equity"],
        "market": ["US", "KR", "US"], "listed_on": [dt.date(2020, 1, 2)] * 3,
        "lot_size": [lot, 1.0, -0.0], "is_synthetic": [False, False, True],
    })  # fmt: skip


def test_value_hash_ignores_physical_choices(tmp_path: Path) -> None:
    whole = instruments()
    one = package(tmp_path / "a", INSTRUMENTS, {"instruments/part-00000.parquet": whole},
                  compression="zstd", row_group_size=2, use_dictionary=True)  # fmt: skip
    split = {"instruments/part-00000.parquet": whole.slice(2), "instruments/part-00001.parquet":
             whole.slice(0, 2).cast(whole.schema)}  # fmt: skip
    two = package(tmp_path / "b", INSTRUMENTS, split, compression="snappy", use_dictionary=False)
    assert value_hash(one, "instruments") == value_hash(two, "instruments")
    other = package(tmp_path / "c", INSTRUMENTS, {"instruments/p.parquet": instruments(lot=100.0)})
    assert value_hash(other, "instruments") != value_hash(one, "instruments")


MARKET, YEAR = {"name": "market", "type": "code"}, {"name": "year", "type": "i16"}
BARS = {"name": "bars_1d", "kind": "bars", "path": "bars", "partitioning": [MARKET, YEAR],
        "key": ["instrument_id", "session_date"], "params": {"freq": "1d"}}  # fmt: skip
KR = pa.table({"instrument_id": ["KR:A", "KR:A"], "close": [7000.0, 6990.0],
               "session_date": [dt.date(2024, 1, 3), dt.date(2024, 1, 2)]})  # fmt: skip
US = pa.table({"instrument_id": ["US:B"], "session_date": [dt.date(2024, 1, 3)], "close": [10.0]})
PARTS = {"bars/market=KR/year=2024/part-00000.parquet": KR,
         "bars/market=US/year=2024/part-00000.parquet": US}  # fmt: skip
(PUBLISHED,) = (v["sha256"] for v in VECTORS["vectors"] if v["name"] == "partition_columns")


def test_partition_columns_from_path(tmp_path: Path) -> None:
    assert value_hash(package(tmp_path / "a", BARS, PARTS), "bars_1d") == PUBLISHED
    moved = {k.replace("US/year=2024", "US/year=2025"): v for k, v in PARTS.items()}
    assert value_hash(package(tmp_path / "b", BARS, moved), "bars_1d") != PUBLISHED


def test_bars_without_a_key_take_the_schema_key_of_their_freq(tmp_path: Path) -> None:
    # Key order puts `ask` first; sorting by every column would put `bid` (smaller ts_end) first.
    ts = pa.timestamp("us", "UTC")
    rows = pa.table({"instrument_id": ["A", "A"], "session_date": [dt.date(2024, 1, 2)] * 2,
                     "ts_start": pa.array([0, 0], ts), "ts_end": pa.array([2, 1], ts),
                     "price_type": ["ask", "bid"]})  # fmt: skip
    cols = [{"name": n, "type": "ts_us"} for n in ("ts_start", "ts_end")]
    minute = {"name": "bars_1m", "kind": "bars", "params": {"freq": "1m"}, "columns": cols}
    keyed = {**minute, "key": ["instrument_id", "ts_start", "price_type"]}
    parts = {"bars/part-00000.parquet": rows}
    expected = value_hash(package(tmp_path / "a", keyed, parts), "bars_1m")
    assert value_hash(package(tmp_path / "b", minute, parts), "bars_1m") == expected


def with_ts_start(unit: str) -> dict[str, pa.Table]:
    stamp = pa.timestamp(unit, "UTC")
    return {k: v.append_column("ts_start", pa.array([0] * len(v), stamp)) for k, v in PARTS.items()}


@pytest.mark.parametrize(("change", "message"), [
    ({"partitioning": [MARKET, YEAR, {"name": "venue", "type": "code"}]}, "no value"),
    ({"partitioning": [MARKET, {"name": "year", "type": "bool"}]}, "no path rule"),
    ({"columns": [{"name": "ts_start", "type": "ts_us/ns"}]}, "no declared type"),
])  # fmt: skip
def test_no_value_hash_without_a_rule(tmp_path: Path, change: dict[str, Any], message: str) -> None:
    with pytest.raises(HashError, match=message):
        value_hash(package(tmp_path, {**BARS, **change}, with_ts_start("us")), "bars_1d")


def test_a_declared_unit_sets_the_bytes(tmp_path: Path) -> None:
    declared = {**BARS, "columns": [{"name": "ts_start", "type": "ts_ns"}]}
    us, ns = (package(tmp_path / u, declared, with_ts_start(u)) for u in ("us", "ns"))
    assert value_hash(us, "bars_1d") == value_hash(ns, "bars_1d")


def test_an_absent_column_and_an_all_null_column_differ(tmp_path: Path) -> None:
    nulls = {k: v.append_column("vwap", pa.nulls(len(v), pa.float64())) for k, v in PARTS.items()}
    assert value_hash(package(tmp_path, BARS, nulls), "bars_1d") != PUBLISHED


def test_bytes_written_out_by_hand() -> None:
    table = pa.table({"flag": pa.array([True, None]), "n": pa.array([2, 1], pa.int16())})
    one, two = (1).to_bytes(8, "little"), (2).to_bytes(8, "little")
    assert encode_table(table, [("flag", "bool"), ("n", "i16")], key=["n"]) == (
        b"TDSV1\nflag\tbool\nn\ti16\n\n"  # header
        + b"\x00" + b"\x01" + one  # row n=1: flag null, n 1 (sorted first)
        + b"\x01\x01" + b"\x01" + two  # row n=2: flag true, n 2
    )  # fmt: skip
