"""The static check behind spec 2.7's `::test_fixtures_are_synthetic` (#599), on test modules
written here: what it must reject and what it must accept."""

from __future__ import annotations

from pathlib import Path

import pytest
from snapshot_sources import GUARD, PARITY_TEST, RUNNER, findings, guard_holds

ROOT = Path(__file__).resolve().parents[2]
NAME = "tests/unit/test_x.py"


SYNTH = "from nexusbt.testing.synth import make_snapshot\n"
CSV = SYNTH + "from nexusbt_tds import import_csv\n"
TINY = "@pytest.fixture\ndef tiny(tmp_path):\n    return make_snapshot(tmp_path / 'p')\n\n"
#: A helper opening the package `s1` in the data root it is given.
OPENED = SYNTH + "def opened(path):\n    return nx.open(path / 's1')\n\n"


def module(*lines: str, head: str = SYNTH) -> str:
    """A test module: a `tiny` fixture made by `make_snapshot`, and `test_x` running `lines`."""
    return head + TINY + "def test_x(tiny, tmp_path, p):\n" + "".join(f"    {s}\n" for s in lines)


FAILS = {  # a literal path never passes, nor what the trace cannot follow
    "literal path": module('open_snapshot(DataConfig(path="/data/snap"))'),
    "Path literal": module('nx.open(Path("/data/snap") / "s1")'),
    "snapshot= literal": module('run_pipeline(q, snapshot="data/snap")'),
    "snapshot= literal name": module('r = Path("~/s")', 'run_pipeline(q, snapshot=str(r / "s1"))'),
    "tds check f-string": module('pkg._tds("check", f"/data/{name}", "--level", "full")'),
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
    "tds check as one string": module("subprocess.run('tds check /data/snap', shell=True)"),
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
    "command in a name": module("cmd = ['tds', 'check', '/data/snap']", "subprocess.run(cmd)"),
    "command tuple": module("subprocess.run(('tds', 'check', '/data/snap'))"),
    "args= keyword": module("runner.invoke(cli, args=['check', '/data/snap'])"),
    "python -m nexusbt_tds": module("subprocess.run('python -m nexusbt_tds check /data/snap')"),
    "nexusbt_tds check()": module(
        "check('/data/snap')", head=SYNTH + "from nexusbt_tds import check\n"
    ),
    "nexusbt.api by another name": module(
        "a.open('/data/snap')", head=SYNTH + "from nexusbt import api as a\n"
    ),
    # Copies and imports: only of a synthetic source, from the test's own files.
    "import_csv of files outside": module(
        "k = import_csv(Path.home() / 'm.yaml', tmp_path / 'k')", "nx.open(k)", head=CSV
    ),
    "import_csv from elsewhere": module(
        "k = import_csv(tmp_path / 'm', tmp_path / 'k')",
        "nx.open(k)",
        head=SYNTH + "from mylib import import_csv\n",
    ),
    "copytree from elsewhere": module(
        "nx.open(copytree(tiny, tmp_path / 'c'))", head=SYNTH + "from mylib import copytree\n"
    ),
    # #630's item 10: a container changed after it is bound.
    "item set to a literal": module("d = {'a': tiny}", "d['a'] = '/data/snap'", "nx.open(d['a'])"),
    # Data roots: only in the test's own folder, and only on the way down to a package.
    "data root outside the temporary folder": OPENED + "def test_x(tmp_path):\n"
    "    d = Path.home() / 'x'\n    make_snapshot(d / 's1')\n    opened(d)\n",
    "beside the packages of a data root": module(
        "make_snapshot(tmp_path / 's1')", "nx.open(tmp_path / 'real')"
    ),
}
PASSES = {  # the sources the check accepts
    "make_snapshot": module("r = make_snapshot(tmp_path)", "open_snapshot(DataConfig(path=r))"),
    "fixture, positional": module("open_snapshot(DataConfig(tiny))"),
    "import_csv": module(
        "k = import_csv(tmp_path / 'm', tmp_path / 'k')", "nx.open(k)", "_tds('check', k)", head=CSV
    ),
    "copy": module("nx.open(shutil.copytree(tiny, tmp_path / 'c'))"),
    "data root": module(
        "make_snapshot(tmp_path / 's1')", "open_snapshot(DataConfig(path=tmp_path))"
    ),
    "data root, down to a package": OPENED
    + "def test_x(tmp_path):\n    make_snapshot(tmp_path / 's1')\n    opened(tmp_path)\n",
    "a helper writes into a folder given": SYNTH
    + "def write(at):\n    make_snapshot(at / 's1')\n\n"
    "def test_x(tmp_path):\n    write(tmp_path)\n    nx.open(tmp_path / 's1')\n",
    "data root from mktemp": module(
        "d = tmp_path_factory.mktemp('d')",
        "make_snapshot(d / 's1')",
        "open_snapshot(DataConfig(d))",
    ),
    "Snapshot given": module("nx.run_pipeline(q, snapshot=nx.open(tiny))"),
    "a file inside": module("for f in sorted(tiny.rglob('*')):", "    nx.open(f)"),
    "a helper's return": SYNTH + "def made(at):\n    return make_snapshot(at / 's')\n\n"
    "def test_x(tmp_path):\n    nx.open(made(tmp_path))\n",
    "option before the path": module("_tds('check', '--level', 'full', str(tiny))"),
    "join a looped literal": module("for n in ('a', 'b'):", "    nx.open(tiny / n)"),
    "items set in an empty dict": module("d = {}", "d['a'] = tiny", "nx.open(d['a'])"),
    "check closing its own list": module("parametrize(('source', 'check'), [('x', '/data/x')])"),
}


