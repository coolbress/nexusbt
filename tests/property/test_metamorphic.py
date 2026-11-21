"""P-START and the metamorphic relations of spec 8.3 (INV-14, INV-15; T1.21, #255).

Each case runs `nx.run_pipeline` over 8 KR instruments of the synthetic `small` package
(spec 4.8) on a random graph of built-in terms (`_pipelines.build`, #254), and compares the
result table and `term_diagnostics` bit for bit. M1 has no targets, so the table stands for
the canonical targets 8.3 names (#255's Decisions, 2026-11-21; #43's M3a list).

These tests carry `slow` and run in `engine / property-deep`, as #254's do.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pytest
from hypothesis import HealthCheck, event, example, given, settings
from hypothesis import strategies as st

import nexusbt as nx
from nexusbt.data import Snapshot, decision_grid, every
from nexusbt.testing.synth import make_snapshot
from property._pipelines import GRAPH, bits, build, inside

pytestmark = [pytest.mark.property, pytest.mark.slow]

END = "2019-12-30"
CASES = settings(max_examples=5, suppress_health_check=[HealthCheck.too_slow])
#: 8.3's shifts of the start, in sessions.
SHIFTS = (1, 21, 252)
#: `every(n)`'s n: none divides a shift, so a schedule counted from the run's first session
#: instead of the absolute `session_ord` (3.7) would decide on other sessions.
EVERY = (5, 10, 13)
#: A fixed graph that reads 64 rows back (three chained 21-row windows), as #254's `DEEP`.
DEEP = [("mdd", 0, 0, 21), ("mdd", 1, 0, 21), ("mdd", 2, 0, 21)]


@pytest.fixture(scope="module")
def project(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A project folder with its `nexusbt.toml`; pins in the index only (no data root)."""
    folder = tmp_path_factory.mktemp("project")
    (folder / "nexusbt.toml").write_text('[data]\npins = "index"\n', encoding="utf-8")
    return folder


#: Written here, as in `test_pipeline_invariants.py`, not shared: `test_fixtures_are_synthetic`
#: traces a snapshot's path inside one module (#599, #630 39).
@pytest.fixture(scope="module")
def packages(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Snapshot]:
    """`small` and its late-bar variant (4.8 rule 3a, #354), 8 KR instruments, opened."""
    root = tmp_path_factory.mktemp("synth")
    small = make_snapshot(root / "small", preset="small", markets=("KR",), n_kr=8, degrade=())
    late = make_snapshot(root / "late_bars", preset="small", markets=("KR",), n_kr=8,
                         degrade=("late_bars",))  # fmt: skip
    return {"small": nx.open(str(small)), "late_bars": nx.open(str(late))}


def run(
    pipe: nx.Pipeline, snapshot: Snapshot, start: dt.date, freq: Literal["daily", "monthly"]
) -> Any:
    return nx.run_pipeline(pipe, start=start, end=END, freq=freq, snapshot=snapshot)


def since(table: pa.Table, day: dt.date) -> pa.Table:
    return table.filter(pc.greater_equal(table["session_date"], pa.scalar(day, pa.date32())))


def on(table: pa.Table, days: tuple[dt.date, ...]) -> pa.Table:
    return table.filter(pc.is_in(table["session_date"], value_set=pa.array(days, pa.date32())))


@CASES
@given(graph=GRAPH, package=st.sampled_from(["small", "late_bars"]), first=st.integers(0, 250),
       schedule=st.none() | st.tuples(st.sampled_from(EVERY), st.integers(0, 12)))  # fmt: skip
@example(graph=DEEP, package="small", first=0, schedule=None)
@example(graph=DEEP, package="late_bars", first=0, schedule=None)
@example(graph=DEEP, package="small", first=3, schedule=(5, 2))
@example(graph=DEEP, package="late_bars", first=3, schedule=(13, 7))
def test_P_START(  # noqa: N802 - spec 10.1's name
    graph: list[Any], package: str, first: int, schedule: tuple[int, int] | None,
    packages: dict[str, Snapshot], project: Path,
) -> None:  # fmt: skip
    """INV-14: a run started 1, 21 or 252 sessions later gives, on every decision both runs
    have, the same table rows and the same `term_diagnostics` rows, bit for bit, on `small` and
    on `late_bars`. The first start is drawn from 2016's first 251 sessions, so every window
    reads data. With `every(n, offset)` the runs are daily and keep the sessions
    `decision_grid` gives from each run's own start, so the decisions are compared as well."""
    snapshot, pipe = packages[package], build(graph)
    event(f"{package}, {'monthly' if schedule is None else 'every(n)'}")
    dates = snapshot.calendar("KR").dates
    base = int(np.searchsorted(dates, np.datetime64("2016-01-04"))) + first
    starts = [dates[base + k].astype(dt.date) for k in (0, *SHIFTS)]
    with inside(project):
        found = [run(pipe, snapshot, s, "monthly" if schedule is None else "daily") for s in starts]
    tables = [r.table for r in found]
    if schedule is not None:
        n, offset = schedule
        assert all(k % n for k in SHIFTS)
        grids = [decision_grid(snapshot, every(n, offset % n), s, END) for s in starts]
        tables = [on(t, g.session_dates) for t, g in zip(tables, grids, strict=True)]
    for k, start, table, later in zip(SHIFTS, starts[1:], tables[1:], found[1:], strict=True):
        whole = since(tables[0], start)
        assert whole.num_rows > 0, k
        keys = [list(zip(*(t[c].to_pylist() for c in ("session_date", "instrument_id")),
                         strict=True)) for t in (whole, table)]  # fmt: skip
        assert keys[1] == keys[0], (k, sorted(set(keys[0]) ^ set(keys[1]))[:4])
        assert bits(table) == bits(whole), k
        counts = [since(r.term_diagnostics, start) for r in (found[0], later)]
        assert bits(counts[1]) == bits(counts[0]), k
