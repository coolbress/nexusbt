"""Which files are the user's project (spec 6.5 (6), #573): the standard library and the
installed packages are outside it however the interpreter's folder is reached, a symbolic link
included, so a user function's graph hash does not depend on that."""

from __future__ import annotations

import functools
import importlib.util
import statistics
import sys
from pathlib import Path
from types import FunctionType, ModuleType
from typing import Any

import pytest

from nexusbt.pipeline import _terms, graph_hash

USER = """
import nexusbt as nx
from nexusbt.pipeline import BoundColumn
import lib573

@nx.factor(window=2, inputs=[BoundColumn.of("Price", "close")])
def score(close):
    return lib573.fmean([1.0, 2.0]) + close[-1]
"""


def load(path: Path, text: str) -> ModuleType:
    """`text` written to `path` and imported under a name of its own."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    spec = importlib.util.spec_from_file_location(f"m573_{abs(hash(str(path)))}", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_outside_through_a_symbolic_link(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A file of the library's folder and of an installed package is outside the project when
    the folder compared against is a link and the file is named through its target, and the
    other way round; a file of the project is inside either way."""
    real, link = tmp_path / "real", tmp_path / "link"
    for file in ("stdlib/mod.py", "site/pkg/mod.py"):
        (real / file).parent.mkdir(parents=True)
        (real / file).write_text("")
    link.symlink_to(real, target_is_directory=True)
    project = tmp_path / "project" / "strategy.py"
    for compared, named in ((link, real), (real, link)):
        monkeypatch.setattr(_terms, "_OUTSIDE", (compared / "stdlib", compared / "site"))
        assert not _terms._project_file(str(named / "stdlib" / "mod.py"))
        assert not _terms._project_file(str(named / "site" / "pkg" / "mod.py"))
        assert _terms._project_file(str(project))
    assert not _terms._project_file("<string>")  # code with no file, such as `exec`'s
    # An installed file that is itself a link into a store (`uv`'s symlink link mode, Nix)
    (tmp_path / "store").mkdir()
    (tmp_path / "store" / "linked.py").write_text("")
    (real / "site" / "pkg" / "linked.py").symlink_to(tmp_path / "store" / "linked.py")
    assert not _terms._project_file(str(real / "site" / "pkg" / "linked.py"))


def test_a_library_function_is_no_helper(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A user function calling a pure-Python function of a library reached through a link has no
    helper from it: two releases of the library with different bodies give one graph hash."""
    real, link = tmp_path / "real", tmp_path / "link"
    real.mkdir()
    link.symlink_to(real, target_is_directory=True)
    monkeypatch.setattr(_terms, "_OUTSIDE", (*_terms._OUTSIDE, link))
    hashes = []
    for release, body in enumerate(("sum(xs) / len(xs)", "sum(xs) / max(len(xs), 1)")):
        lib = load(real / f"v{release}" / "lib573.py", f"def fmean(xs):\n    return {body}\n")
        monkeypatch.setitem(sys.modules, "lib573", lib)
        score = load(tmp_path / "project" / f"user{release}.py", USER).score
        assert score.function is not None
        assert _terms._reads(score.function).helpers == ()
        hashes.append(graph_hash(score))
    assert hashes[0] == hashes[1]


@functools.lru_cache
def _cached(x: Any) -> Any:
    return x


def _uses_the_stdlib(close: Any) -> Any:
    return statistics.fmean([1.0, 2.0]) + _cached(close[-1])


def test_the_interpreters_stdlib_is_outside() -> None:
    """This interpreter's standard library, however its folder is reached: `statistics.fmean` is
    no helper and an `lru_cache` wrapper is not taken for a project object (not E24)."""
    assert not _terms._project_file(statistics.__file__)
    assert not _terms._project_file(functools.__file__)
    assert isinstance(_uses_the_stdlib, FunctionType)
    reads = _terms._reads(_uses_the_stdlib)
    assert (reads.helpers, reads.impure) == ((), ())
