"""#690: a class or a module a user function reads that `sys.modules` cannot give back by its
name is E24 with L1 off, the message naming it; what is judged today stays as it is."""

from __future__ import annotations

import importlib.util
import runpy
import sys
import warnings
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

import nexusbt as nx
from nexusbt.pipeline import BoundColumn, graph_hash
from nexusbt.pipeline._terms import l1_disabled

CLOSE = BoundColumn.of("Price", "close")
SETTINGS = "import numpy as np\n\n\nclass Cfg:\n    LIMIT = 1\n    W = np.array([1.0])\n"
FIX = "load the file that defines {} with an import statement, which puts it in sys.modules"


def _file(at: Path) -> Path:
    path = at / "settings690.py"
    path.write_text(SETTINGS)
    return path


def _spec(path: Path, register: bool) -> Any:
    name = f"settings690_{abs(hash(str(path)))}"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    if register:
        sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _exec(path: Path) -> Any:
    namespace: dict[str, Any] = {"__name__": "settings690_exec"}
    exec(compile(path.read_text(), str(path), "exec"), namespace)  # noqa: S102
    return namespace["Cfg"]


UNREGISTERED: dict[str, Callable[[Path], Any]] = {
    "spec_from_file_location, not registered": lambda p: _spec(p, register=False).Cfg,
    "runpy.run_path(run_name='settings690_runpy')": (
        lambda p: runpy.run_path(str(p), run_name="settings690_runpy")["Cfg"]
    ),
    "runpy.run_path (default run_name)": lambda p: runpy.run_path(str(p))["Cfg"],
    "exec": _exec,
}


def _terms(cfg: Any) -> tuple[nx.Factor, nx.Factor]:
    def const(close: Any) -> Any:
        return close[-1] * cfg.LIMIT

    def array(close: Any) -> Any:
        return close[-1] * cfg.W[0]

    make = nx.factor(window=2, inputs=[CLOSE])
    return make(const), make(array)


@pytest.mark.parametrize("load", UNREGISTERED.values(), ids=UNREGISTERED.keys())
def test_a_class_whose_module_is_not_in_sys_modules_is_e24(
    tmp_path: Path, load: Callable[[Path], Any]
) -> None:
    """AC 1: reading `Cfg.LIMIT` or `Cfg.W` of a class loaded without a `sys.modules` entry is E24
    with L1 off, naming the class and saying its module cannot be found by its name."""
    cfg = load(_file(tmp_path))
    assert cfg.__module__ not in sys.modules
    said = rf"reads class Cfg as 'cfg', whose module '{cfg.__module__}' cannot be found by its name"
    with pytest.warns(UserWarning, match=said) as caught:
        const, array = _terms(cfg)
    assert len(caught) == 2
    assert all(FIX.format("Cfg") in str(w.message) for w in caught)
    assert dict(const.params)["captured"] == ()
    assert l1_disabled(const)
    assert l1_disabled(array)


def test_a_module_not_held_by_sys_modules_is_e24(tmp_path: Path) -> None:
    """AC 3: a module made by `module_from_spec` and not registered, read as `cfg.LIMIT`, is E24
    with L1 off, naming the module."""
    cfg = _spec(_file(tmp_path), register=False)
    said = rf"reads module '{cfg.__name__}' as 'cfg', which cannot be found by its name"
    with pytest.warns(UserWarning, match=said) as caught:
        const, _ = _terms(cfg)
    assert FIX.format(f"module '{cfg.__name__}'") in str(caught[0].message)
    assert l1_disabled(const)


def test_a_class_imported_by_its_name_is_judged_as_before(tmp_path: Path) -> None:
    """AC 2: a class whose module is registered, as `import` does, keeps its constant in the
    hash, an edit of it moving the hash, and its array read E24 for the array, not the module."""
    cfg = _spec(_file(tmp_path), register=True).Cfg
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        const, array = _terms(cfg)
        cfg.LIMIT = 100
        moved = _terms(cfg)[0]
    assert dict(const.params)["captured"] == (("cfg.LIMIT", 1),)
    assert graph_hash(moved) != graph_hash(const)
    assert not l1_disabled(const)
    assert l1_disabled(array)
    assert not [w for w in caught if "cannot be found by its name" in str(w.message)]


def test_a_library_submodule_not_in_sys_modules_is_not_lost() -> None:
    """Fresh-context review: a library's class or module whose own module is not registered
    (`sys.monitoring`; a class of a submodule numpy loads lazily) stays unjudged as before, as
    its top package is loaded from outside the project."""
    lazy = type("Lazy", (), {"__module__": "numpy.not_loaded_690", "LIMIT": 1})
    for cfg in (sys.monitoring, lazy):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            _terms(cfg)
        assert not [w for w in caught if "cannot be found by its name" in str(w.message)]


def test_a_namespace_named_by_no_string_is_not_lost() -> None:
    """#794's uncovered line: a class whose `__module__` is not a string, and a module whose
    `__name__` is not, give no module to look for, so they are left as before #690."""
    nameless = type("Nameless", (), {"LIMIT": 1})
    nameless.__module__ = None  # type: ignore[assignment]
    module = ModuleType("m690")
    module.__name__ = 690  # type: ignore[assignment]
    vars(module)["LIMIT"] = 1
    for cfg in (nameless, module):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            _terms(cfg)
        assert not [w for w in caught if "cannot be found by its name" in str(w.message)]


def test_a_class_run_as_main_is_not_lost(tmp_path: Path) -> None:
    """Decision 2026-11-26: `runpy.run_path(run_name='__main__')` names a module that is in
    `sys.modules`, so the class is judged by that module as before, never said to be lost."""
    cfg = runpy.run_path(str(_file(tmp_path)), run_name="__main__")["Cfg"]
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        _terms(cfg)
    assert not [w for w in caught if "cannot be found by its name" in str(w.message)]
