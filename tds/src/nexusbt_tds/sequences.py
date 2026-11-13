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
from itertools import pairwise
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from .check import SEQUENCED, WITHIN, Finding
from .keys import _shown, listed
from .manifest import Manifest
from .refs import _rows

V032 = "TDS-V032"


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
    columns = ("sequence", "is_snapshot", *split)  # `is_snapshot` is read on book_deltas only
    for part in sorted(parts):
        groups: defaultdict[tuple[Any, ...], list[int]] = defaultdict(list)
        files = {**ds, "files": [{"path": rel} for rel in sorted(parts[part])]}
        for rel in parts[part]:  # a listed column a file lacks is S001's; its groups are unknown
            if not set(split) <= set(pq.read_schema(root / rel).names):
                raise ValueError(f"{rel} lacks a column of params.{WITHIN}")
        for number, snapshot, *split_by in _rows(root, files, columns):
            if number is not None and not (snapshots and snapshot):
                groups[tuple(split_by)].append(number)
        for group, numbers in sorted(groups.items(), key=lambda g: str(g[0])):
            steps = [(a, b) for a, b in pairwise(sorted(numbers)) if b - a > 1]
            if not steps:
                continue
            missing = sum(b - a - 1 for a, b in steps)
            msg = f"{missing} missing sequence number(s); first gap {steps[0][0]} -> {steps[0][1]}"
            shown = _shown(split, dict(zip(split, group, strict=True)))
            key = {**dict(part), **shown}  # the partition's values first (#432, 2026-11-13)
            out.append(Finding(V032, "warning", msg, name, key=key, count=missing))
    return out
