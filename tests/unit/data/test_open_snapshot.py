"""T1.1a: `open_snapshot` and `nx.open` (spec 4.1 to 4.4, 4.7), on synthetic packages (2.7)."""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import shutil
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

import nexusbt as nx
from nexusbt.api import _begin_run
from nexusbt.artifacts import Index, RunStore
from nexusbt.config import load_config
from nexusbt.contracts import (
    AccountingDataError,
    CapabilityError,
    ConfigError,
    DecimalRatioPolicy,
    FallbacksPolicy,
    PinsPolicy,
    SnapshotError,
    VerifyPolicy,
)
from nexusbt.data import (
    CapabilityRequest,
    DataConfig,
    FallbackRecord,
    RatioExclusion,
    open_snapshot,
)
from nexusbt.testing.synth import make_snapshot
from nexusbt_tds import ProfileStatus
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
    with pytest.warns(UserWarning, match="F-15"):  # the generic pack has no grid (4.5)
        s = open_snapshot(cfg)
    assert (s.markets["KR"].rules, s.markets["ZZ"].rules) == ("KR@1", "_generic@1")
    assert s.assumptions == ("untested market rules: ZZ",)
    with pytest.warns(UserWarning, match="F-15"):
        again = open_snapshot(DataConfig(path=kr_zz, allow_untested=True))
    assert again.assumptions == s.assumptions


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


def test_edited_markets_change_the_semantic_hash_at_open(tiny: Path, tmp_path: Path) -> None:
    """ADR 0042: below `full` the semantic hash is recomputed from tds.json and the declared
    dataset value hashes; the value and physical hashes stay as declared (#329)."""
    edited = shutil.copytree(tiny, tmp_path / "edited")
    declared = json.loads((tiny / "tds.json").read_text(encoding="utf-8"))["hashes"]
    edit_manifest(edited, lambda d: d["markets"]["KR"].update(timezone="Asia/Tokyo"))
    s = open_snapshot(DataConfig(path=edited))
    assert s.semantic_hash != declared["semantic_sha256"]
    assert s.semantic_hash == package_hashes(edited)["semantic_sha256"]  # as the full read gives
    assert (s.value_hash, s.physical_hash) == (
        declared["value_sha256"], declared["physical_sha256"])  # fmt: skip
    assert open_snapshot(DataConfig(path=tiny)).semantic_hash == declared["semantic_sha256"]
    edit_manifest(edited, lambda d: dataset(d, "bars_1d").pop("value_sha256"))  # none: computed
    assert open_snapshot(DataConfig(path=edited)).semantic_hash == s.semantic_hash


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


Rows = list[dict[str, Any]]


def with_rows(split: Path, at: Path, change: Callable[[Rows], Rows]) -> Path:
    """A copy of `split` whose `corporate_actions` rows are `change(rows)`, rehashed so that
    only the rows differ."""
    shutil.copytree(split, at)
    part = at / "corporate_actions" / "part-00000.parquet"
    table = pq.read_table(part)
    pq.write_table(pa.Table.from_pylist(change(table.to_pylist()), schema=table.schema), part)
    edit_manifest(at, lambda d: dataset(d, "corporate_actions")["files"][0].update(
        bytes=part.stat().st_size))  # fmt: skip
    write_hashes(at)
    return at


def with_ratios(split: Path, at: Path, **ratios: tuple[int | None, int | None, float]) -> Path:
    """A copy of `split` whose event rows of the instruments named (`KR_T00001=...`) take
    (ratio_num, ratio_den, share_factor)."""

    def change(rows: Rows) -> Rows:
        for row in rows:
            if (given := ratios.get(row["instrument_id"].replace(":", "_"))) is not None:
                row.update(zip(("ratio_num", "ratio_den", "share_factor"), given, strict=True))
        return rows

    return with_rows(split, at, change)


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


CORE, MINIMAL = "tds:equity-daily-core@1.0", "tds:minimal-daily@1.0"


