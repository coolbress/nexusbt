"""P-START and the metamorphic relations of spec 8.3 (INV-14, INV-15; T1.21, #255).

Each case runs `nx.run_pipeline` over 8 KR instruments of the synthetic `small` package
(spec 4.8) on a random graph of built-in terms (`_pipelines.build`, #254), and compares the
result table and `term_diagnostics` bit for bit. M1 has no targets, so the table stands for
the canonical targets 8.3 names (#255's Decisions, 2026-11-21; #43's M3a list).

These tests carry `slow` and run in `engine / property-deep`, as #254's do.
"""

from __future__ import annotations

import datetime as dt
import shutil
from fractions import Fraction
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pytest
from hypothesis import HealthCheck, assume, event, example, given, settings
from hypothesis import strategies as st

import nexusbt as nx
from nexusbt.data import Snapshot, decision_grid, every
from nexusbt.factors import SMA, Returns
from nexusbt.pipeline import Price, graph_hash
from nexusbt.pipeline._degree import ZERO, _walk
from nexusbt.pipeline._terms import describe_term
from nexusbt.testing.synth import make_snapshot
from property._pipelines import GRAPH, WINDOWS, bits, build, inside
from property._variants import (
    append_action,
    drop_instrument,
    neutral_split,
    rows_of,
    scale_prices,
)

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
def roots(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    """`small` and its late-bar variant (4.8 rule 3a, #354), 8 KR instruments: their folders,
    which the metamorphic tests copy before changing (`_variants`) and never change."""
    root = tmp_path_factory.mktemp("synth")
    small = make_snapshot(root / "small", preset="small", markets=("KR",), n_kr=8, degrade=())
    late = make_snapshot(root / "late_bars", preset="small", markets=("KR",), n_kr=8,
                         degrade=("late_bars",))  # fmt: skip
    return {"small": small, "late_bars": late}


@pytest.fixture(scope="module")
def packages(roots: dict[str, Path]) -> dict[str, Snapshot]:
    """The two packages of `roots`, opened."""
    return {"small": nx.open(str(roots["small"])), "late_bars": nx.open(str(roots["late_bars"]))}


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
    reads data. With `every(n, offset)` the runs are daily, so the later run's first session
    (the row a start-dependent read changes first) is compared too, and `decision_grid` gives
    the same sessions from both starts. A column `0 / 0` gives `DivisionByZero` counts on
    every row, so the counts are compared on rows that hold some."""
    snapshot = packages[package]
    pipe = nx.Pipeline({**build(graph).columns, "zero_by_zero": Returns(2) * 0.0 / 0.0})
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
        grids = [decision_grid(snapshot, every(n, offset % n), s, END).session_dates
                 for s in starts]  # fmt: skip
        for k, start, grid in zip(SHIFTS, starts[1:], grids[1:], strict=True):
            assert grid == tuple(d for d in grids[0] if d >= start), k
            assert on(since(tables[0], start), grid).num_rows > 0, k
    for k, start, table, later in zip(SHIFTS, starts[1:], tables[1:], found[1:], strict=True):
        assert table["session_date"][0].as_py() == start or schedule is None, k
        whole = since(tables[0], start)
        assert whole.num_rows > 0, k
        keys = [list(zip(*(t[c].to_pylist() for c in ("session_date", "instrument_id")),
                         strict=True)) for t in (whole, table)]  # fmt: skip
        assert keys[1] == keys[0], (k, sorted(set(keys[0]) ^ set(keys[1]))[:4])
        assert bits(table) == bits(whole), k
        counts = [since(r.term_diagnostics, start) for r in (found[0], later)]
        assert counts[0].num_rows > 0, k
        assert bits(counts[1]) == bits(counts[0]), k


FROM = dt.date(2015, 1, 5)
IDS = [f"KR:T{n:05d}" for n in range(1, 9)]
ONE = (Fraction(1), Fraction(0))  # #499's degree of a price level
#: M-SCALE's k: powers of two on both sides of 1, so k times x is exact and every relation is
#: compared bit for bit (#255's Decisions, 2026-11-21).
KS = (2.0**-3, 2.0, 2.0**10)
#: `build`'s steps whose terms #499's verdict gives a degree: spec 3.4 has no rule for
#: `nx.ops.rolling` (no degree, never refused), so its five picks are left out of M-SCALE's
#: graphs, as is `build`'s last column, a rolling mean (#255's Decisions, 2026-11-21).
DEGREED = st.lists(st.tuples(st.sampled_from(("returns", "sma", "shift", "mdd", "zero", "rank",
                                              "add")),
                             st.integers(0, 50), st.integers(0, 50), st.sampled_from(WINDOWS)),
                   min_size=2, max_size=7)  # fmt: skip
#: One step of a price-level part: `latest` or `sma` of a column (a window over a column, which
#: #499's refusal allows), a sum, half a term, or a ratio of two, which is degree 0.
LEVEL = st.lists(st.tuples(st.sampled_from(("latest", "sma", "add", "half", "ratio")),
                           st.sampled_from(("open", "high", "low", "close", "close_tr")),
                           st.integers(0, 50), st.integers(0, 50), st.sampled_from(WINDOWS)),
                 min_size=1, max_size=5)  # fmt: skip


def level(steps: list[tuple[str, str, int, int, int]]) -> list[Any]:
    """The terms of a price-level part, after `Price.close.latest`: ratios are kept apart, so
    each other term is degree 1 and a ratio of two of them degree 0."""
    terms: list[Any] = [Price.close.latest]
    ratios = []
    for kind, column, i, j, w in steps:
        x, y = terms[i % len(terms)], terms[j % len(terms)]
        match kind:
            case "latest":
                terms.append(getattr(Price, column).latest)
            case "sma":
                terms.append(SMA(w, inputs=[getattr(Price, column)]))
            case "add":
                terms.append(x + y)
            case "half":
                terms.append(x * 0.5)
            case _:
                ratios.append(x / y)
    return terms + ratios


def nodes(roots: list[Any]) -> list[Any]:
    """Every term of the graph once, the terms in its inputs and in its parameters (a mask)."""
    found, todo = {}, list(roots)
    while todo:
        if (t := todo.pop())._key not in found:
            found[t._key] = t
            todo += [i for i in (*t.inputs, *(v for _, v in t.params)) if hasattr(i, "_key")]
    return list(found.values())


def scaled_run(root: Path, tmp: Path, project: Path, pipe: nx.Pipeline, instrument: str,
               k: float) -> tuple[Any, Any]:  # fmt: skip
    """The run on the package at `root` and on its copy with `instrument`'s prices times k."""
    at = shutil.copytree(root, tmp / "scaled")
    scale_prices(at, instrument, k)
    with inside(project):
        return run(pipe, nx.open(str(root)), FROM, "monthly"), run(
            pipe, nx.open(str(at)), FROM, "monthly"
        )


def times(table: pa.Table, columns: list[str], instrument: str, k: float) -> pa.Table:
    """`table` with each of `columns` times k on `instrument`'s rows."""
    hit = pc.equal(table["instrument_id"], instrument)
    for name in columns:
        at, old = table.schema.get_field_index(name), table[name]
        new = pc.if_else(hit, pc.multiply(old, pa.scalar(k, pa.float64())), old)
        table = table.set_column(at, table.schema.field(at), new)
    return table


@CASES
@given(graph=DEGREED, prices=LEVEL, instrument=st.sampled_from(IDS), k=st.sampled_from(KS))
def test_M_SCALE(  # noqa: N802 - spec 10.1's name
    graph: list[Any], prices: list[Any], instrument: str, k: float, roots: dict[str, Path],
    project: Path, tmp_path_factory: pytest.TempPathFactory,
) -> None:  # fmt: skip
    """INV-15, M-SCALE: with one instrument's raw prices times k and its volume times 1/k, a
    degree-0 column is the same, bit for bit, a degree-1 column is k times as much on that
    instrument's rows and the same on the others', and the rows the screen keeps (a top-6 of
    a degree-0 term) are the same. The precondition is read from #499's verdict: every column
    is of degree 0 or (1, 0) and every rank, `top` and `zscore` reads a degree-0 term.
    `Price.close_unadjusted` is a fixed column of verdict 0 (the adjustment basis of a row)
    that M-SCALE multiplies by k: the two notions part on it (#255's Decisions, 2026-11-18)."""
    returns = dict(list(build(graph).columns.items())[:-1])  # without the rolling last column
    columns = {**returns, **{f"p{n}": t for n, t in enumerate(level(prices))},
               "unadjusted": Price.close_unadjusted.latest}  # fmt: skip
    screen = Returns(5).top(6)
    degree = _walk([*columns.values(), screen], refuse=False)
    assert all(degree[t._key] in (ZERO, ONE) for t in columns.values())
    assert all(degree[t.inputs[0]._key] == ZERO for t in nodes([*columns.values(), screen])
               if t.op in ("rank", "top", "zscore"))  # fmt: skip
    assert degree[columns["unadjusted"]._key] == ZERO
    ones = [n for n, t in columns.items() if degree[t._key] == ONE or n == "unadjusted"]
    event(f"k = {k}, {len(ones)} of {len(columns)} columns degree 1")
    pipe = nx.Pipeline(columns, screen=screen)
    tmp = tmp_path_factory.mktemp("scale")
    try:
        whole, scaled = scaled_run(roots["small"], tmp, project, pipe, instrument, k)
    finally:
        shutil.rmtree(tmp)
    assert pc.sum(pc.equal(whole.table["instrument_id"], instrument)).as_py() > 0
    assert bits(scaled.table) == bits(times(whole.table, ones, instrument, k))
    assert bits(scaled.term_diagnostics) == bits(whole.term_diagnostics)


@settings(max_examples=3, suppress_health_check=[HealthCheck.too_slow])
@given(instrument=st.sampled_from(IDS))
def test_M_SCALE_counterexample_threshold(  # noqa: N802 - spec 10.1's name
    instrument: str, roots: dict[str, Path], project: Path,
    tmp_path_factory: pytest.TempPathFactory,
) -> None:  # fmt: skip
    """8.3's counterexample, the threshold `close > X`: with the instrument's prices doubled, X
    its median close at the decisions, the threshold flips on exactly its cells with
    X/2 < close <= X, and on no other instrument's; `Returns(5)` is the same throughout."""
    close = Price.close.latest
    with inside(project):
        first = run(nx.Pipeline({"close": close}), nx.open(str(roots["small"])), FROM, "monthly")
    mine = first.table.filter(pc.equal(first.table["instrument_id"], instrument))
    assert len(mine) > 0, instrument  # else nothing could flip and the test would see nothing
    x = float(np.nanmedian(mine["close"].to_numpy(zero_copy_only=False)))
    pipe = nx.Pipeline({"close": close, "above": close > x, "returns": Returns(5)})
    tmp = tmp_path_factory.mktemp("threshold")
    try:
        whole, scaled = scaled_run(roots["small"], tmp, project, pipe, instrument, 2.0)
    finally:
        shutil.rmtree(tmp)
    old, new = whole.table, scaled.table
    assert old["instrument_id"].to_pylist() == new["instrument_id"].to_pylist()
    ids, before = old["instrument_id"].to_pylist(), old["close"].to_pylist()
    flipped = [n for n, (a, b) in enumerate(zip(old["above"].to_pylist(), new["above"].to_pylist(),
                                                strict=True)) if a != b]  # fmt: skip
    expected = [n for n, (i, c) in enumerate(zip(ids, before, strict=True))
                if i == instrument and c is not None and x / 2 < c <= x]  # fmt: skip
    event(f"{instrument}: the threshold flipped on {len(flipped)} of {len(mine)} cells")
    assert flipped == expected
    assert len(flipped) >= FLIPS * len(mine)
    assert bits(new.select(["returns"])) == bits(old.select(["returns"]))


#: The least share of the instrument's cells the threshold must flip: measured 2026-11-21 on
#: `small`'s 8 KR instruments, 0.49 to 0.57 (1 of 1 on KR:T00006). The set equality above
#: catches an engine that flips other cells; this catches data or an X under which the
#: counterexample breaks the relation on few cells or none (#255).
FLIPS = 0.45


@CASES
@given(graph=GRAPH, instrument=st.sampled_from(IDS), pick=st.integers(0, 10**6))
def test_M_SPLIT_NEUTRAL(  # noqa: N802 - spec 10.1's name
    graph: list[Any], instrument: str, pick: int, roots: dict[str, Path], project: Path,
    tmp_path_factory: pytest.TempPathFactory,
) -> None:  # fmt: skip
    """INV-15, M-SPLIT-NEUTRAL: a fake split of ratio 1.0 added on a session the instrument
    trades and has no other event leaves the table and `term_diagnostics` the same, bit for
    bit (8.3 has no precondition for it)."""
    root = roots["small"]
    events = {r["ex_date"] for r in rows_of(root, "corporate_actions")
              if r["instrument_id"] == instrument}  # fmt: skip
    traded = [r["session_date"] for r in rows_of(root, "bars_1d")
              if r["instrument_id"] == instrument and r["obs_status"] == "traded"]  # fmt: skip
    days = [d for d in traded[1:] if d not in events and d > FROM]
    ex_date = days[pick % len(days)]
    event(f"{instrument}, ex-date in {ex_date.year}")
    at = shutil.copytree(root, tmp_path_factory.mktemp("split") / "pkg")
    try:
        append_action(at, neutral_split(at, instrument, ex_date))
        pipe = build(graph)
        with inside(project):
            whole = run(pipe, nx.open(str(root)), FROM, "monthly")
            split = run(pipe, nx.open(str(at)), FROM, "monthly")
    finally:
        shutil.rmtree(at.parent)
    assert bits(split.table) == bits(whole.table)
    assert bits(split.term_diagnostics) == bits(whole.term_diagnostics)


#: Written here, not shared, as `roots` above (#630 39): 9 KR instruments, so one is deleted.
@pytest.fixture(scope="module")
def nine(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return make_snapshot(tmp_path_factory.mktemp("synth") / "nine", preset="small",
                         markets=("KR",), n_kr=9, degrade=())  # fmt: skip


CROSS = ("rank", "zscore", "demean", "winsorize", "pct_rank", "top", "bottom",
         "percentile_between", "quantiles")  # fmt: skip


def dummy(root: Path, project: Path, pick: int) -> tuple[str, Any, pa.Table]:
    """M-DUMMY's added instrument, its universe and its `Returns(5)` at the decisions: one of the
    instruments with at least the median number of decisions (counted from the package, at
    least 3 of them), drawn by `pick`; the universe `close_unadjusted > X`, X its highest raw
    close at any session, so it enters the universe at no row a term is computed at, the rows
    a window reads before a decision included (#255's Decisions, 2026-11-21)."""
    close = Price.close_unadjusted.latest
    with inside(project):
        seen = run(nx.Pipeline({"close": close, "r": Returns(5)}), nx.open(str(root)), FROM,
                   "monthly").table  # fmt: skip
    seen = seen.filter(pc.is_finite(seen["close"]))
    counts = dict(zip(*pc.value_counts(seen["instrument_id"]).flatten(), strict=True))
    long = sorted(i.as_py() for i, n in counts.items() if n.as_py() >= np.median(
        [n.as_py() for n in counts.values()]))  # fmt: skip
    assert len(long) >= 3, long
    name = long[pick % len(long)]
    mine = seen.filter(pc.equal(seen["instrument_id"], name))
    bars = [r["close"] for r in rows_of(root, "bars_1d") if r["instrument_id"] == name]
    return name, close > max(c for c in bars if c is not None), mine


def without(root: Path, tmp: Path, project: Path, pipe: nx.Pipeline, name: str) -> tuple[Any, Any]:
    """The run on the package at `root`, and on its copy with `name` deleted."""
    at = shutil.copytree(root, tmp / "without")
    drop_instrument(at, name)
    with inside(project):
        return run(pipe, nx.open(str(root)), FROM, "monthly"), run(
            pipe, nx.open(str(at)), FROM, "monthly"
        )


def label(term: Any) -> str:
    """How `term_diagnostics` names a term (5.4.1, until T2.11)."""
    return f"{describe_term(term).splitlines()[0]} {graph_hash(term)[:12]}"


@CASES
@given(graph=GRAPH, pick=st.integers(0, 10**6))
# a rank under a 21-row window: computed at rows before a decision too (the review of #255's
# last pull request; with X from the decisions alone KR:T00005 entered the rank's mask there)
@example(graph=[("rank", 0, 0, 2), ("sma", 1, 0, 21)], pick=2)
def test_M_DUMMY(  # noqa: N802 - spec 10.1's name
    graph: list[Any], pick: int, nine: Path, project: Path,
    tmp_path_factory: pytest.TempPathFactory,
) -> None:  # fmt: skip
    """INV-15, M-DUMMY: an instrument that enters the universe at no decision, outside every
    cross-section's mask, leaves the result table the same, every column and row bit for bit.
    `term_diagnostics` counts every listed cell (5.4.1), so the owner's rule of 2026-11-21: per
    (market, session, term, diagnostic), the count with the instrument is the count without
    it or one more (its own cell); no count exists only without it; the counts of another
    market, and of every cross-section masked by the universe, are the same."""
    name, universe, _ = dummy(nine, project, pick)
    event(f"{name} added")
    # a random graph may hold no rank: two fixed masked cross-sections are in every case
    columns = {**build(graph, mask=universe).columns, "zero_by_zero": Returns(2) * 0.0 / 0.0,
               "rank": Returns(5).rank(mask=universe),
               "zscore": Returns(5).zscore(mask=universe)}  # fmt: skip
    pipe = nx.Pipeline(columns, screen=universe)
    cross = [t for t in nodes([*columns.values()]) if t.op in CROSS]
    assert all(dict(t.params).get("mask") is universe for t in cross)  # the precondition
    tmp = tmp_path_factory.mktemp("dummy")
    try:
        whole, less = without(nine, tmp, project, pipe, name)
    finally:
        shutil.rmtree(tmp)
    assume(whole.table.num_rows > 0)  # a universe that holds no one compares nothing
    assert name not in whole.table["instrument_id"].to_pylist()
    assert bits(less.table) == bits(whole.table)
    keys = ("market", "session_date", "term", "diagnostic")
    counts = [{tuple(r[k] for k in keys): r["n"] for r in t.term_diagnostics.to_pylist()}
              for t in (whole, less)]  # fmt: skip
    assert counts[1].keys() <= counts[0].keys()
    added = {k: n - counts[1].get(k, 0) for k, n in counts[0].items()}
    assert set(added.values()) <= {0, 1}
    assert all(added[k] == 0 for k in added if k[0] != name.split(":")[0])
    masked = {label(t) for t in cross}
    assert all(added[k] == 0 for k in added if k[2] in masked)
    event(f"{sum(added.values())} counts one more, of {len(added)}")
    event(f"{sum(k[2] in masked for k in added)} counts at a masked cross-section")


@settings(max_examples=3, suppress_health_check=[HealthCheck.too_slow])
@given(pick=st.integers(0, 10**6))
def test_M_DUMMY_counterexample_unmasked(  # noqa: N802 - spec 10.1's name
    pick: int, nine: Path, project: Path, tmp_path_factory: pytest.TempPathFactory
) -> None:
    """8.3's counterexample, a universe on top of a `zscore` without a mask: with the added
    instrument in the zscore's cross-section, a cell of it changes only at a decision where
    that instrument's `Returns(5)` is finite (it then moves the mean), and nearly every such
    cell does; the same zscore masked by the universe is the same, bit for bit."""
    name, universe, mine = dummy(nine, project, pick)
    finite = set(mine.filter(pc.is_finite(mine["r"]))["session_date"].to_pylist())
    columns = {"z": Returns(5).zscore(), "masked": Returns(5).zscore(mask=universe)}
    tmp = tmp_path_factory.mktemp("unmasked")
    try:
        whole, less = without(nine, tmp, project, nx.Pipeline(columns, screen=universe), name)
    finally:
        shutil.rmtree(tmp)
    old, new = whole.table, less.table
    assume(old.num_rows > 0)  # a universe that holds no one (KR:T00008's X) compares nothing
    assert old.select(["session_date", "instrument_id"]) == new.select(
        ["session_date", "instrument_id"]
    )
    days, z = old["session_date"].to_pylist(), old["z"].to_pylist()
    a, b = old["z"].to_numpy(zero_copy_only=False), new["z"].to_numpy(zero_copy_only=False)
    changed = {n for n in range(len(z)) if a[n].tobytes() != b[n].tobytes()}
    expected = {n for n in range(len(z)) if days[n] in finite and np.isfinite(z[n])}
    event(f"{name}: z changed on {len(changed)} of {len(expected)} cells it can change")
    assert changed <= expected
    # KR:T00009's Returns(5) is finite at no decision the universe holds anyone: nothing to show
    assume(expected)
    assert len(changed) >= MOVED * len(expected)
    assert bits(new.select(["masked"])) == bits(old.select(["masked"]))


#: The least share of the cells the unmasked zscore must change: measured 2026-11-21 on the
#: instruments `dummy` draws from, all of them (KR:T00001 22 of 22, KR:T00003 161 of 161,
#: KR:T00005 15 of 15; KR:T00008 and KR:T00009 assumed away above). A cell whose mean and std
#: moved together to the same z would fail it; none did (#255).
MOVED = 1.0
