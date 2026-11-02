"""Spec 6.6 E46: an engine bug exits 2 and points at `nexusbt bugreport RUN_ID`, whose bundle
is `./bugreport-<id>.zip` (#52 Decisions, 2026-11-02)."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

import nexusbt as nx
import nexusbt.cli.main as cli


def test_bugreport_demo_prints_the_bundle_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    assert cli.main(["bugreport", "demo"]) == 0
    path = Path(capsys.readouterr().out.strip())
    assert path == tmp_path / "bugreport-demo.zip"
    with zipfile.ZipFile(path) as bundle:
        assert sorted(bundle.namelist()) == ["command.txt", "manifest.json", "versions.json"]
        assert "nexusbt" in bundle.read("command.txt").decode()
        assert json.loads(bundle.read("manifest.json"))["run_id"] == "demo"
        versions = json.loads(bundle.read("versions.json"))
    assert set(versions) == {"nexusbt", "nexusbt-tds", "python"}
    assert versions["nexusbt"]


def test_bugreport_of_a_saved_run_is_not_built_yet() -> None:
    with pytest.raises(NotImplementedError, match=r"T1\.14a"):
        cli.main(["bugreport", "r1"])


@pytest.mark.parametrize("command", [["bugreport", "demo"], ["backtest"]])
def test_engine_bug_exits_2(
    command: list[str], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def bug(*_: object) -> int:
        raise nx.EngineBugError.example()

    monkeypatch.setattr(cli, "_bundle", bug)
    monkeypatch.setattr(cli, "_run", bug)  # any command (6.6 E46)
    assert cli.main(command) == 2
    assert "engine bug — please report: nexusbt bugreport r1" in capsys.readouterr().err
