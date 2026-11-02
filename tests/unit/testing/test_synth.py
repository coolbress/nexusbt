"""The synthetic TDS package generator, part 1: the hand-authored `tiny` preset (spec 4.8)."""

from __future__ import annotations

import datetime as dt
import json
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


@pytest.mark.parametrize(("preset", "markets"), [("small", ("KR",)), ("tiny", ()), ("tiny", "XX")])
def test_refuses_unbuilt_preset_and_bad_markets(preset: Any, markets: Any, tmp_path: Path) -> None:
    with pytest.raises(NotImplementedError if preset == "small" else ValueError):
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
    assert lines[:4] == [
        "instruments 12 rows", "instrument_symbols 14 rows", "calendar_sessions 124 rows",
        "bars_1d 682 rows",
    ]  # fmt: skip
    hashes = json.loads((out / "tds.json").read_text(encoding="utf-8"))["hashes"]
    assert lines[4:6] == [f"value_sha256 {hashes['value_sha256']}",
                          f"semantic_sha256 {hashes['semantic_sha256']}"]  # fmt: skip
    assert "0 errors, 0 warnings at level full" in printed.out
