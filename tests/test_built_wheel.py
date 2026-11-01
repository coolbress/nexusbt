"""The two packages as a person gets them: built into wheels, imported from those wheels.

The packages' own tests import the source trees. A module a wheel leaves out,
or a public name that exists only in a source tree, passes there and fails
here. The wheels are built with `uv build --all-packages` (spec 9.1; the build
backend is fetched the first time, as the `uv build` check does) and imported
from the files themselves, ahead of the source trees on the path.

When you change the public name or how the package is built, change this test
with it.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

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


def test_both_packages_import_from_their_built_wheels(tmp_path: Path) -> None:
    uv = shutil.which("uv")
    assert uv, "uv is not on PATH: this test builds the wheels with `uv build`"
    built = subprocess.run(  # noqa: S603
        [uv, "build", "--all-packages", "--wheel", "--out-dir", str(tmp_path), str(ROOT)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert built.returncode == 0, f"uv build failed\n{built.stdout}\n{built.stderr}"
    wheels = sorted(str(w) for w in tmp_path.glob("*.whl"))
    assert len(wheels) == 2, wheels
    done = subprocess.run(  # noqa: S603
        [sys.executable, "-I", "-c", CALL, *wheels],
        capture_output=True,
        text=True,
        check=False,
        cwd=tmp_path,
        timeout=60,
    )
    assert done.returncode == 0, f"exit {done.returncode}\n{done.stdout}\n{done.stderr}"
    assert done.stdout.startswith("nexusbt\nnexusbt_tds\nusage: tds")
