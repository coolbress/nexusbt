"""The random pipelines of the property tests and how they are compared (spec 8.3; #254, #255).

Shared by `test_pipeline_invariants.py` and `test_metamorphic.py`. Only helpers that open no
snapshot live here: spec 2.7's `test_fixtures_are_synthetic` traces a snapshot's path inside
one module, so the fixtures that call `make_snapshot` and the `run()` that passes `snapshot=`
stay in each test module (#599; #630 item 39).
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow as pa
import pytest
from hypothesis import strategies as st

import nexusbt as nx
from nexusbt import ops
from nexusbt.factors import SMA, MaxDrawdown, Returns

WINDOWS = (2, 3, 5, 10, 21)
KINDS = ("returns", "sma", "shift", "min", "max", "median", "mean", "std", "mdd", "zero",
         "rank", "add")  # fmt: skip
#: One step adds a term made from the terms so far (indices taken modulo their number).
STEP = st.tuples(st.sampled_from(KINDS), st.integers(0, 50), st.integers(0, 50),
                 st.sampled_from(WINDOWS))  # fmt: skip
GRAPH = st.lists(STEP, min_size=2, max_size=7)


def term(kind: str, x: Any, y: Any, w: int, mask: Any = None) -> Any:
    """One step's term from the terms `x` and `y` and the window or shift `w`; a rank takes
    `mask` (None: the term `x.rank()` is, with the same hash)."""
    match kind:
        case "returns":
            return Returns(w)
        case "sma":
            return SMA(w, inputs=[x])
        case "shift":
            return x.shift(w)
        case "mdd":
            return MaxDrawdown(w, inputs=[x])
        case "zero":
            return x * 0.0
        case "rank":
            return x.rank(mask=mask)
        case "add":
            return x + y
    return getattr(ops.rolling(x, w), kind)()  # min, max, median, mean, std


def reach(steps: Sequence[tuple[str, int, int, int]]) -> int:
    """How many rows before a row the terms of `build(steps)` read, at most, worked out here
    from the steps and 3.4's warm-up column: `W - 1` for `Returns`, `SMA`, `MaxDrawdown` and a
    rolling window, `k` for `shift(k)`, nothing for a rank or `* 0.0`, and a sum its further
    input. Not asked of the engine: an engine whose lookback came out short would lose a row
    and shorten the column that is there to see it (#683's Decisions, 2026-11-21)."""
    back = [4]  # the first `Returns(5)`
    for kind, i, j, w in steps:
        x, y = back[i % len(back)], back[j % len(back)]
        match kind:
            case "returns":
                back.append(w - 1)
            case "shift":
                back.append(x + w)
            case "zero" | "rank":
                back.append(x)
            case "add":
                back.append(max(x, y))
            case _:
                back.append(x + w - 1)
    return max(back)


def build(steps: Sequence[tuple[str, int, int, int]], mask: Any = None) -> nx.Pipeline:
    """The pipeline of every term the steps make, after a first `Returns(5)`, and a last
    column that needs every row it reads, as far back as the furthest read of the others
    (`reach`) and never less than 45: `Returns` reads both ends (3.4), `rolling` needs
    `min_periods` = window finite cells (3.3's default), `shift` the row it names. So a chunk
    that loses even the first row of its lookback changes a value (checked for `SIGNED_ZEROS`,
    #254, and `DEEP`, #683). Every rank takes `mask`."""
    terms: list[Any] = [Returns(5)]
    for kind, i, j, w in steps:
        terms.append(term(kind, terms[i % len(terms)], terms[j % len(terms)], w, mask))
    terms.append(ops.rolling(Returns(21), 21).mean().shift(max(5, reach(steps) - 40)))
    return nx.Pipeline({f"t{k}": t for k, t in enumerate(terms)})


@contextmanager
def inside(folder: Path, pairs: dict[tuple[Any, str], Any] | None = None) -> Iterator[None]:
    """Run in `folder` with each `(object, name)` of `pairs` set to its value, then undo both."""
    with pytest.MonkeyPatch.context() as mp:
        mp.chdir(folder)
        for (target, name), value in (pairs or {}).items():
            mp.setattr(target, name, value)
        yield


def bits(table: pa.Table) -> dict[str, Any]:
    """Each column's values as bytes, NaN where NaN with one payload (a payload is not a
    value), -0.0 kept apart from 0.0, and where its nulls are."""
    found = {}
    for name in table.column_names:
        column = table[name].combine_chunks()
        if pa.types.is_floating(column.type):
            values = column.to_numpy(zero_copy_only=False).astype(np.float64)
            values = np.where(np.isnan(values), np.nan, values)
            found[name] = (values.tobytes(), column.is_null().to_pylist())
        else:
            found[name] = column.to_pylist()
    return found