def test_three_status_distinct(tiny: Path, tmp_path: Path) -> None:
    """4.3: declared, checked (to a level; not passed) and supported are three results."""
    s = open_snapshot(DataConfig(path=tiny))
    assert s.profiles[CORE] == ProfileStatus(True, "manifest", "not_checked")
    schema = open_snapshot(DataConfig(path=tiny, verify=VerifyPolicy.SCHEMA))
    assert schema.profiles[CORE].verified_level == "schema"
    more = shutil.copytree(tiny, tmp_path / "more")
    edit_manifest(more, lambda d: d["profiles"].append("tds:bitemporal@1.0"))
    s = open_snapshot(DataConfig(path=more))  # declared and checked, not read by v1 (4.3)
    assert s.profiles["tds:bitemporal@1.0"] == ProfileStatus(True, "manifest", "not_checked")
    assert s.capabilities.supported == {CORE, MINIMAL}


def test_price_only_graph_needs_core_only(tiny: Path, tmp_path: Path) -> None:
    """4.3: `Price` alone needs instruments and bars; a richer feature is E18 on such a package."""
    assert CapabilityRequest().datasets == {"instruments", "bars"}
    bare = shutil.copytree(tiny, tmp_path / "bare")
    kept = {"instruments", "bars"}
    for d in json.loads((bare / "tds.json").read_text(encoding="utf-8"))["datasets"]:
        if d["kind"] not in kept:
            shutil.rmtree(bare / d["path"])
    edit_manifest(bare, lambda d: d.update(
        profiles=[MINIMAL], datasets=[x for x in d["datasets"] if x["kind"] in kept]))  # fmt: skip
    s = open_snapshot(DataConfig(path=bare), required=CapabilityRequest())
    assert (s.capabilities.features, s.fallbacks) == (frozenset({"price", "grid"}), [])
    with pytest.raises(CapabilityError, match="backtest needs corporate_actions,"):  # F-02 too
        open_snapshot(DataConfig(path=bare), required=CapabilityRequest(frozenset({"backtest"})))
    with pytest.raises(ValueError, match="no feature"):
        CapabilityRequest(frozenset({"Price"}))


def test_declared_but_broken_is_E14_not_fallback(tiny: Path, tmp_path: Path) -> None:  # noqa: N802 - the ticket's test name
    """4.4-3: a package that declares the core profile without calendar_sessions is not given
    F-02: the checker's error is E14 (INV-17)."""
    broken = shutil.copytree(tiny, tmp_path / "broken")
    shutil.rmtree(broken / "calendar_sessions")
    edit_manifest(broken, lambda d: d.update(
        datasets=[x for x in d["datasets"] if x["kind"] != "calendar_sessions"]))  # fmt: skip
    with pytest.raises(SnapshotError, match="TDS-M008") as raised:
        open_snapshot(DataConfig(path=broken), required=CapabilityRequest(frozenset({"backtest"})))
    assert "F-02" not in str(raised.value)


BACKTEST = CapabilityRequest(frozenset({"backtest"}))


def opened_warned(path: Path, **cfg: Any) -> tuple[Any, list[str]]:
    """The snapshot opened at `path`, and the text of each E30 warning the open gave."""
    with pytest.warns(UserWarning, match=r"DataProfileWarning \[E30\]") as said:
        s = open_snapshot(DataConfig(path=path, **cfg), required=BACKTEST)
    return s, [str(w.message) for w in said]


def test_fallback_F02_sessions(tmp_path: Path) -> None:  # noqa: N802 - the ticket's test name
    """F-02: one E30 line, one record per market (XKRX and XNYS sessions of the bars' period),
    and the manifest assumption; a calendar exchange_calendars does not know is E18."""
    s, said = opened_warned(make_snapshot(tmp_path / "a", preset="tiny", degrade=["no_sessions"]))
    assert len(said) == 1
    assert "DataProfileWarning [E30] F-02" in said[0]
    assert s.fallbacks == [FallbackRecord("F-02", "calendar_sessions", "KR", 62),  # tiny's own
                           FallbackRecord("F-02", "calendar_sessions", "US", 62)]  # fmt: skip
    assert s.assumptions == ("sessions synthesized from exchange_calendars 4.13.2",)
    old = s.fallbacks  # bars from 2001: before exchange_calendars' default 20 years back
    edit_manifest(tmp_path / "a", lambda d: dataset(d, "bars_1d")["coverage"]["by_market"][
        "US"].update(first="2001-01-02", last="2001-01-31"))  # fmt: skip
    assert opened_warned(tmp_path / "a")[0].fallbacks == [old[0], replace(old[1], count=21)]
    zz =make_snapshot(tmp_path / "zz", preset="tiny", markets=("KR", "ZZ"),
                       degrade=["no_sessions"])  # fmt: skip
    with pytest.raises(CapabilityError, match="backtest needs calendar_sessions"):
        open_snapshot(DataConfig(path=zz, allow_untested=True), required=BACKTEST)


