"""T1.1a: `open_snapshot` and `nx.open` (spec 4.1 to 4.4, 4.7), on synthetic packages (2.7)."""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import shutil
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

import nexusbt as nx
from nexusbt.config import load_config
from nexusbt.contracts import (
    AccountingDataError,
    CapabilityError,
    ConfigError,
    DecimalRatioPolicy,
    SnapshotError,
    VerifyPolicy,
)
from nexusbt.data import DataConfig, RatioExclusion, open_snapshot
from nexusbt.testing.synth import make_snapshot
from nexusbt_tds.hash import package_hashes, write_hashes


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
    assert all(part in text for part in ("TDS-M004", hint, "delistings", "snapshot synth-0001"))
    assert not re.search(r" [A-Z][0-9]+ ", text)  # no producer ticket shape (2.7)


def test_unknown_required_rule_E14(tiny: Path, tmp_path: Path) -> None:  # noqa: N802 - the ticket's test name
    newer = shutil.copytree(tiny, tmp_path / "newer")  # 4.1: a newer MINOR is a warning, M011
    edit_manifest(newer, lambda d: dataset(d, "instrument_xref").update(schema_version="1.9"))
    assert open_snapshot(DataConfig(path=newer)).warnings == {"TDS-M011": 1}
    rule = "next_auction_open"  # a 1.x availability rule this engine does not know (4.1)
    edit_manifest(newer, lambda d: dataset(d, "bars_1d").update(availability=rule))
    with pytest.raises(SnapshotError, match="TDS-M014") as raised:
        open_snapshot(DataConfig(path=newer))
    assert rule in str(raised.value)


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
    assert open_snapshot(DataConfig(path=kr_zz, allow_untested=True)).assumptions == s.assumptions


def test_semantic_hash_exposed(tmp_path: Path) -> None:
    small = make_snapshot(tmp_path / "small", preset="small", n_kr=6, n_us=6)
    s = open_snapshot(DataConfig(path=small, verify=VerifyPolicy.FULL))
    hashes = package_hashes(small)
    assert (s.semantic_hash, s.value_hash, s.physical_hash) == (
        hashes["semantic_sha256"], hashes["value_sha256"], hashes["physical_sha256"])  # fmt: skip
    assert (s.id, set(s.markets)) == ("synth-0001", {"KR", "US"})
    edit_manifest(small, lambda d: d["hashes"].pop("value_sha256"))  # partly declared: computed
    assert open_snapshot(DataConfig(path=small)).value_hash == hashes["value_sha256"]
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


