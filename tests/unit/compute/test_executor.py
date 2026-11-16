"""The reference executor over chunks and late cells, T1.7b (#240): the parts of P-CHUNK and P-FUT
that need no built-in factor or selection (decision 2026-11-10, #356)."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

import numpy as np
import numpy.typing as npt
import pyarrow as pa
import pytest

from nexusbt.compute._executor import execute
from nexusbt.data._block import MarketBlock
from nexusbt.pipeline import BoundColumn, Factor, Term, factor, graph_hash

pytestmark = pytest.mark.unit

CLOSE = BoundColumn.of("Price", "close")
SESSIONS, IDS = 200, ("A", "B", "C")
DATES = np.datetime64("2020-01-01") + np.arange(SESSIONS).astype("timedelta64[D]")
READY = (DATES + np.timedelta64(16, "h")).astype("datetime64[us]")


def _mean(w: Any) -> Any:
    acc = np.zeros(w.shape[1])
    for r in range(w.shape[0]):
        acc = acc + w[r]
    return acc / w.shape[0]


def sma(window: int, of: BoundColumn | Factor) -> Factor:
    return factor(window, [of])(_mean)


def block(seed: int = 7) -> MarketBlock:
    """A whole axis of synthetic closes; C is listed from row 30 (absent before, 5.3.1)."""
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.02, (SESSIONS, 3)), axis=0))
    exists = np.ones((SESSIONS, 3), dtype=bool)
    exists[:30, 2] = False
    close[~exists] = np.nan
    available = np.where(exists, READY[:, None], np.datetime64("NaT", "us"))
    status = np.zeros((SESSIONS, 3), np.int8)
    return MarketBlock("XX", DATES, 0, IDS, {"close": close}, exists, status, available)


def reader(whole: MarketBlock, reads: list[tuple[int, int]]) -> Callable[[int, int], MarketBlock]:
    def read(first: int, last: int) -> MarketBlock:
        reads.append((first, last))
        s = slice(first, last + 1)
        values = {k: v[s] for k, v in whole.values.items()}
        cells = (whole.exists[s], whole.obs_status[s], whole.ts_available[s])
        return MarketBlock(whole.market, whole.dates[s], 0, whole.instrument_ids, values, *cells)

    return read


Spans = list[tuple[int, int]]


def run(
    terms: list[Term],
    decisions: list[int],
    spans: Spans,
    whole: MarketBlock,
    reads: Spans | None = None,
) -> dict[str, pa.Table]:
    functions = {graph_hash(t): _mean for t in _users(terms)}
    read = reader(whole, [] if reads is None else reads)
    return execute(terms, decisions, spans, read, READY, functions)


def _users(terms: list[Term]) -> list[Term]:
    found, stack = [], list(terms)
    while stack:
        t = stack.pop()
        found += [t] if t.op == "user" else []
        stack.extend(t.inputs)
    return found


def bits(table: pa.Table) -> tuple[list[int], list[str], bytes]:
    value: npt.NDArray[np.float64] = table["value"].to_numpy()
    return table["row"].to_pylist(), table["instrument_id"].to_pylist(), value.tobytes()


def test_chunk_boundary_values_equal_unchunked(caplog: pytest.LogCaptureFixture) -> None:
    """Nested windows and a `shift` (the case of `test_nested_windows_across_chunks`): a chunk
    starting at row 100 reads 14 rows before it, as the plan gives, not `W_max - 1 = 9`, and every
    value equals the unchunked run bit for bit, sub-year chunks included (INV-03, P-CHUNK)."""
    inner = sma(10, CLOSE)
    outer = sma(5, inner).shift(2)
    terms: list[Term] = [outer, CLOSE.latest / inner - 1.0]
    decisions = [*range(19, SESSIONS, 21), 100, 101, 199]
    whole = block()
    with caplog.at_level("DEBUG", logger="nexusbt.compute"):
        unchunked = run(terms, decisions, [(0, SESSIONS - 1)], whole)
    computed, total = map(int, re.findall(r"rows computed: (\d+) of (\d+)", caplog.text)[0])
    assert computed < total  # the executor plans: some rows, not every row of every node
    reads: list[tuple[int, int]] = []
    spans = [(0, 99), (100, 149), (150, 199)]
    for split in (spans, [(s, min(s + 24, SESSIONS - 1)) for s in range(0, SESSIONS, 25)]):
        chunked = run(terms, decisions, split, whole, reads)
        for t in terms:
            assert bits(chunked[graph_hash(t)]) == bits(unchunked[graph_hash(t)])
    assert (85, 149) in reads  # the plan's 14 rows before row 100, in more than the last chunk
    found = unchunked[graph_hash(outer)]
    assert not np.isnan(found["value"].to_numpy()).all()
    pairs = zip(found["row"].to_pylist(), found["instrument_id"].to_pylist(), strict=True)
    assert {i for r, i in pairs if r < 30} == {"A", "B"}  # C is listed from row 30: no value


def test_cutoff_hides_late_cells() -> None:
    """A bar of row s available only at `ready(s+1)` is NaN in the values of row s and read at
    its own row from s+1 (5.1.2); deleting every cell available after `ready(s)` leaves the values
    of rows up to s unchanged (INV-02, P-FUT)."""
    s, whole = 120, block()
    whole.ts_available[s, 0] = READY[s + 1]
    latest, total = CLOSE.latest, sma(2, CLOSE)
    terms: list[Term] = [latest, total]
    found = run(terms, [s, s + 1], [(0, SESSIONS - 1)], whole)
    columns = (found[graph_hash(latest)][c].to_pylist() for c in ("row", "instrument_id", "value"))
    at = {(r, i): v for r, i, v in zip(*columns, strict=True)}
    assert np.isnan(at[s, "A"])
    assert at[s, "B"] == whole.values["close"][s, 1]
    assert at[s + 1, "A"] == whole.values["close"][s + 1, 0]
    window = found[graph_hash(total)]["value"].to_numpy()
    assert np.isnan(window[0])  # row s, A: its own cell is not seen yet
    assert window[3] == _mean(whole.values["close"][s : s + 2, :1])[0]  # row s+1 sees it at s
    # Only a term reading the cells hides them by its own row's `ready`; a term reading another
    # term's values reads them as given at each row, so row s's frozen NaN stays (3.3 `shift`,
    # 5.1.2 "the values of a row that has already frozen are not changed by data that arrives
    # late"). At s+1, for A: the shift is NaN, the window over `latest` is computed with row s
    # NaN, and the window over the column reads row s's cell.
    lagged, smoothed = latest.shift(1), sma(2, latest)
    later = run([lagged, smoothed, total], [s + 1], [(0, SESSIONS - 1)], whole)
    assert np.isnan(later[graph_hash(lagged)]["value"][0].as_py())
    frozen = np.array([[np.nan], whole.values["close"][s + 1, :1]])
    assert later[graph_hash(smoothed)]["value"][0].as_py() is not None
    assert bits(later[graph_hash(smoothed)].slice(0, 1))[2] == _mean(frozen).tobytes()
    seen = whole.values["close"][s : s + 2, :1]
    assert bits(later[graph_hash(total)].slice(0, 1))[2] == _mean(seen).tobytes()
    assert not np.isnan(_mean(seen)[0])
    cut = block()
    late = whole.ts_available > READY[s]
    cut.values["close"][late] = np.nan
    cut.ts_available[late] = np.datetime64("NaT", "us")
    decisions = list(range(60, s + 1, 15))
    before = run(terms, decisions, [(0, 99), (100, 199)], whole)
    after = run(terms, decisions, [(0, 199)], cut)
    for t in terms:
        assert bits(before[graph_hash(t)]) == bits(after[graph_hash(t)])


def test_unknown_term_and_missing_function_are_refused() -> None:
    with pytest.raises(NotImplementedError, match="no `rank` term"):
        run([CLOSE.latest.rank()], [50], [(0, 199)], block())
    with pytest.raises(ValueError, match="no function given"):
        execute([sma(3, CLOSE)], [50], [(0, 199)], reader(block(), []), READY)
    with pytest.raises(ValueError, match=r"outside every chunk: \[250\]"):
        run([CLOSE.latest], [50, 250], [(0, 199)], block())
    with pytest.raises(ValueError, match="in order and apart"):
        run([CLOSE.latest], [50], [(0, 99), (90, 199)], block())
    with pytest.raises(ValueError, match=r"through a term, such as `\.latest`: \['close'\]"):
        run([CLOSE], [50], [(0, 199)], block())


def test_edges_a_run_meets() -> None:
    """A chunk with no decisions reads nothing; an element function runs compiled; a user window
    before the axis start is NaN; a user mask and a wrong-shaped return are refused."""
    whole, reads = block(), list[tuple[int, int]]()
    logged = CLOSE.latest.log()
    found = run([logged, sma(3, CLOSE)], [1, 60], [(0, 49), (50, 99), (100, 199)], whole, reads)
    assert [r for r in reads if r[1] == 199] == []  # the last chunk holds no decision
    assert found[graph_hash(logged)]["value"][0].as_py() == np.log(whole.values["close"][1, 0])
    assert np.isnan(found[graph_hash(sma(3, CLOSE))]["value"][0].as_py())  # row 1 of window 3
    masked = factor(3, [CLOSE], mask=CLOSE.latest > 0.0)(_mean)
    with pytest.raises(NotImplementedError, match=r"mask comes with T1\.12"):
        execute([masked], [50], [(0, 199)], reader(whole, []), READY, {graph_hash(masked): _mean})
    wide = sma(3, CLOSE)
    with pytest.raises(ValueError, match=r"returned \(1,\), not \(3,\)"):
        execute([wide], [50], [(0, 199)], reader(whole, []), READY, {graph_hash(wide): _first})


def _first(w: Any) -> Any:
    return w[0, :1]


def test_a_term_listed_twice_is_one_output() -> None:
    found = run([CLOSE.latest, CLOSE.latest], [50], [(0, 199)], block())
    assert found[graph_hash(CLOSE.latest)].num_rows == 3  # A, B and C once each
