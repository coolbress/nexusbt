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
    no helper and an `lru_cache` wrapper is not taken for a project object (not E24); the
    function it wraps is a helper (#572)."""
    assert not _terms._project_file(statistics.__file__)
    assert not _terms._project_file(functools.__file__)
    assert isinstance(_uses_the_stdlib, FunctionType)
    reads = _terms._reads(_uses_the_stdlib)
    assert (reads.helpers, reads.impure) == ((_cached.__wrapped__,), ())


def test_a_file_named_by_no_path_is_outside() -> None:
    """A code object whose file name is not an absolute path is outside the project: a frozen
    module's, the interactive prompt's, `exec`'s (#577)."""
    for name in ("<frozen posixpath>", "<stdin>", "<string>", "relative/mod.py"):
        assert not _terms._project_file(name)


def test_an_editable_package_is_the_project(tmp_path: Path) -> None:
    """A package installed in editable mode lies outside the library folders, so it is inside
    the project (#577, decision (b)): a user function calling it has its function as a helper,
    and two versions of its source give two graph hashes."""
    hashes = []
    for release, body in enumerate(("sum(xs) / len(xs)", "sum(xs) / max(len(xs), 1)")):
        lib = load(tmp_path / "other" / "src" / f"v{release}" / "lib573.py",
                   f"def fmean(xs):\n    return {body}\n")  # fmt: skip
        assert _terms._project_file(str(lib.__file__))
        sys.modules["lib573"] = lib
        try:
            score = load(tmp_path / "project" / f"user{release}.py", USER).score
            assert score.function is not None
            assert _terms._reads(score.function).helpers == (lib.fmean,)
            hashes.append(graph_hash(score))
        finally:
            del sys.modules["lib573"]
    assert hashes[0] != hashes[1]


def test_a_zipped_stdlib_is_outside(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A `.zip` entry of `sys.path` under the interpreter's folder, as written or through a link
    to it, is outside the project, by where it is and not by module name; a `.zip` elsewhere, and
    a project file named like a standard module, are inside (#577, decision (a))."""
    real, link = tmp_path / "python", tmp_path / "python-link"
    real.mkdir()
    link.symlink_to(real, target_is_directory=True)
    project = tmp_path / "project"
    entries = [str(real / "lib" / "python313.zip"), str(project / "vendored.zip"), str(project)]
    for base in (real, link):
        zips = _terms._stdlib_zips(entries, str(base))
        assert zips == (real / "lib" / "python313.zip",)
    zips = _terms._stdlib_zips([str(link / "lib" / "python313.zip")], str(real))
    assert zips == (link / "lib" / "python313.zip",)
    monkeypatch.setattr(_terms, "_OUTSIDE", zips)
    assert not _terms._project_file(str(link / "lib" / "python313.zip" / "random.py"))
    assert not _terms._project_file(str(real / "lib" / "python313.zip" / "json" / "decoder.py"))
    assert _terms._project_file(str(project / "vendored.zip" / "random.py"))
    assert _terms._project_file(str(project / "random.py"))


def test_the_checker_is_outside() -> None:
    """`nexusbt_tds` is the engine's, outside the project as `nexusbt` is, editable in this
    repository's environment too: a user function calling its pure-Python `profile_id` has no
    helper from it (#577, Decisions)."""
    import nexusbt
    import nexusbt_tds
    from nexusbt_tds import profiles

    assert not _terms._project_file(str(nexusbt.__file__))
    assert not _terms._project_file(str(nexusbt_tds.__file__))
    assert not _terms._project_file(profiles.__file__)

    def uses_the_checker(close: Any) -> Any:
        return len(profiles.profile_id("equity-daily-core")) + close[-1]

    assert isinstance(uses_the_checker, FunctionType)
    reads = _terms._reads(uses_the_checker)
    assert (reads.helpers, reads.impure) == ((), ())
