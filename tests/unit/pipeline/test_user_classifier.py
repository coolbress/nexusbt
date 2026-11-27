"""Spec 3.3, 5.3.7, 6.5 (5)(6), #620: `@nx.classifier`, a Classifier from a window function
returning integer codes, -1 the missing group (Decisions 2026-11-20, 2026-11-27); a str result
is E8 until #818 builds its code table."""

from __future__ import annotations

import traceback
from collections.abc import Sequence
from typing import Any, cast

import numpy as np
import pytest

import nexusbt as nx
from nexusbt.compute._executor import Counts, execute
from nexusbt.contracts import ConfigError, SchemaRegistry
from nexusbt.data._block import MarketBlock
from nexusbt.pipeline import BoundColumn, Classifier, Term, bind, graph_hash
from nexusbt.pipeline._terms import l1_disabled

IDS = ("KR:T00001", "KR:T00002", "KR:T00003")
CLOSE = BoundColumn.of("Price", "close")


def run(terms: Sequence[Term], row: int, close: Sequence[Sequence[float]],
        counts: Counts | None = None) -> dict[str, list[Any]]:  # fmt: skip
    """Each term's values at `row`, one per instrument in `IDS` order, over sessions whose
    closes are `close` (a row per session, a column per instrument), every bar on time."""
    closes = np.array(close, dtype=np.float64)
    n = len(closes)
    dates = np.datetime64("2020-01-01") + np.arange(n).astype("timedelta64[D]")
    ready = (dates + np.timedelta64(16, "h")).astype("datetime64[us]")
    on_time = np.repeat(ready[:, None], 3, axis=1)
    block = MarketBlock("KR", dates, 0, IDS, {"close": closes}, np.ones((n, 3), bool),
                        np.zeros((n, 3), np.int8), on_time)  # fmt: skip
    found = execute(terms, [row], [(0, n - 1)], lambda a, b: block, ready, counts=counts)
    return {key: [v["value"] for v in table.to_pylist()] for key, table in found.items()}


CLOSES = [[100.0, 50.0, 10.0], [110.0, 40.0, 10.0], [120.0, 45.0, 10.0]]


