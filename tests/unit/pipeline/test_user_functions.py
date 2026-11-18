"""Window-style user functions (spec 3.3, 5.3.7, 6.5 (5)(6); T1.12, #246): run through the
executor on the windows it adjusts as of their row (#548), E8 for a row outside the window and
a user exception as the user raised it."""

from __future__ import annotations

import functools
import importlib.util
import traceback
import warnings
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pytest

import nexusbt as nx
from nexusbt.compute._executor import Actions, execute
from nexusbt.contracts import SchemaRegistry
from nexusbt.data import DataConfig, open_snapshot
from nexusbt.data._block import MarketBlock
from nexusbt.pipeline import BoundColumn, Factor, Term, bind, graph_hash
from nexusbt.pipeline._terms import l1_disabled
from nexusbt.testing.synth import make_snapshot, write_actions

ID = "KR:T00001"
CLOSE = BoundColumn.of("Price", "close")
#: A 2-for-1 split effective 2020-01-07 (row 3 of the tiny calendar), terms known in advance.
SPLIT = {"event_id": "CA-1", "instrument_id": ID, "kind": "split", "ex_date": "2020-01-07",
         "ts_effective": "2020-01-07T00:00:00Z", "ts_announced": "2019-12-20T07:00:00Z",
         "ratio_num": 2, "ratio_den": 1, "ratio_new_per_old": 2.0, "price_factor": 0.5,
         "share_factor": 2.0, "affects": "split_and_total", "factor_method": "ratio",
         "pay_date_status": "not_applicable", "status": "effective"}  # fmt: skip


def run(at: Path, terms: Sequence[Term], rows: Sequence[int], close: Sequence[float],
        events: Sequence[dict[str, Any]] = ()) -> dict[tuple[int, str], float]:  # fmt: skip
    """Each term's value at `rows` over the tiny KR calendar, one instrument with `close`, the
    `events` known to the snapshot; no function mapping is given, so each user term runs the
    function it was built from."""
    root = make_snapshot(at, preset="tiny", markets=("KR",))
    write_actions(root, list(events))
    snapshot = open_snapshot(DataConfig(path=root))
    calendar, n = snapshot.calendar("KR"), len(close)
    block = MarketBlock("KR", calendar.dates[:n], 0, (ID,), {"close": np.array(close)[:, None]},
                        np.ones((n, 1), bool), np.zeros((n, 1), np.int8),
                        calendar.ts_close[:n, None].copy())  # fmt: skip
    actions = Actions(functools.partial(snapshot.actions, "KR"), calendar.ts_open)
    found = execute(terms, rows, [(0, n - 1)], lambda a, b: block, calendar.ready[:n],
                    actions=actions)  # fmt: skip
    return {(v["row"], key): v["value"] for key, table in found.items()
            for v in table.to_pylist()}  # fmt: skip


def plain(terms: Sequence[Term], rows: Sequence[int], n: int) -> dict[str, Any]:
    """`execute` over `n` sessions of two instruments with closes 100 + row and 1000 + row,
    every bar on time, no corporate actions."""
    dates = np.datetime64("2020-01-01") + np.arange(n).astype("timedelta64[D]")
    ready = (dates + np.timedelta64(16, "h")).astype("datetime64[us]")
    close = np.arange(n)[:, None] + np.array([[100.0, 1000.0]])
    block = MarketBlock("KR", dates, 0, (ID, "KR:T00002"), {"close": close},
                        np.ones((n, 2), bool), np.zeros((n, 2), np.int8),
                        np.repeat(ready[:, None], 2, axis=1))  # fmt: skip
    return execute(terms, rows, [(0, n - 1)], lambda a, b: block, ready)


def _mom_12_1_custom(close: Any) -> Any:
    return close[-22] / close[-273] - 1


