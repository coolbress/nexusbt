"""Spec 3.3, 5.4.1 [V31-21, R3-13]: three-valued Filters through the reference executor.

A Filter's cell is true, false or unknown; the executor's table gives it as a boolean that is
null where the cell is unknown.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pyarrow as pa
import pytest

from nexusbt.compute import _crosssection as xs
from nexusbt.compute import _kernels as k
from nexusbt.compute._executor import execute
from nexusbt.compute._screen import screened
from nexusbt.contracts import TiebreakPolicy
from nexusbt.data._block import MarketBlock
from nexusbt.pipeline import BoundColumn, Pipeline, Term, graph_hash
from nexusbt.pipeline.factors import SimpleMovingAverage

pytestmark = pytest.mark.unit
HASH = TiebreakPolicy.HASH

N = np.nan
U = None  # an unknown cell in a table
CLOSE, OPEN = BoundColumn.of("Price", "close"), BoundColumn.of("Price", "open")
#: Nine instruments: each pair of (close > 0, open > 0) in true, false, unknown.
PAIRS = [(1.0, 1.0), (1.0, -1.0), (1.0, N), (-1.0, 1.0), (-1.0, -1.0), (-1.0, N),
         (N, 1.0), (N, -1.0), (N, N)]  # fmt: skip


def block(**columns: list[list[float]]) -> MarketBlock:
    """Rows of a whole axis, one column a list of rows; every instrument listed, every bar seen."""
    values = {name: np.array(rows, dtype=np.float64) for name, rows in columns.items()}
    shape = next(iter(values.values())).shape
    dates = np.datetime64("2020-01-01") + np.arange(shape[0]).astype("timedelta64[D]")
    ready = (dates + np.timedelta64(16, "h")).astype("datetime64[us]")
    ids = tuple(f"I{i}" for i in range(shape[1]))
    seen = np.broadcast_to(ready[:, None], shape).copy()
    status = np.zeros(shape, np.int8)
    return MarketBlock("XX", dates, 0, ids, values, np.ones(shape, bool), status, seen)


def values(terms: list[Term], whole: MarketBlock, tiebreak: Any = HASH) -> list[list[Any]]:
    """Each term's cells at the last row, in instrument order."""
    last = len(whole.dates) - 1
    ready = (whole.dates + np.timedelta64(16, "h")).astype("datetime64[us]")
    found = execute(terms, [last], [(0, last)], lambda a, b: whole, ready, tiebreak=tiebreak)
    tables: list[pa.Table] = [found[graph_hash(t)] for t in terms]
    return [t["value"].to_pylist() for t in tables]


def pairs() -> MarketBlock:
    return block(close=[[c for c, _ in PAIRS]], open=[[o for _, o in PAIRS]])


def test_kleene_and_or() -> None:
    """`&` and `|` are Kleene: false & unknown = false, true | unknown = true, the rest of the
    pairs with an unknown are unknown (5.4.1)."""
    a, b = CLOSE.latest > 0, OPEN.latest > 0
    both, either = values([a & b, a | b], pairs())
    assert both == [True, False, U, False, False, False, U, False, U]
    assert either == [True, True, True, True, False, U, True, U, U]


def test_not_keeps_unknown() -> None:
    """`~` inverts the value and keeps validity: a halted instrument, with no close, is unknown
    in `~(close > 10_000)`, not true as v3 (and zipline) made it (5.4.1)."""
    halted = block(close=[[12_000.0, 8_000.0, N]])
    above = CLOSE.latest > 10_000
    assert values([above, ~above, ~~above], halted) == [
        [True, False, U], [False, True, U], [True, False, U]]  # fmt: skip


def test_isnan_always_valid() -> None:
    """`isnan`, `notnan`, `isfinite`, `isnull` and `notnull` are never unknown, a missing
    input included; so `(close > 0) | close.isnan()` is known everywhere (5.4.1)."""
    x = CLOSE.latest
    found = values([x.isnan(), x.notnan(), x.isfinite(), x.isnull(), x.notnull(),
                    (x > 0) | x.isnan()], block(close=[[1.0, N, -1.0]]))  # fmt: skip
    assert found == [
        [False, True, False],
        [True, False, True],
        [True, False, True],
        [False, True, False],
        [True, False, True],
        [True, True, False],
    ]


def test_all_any_kleene() -> None:
    """`all(2)` is false when one session is false, else unknown when one is unknown; `any(2)` is
    true when one is true, else unknown when one is unknown (3.3, R3-13). The two sessions are
    the rows of `PAIRS`."""
    up = CLOSE.latest > 0
    two = block(close=[[a for a, _ in PAIRS], [b for _, b in PAIRS]])
    every, some = values([up.all(2), up.any(2)], two)
    assert every == [True, False, U, False, False, False, U, False, U]
    assert some == [True, True, True, True, False, U, True, U, U]


