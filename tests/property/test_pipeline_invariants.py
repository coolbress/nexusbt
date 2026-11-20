"""P-CHUNK, P-PERM and P-DET at the pipeline (spec 8.3; INV-03, INV-04, INV-09; T1.19, #254).

Each case builds a random graph of built-in terms (nested windows, `shift`, rolling picks,
`MaxDrawdown`, a cross-section rank, sums, and a term times 0.0, which is 0.0 or -0.0 by the
sign of the term) and runs `nx.run_pipeline` over 8 KR instruments of the synthetic `small`
package (spec 4.8), 2015 to 2019, monthly decisions, every term a column. Values are compared
bit for bit, -0.0 against 0.0 included; a NaN's payload is not a value.

These tests carry `slow` and run in `engine / property-deep`, 5 cases each plus the fixed
examples (#254's Decisions, 2026-11-20): one run is a few seconds.
"""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow as pa
import pytest
from hypothesis import HealthCheck, example, given, settings
from hypothesis import strategies as st

import nexusbt as nx
from nexusbt import ops
from nexusbt.compute import _chunks
from nexusbt.data import Snapshot
from nexusbt.factors import SMA, MaxDrawdown, Returns
from nexusbt.testing.synth import make_snapshot

pytestmark = [pytest.mark.property, pytest.mark.slow]

START, END = "2015-01-05", "2019-12-30"
WINDOWS = (2, 3, 5, 10, 21)
KINDS = ("returns", "sma", "shift", "min", "max", "median", "mean", "std", "mdd", "zero",
         "rank", "add")  # fmt: skip
#: One step adds a term made from the terms so far (indices taken modulo their number).
STEP = st.tuples(st.sampled_from(KINDS), st.integers(0, 50), st.integers(0, 50),
                 st.sampled_from(WINDOWS))  # fmt: skip
GRAPH = st.lists(STEP, min_size=2, max_size=7)
#: A fixed graph whose picking kernels (rolling min, max and median, `MaxDrawdown`) read
#: zeros of both signs: `Returns(2) * 0.0` is -0.0 where the return is negative (#254's
#: Decisions, 2026-11-20: whether x86 picks a zero's sign by a value's place in the array).
SIGNED_ZEROS = [("returns", 0, 0, 2), ("zero", 1, 0, 2), ("max", 2, 0, 5), ("min", 2, 0, 5),
                ("median", 2, 0, 5), ("mdd", 2, 0, 10), ("add", 2, 1, 2), ("mdd", 6, 0, 21),
                ("sma", 1, 0, 5), ("shift", 8, 0, 2)]  # fmt: skip
CASES = settings(max_examples=5, suppress_health_check=[HealthCheck.too_slow])


def term(kind: str, x: Any, y: Any, w: int) -> Any:
    """One step's term from the terms `x` and `y` and the window or shift `w`."""
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
            return x.rank()
        case "add":
            return x + y
    return getattr(ops.rolling(x, w), kind)()  # min, max, median, mean, std


def build(steps: Sequence[tuple[str, int, int, int]]) -> nx.Pipeline:
    """The pipeline of every term the steps make, after a first `Returns(5)`, and a last
    column that needs every row it reads, 45 back: `Returns` reads both ends (3.4), `rolling`
    needs `min_periods` = window finite cells (3.3's default), `shift` the row it names. When
    that is the graph's furthest read, a chunk that loses even the first row of its lookback
    changes a value (checked for `SIGNED_ZEROS`, #254)."""
    terms: list[Any] = [Returns(5)]
    for kind, i, j, w in steps:
        terms.append(term(kind, terms[i % len(terms)], terms[j % len(terms)], w))
    terms.append(ops.rolling(Returns(21), 21).mean().shift(5))
    return nx.Pipeline({f"t{k}": t for k, t in enumerate(terms)})


