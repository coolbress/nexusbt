"""`table_value_hash` (spec 5.9.2 `outputs{file: {physical_sha256, value_sha256}}`, 5.9.4): a
run output table's value hash is TDS 4.5's canonical serialisation, each column's type tag read
from its Arrow type (#250 Decisions, 2026-11-20)."""

from __future__ import annotations

import datetime as dt
import hashlib

import pyarrow as pa
import pytest

from nexusbt.data import table_value_hash
from nexusbt_tds.hash import encode_table

pytestmark = pytest.mark.unit

_UTC = pa.timestamp("us", tz="UTC")


def _table() -> pa.Table:
    return pa.table({
        "market": pa.array(["KR", "KR", "US"], pa.string()),
        "session_date": pa.array([dt.date(2020, 1, 7), dt.date(2020, 1, 6), dt.date(2020, 1, 6)]),
        "decision_ts": pa.array([1, 2, 3], _UTC),
        "n": pa.array([1, None, 3], pa.int64()),
        "code": pa.array([0, 1, 2], pa.int32()),
        "keep": pa.array([True, False, None]),
        "x": pa.array([0.5, float("nan"), -0.0]),
    })  # fmt: skip


def test_the_hash_is_tds_4_5_with_the_tags_of_the_arrow_types() -> None:
    table = _table()
    tags = [("market", "string"), ("session_date", "date"), ("decision_ts", "ts_us"),
            ("n", "i64"), ("code", "i32"), ("keep", "bool"), ("x", "f64")]  # fmt: skip
    key = ("session_date", "market")
    expected = hashlib.sha256(encode_table(table, tags, key)).hexdigest()
    assert table_value_hash(table, key) == expected


def test_row_order_and_chunks_do_not_change_it() -> None:
    table = _table()
    shuffled = pa.concat_tables([table.slice(2), table.slice(0, 2)])
    assert table_value_hash(shuffled, ("session_date", "market")) == table_value_hash(
        table, ("session_date", "market")
    )


def test_a_value_change_changes_it() -> None:
    table = _table()
    changed = table.set_column(6, "x", pa.array([0.5, 1.0, 0.0]))
    assert table_value_hash(changed, ()) != table_value_hash(table, ())


def test_a_type_with_no_tds_tag_is_refused() -> None:
    table = pa.table({"s": pa.array([{"a": 1}])})
    with pytest.raises(TypeError, match=r"s: .*struct"):
        table_value_hash(table, ())
