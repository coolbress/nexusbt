"""TDS 4.5: the canonical value serialisation, its reference encoder and the published vectors."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import shutil
import tracemalloc
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from nexusbt_tds import cli
from nexusbt_tds import hash as tds_hashes
from nexusbt_tds.hash import (
    HashError,
    canonical_json,
    encode_table,
    package_hashes,
    semantic_hash,
    semantic_json,
    value_hash,
)
from nexusbt_tds.manifest import read_manifest

from . import ref_encoder

VECTORS = json.loads((Path(__file__).parents[1] / "conformance" / "hash-vectors.json").read_text())
ARROW = {
    "bool": pa.bool_(), "i8": pa.int8(), "i16": pa.int16(), "i32": pa.int32(), "i64": pa.int64(),
    "fixed": pa.int64(), "f64": pa.float64(), "date": pa.date32(), "string": pa.string(),
    "id": pa.string(), "code": pa.string(), "ts_us": pa.timestamp("us", "UTC"),
    "ts_ns": pa.timestamp("ns", "UTC"), "list<code>": pa.list_(pa.string()), "json": pa.string(),
}  # fmt: skip


@pytest.fixture(autouse=True, params=["in memory", "in sorted runs"])
def sorted_in(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> str:
    """Every hash here twice: a dataset sorted whole, and one row per run (#309's external sort,
    a run per batch written to a temporary file and merged): the same bytes either way."""
    if request.param == "in sorted runs":
        monkeypatch.setattr(tds_hashes, "BATCH_ROWS", 1)
    return str(request.param)


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


TABLES = [v for v in VECTORS["vectors"] if "rows" in v]  # a logical table; else files (below)


def _published(vector: dict[str, Any]) -> bytes:
    """A vector's bytes: one stream, or a partitioned dataset's joined bytes (TDS 4.5 step 6)
    after each partition's own stream is matched."""
    if "partitioning" not in vector:
        return encode_table(arrow_table(vector), spec(vector), vector["key"])
    names = [p["name"] for p in vector["partitioning"]]
    at = [spec(vector).index(c) for c in spec(vector) if c[0] in names]
    digests = {}
    for part in vector["partitions"]:
        mine = [r for r in vector["rows"] if [r[i] for i in at] == part["values"]]
        data = encode_table(arrow_table({**vector, "rows": mine}), spec(vector), vector["key"])
        assert (data.hex(), hashlib.sha256(data).hexdigest()) == (part["bytes"], part["sha256"])
        digests[b"".join(ref_encoder.text(str(v)) for v in part["values"])] = data
    hashed = {n: hashlib.sha256(d).digest() for n, d in digests.items()}
    return tds_hashes.joined(vector["partitioning"], hashed)


@pytest.mark.parametrize("vector", TABLES, ids=lambda v: v["name"])
def test_vectors_match_published(vector: dict[str, Any]) -> None:
    data = _published(vector)
    assert data.hex() == vector["bytes"]
    assert hashlib.sha256(data).hexdigest() == vector["sha256"]
    assert not [n for n in vector.get("absent", []) if f"\n{n}\t".encode() in data]


@pytest.mark.parametrize("vector", TABLES, ids=lambda v: v["name"])
def test_reference_encoder_matches_pyarrow_path(vector: dict[str, Any]) -> None:
    if "partitioning" in vector:
        names = [p["name"] for p in vector["partitioning"]]
        joined, _ = ref_encoder.partitioned(spec(vector), vector["key"], vector["rows"], names)
        assert joined == _published(vector)
        return
    reference = ref_encoder.encode(spec(vector), vector["key"], vector["rows"])
    assert reference == encode_table(arrow_table(vector), spec(vector), vector["key"])


@pytest.mark.parametrize("vector", [v for v in VECTORS["vectors"] if "files" in v],
                         ids=lambda v: v["name"])  # fmt: skip
def test_vectors_of_files_match_published(vector: dict[str, Any], tmp_path: Path) -> None:
    """The same values split into files another way, in another order: one hash (#725 160)."""
    names = [c["name"] for c in vector["columns"]]
    parts = {f"bars/{rel}": arrow_table({**vector, "rows": rows}) for rel, rows in
             vector["files"].items()}  # fmt: skip
    dataset = {**BARS, "partitioning": vector["partitioning"], "key": vector["key"]}
    assert names == ["instrument_id", "session_date", "close"]
    assert value_hash(package(tmp_path, dataset, parts), "bars_1d") == vector["sha256"]
    (same,) = (v for v in VECTORS["vectors"] if v["name"] == vector["same_as"])
    assert vector["sha256"] == same["sha256"]


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


