"""A user function under a library decorator that keeps it in `__wrapped__` (spec 6.5 (6), #645):
the user function's reads go into the hash as they would without the decorator, and the
decorator's wrapper is judged by #589's rule; an E24 names the function and the decorator."""

from __future__ import annotations

import importlib.util
import sys
import warnings
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

import nexusbt as nx
from nexusbt.pipeline import BoundColumn, Factor, graph_hash
from nexusbt.pipeline._terms import l1_disabled

CLOSE = BoundColumn.of("Price", "close")

#: A file of the user's project: `score` under `{decorator}` calls the helper `_helper`.
SINGLE = """
import functools

TABLE = {table}

def _helper(x):
    return x * {k}

@functools.singledispatch
def score(close):
    return _helper(close[-1]){read}
"""


def load(at: Path, name: str, text: str) -> Any:
    """`text` as a file of the user's project, imported."""
    path = at / f"{name}.py"
    path.write_text(text)
    spec = importlib.util.spec_from_file_location(f"{name}_{abs(hash(str(at)))}", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _single(at: Path, name: str, k: int = 2, read: str = "", table: str = "1") -> Factor:
    module = load(at, name, SINGLE.format(k=k, read=read, table=table))
    return nx.factor(window=2, inputs=[CLOSE])(module.score)


def test_editing_a_helper_under_singledispatch_changes_the_hash(tmp_path: Path) -> None:
    """#645's table reversed: editing the body of the helper a `singledispatch` user function
    calls changes `graph_hash`, as it does with no decorator (6.5 (6)); the term stays E24."""
    with pytest.warns(UserWarning, match="E24"):
        before = graph_hash(_single(tmp_path, "single_2"))
    with pytest.warns(UserWarning, match="E24"):
        again = graph_hash(_single(tmp_path, "single_2_again"))
    with pytest.warns(UserWarning, match="E24"):
        after = graph_hash(_single(tmp_path, "single_5", k=5))
    assert again == before
    assert after != before


def _e24(term: Any) -> str:
    """The one E24 building the term gave, as printed."""
    with warnings.catch_warnings(record=True) as got:
        warnings.simplefilter("always")
        factor = term()
    said = [str(w.message) for w in got if "[E24]" in str(w.message)]
    assert len(said) == 1
    assert l1_disabled(factor)
    return said[0]


def test_e24_names_the_function_and_the_decorator(tmp_path: Path) -> None:
    """#645 Decisions 3, spec 6.6: the E24 says what the user wrote, the function and the library
    decorator by its qualified name, and never tells the user to pass `'dispatch'`."""
    text = _e24(lambda: _single(tmp_path, "named"))
    assert ("what   score is under functools.singledispatch, whose wrapper holds what the engine"
            " cannot check\n") in text  # fmt: skip
    assert ("fix    apply @nx.factor to a function that is not under @functools.singledispatch;"
            " the engine hashes score's own code and the helpers it calls, not what the"
            " decorator's wrapper holds\n") in text  # fmt: skip
    assert "dispatch'" not in text
    assert "reads global" not in text


def test_e24_names_the_globals_the_function_reads_and_the_decorator(tmp_path: Path) -> None:
    """#645 Decisions 1: the user function's own reads are judged as they would be without the
    decorator, so a list it reads is named first, then the decorator."""
    text = _e24(lambda: _single(tmp_path, "both", read=" * TABLE[0]", table="[1.0]"))
    assert ("what   score reads global 'TABLE'; the engine cannot check what it contains; score is"
            " under functools.singledispatch, whose wrapper holds what the engine cannot"
            " check\n") in text  # fmt: skip
    assert "fix    pass 'TABLE' as an input" in text
    assert "; apply @nx.factor to a function that is not under @functools.singledispatch" in text


def test_a_constant_the_function_reads_is_in_the_hash(tmp_path: Path) -> None:
    """#645 Decisions 1: a constant the user function under `singledispatch` reads goes into the
    hash (6.5 (6)), as it does with no decorator."""
    hashes = []
    for value in ("1", "2"):
        with pytest.warns(UserWarning, match="E24"):
            term = _single(tmp_path, f"constant_{value}", read=" * TABLE", table=value)
        hashes.append(graph_hash(term))
    assert hashes[0] != hashes[1]


#: A stand-in library, outside the project (its file name is not absolute): `scaled(k)` is a
#: `wraps` decorator with an argument and nothing the hash cannot read; `kept` holds a list.
LIBRARY = """
import functools

def scaled(k):
    def deco(f):
        @functools.wraps(f)
        def wrapper(*args):
            return f(*args) * k
        return wrapper
    return deco

def kept(f):
    calls = []
    @functools.wraps(f)
    def wrapper(*args):
        calls.append(args)
        return f(*args)
    return wrapper
"""

#: A file of the user's project whose `score` is under `{decorator}` of the stand-in library.
UNDER = """
import _lib645

def _helper(x):
    return x * {k}

{decorator}
def score(close):
    return _helper(close[-1])
"""


@pytest.fixture
def library(monkeypatch: pytest.MonkeyPatch) -> None:
    module = ModuleType("_lib645")
    exec(compile(LIBRARY, "_lib645.py", "exec"), vars(module))  # noqa: S102
    monkeypatch.setitem(sys.modules, "_lib645", module)


def _under(at: Path, name: str, decorator: str, k: int = 2) -> Factor:
    module = load(at, name, UNDER.format(decorator=decorator, k=k))
    return nx.factor(window=2, inputs=[CLOSE])(module.score)


@pytest.mark.usefixtures("library")
def test_a_library_decorator_that_holds_nothing_unreadable_is_pure(tmp_path: Path) -> None:
    """#645 Decisions 2, no false alarm: a library's `wraps` decorator whose wrapper holds only
    the function and a constant is pure by #589's rule, no warning and L1 on; editing the
    helper still changes the hash."""
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        before = _under(tmp_path, "pure_2", "@_lib645.scaled(2)")
        after = _under(tmp_path, "pure_5", "@_lib645.scaled(2)", k=5)
    assert not l1_disabled(before)
    assert graph_hash(after) != graph_hash(before)


@pytest.mark.usefixtures("library")
def test_a_library_decorators_arguments_are_in_the_hash(tmp_path: Path) -> None:
    """#645: the wrapper's own constants are left out of the hash, but the decorator's arguments
    are in the user function's source (#572 Decisions 4), so `scaled(1)` and `scaled(2)` give two
    hashes."""
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        one = graph_hash(_under(tmp_path, "arg_1", "@_lib645.scaled(1)"))
        two = graph_hash(_under(tmp_path, "arg_2", "@_lib645.scaled(2)"))
    assert one != two


def test_lru_caches_arguments_are_in_the_hash(tmp_path: Path) -> None:
    """#645: `@functools.lru_cache(maxsize=1)` and `(maxsize=2)` on a helper give two hashes
    (`lru_cache` on the function `@nx.factor` takes is refused: it is not a function)."""
    text = ("import functools\n@functools.lru_cache(maxsize={m})\ndef _helper(x):\n    return x"
            "\ndef score(close):\n    return _helper(close[-1])\n")  # fmt: skip
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        hashes = {graph_hash(nx.factor(window=2, inputs=[CLOSE])(
            load(tmp_path, f"maxsize_{m}", text.format(m=m)).score)) for m in (1, 2)}  # fmt: skip
    assert len(hashes) == 2


@pytest.mark.usefixtures("library")
def test_a_library_decorator_that_holds_data_is_e24(tmp_path: Path) -> None:
    """#645 Decisions 2, 3: a library wrapper holding a list is E24 by #589's rule, naming the
    function and the decorator, not the list inside the library."""
    text = _e24(lambda: _under(tmp_path, "kept", "@_lib645.kept"))
    assert "what   score is under _lib645.kept, whose wrapper holds what" in text
    assert "'calls'" not in text
