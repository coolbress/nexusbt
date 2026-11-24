"""#649, spec 3.10: in the CLI a 6.6 warning is printed on standard error in 6.6's shape alone,
once, with no Python `file:line: UserWarning:` prefix and no source line; the Python API and
the person's warning filters (`-W`, `PYTHONWARNINGS`) are as before."""

from __future__ import annotations

import os
import re
import subprocess
import sys
import warnings
from pathlib import Path

import pytest

import nexusbt as nx
from nexusbt import api
from nexusbt.api import _doctor as api_doctor
from nexusbt.cli.main import main
from nexusbt.contracts import VerifyPolicy
from nexusbt.data import DataConfig, open_snapshot
from nexusbt.testing.synth import make_snapshot

#: A process with no `-W` runs Python's default filter; this repository's tests turn every
#: warning into an error (pyproject), so the commands run here under Python's default.
pytestmark = pytest.mark.filterwarnings("default")

#: `tiny` of KR and the untested ZZ without tick information: one E30 for F-15 (4.5), a
#: `fallback` line for ZZ (F-01, F-18 and F-03, the samples before, leave, #705).
F15 = ["fallback   F-15 market_rules ZZ 6"]
UNTESTED = "\n[markets]\nallow_untested = true\n"  # ZZ has no rules pack