def test_two_partitionings_of_the_same_values_hash_apart(tmp_path: Path) -> None:
    """One logical table split by `obs_status` or by `price_type`, both "traded": the same
    partition names and rows; the joined bytes name the columns (#725 Decisions 198)."""
    row = {"instrument_id": ["US:B"], "session_date": [dt.date(2024, 1, 3)], "close": [10.0]}
    hashes = []
    for by, other in (("obs_status", "price_type"), ("price_type", "obs_status")):
        dataset = {**BARS, "partitioning": [{"name": by, "type": "code"}]}
        part = {f"bars/{by}=traded/part-00000.parquet": pa.table({**row, other: ["traded"]})}
        hashes.append(value_hash(package(tmp_path / by, dataset, part), "bars_1d"))
    assert hashes[0] != hashes[1]


def test_a_partition_is_one_some_row_holds(tmp_path: Path) -> None:
    """An empty file in a partition of its own adds no partition; with no rows at all the
    dataset joins none (TDS 4.5 step 6)."""
    empty = US.slice(0, 0)
    more = {**PARTS, "bars/market=JP/year=2024/part-00000.parquet": empty}
    assert value_hash(package(tmp_path / "a", BARS, more), "bars_1d") == PUBLISHED
    none = {"bars/market=JP/year=2024/part-00000.parquet": empty}
    data = tds_hashes.joined([MARKET, YEAR], {})
    expected = hashlib.sha256(data).hexdigest()
    assert value_hash(package(tmp_path / "b", BARS, none), "bars_1d") == expected
    names = b"\x02\x00\x00\x00\x06\x00\x00\x00market\x04\x00\x00\x00year"
    assert data == b"TDSP1\n" + names + b"\x00\x00\x00\x00"  # no partition


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


TS = [{"name": "ts_start", "type": "ts_us"}]
#: Two weekly bars whose `ts_start` runs against their `session_date`: the intraday key would put
#: the 2024-01-12 bar first, the daily key the 2024-01-05 bar.
AGAINST = pa.table({"instrument_id": ["A", "A"], "close": [1.0, 2.0],
                    "session_date": [dt.date(2024, 1, 12), dt.date(2024, 1, 5)],
                    "ts_start": pa.array([0, 1], pa.timestamp("us", "UTC")),
                    "price_type": ["last", "last"]})  # fmt: skip


@pytest.mark.parametrize("freq", ["1w", "1mo"])
@pytest.mark.parametrize("rows", [KR, AGAINST], ids=["daily columns", "ts_start against the date"])
def test_bars_of_a_day_or_longer_hash_by_the_daily_key(
    tmp_path: Path, freq: str, rows: pa.Table
) -> None:
    """#609: TDS 5.5 makes only `freq<1d` intraday, and the key checks (K001, K002) judge `1w` and
    `1mo` bars by the daily key; the value hash orders them by that same key."""
    bars = {"name": "bars", "kind": "bars", "params": {"freq": freq}, "columns": TS}
    daily = {**bars, "key": ["instrument_id", "session_date"]}
    parts = {"bars/part-00000.parquet": rows}
    expected = value_hash(package(tmp_path / "a", daily, parts), "bars")
    assert value_hash(package(tmp_path / "b", bars, parts), "bars") == expected


@pytest.mark.parametrize(("freq", "rows", "pinned"), [
    ("1d", KR, "7faa62bba2fefc0399d568c5f52b736e9c0fa4b0a539b6e772f68c4f736e7831"),
    ("1d", AGAINST, "f13e9e5149031fd606d6afb55261bd4454eaee79c2c5493921cb1b7355ea8ed7"),
    ("1m", AGAINST, "d1b9cbfd44d96b1ccb6413c1c86546b97afe188d7a0d5707b54a1895c0ce9c5b"),
    ("1h", AGAINST, "d1b9cbfd44d96b1ccb6413c1c86546b97afe188d7a0d5707b54a1895c0ce9c5b"),
])  # fmt: skip
def test_daily_and_intraday_bars_keep_their_hash(
    tmp_path: Path, freq: str, rows: pa.Table, pinned: str
) -> None:
    """#609 changes only `1w` and `1mo`: these hashes were taken before it."""
    bars = {"name": "bars", "kind": "bars", "params": {"freq": freq}, "columns": TS}
    assert value_hash(package(tmp_path, bars, {"bars/part-00000.parquet": rows}), "bars") == pinned


