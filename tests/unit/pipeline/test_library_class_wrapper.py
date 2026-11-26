"""Spec 6.5 (6), #695: a helper kept in `__wrapped__` by an object that is not a Python function
is E24, naming the function that reads it and the object's class, unless the object is
`functools.lru_cache`'s or `functools.cache`'s wrapper or `numba.njit`'s dispatcher (decision
2026-11-26)."""

from __future__ import annotations

import functools
import sys
import warnings
from types import ModuleType
from typing import Any

import numba
import pytest

import nexusbt as nx
from nexusbt.pipeline import BoundColumn
from nexusbt.pipeline._terms import l1_disabled

CLOSE = BoundColumn.of("Price", "close")

#: A stand-in library outside the project (its file name is not absolute): `Memo` keeps the
#: function in `__wrapped__` and holds a dict, as joblib's `MemorizedFunc` holds its store;
#: `Plain` keeps it and holds nothing else.
LIBRARY = """
import functools

class Memo:
    def __init__(self, f):
        functools.update_wrapper(self, f)
        self.cache = {}

    def __call__(self, *args):
        if args not in self.cache:
            self.cache[args] = self.__wrapped__(*args)
        return self.cache[args]

class Plain:
    def __init__(self, f):
        functools.update_wrapper(self, f)

    def __call__(self, *args):
        return self.__wrapped__(*args)

def deco(f):
    @functools.wraps(f)
    def wrapper(*args):
        return f(*args)
    return wrapper
"""
_lib = ModuleType("_lib695")
exec(compile(LIBRARY, "_lib695.py", "exec"), vars(_lib))  # noqa: S102


class _ProjectMemo:
    """A project class keeping the function in `__wrapped__`."""

    def __init__(self, f: Any) -> None:
        functools.update_wrapper(self, f)
        self.f = f

    def __call__(self, *args: Any) -> Any:
        return self.f(*args)


def _base(x: Any) -> Any:
    return x * 2


_helper: Any = None  # set by each test to the wrapper under test


def by_helper(close: Any) -> Any:
    return _helper(close[-1])


#: #695's table: the wrapper, and what reading it as a helper gives (`None`: pure).
ROWS = {
    "functools.lru_cache": (functools.lru_cache(_base), None),
    "functools.cache": (functools.cache(_base), None),
    "numba.njit": (numba.njit(_base), None),
    "functools.partial": (functools.partial(_base), r"reads global '_helper'"),
    "library class, with state": (_lib.Memo(_base), r"reads _helper, which is under _lib695\.Memo"),
    "library class, no state": (_lib.Plain(_base), r"reads _helper, which is under _lib695\.Plain"),
    "project class": (_ProjectMemo(_base), r"reads global '_helper'"),
    # fresh-context review: the object behind a library's function and an `lru_cache`
    "library class, behind a library function": (
        functools.lru_cache(_lib.deco(_lib.Memo(_base))),
        r"reads _helper, which is under _lib695\.Memo",
    ),
}


@pytest.mark.parametrize("row", ROWS)
def test_each_wrapper_of_a_helper_is_judged_as_the_table_has_it(
    row: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC 1, 2 (decision 2026-11-26): only `functools._lru_cache_wrapper` and numba's
    `Dispatcher` stay pure as helpers, no warning and L1 on; any other object keeping the
    helper is E24 with L1 off, a library's naming `by_helper`, `_helper` and the class."""
    wrapper, said = ROWS[row]
    monkeypatch.setattr(sys.modules[__name__], "_helper", wrapper)
    if said is None:
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            assert not l1_disabled(nx.factor(window=2, inputs=[CLOSE])(by_helper))
        return
    with pytest.warns(UserWarning, match=said):
        term = nx.factor(window=2, inputs=[CLOSE])(by_helper)
    assert l1_disabled(term)


def test_the_terms_own_function_under_a_class_stays_refused() -> None:
    """Decisions 4: `@nx.factor` on such an instance stays a `TypeError`."""
    with pytest.raises(TypeError, match="decorates a function, not Memo"):
        nx.factor(window=2, inputs=[CLOSE])(_lib.Memo(_base))
