"""The static check behind spec 2.7's `::test_fixtures_are_synthetic` (#599), on test modules
written here: what it must reject and what it must accept."""

from __future__ import annotations

import pytest
from snapshot_sources import findings

NAME = "tests/unit/test_x.py"


SYNTH = "from nexusbt.testing.synth import make_snapshot\n"
TINY = "@pytest.fixture\ndef tiny(tmp_path):\n    return make_snapshot(tmp_path / 'p')\n\n"


def module(*lines: str, head: str = SYNTH) -> str:
    """A test module: a `tiny` fixture made by `make_snapshot`, and `test_x` running `lines`."""
    return head + TINY + "def test_x(tiny, tmp_path, p):\n" + "".join(f"    {s}\n" for s in lines)


FAILS = {  # a literal path never passes, nor what the trace cannot follow
    "literal path": module('open_snapshot(DataConfig(path="/data/snap"))'),
    "Path literal": module('nx.open(Path("/data/snap") / "s1")'),
    "snapshot= literal": module('run_pipeline(q, snapshot="data/snap")'),
    "snapshot= literal name": module('r = Path("~/s")', 'run_pipeline(q, snapshot=str(r / "s1"))'),
    "synth in literal folder": module('w = Path("/d")', "make_snapshot(w)", "nx.open(w)"),
    "copy beside outside": module('c = merge(tiny, "/d", tmp_path / "c")', "nx.open(c)"),
    "package written by hand": module('by_hand(tmp_path / "pkg")', 'nx.open(tmp_path / "pkg")'),
    "parameter with no caller": module("nx.open(p)"),
    # The first fresh-context review's bypasses, as it gave them.
    "DataConfig positional": module("open_snapshot(DataConfig(Path('/data/snap')))"),
    "nexusbt.open": module("nexusbt.open('/data/snap')", head=SYNTH + "import nexusbt\n"),
    "open imported by name": module(
        "o('/data/snap')", head=SYNTH + "from nexusbt import open as o\n"
    ),
    "snapshot= in **": module("run(**{'snapshot': '/data/snap'})"),
    "print beside synth": module(
        "d = Path.home() / 'snap'", "s = make_snapshot(tmp_path / 's')", "print(d, s)", "nx.open(d)"
    ),
    "log beside synth": module(
        "d = Path(os.environ['REAL'])",
        "make_snapshot(tmp_path / 'x')",
        "log(d, tmp_path)",
        "nx.open(d)",
    ),
    "environ.get default": module("nx.open(os.environ.get('REAL', tiny))"),
    "str + ..": module("nx.open(str(tiny) + '/../../real')"),
    ".parent.parent": module("nx.open(tiny.parent.parent / 'home')"),
    "os.path.join ..": module("nx.open(os.path.join(tiny, 'x/../../../../data/snap'))"),
    "join ..": module("nx.open(tiny / '../../data')"),
    "real copy beside synth": module(
        "make_snapshot(tmp_path / 's1')",
        "shutil.copytree(Path.home() / 's', tmp_path / 'real')",
        "nx.open(tmp_path / 'real')",
    ),
    # The second fresh-context review's bypasses and missed forms, as it gave them.
    "join a name holding /": module("a = '/data/snap'", "nx.open(tiny / a)"),
    "join Path.home()": module("nx.open(tiny / Path.home())"),
    "make_snapshot defined here": module("nx.open(make_snapshot(tmp_path / 's'))", head="")
    + "def make_snapshot(root):\n    return shutil.copytree(Path.home() / 'r', root)\n",
    "make_snapshot from elsewhere": module(
        "nx.open(make_snapshot(tmp_path / 's'))",
        head="from mylib import copy_real as make_snapshot\n",
    ),
    "open(path=)": module("nx.open(path='/data/snap')"),
    "nexusbt.api by another name": module(
        "a.open('/data/snap')", head=SYNTH + "from nexusbt import api as a\n"
    ),
}
PASSES = {  # the sources this part accepts; #599's next part adds the others
    "make_snapshot": module("r = make_snapshot(tmp_path)", "open_snapshot(DataConfig(path=r))"),
    "fixture, positional": module("open_snapshot(DataConfig(tiny))"),
    "Snapshot given": module("nx.run_pipeline(q, snapshot=nx.open(tiny))"),
    "a helper's return": SYNTH + "def made(at):\n    return make_snapshot(at / 's')\n\n"
    "def test_x(tmp_path):\n    nx.open(made(tmp_path))\n",
    "join a looped literal": module("for n in ('a', 'b'):", "    nx.open(tiny / n)"),
}


@pytest.mark.parametrize("body", FAILS.values(), ids=FAILS)
def test_a_snapshot_opened_from_a_literal_or_unknown_path_fails(body: str) -> None:
    assert len(findings(NAME, body)) == 1


@pytest.mark.parametrize("body", PASSES.values(), ids=PASSES)
def test_a_snapshot_opened_from_a_synthetic_source_passes(body: str) -> None:
    assert findings(NAME, body) == []


def test_a_finding_names_the_file_and_the_line() -> None:
    body = 'import nexusbt as nx\n\n\ndef test_x():\n    nx.open("data/snap")\n'
    assert findings(NAME, body) == [
        f"{NAME}:5: snapshot path `'data/snap'` not from a synthetic source"
    ]
