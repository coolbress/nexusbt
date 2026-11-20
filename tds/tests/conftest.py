"""Not for merge: a measurement for #662 (the K001 memory test in CI). Closed after one run.

Measures only inside `test_k001_memory_holds_a_batch_not_every_key`: which `keys` module the
test patched and which one `check_keys` reads, both `BATCH_ROWS`, the merge path (spill files,
runs, block, the largest `os.pread` size `_run` asked for), the five largest live allocations
(10 frames) at the highest point seen, and the last 30 test files run before it. Printed in the
terminal summary as `[measure-662b]` lines.
"""

from __future__ import annotations

import os
import sys
import tracemalloc
from pathlib import Path
from typing import Any

import pytest

from nexusbt_tds import hash as tds_hash
from nexusbt_tds import keys as tds_keys

K001 = "test_k001_memory_holds_a_batch_not_every_key"
ROOT = Path(__file__).resolve().parents[2]
LINES: list[str] = []
FILES: list[str] = []
_GET_TRACED = tracemalloc.get_traced_memory  # the real one, before any wrapping


def _say(text: str) -> None:
    LINES.append(f"[measure-662b] {text}")


def _where(file: str) -> str:
    path = Path(file)
    if "site-packages" in path.parts:
        return "/".join(path.parts[len(path.parts) - path.parts[::-1].index("site-packages") :])
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        if "lib" in path.parts:
            return "/".join(path.parts[len(path.parts) - path.parts[::-1].index("lib") :])
        return path.name


NODES: list[str] = []


def pytest_runtest_logstart(nodeid: str, location: Any) -> None:
    NODES[:] = [*NODES[-3:], nodeid]
    file = nodeid.split("::")[0]
    if not FILES or FILES[-1] != file:
        FILES.append(file)


class _Probe:
    def __init__(self) -> None:
        self.phase, self.true_peak = 0, 0
        self.best: tuple[int, str, list[str]] = (-1, "", [])
        self.pread_max = 0

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
                top.append(f"{stat.size} B in {stat.count} blocks: {frames}")
            del snap
            self.best = (cur, where, top)
        tracemalloc.reset_peak()


def _modules(test_keys: Any) -> None:
    same = {n for n, m in list(sys.modules.items())
            if str(getattr(m, "__file__", "")).endswith(("nexusbt_tds/keys.py",
                                                         "nexusbt_tds/hash.py"))}
    _say(f"keys: test's keys is sys.modules['nexusbt_tds.keys']="
         f"{test_keys is sys.modules.get('nexusbt_tds.keys')}"
         f" conftest's keys is it={tds_keys is sys.modules.get('nexusbt_tds.keys')}"
         f" check_keys.__globals__['BATCH_ROWS']={test_keys.check_keys.__globals__['BATCH_ROWS']}"
         f" test keys.BATCH_ROWS={test_keys.BATCH_ROWS}"
         f" hash.BATCH_ROWS={sys.modules['nexusbt_tds.hash'].BATCH_ROWS}"
         f" modules with those files={sorted(same)}")


@pytest.fixture(autouse=True)
def _measure_662b(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> Any:
    if request.node.name != K001:
        yield
        return
    before = FILES[:-1] if FILES and FILES[-1].endswith("test_conformance.py") else FILES
    _say(f"files run before it (last 30 of {len(before)}): {before[-30:]}")
    _say(f"tests just before it: {NODES[:-1]}")
    test_keys = request.module.keys
    probe = _Probe()
    real_start, real_get, real_pread = tracemalloc.start, tracemalloc.get_traced_memory, os.pread

    def start(nframe: int = 1) -> None:
        probe.phase += 1
        probe.true_peak, probe.best, probe.pread_max = 0, (-1, "", []), 0
        real_start(10)

    def get_traced_memory() -> tuple[int, int]:
        cur, peak = real_get()
        peak = max(peak, probe.true_peak)
        _say(f"phase {probe.phase}: peak={peak} highest live={probe.best[0]} at {probe.best[1]}"
             f" largest pread={probe.pread_max}")
        for t in probe.best[2]:
            _say(f"phase {probe.phase} top: {t}")
        _modules(test_keys)
        return cur, peak

    def pread(fd: int, n: int, at: int) -> bytes:
        probe.pread_max = max(probe.pread_max, n)
        return real_pread(fd, n, at)

    add, merged, dup = tds_hash.SortedRuns.add, tds_hash.SortedRuns.merged, tds_keys._duplicates

    def add_(self: Any, run: list[Any]) -> None:
        probe.sample("SortedRuns.add")
        add(self, run)

    def merged_(self: Any) -> Any:
        probe.sample("SortedRuns.merged")
        spans = len(self.spans)
        block = min(tds_hash._BLOCK, max(tds_hash._MERGE_BYTES // spans, 4096)) if spans else 0
        size = os.fstat(self.out.fileno()).st_size if self.out is not None else 0
        _say(f"phase {probe.phase} path: spill_file={self.out is not None}"
             f" spilled={len(self.spilled)} runs={spans} first_in_memory={len(self.first)}"
             f" file_bytes={size} block={block} buffers={block * spans}"
             f" _BLOCK={tds_hash._BLOCK} _MERGE_BYTES={tds_hash._MERGE_BYTES}")
        return merged(self)

    def dup_(records: Any, key: list[str]) -> Any:
        def counted() -> Any:
            for i, r in enumerate(records):
                if i % 500 == 0:
                    probe.sample(f"_duplicates record {i}")
                yield r
            probe.sample("_duplicates end")

        return dup(counted(), key)

    monkeypatch.setattr(tracemalloc, "start", start)
    monkeypatch.setattr(tracemalloc, "get_traced_memory", get_traced_memory)
    monkeypatch.setattr(os, "pread", pread)
    monkeypatch.setattr(tds_hash.SortedRuns, "add", add_)
    monkeypatch.setattr(tds_hash.SortedRuns, "merged", merged_)
    monkeypatch.setattr(tds_keys, "_duplicates", dup_)
    yield


def pytest_terminal_summary(terminalreporter: Any) -> None:
    for line in LINES:
        terminalreporter.write_line(line)
