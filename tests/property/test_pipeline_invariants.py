"""P-CHUNK, P-PERM, P-FUT and P-DET at the pipeline (spec 8.3; INV-03, INV-04, INV-02, INV-09;
T1.19, #254).

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
import datetime as dt
import json
import shutil
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
import pytest
from hypothesis import HealthCheck, assume, example, given, settings
from hypothesis import strategies as st

import nexusbt as nx
from nexusbt import ops
from nexusbt.compute import _chunks
from nexusbt.data import Snapshot
from nexusbt.factors import SMA, MaxDrawdown, Returns
from nexusbt.testing.synth import make_snapshot
from property._future import cut_after

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
                ("sma", 1, 0, 5), ("shift", 8, 0, 2), ("mdd", 1, 0, 2)]  # fmt: skip
#: `MaxDrawdown` of an all-zero window is 0/0, NaN, whatever the zeros' signs; its last step,
#: `MaxDrawdown(2)` of `Returns(2)`, picks between two zero drawdowns (`(p - p) / p`, signed as
#: `p`) on a rising pair, so its output holds both 0.0 and -0.0 (81 and 49 of 203 rows on
#: `small`, 2026-11-20).
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
def roots(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    """`small` and its late-bar variant (4.8 rule 3a, #354), 8 KR instruments: their folders."""
    root = tmp_path_factory.mktemp("synth")
    small = make_snapshot(root / "small", preset="small", markets=("KR",), n_kr=8, degrade=())
    late = make_snapshot(root / "late_bars", preset="small", markets=("KR",), n_kr=8,
                         degrade=("late_bars",))  # fmt: skip
    return {"small": small, "late_bars": late}


@pytest.fixture(scope="module")
def packages(roots: dict[str, Path]) -> dict[str, Snapshot]:
    """The two packages of `roots`, opened."""
    return {"small": nx.open(str(roots["small"])), "late_bars": nx.open(str(roots["late_bars"]))}


@contextmanager
def inside(folder: Path, pairs: dict[tuple[Any, str], Any] | None = None) -> Iterator[None]:
    """Run in `folder` with each `(object, name)` of `pairs` set to its value, then undo both."""
    with pytest.MonkeyPatch.context() as mp:
        mp.chdir(folder)
        for (target, name), value in (pairs or {}).items():
            mp.setattr(target, name, value)
        yield


def run(pipe: nx.Pipeline, snapshot: Snapshot, *, save: bool = False) -> Any:
    return nx.run_pipeline(pipe, start=START, end=END, freq="monthly", snapshot=snapshot,
                           save=save)  # fmt: skip


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


#: τ drawn over the run (8.3's "random τ"), up to before the last session's close so that
#: every case cuts something (a τ at or after the package's end cuts nothing); one before
#: KR's first close, which the helper refuses, is assumed away.
TAU = st.datetimes(min_value=dt.datetime(2015, 1, 1), max_value=dt.datetime(2019, 12, 30),
                   timezones=st.just(dt.UTC))  # fmt: skip
#: Fixed τ, each checked in the test to show what it is chosen for, so that a change of the
#: generator fails its example rather than passing it (#254's Decisions, 2026-11-20).
#: "bar": a bar closed by τ and available after it (KR:T00005's of 2016-12-29) is cut, and the
#: December decision reads that session: an engine that read the bar at its close fails here.
#: "terms" and "version" check the cut only, not the engine: "terms", the cut keeps a dividend
#: known by τ whose amount comes after it (KR:E000002, 2017-09-22 and 2017-11-16), the same row
#: on both sides; "version", the cut deletes a later version of an event it keeps (the split
#: KR:E000015, ratio 5, amended to 7 at 2016-01-13 03:00), and every decision by τ comes
#: before its ex-date. These 8 KR instruments hold no version known after its ex-date (the
#: whole `small` holds one, in US). `LATE_EVENT` below bites with a whole event known after
#: its ex-date; a later version known that late is not tested here (#679).
CHOSEN = {"terms": dt.datetime(2017, 11, 1, 3, 0, tzinfo=dt.UTC),
          "version": dt.datetime(2016, 1, 13, 2, 0, tzinfo=dt.UTC),
          "bar": dt.datetime(2016, 12, 29, 6, 30, tzinfo=dt.UTC)}  # fmt: skip


def rows_of(root: Path, name: str) -> list[dict[str, Any]]:
    manifest = json.loads((root / "tds.json").read_text(encoding="utf-8"))
    (entry,) = (d for d in manifest["datasets"] if d["name"] == name)
    return [r for f in entry["files"] for r in pq.read_table(root / f["path"]).to_pylist()]


def shown(original: Path, cut: Path, tau: dt.datetime) -> set[str]:
    """Which of `CHOSEN`'s cases the cut at `tau` holds."""
    found = set()
    actions = rows_of(cut, "corporate_actions")
    if any(r["ts_terms_available"] is not None and r["ts_terms_available"] > tau for r in actions):
        found.add("terms")
    kept = {r["event_id"] for r in actions}
    if any(r["revision_of"] in kept and r["event_id"] not in kept
           for r in rows_of(original, "corporate_actions")):  # fmt: skip
        found.add("version")
    bars = {(r["instrument_id"], r["session_date"]) for r in rows_of(cut, "bars_1d")}
    if any(r["ts_end"] <= tau < r.get("ts_available", r["ts_end"])
           and (r["instrument_id"], r["session_date"]) not in bars
           for r in rows_of(original, "bars_1d")):  # fmt: skip
        found.add("bar")
    return found


def decided(table: pa.Table, tau: dt.datetime) -> pa.Table:
    """The rows of a pipeline table with `decision_ts <= tau`, in key order."""
    by = pc.less_equal(table["decision_ts"], pa.scalar(tau, table["decision_ts"].type))
    keys = ("market", "session_date", "instrument_id")
    return table.filter(by).sort_by([(k, "ascending") for k in keys])


def closed(diagnostics: pa.Table, root: Path, tau: dt.datetime) -> pa.Table:
    """The rows of `term_diagnostics` at sessions closed by `tau` (a session's decision is at
    its close), as 5.4.1 counts a cell at the session of the row that produced it."""
    manifest = json.loads((root / "tds.json").read_text(encoding="utf-8"))
    market = {about["calendar_id"]: m for m, about in manifest["markets"].items()}
    done = {(market[r["calendar_id"]], r["session_date"])
            for r in rows_of(root, "calendar_sessions")
            if r["calendar_id"] in market and r["ts_close"] <= tau}  # fmt: skip
    keys = zip(*(diagnostics[k].to_pylist() for k in ("market", "session_date")), strict=True)
    return diagnostics.filter(pa.array([key in done for key in keys], pa.bool_()))


@CASES
@given(graph=GRAPH, package=st.sampled_from(["small", "late_bars"]), tau=TAU, chosen=st.just(""))
@example(graph=SIGNED_ZEROS, package="small", tau=CHOSEN["terms"], chosen="terms")
@example(graph=SIGNED_ZEROS, package="small", tau=CHOSEN["version"], chosen="version")
@example(graph=SIGNED_ZEROS, package="late_bars", tau=CHOSEN["bar"], chosen="bar")
def test_P_FUT_pipeline(  # noqa: N802 - spec 10.1's name
    graph: list[Any], package: str, tau: dt.datetime, chosen: str, roots: dict[str, Path],
    packages: dict[str, Snapshot], project: Path, tmp_path_factory: pytest.TempPathFactory,
) -> None:  # fmt: skip
    """INV-02 in M1's terms (#254's Decisions, 2026-11-20: M1 has no targets or orders): on the
    package and on its copy with the data after τ deleted (`cut_after`, 8.3), the pipeline
    table's rows with `decision_ts <= τ` are the same rows, every column bit for bit, and so
    are `term_diagnostics`' rows at sessions closed by τ; on `small` and on `late_bars`."""
    at = shutil.copytree(roots[package], tmp_path_factory.mktemp("asof") / "pkg")
    try:
        try:
            cut_after(at, tau)
        except ValueError as refused:  # τ before the first close: no package as of then
            assume("first close" not in str(refused))
            raise
        if chosen:
            assert chosen in shown(roots[package], at, tau), chosen
        pipe = build(graph)
        with inside(project):
            whole, earlier = run(pipe, packages[package]), run(pipe, nx.open(str(at)))
        old, new = decided(whole.table, tau), decided(earlier.table, tau)
        assume(old.num_rows > 0)  # τ before the first decision compares nothing
        if chosen == "bar":  # a decision at τ itself reads the session of the bar cut
            assert tau in old["decision_ts"].to_pylist()
        keys =[list(zip(*(t[k].to_pylist() for k in ("market", "session_date", "instrument_id")),
                         strict=True)) for t in (old, new)]  # fmt: skip
        assert keys[1] == keys[0], sorted(set(keys[0]) ^ set(keys[1]))[:10]
        assert bits(new) == bits(old)
        assert bits(closed(earlier.term_diagnostics, at, tau)) == bits(
            closed(whole.term_diagnostics, at, tau)
        )
    finally:
        shutil.rmtree(at.parent)


#: A dividend first known after its ex-date, injected into `tiny` (4.8 `events`): the 8 KR
#: instruments above hold no event known that late (#254's Decisions, 2026-11-20).
#: τ lies between the ex-date and that instant, so the cut deletes the row, and the decision
#: of 2020-02-28 reads `Returns`' `Price.close_tr` across the ex-date.
LATE_EVENT = {"dataset": "corporate_actions", "instrument_id": "KR:T00001",
              "kind": "cash_dividend", "ex_date": "2020-02-25", "cash_per_share": 100.0,
              "ts_announced": "2020-03-05T06:30:00Z",
              "ts_terms_available": "2020-03-05T06:30:00Z"}  # fmt: skip
LATE_TAU = dt.datetime(2020, 3, 2, 3, 0, tzinfo=dt.UTC)


def test_P_FUT_pipeline_event_known_after_its_ex_date(  # noqa: N802 - after spec 10.1's name
    tmp_path: Path, project: Path
) -> None:
    """INV-02 as `test_P_FUT_pipeline` states it, at a τ after an event's ex-date and before
    it is first known: deleting the event leaves the rows decided by τ as they were."""
    root = make_snapshot(tmp_path / "tiny", preset="tiny", markets=("KR",), events=[LATE_EVENT])
    (event,) = rows_of(root, "corporate_actions")
    assert event["ts_effective"] < LATE_TAU < event["ts_announced"]  # what the case is for
    at = shutil.copytree(root, tmp_path / "cut")
    assert cut_after(at, LATE_TAU)["corporate_actions"] == 1
    pipe, period = build(SIGNED_ZEROS), ("2020-01-02", "2020-03-31")
    with inside(project):
        whole = nx.run_pipeline(pipe, start=period[0], end=period[1], freq="monthly",
                                snapshot=nx.open(str(root)))  # fmt: skip
        earlier = nx.run_pipeline(pipe, start=period[0], end=period[1], freq="monthly",
                                  snapshot=nx.open(str(at)))  # fmt: skip
    old, new = decided(whole.table, LATE_TAU), decided(earlier.table, LATE_TAU)
    assert dt.date(2020, 2, 28) in old["session_date"].to_pylist()  # a decision across it
    assert bits(new) == bits(old)
    assert bits(closed(earlier.term_diagnostics, at, LATE_TAU)) == bits(
        closed(whole.term_diagnostics, at, LATE_TAU)
    )