@pytest.mark.parametrize("body", FAILS.values(), ids=FAILS)
def test_a_snapshot_opened_from_a_literal_or_unknown_path_fails(body: str) -> None:
    assert len(findings(NAME, body)) == 1


@pytest.mark.parametrize("body", PASSES.values(), ids=PASSES)
def test_a_snapshot_opened_from_a_synthetic_source_passes(body: str) -> None:
    assert findings(NAME, body) == []


def test_a_join_a_caller_gives_is_followed_where_the_caller_is() -> None:
    """#631's `part()` followed what a caller gives a helper inside the helper, not inside the
    caller, so a name the caller loops over was never found there and the join was rejected."""
    body = SYNTH + "def opened(at, name):\n    return nx.open(at / name)\n\n"
    body += "def test_x(tmp_path):\n    for n in ('a', 'b'):\n"
    body += "        opened(make_snapshot(tmp_path / 's'), n)\n"
    assert findings(NAME, body) == []


def test_a_finding_names_the_file_and_the_line() -> None:
    body = 'import nexusbt as nx\n\n\ndef test_x():\n    nx.open("data/snap")\n'
    assert findings(NAME, body) == [
        f"{NAME}:5: snapshot path `'data/snap'` not from a synthetic source"
    ]


CONFORMANCE = "ROOT = Path(__file__).resolve().parents[1]\n\n" + module(
    "bad = shutil.copytree({src}, tmp_path / 'bad')", '_run(["check", str(bad)])'
)
REPO = 'ROOT / "tds" / "conformance" / "TDS-S002" / "fail"'
GUARDED = f"def {GUARD[1]}(tmp_path):\n    build.build(tmp_path)\n    assert tree(A) == tree(B)\n"
CONFORMANCE_CASES = [
    pytest.param(REPO, GUARDED, 0, id="the repository's packages, guarded"),
    pytest.param(REPO, GUARDED.replace("build.build", "copy"), 1, id="guard not rebuilding"),
    pytest.param(REPO, "def test_other():\n    assert True\n", 1, id="guard gone"),
    pytest.param("'tds/conformance/TDS-S002/fail'", GUARDED, 1, id="one literal"),
    pytest.param("'/repo/tds/conformance/TDS-S002/fail'", GUARDED, 1, id="absolute"),
    pytest.param(
        REPO.replace("ROOT", "Path(__file__).resolve().parents[2]"),
        GUARDED,
        1,
        id="outside the repository",
    ),
    pytest.param(REPO.replace("ROOT", "Path.cwd()"), GUARDED, 1, id="from the current folder"),
    pytest.param(REPO + ' / ".." / "x"', GUARDED, 1, id="up out of it"),
]


@pytest.mark.parametrize(("src", "guard", "found"), CONFORMANCE_CASES)
def test_a_conformance_package_passes_only_from_the_repository_and_guarded(
    src: str, guard: str, found: int
) -> None:
    """2.7: `tds/conformance/` packages are the output of `tds/conformance/build.py`, as the
    guard test shows by rebuilding them; any other way to reach such a folder fails."""
    body = CONFORMANCE.replace("{src}", src)
    assert len(findings("tests/test_x.py", body, guard)) == found


def test_the_guard_holds_on_the_repository() -> None:
    """The fact the conformance exception rests on, read from the guard file as it is now."""
    assert guard_holds((ROOT / GUARD[0]).read_text("utf-8"))


#: Test modules of this repository whose data roots go through helpers and `mktemp` (doctor)
#: and item assignments (`roots[name] = …`); the longest ones (`test_open_snapshot.py`,
#: `test_market_block.py`) take minutes without the memos, which is why they exist.
TRACED = ["tests/unit/cli/test_doctor.py", "tests/unit/api/test_run_pipeline_save.py"]


def test_the_memos_change_no_verdict() -> None:
    """The memos only keep the check fast: every case above, and two of the repository's
    modules with data roots, get the same findings with and without them."""
    bodies: list[tuple[str, str, str | None]] = [
        (NAME, b, None) for b in [*FAILS.values(), *PASSES.values()]
    ]
    for case in CONFORMANCE_CASES:
        src, text, _ = (str(v) for v in case.values)
        bodies.append(("tests/test_x.py", CONFORMANCE.replace("{src}", src), text))
    bodies += [(p, (ROOT / p).read_text("utf-8"), None) for p in TRACED]
    for name, body, guard in bodies:
        assert findings(name, body, guard) == findings(name, body, guard, remember=False), name