def test_fallback_F03_densify(tmp_path: Path) -> None:  # noqa: N802 - the ticket's test name
    """F-03: sparse bars without obs_status are recorded for a backtest, not for `Price` alone."""
    sparse = make_snapshot(tmp_path / "s", preset="tiny", degrade=["sparse_bars"])
    s, said = opened_warned(sparse)
    assert [(r.id, r.market) for r in s.fallbacks] == [("F-03", "KR"), ("F-03", "US")]
    assert {(r.dataset, r.count) for r in s.fallbacks} == {("bars_1d", 341)}  # tiny: all traded
    assert "listing period x sessions" in said[0]
    assert open_snapshot(DataConfig(path=sparse), required=CapabilityRequest()).fallbacks == []


def test_fallback_F04_factors_from_resolver(tiny: Path, tmp_path: Path) -> None:  # noqa: N802 - the ticket's test name
    """F-04 is a definition: no cumulative factor columns, the resolver's factors, no warning."""
    assert open_snapshot(DataConfig(path=tiny), required=BACKTEST).capabilities.cum_factors == (
        "columns")  # fmt: skip
    bare = make_snapshot(tmp_path / "f", preset="tiny", degrade=["no_cum_factors"])
    s = open_snapshot(DataConfig(path=bare), required=BACKTEST)  # filterwarnings: no warning
    assert (s.capabilities.cum_factors, s.fallbacks) == ("resolver", [])
    assert "backtest" in s.capabilities.features


def test_fallbacks_fail_mode_raises_E14(tmp_path: Path) -> None:  # noqa: N802 - the ticket's test name
    """4.4-3: `[data] fallbacks = "fail"` makes a needed fallback E14, without a warning."""
    gap = make_snapshot(tmp_path / "g", preset="tiny", degrade=["no_sessions"])
    with pytest.raises(SnapshotError, match="fallback F-02 needed") as raised:
        open_snapshot(DataConfig(path=gap, fallbacks=FallbacksPolicy.FAIL), required=BACKTEST)
    assert "[E14]" in str(raised.value)
    price = CapabilityRequest()  # `Price` alone needs no session table: nothing to refuse
    assert open_snapshot(DataConfig(path=gap, fallbacks=FallbacksPolicy.FAIL), required=price)


def test_volume_unit_warning_lifted_E30(tmp_path: Path) -> None:  # noqa: N802 - the ticket's test name
    """F-16 (V31-16): the checker's TDS-V011 warnings become one E30 line and a record of the
    KR instrument-years whose volume unit is unverified; no repair."""
    lots = make_snapshot(tmp_path / "v", preset="small", n_kr=6, n_us=6, degrade=["volume_in_lots"])
    s, said = opened_warned(lots, verify=VerifyPolicy.FULL)
    assert s.fallbacks == [FallbackRecord("F-16", "bars_1d", "KR", 16)]
    assert s.warnings["TDS-V011"] == 16
    assert len(said) == 1
    assert "volume unit unverified" in said[0]


def test_fallback_F15_grid_minor_unit(tmp_path: Path) -> None:  # noqa: N802 - the ticket's test name
    """F-15 (V31-05): no grid anywhere for ZZ (generic pack, no tick column, no market_rules):
    the currency minor unit, E30; KR keeps its pack's tick table."""
    path = make_snapshot(tmp_path / "t", preset="tiny", markets=("KR", "ZZ"),
                         degrade=["no_tick_info"])  # fmt: skip
    grid = CapabilityRequest(frozenset({"grid"}))
    with pytest.warns(UserWarning, match="price grid = currency minor unit for ZZ"):
        s = open_snapshot(DataConfig(path=path, allow_untested=True), required=grid)
    assert s.fallbacks == [FallbackRecord("F-15", "market_rules", "ZZ", 6)]
    assert open_snapshot(DataConfig(path=path), required=grid).fallbacks == []  # ZZ: no pack


NO_RATIO = {"ratio_num": None, "ratio_den": None}


def kr(**columns: Any) -> Callable[[Rows], Rows]:
    """Set `columns` on KR:T00001's event row."""
    return lambda rows: [r | columns if r["instrument_id"] == "KR:T00001" else r for r in rows]


