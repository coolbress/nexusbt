"""Window-style user functions (spec 3.3, 5.3.7, 6.5 (5)(6); T1.12, #246): run through the
executor on the windows it adjusts as of their row (#548), E8 for a row outside the window and
a user exception as the user raised it."""

from __future__ import annotations

import functools
import importlib.util
import sys
import traceback
import warnings
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pytest

import nexusbt as nx
from nexusbt.compute._executor import Actions, execute
from nexusbt.contracts import ConfigError, SchemaRegistry
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


def _scaled(by: Any) -> Factor:
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


def test_one_hash_for_two_functions_under_an_operation_is_refused() -> None:
    """#562: the two terms are refused wherever they sit, under `top`, under `&` or as a
    `mask`, in either order; built from the same value, each under `top(1)`, they still run."""
    plus, minus = _scaled(np.array([1.0])), _scaled(np.array([-1.0]))
    for terms in ([plus.top(1), minus.top(1)], [minus.top(1), plus.top(1)],
                  [plus.top(1) & minus.top(1)], [plus.top(1, mask=minus.top(1))]):  # fmt: skip
        with pytest.raises(ValueError, match="scaled share one graph hash"):
            plain(terms, [3], 4)
    by = np.array([-1.0])
    alone = plain([_scaled(by).top(1)], [3], 4)
    together = plain([_scaled(by).top(1), _scaled(by).top(1)], [3], 4)
    assert together == alone
    assert alone[graph_hash(_scaled(by).top(1))]["value"].to_pylist() == [True, False]


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


#: A file of the user's project: `score` calls `_helper`, which calls `_inner` (`{inner}`).
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