def with_ts_start(unit: str) -> dict[str, pa.Table]:
    stamp = pa.timestamp(unit, "UTC")
    return {k: v.append_column("ts_start", pa.array([0] * len(v), stamp)) for k, v in PARTS.items()}


@pytest.mark.parametrize(("change", "message"), [
    ({"partitioning": [MARKET, YEAR, {"name": "venue", "type": "code"}]}, "no value"),
    ({"partitioning": [MARKET, {"name": "year", "type": "bool"}]}, "no path rule"),
    ({"columns": [{"name": "ts_start", "type": "ts_us/ns"}]}, "no declared type"),
    ({"columns": [{"name": "ts_start", "type": "i64"}]}, "no declared type"),
    ({"columns": [{"name": "ts_start", "type": "string"}]}, "no declared type"),
    ({"key": ["instrument_id", "nope"], "columns": [{"name": "ts_start", "type": "ts_us"}]},
     "not in the data"),
])  # fmt: skip
def test_no_value_hash_without_a_rule(tmp_path: Path, change: dict[str, Any], message: str) -> None:
    with pytest.raises(HashError, match=message):
        value_hash(package(tmp_path, {**BARS, **change}, with_ts_start("us")), "bars_1d")


#: TDS 4.5 step 1: the schema file's columns, then a column declared in tds.json only
#: (`momentum`). On `tradability_daily` since the panels left (#752); the published vector
#: `declared_non_schema_column` is checked as a table by the tests above.
STATUS = {"name": "status", "kind": "tradability_daily", "path": "status",
          "columns": [{"name": "instrument_id", "type": "id"},
                      {"name": "ts_available", "type": "ts_us"},
                      {"name": "momentum", "type": "f64"}]}  # fmt: skip


def status(momentum: float) -> pa.Table:
    return pa.table({
        "instrument_id": ["US:B"], "session_date": [dt.date(2024, 1, 31)],
        "status_known": [True], "ts_available": pa.array([0], ARROW["ts_us"]),
        "momentum": [momentum],
    })  # fmt: skip


def test_value_hash_sees_declared_column(tmp_path: Path) -> None:
    one, other = (
        package(tmp_path / str(m), STATUS, {"status/p.parquet": status(m)}) for m in (1.0, 999.0)
    )
    assert value_hash(one, "status") != value_hash(other, "status")


@pytest.mark.parametrize("said", ["ts_ns", "i64", None])
def test_a_typed_column_takes_the_schema_type(tmp_path: Path, said: str | None) -> None:
    # `ts_available` is `ts_us` in the schema file: another declaration is S002 at the schema
    # level, and the hash still takes the schema's tag (TDS 4.5 step 3, #404).
    kept = [{"name": "instrument_id", "type": "id"}, {"name": "momentum", "type": "f64"}]
    declared = [*kept, {"name": "ts_available", "type": said}] if said else kept
    parts = {"status/p.parquet": status(1.0)}
    other = package(tmp_path / "other", {**STATUS, "columns": declared}, parts)
    same = package(tmp_path / "same", STATUS, parts)
    assert value_hash(other, "status") == value_hash(same, "status")


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


def tds_hash(path: Path, capsys: pytest.CaptureFixture[str], *flags: str) -> dict[str, str]:
    """`tds hash PATH`: its `name value` lines, as a mapping."""
    assert cli.main(["hash", str(path), *flags]) == 0
    return dict(line.split(" ", 1) for line in capsys.readouterr().out.splitlines())


def edited(src: Path, dst: Path, change: Any) -> Path:
    """A copy of package `src` whose tds.json `change(manifest)` edited."""
    shutil.copytree(src, dst)
    manifest = json.loads((dst / "tds.json").read_text())
    change(manifest)
    (dst / "tds.json").write_text(json.dumps(manifest))
    return dst


BARS_TWO = {**BARS, "availability": {"rule": "ts_end"}, "params": {"freq": "1d"}}