def test_out_of_window_index_E8() -> None:  # noqa: N802 - spec 10.1's name
    """5.3.7, 6.6: `close[-273]` in a 253-row window is `WindowError` (E8) naming the function
    and suggesting `window=273`, at the user's line."""
    mom = nx.factor(window=253, inputs=[CLOSE])(_mom_12_1_custom)
    with pytest.raises(nx.WindowError) as caught:
        plain([mom], [260], 261)
    error = caught.value
    assert error.code == "E8"
    assert error.parts["what"] == "_mom_12_1_custom reads close[-273] but window=253"
    assert "@nx.factor(window=273, ...)" in error.parts["fix"]
    assert str(error.at).startswith("test_user_functions.py:")


def _lookup(close: Any) -> Any:
    return {"a": close[-1]}["b"]  # the user's own mistake


def test_user_exception_keeps_user_frame() -> None:
    """6.6, R-42: an exception inside a user function comes out as the user raised it, not
    wrapped and not chained, and the frames a reader sees go from the caller straight to the
    user's line: the engine's are hidden (`__tracebackhide__`)."""
    lookup = nx.factor(window=2, inputs=[CLOSE])(_lookup)
    registry = SchemaRegistry(columns={}, labels={})
    for caller, where in ((lambda: plain([lookup], [3], 4), "plain"),
                          (lambda: bind(lookup, registry), None)):  # fmt: skip
        with pytest.raises(KeyError) as caught:
            caller()
        error = caught.value
        assert error.args == ("b",)
        assert error.__cause__ is None
        assert not error.__suppress_context__
        tb, shown = error.__traceback__, []
        while tb is not None:
            if not tb.tb_frame.f_locals.get("__tracebackhide__"):
                shown.append(traceback.extract_tb(tb, limit=1)[0])
            tb = tb.tb_next
        assert [frame.name for frame in shown] == [
            "test_user_exception_keeps_user_frame", "<lambda>", *([where] if where else []),
            "_lookup",
        ]  # fmt: skip
        assert shown[-1].line == 'return {"a": close[-1]}["b"]  # the user\'s own mistake'


def test_user_exception_carries_layer_and_fix_notes() -> None:
    """6.6 "User function exceptions": the executor adds the `layer` line at the user's line
    and a `fix` line naming an instrument and the row's date to reproduce it (`add_note`, the
    helper of T0.4b, #52), the exception still the user's."""
    stale = nx.factor(window=2, inputs=[CLOSE])(_stale)
    with pytest.raises(RuntimeError) as caught:
        plain([stale], [3], 4)
    assert caught.value.args == ("stale state",)
    line = _stale.__code__.co_firstlineno + 1
    assert caught.value.__notes__ == [
        f"  layer  your code — test_user_functions.py:{line} in _stale",
        f"  fix    check _stale at test_user_functions.py:{line}; reproduce with"
        f" nx.explain(strategy, '{ID}', '2020-01-04')",
    ]


def _stale(close: Any) -> Any:
    raise RuntimeError("stale state")  # no hint in errors/hints.toml: the general sentence


def _is_up(close: Any) -> Any:
    return close[-1] > close[0]


def test_a_result_of_another_dtype_is_E8() -> None:  # noqa: N802 - E8 is a code
    """5.3.7: `@nx.factor` returns float64; a bool result is E8, not a Factor of 1.0 and 0.0."""
    up = nx.factor(window=2, inputs=[CLOSE])(_is_up)
    with pytest.raises(nx.WindowError, match=r"returned bool \(2,\), not float64 \(2,\)"):
        plain([up], [3], 4)


def _scaled(by: Any) -> Term:
    def scaled(close: Any) -> Any:
        return close[-1] * by[0]

    with pytest.warns(UserWarning, match=r"\[E24\]"):  # a closure over an array is E24 too
        return nx.factor(window=2, inputs=[CLOSE])(scaled)


