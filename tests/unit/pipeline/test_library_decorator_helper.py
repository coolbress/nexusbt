"""A helper under a library decorator that keeps it in `__wrapped__` (spec 6.5 (6), #676): judged
the way the term's own function is (#645), its wrapper walked by #589's rule; an E24 names the
function that reads the helper, the helper and the decorator."""

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

#: A file of the user's project: `score` calls the helper `sd`, under `{decorator}`, which calls
#: `_helper`.
HELPER = """
import functools
import _lib676

K = {kk}

def _helper(x):
    return x * {k}

{decorator}
def sd(x):
    return _helper(x)

def score(close):
    return sd(close[-1])
"""


@pytest.fixture(autouse=True)
def library(monkeypatch: pytest.MonkeyPatch) -> None:
    module = ModuleType("_lib676")
    exec(compile(LIBRARY, "_lib676.py", "exec"), vars(module))  # noqa: S102
    monkeypatch.setitem(sys.modules, "_lib676", module)


def _term(at: Path, name: str, decorator: str, k: int = 2, kk: int = 1, as_: str = "") -> Factor:
    """`score` of a file of the user's project, as a user term; imported under the module name
    `as_` if given (a helper's constants are keyed by its module's name, #673)."""
    path = at / f"{name}.py"
    path.write_text(HELPER.format(decorator=decorator, k=k, kk=kk))
    spec = importlib.util.spec_from_file_location(as_ or f"{name}_{abs(hash(str(at)))}", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return nx.factor(window=2, inputs=[CLOSE])(module.score)


def _e24(term: Any) -> str:
    """The one E24 building the term gave, as printed; the term's L1 is off."""
    with warnings.catch_warnings(record=True) as got:
        warnings.simplefilter("always")
        factor = term()
    said = [str(w.message) for w in got if "[E24]" in str(w.message)]
    assert len(said) == 1
    assert l1_disabled(factor)
    return said[0]


def test_a_singledispatch_helper_is_e24(tmp_path: Path) -> None:
    """#676's table reversed: `score` reading the `singledispatch` function `sd` is E24 with L1
    off, naming `sd` and the decorator (spec 6.6), not `'dispatch'` inside the library."""
    text = _e24(lambda: _term(tmp_path, "sd_named", "@functools.singledispatch"))
    assert ("what   score reads sd, which is under functools.singledispatch, whose wrapper holds"
            " what the engine cannot check\n") in text  # fmt: skip
    assert ("fix    read a function that is not under @functools.singledispatch in place of sd;"
            " the engine hashes sd's own code and the helpers it calls, not what the decorator's"
            " wrapper holds\n") in text  # fmt: skip
    assert "where  function score\n" in text
    assert "dispatch'" not in text


def test_a_singledispatch_helpers_hash_follows_its_helper(tmp_path: Path) -> None:
    """#676: the graph hash still follows `_helper`'s body under the `singledispatch` helper, and
    the same file imported again under the same module name gives the same hash."""
    hashes: list[str] = []
    for k in (2, 2, 5):
        name = f"sd_{len(hashes)}"
        with pytest.warns(UserWarning, match="E24"):
            term = _term(tmp_path, name, "@functools.singledispatch", k=k, as_="project_sd")
        hashes.append(graph_hash(term))
    assert hashes[0] == hashes[1]
    assert hashes[2] != hashes[0]


def test_a_library_decorator_that_holds_data_is_e24_as_a_helper(tmp_path: Path) -> None:
    """#676 Decisions 4: a library wrapper holding a list is E24 as a helper too, as it is on the
    term's own function (#645)."""
    text = _e24(lambda: _term(tmp_path, "kept", "@_lib676.kept"))
    assert "what   score reads sd, which is under _lib676.kept, whose wrapper holds what" in text
    assert "'calls'" not in text


def test_a_library_decorator_that_holds_nothing_unreadable_is_pure_as_a_helper(
    tmp_path: Path,
) -> None:
    """#676 Decisions 2, no false alarm: a helper under a library `wraps` decorator whose wrapper
    holds only the function and a constant is pure, L1 on; editing `_helper` changes the hash."""
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        before = _term(tmp_path, "pure_2", "@_lib676.scaled(2)", as_="project_pure")
        after = _term(tmp_path, "pure_5", "@_lib676.scaled(2)", k=5, as_="project_pure")
    assert not l1_disabled(before)
    assert graph_hash(after) != graph_hash(before)


def test_a_helpers_library_decorator_argument_passed_by_name_is_in_the_hash(
    tmp_path: Path,
) -> None:
    """#676: the wrapper's own constants go into the hash as they do on the term's own function
    (#645): `@scaled(K)` with `K = 1` and `K = 2` gives two hashes."""
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        one = graph_hash(_term(tmp_path, "named_1", "@_lib676.scaled(K)", kk=1, as_="named"))
        again = graph_hash(_term(tmp_path, "named_1b", "@_lib676.scaled(K)", kk=1, as_="named"))
        two = graph_hash(_term(tmp_path, "named_2", "@_lib676.scaled(K)", kk=2, as_="named"))
    assert one == again
    assert one != two