#: A parity runner as 8.1's: a helper makes the package (`{makes}`), `main` names it.
MAKES = 'tool("uv", "run", "python", "-m", "nexusbt.testing.synth", "--out", str(snapshot))'
RUNNER_TEXT = (
    "ROOT = Path(__file__).resolve().parents[3]\n\n"
    "def fixture(out):\n    snapshot = out / 'snapshot'\n    {makes}\n    return snapshot\n\n"
    "def main():\n    p = argparse.ArgumentParser()\n"
    "    p.add_argument('--fixture', choices=['small'], default='small')\n"
    "    p.add_argument('--out', type=Path, default=ROOT / '.scratch' / 'parity')\n"
    "    out = p.parse_args().out\n    snapshot = fixture(out)\n"
    "    manifest = {{'snapshot': str(snapshot)}}\n"
)
#: A parity test as `test_L1.py`: its `manifest` fixture reads the runner's manifest.
PARITY = (
    "import json\nfrom pathlib import Path\nimport nexusbt as nx\n\n"
    "ROOT = Path(__file__).resolve().parents[2]\nOUT = ROOT / '.scratch' / 'parity' / 'small'\n\n"
    "@pytest.fixture(scope='module')\ndef manifest():\n    path = {path}\n"
    "    found = json.loads(path.read_text(encoding='utf-8'))\n    return found\n\n"
    "def test_x(manifest):\n    {opens}\n"
)
OPENS = "nx.run_pipeline(p, snapshot=manifest['snapshot'])"


def parity(path: str = "OUT / 'manifest.json'", opens: str = OPENS) -> str:
    return PARITY.format(path=path, opens=opens)


@pytest.mark.parametrize(
    ("name", "body", "makes", "found"),
    [
        pytest.param(PARITY_TEST, parity(), MAKES, 0, id="the runner's manifest"),
        pytest.param(
            PARITY_TEST, parity(), "shutil.copytree(SOURCE, snapshot)", 1, id="runner copytree"
        ),
        pytest.param(
            PARITY_TEST,
            parity(),
            MAKES.replace("(snapshot)", "(out)"),
            1,
            id="runner's other --out",
        ),
        pytest.param("tests/unit/test_x.py", parity(), MAKES, 1, id="another file"),
        pytest.param(
            PARITY_TEST,
            parity(opens="manifest = {'snapshot': '/data/x'}\n    " + OPENS),
            MAKES,
            1,
            id="a manifest dict the test builds",
        ),
        pytest.param(
            PARITY_TEST,
            parity(path="Path.home() / 'manifest.json'"),
            MAKES,
            1,
            id="fixture reads another file",
        ),
        pytest.param(
            PARITY_TEST,
            parity(path="ROOT / 'manifest.json'"),
            MAKES,
            1,
            id="fixture reads outside OUT",
        ),
        pytest.param(
            PARITY_TEST,
            parity(opens=OPENS.replace("'snapshot']", "'fixture']")),
            MAKES,
            1,
            id="another key",
        ),
        pytest.param(
            PARITY_TEST,
            parity()
            + "\ndef opens(manifest):\n    nx.open(manifest['snapshot'])\n\n"
            + "def test_y():\n    opens({'snapshot': '/data/x'})\n",
            MAKES,
            1,
            id="a helper given a manifest dict",
        ),
        pytest.param(
            PARITY_TEST,
            parity(
                opens="def inner(manifest):\n        nx.open(manifest['snapshot'])\n"
                "    inner({'snapshot': '/data/x'})"
            ),
            MAKES,
            1,
            id="a nested function given a manifest dict",
        ),
    ],
)
def test_the_parity_manifest_passes_only_as_the_runner_makes_it(
    name: str, body: str, makes: str, found: int
) -> None:
    """2.7: the package 8.1's parity runner writes with the generator's command and names in
    its manifest, opened in `PARITY_TEST` from the fixture that reads that manifest."""
    assert len(findings(name, body, runner=RUNNER_TEXT.format(makes=makes))) == found


def test_the_parity_exception_holds_only_while_the_runner_writes_the_generator_output() -> None:
    """The repository's own runner and parity test: the two openings pass, and fail again
    when one line of a copy of the runner gives the generator another `--out`."""
    runner, test = (ROOT / RUNNER).read_text("utf-8"), (ROOT / PARITY_TEST).read_text("utf-8")
    broken = runner.replace('"--out", str(snapshot)', '"--out", str(out)')
    assert broken != runner
    assert findings(PARITY_TEST, test, runner=runner) == []
    assert len(findings(PARITY_TEST, test, runner=broken)) == 2
