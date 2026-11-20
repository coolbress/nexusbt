"""Spec 6.5 (6), #673: the constant a project helper reads goes into the hash under the helper's
module and qualified name (`<module>.<qualname>:<name>`), so two helpers of one qualified name in
two modules keep both constants; the module is named as Python knows it, never by a path
(5.9.3 "No local path")."""

from __future__ import annotations

import importlib.util
import sys
import warnings
from pathlib import Path
from typing import Any

import pytest

import nexusbt as nx
from nexusbt.pipeline import BoundColumn, graph_hash

CLOSE = BoundColumn.of("Price", "close")

#: A helper module of the user's project: a function `scale` and a class `Scale` with a method
#: `get`, both reading the module's constant `LIMIT`.
HELPER = """
LIMIT = {limit}

def scale():
    return LIMIT

class Scale:
    @staticmethod
    def get():
        return LIMIT
"""

#: The user's file: `score` calls `{call}` of the two helper modules `hb1` and `hb2`, set from
#: outside as `import` would.
USER = """
def score(close):
    return close[-1] * (hb1.{call}() + hb2.{call}())
"""


def load(at: Path, name: str, text: str, monkeypatch: pytest.MonkeyPatch) -> Any:
    """`text` as a file of the user's project, imported under the module name `name` (and in
    `sys.modules` for the test, as `import` does: a class is the project's by its module)."""
    path = at / f"{name}.py"
    path.write_text(text)
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, module)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(("call", "qualname"), [("scale", "scale"), ("Scale.get", "Scale.get")])
def test_two_helpers_of_one_qualified_name_keep_both_constants(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, call: str, qualname: str
) -> None:
    """#673's reproduction reversed, for two functions and for two classes' methods of one
    qualified name in two modules: `captured` holds both constants, each under
    `<module>.<qualname>:LIMIT` with no path in it, and editing either changes the graph hash."""
    hb1 = load(tmp_path, "hb1_673", HELPER.format(limit=1), monkeypatch)
    hb2 = load(tmp_path, "hb2_673", HELPER.format(limit=2), monkeypatch)
    user = load(tmp_path, "user_673", USER.format(call=call), monkeypatch)
    user.hb1, user.hb2 = hb1, hb2

    def hashed() -> tuple[str, tuple[tuple[str, object], ...]]:
        with warnings.catch_warnings():
            warnings.simplefilter("error")  # no E24: both reads are constants
            term = nx.factor(window=2, inputs=[CLOSE])(user.score)
        return graph_hash(term), dict(term.params)["captured"]

    base, captured = hashed()
    assert captured == ((f"hb1_673.{qualname}:LIMIT", 1), (f"hb2_673.{qualname}:LIMIT", 2))
    assert not any(str(tmp_path) in key or "/" in key for key, _ in captured)
    for module in (hb1, hb2):
        with monkeypatch.context() as edit:
            edit.setattr(module, "LIMIT", 100)  # the same as editing `LIMIT = 100` in the file
            assert hashed()[0] != base, module.__name__
    assert hashed()[0] == base
