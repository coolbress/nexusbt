"""Spec 3.3, 5.3.7, 6.5 (5)(6), #620: `@nx.filter`, a Filter from a window function returning
bool; its cell unknown where any cell of the instrument's input windows is NaN (Decisions
2026-11-20), and the checks `@nx.factor` has."""

from __future__ import annotations

import traceback
from collections.abc import Sequence
from typing import Any

import numpy as np
import pytest

import nexusbt as nx
from nexusbt.compute._executor import execute
from nexusbt.contracts import ConfigError, SchemaRegistry
from nexusbt.data._block import MarketBlock
from nexusbt.pipeline import BoundColumn, Filter, Term, bind, graph_hash
from nexusbt.pipeline._terms import l1_disabled

IDS = ("KR:T00001", "KR:T00002")
CLOSE = BoundColumn.of("Price", "close")


def run(terms: Sequence[Term], row: int, close: Sequence[Sequence[float]]) -> dict[str, list[Any]]:
    """Each term's values at `row`, one per instrument in `IDS` order, over sessions whose
    closes are `close` (a row per session, a column per instrument), every bar on time."""
    closes = np.array(close, dtype=np.float64)
    n = len(closes)
    dates = np.datetime64("2020-01-01") + np.arange(n).astype("timedelta64[D]")
    ready = (dates + np.timedelta64(16, "h")).astype("datetime64[us]")
    on_time = np.repeat(ready[:, None], 2, axis=1)
    block = MarketBlock("KR", dates, 0, IDS, {"close": closes}, np.ones((n, 2), bool),
                        np.zeros((n, 2), np.int8), on_time)  # fmt: skip
    found = execute(terms, [row], [(0, n - 1)], lambda a, b: block, ready)
    return {key: [v["value"] for v in table.to_pylist()] for key, table in found.items()}


def _up(close: Any) -> Any:
    return close[-1] > close[0]


def _over(close: Any, *, level: float = 100.0) -> Any:
    return close[-1] > level


UP = nx.filter(window=2, inputs=[CLOSE])(_up)


def test_a_call_with_an_array_names_function() -> None:
    """AC 1 (#582's criterion for a filter): a call with an array is E16 whose fix is the
    `.function` call to type, with the values the Filter has bound."""
    assert isinstance(UP, Filter)
    for term, shown in ((UP, "_up.function(close)"),
                        (nx.filter(window=2, inputs=[CLOSE])(_over)(level=5.0),
                         "_over.function(close, level=5.0)")):  # fmt: skip
        with pytest.raises(ConfigError) as caught:
            term(np.ones((2, 2)))
        assert caught.value.code == "E16"
        assert caught.value.parts["fix"] == f"{shown} on the arrays, one for each input"
        assert caught.value.parts["what"].endswith("binds keyword values and makes a Filter")


def test_function_runs_alone_as_the_executor_does() -> None:
    """AC 2: `f.function` on the window the executor gives a row returns that row's values."""
    close = [[100.0, 50.0], [101.0, 40.0], [99.0, 45.0]]
    got = run([UP], 2, close)[graph_hash(UP)]
    assert UP.function is not None
    assert UP.function(np.array(close[1:])).tolist() == got == [False, True]


def test_a_cell_is_unknown_where_an_input_window_holds_nan() -> None:
    """AC 7 (Decisions 2026-11-20): a NaN anywhere in an instrument's input window makes its
    cell unknown, though the function answered for it; `~f` keeps it unknown, and
    `f.fillna(False)` makes it false."""
    close = [[100.0, np.nan], [101.0, 60.0], [102.0, 70.0]]  # the second's NaN is in row 2's window
    terms = [UP, ~UP, UP.fillna(False)]
    found = run(terms, 1, close)
    assert [found[graph_hash(t)] for t in terms] == [[True, None], [False, None], [True, False]]
    assert run([UP], 2, close)[graph_hash(UP)] == [True, True]  # the NaN has left the window


def _reads_back(close: Any) -> Any:
    return close[-3] > 0