def excluded(root: Path, **config: Any) -> list[tuple[str, str]]:
    return [(e.event_id, e.cause)
            for e in open_snapshot(DataConfig(path=root, **config)).ca_exclusions]  # fmt: skip


def test_paid_capital_reduction_without_ratio_not_excluded(split: Path, tmp_path: Path) -> None:
    """#446 (a): a `capital_reduction` or `rights_issue` needs an exact ratio only with a
    `ratio_new_per_old`, as A010 reads TDS 5.11, whatever its `share_factor`."""
    paid = kr(kind="capital_reduction", share_factor=1.0, cash_per_share=100.0,
              ratio_new_per_old=None, **NO_RATIO)  # fmt: skip
    assert excluded(with_rows(split, tmp_path / "paid", paid)) == []
    rights = kr(kind="rights_issue", share_factor=None, ratio_new_per_old=None, **NO_RATIO)
    assert excluded(with_rows(split, tmp_path / "rights", rights)) == []
    merged = kr(kind="capital_reduction", share_factor=None, ratio_new_per_old=0.5, **NO_RATIO)
    found = excluded(with_rows(split, tmp_path / "merged", merged))
    assert found == [("KR:E000001", "ca_ratio_missing")]


def test_literal_without_decimal_is_e13(split: Path, tmp_path: Path) -> None:
    """#446 (b): under `literal`, a share event with no exact ratio and no f64 to read is E13
    at open naming it, not an event read literally; the default still excludes it."""
    empty = kr(share_factor=None, ratio_new_per_old=None, **NO_RATIO)
    both = with_rows(split, tmp_path / "both", lambda rows: [
        r | NO_RATIO for r in empty(rows)])  # fmt: skip
    with pytest.raises(AccountingDataError, match="KR:E000001") as raised:
        open_snapshot(DataConfig(path=both, decimal_ratio=DecimalRatioPolicy.LITERAL))
    assert "US:E000001" not in str(raised.value)  # its share_factor can be read
    assert "exclude_instrument" in str(raised.value)
    assert excluded(both) == [("KR:E000001", "ca_ratio_missing"),
                              ("US:E000001", "ca_ratio_missing")]  # fmt: skip


def test_visible_time_falls_back(split: Path, tmp_path: Path) -> None:
    """5.6.1 (1): v(e) is `ts_announced`, else `ts_terms_available`, else `ts_effective`."""
    terms, effective = (dt.datetime(2020, 1, d, 0, 0, tzinfo=dt.UTC) for d in (3, 7))
    cases: list[tuple[str, dt.datetime, dict[str, Any]]] = [
        ("terms", terms, {"ts_terms_available": terms}),
        ("effective", effective, {"ts_terms_available": None, "ts_effective": effective}),
    ]
    for name, shown, columns in cases:
        root = with_rows(split, tmp_path / name, kr(ts_announced=None, **columns, **NO_RATIO))
        assert [e.visible for e in open_snapshot(DataConfig(path=root)).ca_exclusions] == [shown]


def test_revised_and_cancelled_events_are_not_checked(split: Path, tmp_path: Path) -> None:
    """Only an event's latest version that is not cancelled is checked: a version without a
    ratio that a later one revises excludes nothing, nor does a cancelled one."""

    def revised(by: dict[str, Any]) -> Callable[[Rows], Rows]:
        return lambda rows: [*kr(**NO_RATIO)(rows), rows[0] | {
            "event_id": "KR:E000009", "revision_of": "KR:E000001"} | by]  # fmt: skip

    assert excluded(with_rows(split, tmp_path / "fixed", revised({}))) == []
    broken = excluded(with_rows(split, tmp_path / "broken", revised(NO_RATIO)))
    assert broken == [("KR:E000009", "ca_ratio_missing")]
    cancelled = kr(status="cancelled", **NO_RATIO)
    assert excluded(with_rows(split, tmp_path / "cancelled", cancelled)) == []


@pytest.mark.parametrize(("kind", "ratio", "f64"), [
    ("bonus_issue", (3, 2), 0.5), ("stock_dividend", (11, 10), 0.1), ("stock_merger", (1, 2), 0.5),
])  # fmt: skip
def test_ratio_compared_with_its_f64_column(
    split: Path, tmp_path: Path, kind: str, ratio: tuple[int, int], f64: float
) -> None:
    """A010's f64 column for kinds other than a split with a `share_factor`: 1 +
    `ratio_new_per_old` for a bonus issue or stock dividend, `ratio_new_per_old` for the rest."""
    for name, given in (("agrees", f64), ("disagrees", f64 * 1.01)):
        row = kr(kind=kind, ratio_num=ratio[0], ratio_den=ratio[1], share_factor=None,
                 ratio_new_per_old=given)  # fmt: skip
        found = excluded(with_rows(split, tmp_path / name, row))
        assert found == ([] if name == "agrees" else [("KR:E000001", "ca_ratio_disagrees")])


