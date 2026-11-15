"""T1.2: `nexusbt init` and `nexusbt doctor` (spec 3.10), on synthetic packages (2.7)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import nexusbt as nx
from nexusbt.artifacts import Index
from nexusbt.cli.main import main
from nexusbt.testing.synth import make_snapshot


@pytest.fixture(scope="module")
def snap(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A data root whose `LATEST` names one tiny package (4.2)."""
    root = tmp_path_factory.mktemp("root")
    make_snapshot(root / "s1", preset="tiny", snapshot_id="s1")
    (root / "LATEST").write_text("s1\n", encoding="utf-8")
    return root


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("NEXUSBT_DATA_ROOT", raising=False)
    return tmp_path


def test_init_uses_env_root(
    snap: Path, project: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["init"]) == 1  # no root anywhere: how to make a synthetic snapshot, no file
    assert "python -m nexusbt.testing.synth" in capsys.readouterr().err
    assert not (project / "nexusbt.toml").exists()
    monkeypatch.setenv("NEXUSBT_DATA_ROOT", str(snap))
    assert main(["init"]) == 0
    assert f'root = "{snap}"' in (project / "nexusbt.toml").read_text(encoding="utf-8")
    assert main(["init"]) == 1  # an existing nexusbt.toml is kept
    assert "already exists" in capsys.readouterr().err


def doctor(root: Path, capsys: pytest.CaptureFixture[str]) -> str:
    assert main(["init", "--data-root", str(root)]) == 0
    capsys.readouterr()
    assert main(["doctor"]) == 0
    return capsys.readouterr().out


def test_doctor_lists_markets_packs_and_counts(
    snap: Path, project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = doctor(snap, capsys)
    assert re.search(r"^snapshot +s1$", out, re.M)
    assert re.search(rf"^semantic +{nx.open(snap).semantic_hash}$", out, re.M)
    assert re.search(r"^edition +strict$", out, re.M)  # the 3.11 default
    for m in ("KR", "US"):  # the tiny preset: 6 instruments, 341 daily rows per market
        line = rf"^market {m} +rules {m}@1 +2020-01-02\.\.2020-03-31 +instruments 6 +rows 341$"
        assert re.search(line, out, re.M), out
    assert re.search(r"^columns +12 daily bar columns$", out, re.M)  # tiny's bars file has 12
    assert re.search(r"^free disk +\d+\.\d GB$", out, re.M)


def test_doctor_lists_fallbacks_and_unchecked(
    tmp_path: Path, project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """INV-12: what a run would fill and what the check level did not judge, both shown."""
    package = make_snapshot(tmp_path / "pkg", preset="tiny", degrade=["no_sessions"])
    with pytest.warns(UserWarning, match=r"\[E30\] F-02"):  # the line `open` also gives
        out = doctor(package, capsys)
    for m in ("KR", "US"):  # tiny's 62 sessions per market, synthesized (F-02)
        assert re.search(rf"^fallback +F-02 calendar_sessions {m} 62$", out, re.M), out
    assert re.search(r"^unchecked +.*\bTDS-K001\b", out, re.M)  # a row rule, at `manifest`
    profile = r"tds:minimal-daily@1\.0 +declared yes +checked manifest +result not_checked"
    assert re.search(rf"^profile +{profile} +supported yes$", out, re.M), out


def test_publishing_marker(
    tmp_path: Path, project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Mid-publication: `LATEST` already names a snapshot not yet there; only the one line."""
    root = tmp_path / "root"
    make_snapshot(root / "s1", preset="tiny", snapshot_id="s1")
    (root / "LATEST").write_text("s1\n", encoding="utf-8")
    assert main(["init", "--data-root", str(root)]) == 0
    (root / "LATEST").write_text("s2\n", encoding="utf-8")
    (root / ".publishing").touch()
    capsys.readouterr()
    assert main(["doctor"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("publishing in progress")
    assert "wait for the new snapshot" in out
    assert len(out.splitlines()) == 1


def test_pins_not_visible_line(
    tmp_path: Path, project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """R3-17: a run pinned in the index only, its root pin unwritten, is the one counted."""
    root = tmp_path / "root"
    make_snapshot(root / "s1", preset="tiny", snapshot_id="s1")
    (root / "LATEST").write_text("s1\n", encoding="utf-8")
    assert "pins not visible to producer: 0 runs" in doctor(root, capsys)  # no runs/ yet
    index = Index(project / "runs")  # `[runs] dir`'s default
    for run in ("seen", "unseen", "released"):
        index.pin("s1", run)
    (root / "PINS" / "s1").mkdir(parents=True)
    (root / "PINS" / "s1" / "seen").touch()  # the root pin `_begin_run` writes when it can
    index.release("s1", "released")
    assert main(["doctor"]) == 0
    assert "pins not visible to producer: 1 runs" in capsys.readouterr().out.splitlines()
