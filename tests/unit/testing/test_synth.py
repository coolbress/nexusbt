"""The synthetic TDS package generator: the hand-authored `tiny` and the seeded `small` (4.8)."""

from __future__ import annotations

import ast
import csv
import datetime as dt
import inspect
import itertools
import json
import math
import re
import sysconfig
import textwrap
from importlib.resources import files
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
import pytest

from nexusbt.testing import synth
from nexusbt.testing.synth import a001, main, make_snapshot, read

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
    assert lines[:8] == [
        "instruments 12 rows", "instrument_symbols 14 rows", "instrument_xref 0 rows",
        "calendar_sessions 124 rows", "corporate_actions 0 rows", "delistings 0 rows",
        "bars_1d 682 rows", "corporate_actions revisions 0, cancellations 0",
    ]  # fmt: skip
    hashes = json.loads((out / "tds.json").read_text(encoding="utf-8"))["hashes"]
    assert lines[8:11] == [
        f"value_sha256 {hashes['value_sha256']}",
        f"semantic_sha256 {hashes['semantic_sha256']}",
        "TDS-A001: 0",
    ]
    assert "0 errors, 0 warnings at level full" in printed.out
    assert "tds:equity-daily-core@1.0: declared" in printed.out  # with empty events (TDS 7)


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
        if b["obs_status"] == "traded":  # a halted bar has no prices (4.8 (5))
            assert b["low"] <= min(b["open"], b["close"]) <= max(b["open"], b["close"])
            assert max(b["open"], b["close"]) <= b["high"]
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


def test_small_hashes_match_on_macos_and_linux(tmp_path: Path) -> None:
    # printed by a macOS arm64 run; `ci / test` on Linux must reach the same literals (#139)
    package = make_snapshot(tmp_path / "d", preset="small")  # default markets KR, US; seed 0
    hashes = json.loads((package / "tds.json").read_text())["hashes"]
    assert (hashes["value_sha256"], hashes["semantic_sha256"]) == (
        "e9d34e7e8e348bd462f9ed945e2e337fea297faff6b06c781eb21eb6c153f521",
        "65b7624fbacdfadf9fa77972bfd6bed1dc531e7376785673ab92d25f10b107fd",
    )


#: Calls that go through platform code (SIMD paths, the system libm), so their last bits can
#: differ between machines: none of them may reach a column of `small` (#128, #139).
PLATFORM_MATH = {"exp", "log", "normal", "lognormal", "sqrt", "power"}


def called_names(source: str) -> set[str]:
    """The names of the functions and methods the code in `source` calls; `**` is `power`."""
    nodes = list(ast.walk(ast.parse(textwrap.dedent(source))))
    calls = (n.func for n in nodes if isinstance(n, ast.Call))
    names = {f.id if isinstance(f, ast.Name) else f.attr for f in calls
             if isinstance(f, ast.Name | ast.Attribute)}  # fmt: skip
    ops = (n.op for n in nodes if isinstance(n, ast.BinOp | ast.AugAssign))
    pow_ = any(isinstance(op, ast.Pow) for op in ops)
    return names | ({"power"} if pow_ else set())


def test_small_value_path_uses_no_platform_math() -> None:
    for step in (synth._small, synth._actions, synth._terms, synth._dividend, synth._revise,
                 synth._move, synth._delistings, synth._exit_value, synth._snap, synth._ratios,
                 synth._kr_rows, synth._tradability, synth._sample, synth._halts, synth._limits,
                 synth._wobble, synth._status, synth._last_traded):  # fmt: skip
        assert not called_names(inspect.getsource(step)) & PLATFORM_MATH, step.__name__
    # the check refuses what it is for, so the pass above is not vacuous
    bad = "def f(rng, p):\n    return np.exp(rng.normal(0, 1)) * p.sqrt() + math.log(2) ** 2\n"
    assert called_names(bad) & PLATFORM_MATH == {"exp", "normal", "sqrt", "log", "power"}


def test_small_takes_a_short_period(tmp_path: Path) -> None:
    week = make_snapshot(tmp_path / "w", preset="small", start=dt.date(2019, 12, 26),
                         end=dt.date(2019, 12, 31), n_kr=3, n_us=3)  # fmt: skip
    assert len(rows(week, "instruments")) == 6
    with pytest.raises(ValueError, match="small only"):
        make_snapshot(tmp_path / "t", preset="tiny", n_kr=0)