BARS = Path("bars/freq=1d/market=KR/year=2020/part-00000.parquet")  # one of tiny's files


def flip_byte(path: Path) -> None:
    """Change one byte of a page in place: the same inode and size, a later mtime."""
    with open(path, "r+b") as f:
        f.seek(100)
        byte = f.read(1)[0]
        f.seek(100)
        f.write(bytes([byte ^ 0xFF]))


def stamped(path: Path, stamps: Path | None) -> Any:
    """An open that needs each file's sha256 (`rerun`, `reconcile`, `live`, `fill`; 4.4-1)."""
    return open_snapshot(DataConfig(path=path, stamps=stamps), sha256=True)


def test_full_verify_detects_tamper(tiny: Path, tmp_path: Path) -> None:
    """One changed byte: `manifest` reads sizes, not bytes; `full` gives E14 TDS-H001."""
    copy = shutil.copytree(tiny, tmp_path / "t")
    flip_byte(copy / BARS)
    open_snapshot(DataConfig(path=copy))
    with pytest.raises(SnapshotError, match="TDS-H001"):
        open_snapshot(DataConfig(path=copy, verify=VerifyPolicy.FULL))


def test_verified_stamp_detects_later_tamper(tiny: Path, tmp_path: Path) -> None:
    """The first open hashes every file and stamps their identities, as relative paths (2.7).
    A byte changed with the identity kept passes: the cost ADR-0037 names, which an open without
    the stamp sees. A file replaced later has a new inode, so it is hashed again: E14, and the
    stamp is discarded."""
    copy, stamps = shutil.copytree(tiny, tmp_path / "t"), tmp_path / "runs/.cache/verified"
    stamp = stamps / stamped(copy, stamps).physical_hash
    held = json.loads(stamp.read_text(encoding="utf-8"))["files"]
    assert str(BARS) in held
    assert not any(Path(p).is_absolute() for p in held)
    stamp.write_text('{"files": []}', encoding="utf-8")  # a stamp of another shape: hash all
    stamped(copy, stamps)
    assert json.loads(stamp.read_text(encoding="utf-8"))["files"] == held
    kept = os.stat(copy / BARS)
    flip_byte(copy / BARS)
    os.utime(copy / BARS, ns=(kept.st_atime_ns, kept.st_mtime_ns))
    stamped(copy, stamps)
    with pytest.raises(SnapshotError, match="TDS-H001"):
        stamped(copy, None)
    shutil.copy2(copy / BARS, tmp_path / "bars.parquet")
    os.replace(tmp_path / "bars.parquet", copy / BARS)  # same bytes and mtime, a new inode
    with pytest.raises(SnapshotError, match="TDS-H001") as raised:
        stamped(copy, stamps)
    assert str(BARS) in str(raised.value)
    assert not stamp.exists()


def test_inplace_edit_invalidates_stamp_and_l0(tiny: Path, tmp_path: Path) -> None:
    """An edit in place after the stamp keeps the inode and size but not the mtime, so the next
    open sees another identity, hashes the file again and gives E14; the stamp is discarded.
    The L0 half comes with the L0 cache (T6.12)."""
    copy, stamps = shutil.copytree(tiny, tmp_path / "t"), tmp_path / "runs/.cache/verified"
    stamp = stamps / stamped(copy, stamps).physical_hash
    before = os.stat(copy / BARS)
    flip_byte(copy / BARS)
    after = os.stat(copy / BARS)
    assert (after.st_ino, after.st_size) == (before.st_ino, before.st_size)
    assert after.st_mtime_ns != before.st_mtime_ns
    with pytest.raises(SnapshotError, match="TDS-H001"):
        stamped(copy, stamps)
    assert not stamp.exists()


