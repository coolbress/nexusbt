"""Spec 2.7: the public repository holds nothing private (#47).

The files read are git's: tracked ones plus new ones not yet ignored, so a file
created and not yet added is caught too. A file that is not UTF-8 text is not read.

The private words live outside the repository, one per line (`#` starts a comment):
the file `NEXUSBT_HYGIENE_WORDS_FILE` names, else the git-ignored `.hygiene-private.txt`
at the root. Without either, the word part checks nothing and the rest still runs;
CI has no list. A word found is reported by file and line, never spelled out.
"""

from __future__ import annotations

import os
import re
import subprocess
import tomllib
from collections.abc import Callable
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
WORDS_ENV = "NEXUSBT_HYGIENE_WORDS_FILE"

#: A macOS home path: `/Users/` followed by an account name.
HOME = re.compile(r"/Users/[\w.-]")
#: 2.7, as written: four-number private addresses only.
PRIVATE_IP = re.compile(
    r"(?<![\d.])(10(\.\d{1,3}){3}|192\.168(\.\d{1,3}){2}|172\.(1[6-9]|2\d|3[01])(\.\d{1,3}){2})(?!\.?\d)"
)
#: 2.7 `::test_no_producer_internal_refs`, as written.
TICKET = re.compile(r" X[0-9]+ ")
LOCK = ".rebuild.lock"
#: The one line that quotes the patterns while defining the rule: spec 2.7's bullet, starting
#: with this, in both editions (#47). The ticket's acceptance line names the test and is checked.
RULE_LINE = {
    "docs/spec/engine-spec-v3.4.md": "- `::test_no_producer_internal_refs` —",
    "docs/spec/engine-spec-v3.4.ko.md": "- `::test_no_producer_internal_refs` —",
}
DATA_SUFFIX = (".parquet", ".duckdb", ".csv")
DATA_ALLOWED = ("src/nexusbt/resources/", "tds/conformance/")

#: (file name, its text, the private words) → findings.
TextCheck = Callable[[str, str, list[str]], list[str]]


def repo_files(root: Path) -> list[str]:
    """Tracked files and new ones git does not ignore, that exist on disk."""
    done = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],  # noqa: S607
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "LC_ALL": "C"},
    )
    if done.returncode != 0:  # a check that turns green for no reason is worse than none
        raise AssertionError(f"`git ls-files` failed: {done.stderr.strip()}")
    return sorted({p for p in done.stdout.split("\0") if p and (root / p).is_file()})


def read_text(path: Path) -> str | None:
    data = path.read_bytes()
    if b"\0" in data:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def banned_words(root: Path = ROOT) -> list[str]:
    named = os.environ.get(WORDS_ENV)
    path = Path(named) if named else root / ".hygiene-private.txt"
    if not path.is_file():
        assert not named, f"{WORDS_ENV} names {named}, which is not a file"
        return []
    lines = (line.split("#", 1)[0].strip() for line in path.read_text("utf-8").splitlines())
    return [w.casefold() for w in lines if w]


def word_hits(name: str, text: str, words: list[str]) -> list[str]:
    return [
        f"{name}:{n}: a word from the private list"
        for n, line in enumerate(text.splitlines(), 1)
        if any(w in line.casefold() for w in words)
    ]


def private_hits(name: str, text: str, words: list[str]) -> list[str]:
    """`::test_no_private_paths`: a home path, a private word or a private address."""
    out = word_hits(name, text, words)
    for n, line in enumerate(text.splitlines(), 1):
        out += [f"{name}:{n}: home path" for _ in HOME.finditer(line)]
        out += [f"{name}:{n}: private address" for _ in PRIVATE_IP.finditer(line)]
    return out


def internal_refs(name: str, text: str, words: list[str]) -> list[str]:
    """`::test_no_producer_internal_refs`: a private word, the ticket shape or the lock file."""
    out = word_hits(name, text, words)
    marker = RULE_LINE.get(name)
    for n, line in enumerate(text.splitlines(), 1):
        if marker and line.startswith(marker):
            continue
        if TICKET.search(line) or LOCK in line:
            out.append(f"{name}:{n}: producer-internal reference")
    return out


def scan(root: Path, check: TextCheck, prefixes: tuple[str, ...] = ("",)) -> list[str]:
    words = banned_words(root)
    out: list[str] = []
    for name in repo_files(root):
        if name.startswith(prefixes) and (text := read_text(root / name)) is not None:
            out += check(name, text, words)
    return out


def data_files(names: list[str]) -> list[str]:
    return [n for n in names if n.lower().endswith(DATA_SUFFIX) and not n.startswith(DATA_ALLOWED)]


