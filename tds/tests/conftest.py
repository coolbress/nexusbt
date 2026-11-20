"""Not for merge: a measurement for #662 (the K001 memory test in CI). Closed after one run.

Measures `test_k001_memory_holds_a_batch_not_every_key` twice: once right after collection,
before any test, and once where the suite runs it. Each time: the process state when it starts,
the two peaks, the five largest live allocations (10 frames) at the highest point seen while
`check_keys` runs, and the path `SortedRuns` took (runs, spill file, merge buffers). Printed in
the terminal summary as `[measure-662]` lines.
"""

from __future__ import annotations

import gc
import os
import sys
import tempfile
import tracemalloc
from pathlib import Path
from typing import Any

import pytest

from nexusbt_tds import hash as tds_hash
from nexusbt_tds import keys as tds_keys

K001 = "test_k001_memory_holds_a_batch_not_every_key"
ROOT = Path(__file__).resolve().parents[2]
LINES: list[str] = []
_GET_TRACED = tracemalloc.get_traced_memory  # the real one, before any wrapping


def _where(file: str) -> str:
    path = Path(file)
    for cut in ("site-packages",):
        if cut in path.parts:
            return "/".join(path.parts[len(path.parts) - path.parts[::-1].index(cut) :])
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        if "lib" in path.parts:
            return "/".join(path.parts[len(path.parts) - path.parts[::-1].index("lib") :])
        return path.name


def _state(label: str) -> None:
    import numpy as np
    import pyarrow as pa

    mon = getattr(sys, "monitoring", None)
    tools = {i: mon.get_tool(i) for i in range(6) if mon and mon.get_tool(i)} if mon else {}
    cov = sys.modules.get("coverage")
    LINES.append(
        f"[measure-662] {label} state: gc.isenabled={gc.isenabled()} threshold={gc.get_threshold()}"
        f" count={gc.get_count()} tracing={tracemalloc.is_tracing()}"
        f" numba={'numba' in sys.modules} gettrace={type(sys.gettrace()).__name__}"
        f" monitoring_tools={tools} coverage={getattr(cov, '__version__', None)}"
        f" COVERAGE_CORE={os.environ.get('COVERAGE_CORE')}"
        f" pool={pa.default_memory_pool().backend_name} arrow_allocated={pa.total_allocated_bytes()}"
        f" platform={sys.platform} python={sys.version.split()[0]} numpy={np.__version__}"
        f" pyarrow={pa.__version__}"
    )


class _Probe:
    """Wraps `tracemalloc` and the K001 path for one call of the test body."""

    def __init__(self, label: str) -> None:
        self.label, self.phase, self.true_peak = label, 0, 0
        self.best: tuple[int, list[str]] = (-1, [])
        self.runs: list[str] = []

    def sample(self, where: str) -> None:
        if not tracemalloc.is_tracing():
            return
        cur, peak = _GET_TRACED()
        self.true_peak = max(self.true_peak, peak)
        if cur > self.best[0]:
            snap = tracemalloc.take_snapshot()
            top = []
            for stat in snap.statistics("traceback")[:5]:
                inner = reversed(list(stat.traceback))  # the allocating line first
                frames = " <- ".join(f"{_where(f.filename)}:{f.lineno}" for f in inner)
                top.append(f"{stat.size} B in {stat.count} blocks at {where}: {frames}")
            del snap
            self.best = (cur, top)
        tracemalloc.reset_peak()

    def start(self, real: Any) -> Any:
        def start(nframe: int = 1) -> None:
            self.phase += 1
            self.true_peak, self.best = 0, (-1, [])
            real(10)

        return start

    def traced(self, real: Any) -> Any:
        def get_traced_memory() -> tuple[int, int]:
            cur, peak = real()
            peak = max(peak, self.true_peak)
            LINES.append(f"[measure-662] {self.label} phase {self.phase}: peak={peak}"
                         f" highest live={self.best[0]}")
            LINES.extend(f"[measure-662] {self.label} phase {self.phase} top: {t}"
                         for t in self.best[1])
            return cur, peak

        return get_traced_memory


@pytest.fixture(autouse=True)
def _measure_662(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> Any:
    if request.node.name != K001:
        yield
        return
    yield from _instrumented("in order", monkeypatch)


def _instrumented(label: str, monkeypatch: pytest.MonkeyPatch) -> Any:
    _state(label)
    probe = _Probe(label)
    monkeypatch.setattr(tracemalloc, "start", probe.start(tracemalloc.start))
    monkeypatch.setattr(tracemalloc, "get_traced_memory",
                        probe.traced(tracemalloc.get_traced_memory))
    add, merged, dup = tds_hash.SortedRuns.add, tds_hash.SortedRuns.merged, tds_keys._duplicates
    sample = probe.sample

    def add_(self: Any, run: list[Any]) -> None:
        sample("SortedRuns.add")
        add(self, run)

    def merged_(self: Any) -> Any:
        sample("SortedRuns.merged")
        spans = len(self.spans)
        block = min(tds_hash._BLOCK, max(tds_hash._MERGE_BYTES // spans, 4096)) if spans else 0
        size = os.fstat(self.out.fileno()).st_size if self.out is not None else 0
        probe.runs.append(f"spill_file={self.out is not None} spilled={len(self.spilled)}"
                          f" runs={spans} first_in_memory={len(self.first)} file_bytes={size}"
                          f" block={block} buffers={block * spans} _BLOCK={tds_hash._BLOCK}"
                          f" _MERGE_BYTES={tds_hash._MERGE_BYTES}")
        return merged(self)

    def dup_(records: Any, key: list[str]) -> Any:
        def counted() -> Any:
            for i, r in enumerate(records):
                if i % 500 == 0:
                    sample(f"_duplicates record {i}")
                yield r
            sample("_duplicates end")

        return dup(counted(), key)

    monkeypatch.setattr(tds_hash.SortedRuns, "add", add_)
    monkeypatch.setattr(tds_hash.SortedRuns, "merged", merged_)
    monkeypatch.setattr(tds_keys, "_duplicates", dup_)
    yield
    LINES.extend(f"[measure-662] {label} path: {r}" for r in probe.runs)


def pytest_collection_finish(session: pytest.Session) -> None:
    """The same test body, before any test runs."""
    item = next((i for i in session.items if getattr(i, "name", "") == K001), None)
    if item is None:
        LINES.append("[measure-662] at start: the test was not collected")
        return
    with pytest.MonkeyPatch.context() as mp:
        steps = _instrumented("at start", mp)
        next(steps)
        try:
            item.obj(tmp_path=Path(tempfile.mkdtemp()), monkeypatch=mp)
            LINES.append("[measure-662] at start: passed")
        except AssertionError as error:
            LINES.append(f"[measure-662] at start: failed {error}")
        next(steps, None)


def pytest_terminal_summary(terminalreporter: Any) -> None:
    for line in LINES:
        terminalreporter.write_line(line)
