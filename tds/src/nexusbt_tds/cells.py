"""The `full` level's S006, S007 and S009 from the rows (TDS 8.1, 8.3; #391).

The `schema` level sees an enum column's minimum and maximum and a float column's ±Inf in the
statistics; the rows hold every value, NaN included. S006: a value outside a closed enum
(error); S007: outside an open enum and not in `dictionary/codes` (warning); S009: NaN or ±Inf
in an `f64` column (error). One finding per file and value (S006, S007) or per file and column
(S009, with the count). A null is no value. A column of the wrong type is S002's and is not
read; a partition column is S008's. A file Parquet cannot read leaves the three unchecked.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from .check import (
    _IS,
    _VERSION,
    CELL_CODES,
    DICTIONARIES,
    SUPPORTED_MAJOR,
    Finding,
    _dictionary_codes,
    _listed,
)
from .keys import listed
from .manifest import Manifest

S006, S007, S009 = CELL_CODES
BATCH_ROWS = 65_536


def check_cells(m: Manifest, only: Sequence[str] | None, blind: set[str]) -> list[Finding]:
    """S006, S007 and S009 of the checked datasets; a kind with no schema file leaves them
    unchecked, as at the `schema` level. The rows replace what the footers could not see."""
    blind.difference_update(CELL_CODES)  # the causes the rows share are added again below
    try:
        return _check(m, only, blind)
    except (OSError, pa.ArrowException):  # a file Parquet cannot read: S010's, its rows unseen
        blind.update(CELL_CODES)
        return []


def _check(m: Manifest, only: Sequence[str] | None, blind: set[str]) -> list[Finding]:
    from .hash import resolved_columns
    from .schemas.verify import load_schemas

    schemas, root, out = load_schemas(), m.root.resolve(), []
    codes = _dictionary_codes(m, root)
    for ds in m.datasets:
        schema = schemas.get(str(ds.get("kind")))
        version = _VERSION.fullmatch(str(ds.get("schema_version")))
        if only is not None and ds.get("name") not in only:
            continue
        if schema is None and ds.get("kind") not in DICTIONARIES:
            blind.update(CELL_CODES)  # `x_custom`: which column is an enum or a float, unknown
        if schema is None or not version or int(version[1]) != SUPPORTED_MAJOR:  # M009
            continue
        columns = resolved_columns(ds, schema.columns)
        for rel, _ in listed(root, ds):
            found = _check_file(root / rel, columns, codes)
            out += [replace(f, dataset=ds.get("name"), file=rel) for f in found]
    return out


def _check_file(path: Path, columns: Sequence[Any], codes: set[tuple[str, str]]) -> list[Finding]:
    """The findings of one file, in column order; no dataset or file named yet."""
    arrow = pq.read_schema(path)
    kinds = dict(zip(arrow.names, arrow.types, strict=True))  # a name twice: Arrow refuses it
    enums = [c for c in columns if c.values is not None and c.name in kinds
             and _IS["code"](kinds[c.name])]  # fmt: skip
    seen: dict[str, set[str]] = {c.name: set() for c in enums}
    bad = {c.name: 0 for c in columns if c.type == "f64" and c.name in kinds
           and pa.types.is_float64(kinds[c.name])}  # fmt: skip
    if not seen and not bad:
        return []
    for batch in pq.ParquetFile(path).iter_batches(BATCH_ROWS, columns=[*seen, *bad]):
        for name in seen:
            seen[name].update(pc.unique(_plain(batch.column(name))).drop_null().to_pylist())
        for name in bad:
            column = batch.column(name)
            bad[name] += pc.sum(pc.or_(pc.is_nan(column), pc.is_inf(column))).as_py() or 0
    out = []
    for column in enums:
        code, closed = (S006, True) if column.enum == "closed" else (S007, False)
        for value in sorted(seen[column.name]):
            if not _listed(value, column.values) and (closed or (column.name, value) not in codes):
                msg = f"{column.name} holds {value!r}, not in its {column.enum} list"
                out.append(Finding(code, "error" if closed else "warning", msg))
    out += [Finding(S009, "error", f"{name} holds NaN or ±Inf", count=n)
            for name, n in bad.items() if n]  # fmt: skip
    return out


def _plain(column: pa.Array) -> pa.Array:
    """A dictionary-encoded column as its values (TDS 3.7)."""
    return column.dictionary_decode() if pa.types.is_dictionary(column.type) else column
