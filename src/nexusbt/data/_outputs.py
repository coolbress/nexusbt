"""The value hash of a run output table (5.9.2 `outputs{file: {value_sha256}}`, 5.9.4).

TDS 4.5's canonical serialisation, the function that hashes a dataset; a run table declares no
schema, so each column's type tag is read from its Arrow type. `api` hands the result to
`artifacts`, which may not import `nexusbt_tds` (2.5; #250 Decisions, 2026-11-20)."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence

import pyarrow as pa

from nexusbt_tds.hash import encode_table

_TAGS = {pa.int8(): "i8", pa.int16(): "i16", pa.int32(): "i32", pa.int64(): "i64",
         pa.bool_(): "bool", pa.float64(): "f64", pa.date32(): "date", pa.string(): "string",
         pa.large_string(): "string"}  # fmt: skip


def _tag(kind: pa.DataType) -> str | None:
    """TDS 3.2's type name for an Arrow type, or None when there is none."""
    if pa.types.is_dictionary(kind):
        kind = kind.value_type
    if pa.types.is_timestamp(kind) and kind.unit in ("us", "ns"):
        return f"ts_{kind.unit}"
    if pa.types.is_list(kind) or pa.types.is_large_list(kind):
        inner = _tag(kind.value_type)
        return None if inner is None or inner.startswith("list<") else f"list<{inner}>"
    return _TAGS.get(kind)


def table_value_hash(table: pa.Table, key: Sequence[str]) -> str:
    """sha256 of TDS 4.5's bytes of `table`: rows by `key`, ties by the other columns."""
    columns = []
    for field in table.schema:
        tag = _tag(field.type)
        if tag is None:
            raise TypeError(f"{field.name}: {field.type} has no TDS type (TDS 3.2)")
        columns.append((field.name, tag))
    return hashlib.sha256(encode_table(table, columns, key)).hexdigest()