def steps(package: Path, basis: str) -> dict[tuple[str, dt.date], float]:
    """cum_factor_<basis>[s] / [s-1] of each bar after an instrument's first."""
    bars = sorted(rows(package, "bars"), key=lambda b: (b["instrument_id"], b["session_date"]))
    key, col = "instrument_id", f"cum_factor_{basis}"
    return {(b[key], b["session_date"]): b[col] / a[col]
            for a, b in itertools.pairwise(bars) if a[key] == b[key]}  # fmt: skip


def test_factor_event_reconciliation(small: Path) -> None:
    actions = read(small, "corporate_actions")
    assert a001(actions, read(small, "bars_1d")) == 0
    revised = {r["revision_of"]: r for r in actions.to_pylist()
               if r["revision_of"] and r["status"] == "effective"}  # fmt: skip
    total = steps(small, "total")
    for old in (r for r in actions.to_pylist() if r["event_id"] in revised):
        new = revised[old["event_id"]]  # the bars move by the amended factor, not the first
        assert new["price_factor"] != old["price_factor"]
        assert total[new["instrument_id"], new["ex_date"]] == pytest.approx(new["price_factor"])
    # counter-example: without its amendments the first versions are the latest, and A001 sees it
    amendments = pa.array([r["event_id"] for r in revised.values()])
    stale = actions.filter(pc.invert(pc.is_in(actions["event_id"], amendments)))
    assert a001(stale, read(small, "bars_1d")) == len(revised) + sum(
        r["kind"] != "cash_dividend" for r in revised.values()
    )  # a share event: split and total


def test_reverse_split_makes_factor_non_monotonic(small: Path) -> None:
    split = steps(small, "split")
    reverse = [r for r in rows(small, "corporate_actions") if r["kind"] == "reverse_split"]
    assert reverse
    for r in reverse:  # 1:10 → x10, 1:3 → x3: up, where a split or a dividend goes down
        assert r["price_factor"] == r["ratio_den"] / r["ratio_num"] > 1
    ups = [r for r in reverse if split[r["instrument_id"], r["ex_date"]] > 1]
    assert ups  # a rising factor is data, not an error: A001 above and tds check below hold
    assert min(split.values()) < 1
    assert "0 errors" in synth._tds("check", str(small), "--level", "full").stdout


