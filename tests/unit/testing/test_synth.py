"""The synthetic TDS package generator: the hand-authored `tiny` and the seeded `small` (4.8)."""

from __future__ import annotations

import csv
import datetime as dt
import json
import sysconfig
from importlib.resources import files
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq
import pytest

from nexusbt.testing.synth import main, make_snapshot

UTC = dt.UTC


@pytest.fixture(scope="module")
def tiny(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return make_snapshot(tmp_path_factory.mktemp("tiny") / "snap", preset="tiny")


def rows(package: Path, kind: str) -> list[dict[str, Any]]:
    """Every row of the dataset of `kind`, read from the files tds.json lists."""
    manifest = json.loads((package / "tds.json").read_text(encoding="utf-8"))
    (entry,) = (d for d in manifest["datasets"] if d["kind"] == kind)
    out: list[dict[str, Any]] = []
    for f in entry["files"]:
        out += pq.read_table(package / f["path"]).to_pylist()
    return out


def session(package: Path, calendar: str, day: dt.date) -> dict[str, Any]:
    (row,) = (
        r for r in rows(package, "calendar_sessions")
        if r["calendar_id"] == calendar and r["session_date"] == day
    )  # fmt: skip
    return row


def test_sessions_have_utc_open_close_with_dst(tiny: Path) -> None:
    # US daylight saving began on Sunday 2020-03-08: 14:30Z-21:00Z before, 13:30Z-20:00Z after
    before = session(tiny, "XNYS", dt.date(2020, 3, 6))
    after = session(tiny, "XNYS", dt.date(2020, 3, 9))
    assert (before["ts_open"], before["ts_close"]) == (
        dt.datetime(2020, 3, 6, 14, 30, tzinfo=UTC),
        dt.datetime(2020, 3, 6, 21, 0, tzinfo=UTC),
    )
    assert (after["ts_open"], after["ts_close"]) == (
        dt.datetime(2020, 3, 9, 13, 30, tzinfo=UTC),
        dt.datetime(2020, 3, 9, 20, 0, tzinfo=UTC),
    )
    kr = session(tiny, "XKRX", dt.date(2020, 3, 9))  # no daylight saving: 00:00Z-06:30Z
    assert (kr["ts_open"], kr["ts_close"]) == (
        dt.datetime(2020, 3, 9, 0, 0, tzinfo=UTC),
        dt.datetime(2020, 3, 9, 6, 30, tzinfo=UTC),
    )
    # the holidays are not sessions: Seollal (KR 2020-01-24, 01-27), Presidents' Day (US 02-17)
    days = {(r["calendar_id"], r["session_date"]) for r in rows(tiny, "calendar_sessions")}
    assert ("XKRX", dt.date(2020, 1, 24)) not in days
    assert ("XKRX", dt.date(2020, 1, 27)) not in days
    assert ("XNYS", dt.date(2020, 2, 17)) not in days
    ords = [r["session_ord"] for r in rows(tiny, "calendar_sessions") if r["calendar_id"] == "XNYS"]
    assert ords == list(range(62))  # 2020 Q1 has 62 NYSE sessions


def files_of(package: Path) -> dict[str, bytes]:
    return {str(p.relative_to(package)): p.read_bytes() for p in package.rglob("*") if p.is_file()}


def test_deterministic_bytes(tiny: Path, tmp_path: Path) -> None:
    again = make_snapshot(tmp_path / "again", preset="tiny")
    assert files_of(again) == files_of(tiny)
    assert "tds.json" in files_of(tiny)


def test_tiny_is_hand_authored_no_rng(tiny: Path, tmp_path: Path) -> None:
    assert files_of(make_snapshot(tmp_path / "s7", preset="tiny", seed=7)) == files_of(tiny)
    closes = [(r["session_date"], r["open"], r["close"]) for r in rows(tiny, "bars")
              if r["instrument_id"] == "KR:T00001"][:3]  # fmt: skip
    assert closes == [
        (dt.date(2020, 1, 2), 10000.0, 10000.0),
        (dt.date(2020, 1, 3), 10000.0, 10100.0),
        (dt.date(2020, 1, 6), 10100.0, 10200.0),
    ]
    us = [r["close"] for r in rows(tiny, "bars") if r["instrument_id"] == "US:T00002"][:4]
    assert us == [20.0, 20.2, 20.4, 20.2]
    mics = {r["instrument_id"]: r["venue_mic"] for r in rows(tiny, "instruments")}
    assert [mics[f"KR:T0000{n}"] for n in (1, 2)] == ["XKRX", "XKOS"]  # fixed: odd, even
    assert [mics[f"US:T0000{n}"] for n in (1, 2)] == ["XNYS", "XNAS"]


def test_bars_dense_per_listing(tiny: Path) -> None:
    sessions = {
        cal: sorted(r["session_date"] for r in rows(tiny, "calendar_sessions")
                    if r["calendar_id"] == cal)
        for cal in ("XKRX", "XNYS")
    }  # fmt: skip
    bars = rows(tiny, "bars")
    for inst in rows(tiny, "instruments"):
        days = [b["session_date"] for b in bars if b["instrument_id"] == inst["instrument_id"]]
        listed = [d for d in sessions[str(inst["calendar_id"])] if d >= inst["listed_on"]]
        assert days == listed, inst["instrument_id"]
    late = [b for b in bars if b["instrument_id"] == "KR:T00006"]
    assert late[0]["session_date"] == dt.date(2020, 2, 18)
    assert len(late) == 31
    assert {b["obs_status"] for b in bars} == {"traded"}
    assert {b["cum_factor_split"] for b in bars} == {b["cum_factor_total"] for b in bars} == {1.0}


def test_symbol_reuse_present(tiny: Path) -> None:
    held = [(r["instrument_id"], r["valid_from"], r["valid_to"])
            for r in rows(tiny, "instrument_symbols") if r["symbol"] == "QUS02"]  # fmt: skip
    assert held == [
        ("US:T00002", dt.date(2020, 1, 2), dt.date(2020, 2, 14)),
        ("US:T00006", dt.date(2020, 2, 18), None),
    ]


def test_zz_market_generated(tiny: Path, tmp_path: Path) -> None:
    assert not [r for r in rows(tiny, "instruments") if r["market"] == "ZZ"]
    zz = make_snapshot(tmp_path / "zz", preset="tiny", markets=("KR", "US", "ZZ"))
    instruments = [r for r in rows(zz, "instruments") if r["market"] == "ZZ"]
    assert len(instruments) == 6
    assert {(r["calendar_id"], r["currency"]) for r in instruments} == {("XZZZ", "XTS")}
    by_calendar = {
        cal: [(r["session_date"], r["ts_open"], r["ts_close"])
              for r in rows(zz, "calendar_sessions") if r["calendar_id"] == cal]
        for cal in ("XZZZ", "XNYS")
    }  # fmt: skip
    assert by_calendar["XZZZ"] == by_calendar["XNYS"]  # a copy of XNYS, only the name differs
    manifest = json.loads((zz / "tds.json").read_text(encoding="utf-8"))
    assert manifest["markets"]["ZZ"]["currency"] == "XTS"
    assert any(f["path"].startswith("bars/freq=1d/market=ZZ/") for d in manifest["datasets"]
               for f in d["files"])  # fmt: skip


@pytest.mark.parametrize(("preset", "markets"), [("full", ("KR",)), ("tiny", ()), ("tiny", "XX")])
def test_refuses_unbuilt_preset_and_bad_markets(preset: Any, markets: Any, tmp_path: Path) -> None:
    with pytest.raises(NotImplementedError if preset == "full" else ValueError):
        make_snapshot(tmp_path / "p", preset=preset, markets=markets)


def test_command_prints_counts_and_hashes_then_checks(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "cli"
    code = main(["--preset", "tiny", "--out", str(out), "--validate"])
    printed = capsys.readouterr()
    assert code == 0, printed.out + printed.err
    lines = printed.out.splitlines()
    # 2 markets x (5 instruments x 62 sessions + 1 listed on 02-18 x 31 sessions)
    assert lines[:5] == [
        "instruments 12 rows", "instrument_symbols 14 rows", "instrument_xref 0 rows",
        "calendar_sessions 124 rows", "bars_1d 682 rows",
    ]  # fmt: skip
    hashes = json.loads((out / "tds.json").read_text(encoding="utf-8"))["hashes"]
    assert lines[5:7] == [f"value_sha256 {hashes['value_sha256']}",
                          f"semantic_sha256 {hashes['semantic_sha256']}"]  # fmt: skip
    assert "0 errors, 0 warnings at level full" in printed.out


def test_command_without_validate_prints_and_does_not_check(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["--preset", "tiny", "--out", str(tmp_path / "plain")]) == 0
    printed = capsys.readouterr().out
    assert "bars_1d 682 rows" in printed
    assert "errors" not in printed


def test_a_failing_tds_hash_is_an_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    scripts = tmp_path / "bin"  # a `tds` that fails, in place of the one beside the interpreter
    scripts.mkdir()
    (scripts / "tds").write_text("#!/bin/sh\necho broken >&2\nexit 3\n", encoding="utf-8")
    (scripts / "tds").chmod(0o755)
    monkeypatch.setattr(sysconfig, "get_path", lambda name: str(scripts))
    with pytest.raises(RuntimeError, match="exited 3: broken"):
        make_snapshot(tmp_path / "p", preset="tiny")


@pytest.fixture(scope="module")
def small(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("small") / "snap"
    return make_snapshot(path, preset="small", markets=("KR", "US", "ZZ"))


def test_small_sessions_from_exchange_calendars(small: Path) -> None:
    us = [r for r in rows(small, "calendar_sessions") if r["calendar_id"] == "XNYS"]
    assert len([r for r in us if r["session_date"].year == 2015]) == 252  # NYSE sessions in 2015
    assert [r["session_ord"] for r in us] == list(range(len(us)))
    half = session(small, "XNYS", dt.date(2019, 11, 29))  # day after Thanksgiving: 13:00 EST
    assert half["ts_close"] == dt.datetime(2019, 11, 29, 18, tzinfo=UTC)
    assert half["is_half_day"]
    assert session(small, "XNYS", dt.date(2019, 3, 8))["ts_open"].hour == 14  # EST
    assert session(small, "XNYS", dt.date(2019, 3, 11))["ts_open"].hour == 13  # EDT from 03-10
    kr = session(small, "XKRX", dt.date(2016, 7, 29))  # 06:00Z close: a full KR day, not half
    assert (kr["ts_close"].time(), kr["is_half_day"]) == (dt.time(6, 0), False)
    assert session(small, "XKRX", dt.date(2016, 8, 1))["ts_close"].time() == dt.time(6, 30)
    assert session(small, "XKRX", dt.date(2019, 11, 14))["ts_open"].time() == dt.time(0, 0)
    zz = [r["session_date"] for r in rows(small, "calendar_sessions") if r["calendar_id"] == "XZZZ"]
    assert zz == [r["session_date"] for r in us]


def test_small_listings_are_dense_and_mixed(small: Path) -> None:
    instruments = rows(small, "instruments")
    assert {m: sum(r["market"] == m for r in instruments) for m in ("KR", "US", "ZZ")} == {
        "KR": 120, "US": 180, "ZZ": 120}  # fmt: skip
    assert {r["listed_on_censored"] for r in instruments} == {True, False}  # listed before, in
    assert any(r["last_session"] for r in instruments)  # and a delisting inside the period
    days: dict[str, list[dt.date]] = {}
    for r in rows(small, "calendar_sessions"):
        days.setdefault(r["calendar_id"], []).append(r["session_date"])
    held: dict[str, list[dt.date]] = {}
    for b in rows(small, "bars"):
        held.setdefault(b["instrument_id"], []).append(b["session_date"])
        assert b["low"] <= min(b["open"], b["close"]) <= max(b["open"], b["close"]) <= b["high"]
    for r in instruments:
        last = r["last_session"] or dt.date(2019, 12, 31)
        life = [d for d in days[r["calendar_id"]] if r["listed_on"] <= d <= last]
        assert held[r["instrument_id"]] == life, r["instrument_id"]


def test_small_tickers_change_and_are_reused(small: Path) -> None:
    holders: dict[str, set[str]] = {}
    per_id: dict[str, int] = {}
    for r in rows(small, "instrument_symbols"):
        holders.setdefault(r["symbol"], set()).add(r["instrument_id"])
        per_id[r["instrument_id"]] = per_id.get(r["instrument_id"], 0) + 1
    assert any(len(ids) > 1 for ids in holders.values())  # an old ticker on another id
    assert any(count > 1 for count in per_id.values())  # a ticker history that changes


@pytest.mark.parametrize("preset", ["tiny", "small"])
def test_emitted_mics_are_in_venue_groups(preset: str, small: Path, tmp_path: Path) -> None:
    table = files("nexusbt.resources") / "costs/venue_groups_v1.csv"
    with table.open(encoding="utf-8") as f:
        listed = {(r["country"], r["venue_mic"]) for r in csv.DictReader(f)}
    package = small if preset == "small" else make_snapshot(
        tmp_path / "t", preset="tiny", markets=("KR", "US", "ZZ"))  # fmt: skip
    mics: dict[str, set[str | None]] = {}
    for r in rows(package, "instruments"):
        mics.setdefault(r["market"], set()).add(r["venue_mic"])
        if r["market"] != "ZZ":  # every KR and US MIC is a row for its country
            assert (r["market"], r["venue_mic"]) in listed, r["instrument_id"]
    assert mics == {"KR": {"XKRX", "XKOS"}, "US": {"XNYS", "XNAS"}, "ZZ": {None}}


def test_small_is_seeded_and_byte_identical(tmp_path: Path) -> None:
    args: dict[str, Any] = {"preset": "small", "end": dt.date(2015, 6, 30), "n_kr": 8, "n_us": 8}
    a, b = make_snapshot(tmp_path / "a", **args), make_snapshot(tmp_path / "b", **args)
    other = make_snapshot(tmp_path / "c", seed=1, **args)
    assert files_of(a) == files_of(b)
    assert files_of(a) != files_of(other)
    us = "bars/freq=1d/market=US/year=2015/part-00000.parquet"  # US rows without KR alongside
    assert files_of(make_snapshot(tmp_path / "u", markets=("US",), **args))[us] == files_of(a)[us]


def test_small_takes_a_short_period(tmp_path: Path) -> None:
    week = make_snapshot(tmp_path / "w", preset="small", start=dt.date(2019, 12, 26),
                         end=dt.date(2019, 12, 31), n_kr=3, n_us=3)  # fmt: skip
    assert len(rows(week, "instruments")) == 6
    with pytest.raises(ValueError, match="small only"):
        make_snapshot(tmp_path / "t", preset="tiny", n_kr=0)
