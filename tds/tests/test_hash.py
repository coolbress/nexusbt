"""TDS 4.5: the canonical value serialisation, its reference encoder and the published vectors."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from nexusbt_tds import cli
from nexusbt_tds.hash import (
    HashError,
    canonical_json,
    encode_table,
    semantic_hash,
    semantic_json,
    value_hash,
)

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
    ({"key": ["instrument_id", "nope"], "columns": [{"name": "ts_start", "type": "ts_us"}]},
     "not in the data"),
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


def test_semantic_json_holds_every_listed_key(tmp_path: Path) -> None:
    exponent = edited(package(tmp_path / "a", BARS_TWO, PARTS), tmp_path / "b",
                      lambda m: m["datasets"][0].update(price_exponent=-9.0))  # fmt: skip
    assert semantic_json(exponent) == (
        '{"currencies":null,"datasets":[{"availability":{"rule":"ts_end"},'
        '"key":["instrument_id","session_date"],"kind":"bars","name":"bars_1d",'
        '"params":{"freq":"1d"},"pit_quality":null,"price_exponent":-9,"schema_version":null,'
        f'"size_exponent":0,"units":{{}},"value_sha256":"{PUBLISHED}"}}],"editions":null,'
        '"hash_spec":"tds-hash-1","id_namespaces":null,"markets":null,"policies":null,'
        '"profiles":null,"roll_rules":null,"tds_version":"1.0"}'
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
    assert written["hashes"] == {"hash_spec": "tds-hash-1", **{
        k: printed[k] for k in ("physical_sha256", "value_sha256", "semantic_sha256")}}  # fmt: skip
    (dataset,) = written["datasets"]
    assert dataset["value_sha256"] == printed["bars_1d"] == PUBLISHED
    for entry in dataset["files"]:
        assert entry["sha256"] == hashlib.sha256((pkg / entry["path"]).read_bytes()).hexdigest()
        one = {entry["path"]: PARTS[entry["path"]]}
        alone = package(tmp_path / entry["path"].split("/")[1], BARS_TWO, one)
        assert entry["value_sha256"] == value_hash(alone, "bars_1d")  # that file's rows only
        assert printed[entry["path"]] == f"{entry['sha256']} {entry['value_sha256']}"
    assert tds_hash(pkg, capsys) == printed  # writing the hashes does not change them