def test_edges_of_the_filter_terms() -> None:
    """A window that starts before the axis is unknown, as a user window is NaN there (the spec
    does not say; #535); a Filter term not built yet and a comparison code out of range are
    refused."""
    assert values([(CLOSE.latest > 0).all(3)], block(close=[[-1.0], [1.0]])) == [[U]]
    with pytest.raises(NotImplementedError, match="no `startswith` term"):
        values([CLOSE.latest.quantiles(2).startswith("A")], block(close=[[1.0]]))
    with pytest.raises(NotImplementedError, match="across_markets=True is run_pipeline's"):
        values([CLOSE.latest.rank(across_markets=True)], block(close=[[1.0]]))
    for name in ("x", True):  # a name, and a bool, which is an int to Python but no code
        with pytest.raises(NotImplementedError, match="Classifier names come with its code"):
            values([CLOSE.latest.quantiles(2).eq(name)], block(close=[[1.0]]))
    with pytest.raises(ValueError, match="no comparison has code 6"):
        k.compare(6, np.zeros(1), np.zeros(1))


def test_as_factor_unknown_nan() -> None:
    """`as_factor()` gives 1.0, 0.0 and NaN for unknown; `if_else` is NaN where its condition is
    unknown; `fillna(bool)` is the only fill (3.3, R3-13, INV-12)."""
    up = CLOSE.latest > 10_000
    x = block(close=[[12_000.0, 8_000.0, N]], open=[[1.0, 2.0, 3.0]])
    picked = up.if_else(OPEN.latest, -OPEN.latest)
    factor, chosen, yes, no = values([up.as_factor(), picked, up.fillna(True), up.fillna(False)], x)
    assert np.array_equal(factor, [1.0, 0.0, N], equal_nan=True)
    assert np.array_equal(chosen, [1.0, -2.0, N], equal_nan=True)
    assert (yes, no) == ([True, False, True], [True, False, False])


def _n(cells: list[Any]) -> list[Any]:
    """A Factor's cells with NaN as None, so a list compares with `==`."""
    return [None if isinstance(c, float) and np.isnan(c) else c for c in cells]


def test_final_use_unknown_is_false() -> None:
    """At a final use, unknown is false (5.4.1): a `~(close > 10_000)` mask leaves the halted
    instrument (no close) out of the cross-section and out of `top`'s candidates, where
    `fillna(True)` lets it in. Outside the mask a Factor is NaN and a Filter unknown (3.3)."""
    x = block(close=[[12_000.0, 8_000.0, N, 7_000.0]], open=[[1.0, 2.0, 3.0, 4.0]])
    low = ~(CLOSE.latest > 10_000)
    score = OPEN.latest
    ranks, picks, filled = values([score.rank(mask=low), score.top(5, mask=low),
                                   score.rank(mask=low.fillna(True))], x)  # fmt: skip
    assert _n(ranks) == [U, 1.0, U, 2.0]
    assert picks == [U, True, U, True]
    assert _n(filled) == [U, 1.0, 2.0, 3.0]


def test_classifier_missing_is_unknown() -> None:
    """A Classifier's `eq` and `element_of` on the missing code -1 are unknown; `isnull` and
    `notnull` are always valid (3.3, R3-13). Closes 3, 1, NaN, 2 in two tie-preserving buckets
    (5.4.3): mean ranks 3, 1, 2 of n = 3 give `ceil(r * 2 / 3)` = 2, 1, 2; NaN has no bucket."""
    q = CLOSE.latest.quantiles(2)
    x = block(close=[[3.0, 1.0, N, 2.0]])
    codes, two, one, null, known = values([q, q.eq(2), q.element_of([1]), q.isnull(),
                                           q.notnull()], x)  # fmt: skip
    assert codes == [2, 1, -1, 2]
    assert two == [True, False, U, True]
    assert one == [False, True, U, False]
    assert (null, known) == ([False, False, True, False], [True, True, False, True])


def test_builtin_factor_mask() -> None:
    """A built-in factor's `mask` is its domain (3.3): `SMA(2)` of closes 10..40 then 12..42 is
    11, 21, 31, 41, NaN where the mask is false or unknown."""
    x = block(close=[[10.0, 20.0, 30.0, 40.0], [12.0, 22.0, 32.0, 42.0]],
              open=[[1.0, 1.0, 1.0, 1.0], [1.0, -1.0, N, 1.0]])  # fmt: skip
    sma = SimpleMovingAverage(2, [CLOSE], mask=OPEN.latest > 0)
    assert _n(values([sma], x)[0]) == [11.0, U, U, 41.0]