def test_a_row_before_the_window_is_E8_at_run_and_at_bind() -> None:  # noqa: N802 - E8 is a code
    """AC 4, 5.3.7 and 6.5 (5): an index before the window is E8 naming `@nx.filter` and the
    window it needs, when the graph is bound (windows of 1.0) and when it runs."""
    back = nx.filter(window=2, inputs=[CLOSE])(_reads_back)
    for go in (lambda: bind(back, SchemaRegistry(columns={})),
               lambda: run([back], 2, [[1.0, 1.0]] * 3)):  # fmt: skip
        with pytest.raises(nx.WindowError) as caught:
            go()
        assert caught.value.code == "E8"
        assert caught.value.parts["what"] == "_reads_back reads close[-3] but window=2"
        assert caught.value.parts["where"] == "filter _reads_back"
        assert "@nx.filter(window=3, ...)" in caught.value.parts["fix"]


def _as_float(close: Any) -> Any:
    return (close[-1] > close[0]).astype(np.float64)


def _one_number(close: Any) -> Any:
    return close[-1, :1] > 0


@pytest.mark.parametrize(("fn", "said"), [
    (_as_float, r"returned float64 \(2,\), not bool \(2,\)"),
    (_one_number, r"returned bool \(1,\), not bool \(2,\)"),
])  # fmt: skip
def test_a_result_of_another_dtype_or_shape_is_E8(fn: Any, said: str) -> None:  # noqa: N802
    """AC 4, Decisions 2026-11-27: a filter's function returns bool `(n_alive,)`; a float, even
    of 1.0 and 0.0, or another shape is E8."""
    term = nx.filter(window=2, inputs=[CLOSE])(fn)
    with pytest.raises(nx.WindowError, match=said) as caught:
        run([term], 2, [[1.0, 2.0]] * 3)
    assert caught.value.parts["fix"] == "return one bool for each column of the window"


LEVELS = np.array([100.0])


def _over_global(close: Any) -> Any:
    return close[-1] > LEVELS[0]


def test_a_global_array_is_E24_with_l1_off() -> None:  # noqa: N802 - E24 is a code
    """AC 4, 6.5 (6): a read of a non-constant global is E24 and turns the L1 cache off."""
    with pytest.warns(UserWarning, match=r"_over_global reads global 'LEVELS'"):
        term = nx.filter(window=2, inputs=[CLOSE])(_over_global)
    assert l1_disabled(term)
    assert not l1_disabled(UP)


def _level() -> float:
    return 100.0


def _other_level() -> float:
    return 200.0


def _over_helper(close: Any) -> Any:
    return close[-1] > _level()


def test_helpers_and_bound_values_are_in_the_graph_hash(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC 4, 6.5 (6): a bound keyword value and a helper's source go into the graph hash, so
    another value, or a helper with another body under the same name, is another hash."""
    over = nx.filter(window=2, inputs=[CLOSE])(_over)
    assert len({graph_hash(over(level=1.0)), graph_hash(over(level=2.0)), graph_hash(over)}) == 3
    before = graph_hash(nx.filter(window=2, inputs=[CLOSE])(_over_helper))
    monkeypatch.setitem(globals(), "_level", _other_level)
    assert graph_hash(nx.filter(window=2, inputs=[CLOSE])(_over_helper)) != before


def _lookup(close: Any) -> Any:
    return {"a": close[-1] > 0}["b"]  # the user's own mistake


def test_a_user_exception_keeps_the_users_frame() -> None:
    """AC 4, R-42: the user's exception comes out as raised, its last shown frame the user's."""
    term = nx.filter(window=2, inputs=[CLOSE])(_lookup)
    with pytest.raises(KeyError) as caught:
        run([term], 2, [[1.0, 2.0]] * 3)
    assert caught.value.args == ("b",)
    tb, shown = caught.value.__traceback__, []
    while tb is not None:
        if not tb.tb_frame.f_locals.get("__tracebackhide__"):
            shown.append(traceback.extract_tb(tb, limit=1)[0])
        tb = tb.tb_next
    assert shown[-1].name == "_lookup"


def test_a_filter_decorates_a_function_only() -> None:
    """As `@nx.factor` does: a callable that is not a plain function is refused."""
    with pytest.raises(TypeError, match=r"@nx\.filter decorates a function, not builtin"):
        nx.filter(window=2, inputs=[CLOSE])(len)