def test_recompress_same_semantic(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    a = tds_hash(package(tmp_path / "a", BARS_TWO, PARTS, compression="zstd"), capsys)
    b = tds_hash(package(tmp_path / "b", BARS_TWO, PARTS, compression="snappy",
                         row_group_size=1, use_dictionary=False), capsys)  # fmt: skip
    for name in ("value_sha256", "semantic_sha256", "bars_1d"):
        assert a[name] == b[name]
    assert a["physical_sha256"] != b["physical_sha256"]  # the files' bytes did change
    assert a["bars_1d"] == PUBLISHED


def test_availability_change_changes_semantic(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    a = package(tmp_path / "a", BARS_TWO, PARTS)
    rule = {"rule": "ts_end+PT1H"}
    later = edited(a, tmp_path / "b", lambda m: m["datasets"][0].update(availability=rule))
    before, after = tds_hash(a, capsys), tds_hash(later, capsys)
    assert before["value_sha256"] == after["value_sha256"]
    assert before["semantic_sha256"] != after["semantic_sha256"]


def test_semantic_hash_resolves_defaults_and_dataset_order(tmp_path: Path) -> None:
    a = package(tmp_path / "a", BARS_TWO, PARTS)
    explicit = edited(a, tmp_path / "b", lambda m: m["datasets"][0].update(price_exponent=-9))
    assert semantic_hash(explicit) == semantic_hash(a)
    other = {**INSTRUMENTS, "files": [{"path": "instruments/part-00000.parquet"}]}
    pq.write_table(instruments(), tmp_path / "part.parquet")
    two = [edited(a, tmp_path / n, lambda m, at=at: m["datasets"].insert(at, other)) for n, at
           in (("c", 0), ("d", 1))]  # fmt: skip
    for pkg in two:
        (pkg / "instruments").mkdir()
        shutil.copy(tmp_path / "part.parquet", pkg / "instruments" / "part-00000.parquet")
    assert semantic_hash(two[0]) == semantic_hash(two[1]) != semantic_hash(a)
    changed = edited(a, tmp_path / "e", lambda m: m["datasets"][0].update(price_exponent=-8))
    assert semantic_hash(changed) != semantic_hash(a)


def with_markets(src: Path, dst: Path, **us: Any) -> Path:
    """A copy of `src` whose tds.json has markets US (the stable fields, then `us`) and KR."""
    stable = {"calendar_id": "XNYS", "currency": "USD", "timezone": "America/New_York"}
    kr = {"calendar_id": "XKRX", "currency": "KRW", "timezone": "Asia/Seoul"}
    return edited(src, dst, lambda m: m.update(markets={"US": {**stable, **us}, "KR": kr}))


def test_semantic_hash_ignores_watermark(tmp_path: Path) -> None:
    a = package(tmp_path / "a", BARS_TWO, PARTS)
    old = with_markets(a, tmp_path / "old", complete_through_session="2024-01-03",
                       complete_through="2024-01-03T21:00:00Z")  # fmt: skip
    new = with_markets(a, tmp_path / "new", complete_through_session="2024-01-04",
                       complete_through="2024-01-04T21:00:00Z")  # fmt: skip
    plain = with_markets(a, tmp_path / "b")
    assert semantic_hash(old) == semantic_hash(new) == semantic_hash(plain)


def test_semantic_hash_ignores_unknown_market_key(tmp_path: Path) -> None:
    a = package(tmp_path / "a", BARS_TWO, PARTS)
    extra = with_markets(a, tmp_path / "x", x_published_by="nightly")
    assert semantic_hash(extra) == semantic_hash(with_markets(a, tmp_path / "b"))


def test_semantic_hash_sees_market_currency(tmp_path: Path) -> None:
    a = package(tmp_path / "a", BARS_TWO, PARTS)
    plain = with_markets(a, tmp_path / "b")
    for field, value in (("currency", "EUR"), ("calendar_id", "XNAS"), ("timezone", "UTC")):
        assert semantic_hash(with_markets(a, tmp_path / field, **{field: value})) != (
            semantic_hash(plain)
        )


def test_semantic_json_keeps_absent_market_fields_absent(tmp_path: Path) -> None:
    a = package(tmp_path / "a", BARS_TWO, PARTS)
    us = {"currency": "USD", "complete_through": "2024-01-03T21:00:00Z"}
    pkg = edited(a, tmp_path / "b", lambda m: m.update(markets={"US": us}))
    assert '"markets":{"US":{"currency":"USD"}}' in semantic_json(pkg)


def test_canonical_json_is_rfc_8785() -> None:
    numbers = [1.0, -9.0, 1e16, 1e21, 1e-7, 2e-3, -0.0, 333333333.33333329, 1e-27, 5]
    doc = {"": 1, "\U0001f600": 2, "é": 3, "a": numbers, "s": 'a"b\\c\n\x01é', "n": None}
    assert canonical_json(doc) == (  # keys by UTF-16 code units: U+1F600 (D83D) before U+E000
        '{"a":[1,-9,10000000000000000,1e+21,1e-7,0.002,0,333333333.3333333,1e-27,5],'
        '"n":null,"s":"a\\"b\\\\c\\n\\u0001é","é":3,"\U0001f600":2,"":1}'
    )


def test_editions_and_roll_rules_are_not_hashed(tmp_path: Path) -> None:
    """#752's 12e (TDS 4.2, 4.5): a package that still writes `editions` or `roll_rules` hashes
    as one without them."""
    plain = package(tmp_path / "a", BARS_TWO, PARTS)
    old = edited(plain, tmp_path / "b", lambda m: m.update(
        editions={"default": "strict", "values": {"strict": "x"}}, roll_rules={}))  # fmt: skip
    assert semantic_json(old) == semantic_json(plain)
    assert "editions" not in semantic_json(old)


def test_semantic_json_holds_every_listed_key(tmp_path: Path) -> None:
    exponent = edited(package(tmp_path / "a", BARS_TWO, PARTS), tmp_path / "b",
                      lambda m: m["datasets"][0].update(price_exponent=-9.0))  # fmt: skip
    assert semantic_json(exponent) == (
        '{"currencies":null,"datasets":[{"availability":{"rule":"ts_end"},'
        '"key":["instrument_id","session_date"],"kind":"bars","name":"bars_1d",'
        '"params":{"freq":"1d"},"pit_quality":null,"price_exponent":-9,"schema_version":null,'
        f'"size_exponent":0,"units":{{}},"value_sha256":"{PUBLISHED}"}}],'
        '"hash_spec":"tds-hash-2","id_namespaces":null,"markets":null,"policies":null,'
        '"profiles":null,"tds_version":"1.0"}'  # no editions or roll_rules since 12e (#752)
    )


@pytest.mark.parametrize("change", [
    lambda m, root: (root / m["datasets"][0]["files"][0]["path"]).write_bytes(b"not parquet"),
    lambda m, root: m["datasets"][0]["files"].append({"path": "bars/missing.parquet"}),
    lambda m, root: m["datasets"][0].update(kind="nonsense"),
    lambda m, root: m["datasets"][0]["files"].append({"path": "/etc/hosts"}),  # outside: not read
    lambda m, root: m["datasets"][0]["files"].append(m["datasets"][0]["files"][0]),
])  # fmt: skip
def test_bad_data_exits_1(tmp_path: Path, change: Any) -> None:
    pkg = package(tmp_path / "a", BARS_TWO, PARTS)
    bad = edited(pkg, tmp_path / "b", lambda m: change(m, tmp_path / "b"))
    assert cli.main(["hash", str(bad)]) == 1


def test_file_value_hash_written(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    plain = package(tmp_path / "plain", BARS_TWO, PARTS)
    pkg = edited(plain, tmp_path / "a", lambda m: m.update(title="kept", producer={"name": "p"}))
    printed = tds_hash(pkg, capsys, "--write")
    written = json.loads((pkg / "tds.json").read_text())
    assert (written["title"], written["producer"]) == ("kept", {"name": "p"})
    assert written["hashes"] == {"hash_spec": "tds-hash-2", **{
        k: printed[k] for k in ("physical_sha256", "value_sha256", "semantic_sha256")}}  # fmt: skip
    (dataset,) = written["datasets"]
    assert dataset["value_sha256"] == printed["bars_1d"] == PUBLISHED
    (vector,) = (v for v in VECTORS["vectors"] if v["name"] == "partition_columns")
    for entry in dataset["files"]:
        assert entry["sha256"] == hashlib.sha256((pkg / entry["path"]).read_bytes()).hexdigest()
        # that file's rows only, one stream: alone in its partition, the partition's hash
        (own,) = (p for p in vector["partitions"] if f"market={p['values'][0]}/" in entry["path"])
        assert entry["value_sha256"] == own["sha256"]
        assert printed[entry["path"]] == f"{entry['sha256']} {entry['value_sha256']}"
    assert tds_hash(pkg, capsys) == printed  # writing the hashes does not change them


def test_sorted_runs_go_beside_the_package_and_are_removed(tmp_path: Path, sorted_in: str) -> None:
    pkg = package(tmp_path / "pkg", BARS_TWO, PARTS)
    spilled: list[Path] = []
    assert package_hashes(pkg, spilled=spilled)["value_sha256"]
    assert [p.parent for p in spilled] == ([tmp_path] if sorted_in == "in sorted runs" else [])
    assert sorted(p.name for p in tmp_path.iterdir()) == ["pkg"]  # nothing left beside it


def test_sorted_runs_are_removed_when_the_hash_fails(tmp_path: Path, sorted_in: str) -> None:
    # `x_note` declared i64: the first file's nulls encode, the second file's text does not
    note = {**BARS_TWO, "columns": [{"name": "x_note", "type": "i64"}]}
    first, second = PARTS.values()
    notes = [pa.nulls(2, pa.int64()), pa.array(["text"])]
    tables = [t.append_column("x_note", n) for t, n in zip((first, second), notes, strict=True)]
    pkg = package(tmp_path / "pkg", note, dict(zip(PARTS, tables, strict=True)))
    spilled: list[Path] = []
    with pytest.raises(HashError, match="bars_1d"):
        package_hashes(pkg, spilled=spilled)
    assert len(spilled) == (sorted_in == "in sorted runs")  # written, then the hash failed
    assert sorted(p.name for p in tmp_path.iterdir()) == ["pkg"]


@pytest.mark.parametrize(("files", "message"), [
    (lambda fs: [*fs, fs[0]], r"bars_1d: a file is listed twice \(TDS-M013\)"),
    (lambda fs: [], "bars_1d: no files, no rows to hash"),
])  # fmt: skip
def test_a_dataset_hash_refuses_files_it_cannot_hash(
    tmp_path: Path, files: Any, message: str
) -> None:
    pkg = package(tmp_path / "pkg", BARS_TWO, PARTS)  # `tds hash` stops a file listed twice
    (entry,) = read_manifest(pkg).datasets  # earlier, in the inventory: here, a caller of its own
    with pytest.raises(HashError, match=message):
        tds_hashes.dataset_hashes(pkg, {**entry, "files": files(entry["files"])}, tmp_path, [])


def test_a_sorted_run_that_ends_early_fails_the_hash(tmp_path: Path) -> None:
    run = tmp_path / "run.tmp"  # a record that says its key is 10 bytes, then 5 bytes
    run.write_bytes(tds_hashes._RECORD.pack(10, 0, 0, 0) + b"short")
    fd = os.open(run, os.O_RDONLY)
    try:
        with pytest.raises(HashError, match="a temporary sort file ended early"):
            list(tds_hashes._run(fd, 0, run.stat().st_size))
    finally:
        os.close(fd)


def test_short_reads_of_a_sorted_run_still_give_the_hash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A network file system may return fewer bytes than asked before the end (#309's review of
    #325): the merge reads again rather than failing the hash."""
    pread = os.pread
    monkeypatch.setattr(os, "pread", lambda fd, n, at: pread(fd, min(n, 7), at))
    assert value_hash(package(tmp_path / "pkg", BARS_TWO, PARTS), "bars_1d") == PUBLISHED


def test_the_merge_buffers_share_one_budget_however_many_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """#309: each run's read buffer was 32 KiB, so 927 runs (`bars_1d`) held 30 MB. The runs now
    share `_MERGE_BYTES`; here 200 runs of 40 KB merge in a 1 MiB budget."""
    monkeypatch.setattr(tds_hashes, "_MERGE_BYTES", 1 << 20)
    records = [(f"{n:08}".encode(), b"x" * 92, 0, b"") for n in range(80_000)]
    with tds_hashes.SortedRuns(tmp_path, []) as runs:
        for start in range(0, len(records), 400):
            runs.add(records[start : start + 400])
        del records
        tracemalloc.start()
        merged = sum(1 for _ in runs.merged())
        peak = tracemalloc.get_traced_memory()[1]
        tracemalloc.stop()
    assert merged == 80_000
    assert peak < 2 << 20, peak  # the 1 MiB of buffers, a record per run and the heap


def test_tds_hash_writes_sorted_runs_to_the_folder_named(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], sorted_in: str
) -> None:
    pkg, scratch = package(tmp_path / "pkg", BARS_TWO, PARTS), tmp_path / "scratch"
    scratch.mkdir()
    assert cli.main(["hash", str(pkg), "--tmp-dir", str(scratch)]) == 0
    out, err = capsys.readouterr()
    assert f"bars_1d {PUBLISHED}" in out.splitlines()
    assert (str(scratch) in err) == (sorted_in == "in sorted runs")  # where, on stderr
    assert list(scratch.iterdir()) == []
