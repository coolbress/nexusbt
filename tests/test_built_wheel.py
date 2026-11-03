"""The two packages as a person gets them: built into wheels, imported from those wheels.

The packages' own tests import the source trees. A module a wheel leaves out,
or a public name that exists only in a source tree, passes there and fails
here. The wheels are built with `uv build --all-packages` (spec 9.1; the build
backend is fetched the first time, as the `uv build` check does), from each
sdist as a release builds them, and imported from the files themselves, ahead
of the source trees on the path. The checker's schema files are package data
that the wheel must carry (#145).

When you change the public name or how the package is built, change this test
with it.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from nexusbt.testing.synth import make_snapshot
from nexusbt_tds.check import SCHEMA_CODES

ROOT = Path(__file__).resolve().parents[1]

# Runs in a fresh interpreter: the wheels go first on the path, and each module
# must come from one of them, not from the source tree the environment also
# holds. `tds --help` is the install check of spec 9.1.
CALL = """
import sys
wheels = sys.argv[1:]
sys.path[:0] = wheels
import nexusbt, nexusbt_tds
for package in (nexusbt, nexusbt_tds):
    assert any(package.__file__.startswith(w) for w in wheels), package.__file__
    print(package.__name__)
from nexusbt_tds.cli import main
try: main(["--help"])
except SystemExit as done: assert done.code == 0, done.code
"""


# `tds <argv>` from the wheels only, its stdout and exit code: the checker reads the schema
# files from the installed package, never from a checkout (#145).
TDS = """
import sys
wheels, argv = sys.argv[1:3], sys.argv[3:]
sys.path[:0] = wheels
from nexusbt_tds.cli import main
sys.exit(main(argv))
"""


@pytest.fixture(scope="module")
def wheels(tmp_path_factory: pytest.TempPathFactory) -> list[str]:
    out = tmp_path_factory.mktemp("wheels")
    uv = shutil.which("uv")
    assert uv, "uv is not on PATH: this test builds the wheels with `uv build`"
    built = subprocess.run(  # noqa: S603
        [uv, "build", "--all-packages", "--out-dir", str(out), str(ROOT)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert built.returncode == 0, f"uv build failed\n{built.stdout}\n{built.stderr}"
    found = sorted(str(w) for w in out.glob("*.whl"))
    assert len(found) == 2, found
    return found


def _run(code: str, args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    assert ROOT not in cwd.resolve().parents, cwd  # outside the repository tree
    return subprocess.run(  # noqa: S603
        [sys.executable, "-I", "-c", code, *args],
        capture_output=True,
        text=True,
        check=False,
        cwd=cwd,
        timeout=120,
    )


def test_both_packages_import_from_their_built_wheels(wheels: list[str], tmp_path: Path) -> None:
    done = _run(CALL, wheels, tmp_path)
    assert done.returncode == 0, f"exit {done.returncode}\n{done.stdout}\n{done.stderr}"
    assert done.stdout.startswith("nexusbt\nnexusbt_tds\nusage: tds")


def test_the_wheel_checks_and_hashes_with_its_own_schemas(
    wheels: list[str], tmp_path: Path
) -> None:
    root = make_snapshot(tmp_path / "pkg", preset="tiny")  # hashes written by the source tree
    level = ["--level", "schema", "--format", "json"]
    checked = _run(TDS, [*wheels, "check", str(root), *level], root)
    assert checked.returncode == 0, f"exit {checked.returncode}\n{checked.stdout}{checked.stderr}"
    summary = json.loads(checked.stdout.splitlines()[-1])["summary"]
    assert summary["level"] == "schema"
    assert [c for c in SCHEMA_CODES if c in summary["unchecked"]] == []

    # Checked, not skipped: a column of the wrong type is found from the wheel's schema files.
    bad = shutil.copytree(ROOT / "tds" / "conformance" / "TDS-S002" / "fail", tmp_path / "bad")
    failed = _run(TDS, [*wheels, "check", str(bad), *level], bad)
    assert failed.returncode == 1, f"exit {failed.returncode}\n{failed.stdout}{failed.stderr}"
    codes = [json.loads(line).get("code") for line in failed.stdout.splitlines()]
    assert "TDS-S002" in codes

    hashed = _run(TDS, [*wheels, "hash", str(root)], root)
    assert hashed.returncode == 0, f"exit {hashed.returncode}\n{hashed.stdout}{hashed.stderr}"
    declared = json.loads((root / "tds.json").read_text(encoding="utf-8"))["hashes"]
    lines = dict(line.split(" ", 1) for line in hashed.stdout.splitlines())  # `<name> <value>`
    assert lines["value_sha256"] == declared["value_sha256"]
