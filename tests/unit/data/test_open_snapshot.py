"""T1.1a: `open_snapshot` and `nx.open` (spec 4.1 to 4.4, 4.7), on synthetic packages (2.7)."""

from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path
from typing import Any

import pytest

import nexusbt as nx
from nexusbt.config import load_config
from nexusbt.contracts import CapabilityError, SnapshotError, VerifyPolicy
from nexusbt.data import DataConfig, open_snapshot
from nexusbt.testing.synth import make_snapshot
from nexusbt_tds.hash import package_hashes


def edit_manifest(root: Path, change: Any) -> None:
    """Rewrite `root/tds.json` through `change(data)`; the declared hashes are left as they are."""
    data = json.loads((root / "tds.json").read_text(encoding="utf-8"))
    change(data)
    (root / "tds.json").write_text(json.dumps(data), encoding="utf-8")


def dataset(data: dict[str, Any], name: str) -> dict[str, Any]:
    return next(d for d in data["datasets"] if d["name"] == name)


@pytest.fixture(scope="module")
def tiny(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return make_snapshot(tmp_path_factory.mktemp("tiny") / "snap", preset="tiny")


@pytest.fixture
def root(tmp_path: Path) -> Path:
    """A data root of two snapshots with `LATEST` naming the first (4.2)."""
    for name, seed in (("s1", 0), ("s2", 1)):
        make_snapshot(tmp_path / name, preset="tiny", seed=seed, snapshot_id=name)
    (tmp_path / "LATEST").write_text("s1\n", encoding="utf-8")
    return tmp_path


def test_latest_resolved_once(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    reads: list[Path] = []
    read_text = Path.read_text

    def counted(self: Path, *args: Any, **kwargs: Any) -> str:
        if self.name == "LATEST":
            reads.append(self)
        return read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", counted)
    s = open_snapshot(DataConfig(path=root))
    assert (s.id, len(reads)) == ("s1", 1)
    (root / "LATEST").write_text("s2\n", encoding="utf-8")  # the writer swaps it after the open
    assert s.id == "s1"  # the opened snapshot keeps what the one read gave
    assert open_snapshot(DataConfig(path=root)).id == "s2"


def test_E14_carries_tds_code_and_hint_not_ticket(tiny: Path, tmp_path: Path) -> None:  # noqa: N802 - the ticket's test name
    broken = shutil.copytree(tiny, tmp_path / "broken")
    hint = "rebuild the package from the producer's last good build"
    (broken / "delistings" / "part-00000.parquet").unlink()  # TDS-M004: a listed file is missing
    edit_manifest(broken, lambda d: d["producer"]["hints"].update({"TDS-M004": hint}))
    with pytest.raises(SnapshotError) as raised:
        open_snapshot(DataConfig(path=broken))
    text = str(raised.value)
    assert all(part in text for part in ("TDS-M004", hint, "delistings"))
    assert not re.search(r" [A-Z][0-9]+ ", text)  # no producer ticket shape (2.7)


def test_unknown_required_rule_E14(tiny: Path, tmp_path: Path) -> None:  # noqa: N802 - the ticket's test name
    newer = shutil.copytree(tiny, tmp_path / "newer")
    rule = "next_auction_open"  # a 1.x availability rule this engine does not know (4.1)
    edit_manifest(newer, lambda d: dataset(d, "bars_1d").update(availability=rule))
    with pytest.raises(SnapshotError, match="TDS-M014") as raised:
        open_snapshot(DataConfig(path=newer))
    assert rule in str(raised.value)


def test_newer_minor_version_warns_m011(tiny: Path, tmp_path: Path) -> None:
    newer = shutil.copytree(tiny, tmp_path / "newer")
    edit_manifest(newer, lambda d: dataset(d, "instrument_xref").update(schema_version="1.9"))
    assert open_snapshot(DataConfig(path=newer)).warnings == {"TDS-M011": 1}


@pytest.fixture(scope="module")
def kr_zz(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("kr_zz") / "snap"
    return make_snapshot(path, preset="tiny", markets=("KR", "ZZ"))


def test_market_without_pack_E18(kr_zz: Path) -> None:  # noqa: N802 - the ticket's test name
    s = open_snapshot(DataConfig(path=kr_zz))  # opening needs no market: KR still runs
    assert (s.markets["KR"].rules, s.markets["ZZ"].rules) == ("KR@1", None)
    assert open_snapshot(DataConfig(path=kr_zz, markets=("KR",))).id == s.id
    with pytest.raises(CapabilityError, match="no market rules pack for ZZ; supported: KR, US"):
        open_snapshot(DataConfig(path=kr_zz, markets=("KR", "ZZ")))
    with pytest.raises(CapabilityError, match="market XX is not in the snapshot"):
        open_snapshot(DataConfig(path=kr_zz, markets=("XX",)))


def test_allow_untested_recorded(kr_zz: Path) -> None:
    cfg = DataConfig(path=kr_zz, markets=("KR", "ZZ"), allow_untested=True)
    s = open_snapshot(cfg)
    assert (s.markets["KR"].rules, s.markets["ZZ"].rules) == ("KR@1", "_generic@1")
    assert s.assumptions == ("untested market rules: ZZ",)


def test_semantic_hash_exposed(tmp_path: Path) -> None:
    small = make_snapshot(tmp_path / "small", preset="small", n_kr=6, n_us=6)
    s = open_snapshot(DataConfig(path=small, verify=VerifyPolicy.FULL))
    hashes = package_hashes(small)
    assert (s.semantic_hash, s.value_hash, s.physical_hash) == (
        hashes["semantic_sha256"], hashes["value_sha256"], hashes["physical_sha256"])  # fmt: skip
    assert (s.id, set(s.markets)) == ("synth-0001", {"KR", "US"})
    us = s.markets["US"]
    assert (us.calendar_id, us.currency, us.timezone, us.rules) == (
        "XNYS", "USD", "America/New_York", "US@1")  # fmt: skip


def test_open_path_and_latest_parent(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert nx.open(root / "s2").id == "s2"  # the package folder
    assert nx.open(str(root)).id == "s1"  # a parent folder: through LATEST
    monkeypatch.chdir(root)
    for toml, expected in ((f"path = '{root / 's2'}'", "s2"), (f"path = '{root}'", "s1"),
                           (f"root = '{root}'\nsnapshot = 's2'", "s2")):  # fmt: skip
        Path("nexusbt.toml").write_text(f"[data]\n{toml}\n", encoding="utf-8")
        cfg = DataConfig.from_config(load_config(Path("nexusbt.toml")))
        assert open_snapshot(cfg).id == expected


def test_cloned_and_hardlinked_partitions_ok(tiny: Path, tmp_path: Path) -> None:
    """A producer's next build: unchanged partitions hard-linked or cloned (4.2); read-only."""
    for name, place in (("linked", os.link), ("cloned", shutil.copy2)):
        shutil.copytree(tiny, tmp_path / name, copy_function=place)
        os.unlink(tmp_path / name / "tds.json")  # the manifest is written anew, not shared
        shutil.copy2(tiny / "tds.json", tmp_path / name / "tds.json")
    part = Path("instruments/part-00000.parquet")
    assert os.stat(tmp_path / "linked" / part).st_ino == os.stat(tiny / part).st_ino
    folders = [tmp_path / "linked", tmp_path / "cloned"]
    for folder in folders:
        for path in sorted(folder.rglob("*"), reverse=True):  # the engine needs no write access
            path.chmod(0o555 if path.is_dir() else 0o444)
        folder.chmod(0o555)
    try:
        opened = [open_snapshot(DataConfig(path=f, verify=VerifyPolicy.FULL)) for f in folders]
        original = open_snapshot(DataConfig(path=tiny, verify=VerifyPolicy.FULL))
        assert {s.physical_hash for s in opened} == {original.physical_hash}
    finally:
        for path in [*folders, *(p for f in folders for p in f.rglob("*"))]:
            path.chmod(0o755 if path.is_dir() else 0o644)