def test_one_hash_for_two_functions_is_refused() -> None:
    """Two user terms whose functions differ only in a non-constant value they read have one
    graph hash (6.5 (6) hashes constants only), so one run cannot tell them apart: it refuses
    them rather than give both the values of one. Built twice from the same values, they run."""
    with pytest.raises(ValueError, match="scaled"):
        plain([_scaled(np.array([1.0])), _scaled(np.array([2.0]))], [3], 4)
    by = np.array([2.0])
    got = plain([_scaled(by), _scaled(by)], [3], 4)
    assert got[graph_hash(_scaled(by))]["value"].to_pylist() == [206.0, 2006.0]
    copies = [_copy_a(), _copy_b()]  # one source written twice: one hash, one computation
    assert graph_hash(copies[0]) == graph_hash(copies[1])
    assert plain(copies, [3], 4)[graph_hash(copies[0])]["value"].to_pylist() == [103.0, 1003.0]


def _copy_a() -> Term:
    def last(close: Any) -> Any:
        return close[-1]

    return nx.factor(window=2, inputs=[CLOSE])(last)


def _copy_b() -> Term:
    def last(close: Any) -> Any:
        return close[-1]

    return nx.factor(window=2, inputs=[CLOSE])(last)


def _list_index(close: Any) -> Any:
    return close[-1] + [0.0][5]


def test_an_index_error_outside_the_window_is_the_users() -> None:
    """3.3: only a row before the window is E8; another `IndexError` is the user's, as raised.
    A user term built without a function (by hand, not by `@nx.factor`) is refused."""
    with pytest.raises(IndexError, match="list index out of range"):
        plain([nx.factor(window=2, inputs=[CLOSE])(_list_index)], [3], 4)
    built = nx.factor(window=2, inputs=[CLOSE])(_first)
    bare = Factor(built.op, built.inputs, built.params)
    with pytest.raises(ValueError, match="no function given for the user term _first"):
        plain([bare], [3], 4)


def _width(close: Any) -> Any:
    """The number of columns the window holds, in each column."""
    return np.full(close.shape[1], float(close.shape[1]))


def test_mask_is_the_domain_the_function_computes_on() -> None:
    """3.3 `mask`: the function gets the window of the columns its mask is true at, and the
    cells outside the mask are NaN."""
    width = nx.factor(window=2, inputs=[CLOSE], mask=CLOSE.latest > 500)(_width)
    rows = plain([width], [3], 4)[graph_hash(width)].to_pylist()
    assert [r["instrument_id"] for r in rows] == [ID, "KR:T00002"]
    assert np.isnan(rows[0]["value"])
    assert rows[1]["value"] == 1.0


def test_out_of_window_index_E8_when_the_graph_is_built() -> None:  # noqa: N802 - E8 is a code
    """6.5 (5): binding the graph calls each user function once on `(W, 3)` windows of 1.0, so
    `close[-273]` in a 253-row window is E8 before any data is read; a function that keeps to
    its window binds, and so does a graph holding it twice."""
    mom = nx.factor(window=253, inputs=[CLOSE])(_mom_12_1_custom)
    with pytest.raises(nx.WindowError, match=r"@nx.factor\(window=273, \.\.\.\)"):
        bind(mom.rank(), SchemaRegistry(columns={}, labels={}))
    first = nx.factor(window=3, inputs=[CLOSE])(_first)
    bind(nx.Pipeline({"a": first, "b": first.rank()}), SchemaRegistry(columns={}, labels={}))


def _first(close: Any) -> Any:
    return close[0]


def test_window_is_asof_adjusted(tmp_path: Path) -> None:
    """5.3.7 and 3.3: across the 2-for-1 split at row 3 the window row 4 reads holds the earlier
    closes on row 4's basis, 100 → 50, through the executor's column windows (#548); row 2's
    window, before the split, holds them as they are."""
    first = nx.factor(window=3, inputs=[CLOSE])(_first)
    got = run(tmp_path, [first], [2, 4], [100.0, 100.0, 100.0, 50.0, 50.0], [SPLIT])
    assert got[2, graph_hash(first)] == 100.0
    assert got[4, graph_hash(first)] == 50.0


USER_FILE = """
import numpy as np
import nexusbt as nx
from nexusbt.pipeline import BoundColumn

LIMIT = 3

def _inner(x):
    return x * {inner}

def _helper(x):
    return _inner(x) + LIMIT

@nx.factor(window=2, inputs=[BoundColumn.of("Price", "close")])
def score(close):
    return _helper(close[-1])
"""


