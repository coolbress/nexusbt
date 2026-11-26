"""Spec 6.5 (6), #797: a chain of names that starts inside a library wrapper is marked `@`, so a
helper the wrapper holds under a name and another the wrapped function reads as its global of
that name keep a key each (decision 2026-11-26)."""

from __future__ import annotations

import importlib.util
import sys
import warnings
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

import nexusbt as nx
from nexusbt.pipeline import BoundColumn, graph_hash

CLOSE = BoundColumn.of("Price", "close")

#: A stand-in library outside the project (its file name is not absolute): the wrapper's closure
#: holds the project function `g` it is given under the name `g`.
LIBRARY = """
import functools

def using(g):
    def deco(f):
        @functools.wraps(f)
        def wrapper(*a):
            return f(*a) * g()
        return wrapper
    return deco
"""

#: The issue's module: `_base` reads its global `g`; the wrapper around it holds `h` as `g`.
#: `own` is a term's own function under the same wrapper, reading the global `g`.
U = """
import _lib797


def make(k):
    def inner():
        return k

    return inner


g = make({a})
h = make({b})


def _base(x):
    return x - g()


fast = _lib797.using(h)(_base)


def helper_case(close):
    return fast(close[-1])


@_lib797.using(h)
def own(close):
    return close[-1] - g()
"""


@pytest.fixture(autouse=True)
def library(monkeypatch: pytest.MonkeyPatch) -> None:
    lib = ModuleType("_lib797")
    exec(compile(LIBRARY, "_lib797.py", "exec"), vars(lib))  # noqa: S102
    monkeypatch.setitem(sys.modules, "_lib797", lib)


def hashed(at: Path, monkeypatch: pytest.MonkeyPatch, name: str, a: int, b: int) -> tuple[str, Any]:
    """The graph hash and `captured` of `name` in the module `U` makes with `a` and `b`, the
    file in a folder of its own for each pair (the bytecode cache keys on size and time)."""
    folder = at / f"{a}_{b}"
    folder.mkdir()
    (folder / "u797.py").write_text(U.format(a=a, b=b))
    spec = importlib.util.spec_from_file_location("u797", folder / "u797.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "u797", module)
    spec.loader.exec_module(module)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        term = nx.factor(window=2, inputs=[CLOSE])(getattr(module, name))
    return graph_hash(term), dict(term.params)["captured"]


@pytest.mark.parametrize(("name", "keys"), [
    ("helper_case", ("u797.make.<locals>.inner[fast>@g]:k", "u797.make.<locals>.inner[fast>g]:k")),
    ("own", ("u797.make.<locals>.inner[@g]:k", "u797.make.<locals>.inner[g]:k")),
])  # fmt: skip
def test_a_name_inside_the_wrapper_and_the_functions_own_keep_a_key_each(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str, keys: tuple[str, str]
) -> None:
    """AC 1: both `k` values are in `captured`, the wrapper's under `@g`, and editing either
    changes the graph hash, for the helper under the wrapper and for the term's own function."""
    base, captured = hashed(tmp_path, monkeypatch, name, 1, 2)
    assert dict(captured) == {keys[0]: 2, keys[1]: 1}
    assert hashed(tmp_path, monkeypatch, name, 9, 2)[0] != base
    assert hashed(tmp_path, monkeypatch, name, 1, 7)[0] != base
