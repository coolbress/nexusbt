"""`nexusbt-tds` is released on its own `tds-v*` tags, apart from the engine's `v*` (2.3, #444).

The template's `release.yml` decides which package a tag releases in its first step, "Check
the tag against pyproject.toml's version". This test reads that step from the workflow file
as it stands, not a copy, and runs it against this repository's `pyproject.toml` files. It
does not build or upload: `uv build` and PyPI are the tag run's.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/release.yml"
STEP = "- name: Check the tag against pyproject.toml's version"


def _tag_step() -> str:
    text = WORKFLOW.read_text(encoding="utf-8")
    after = text[text.index(STEP) :]
    found = re.search(r"python3 - <<'PY'\n(.*?)\n *PY\n", after, flags=re.DOTALL)
    assert found, f"{WORKFLOW.name}: no Python heredoc under {STEP!r}"
    lines = found[1].splitlines()
    indent = min(len(line) - len(line.lstrip()) for line in lines if line.strip())
    return "\n".join(line[indent:] for line in lines) + "\n"


def _run(tmp_path: Path, tag: str, tds_version: str | None = None) -> tuple[int, str, Path]:
    """Run the step on `tag` in a copy of the two pyproject files; its exit code, output, temp."""
    work, temp = tmp_path / "repo", tmp_path / "runner"
    (work / "tds").mkdir(parents=True)
    temp.mkdir()
    shutil.copy(ROOT / "pyproject.toml", work / "pyproject.toml")
    tds = (ROOT / "tds/pyproject.toml").read_text(encoding="utf-8")
    if tds_version is not None:
        tds = re.sub(r'(?m)^version = ".*"$', f'version = "{tds_version}"', tds, count=1)
    (work / "tds/pyproject.toml").write_text(tds, encoding="utf-8")
    env = {**os.environ, "GITHUB_REF_NAME": tag, "RUNNER_TEMP": str(temp)}
    env.pop("GITHUB_OUTPUT", None)
    done = subprocess.run(
        [sys.executable, "-"],
        input=_tag_step(),
        cwd=work,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    return done.returncode, done.stdout + done.stderr, temp


def _read(temp: Path, name: str) -> str:
    return (temp / f"release-{name}").read_text(encoding="utf-8")


def test_an_engine_v_tag_releases_the_engine_and_leaves_nexusbt_tds_out(tmp_path: Path) -> None:
    code, out, temp = _run(tmp_path, "v0.1.0")
    assert code == 0, out
    assert _read(temp, "member") == ""
    # Left out of dist/ after the build, and needed on the index before the upload.
    assert _read(temp, "listed").split() == ["nexusbt_tds"]
    assert _read(temp, "needs") == "nexusbt-tds>=1.0,<2\ttds-\n"


def test_a_tds_v_tag_releases_nexusbt_tds_alone(tmp_path: Path) -> None:
    code, out, temp = _run(tmp_path, "tds-v1.0.0", tds_version="1.0.0")
    assert code == 0, out
    assert _read(temp, "member") == "nexusbt-tds"


def test_a_release_candidate_tag_matches_its_pep_440_version(tmp_path: Path) -> None:
    code, out, temp = _run(tmp_path, "tds-v1.0.0-rc.1", tds_version="1.0.0rc1")
    assert code == 0, out
    assert _read(temp, "member") == "nexusbt-tds"


@pytest.mark.parametrize(
    ("tag", "tds_version"), [("tds-v1.0.1", "1.0.0"), ("tds-v1.0.0-rc.2", "1.0.0rc1")]
)
def test_a_tds_v_tag_that_differs_from_the_version_stops_before_any_upload(
    tmp_path: Path, tag: str, tds_version: str
) -> None:
    code, out, temp = _run(tmp_path, tag, tds_version=tds_version)
    assert code != 0
    assert "The tag and the version differ" in out
    assert not (temp / "release-member").exists()