def test_cross_section_terms_match_kernels(caplog: pytest.LogCaptureFixture) -> None:
    """Each cross-section term through the executor equals its kernel on the row's cells, with
    `groupby` codes and the tie-break key (5.4.2, 3.7); a cell of the unknown group -1 is left
    out and counted in the `nexusbt.compute` debug log (`UnknownGroup`, 3.3)."""
    close, opens = [5.0, 1.0, 3.0, N, 2.0, 4.0], [1.0, 1.0, 2.0, 2.0, N, 1.0]
    x = block(close=[close], open=[opens])
    g = OPEN.latest.quantiles(2)  # opens 1, 1, 2, 2, -, 1: mean ranks 2 and 4.5 of n = 5
    s = CLOSE.latest
    terms = [s.rank("average", groupby=g), s.rank(ascending=False, groupby=g), s.zscore(groupby=g),
             s.demean(groupby=g), s.winsorize(0.1, 0.9, groupby=g), s.quantiles(2, groupby=g),
             s.top(1, groupby=g), s.bottom(1, groupby=g), s.percentile_between(0, 50)]  # fmt: skip
    with caplog.at_level("DEBUG", logger="nexusbt.compute"):
        found = values([g, *terms], x)
    assert found[0] == [1, 1, 2, 2, -1, 1]
    c, inside = np.array(close), np.ones(6, dtype=bool)
    ids = [f"I{i}" for i in range(6)]
    groups, tie, order = np.array(found[0], np.int32), xs.tie_order(ids, HASH), xs.sorted_order(ids)
    want: list[Any] = [k.rank(c, inside, groups, tie, k.AVERAGE, k.ASCENDING)[0],
            k.rank(c, inside, groups, tie, k.ORDINAL, k.DESCENDING)[0],
            k.zscore(c, inside, groups, order)[0], k.demean(c, inside, groups, order)[0],
            k.winsorize(c, inside, groups, 0.1, 0.9)[0],
            k.quantiles(c, inside, groups, order, 2)[0],
            k.select(c, inside, groups, tie, 1, k.DESCENDING)[0],
            k.select(c, inside, groups, tie, 1, k.ASCENDING)[0],
            k.percentile_between(c, inside, 0, 50)]  # fmt: skip
    for got, expected in zip(found[1:], want, strict=True):
        assert np.array_equal(np.array(_n(got), dtype=float), expected, equal_nan=True)
    assert "UnknownGroup: rank" in caplog.text
    assert "left out 1 cell(s)" in caplog.text


def test_tiebreak_orders_equal_scores() -> None:
    """An ordinal `rank` of equal scores follows the `[portfolio] tiebreak` key (3.7): `"id"` by
    ascending id, `"hash"` (the default) by the salted hash, which orders I0..I5 as I0, I5, I4,
    I1, I2, I3 (six ids: with three or four the two orders agree)."""
    x = block(close=[[1.0] * 6])
    assert values([CLOSE.latest.rank()], x)[0] == [1.0, 4.0, 5.0, 6.0, 3.0, 2.0]
    by_id = values([CLOSE.latest.rank()], x, tiebreak=TiebreakPolicy.ID)[0]
    assert by_id == [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]


def test_pipeline_screen_unknown_false() -> None:
    """`Pipeline(screen=)` keeps the rows where the screen is true; unknown is false there
    (5.4.1, R3-13): I1 is halted at row 1, so its unknown `~(close > 10_000)` drops it."""
    x = block(close=[[12_000.0, 8_000.0, 9_000.0], [12_000.0, N, 7_000.0]],
              open=[[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])  # fmt: skip
    pipe = Pipeline({"open": OPEN.latest}, screen=~(CLOSE.latest > 10_000))
    terms = [*pipe.columns.values(), *([pipe.screen] if pipe.screen else [])]
    ready = (x.dates + np.timedelta64(16, "h")).astype("datetime64[us]")
    kept = screened(pipe, execute(terms, [0, 1], [(0, 1)], lambda a, b: x, ready))
    assert list(kept) == ["open"]
    assert kept["open"].to_pydict() == {
        "row": [0, 0, 1],
        "instrument_id": ["I1", "I2", "I2"],
        "value": [2.0, 3.0, 6.0],
    }
    unscreened = Pipeline({"open": OPEN.latest})
    whole = screened(unscreened, execute([OPEN.latest], [1], [(0, 1)], lambda a, b: x, ready))
    assert whole["open"]["value"].to_pylist() == [4.0, 5.0, 6.0]
    apart = {**execute(terms[1:], [0, 1], [(0, 1)], lambda a, b: x, ready),
             **execute(terms[:1], [1], [(0, 1)], lambda a, b: x, ready)}  # fmt: skip
    with pytest.raises(ValueError, match="'open' and the screen list different cells"):
        screened(pipe, apart)