@pytest.fixture(scope="module")
def project(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A project folder with its `nexusbt.toml`; pins in the index only (no data root)."""
    folder = tmp_path_factory.mktemp("project")
    (folder / "nexusbt.toml").write_text('[data]\npins = "index"\n', encoding="utf-8")
    return folder


@pytest.fixture(scope="module")
def packages(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Snapshot]:
    """`small` and its late-bar variant (4.8 rule 3a, #354), 8 KR instruments."""
    root = tmp_path_factory.mktemp("synth")
    made = {name: make_snapshot(root / name, preset="small", markets=("KR",), n_kr=8,
                                degrade=degrade)
            for name, degrade in (("small", ()), ("late_bars", ("late_bars",)))}  # fmt: skip
    return {name: nx.open(str(path)) for name, path in made.items()}


@contextmanager
def inside(folder: Path, **patches: Any) -> Iterator[None]:
    """Run in `folder` with `patches` (`(object, name)` to value) set, then undo both."""
    with pytest.MonkeyPatch.context() as mp:
        mp.chdir(folder)
        for (target, name), value in patches.get("pairs", {}).items():
            mp.setattr(target, name, value)
        yield


def run(pipe: nx.Pipeline, snapshot: Snapshot, *, save: bool = False) -> Any:
    return nx.run_pipeline(pipe, start=START, end=END, freq="monthly", snapshot=snapshot,
                           save=save)  # fmt: skip


def bits(table: pa.Table) -> dict[str, Any]:
    """Each column's values as bytes, NaN where NaN with one payload (a payload is not a
    value), -0.0 kept apart from 0.0."""
    found = {}
    for name in table.column_names:
        column = table[name].combine_chunks()
        if pa.types.is_floating(column.type):
            values = column.to_numpy(zero_copy_only=False).astype(np.float64)
            values = np.where(np.isnan(values), np.nan, values)
            found[name] = (values.tobytes(), column.null_count)
        else:
            found[name] = column.to_pylist()
    return found


def spans_by(group: Callable[[Any], Any]) -> Callable[..., list[tuple[int, int]]]:
    """A stand-in for `_chunks.spans` that cuts the run's sessions where `group` changes."""

    def spans(dates: Any, *_: Any, **__: Any) -> list[tuple[int, int]]:
        keys = [group(d) for d in np.asarray(dates, dtype="datetime64[D]")]
        cuts = [k for k in range(1, len(keys)) if keys[k] != keys[k - 1]]
        return list(zip([0, *cuts], [c - 1 for c in cuts] + [len(keys) - 1], strict=True))

    return spans


def year(d: Any) -> int:
    return int(d.astype("datetime64[Y]").astype(int)) + 1970


CHUNKINGS = {
    "1 year": spans_by(year),
    "3 years": spans_by(lambda d: (year(d) - 2015) // 3),
    "a quarter": spans_by(lambda d: int(d.astype("datetime64[M]").astype(int)) // 3),
}


@CASES
@given(graph=GRAPH, package=st.sampled_from(["small", "late_bars"]))
@example(graph=SIGNED_ZEROS, package="small")
@example(graph=SIGNED_ZEROS, package="late_bars")
def test_P_CHUNK(  # noqa: N802 - spec 10.1's name
    graph: list[Any], package: str, packages: dict[str, Snapshot], project: Path
) -> None:
    """INV-03: every column bit for bit whether the run is one chunk or cut by years, three
    years or quarters (sub-year chunks, 10.0's M1 row), on `small` and on `late_bars`."""
    pipe = build(graph)
    with inside(project, pairs={(_chunks, "spans"): spans_by(lambda _: 0)}):
        whole = run(pipe, packages[package])
    for name, chunking in CHUNKINGS.items():
        with inside(project, pairs={(_chunks, "spans"): chunking}):
            cut = run(pipe, packages[package])
        assert bits(cut.table) == bits(whole.table), name
        assert bits(cut.term_diagnostics) == bits(whole.term_diagnostics), name


@CASES
@given(graph=GRAPH, seed=st.integers(0, 2**32 - 1))
@example(graph=SIGNED_ZEROS, seed=7)
def test_P_PERM(  # noqa: N802 - spec 10.1's name
    graph: list[Any], seed: int, packages: dict[str, Snapshot], project: Path
) -> None:
    """INV-04: every column bit for bit when each block's instrument columns come in a
    shuffled memory order."""
    pipe, snapshot = build(graph), packages["small"]
    read = Snapshot.market_block
    rng = np.random.default_rng(seed)

    def shuffled(self: Snapshot, *args: Any, **kwargs: Any) -> Any:
        block = read(self, *args, **kwargs)
        order = rng.permutation(len(block.instrument_ids))
        return dataclasses.replace(
            block, instrument_ids=tuple(block.instrument_ids[k] for k in order),
            values={f: v[:, order] for f, v in block.values.items()},
            exists=block.exists[:, order], obs_status=block.obs_status[:, order],
            ts_available=block.ts_available[:, order],
        )  # fmt: skip

    with inside(project):
        straight = run(pipe, snapshot)
    with inside(project, pairs={(Snapshot, "market_block"): shuffled}):
        moved = run(pipe, snapshot)
    assert bits(moved.table) == bits(straight.table)
    assert bits(moved.term_diagnostics) == bits(straight.term_diagnostics)


@CASES
@given(graph=GRAPH)
@example(graph=SIGNED_ZEROS)
def test_P_DET_pipeline(  # noqa: N802 - spec 10.1's name
    graph: list[Any], packages: dict[str, Snapshot], project: Path
) -> None:
    """INV-09: the same input twice gives output files with the same physical and value hashes
    (two runs in one process; two new processes are T1.27's)."""
    pipe = build(graph)
    with inside(project):
        ids = [run(pipe, packages["small"], save=True).run_id for _ in range(2)]
    outputs = [json.loads((project / "runs" / str(i) / "manifest.json").read_text())["outputs"]
               for i in ids]  # fmt: skip
    tables = ("pipeline.parquet", "term_diagnostics.parquet")
    assert [{t: o[t] for t in tables} for o in outputs] == [{t: outputs[0][t] for t in tables}] * 2
    assert all(o[t].keys() == {"physical_sha256", "value_sha256"} for o in outputs for t in tables)
    assert ids[0] != ids[1]  # two runs, not one read twice
