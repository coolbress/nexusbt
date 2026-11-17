"""T1.2: `nexusbt init` and `nexusbt doctor` (spec 3.10), on synthetic packages (2.7)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

import nexusbt as nx
from nexusbt.api import _begin_run
from nexusbt.artifacts import Index, RunStore
from nexusbt.cli.main import main
from nexusbt.contracts import PinsPolicy
from nexusbt.data import DataConfig, open_snapshot
from nexusbt.testing.synth import make_snapshot


@pytest.fixture(scope="module")
def snap(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A data root whose `LATEST` names one tiny package (4.2)."""
    return _root(tmp_path_factory.mktemp("root"), "s1")


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("NEXUSBT_DATA_ROOT", raising=False)
    return tmp_path


def test_init_uses_env_root(
    snap: Path, project: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    for command in ("init", "doctor"):  # no root anywhere: how to make a synthetic snapshot
        assert main([command]) == 1
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


def test_undeclared_counts_are_unknown_not_zero(
    tmp_path: Path, project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """TDS 4.3's coverage keys are optional: one the package leaves out is `-`, never 0."""
    package = make_snapshot(tmp_path / "pkg", preset="tiny")
    manifest = json.loads((package / "tds.json").read_text(encoding="utf-8"))
    bars = next(d for d in manifest["datasets"] if d["kind"] == "bars")
    for key in ("instruments", "rows"):
        del bars["coverage"]["by_market"]["KR"][key]
    (package / "tds.json").write_text(json.dumps(manifest), encoding="utf-8")
    out = doctor(package, capsys)
    assert re.search(r"^market KR +rules KR@1 +2020-01-02\.\.2020-03-31 +instruments - +rows -$",
                     out, re.M), out  # fmt: skip


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


def _root(path: Path, snapshot_id: str) -> Path:
    make_snapshot(path / snapshot_id, preset="tiny", snapshot_id=snapshot_id)
    (path / "LATEST").write_text(f"{snapshot_id}\n", encoding="utf-8")
    return path


def _sealed(root: Path, runs: Path, pins: PinsPolicy) -> str:
    """A run begun on `root`'s snapshot as `api` begins one (4.4 step 6), sealed at once."""
    cfg = DataConfig(path=root, pins=pins)
    return _begin_run(RunStore(runs), open_snapshot(cfg), cfg, "backtest", "pin").seal().run_id


def test_pins_not_visible_line(
    tmp_path: Path, project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """R3-17, #465 Decisions: N is the runs holding an unreleased pin whose sealed manifest says
    `retention: unmanaged`, whichever data root `nexusbt.toml` names now."""
    first, second = _root(tmp_path / "a", "s1"), _root(tmp_path / "b", "s2")
    line = "pins not visible to producer: {} runs (root pin not written)"
    assert line.format(0) in doctor(first, capsys)  # no runs/ yet
    runs = project / "runs"  # `[runs] dir`'s default
    _sealed(first, runs, PinsPolicy.INDEX_ROOT)  # its root pin is first's PINS/s1/<run_id>
    _sealed(second, runs, PinsPolicy.INDEX)  # `retention: unmanaged`: the producer cannot see it
    second.chmod(0o555)  # no PINS/ can be made: the root pin fails, E30
    try:
        with pytest.warns(UserWarning, match="root pin not written"):
            _sealed(second, runs, PinsPolicy.INDEX_ROOT)
    finally:
        second.chmod(0o755)
    Index(runs).release("s2", _sealed(second, runs, PinsPolicy.INDEX))  # released: not counted
    Index(runs).pin("s2", "running")  # no sealed manifest: not counted
    (project / "nexusbt.toml").unlink()
    assert line.format(2) in doctor(second, capsys).splitlines()  # nexusbt.toml now names b
