"""#466: `nexusbt init` writes the first `[research] family_id`; `--new-family` replaces it (3.10,
3.11, 6.2)."""

from __future__ import annotations

import sqlite3
import uuid
from contextlib import closing
from pathlib import Path

import pytest

from nexusbt.cli.main import main
from nexusbt.config import load_config

TOML = "nexusbt.toml"
OLD = "0b9e7a55-1c7e-4b0a-9a3f-2f4d6c8e0a1b"


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("NEXUSBT_DATA_ROOT", raising=False)
    (tmp_path / "root").mkdir()
    (tmp_path / "root" / "LATEST").write_text("s1\n", encoding="utf-8")  # what load_config needs
    return tmp_path


def family_id(project: Path) -> str:
    found = load_config(project / TOML).values["research"]["family_id"]
    assert isinstance(found, str)
    assert uuid.UUID(found).version == 4
    return found


def test_init_writes_a_family_id(project: Path) -> None:
    """When I run `nexusbt init --data-root PATH` in an empty folder, then `nexusbt.toml` has
    `[data]` and `[research] family_id`."""
    assert main(["init", "--data-root", str(project / "root")]) == 0
    family_id(project)
    assert load_config(project / TOML).values["data"]["root"] == str(project / "root")


@pytest.mark.parametrize(
    ("before", "after"),
    [  # ID stands for the new id
        (b'# mine\r\n[data]\r\nroot = "root"  # kept\r\n\r\n[runs]\r\ndir = "runs"',
         b'# mine\r\n[data]\r\nroot = "root"  # kept\r\n\r\n[runs]\r\ndir = "runs"'
         b'\r\n\r\n[research]\r\nfamily_id = "ID"\r\n'),
        (b'[data]\nroot = "root"\n', b'[data]\nroot = "root"\n\n[research]\nfamily_id = "ID"\n'),
        (b"", b'[research]\nfamily_id = "ID"\n'),
        (b'[research]  # 6.2\n[data]\nroot = "root"\n',  # an empty table: the key goes under it
         b'[research]  # 6.2\nfamily_id = "ID"\n[data]\nroot = "root"\n'),
        (b'[data]\nroot = "root"\n[research]',
         b'[data]\nroot = "root"\n[research]\nfamily_id = "ID"\n'),
    ],
)  # fmt: skip
def test_init_adds_the_key_to_a_toml_without_it(
    project: Path, capsys: pytest.CaptureFixture[str], before: bytes, after: bytes
) -> None:
    """A project #459's `init` made gets its family; every byte already there stays."""
    (project / TOML).write_bytes(before)
    assert main(["init"]) == 0
    family = family_id(project)
    assert (project / TOML).read_bytes() == after.replace(b"ID", family.encode())
    for again in (["init"], ["init", "--data-root", "root"]):  # the key there: refused (#459)
        assert main(again) == 1
        assert "already exists" in capsys.readouterr().err
    assert (project / TOML).read_bytes() == after.replace(b"ID", family.encode())


@pytest.mark.parametrize(
    ("argv", "toml", "said"),
    [
        (["--new-family", "  "], f'[research]\nfamily_id = "{OLD}"\n', "has no reason"),
        (["--new-family", "x", "--data-root", "root"], f'[research]\nfamily_id = "{OLD}"\n',
         "--data-root with --new-family"),
        (["--new-family", "x"], f'# was "{OLD}"\n[research]\nfamily_id = "{OLD}"\n',
         "not in nexusbt.toml once"),
        ([], "research = {}\n", "not as a table"),
        ([], '[research]\nfamily_id = "my-study"\n', "a UUID4"),
        (["--new-family", "x"], '[research]\nfamily_id = "my-study"\n', "a UUID4"),
        ([], "[data\n", "is not TOML"),
        ([], 'research = "x"\n', "is not a table"),
        (["--new-family", "x"], f'runs = 1\n[research]\nfamily_id = "{OLD}"\n', "is not a table"),
        (["--data-root", "root"], '[data]\nroot = "root"\n', "already exists"),  # as #459
    ],
)  # fmt: skip
def test_refused_without_a_write(
    project: Path, capsys: pytest.CaptureFixture[str], argv: list[str], toml: str, said: str
) -> None:
    (project / TOML).write_text(toml, encoding="utf-8")
    assert main(["init", *argv]) == 1
    assert said in capsys.readouterr().err
    assert (project / TOML).read_text(encoding="utf-8") == toml
    assert sorted(p.name for p in project.iterdir()) == ["nexusbt.toml", "root"]  # no index


def test_init_writes_the_family_when_the_data_root_is_not_there(project: Path) -> None:
    """Only `[research]` is read: a data root on a drive not mounted stops neither command."""
    (project / TOML).write_text('[data]\nroot = "/not/mounted"\n', encoding="utf-8")
    assert main(["init"]) == 0
    assert main(["init", "--new-family", "x"]) == 0


def test_new_family_replaces_the_line_and_records_the_parent(project: Path) -> None:
    """When I run `nexusbt init --new-family "new hypothesis line"`, then the family id changes
    and the old one is recorded as its parent with that reason."""
    before = f'[research] # 6.2\nfamily_id   =  "{OLD}"  # mine\n\n[data]\nroot = "root"\n'
    (project / TOML).write_text(before, encoding="utf-8")
    assert main(["init", "--new-family", "new hypothesis line"]) == 0
    new = family_id(project)
    assert new != OLD
    assert (project / TOML).read_bytes() == before.replace(OLD, new).encode()  # that line only
    with closing(sqlite3.connect(project / "runs" / "index.sqlite")) as db:
        rows = db.execute("SELECT family_id, parent_family_id, reason FROM families").fetchall()
    assert rows == [(new, OLD, "new family: new hypothesis line")]  # 5.9.5's reason form


def test_new_family_without_a_project_or_id_is_refused(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A ConfigError (exit 1) with nothing written: no toml, no index."""
    assert main(["init", "--new-family", "why"]) == 1
    assert "E16" in capsys.readouterr().err
    assert not (project / TOML).exists()
    before = b'[data]\nroot = "root"\n'
    (project / TOML).write_bytes(before)
    assert main(["init", "--new-family", "why"]) == 1  # no id to record as the parent
    assert "[research] family_id" in capsys.readouterr().err
    assert (project / TOML).read_bytes() == before
    assert not (project / "runs").exists()