@pytest.fixture(scope="module")
def package(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return make_snapshot(tmp_path_factory.mktemp("pkg") / "s1", preset="tiny",
                         markets=("KR", "ZZ"), degrade=["no_tick_info"])  # fmt: skip


@pytest.fixture
def project(package: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An empty folder whose `nexusbt.toml` names `package` and allows ZZ."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("NEXUSBT_DATA_ROOT", raising=False)
    assert main(["init", "--data-root", str(package)]) == 0
    with (tmp_path / "nexusbt.toml").open("a", encoding="utf-8") as toml:
        toml.write(UNTESTED)
    return tmp_path


def announced(package: Path) -> list[str]:
    """The E30 texts opening gives in Python, as the toml says: still a warning there (4.5,
    INV-12)."""
    with pytest.warns(UserWarning, match=r"^DataProfileWarning \[E30\] ") as given:
        open_snapshot(DataConfig(path=package, allow_untested=True))
    return [str(w.message) for w in given]


def test_doctor_prints_the_warning_in_its_own_shape_once(
    package: Path, project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    capsys.readouterr()
    assert main(["doctor"]) == 0
    out, err = capsys.readouterr()
    (e30,) = announced(package)
    assert e30.startswith("DataProfileWarning [E30] F-15\n  layer  data — snapshot")
    assert err == e30 + "\n"  # no prefix, no source line, nothing else
    for python in ("UserWarning", "_doctor.py", "open_snapshot"):  # its prefix and source line
        assert python not in err
    assert [line for line in out.splitlines() if line.startswith("fallback")] == F15


def test_the_python_api_still_warns_after_a_command(
    package: Path, project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The CLI's printer is the command's alone: once it returns, opening warns as before."""
    assert main(["doctor"]) == 0
    with pytest.warns(UserWarning, match=r"^DataProfileWarning \[E30\] F-15\n"):
        open_snapshot(DataConfig(path=package, allow_untested=True))


def test_stubs_prints_the_warning_the_same_way(
    package: Path, project: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:  # fmt: skip
    """Every command, not `doctor` alone (#649 Decisions 3): `stubs` opens the snapshot too."""
    monkeypatch.setattr(api, "_STUBS", project / "datasets.pyi")  # not the tracked file
    capsys.readouterr()
    assert main(["stubs"]) == 0
    out, err = capsys.readouterr()
    assert out == f"{project / 'datasets.pyi'}\n"
    assert err == announced(package)[0] + "\n"


def test_distinct_warnings_each_once(
    tmp_path: Path, project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Two fallbacks from the same line of `doctor` are two warnings, neither dropped (F-16 of
    KR's volume in lots at `full` and F-15 of an untested market, since F-02 and F-03 retired,
    #705)."""
    both = make_snapshot(tmp_path / "both", preset="small", markets=("KR", "ZZ"), n_kr=6,
                         degrade=["volume_in_lots", "no_tick_info"])  # fmt: skip
    (project / "nexusbt.toml").unlink()
    assert main(["init", "--data-root", str(both)]) == 0
    toml = project / "nexusbt.toml"  # F-16 reads full's V011
    said = toml.read_text(encoding="utf-8").replace("[data]\n", '[data]\nverify = "full"\n')
    toml.write_text(said + UNTESTED, encoding="utf-8")
    capsys.readouterr()
    assert main(["doctor"]) == 0
    err = capsys.readouterr().err
    with pytest.warns(UserWarning, match=r"^DataProfileWarning \[E30\] ") as given:
        open_snapshot(DataConfig(path=both, allow_untested=True, verify=VerifyPolicy.FULL))
    e30s = [str(w.message) for w in given]
    assert [t.split("\n", 1)[0] for t in e30s] == [
        "DataProfileWarning [E30] F-16",
        "DataProfileWarning [E30] F-15",
    ]  # in the records' order (4.5), as the `fallback` lines are
    assert err == "".join(t + "\n" for t in e30s)


def test_a_repeated_warning_is_printed_once_and_another_too(
    project: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The same text given again from the same place in one command is printed once (Python's
    default filter, as before #649); a different text is printed too."""
    e30 = str(nx.DataProfileWarning.example())
    other = e30.replace("F-08", "F-09")

    def doctor() -> str:
        for text in (e30, e30, other):
            warnings.warn(text, stacklevel=1)
        return "result"

    monkeypatch.setattr(api_doctor, "doctor", doctor)
    capsys.readouterr()
    assert main(["doctor"]) == 0
    assert capsys.readouterr() == ("result\n", f"{e30}\n{other}\n")


def test_a_library_warning_is_left_to_python(
    project: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A warning not in 6.6's shape goes to Python's own printer, unchanged."""

    def doctor() -> str:
        warnings.warn("a library's own warning", DeprecationWarning, stacklevel=1)
        return "result"

    monkeypatch.setattr(api_doctor, "doctor", doctor)
    capsys.readouterr()
    with pytest.warns(DeprecationWarning, match="a library's own warning"):
        assert main(["doctor"]) == 0
    assert capsys.readouterr() == ("result\n", "")


#: `nexusbt` as the console script runs it, in a process of its own so `-W` applies.
SCRIPT = "import sys; from nexusbt.cli.main import main; sys.exit(main())"


@pytest.mark.parametrize(
    ("flags", "env", "code"),
    [([], {}, 0), (["-W", "ignore"], {}, 0), (["-W", "always"], {}, 0),
     (["-W", "error"], {}, 1), ([], {"PYTHONWARNINGS": "error"}, 1)],
    ids=["no-filter", "W-ignore", "W-always", "W-error", "PYTHONWARNINGS-error"],
)  # fmt: skip
def test_the_persons_filters_act_as_before(
    package: Path, project: Path, flags: list[str], env: dict[str, str], code: int
) -> None:
    """Python applies a filter before it prints, so the filters act as on `main` before #649:
    `ignore` prints nothing, `error` stops with Python's traceback and exit code 1 (#649,
    the owner's answer of 2026-11-21: this pull request changes the shape, not the filters)."""
    unset = ("PYTHONWARNINGS", "NEXUSBT_DATA_ROOT")
    clean = {k: v for k, v in os.environ.items() if k not in unset}
    done = subprocess.run(  # noqa: S603 - this interpreter, fixed arguments
        [sys.executable, *flags, "-c", SCRIPT, "doctor"],
        cwd=project, env=clean | env, capture_output=True, text=True, check=False,
    )  # fmt: skip
    assert done.returncode == code, done.stderr
    (e30,) = announced(package)
    if code == 1:  # the warning raised as an exception, out of `main`
        assert done.stderr.startswith("Traceback (most recent call last):\n")
        assert done.stderr.endswith(f"UserWarning: {e30}\n")
        assert done.stdout == ""
    else:
        assert done.stderr == ("" if "ignore" in flags else e30 + "\n")
        assert re.search(r"^fallback +F-15 market_rules ZZ 6$", done.stdout, re.M)
