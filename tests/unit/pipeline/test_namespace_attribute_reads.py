"""Spec 6.5 (6), #674: a name counts as read off a project namespace only where the function's
code reads it off that namespace; where the code cannot tell, every attribute name it loads is
looked up there, as before (Decisions 1, 2)."""

from __future__ import annotations

import importlib.util
import sys
import warnings
from pathlib import Path
from typing import Any

import pytest

import nexusbt as nx
from nexusbt.pipeline import BoundColumn, graph_hash
from nexusbt.pipeline._terms import _reads

CLOSE = BoundColumn.of("Price", "close")

#: The issue's module, with a submodule and a class to reach by a chain.
CFG = """
import numpy as np

import sub674 as sub

LIMIT = 3
K = 7
mean = [1.0, 2.0]  # data no function below reads
W = np.array([1.0])


class Cfg:
    LIMIT = 4
    mean = [1.0]
"""


def load(at: Path, name: str, text: str, monkeypatch: pytest.MonkeyPatch) -> Any:
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
def user(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    """A project file whose functions read the module `cfg674` as `cfg`."""
    monkeypatch.syspath_prepend(str(tmp_path))
    load(tmp_path, "sub674", "LIMIT = 5\nmean = [1.0]\n", monkeypatch)
    load(tmp_path, "cfg674", CFG, monkeypatch)
    return load(tmp_path, "user674", USER, monkeypatch)


USER = """
import cfg674 as cfg


def issue(close):
    return close.mean() * cfg.LIMIT


def chains(close):
    return close.mean() * (cfg.sub.LIMIT + cfg.Cfg.LIMIT)


def data(close):
    return close.mean() * cfg.W[0]


def bound(close):
    c = cfg
    return close.mean() * c.LIMIT


def computed(close, name="LIMIT"):
    return close.mean() * getattr(cfg, name)


def get():
    return cfg


def returned(close):
    return close.mean() * (cfg.LIMIT + get().K + len(get().mean))


def defaulted(close, c=cfg):
    return close.mean() * (cfg.LIMIT + c.K)


def imported(close):
    import cfg674 as again

    return close.mean() * (cfg.LIMIT + again.K)


def item(close):
    return close.mean() * (cfg.LIMIT + globals()["cfg"].K)


def joined(close):
    return close.mean() * (cfg.LIMIT + (get() or cfg.sub).K)


def _part(c):
    return c.K + cfg.LIMIT


def through_helper(close):
    return close.mean() * _part(cfg)


def _make():
    space = cfg

    def in_class(close):
        class Box:
            k = space.K

        return close.mean() * Box.k

    return in_class


in_class = _make()
"""


def test_a_method_of_the_input_is_not_read_off_the_module(user: Any) -> None:
    """AC 1: `close.mean()` with `cfg.mean` a list: no E24, `impure` empty, only `cfg.LIMIT` in
    the hash; with `cfg.mean` a constant, editing it leaves the graph hash as it is."""
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        term = nx.factor(window=2, inputs=[CLOSE])(user.issue)
    assert _reads(user.issue).impure == ()
    assert dict(term.params)["captured"] == (("cfg.LIMIT", 3),)
    cfg: Any = sys.modules["cfg674"]
    cfg.mean = 5
    base = graph_hash(nx.factor(window=2, inputs=[CLOSE])(user.issue))
    cfg.mean = 6
    assert graph_hash(nx.factor(window=2, inputs=[CLOSE])(user.issue)) == base


def test_nothing_read_is_lost(user: Any) -> None:
    """AC 2: a chain through a submodule and a name read off a project class are captured, and a
    non-constant read off the namespace is still E24; nothing else of theirs is asked for."""
    assert _reads(user.chains).captured == (("cfg.Cfg.LIMIT", 4), ("cfg.sub.LIMIT", 5))
    assert _reads(user.chains).impure == ()
    with pytest.warns(UserWarning, match=r"reads global 'cfg\.W'"):
        nx.factor(window=2, inputs=[CLOSE])(user.data)
    assert _reads(user.data).impure == ("cfg.W",)


@pytest.mark.parametrize("name", ["bound", "computed"])
def test_where_the_code_cannot_tell_every_loaded_name_is_asked(user: Any, name: str) -> None:
    """AC 3, the safe side: the namespace bound to another name first (`c = cfg`) or read with a
    computed name (`getattr(cfg, name)`) is asked for every attribute name the code loads, as
    before #674: `cfg.mean`, a list, is E24 though `close.mean()` is what the code calls."""
    fn = getattr(user, name)
    assert _reads(fn).impure == ("cfg.mean",)
    with pytest.warns(UserWarning, match=r"reads global 'cfg\.mean'"):
        nx.factor(window=2, inputs=[CLOSE])(fn)


@pytest.mark.parametrize("name", ["returned", "defaulted", "imported", "item", "joined"])
def test_an_attribute_read_off_a_value_the_code_does_not_show_is_asked(
    user: Any, name: str
) -> None:
    """AC 2, 3, fresh-context reviews: an attribute read off a helper's result (`get().K`), a
    default (`c.K`), a local import (`again.K`), an item (`globals()["cfg"].K`) or where two
    paths of the code meet (`(get() or cfg.sub).K`) may be read off any namespace, so each
    namespace the function reads is asked for it, as before: `cfg.K` is in the hash, and
    `get().mean`, a list, is E24. Where a chain stops at that meeting (`cfg.sub`), the namespace
    is asked for every name the code loads, as before #674: `cfg.sub.mean` is E24."""
    reads = _reads(getattr(user, name))
    assert ("cfg.K", 7) in reads.captured
    assert reads.impure == {"returned": ("cfg.mean",), "joined": ("cfg.sub.mean",)}.get(name, ())


def test_a_helpers_parameter_may_hold_a_namespace(user: Any) -> None:
    """AC 2, second fresh-context review: only the term's own parameters are its input windows;
    a helper's (`_part(c)`, given `cfg`) may hold a namespace, so what it reads off one is asked
    of the namespaces the helper reads: `cfg.K` is in the hash under the helper."""
    assert ("user674._part:cfg.K", 7) in _reads(user.through_helper).captured


def test_a_namespace_a_class_body_loads_is_asked_for_every_name(user: Any) -> None:
    """AC 3, #806's uncovered line: a class body in the function loads the closure's `space`
    by an instruction whose chains are not followed (`LOAD_FROM_DICT_OR_DEREF`), so `space` is
    asked for every name the code loads, as before #674: `space.K` is in the hash and
    `space.mean`, a list, is E24. On Python 3.13 the function also loads `space` as it is to
    build the class's closure, which ends the path by itself, so this test runs that line but
    would still pass without it."""
    reads = _reads(user.in_class)
    assert ("space.K", 7) in reads.captured
    assert reads.impure == ("space.mean",)