def ported_problems(notice: str, root: Path) -> list[str]:
    """2.1 (5): a file NOTICE lists as ported names its repository, commit and licence."""
    out = []
    for name in re.findall(r"\b(?:tds/)?src/\S+\.py\b", notice):
        head = "\n".join((root / name).read_text("utf-8").splitlines()[:30]).casefold()
        missing = [part for part in ("https://", "commit", "licen") if part not in head]
        if missing:
            out.append(f"{name}: header lacks {missing}")
    return out


def test_no_private_paths() -> None:
    assert scan(ROOT, private_hits) == []


def test_no_producer_internal_refs() -> None:
    assert scan(ROOT, internal_refs, ("src/", "tds/src/", "docs/")) == []


def test_tds_public_has_no_producer_names() -> None:
    """The public TDS documents and package: docs/tds/ and tds/ (#47; 2.7 names one file)."""
    assert scan(ROOT, internal_refs, ("docs/tds/", "tds/")) == []


def test_no_data_files() -> None:
    assert data_files(repo_files(ROOT)) == []


def test_license_headers() -> None:
    licence = (ROOT / "LICENSE").read_text("utf-8")
    assert "Apache License" in licence
    assert "Version 2.0, January 2004" in licence
    for pyproject in ("pyproject.toml", "tds/pyproject.toml"):
        project = tomllib.loads((ROOT / pyproject).read_text("utf-8"))["project"]
        assert project["license"] == "Apache-2.0", pyproject
    assert ported_problems((ROOT / "NOTICE").read_text("utf-8"), ROOT) == []


SPEC_EN = "docs/spec/engine-spec-v3.4.md"
dotted = ".".join  # the samples are built, so this file holds no address for the scan to find


@pytest.mark.parametrize(
    "text", ["section 10.2", "10.2.3", "172.16", "192.168.1.2.3", "see 10.2 and 172.32.0.1"]
)
def test_section_numbers_not_ip(text: str) -> None:
    assert private_hits("doc.md", text, []) == []


@pytest.mark.parametrize(
    "parts", [("10", "0", "0", "1"), ("192", "168", "1", "20"), ("172", "31", "255", "255")]
)
def test_private_address_is_caught(parts: tuple[str, ...]) -> None:
    assert private_hits("doc.md", f"host at {dotted(parts)}.", []) != []


def test_planted_files_fail_and_a_section_number_passes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Done means (#47): a new file with a home path or a producer name + ticket fails."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)  # noqa: S603, S607 - pytest's tmp
    words = tmp_path.parent / f"{tmp_path.name}-words.txt"
    words.write_text("# private\nacmedata\n", encoding="utf-8")
    monkeypatch.setenv(WORDS_ENV, str(words))
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "ok.md").write_text("See section 10.2.\n", encoding="utf-8")
    assert scan(tmp_path, private_hits) == []
    assert scan(tmp_path, internal_refs, ("docs/",)) == []

    home = "/".join(("", "Users", "someone", "x"))  # built, like the addresses below
    (tmp_path / "notes.txt").write_text(f"data in {home}\n", encoding="utf-8")
    assert scan(tmp_path, private_hits) == ["notes.txt:1: home path"]
    (tmp_path / "docs" / "bad.md").write_text("AcmeData fixed it in X12 today.\n", "utf-8")
    assert scan(tmp_path, internal_refs, ("docs/",)) == [
        "docs/bad.md:1: a word from the private list",
        "docs/bad.md:1: producer-internal reference",
    ]
    assert scan(tmp_path, private_hits) == [
        "docs/bad.md:1: a word from the private list",
        "notes.txt:1: home path",
    ]


@pytest.mark.parametrize(
    ("name", "line", "hits"),
    [
        ("src/nexusbt/x.py", "see X12 for why", 1),
        ("docs/a.md", "remove the .rebuild.lock first", 1),
        ("docs/a.md", "instrument X1, 2020-03-02", 0),
        (SPEC_EN, "- `::test_no_producer_internal_refs` — .rebuild.lock", 0),
        (SPEC_EN, "a later line naming .rebuild.lock", 1),
        (SPEC_EN, "- Acceptance: `::test_no_producer_internal_refs`, .rebuild.lock", 1),
    ],
)
def test_internal_refs_cases(name: str, line: str, hits: int) -> None:
    assert len(internal_refs(name, line, [])) == hits


def test_data_files_cases() -> None:
    names = ["a/b.parquet", "x.CSV", "s.duckdb", "src/nexusbt/resources/costs.csv"]
    assert data_files([*names, "tds/conformance/ok/bars.csv", "README.md"]) == names[:3]


def test_ported_file_without_header_is_caught(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "p.py").write_text('"""Ported from https://x, MIT License."""\n', "utf-8")
    assert ported_problems("Ported: src/p.py", tmp_path) == ["src/p.py: header lacks ['commit']"]