def test_readonly_package_all_consumption_paths(tiny: Path, tmp_path: Path) -> None:
    """A read-only data root opens on every path: the package or its root's `LATEST`, at each
    verify level, and with file sha256s, whose stamp goes under the runs folder and is read by
    the next open, or is skipped where it cannot be written; nothing in the root changes."""
    data, stamps = tmp_path / "data", tmp_path / "runs/.cache/verified"
    shutil.copytree(tiny, data / "s1")
    (data / "LATEST").write_text("s1\n", encoding="utf-8")
    paths = sorted(data.rglob("*"), reverse=True)
    before = [(p, p.stat().st_size, p.stat().st_mtime_ns) for p in paths]
    for path in [*paths, data]:
        path.chmod(0o555 if path.is_dir() else 0o444)
    try:
        for level in VerifyPolicy:
            for path in (data, data / "s1"):
                assert open_snapshot(DataConfig(path=path, verify=level)).id == "synth-0001"
        for _ in range(2):  # the second open reads the stamp the first wrote
            s = stamped(data, stamps)
        assert (stamps / s.physical_hash).is_file()
        assert stamped(data, data / "runs").id == s.id  # a stamp it cannot write is skipped
        assert [(p, p.stat().st_size, p.stat().st_mtime_ns) for p in paths] == before
    finally:
        for path in [data, *paths]:
            path.chmod(0o755 if path.is_dir() else 0o644)


def test_bars_keep_ts_available(tmp_path: Path) -> None:
    """G-TIME-LATE at open: a package with late bars opens with no E14, fallback or warning, and
    the bars its manifest names keep each `ts_available`: a late KR bar's is the close of a
    session 1 to 3 after its own (4.8, #354), every other bar's is its own session's close.
    The bar staying in row s is `market_block`'s (T1.4, test_late_bar_stays_in_its_row)."""
    path = make_snapshot(tmp_path / "late", preset="tiny", degrade=["late_bars"])
    s = open_snapshot(DataConfig(path=path), required=BACKTEST)
    assert (s.fallbacks, s.warnings) == ([], {})
    data = json.loads((path / "tds.json").read_text(encoding="utf-8"))
    sessions = path / dataset(data, "calendar_sessions")["files"][0]["path"]
    close: dict[str, list[dt.datetime]] = {}  # per calendar, its closes in session order
    at: dict[tuple[str, dt.date], int] = {}
    for row in pq.read_table(sessions).sort_by("session_date").to_pylist():
        at[row["calendar_id"], row["session_date"]] = len(close.setdefault(row["calendar_id"], []))
        close[row["calendar_id"]].append(row["ts_close"])
    late = 0
    for f in dataset(data, "bars_1d")["files"]:
        market = f["path"].split("market=")[1].split("/")[0]
        calendar = data["markets"][market]["calendar_id"]
        closes = close[calendar]
        bars = pq.read_table(path / f["path"], columns=["session_date", "ts_available"])
        for bar in bars.to_pylist():
            i = at[calendar, bar["session_date"]]
            if bar["ts_available"] != closes[i]:
                assert (market, bar["ts_available"] in closes[i + 1 : i + 4]) == ("KR", True)
                late += 1
    assert late > 0


def publish(root: Path, tiny: Path, name: str) -> Path:
    """A producer's publication under `root` (4.2): unchanged partitions hard-linked (R3-16),
    a `tds.json` of its own naming snapshot `name`, then `LATEST` swapped to it."""
    shutil.copytree(tiny, root / name, copy_function=os.link)
    os.unlink(root / name / "tds.json")  # written anew, never through the shared inode
    shutil.copy2(tiny / "tds.json", root / name / "tds.json")
    edit_manifest(root / name, lambda d: d.update(snapshot_id=name))
    (root / "LATEST").write_text(f"{name}\n", encoding="utf-8")
    return root / name


def begun(cfg: DataConfig, runs: Path) -> tuple[str, dict[str, Any]]:
    """A run started through `api` on the snapshot `cfg` opens (4.4 step 6), sealed at once:
    its run id and its manifest."""
    record = _begin_run(RunStore(runs), open_snapshot(cfg), cfg, "backtest", "pin").seal()
    return record.run_id, json.loads((record.path / "manifest.json").read_text(encoding="utf-8"))


def test_pin_in_index(tiny: Path, tmp_path: Path) -> None:
    """The run's pin is in the index `pins` (the canonical record, 4.2), with the run row."""
    publish(tmp_path / "data", tiny, "s1")
    run_id, manifest = begun(DataConfig(path=tmp_path / "data"), tmp_path / "runs")
    assert Index(tmp_path / "runs").pinned() == {"s1"}
    assert manifest["retention"] == "managed"
    assert (tmp_path / "data" / "PINS" / "s1" / run_id).is_file()


