"""Spec 6.5 (6), #689: two different objects a user function reads whose constants would share a
key (two helpers one factory made, two wrappers of one helper) each keep theirs, the key carrying
the names by which the function reaches the object (decision 2026-11-26); every other key stays
as #673 made it."""

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

#: The issue's module: two helpers made by one factory, and a helper calling both.
FACTORY = """
def make(k):
    def inner():
        return k

    return inner


a = make({a})
b = make({b})
c = a


def pair():
    return a() + b()
"""

#: A stand-in library outside the project (its file name is not absolute): a decorator factory
#: whose wrapper keeps the function in `__wrapped__` and reads its argument `k`.
LIBRARY = """
import functools

def scaled(k):
    def deco(f):
        @functools.wraps(f)
        def wrapper(*args):
            return f(*args) * k
        return wrapper
    return deco
"""

#: #689's Decisions (#694): one helper under two wrappers, and two wrappers stacked on one.
WRAPPED = """
import _lib689

def _base(x):
    return x

fast = _lib689.scaled({a})(_base)
slow = _lib689.scaled({b})(_base)

@_lib689.scaled({a})
@_lib689.scaled({b})
def stacked(x):
    return x
"""


def load(at: Path, text: str, monkeypatch: pytest.MonkeyPatch, name: str = "u") -> Any:
    """`text` as the project module `name`, in `sys.modules` as `import` does."""
    path = at / f"{name}.py"
    path.write_text(text)
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, module)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def library(monkeypatch: pytest.MonkeyPatch) -> None:
    lib = ModuleType("_lib689")
    exec(compile(LIBRARY, "_lib689.py", "exec"), vars(lib))  # noqa: S102
    monkeypatch.setitem(sys.modules, "_lib689", lib)


def hashed(
    at: Path, monkeypatch: pytest.MonkeyPatch, text: str, body: str, a: int, b: int
) -> tuple[str, tuple[tuple[str, Any], ...]]:
    """The graph hash and `captured` of the user function `fn` of a project file returning
    `close[-1] * (body)`, `u` the module `text` makes with `a` and `b`; no E24. Each pair of
    values has a folder of its own: a file rewritten at its size within a second would be read
    from the bytecode cache of the one before."""
    at = at / f"{a}_{b}"
    at.mkdir(exist_ok=True)
    load(at, text.format(a=a, b=b), monkeypatch)
    user = load(at, f"import u\n\ndef fn(close):\n    return close[-1] * ({body})\n",
                monkeypatch, "user689")  # fmt: skip
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        term = nx.factor(window=2, inputs=[CLOSE])(user.fn)
    return graph_hash(term), dict(term.params)["captured"]


def test_two_helpers_of_one_factory_keep_both_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC 1: the issue's reproduction reversed: `captured` holds both values, each key naming how
    the function reaches its helper, and editing either `make(...)` changes the graph hash."""
    base, captured = hashed(tmp_path, monkeypatch, FACTORY, "u.a() + u.b()", 1, 2)
    assert captured == (("u.make.<locals>.inner[u.a]:k", 1), ("u.make.<locals>.inner[u.b]:k", 2))
    assert not any(str(tmp_path) in key or "/" in key for key, _ in captured)  # no path (5.9.3)
    assert hashed(tmp_path, monkeypatch, FACTORY, "u.a() + u.b()", 100, 2)[0] != base
    assert hashed(tmp_path, monkeypatch, FACTORY, "u.a() + u.b()", 1, 100)[0] != base


def test_the_two_are_told_apart(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """AC 2: a swap of the two values changes what `u.a() - u.b()` computes, and its hash."""
    one = hashed(tmp_path, monkeypatch, FACTORY, "u.a() - u.b()", 1, 2)[0]
    assert hashed(tmp_path, monkeypatch, FACTORY, "u.a() - u.b()", 2, 1)[0] != one


def test_a_helper_reached_through_a_helper_names_the_chain(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Decision 2026-11-26: a helper reached through another helper is keyed by the chain."""
    captured = hashed(tmp_path, monkeypatch, FACTORY, "u.pair()", 1, 2)[1]
    assert captured == (("u.make.<locals>.inner[u.pair>a]:k", 1),
                        ("u.make.<locals>.inner[u.pair>b]:k", 2))  # fmt: skip


def test_one_helper_read_under_two_names_keeps_the_short_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC 3: one object read under two names (`c = a`) is no collision: #673's key, as before."""
    captured = hashed(tmp_path, monkeypatch, FACTORY, "u.a() + u.c()", 1, 2)[1]
    assert captured == (("u.make.<locals>.inner:k", 1),)


@pytest.mark.usefixtures("library")
@pytest.mark.parametrize(
    ("body", "keys"),
    [("u.fast(1.0) + u.slow(1.0)",
      ("u._base[u.fast]:_lib689.scaled:k", "u._base[u.slow]:_lib689.scaled:k")),
     ("u.stacked(1.0)",
      ("u.stacked[u.stacked]:_lib689.scaled:k", "u.stacked[u.stacked>@f]:_lib689.scaled:k"))],
    ids=["two wrappers", "stacked"],
)  # fmt: skip
def test_two_wrappers_of_one_helper_keep_both_arguments(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, body: str, keys: tuple[str, str],
) -> None:  # fmt: skip
    """AC 5: `fast = scaled(A)(_base)`, `slow = scaled(B)(_base)`, and `@scaled(A)` over
    `@scaled(B)`: both arguments are in the hash, and editing either changes it."""
    base, captured = hashed(tmp_path, monkeypatch, WRAPPED, body, 2, 3)
    assert dict(captured) == {keys[0]: 2, keys[1]: 3}
    assert hashed(tmp_path, monkeypatch, WRAPPED, body, 7, 3)[0] != base
    assert hashed(tmp_path, monkeypatch, WRAPPED, body, 2, 9)[0] != base


def test_reads_without_a_shared_key_are_keyed_as_before(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC 3: a function whose helpers each give their own key has #673's keys only."""
    u = load(tmp_path, FACTORY.format(a=1, b=2), monkeypatch)

    def fn(close: Any, n: int = 3) -> Any:
        return close[-1] * u.a() * n

    captured = dict(nx.factor(window=2, inputs=[CLOSE])(fn).params)["captured"]
    assert captured == (("n=", 3), ("u.make.<locals>.inner:k", 1))
