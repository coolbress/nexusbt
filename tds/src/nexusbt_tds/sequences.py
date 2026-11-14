"""TDS-V032 (TDS 5.6~5.8): gaps in `sequence` where the vendor promised consecutive numbers.

The rules are #348's `## Decision` (2026-11-13). A `trades`, `quotes` or `book_deltas` dataset
declares the promise with `params.sequence_consecutive_within`, a list of column names; with no
declaration there is nothing to judge, and the key on any other kind is ignored. A group is a
partition (`venue`, `date`) split further by the listed columns. Within a group the numbers are
sorted: a difference of 0 between neighbours is rows of one message, a difference above 1 is a
gap; the first number may be anything, and duplicate keys are the K codes'. `book_deltas` rows
with `is_snapshot = true` are left out. One warning line per group with a gap. A file the code
cannot read, or a column of the wrong type, leaves V032 unchecked.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from .check import SEQUENCE_CODES, SEQUENCED, WITHIN, Finding
from .keys import _shown, listed
from .manifest import Manifest

(V032,) = SEQUENCE_CODES


def check_sequences(m: Manifest, only: Sequence[str] | None, blind: set[str]) -> list[Finding]:
    """V032 on the checked datasets that declare `params.sequence_consecutive_within`."""
    out: list[Finding] = []
    for ds in m.datasets:
        params = ds.get("params")
        within = params.get(WITHIN) if isinstance(params, dict) else None
        name = str(ds.get("name"))
        if ds.get("kind") not in SEQUENCED or not isinstance(within, list):
            continue  # no promise, or not one of the three kinds: nothing to judge
        if only is not None and name not in only:
            continue
        try:
            out += _dataset(m, ds, [str(c) for c in within])
        except (OSError, pa.ArrowException, TypeError, ValueError):
            blind.add(V032)  # unreadable, or a column of the wrong type: its rows are not judged
    return out


def _dataset(m: Manifest, ds: Mapping[str, Any], within: list[str]) -> list[Finding]:
    root, name, out = m.root.resolve(), str(ds.get("name")), []
    parts: defaultdict[tuple[tuple[str, str], ...], list[str]] = defaultdict(list)
    for rel, values in listed(root, ds):
        parts[tuple(values.items())].append(rel)
    snapshots = ds.get("kind") == "book_deltas"
    split = [c for c in within if c not in dict(next(iter(parts), ()))]  # partition: already one
    for part in sorted(parts):  # one partition in memory at a time (#432 Decisions (3))
        files = [_read(root, rel, split, snapshots) for rel in sorted(parts[part])]
        table = pa.concat_tables(files, promote_options="permissive")  # int widths, nullability
        del files
        if split:
            lists = table.group_by(split, use_threads=False).aggregate([("sequence", "list")])
            groups = [(tuple(r[c] for c in split), lists["sequence_list"][n].values)
                      for n, r in enumerate(lists.select(split).to_pylist())]  # fmt: skip
        else:
            groups = [((), table["sequence"].combine_chunks())]
        del table
        for group, numbers in sorted(groups, key=lambda g: str(g[0])):
            if (gap := _gaps(numbers)) is None:
                continue
            missing, before, after = gap
            msg = f"{missing} missing sequence number(s); first gap {before} -> {after}"
            shown = _shown(split, dict(zip(split, group, strict=True)))
            key = {**dict(part), **shown}  # the partition's values first (#432, 2026-11-13)
            out.append(Finding(V032, "warning", msg, name, key=key, count=missing))
    return out


def _read(root: Path, rel: str, split: list[str], snapshots: bool) -> pa.Table:
    """One file's `sequence` (int64, no null) and `split` columns, without `book_deltas`
    snapshot rows."""
    names = pq.read_schema(root / rel).names
    if len(set(names)) < len(names) or not set(split) <= set(names):  # S001's: groups unknown
        raise ValueError(f"{rel}: a column name twice, or a column of params.{WITHIN} missing")
    flag = ["is_snapshot"] if snapshots and "is_snapshot" in names else []
    table = pq.read_table(root / rel, columns=["sequence", *split, *flag])
    if not pa.types.is_integer(table.schema.field("sequence").type):
        raise TypeError(f"{rel}: sequence is {table.schema.field('sequence').type}")
    keep = pc.is_valid(table["sequence"])
    if flag:
        keep = pc.and_(keep, pc.invert(pc.fill_null(table["is_snapshot"], False)))
    table = table.filter(keep).select(["sequence", *split])
    for n, field in enumerate(table.schema):  # a dictionary column groups by its values
        if pa.types.is_dictionary(field.type):
            table = table.set_column(n, field.name, table[n].cast(field.type.value_type))
    return table.set_column(0, "sequence", table["sequence"].cast(pa.int64()))


def _gaps(numbers: pa.Array) -> tuple[int, int, int] | None:
    """(missing count, number before, number after the first gap) of one group, or None; the
    sort and the neighbour differences run in Arrow's C code, 8 bytes a number."""
    ordered = numbers.take(pc.sort_indices(numbers))
    if len(ordered) > 1:  # a span past int64 raises (unchecked), never wraps into a pass
        pc.subtract_checked(ordered[-1], ordered[0])
    steps = pc.subtract(ordered.slice(1), ordered.slice(0, max(len(ordered) - 1, 0)))
    over = pc.greater(steps, 1)
    if not pc.any(over).as_py():
        return None
    first = pc.index(over, True).as_py()
    missing = pc.sum(pc.subtract(steps.filter(over), 1)).as_py()
    return missing, ordered[first].as_py(), ordered[first + 1].as_py()