def test_readonly_root_runs(tiny: Path, tmp_path: Path) -> None:
    """On a read-only data root the run starts, its pin is in the index, the root pin is an
    E30 warning and the manifest says `retention: unmanaged` (4.2, R3-17)."""
    data = tmp_path / "data"
    folders = [data, publish(data, tiny, "s1"), *(p for p in data.rglob("*") if p.is_dir())]
    for folder in folders:
        folder.chmod(0o555)
    try:
        with pytest.warns(UserWarning, match=r"(?s)E30.*root pin not written") as said:
            _, manifest = begun(DataConfig(path=data), tmp_path / "runs")
    finally:
        for folder in folders:
            folder.chmod(0o755)
    assert Index(tmp_path / "runs").pinned() == {"s1"}
    assert manifest["retention"] == "unmanaged"
    assert not (data / "PINS").exists()
    assert str(tmp_path) not in str(said[0].message)  # no local path in the warning (2.7)


def test_default_pins_written_to_root_or_warn(tiny: Path, tmp_path: Path) -> None:
    """The default `index+root` writes an empty `PINS/<snapshot_id>/<run_id>`; `index` writes
    none and says `unmanaged` without a warning; a package with no data root warns."""
    data, runs = tmp_path / "data", tmp_path / "runs"
    publish(data, tiny, "s1")
    assert PinsPolicy(load_config(None).values["data"]["pins"]) is PinsPolicy.INDEX_ROOT
    run_id, manifest = begun(DataConfig(path=data / "s1"), runs)  # the package, root beside it
    assert ((data / "PINS" / "s1" / run_id).read_bytes(), manifest["retention"]) == (b"", "managed")
    other, manifest = begun(DataConfig(path=data, pins=PinsPolicy.INDEX), runs)
    assert not (data / "PINS" / "s1" / other).exists()
    assert manifest["retention"] == "unmanaged"
    with pytest.warns(UserWarning, match=r"(?s)E30.*no data root"):
        _, manifest = begun(DataConfig(path=tiny), runs)  # a package alone: no LATEST, no PINS
    assert manifest["retention"] == "unmanaged"
    for name, bad in (("s2", "../s1"), ("s3", "")):  # never outside PINS/<snapshot_id>/
        edit_manifest(publish(data, tiny, name), lambda d, bad=bad: d.update(snapshot_id=bad))
        with pytest.warns(UserWarning, match=r"(?s)E30.*not one folder name"):
            _, manifest = begun(DataConfig(path=data), runs)
        assert manifest["retention"] == "unmanaged"
    assert sorted(p.name for p in data.rglob("*") if p.parent.name == "PINS") == ["s1"]
    assert Index(runs).pinned() == {"s1", "synth-0001", "../s1", ""}
    toml = tmp_path / "nexusbt.toml"  # `[data] pins` reaches the open through the config
    toml.write_text(f'[data]\npath = "{data.as_posix()}"\npins = "index"\n', encoding="utf-8")
    assert DataConfig.from_config(load_config(toml)).pins is PinsPolicy.INDEX


def test_default_pin_survives_three_publications(tiny: Path, tmp_path: Path) -> None:
    """A run pins s1; the producer then publishes s2, s3 and s4 with s1's partitions hard-linked,
    and a run starts on each. s1's index pin and root pin stay, and s1 still opens on its
    verification stamp, as the shared files keep their identity (R3-16, R3-17)."""
    data, runs, stamps = tmp_path / "data", tmp_path / "runs", tmp_path / "runs/.cache/verified"
    publish(data, tiny, "s1")
    first, _ = begun(DataConfig(path=data), runs)
    open_snapshot(DataConfig(path=data / "s1", stamps=stamps), sha256=True)
    for name in ("s2", "s3", "s4"):
        publish(data, tiny, name)
        begun(DataConfig(path=data), runs)
    assert Index(runs).pinned() == {"s1", "s2", "s3", "s4"}
    assert (data / "PINS" / "s1" / first).is_file()
    assert open_snapshot(DataConfig(path=data)).id == "s4"
    assert open_snapshot(DataConfig(path=data / "s1", stamps=stamps), sha256=True).id == "s1"