def user_module(at: Path, name: str, inner: str = "2") -> Any:
    """A strategy file of the user's project, imported as a module: `score` calls `_helper`,
    which calls `_inner`, whose body has `inner` in it."""
    path = at / f"{name}.py"
    path.write_text(USER_FILE.format(inner=inner))
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_source_hash_includes_helpers(tmp_path: Path) -> None:
    """6.5 (6): the helpers a user function calls inside the project, followed through
    `co_names` to any depth, go into its source hash, so changing a helper's body changes the
    hash; the same files give the same hash."""
    same = [user_module(tmp_path, f"same_{i}").score for i in range(2)]
    assert graph_hash(same[0]) == graph_hash(same[1])
    changed = user_module(tmp_path, "changed", inner="5").score
    assert graph_hash(changed) != graph_hash(same[0])


def _momentum(close: Any, *, n: int = 21) -> Any:
    return close[-1] / close[-1 - n] - 1


def test_keyword_binding_makes_a_new_factor() -> None:
    """3.3: `f(n=63)` is a new Factor whose value is in the graph hash and in the call; the
    same binding twice is one hash; a name the function does not take, a value that is not
    constant-like, and calling a Factor that is not a user function are refused."""
    mom = nx.factor(window=70, inputs=[CLOSE])(_momentum)
    mom63 = mom(n=63)
    assert isinstance(mom63, Factor)
    assert graph_hash(mom63) == graph_hash(mom(n=63)) != graph_hash(mom)
    got = plain([mom, mom63], [69], 70)
    assert got[graph_hash(mom63)]["value"].to_pylist()[0] == pytest.approx(169 / 106 - 1)
    assert got[graph_hash(mom)]["value"].to_pylist()[0] == pytest.approx(169 / 148 - 1)
    bind(mom63, SchemaRegistry(columns={}, labels={}))
    with pytest.raises(TypeError, match="_momentum takes no keyword 'm'"):
        mom(m=1)
    with pytest.raises(TypeError, match="constant-like"):
        mom(n=np.int64(63))
    with pytest.raises(TypeError, match="only a user function"):
        CLOSE.latest(n=1)


WEIGHTS = np.array([0.5, 2.0])
THRESHOLD = 10


def _weighted(close: Any) -> Any:
    return close[-1] * WEIGHTS[0] + THRESHOLD


def _from_file(close: Any) -> Any:
    with open("weights.txt") as f:  # the call 6.5 (6) names
        return close[-1] * float(f.read())


def _pure(close: Any) -> Any:
    return np.nanmean(close, axis=0) + THRESHOLD


def test_global_array_read_E24_disables_l1() -> None:  # noqa: N802 - spec 10.1's name
    """6.5 (6), 5.3.7, 5.3.9: reading a global array, or opening a file, is
    `ImpureFunctionWarning` (E24) naming the function and the global, and turns off the L1 cache
    of that node and of the nodes that read it; a constant global (`THRESHOLD`) and numpy's
    functions are not E24, and a graph without such a node keeps L1."""
    with pytest.warns(UserWarning, match=r"\[E24\]") as caught:
        weighted = nx.factor(window=2, inputs=[CLOSE])(_weighted)
    (warning,) = caught
    text = str(warning.message)
    assert text.startswith("ImpureFunctionWarning [E24]")
    assert "_weighted reads global 'WEIGHTS'; the engine cannot check what it contains" in text
    assert "L1 cache disabled for node _weighted" in text
    with pytest.warns(UserWarning, match="_from_file reads global 'open'"):
        nx.factor(window=2, inputs=[CLOSE])(_from_file)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        pure = nx.factor(window=2, inputs=[CLOSE])(_pure)
    assert l1_disabled(weighted)
    assert l1_disabled(weighted.rank() + pure)  # a node below it
    assert not l1_disabled(pure.rank())