def load(at: Path, name: str, text: str) -> Any:
    """`text` as a file of the user's project, imported (and in `sys.modules`, as `import` does)."""
    path = at / f"{name}.py"
    path.write_text(text)
    unique = f"{name}_{abs(hash(str(at)))}"
    spec = importlib.util.spec_from_file_location(unique, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[unique] = module
    spec.loader.exec_module(module)
    return module


def test_source_hash_includes_helpers(tmp_path: Path) -> None:
    """6.5 (6): the helpers a user function calls inside the project, followed to any depth,
    go into its source hash, so changing a helper's body changes the hash; the same files give
    the same hash."""
    same = [load(tmp_path, f"same_{i}", USER_FILE.format(inner=2)).score for i in range(2)]
    assert graph_hash(same[0]) == graph_hash(same[1])
    changed = load(tmp_path, "changed", USER_FILE.format(inner=5)).score
    assert graph_hash(changed) != graph_hash(same[0])
    looped = [nx.factor(window=2, inputs=[CLOSE])(_halve) for _ in "ab"]
    assert graph_hash(looped[0]) == graph_hash(looped[1])  # a recursive function walked once


def _halve(close: Any, k: int = 3) -> Any:
    return close[-1] if k == 0 else _halve(close / 2, k - 1)


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
    with pytest.raises(TypeError, match="_momentum takes no keyword 'close'"):
        mom(close=3)  # the window of an input, not a parameter
    with pytest.raises(TypeError, match="constant-like"):
        mom(n=np.int64(63))
    with pytest.raises(TypeError, match="only a user function"):
        CLOSE.latest(n=1)


def test_function_runs_alone_as_the_executor_does() -> None:
    """3.3 (#582): `f.function` is the plain function, unbound; on the window the executor
    gives row 69 it returns that row's values, the bound value passed by hand. `f(n=63)`'s
    `function` is the same unbound one, so it computes with the default n, not 63."""
    mom = nx.factor(window=70, inputs=[CLOSE])(_momentum)
    mom63 = mom(n=63)
    window = np.arange(70)[:, None] + np.array([[100.0, 1000.0]])  # `plain`'s closes
    got = plain([mom, mom63], [69], 70)
    assert mom.function is not None
    assert mom63.function is mom.function
    assert mom.function(window).tolist() == got[graph_hash(mom)]["value"].to_pylist()
    assert mom.function(window, n=63).tolist() == got[graph_hash(mom63)]["value"].to_pylist()
    assert mom63.function(window).tolist() == mom.function(window).tolist()
    assert mom63.function(window)[0] == pytest.approx(169 / 148 - 1) != 169 / 106 - 1


def _ratio(close: Any, volume: Any, *, lag: int = 1, how: str = "mean") -> Any:
    return close[-1] / volume[-1 - lag]


@pytest.mark.parametrize(
    ("make", "shown"),
    [
        (lambda f: f, "_momentum.function(close)"),
        (lambda f: f(n=63), "_momentum.function(close, n=63)"),
    ],
)
def test_a_call_with_an_array_names_function(make: Any, shown: str) -> None:
    """3.3 (#582): a call with a positional argument is E16, and its fix is the `.function`
    call to type, with the values the Factor has bound."""
    term = make(nx.factor(window=70, inputs=[CLOSE])(_momentum))
    with pytest.raises(ConfigError) as caught:
        term(np.ones((70, 2)))
    assert caught.value.parts["fix"] == f"{shown} on the arrays, one for each input"
    assert caught.value.parts["what"].startswith("_momentum was called with an array")


def test_a_call_with_arrays_names_every_input() -> None:
    """Two inputs, two windows in the call to type; bound values by name, as the hash keeps
    them."""
    volume = BoundColumn.of("Price", "volume")
    ratio = nx.factor(window=3, inputs=[CLOSE, volume])(_ratio)(lag=2, how="last")
    with pytest.raises(ConfigError) as caught:
        ratio(np.ones((3, 2)), np.ones((3, 2)))
    assert caught.value.parts["fix"] == (
        "_ratio.function(close, volume, how='last', lag=2) on the arrays, one for each input"
    )
    with pytest.raises(ConfigError) as caught:  # a keyword of the same call is kept, and wins
        ratio(np.ones((3, 2)), np.ones((3, 2)), lag=5)
    assert caught.value.parts["fix"].startswith("_ratio.function(close, volume, how='last', lag=5)")


WEIGHTS = np.array([0.5, 2.0])
THRESHOLD = 10
nanmean = 7  # the name of an attribute `_pure` reads (`np.nanmean`), not a global it reads


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
    assert dict(pure.params)["captured"] == (("THRESHOLD", 10),)  # not ("nanmean", 7)
    assert l1_disabled(weighted)
    assert l1_disabled(weighted.rank() + pure)  # a node below it
    assert not l1_disabled(pure.rank() + pure)  # a node read twice is walked once


SETTINGS = """
import functools
import numpy as np

W = np.array([1.0])
LIMIT = {limit}
SCALE = functools.partial(np.multiply, W)

class Cfg:
    W = np.array([1.0])
    LIMIT = {limit}

def score(close):  # reads `cfg`, set from outside: the project module above, as `import`
    return close[-1] * cfg.{read} + cfg.LIMIT
"""


def test_reads_through_a_project_module_or_class(tmp_path: Path) -> None:
    """6.5 (6) through a module or a class of the project: a constant attribute is in the hash
    (`cfg.LIMIT = 10 → 20` changes it), an array attribute, a class's array and a callable
    object holding an array (`functools.partial`) are E24."""
    hashes = []
    for limit in (10, 20):
        cfg = load(tmp_path, f"settings_{limit}", SETTINGS.format(limit=limit, read="LIMIT"))
        cfg.cfg = cfg
        hashes.append(graph_hash(nx.factor(window=2, inputs=[CLOSE])(cfg.score)))
    assert hashes[0] != hashes[1]
    for read, shown in (("W[0]", "cfg.W"), ("Cfg.W[0]", "cfg.Cfg.W"),
                        ("SCALE(1.0)[0]", "cfg.SCALE")):  # fmt: skip
        cfg = load(tmp_path, "settings", SETTINGS.format(limit=10, read=read))
        cfg.cfg = cfg
        with pytest.warns(UserWarning, match=f"reads global .*'{shown}'"):
            assert l1_disabled(nx.factor(window=2, inputs=[CLOSE])(cfg.score))


WRAPPED = """
import functools
import numba

def _logged(f):
    @functools.wraps(f)
    def inner(*args):
        return f(*args){inner}
    return inner

{decorator}
def _helper(x):
    return x * {k}

def score(close):
    return _helper(close[-1])
"""


def _wrapped_hash(at: Path, name: str, decorator: str, k: int, inner: str = "") -> str:
    """The graph hash of `score`, which calls `_helper` with `decorator` and body `x * k`, the
    `_logged` decorator's inner function ending in `inner`; no warning (a wrapped helper is not
    E24)."""
    module = load(at, name, WRAPPED.format(decorator=decorator, k=k, inner=inner))
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        return graph_hash(nx.factor(window=2, inputs=[CLOSE])(module.score))


@pytest.mark.parametrize("decorator", ["@functools.lru_cache", "@_logged", "@numba.njit"])
def test_a_wrapped_helper_is_in_the_hash(tmp_path: Path, decorator: str) -> None:
    """6.5 (6), #572: a helper wrapped by a decorator that keeps the function in `__wrapped__`
    (`lru_cache`, a `functools.wraps` decorator, `numba.njit`) is followed to it, so editing its
    body changes the user term's hash, with no warning."""
    before = _wrapped_hash(tmp_path, "before", decorator, 2)
    assert _wrapped_hash(tmp_path, "again", decorator, 2) == before
    assert _wrapped_hash(tmp_path, "after", decorator, 5) != before


def test_a_wraps_decorators_inner_body_is_in_the_hash(tmp_path: Path) -> None:
    """6.5 (6), #596: the inner function of a project `functools.wraps` decorator is hashed from
    its own code, not through `__wrapped__`, so changing what the decorator does
    (`f(*args) * 1 → * 100`) changes the user term's hash, with no warning."""
    for decorator in ("@_logged", "@functools.lru_cache\n@_logged"):  # a library's on top too
        before = _wrapped_hash(tmp_path, "inner_1", decorator, 2, " * 1")
        assert _wrapped_hash(tmp_path, "inner_1_again", decorator, 2, " * 1") == before
        assert _wrapped_hash(tmp_path, "inner_100", decorator, 2, " * 100") != before
        assert _wrapped_hash(tmp_path, "helper_5", decorator, 5, " * 1") != before


def test_a_user_function_under_a_library_decorator_is_hashed_from_its_body(tmp_path: Path) -> None:
    """#596: a user function a library decorator wraps (`functools.singledispatch`, whose inner
    function lies outside the project) is read as the project function it keeps in
    `__wrapped__`, as a helper is, so editing its body still changes the hash."""
    text = "import functools\n@functools.singledispatch\ndef score(close):\n    return close[-1] * "
    hashes = [graph_hash(nx.factor(window=2, inputs=[CLOSE])(load(tmp_path, f"single_{k}",
              f"{text}{k}\n").score)) for k in (2, 5)]  # fmt: skip
    assert hashes[0] != hashes[1]


def test_a_decorators_arguments_are_in_the_hash(tmp_path: Path) -> None:
    """#572 Decisions 4: the 5.3.9 canonical source holds the decorator list, so one body under
    `njit()` and under `njit(fastmath=True)` gives two hashes."""
    plain = _wrapped_hash(tmp_path, "plain", "@numba.njit()", 2)
    assert _wrapped_hash(tmp_path, "fast", "@numba.njit(fastmath=True)", 2) != plain


#: A stand-in for a compiled dispatcher that keeps no `__wrapped__`: an object of a library's
#: class (not the project's), named by `__module__` as an object of the module that made it.
_Dispatcher = type("Dispatcher", (), {"__module__": "numba.core.registry",
                                      "__call__": lambda self, x: x})  # fmt: skip
_compiled = _Dispatcher()
_compiled.__module__ = __name__
_looped = _Dispatcher()  # a `__wrapped__` chain that never ends: `inspect.unwrap` refuses it
_looped.__module__, _looped.__wrapped__ = __name__, _looped
_mean = np.mean  # numpy's: has a `__wrapped__`, to a function outside the project


class _Rules:
    @classmethod
    def scale(cls, x: Any) -> Any:
        return x * 2


class _Scaled:
    """A project decorator object that keeps the function in `__wrapped__` and holds data."""

    def __init__(self, f: Any) -> None:
        functools.update_wrapper(self, f)
        self.f, self.factor = f, [2.0]

    def __call__(self, x: Any) -> Any:
        return self.f(x) * self.factor[0]


@_Scaled
def _doubled(x: Any) -> Any:
    return x


def _calls_scaled(close: Any) -> Any:
    return _doubled(close[-1])


def _calls_compiled(close: Any) -> Any:
    return _compiled(close[-1])


def _calls_looped(close: Any) -> Any:
    return _looped(close[-1])


def _calls_classmethod(close: Any) -> Any:
    return _Rules.scale(close[-1])


def _calls_numpy(close: Any) -> Any:
    return _mean(close, axis=0)


@pytest.mark.parametrize(("fn", "shown"), [(_calls_compiled, "_compiled"),
                                           (_calls_looped, "_looped"),
                                           (_calls_classmethod, "_Rules.scale"),
                                           (_calls_scaled, "_doubled")])  # fmt: skip
def test_a_project_callable_with_no_function_is_E24(fn: Any, shown: str) -> None:  # noqa: N802
    """#572 Decisions 2: a callable of the project from which no plain function is reached, a
    compiled dispatcher with no `__wrapped__` or a class's method, cannot have its source in the
    hash: E24, L1 off, never taken as pure without a word. An object of a project class stays
    E24 (#246) when it keeps a function in `__wrapped__`: the data it holds is not hashed."""
    with pytest.warns(UserWarning, match=rf"(?s)reads global '{shown}'.*L1 cache disabled"):
        term = nx.factor(window=2, inputs=[CLOSE])(fn)
    assert l1_disabled(term)


def test_a_wrapped_callable_outside_the_project_is_not_followed() -> None:
    """#572 Decisions 3: `np.mean` keeps a `__wrapped__`, to numpy's own function, which is
    outside the project: no helper and no warning, as before."""
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        term = nx.factor(window=2, inputs=[CLOSE])(_calls_numpy)
    assert not l1_disabled(term)