def _side(close: Any) -> Any:
    """0 for a fall, 1 for a rise, -1 (the missing group) where the close did not move."""
    moved = np.sign(close[-1] - close[0]).astype(np.int64)
    return np.where(moved == 0, -1, (moved + 1) // 2)


def _shifted(close: Any, *, by: int = 0) -> Any:
    return np.zeros(close.shape[1], dtype=np.int64) + by


SIDE = nx.classifier(window=2, inputs=[CLOSE])(_side)


def test_a_call_with_an_array_names_function() -> None:
    """AC 1 (#582's criterion for a classifier): a call with an array is E16 whose fix is the
    `.function` call to type, with the values the Classifier has bound."""
    assert isinstance(SIDE, Classifier)
    for term, shown in ((SIDE, "_side.function(close)"),
                        (nx.classifier(window=2, inputs=[CLOSE])(_shifted)(by=2),
                         "_shifted.function(close, by=2)")):  # fmt: skip
        with pytest.raises(ConfigError) as caught:
            term(np.ones((2, 3)))
        assert caught.value.code == "E16"
        assert caught.value.parts["fix"] == f"{shown} on the arrays, one for each input"
        assert caught.value.parts["what"].endswith("binds keyword values and makes a Classifier")


def test_function_runs_alone_as_the_executor_does() -> None:
    """AC 2: `f.function` on the window the executor gives a row returns that row's codes."""
    got = run([SIDE], 2, CLOSES)[graph_hash(SIDE)]
    assert SIDE.function is not None
    assert SIDE.function(np.array(CLOSES[1:])).tolist() == got == [1, 1, -1]


def test_the_missing_group_is_left_out_and_counted() -> None:
    """Last AC, its int half: -1 is the missing group, left out by `groupby` and counted
    `UnknownGroup` at the term grouped by it."""
    demeaned = CLOSE.latest.demean(groupby=SIDE)
    counts: Counts = {}
    got = run([demeaned], 2, CLOSES, counts)[graph_hash(demeaned)]
    assert got[2] is None or np.isnan(got[2])
    assert counts == {(2, graph_hash(demeaned), "UnknownGroup"): 1}


def test_outside_the_mask_and_before_the_window_is_the_missing_group() -> None:
    """Decisions 2026-11-27: a cell outside `mask`, or on a row whose window starts before the
    axis, is the missing group (-1), as a Factor's is NaN and a Filter's unknown there."""
    masked = nx.classifier(window=2, inputs=[CLOSE], mask=CLOSE.latest > 20)(_shifted)(by=3)
    assert run([masked], 2, CLOSES)[graph_hash(masked)] == [3, 3, -1]
    assert run([SIDE], 0, CLOSES)[graph_hash(SIDE)] == [-1, -1, -1]


def _reads_back(close: Any) -> Any:
    return (close[-3] > 0).astype(np.int64)


def test_a_row_before_the_window_is_E8_at_run_and_at_bind() -> None:  # noqa: N802 - E8 is a code
    """AC 4, 5.3.7 and 6.5 (5): an index before the window is E8 naming `@nx.classifier` and
    the window it needs, when the graph is bound (windows of 1.0) and when it runs."""
    back = nx.classifier(window=2, inputs=[CLOSE])(_reads_back)
    for go in (lambda: bind(back, SchemaRegistry(columns={})), lambda: run([back], 2, CLOSES)):
        with pytest.raises(nx.WindowError) as caught:
            go()
        assert caught.value.code == "E8"
        assert caught.value.parts["what"] == "_reads_back reads close[-3] but window=2"
        assert caught.value.parts["where"] == "classifier _reads_back"
        assert "@nx.classifier(window=3, ...)" in caught.value.parts["fix"]


def _as_float(close: Any) -> Any:
    return np.zeros(close.shape[1])


def _as_bool(close: Any) -> Any:
    return close[-1] > 0


def _as_str(close: Any) -> Any:
    return np.array(["a"] * close.shape[1])


def _below_missing(close: Any) -> Any:
    return np.full(close.shape[1], -2, dtype=np.int64)


def _too_large(close: Any) -> Any:
    return np.full(close.shape[1], 2**31, dtype=np.int64)


def _two_rows(close: Any) -> Any:
    return np.zeros(close.shape, dtype=np.int64)


@pytest.mark.parametrize(("fn", "said"), [
    (_as_float, r"returned float64 \(3,\), not an integer \(3,\)"),
    (_as_bool, r"returned bool \(3,\), not an integer \(3,\)"),
    (_as_str, r"returned <U1 \(3,\), not an integer \(3,\)"),
    (_below_missing, r"returned the code -2, which no code table has"),
    (_too_large, r"returned the code 2147483648, which no code table has"),
    (_two_rows, r"returned int64 \(2, 3\), not an integer \(3,\)"),
])  # fmt: skip
def test_a_result_that_is_no_code_is_E8(fn: Any, said: str) -> None:  # noqa: N802 - E8 is a code
    """AC 4, last AC, Decisions 2026-11-27: a classifier's function returns an integer type; a
    float, a bool, or a str until #818, is E8, and so is a negative code other than -1 or one
    an int32 code cannot hold."""
    term = nx.classifier(window=2, inputs=[CLOSE])(fn)
    with pytest.raises(nx.WindowError, match=said):
        run([term], 2, CLOSES)


GROUPS = np.array([0, 1, 1])


def _from_global(close: Any) -> Any:
    return GROUPS[: close.shape[1]]


def test_a_global_array_is_E24_with_l1_off() -> None:  # noqa: N802 - E24 is a code
    """AC 4, 6.5 (6): a read of a non-constant global is E24 and turns the L1 cache off."""
    with pytest.warns(UserWarning, match=r"_from_global reads global 'GROUPS'"):
        term = nx.classifier(window=2, inputs=[CLOSE])(_from_global)
    assert l1_disabled(term)
    assert not l1_disabled(SIDE)


def _group() -> int:
    return 1


def _other_group() -> int:
    return 2


def _by_helper(close: Any) -> Any:
    return np.full(close.shape[1], _group(), dtype=np.int64)


def test_helpers_and_bound_values_are_in_the_graph_hash(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC 4, 6.5 (6): a bound keyword value and a helper's source go into the graph hash."""
    shifted = nx.classifier(window=2, inputs=[CLOSE])(_shifted)
    assert len({graph_hash(shifted(by=1)), graph_hash(shifted(by=2)), graph_hash(shifted)}) == 3
    before = graph_hash(nx.classifier(window=2, inputs=[CLOSE])(_by_helper))
    monkeypatch.setitem(globals(), "_group", _other_group)
    assert graph_hash(nx.classifier(window=2, inputs=[CLOSE])(_by_helper)) != before


def _lookup(close: Any) -> Any:
    return {"a": 1}["b"]  # the user's own mistake


def test_a_user_exception_keeps_the_users_frame() -> None:
    """AC 4, R-42: the user's exception comes out as raised, its last shown frame the user's."""
    term = nx.classifier(window=2, inputs=[CLOSE])(_lookup)
    with pytest.raises(KeyError) as caught:
        run([term], 2, CLOSES)
    tb, shown = caught.value.__traceback__, []
    while tb is not None:
        if not tb.tb_frame.f_locals.get("__tracebackhide__"):
            shown.append(traceback.extract_tb(tb, limit=1)[0])
        tb = tb.tb_next
    assert shown[-1].name == "_lookup"


def test_a_nan_input_keeps_what_the_function_returned() -> None:
    """Decisions 2026-11-20: unlike a filter's, a classifier's cell is the function's code for a
    NaN in its input window; a missing group is left out where it is used."""
    close = [[100.0, np.nan, 10.0], [110.0, 40.0, 10.0], [120.0, 45.0, 10.0]]
    shifted = nx.classifier(window=2, inputs=[CLOSE])(_shifted)(by=4)
    assert run([shifted], 1, close)[graph_hash(shifted)] == [4, 4, 4]


def _negative(close: Any) -> Any:
    return close[-1] < 0


def test_the_missing_group_is_one_value_to_a_term_reading_it() -> None:
    """Fresh-context review: a cell the function made -1 and one outside the mask both reach a
    term reading the classifier as -1, as a built-in classifier's do, never as NaN."""
    masked = nx.classifier(window=2, inputs=[CLOSE], mask=CLOSE.latest < 105)(_side)
    reader = nx.filter(window=1, inputs=[cast(Any, masked)])(_negative)  # off the signature
    assert run([masked], 2, CLOSES)[graph_hash(masked)] == [-1, 1, -1]
    assert run([reader], 2, CLOSES)[graph_hash(reader)] == [True, False, True]


def test_an_unreadable_source_names_classifier() -> None:
    """Fresh-context review: the refusal of a function with no source file names the decorator."""
    space: dict[str, Any] = {}
    exec(compile("def made(close):\n    return close[-1]\n", "<string>", "exec"), space)  # noqa: S102
    with pytest.raises(TypeError, match=r"@nx\.classifier cannot read the source of made"):
        nx.classifier(window=1, inputs=[CLOSE])(space["made"])


def test_a_classifier_decorates_a_function_only() -> None:
    """As `@nx.factor` does: a callable that is not a plain function is refused."""
    with pytest.raises(TypeError, match=r"@nx\.classifier decorates a function, not builtin"):
        nx.classifier(window=2, inputs=[CLOSE])(len)
