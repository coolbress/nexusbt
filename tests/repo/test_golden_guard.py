"""An implementation pull request does not change the golden answers (spec 8.2, 9.1).

`tests/golden/cases/**`, `tests/golden/check/**` and `tests/golden/factors/**` (T-25's built-in
factor cases, spec 3.4) change only in a golden ticket's pull
request, titled `test(golden): …` (9.1's `engine / golden-guard` row). In CI the title is read
from the event JSON Actions writes at `GITHUB_EVENT_PATH`; without a pull request there (a local
run, a push), a current branch named `test/golden-…` stands in for it (#59 Decisions). The
changes are those since the merge base with `origin/main`, uncommitted and untracked ones
included; a shallow checkout fetches what that needs. CODEOWNERS is the other half of the guard.
"""

from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Iterable, Sequence
from pathlib import Path

import pytest

pytestmark = pytest.mark.repo

GUARDED = ("tests/golden/cases/", "tests/golden/check/", "tests/golden/factors/")
GOLDEN_TITLE = "test(golden):"
GOLDEN_BRANCH = "test/golden-"
BASE = "main"
ROOT = Path(__file__).resolve().parents[2]  # the guarded paths are relative to the repository


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        ["git", *args],  # noqa: S607
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def _out(*args: str) -> str:
    done = _git(*args)
    assert done.returncode == 0, f"`git {' '.join(args)}` failed: {done.stderr.strip()}"
    return done.stdout


def refused(paths: Iterable[str], *, title: str | None, branch: str | None) -> list[str]:
    """The guarded paths among `paths` that this pull request may not change."""
    if title is not None:
        golden = title.startswith(GOLDEN_TITLE)
    else:
        golden = branch is not None and branch.startswith(GOLDEN_BRANCH)
    return [] if golden else sorted(p for p in paths if p.startswith(GUARDED))


def pull_request_title(event_path: str | None) -> str | None:
    """The pull request title in the Actions event JSON, None when there is no pull request."""
    if not event_path:
        return None
    event = json.loads(Path(event_path).read_text())
    pr = event.get("pull_request")
    return None if pr is None else str(pr["title"])


def merge_base() -> str:
    """The merge base of HEAD with origin/main, fetching main and history when they are missing."""
    if _git("merge-base", f"origin/{BASE}", "HEAD").returncode != 0:
        shallow = _out("rev-parse", "--is-shallow-repository").strip() == "true"
        spec = f"+refs/heads/{BASE}:refs/remotes/origin/{BASE}"
        _out("fetch", "--no-tags", *(["--unshallow"] if shallow else []), "origin", spec)
    return _out("merge-base", f"origin/{BASE}", "HEAD").strip()


def changed_paths(base: str) -> Sequence[str]:
    """Paths changed since `base`: committed, uncommitted and untracked."""
    # --no-renames: a golden file moved out of the guarded folders shows as its deletion too.
    tracked = _out("diff", "--name-only", "--no-renames", base).splitlines()
    untracked = _out("ls-files", "--others", "--exclude-standard", *GUARDED).splitlines()
    return tracked + untracked


def test_impl_pr_cannot_edit_expected() -> None:
    title = pull_request_title(os.environ.get("GITHUB_EVENT_PATH"))
    branch = _out("rev-parse", "--abbrev-ref", "HEAD").strip()
    found = refused(changed_paths(merge_base()), title=title, branch=branch)
    assert not found, (
        f"only a `{GOLDEN_TITLE} …` pull request changes the golden answers (spec 8.2): "
        f'{found}; if the spec is wrong, say "spec deviation" and reopen the golden ticket'
    )


@pytest.mark.parametrize(
    ("title", "branch", "expected"),
    [
        ("feat(execution): fill market orders", "feat/x", ["tests/golden/cases/G-01.yaml"]),
        ("test(golden): G-02 limit buy", "feat/x", []),  # the title decides in CI
        ("feat(execution): x", "test/golden-g02", ["tests/golden/cases/G-01.yaml"]),
        (None, "test/golden-g02", []),  # no pull request: the branch stands in
        (None, "feat/x", ["tests/golden/cases/G-01.yaml"]),
    ],
)
def test_the_rule(title: str | None, branch: str, expected: list[str]) -> None:
    paths = ["tests/golden/cases/G-01.yaml", "tests/golden/test_handcalc_self.py", "src/a.py"]
    assert refused(paths, title=title, branch=branch) == expected


def test_factor_cases_are_guarded() -> None:
    path = "tests/golden/factors/Returns.yaml"
    assert refused([path], title="feat(compute): built-in factors", branch="feat/x") == [path]
    assert refused([path], title="test(golden): T-25", branch="feat/x") == []


def test_title_from_the_event_json(tmp_path: Path) -> None:
    event = tmp_path / "event.json"
    event.write_text(json.dumps({"pull_request": {"title": "test(golden): G-01"}}))
    assert pull_request_title(str(event)) == "test(golden): G-01"
    event.write_text(json.dumps({"ref": "refs/heads/main"}))  # a push has no pull request
    assert pull_request_title(str(event)) is None
    assert pull_request_title(None) is None