def test_nothing_to_open_is_refused(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (root / "LATEST").write_text("../elsewhere\n", encoding="utf-8")
    with pytest.raises(SnapshotError, match="outside the data root"):
        open_snapshot(DataConfig(path=root))
    with pytest.raises(SnapshotError, match="TDS-M001"):  # no tds.json: no hints, no producer
        open_snapshot(DataConfig(path=root / "s1" / "instruments"))
    monkeypatch.delenv("NEXUSBT_DATA_ROOT", raising=False)
    monkeypatch.chdir(root / "s1" / "instruments")
    with pytest.raises(ConfigError, match="no snapshot to open"):  # no [data] path nor root
        DataConfig.from_config(load_config(None))


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


#: Two splits on tiny's first KR and US names, announced 2020-01-02 and effective 2020-01-07.
SPLITS = [{"dataset": "corporate_actions", "instrument_id": i, "kind": "split",
           "ex_date": "2020-01-07", "ratio_new_per_old": 2.0}
          for i in ("KR:T00001", "US:T00001")]  # fmt: skip


@pytest.fixture(scope="module")
def split(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return make_snapshot(tmp_path_factory.mktemp("split") / "snap", preset="tiny", events=SPLITS)


def with_ratios(split: Path, at: Path, **ratios: tuple[int | None, int | None, float]) -> Path:
    """A copy of `split` whose event rows of the instruments named (`KR_T00001=...`) take
    (ratio_num, ratio_den, share_factor), rehashed so that only the rows differ."""
    shutil.copytree(split, at)
    part = at / "corporate_actions" / "part-00000.parquet"
    table = pq.read_table(part)
    rows = table.to_pylist()
    for row in rows:
        if (given := ratios.get(row["instrument_id"].replace(":", "_"))) is not None:
            row.update(zip(("ratio_num", "ratio_den", "share_factor"), given, strict=True))
    pq.write_table(pa.Table.from_pylist(rows, schema=table.schema), part)
    edit_manifest(at, lambda d: dataset(d, "corporate_actions")["files"][0].update(
        bytes=part.stat().st_size))  # fmt: skip
    write_hashes(at)
    return at


def test_malformed_exact_ratio_E13(split: Path, tmp_path: Path) -> None:  # noqa: N802 - the ticket's test name
    """4.4-4: one of ratio_num/ratio_den only, or either <= 0, stops the open with E13 under
    every `decimal_ratio`, at every check level, naming the event (R3-06)."""
    for n, given in enumerate([(2, None, 2.0), (0, 1, 0.0), (-2, -1, 2.0)]):
        bad = with_ratios(split, tmp_path / f"bad{n}", KR_T00001=given)
        for policy in DecimalRatioPolicy:
            with pytest.raises(AccountingDataError, match="KR:E000001") as raised:
                open_snapshot(DataConfig(path=bad, decimal_ratio=policy))
            assert "US:E000001" not in str(raised.value)
        with pytest.raises(AccountingDataError):  # full: A010 is not E14 (4.4-2)
            open_snapshot(DataConfig(path=bad, verify=VerifyPolicy.FULL))
    us_only = with_ratios(split, tmp_path / "us", US_T00001=(2, None, 2.0))
    assert open_snapshot(DataConfig(path=us_only, markets=("KR",))).id == "synth-0001"


def test_missing_exact_ratio_excludes_instrument_from_event(split: Path, tmp_path: Path) -> None:
    """5.6.1 (R7-01): the default `exclude_instrument` opens the snapshot and excludes only
    that instrument, from v(e) = ts_announced on; a ratio off its f64 column by more than
    1e-12 relative is handled the same way (4.4-4, #188); `require_exact` is E13."""
    assert open_snapshot(DataConfig(path=split)).ca_exclusions == ()
    missing = with_ratios(split, tmp_path / "missing", KR_T00001=(None, None, 2.0))
    s = open_snapshot(DataConfig(path=missing))
    kr = RatioExclusion("KR:T00001", "KR:E000001", "ca_ratio_missing",
                        dt.datetime(2020, 1, 2, 6, 30, tzinfo=dt.UTC))  # fmt: skip
    assert (s.id, s.ca_exclusions) == ("synth-0001", (kr,))
    off = with_ratios(split, tmp_path / "off", US_T00001=(2, 1, 2.0 * (1 + 1e-9)))
    us = open_snapshot(DataConfig(path=off, verify=VerifyPolicy.FULL)).ca_exclusions
    assert [(e.instrument_id, e.cause) for e in us] == [("US:T00001", "ca_ratio_disagrees")]
    near = with_ratios(split, tmp_path / "near", US_T00001=(2, 1, 2.0 * (1 + 1e-13)))
    assert open_snapshot(DataConfig(path=near)).ca_exclusions == ()
    assert open_snapshot(DataConfig(path=missing, markets=("US",))).ca_exclusions == ()
    with pytest.raises(AccountingDataError, match="KR:E000001"):
        open_snapshot(DataConfig(path=missing, decimal_ratio=DecimalRatioPolicy.REQUIRE_EXACT))
    literal = open_snapshot(DataConfig(path=missing, decimal_ratio=DecimalRatioPolicy.LITERAL))
    assert literal.ca_exclusions == ()
    assert literal.assumptions == ("decimal ratios used literally: 1 events",)