def test_revisions_and_cancellations_present(
    small: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    actions = rows(small, "corporate_actions")
    by_id = {r["event_id"]: r for r in actions}
    later = [(by_id[r["revision_of"]], r) for r in actions if r["revision_of"]]
    amended = [(a, b) for a, b in later if b["status"] == "effective"]
    assert any(a["cash_per_share"] < b["cash_per_share"] for a, b in amended
               if a["cash_per_share"])  # an amount  # fmt: skip
    assert any(a["ratio_num"] != b["ratio_num"] for a, b in amended if a["ratio_num"])  # a ratio
    assert any(b["ts_announced"].date() > b["pay_date"] for _, b in amended)  # after payment
    cancelled = [(a, b) for a, b in later if b["status"] == "cancelled"]
    assert cancelled
    for a, b in cancelled:  # cancelled after the announcement, before it took effect
        assert a["status"] == "announced"
        assert a["ts_announced"] < b["ts_announced"] < b["ts_effective"]
    for r in (r for r in actions if r["kind"] in synth.SHARE_EVENTS):  # exact ratios (#220 (2))
        quotient = r["ratio_num"] / r["ratio_den"]
        assert quotient == r["share_factor"] == pytest.approx(1 / r["price_factor"], rel=1e-12)
    dividends = [r for r in actions if r["kind"] == "cash_dividend"]
    assert {r["resolution_body"] for r in dividends} == {"meeting", "board", None}  # #220 (1)
    assert all(r["ex_date"].month >= 10 for r in dividends if r["resolution_body"] == "meeting")
    late = [(r["ts_terms_available"].date() - r["ex_date"]).days for r in dividends
            if r["ts_terms_available"]]  # fmt: skip
    assert late
    assert {r["instrument_id"][:3] for r in dividends if r["ts_terms_available"]} == {"KR:"}
    assert 30 <= min(late) <= max(late) <= 61  # 30~60 days after the ex-date's close
    code = main(["--preset", "small", "--out", str(tmp_path / "cli"), "--validate"])
    printed = capsys.readouterr().out
    assert code == 0, printed
    assert "TDS-A001: 0" in printed.splitlines()
    assert re.search(r"^corporate_actions revisions [1-9]\d*, cancellations [1-9]", printed, re.M)


def test_delisted_on_matches_delistings(small: Path) -> None:
    exits = {r["instrument_id"]: r for r in rows(small, "delistings")}
    instruments = rows(small, "instruments")
    for r in instruments:  # one exit per listing that ends in the period, at delisted_on (R008)
        out = exits.get(r["instrument_id"])
        assert (out and out["exit_date"], out and out["last_trading_date"]) == (
            r["delisted_on"], r["last_session"]), r["instrument_id"]  # fmt: skip
    assert len(exits) == sum(r["delisted_on"] is not None for r in instruments) > 0
    closes = {(b["instrument_id"], b["session_date"]): b["close"] for b in rows(small, "bars")}
    for r in exits.values():
        assert r["ref_price"] == closes[r["instrument_id"], r["ref_date"]]
        assert r["last_trading_date"] < r["exit_date"]
        assert r["ret_lo"] <= r["ret_hi"]
        assert r["ts_exit_known"] < dt.datetime.combine(r["exit_date"], dt.time(), UTC)
    status = [r["exit_value_status"] for r in exits.values()]
    assert set(status) == {"observed", "estimated", "unobserved"}
    late = [(r["ts_value_available"].date() - r["exit_date"]).days for r in exits.values()
            if r["ts_value_available"]]  # fmt: skip
    assert late
    assert 20 <= min(late) <= max(late) <= 90  # INV-01: an observed value published late
    unobserved = [r["ret_policy"] for r in exits.values() if r["exit_value_status"] == "unobserved"]
    assert None in unobserved  # 5.6.13's E13 path: no policy value for a holding
    assert -0.3 in unobserved
    # 4.8 (4): a liquidating distribution between the last trading day and the exit
    payouts = [r for r in rows(small, "corporate_actions") if r["kind"] == "return_of_capital"]
    assert payouts
    for p in payouts:
        out = exits[p["instrument_id"]]
        assert out["last_trading_date"] < p["ex_date"] < out["exit_date"]
        assert out["delist_type"] == "liquidation"
        assert out["ret_observed_includes_distributions"] is not None  # no A011
    assert all(r["ret_observed_includes_distributions"] is None for r in exits.values()
               if r["delist_type"] != "liquidation")  # fmt: skip


def kr_tick(price: float, venue: str) -> int:
    """KRX tick sizes from 2010-10-04 to 2023-01-25 (KOSPI XKRX, KOSDAQ XKOS), written out."""
    bands = [(1000, 1), (5000, 5), (10000, 10), (50000, 50)]
    bands += [(100000, 100), (500000, 500)] if venue == "XKRX" else []
    return next((t for top, t in bands if price < top), 1000 if venue == "XKRX" else 100)


def test_kr_prices_on_grid_with_halts_and_limits(small: Path) -> None:
    venue = {r["instrument_id"]: r["venue_mic"] for r in rows(small, "instruments")}
    status = {(r["instrument_id"], r["session_date"]): r for r in rows(small, "tradability_daily")}
    bars = sorted(rows(small, "bars"), key=lambda b: (b["instrument_id"], b["session_date"]))
    assert len(status) == len(bars)
    wobbled = 0
    for b in (b for b in bars if b["instrument_id"].startswith("KR:")):
        s, v = status[b["instrument_id"], b["session_date"]], venue[b["instrument_id"]]
        assert s["halted_full_day"] == (b["obs_status"] == "halted")
        if s["halted_full_day"]:  # no prices, no volume
            assert (b["open"], b["close"], b["volume"]) == (None, None, 0.0)
            continue
        for p in (b["open"], b["high"], b["low"]):
            assert p % kr_tick(p, v) == 0, b
        on_grid = round(b["close"] / kr_tick(b["close"], v)) * kr_tick(b["close"], v)
        assert b["close"] in (on_grid, math.nextafter(on_grid, math.inf)), b  # V31-05's wobble
        wobbled += b["close"] != on_grid
        if s["limit_up_close"] or s["limit_down_close"]:  # at the limit, snapped inward
            limit = s["up_limit_price"] if s["limit_up_close"] else s["down_limit_price"]
            tick = kr_tick(limit, v)
            inward = (math.floor if s["limit_up_close"] else math.ceil)(limit / tick) * tick
            assert b["close"] == inward, b
        if s["locked_up"] or s["locked_down"]:
            assert b["open"] == b["high"] == b["low"] == b["close"]
    assert wobbled > 0
    kr = [s for s in status.values() if s["instrument_id"].startswith("KR:")]
    for flag in ("halted_full_day", "limit_up_close", "limit_down_close", "locked_up"):
        assert any(s[flag] for s in kr), flag
    halted = {(s["instrument_id"], s["session_date"]) for s in kr if s["halted_full_day"]}
    over = {r["kind"] for r in rows(small, "corporate_actions")
            if (r["instrument_id"], r["ex_date"]) in halted}  # fmt: skip
    assert {"split", "cash_dividend"} <= over  # G-54: a split and an ex-dividend in a halt


def test_a_halt_never_hides_a_close_a_factor_uses() -> None:
    rng, split = np.random.Generator(np.random.PCG64(0)), [(0, 3, "split")]  # G-54: from 3
    for refs in ({(0, 3)}, set()):  # another event's factor uses session 3's close, or none
        bars: dict[str, list[Any]] = {n: [np.full(6, 100.0)] for n in (*synth.OHLC, "volume")}
        bars["obs_status"] = [["traded"] * 6]
        halted = synth._halts([0], [5], split, refs, bars, rng)
        assert (bars["obs_status"][0][3] == "halted") == bool(halted) == (not refs)


def test_tradability_rows_by_market(small: Path) -> None:
    bars = {(b["instrument_id"], b["session_date"]): b for b in rows(small, "bars")}
    before: dict[str, tuple[float, float]] = {}  # each instrument's last close and its factor
    for s in sorted(rows(small, "tradability_daily"),
                    key=lambda r: (r["instrument_id"], r["session_date"])):  # fmt: skip
        market, day = s["instrument_id"][:2], s["session_date"]
        bar = bars[s["instrument_id"], day]
        if market == "KR":  # from the last close moved by share events, without tick rounding
            ratio = s["price_limit_ratio"]
            assert ratio == (0.15 if day < dt.date(2015, 6, 15) else 0.3)
            last = before.get(s["instrument_id"])
            ref = None if last is None else last[0] * (bar["cum_factor_split"] / last[1])
            assert s["reference_price"] == ref
            if ref is not None:
                assert s["up_limit_price"] == ref * (1 + ratio)
                assert s["down_limit_price"] == ref * (1 - ratio)
                if bar["open"] is not None:  # every bar trades within its own limits
                    assert s["down_limit_price"] <= bar["low"] <= bar["high"]
                    assert bar["high"] <= s["up_limit_price"]
            assert s["admin_status"] in ("normal", "administrative")
        else:  # no price limits, no administrative status
            assert s["up_limit_price"] is s["limit_up_close"] is s["admin_status"] is None
        known = market != "US" or day >= dt.date(2019, 8, 23)
        assert s["status_known"] == known
        if not known:  # nothing else is known either
            assert s["halted_full_day"] is s["halt_count"] is None
        elif market != "KR":
            assert (s["halted_full_day"], s["halt_count"]) == (False, 0)
        if bar["close"] is not None:
            before[s["instrument_id"]] = (bar["close"], bar["cum_factor_split"])
    admin = [s for s in rows(small, "tradability_daily") if s["admin_status"] == "administrative"]
    assert admin
    manifest = json.loads((small / "tds.json").read_text(encoding="utf-8"))
    (entry,) = (d for d in manifest["datasets"] if d["kind"] == "tradability_daily")
    by_column = entry["params"]["availability_by_column"]  # TDS 5.10: before and after the day
    assert by_column["up_limit_price"] == by_column["admin_status"] == "session_open"
    assert by_column["halted_full_day"] == by_column["locked_down"] == "session_close"
