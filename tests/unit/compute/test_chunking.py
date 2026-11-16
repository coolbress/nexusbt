"""Chunk sizes from the memory budget (5.3.8), T1.7b (#240)."""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest

from nexusbt.compute import _executor
from nexusbt.compute._chunks import GB, estimate, lookback, most_alive, spans
from nexusbt.compute._executor import execute
from nexusbt.contracts import ConfigError
from nexusbt.data._block import MarketBlock
from nexusbt.pipeline import BoundColumn, Factor, Term, factor, graph_hash

pytestmark = pytest.mark.unit

CLOSE = BoundColumn.of("Price", "close")
#: The weekdays of 2020 and 2021: 524 sessions.
DATES = np.arange(np.datetime64("2020-01-01"), np.datetime64("2022-01-01"))
DATES = DATES[np.is_busday(DATES)]
READY = (DATES + np.timedelta64(16, "h")).astype("datetime64[us]")
IDS = ("A", "B", "C")


def _mean(w: Any) -> Any:
    acc = np.zeros(w.shape[1])
    for r in range(w.shape[0]):
        acc = acc + w[r]
    return acc / w.shape[0]


def sma(window: int, of: BoundColumn | Factor) -> Factor:
    return factor(window, [of])(_mean)


def whole() -> MarketBlock:
    """B is delisted after row 199 and C listed from row 300, so a chunk's instruments change."""
    n = len(DATES)
    rng = np.random.default_rng(11)
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.02, (n, 3)), axis=0))
    exists = np.ones((n, 3), dtype=bool)
    exists[200:, 1] = False
    exists[:300, 2] = False
    close[~exists] = np.nan
    available = np.where(exists, READY[:, None], np.datetime64("NaT", "us"))
    status = np.zeros((n, 3), np.int8)
    return MarketBlock("XX", DATES, 0, IDS, {"close": close}, exists, status, available)


def read(first: int, last: int) -> MarketBlock:
    """The block of rows `first..last` over the instruments listed in them (5.3.1)."""
    full, rows = whole(), slice(first, last + 1)
    listed = full.exists[rows].any(axis=0)
    ids = tuple(i for i, keep in zip(IDS, listed, strict=True) if keep)
    cells = (full.exists[rows][:, listed], full.obs_status[rows][:, listed])
    values = {"close": full.values["close"][rows][:, listed]}
    available = full.ts_available[rows][:, listed]
    return MarketBlock("XX", DATES[rows], 0, ids, values, *cells, available)


def test_sub_year_chunks_when_budget_small() -> None:
    """A budget a year does not fit splits into quarters, then months; the values are the same
    bits as with year chunks, with each chunk's own instruments (5.3.8, INV-03)."""
    inner = sma(10, CLOSE)
    terms: list[Term] = [sma(5, inner).shift(2), CLOSE.latest / inner - 1.0]
    nodes = most_alive(terms)
    decisions = [*range(20, len(DATES), 21), 199, 200, 300, len(DATES) - 1]
    functions = {graph_hash(t): _mean for t in (inner, terms[0].inputs[0])}
    back = lookback(terms)
    assert back == 15  # the shift's 2, the outer window's 4 and the inner window's 9
    axes: set[tuple[str, ...]] = set()
    held: list[int] = []

    def reading(first: int, last: int) -> MarketBlock:
        found = read(first, last)
        axes.add(found.instrument_ids)
        held.append(len(found.dates))
        return found

    def budget(rows: int) -> float:
        return estimate(rows + back, len(IDS), nodes) / GB

    def values(budget_gb: float) -> tuple[list[tuple[int, int]], dict[str, Any]]:
        held.clear()
        found = spans(DATES, len(IDS), nodes, budget_gb, back)
        out = execute(terms, decisions, found, reading, READY, functions)
        assert estimate(max(held), len(IDS), nodes) <= budget_gb * GB  # blocks, overlap too
        bits = {}
        for key, table in out.items():
            value = table["value"].to_numpy().tobytes()
            bits[key] = (table["row"].to_pylist(), table["instrument_id"].to_pylist(), value)
        return found, bits

    def periods(found: list[tuple[int, int]], unit: str) -> list[bool]:
        """Whether each chunk is exactly one whole calendar period of `unit`."""
        months = DATES.astype("datetime64[M]").astype(np.int64)
        key = {"Y": months // 12, "Q": months // 3, "M": months}[unit]
        last = len(DATES) - 1
        return [
            key[a] == key[b]
            and (a == 0 or key[a] != key[a - 1])
            and (b == last or key[b] != key[b + 1])
            for a, b in found
        ]

    years, by_year = values(1.0)
    assert len(years) == 2
    assert all(periods(years, "Y"))
    quarters, by_quarter = values(budget(70))
    assert len(quarters) == 8
    assert all(periods(quarters, "Q"))  # each chunk is exactly one quarter
    months, by_month = values(budget(30))
    assert len(months) == 24
    assert all(periods(months, "M"))
    halves, by_half = values(budget(12))
    assert len(halves) > 24
    assert by_quarter == by_year
    assert by_month == by_year
    assert by_half == by_year
    ids = {i for _, idents, _ in by_year.values() for i in idents}
    assert ids == {"A", "B", "C"}  # B before its delisting, C after its listing
    assert {("A",), ("A", "B"), ("A", "C")} <= axes  # chunks over different instruments


def test_one_row_over_the_budget_is_e16() -> None:
    """One row with the rows read before it is the least a chunk holds."""
    with pytest.raises(ConfigError, match="memory_budget_gb too small for 3 instruments"):
        spans(DATES, len(IDS), 4, (estimate(1, len(IDS), 4) - 1) / GB)
    with pytest.raises(ConfigError, match="with the 9 rows read before it"):
        spans(DATES, len(IDS), 4, (estimate(10, len(IDS), 4) - 1) / GB, 9)
    with pytest.raises(ValueError, match="positive number, not nan"):
        spans(DATES, len(IDS), 4, float("nan"))


def test_most_alive_drops_a_node_once_read(monkeypatch: pytest.MonkeyPatch) -> None:
    """A node is let go once every reader is computed, an output never (5.3.2 (5)); the executor
    holds at most the nodes the estimate counts."""
    a = CLOSE.latest
    chain = (a + 1.0) * 2.0
    assert most_alive([chain]) == 3  # `latest`, `1.0` and the sum; then `2.0` and the product
    assert most_alive([a, chain]) == 4  # `latest` is an output: kept beside the product
    held: list[int] = []
    compute = _executor._Chunk.compute

    def counting(self: Any, term: Term, rows: Any) -> None:
        compute(self, term, rows)
        held.append(len(self.values))

    monkeypatch.setattr(_executor._Chunk, "compute", counting)
    for terms in ([chain], [a, chain]):
        held.clear()
        execute(terms, [50], [(0, 99)], read, READY)
        assert max(held) == most_alive(terms)
