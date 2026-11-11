"""The synthetic TDS package generator: the hand-authored `tiny` and the seeded `small` (4.8)."""

from __future__ import annotations

import ast
import bisect
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

from nexusbt.testing import _synth_actions as acts
from nexusbt.testing import _synth_daily as daily
from nexusbt.testing import _synth_events as events
from nexusbt.testing import _synth_exits as delist
from nexusbt.testing import _synth_package as pkg
from nexusbt.testing import _synth_trade as trade
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


@pytest.mark.parametrize(("preset", "markets"),
                         [("full_ci", ("KR",)), ("tiny", ()), ("tiny", "XX")])  # fmt: skip
def test_refuses_unbuilt_preset_and_bad_markets(preset: Any, markets: Any, tmp_path: Path) -> None:
    with pytest.raises(NotImplementedError if preset == "full_ci" else ValueError):
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
    assert lines[8:10] == [
        f"value_sha256 {hashes['value_sha256']}",
        f"semantic_sha256 {hashes['semantic_sha256']}",
    ]
    assert re.fullmatch(r"time \d+\.\d s, size \d+ bytes", lines[10])
    assert lines[11:13] == ["profiles tds:minimal-daily@1.0, tds:equity-daily-core@1.0",
                            "TDS-A001: 0"]  # fmt: skip
    assert "0 errors, 0 warnings at level full" in printed.out
    assert "tds:equity-daily-core@1.0: declared" in printed.out  # with empty events (TDS 7)


def test_command_degrade_prints_declared_profiles_and_results(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # T0.16a's done line, on tiny: the declared profiles without core, and the three results
    out = tmp_path / "cli"
    args = ["--out", str(out), "--degrade", "no_ohlc,kr_ex_is_record", "--validate"]
    assert main(["--preset", "tiny", *args]) == 0
    printed = capsys.readouterr().out
    assert "profiles tds:minimal-daily@1.0\n" in printed
    assert re.search(r"^tds:minimal-daily@1\.0: declared, verified to \w+, \w+$", printed, re.M)
    assert "tds:equity-daily-core@1.0" not in printed.replace("profiles tds:minimal", "")
    assert main(["--preset", "tiny", *args[:2], "--degrade", "no_cum_factors", "--validate"]) == 0
    assert "TDS-A001: no cum_factor_* columns\n" in capsys.readouterr().out


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
        "be5d9625deac39764d994d74558799a48cd1227c77a6b9c85f2645a2577e8f9f",
        "e86cb0abf4d73c2c8650133171561e93557e7710d2db9adae7dd688b47d4775f",  # #231: value_traded
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
    for step in (synth._listings, synth._small, acts._actions, acts._terms, acts._dividend,
                 acts._revise, acts._move, delist._delistings, events.exit_value, daily._snap,
                 daily._ratios, daily._kr_rows, trade._tradability, trade._sample, trade._halts,
                 trade._limits, trade._wobble, trade._status, trade._last_traded,
                 daily._share_counts, daily._eligibility, daily._venues, daily._value_traded,
                 daily._market_rules):  # fmt: skip
        assert not called_names(inspect.getsource(step)) & PLATFORM_MATH, step.__name__
    # the check refuses what it is for, so the pass above is not vacuous
    bad = "def f(rng, p):\n    return np.exp(rng.normal(0, 1)) * p.sqrt() + math.log(2) ** 2\n"
    assert called_names(bad) & PLATFORM_MATH == {"exp", "normal", "sqrt", "log", "power"}


def test_small_takes_a_short_period(tmp_path: Path) -> None:
    week = make_snapshot(tmp_path / "w", preset="small", start=dt.date(2019, 12, 26),
                         end=dt.date(2019, 12, 31), n_kr=3, n_us=3)  # fmt: skip
    assert len(rows(week, "instruments")) == 6
    with pytest.raises(ValueError, match="small and full only"):
        make_snapshot(tmp_path / "t", preset="tiny", n_kr=0)


def test_full_preset_parameters_match_table(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """4.8's table and T0.8d: KR 5,500 + US 22,100 instruments ever listed, 1995-01-02 to
    2024-12-31, snapshot `synth-full-m1-0001`; the command asks for it without CI making it."""
    full = synth.PRESETS["full"]
    assert (full.start, full.end) == (dt.date(1995, 1, 2), dt.date(2024, 12, 31))
    assert (full.counts["KR"], full.counts["US"]) == (5_500, 22_100)
    assert full.snapshot_id == "synth-full-m1-0001"
    asked: dict[str, Any] = {}

    def record(root: Path, **kwargs: Any) -> Path:  # makes tiny in full's place
        asked.update(kwargs)
        return make_snapshot(root, preset="tiny")

    monkeypatch.setattr(synth, "make_snapshot", record)
    assert main(["--preset", "full", "--out", str(tmp_path / "f")]) == 0
    assert (asked["preset"], asked["snapshot_id"]) == ("full", "synth-full-m1-0001")
    assert re.search(r"^time \d+\.\d s, size \d+ bytes$", capsys.readouterr().out, re.M)


def open_sessions(spans: tuple[list[int], list[int]]) -> int:
    """The sessions the listings of `_listings` are open on, summed: their daily bar rows."""
    return sum(j - i + 1 for i, j in zip(*spans, strict=True))


def test_full_holds_the_tables_instruments_alive_on_a_day() -> None:
    """#334: 4.8's table gives `full` about KR 2,300 and US 5,700 instruments alive on a day.
    At a tenth of its instruments the mean count of listings open on a session, drawn from
    `make_snapshot`'s streams of seed 0, is within 10 % of a tenth of those in each market,
    and `small` keeps 4.8 (2)'s mean life of 8 years."""
    full = synth.PRESETS["full"]
    spawned = np.random.Generator(np.random.PCG64(0)).spawn(3)
    streams = dict(zip(synth.MARKETS, spawned, strict=True))
    for market, table in (("KR", 2_300), ("US", 5_700)):
        calendar = synth._small_calendar(synth.MARKETS[market]["calendar_id"], full.start, full.end)
        n, sessions = full.counts[market] // 10, len(calendar["session_date"])
        spans = synth._listings(n, sessions, full.life[market], streams[market])
        assert open_sessions(spans) / sessions == pytest.approx(table / 10, rel=0.1), market
    assert set(synth.PRESETS["small"].life.values()) == {8}


def test_full_is_small_rules_at_full_scale(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`full` with fewer instruments writes the same data as `small` over full's period with
    full's listing lives (#334), its bars are those listings' sessions, and that period (from
    1995, before KR price limits) passes `tds check --level full` (INV-17)."""
    few: dict[str, Any] = {"n_kr": 6, "n_us": 6}
    full = make_snapshot(tmp_path / "full", preset="full", **few)
    kr = np.random.Generator(np.random.PCG64(0)).spawn(3)[0]  # make_snapshot's KR stream, seed 0
    days = sum(r["calendar_id"] == "XKRX" for r in rows(full, "calendar_sessions"))
    drawn = open_sessions(synth._listings(6, days, synth.PRESETS["full"].life["KR"], kr))
    assert sum(r["instrument_id"].startswith("KR:") for r in rows(full, "bars")) == drawn
    lives = synth.PRESETS["small"]._replace(life=synth.PRESETS["full"].life)
    monkeypatch.setitem(synth.PRESETS, "small", lives)
    small = make_snapshot(tmp_path / "small", preset="small", start=dt.date(1995, 1, 2),
                          end=dt.date(2024, 12, 31), **few)  # fmt: skip
    data, same = files_of(full), files_of(small)
    assert data.pop("tds.json") != same.pop("tds.json")  # the name synth-full, the hashes alike
    assert data == same
    manifest = json.loads((full / "tds.json").read_text(encoding="utf-8"))
    assert manifest["name"] == "synth-full"
    paths = {f["path"] for d in manifest["datasets"] for f in d["files"]}
    assert {f"bars/freq=1d/market={m}/year={y}/part-00000.parquet"
            for m in ("KR", "US") for y in (1995, 2024)} <= paths  # fmt: skip
    done = pkg._tds("check", str(full), "--level", "full")
    assert done.returncode == 0, done.stdout + done.stderr
    assert "0 errors, 0 warnings at level full" in done.stdout


@pytest.mark.parametrize(("term", "ref", "unit", "cash"), [
    (20, 0.0075, 100, 0.01),  # a close under one cent: the one-cent floor is above it (#357)
    (20, 1.0, 1, 1.0),  # a close of one won: the floor equals it, a factor of 0
    (8000, 2.0, 1, 2.0),  # a return of capital of 80 % of 2 won rounds up to the close
])  # fmt: skip
def test_cash_reaching_the_previous_close_has_no_factor(
    term: int, ref: float, unit: int, cash: float
) -> None:
    """TDS 5.11: 1 - D / close[e-1] is not positive, so the factor is null and its method
    `unavailable`, never a value A003 refuses; one cent on a two-cent close keeps its factor."""
    terms = acts._terms("cash_dividend", term, ref, unit, "USD")
    assert (terms["cash_per_share"], terms["factor_ref_price"]) == (cash, ref)
    assert (terms["price_factor"], terms["factor_method"]) == (None, "unavailable")
    below = acts._terms("cash_dividend", 20, 0.02, 100, "USD")
    assert (below["price_factor"], below["factor_method"]) == (0.5, "cash_prev_close")


def test_full_slice_with_a_dividend_above_the_close_conforms(tmp_path: Path) -> None:
    """#357: a slice of `full` (seed 29, 60 US instruments; seed 49 before #334's lives) where
    US:T00041 closes under a cent from its 2015-12-14 dividend on. No factor is null or <= 0
    under a method other than `unavailable`, those dividends move no bar, and the package passes
    the full level (INV-17)."""
    full = make_snapshot(tmp_path / "f", preset="full", seed=29, markets=("US",), n_us=60)
    actions = rows(full, "corporate_actions")
    none = [r for r in actions if r["factor_method"] == "unavailable"]
    assert {(r["instrument_id"], r["kind"]) for r in none} == {("US:T00041", "cash_dividend")}
    assert min(r["ex_date"] for r in none) == dt.date(2015, 12, 14)
    total = steps(full, "total")
    for r in none:  # the one-cent floor reaches the close: no factor, and the bars stay
        assert r["price_factor"] is None
        assert r["cash_per_share"] == 0.01 > r["factor_ref_price"]
        assert total[r["instrument_id"], r["ex_date"]] == 1.0
    assert all(r["price_factor"] > 0 for r in actions if r not in none)
    assert min(b["close"] for b in rows(full, "bars")) > 0  # a negative factor flipped them
    assert a001(read(full, "corporate_actions"), read(full, "bars_1d")) == 0
    assert "0 errors" in pkg._tds("check", str(full), "--level", "full").stdout


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
    assert "0 errors" in pkg._tds("check", str(small), "--level", "full").stdout


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
    for r in (r for r in actions if r["kind"] in acts.SHARE_EVENTS):  # exact ratios (#220 (2))
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


def test_small_declares_availability_for_every_dataset_with_an_instant(small: Path) -> None:
    # TDS 4.2, 6.2 (#276); instruments and calendar_sessions are timeless (8.2), and
    # instrument_xref has no known time in v1 (5.3)
    manifest = json.loads((small / "tds.json").read_text(encoding="utf-8"))
    assert {d["name"]: d.get("availability") for d in manifest["datasets"]} == {
        "instruments": None,
        "instrument_symbols": {"column": "ts_known_from"},
        "instrument_xref": None,
        "calendar_sessions": None,
        "corporate_actions": {"effect": "ts_effective", "terms": "ts_terms_available"},
        "delistings": {"exit": "ts_exit_known", "value": "ts_value_available"},
        "market_rules": None,  # 5.27 has no instant column, only its validity dates
        "bars_1d": {"rule": "ts_end"},
        "tradability_daily": None,  # its rules are `params.availability_by_column` (6.2, 5.10)
        "share_counts": {"column": "ts_available"},
        "eligibility_daily": {"rule": "session_close"},
    }
    (status,) = (d for d in manifest["datasets"] if d["name"] == "tradability_daily")
    assert status["params"]["availability_by_column"]


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
        if s["limit_up_close"] or s["limit_down_close"]:  # at the published limit price
            limit = s["up_limit_price"] if s["limit_up_close"] else s["down_limit_price"]
            assert b["close"] == limit, b
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


def warned(printed: str, code: str) -> int:
    """The warnings of `code` in what `tds check` printed, one line per dataset or key."""
    return len(re.findall(rf"^warning TDS-{code}\b", printed, re.M))


def test_prices_on_grid_with_ulp_noise(small: Path, tmp_path: Path) -> None:
    # 4.8 (5), (11a) [V31-05]: the package declares the KR grid, and its raw prices are on it
    rules = rows(small, "market_rules")
    bands = [r for r in rules if r["rule_kind"] == "tick_band"]
    assert {r["valid_from"] for r in bands} == {dt.date(2010, 10, 4), dt.date(2023, 1, 25)}
    assert {(r["venue_group"], r["limit_ratio"]) for r in rules
            if r["rule_kind"] == "price_limit" and r["valid_to"] is None} == {
        ("KOSPI", 0.3), ("KOSDAQ", 0.3)}  # fmt: skip
    assert {r["market"] for r in rules} == {"KR"}
    pointed = {(r["market"], r["tick_rule_id"]) for r in rows(small, "instruments")}
    assert pointed == {("KR", bands[0]["rule_id"]), ("US", None), ("ZZ", None)}
    closes = [b["close"] for b in rows(small, "bars")
              if b[ID].startswith("KR:") and b["close"] is not None]  # fmt: skip
    noisy = [c for c in closes if c != round(c)]  # every KR tick is a whole number of won
    assert noisy
    assert all(c == math.nextafter(round(c), math.inf) for c in noisy)  # 1 ULP: within 1e-9
    assert warned(check_full(small), "V012") == 0
    # counter-example: the lows of one file 1e-7 lower, and V012 counts each of them
    package = make_snapshot(tmp_path / "off", **SHORT, markets=("KR",))
    path = package / "bars/freq=1d/market=KR/year=2019/part-00000.parquet"
    bars = pq.read_table(path)
    lows = pc.multiply(bars["low"], 1 - 1e-7)
    pq.write_table(bars.set_column(bars.schema.get_field_index("low"), "low", lows), path)
    assert pkg._tds("hash", str(package), "--write").returncode == 0
    printed = pkg._tds("check", str(package), "--level", "full").stdout
    off = len(bars) - bars["low"].null_count
    assert f"warning TDS-V012 bars_1d: {off} raw price(s) off the price grid" in printed


def test_a_halt_never_hides_a_close_a_factor_uses() -> None:
    rng, split = np.random.Generator(np.random.PCG64(0)), [(0, 3, "split")]  # G-54: from 3
    for refs in ({(0, 3)}, set()):  # another event's factor uses session 3's close, or none
        bars: dict[str, list[Any]] = {n: [np.full(6, 100.0)] for n in (*daily.OHLC, "volume")}
        bars["obs_status"] = [["traded"] * 6]
        halted = trade._halts([0], [5], split, refs, bars, rng, set())
        assert (bars["obs_status"][0][3] == "halted") == bool(halted) == (not refs)


def test_tradability_rows_by_market(small: Path) -> None:
    bars = {(b["instrument_id"], b["session_date"]): b for b in rows(small, "bars")}
    before: dict[str, tuple[float, float]] = {}  # each instrument's last close and its factor
    for s in sorted(rows(small, "tradability_daily"),
                    key=lambda r: (r["instrument_id"], r["session_date"])):  # fmt: skip
        market, day = s["instrument_id"][:2], s["session_date"]
        bar = bars[s["instrument_id"], day]
        if market == "KR":  # from the last close moved by share events
            ratio = s["price_limit_ratio"]
            assert ratio == (0.15 if day < dt.date(2015, 6, 15) else 0.3)
            last = before.get(s["instrument_id"])
            ref = None if last is None else last[0] * (bar["cum_factor_split"] / last[1])
            assert s["reference_price"] == ref
            if ref is None:
                assert s["up_limit_price"] is s["down_limit_price"] is None
            else:
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


def test_kr_limit_prices_on_the_grid_inside_the_band(small: Path) -> None:
    """TDS 5.10: the upper limit rounded down and the lower up to the tick, so both lie inside
    `reference_price x (1 +- price_limit_ratio)`, each the nearest grid price there."""
    venue = {r["instrument_id"]: r["venue_mic"] for r in rows(small, "instruments")}
    checked = 0
    for s in rows(small, "tradability_daily"):
        if not s["instrument_id"].startswith("KR:") or s["reference_price"] is None:
            continue
        v, ref, ratio = venue[s["instrument_id"]], s["reference_price"], s["price_limit_ratio"]
        up, down = s["up_limit_price"], s["down_limit_price"]
        assert up % kr_tick(up, v) == 0, s
        assert down % kr_tick(down, v) == 0, s
        assert ref * (1 + ratio) - kr_tick(up, v) < up <= ref * (1 + ratio) + 1e-6, s
        assert ref * (1 - ratio) - 1e-6 <= down < ref * (1 - ratio) + kr_tick(down, v), s
        checked += 1
    assert checked


def test_limit_prices_round_inward_on_the_issue_example() -> None:
    """KR reference 10,030 won at 0.30 on the 2023 table's 10-won band: 13,039 down to 13,030
    and 7,021 up to 7,030; 10,000 x 0.7, 7,000 within a float error, stays 7,000."""
    dates = np.array(["2024-01-02"] * 2, dtype="datetime64[D]")
    up, down = trade._limit_prices(np.array([10030.0, 10000.0]), np.full(2, 0.3), dates, "XKRX")
    assert (up.tolist(), down.tolist()) == ([13030.0, 13000.0], [7030.0, 7000.0])


def test_no_limit_hit_before_kr_had_a_price_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    """`kr_price_limits_v1` starts on 1995-04-01: a day before has no limit to close at, so no
    hit falls there, and no price after it turns NaN (full's period starts 1995-01-02)."""
    dates = np.arange("1995-03-20", "1995-04-15", dtype="datetime64[D]")  # every day offered
    bars: dict[str, list[Any]] = {n: [np.full(len(dates), 10_000.0)] for n in daily.OHLC}
    bars["session_date"] = [dates]

    def every_day(first: Any, last: Any, rate: float, rng: Any, take: Any) -> None:
        for d in range(first[0] + 1, last[0] + 1):
            take(0, d)

    monkeypatch.setattr(trade, "_sample", every_day)
    rng = np.random.Generator(np.random.PCG64(0))
    hits = trade._limits([0], [len(dates) - 1], ["XKRX"], [0], set(), bars, rng)
    assert hits  # the days from 1995-04-01 take some
    assert min(dates[d] for _, d in hits) >= np.datetime64("1995-04-01")
    assert not any(np.isnan(bars[n][0]).any() for n in daily.OHLC)


def by_bar(package: Path, kind: str) -> dict[tuple[str, dt.date], dict[str, Any]]:
    return {(r["instrument_id"], r["session_date"]): r for r in rows(package, kind)}


def test_eligibility_no_lookahead(small: Path) -> None:
    manifest = json.loads((small / "tds.json").read_text(encoding="utf-8"))
    (entry,) = (d for d in manifest["datasets"] if d["kind"] == "eligibility_daily")
    assert entry["availability"] == {"rule": "session_close"}  # not v2's session_open (RV-C09)
    assert entry["params"] == {"missing_means": False}  # no row yet: not eligible
    calendar = {r["instrument_id"]: r["calendar_id"] for r in rows(small, "instruments")}
    hours = {(r["calendar_id"], r["session_date"]): (r["ts_open"], r["ts_close"])
             for r in rows(small, "calendar_sessions")}  # fmt: skip
    bars, status = by_bar(small, "bars"), by_bar(small, "tradability_daily")
    runs: dict[str, str] = {}  # each instrument's eligibility, one letter per change
    for e in sorted(rows(small, "eligibility_daily"),
                    key=lambda r: (r["instrument_id"], r["session_date"])):  # fmt: skip
        iid, day = e["instrument_id"], e["session_date"]
        opens, closes = hours[calendar[iid], day]
        assert e["ts_available"] == closes > opens  # a decision at its own open cannot read it
        traded = bars[iid, day]["obs_status"] == "traded"  # that day's own result
        admin = status[iid, day]["admin_status"] == "administrative"
        assert (e["rule_id"], e["is_eligible"]) == ("investable-v1", traded and not admin)
        assert e["reason"] == (None if e["is_eligible"] else
                               "no_price" if not traded else "administrative")  # fmt: skip
        letter = "T" if e["is_eligible"] else "F"
        runs[iid] = runs.get(iid, "") + ("" if runs.get(iid, " ")[-1:] == letter else letter)
    assert len(runs) == len(calendar)
    changed = [iid for iid, run in runs.items() if "FTF" in run]
    assert changed  # out, back in and out again, each change readable only at its close
    assert {e["reason"] for e in rows(small, "eligibility_daily")} == {
        None, "no_price", "administrative"}  # fmt: skip


def test_share_counts_follow_share_events(small: Path) -> None:
    bars, end = (
        by_bar(small, "bars"),
        max(r["session_date"] for r in rows(small, "calendar_sessions")),
    )
    days: dict[str, list[dt.date]] = {}
    for iid, day in sorted(bars):
        days.setdefault(iid, []).append(day)
    counts: dict[str, list[dict[str, Any]]] = {}
    for r in sorted(rows(small, "share_counts"), key=lambda r: r["as_of_date"]):
        counts.setdefault(r["instrument_id"], []).append(r)
    for iid, held in counts.items():
        kr = iid.startswith("KR:")
        assert {r["count_kind"] for r in held} == {"listed" if kr else "outstanding"}
        on = [bars[iid, days[iid][bisect.bisect_right(days[iid], r["as_of_date"]) - 1]]
              for r in held]  # the last bar on or before each count  # fmt: skip
        start = held[0]["shares"] * on[0]["cum_factor_split"]
        for r, bar in zip(held, on, strict=True):  # the first count moved by the share events
            moved = on[0]["cum_factor_split"] / bar["cum_factor_split"]  # since, fractions cut
            assert abs(r["shares"] - start / bar["cum_factor_split"]) < 1 + moved
            if kr:  # every session, known at its close
                assert (r["as_of_date"], r["ts_available"]) == (bar["session_date"], bar["ts_end"])
            else:  # each quarter's last day, filed 40 days later inside the period
                assert (r["as_of_date"] + dt.timedelta(1)).day == 1
                assert r["as_of_date"].month % 3 == 0
                assert r["ts_available"] == dt.datetime.combine(
                    r["as_of_date"] + dt.timedelta(40), dt.time(21), UTC)  # fmt: skip
                assert r["ts_available"].date() <= end
    assert sum(len(v) for k, v in counts.items() if k.startswith("KR:")) == sum(
        k[0].startswith("KR:") for k in bars)  # fmt: skip


def first_versions(package: Path) -> dict[tuple[str, dt.date], str]:
    return {(r["instrument_id"], r["ex_date"]): r["kind"]
            for r in rows(package, "corporate_actions") if r["revision_of"] is None}  # fmt: skip


def test_injected_event_overrides_random(tmp_path: Path, tiny: Path) -> None:
    # spec 4.8 EventSpec: on its day the injected event replaces that instrument's random one
    short: dict[str, Any] = {"markets": ("KR",), "start": dt.date(2019, 1, 2), "n_kr": 20}
    drawn = first_versions(make_snapshot(tmp_path / "a", **short))
    (iid, day) = next(key for key, kind in sorted(drawn.items()) if kind == "cash_dividend")
    split = {"dataset": "corporate_actions", "kind": "split", "instrument_id": iid,
             "ex_date": day.isoformat(), "ratio_new_per_old": 2.0}  # fmt: skip
    package = make_snapshot(tmp_path / "b", **short, events=[split])
    assert first_versions(package) == drawn | {(iid, day): "split"}  # the others as drawn
    (row,) = (r for r in rows(package, "corporate_actions") if r["instrument_id"] == iid
              and r["ex_date"] == day)  # fmt: skip
    assert (row["ratio_num"], row["ratio_den"], row["price_factor"]) == (2, 1, 0.5)
    assert a001(read(package, "corporate_actions"), read(package, "bars_1d")) == 0
    assert files_of(make_snapshot(tmp_path / "c", **short, events=[split])) == files_of(package)
    # tiny's hand-set bars move too, so A001 stays 0 there
    ex, cash = dt.date(2020, 2, 3), {"kind": "cash_dividend", "cash_per_share": 0.2}
    injected = [split | {"instrument_id": "KR:T00001", "ex_date": ex.isoformat()},
                split | cash | {"instrument_id": "US:T00002", "ex_date": ex,
                                "ts_announced": "2020-01-22T06:00:00+09:00"}]  # fmt: skip
    moved = make_snapshot(tmp_path / "t", preset="tiny", events=injected)
    assert a001(read(moved, "corporate_actions"), read(moved, "bars_1d")) == 0
    plain = {(b["instrument_id"], b["session_date"]): b for b in rows(tiny, "bars")}
    for b in (b for b in rows(moved, "bars") if b["instrument_id"] == "KR:T00001"):
        was = plain["KR:T00001", b["session_date"]]
        after = b["session_date"] >= ex
        assert (b["close"], b["cum_factor_split"]) == (was["close"] / (1 + after), 1 / (1 + after))
    (dividend,) = (r for r in rows(moved, "corporate_actions") if r["kind"] == "cash_dividend")
    assert dividend["pay_date"] == dividend["declared_date"] + dt.timedelta(30)
    assert (dividend["resolution_body"], dividend["ts_terms_available"]) == (None, None)
    assert dividend["ts_announced"] == dt.datetime(2020, 1, 21, 21, tzinfo=UTC)  # +09:00 read
    for wrong, error, words in (
        ({"dataset": "fundamentals_state"}, NotImplementedError, "not generated until M2"),
        ({"kind": "merger"}, ValueError, "kind one of"),
        ({"ex_date": "2020-01-25"}, ValueError, "a session of its listing"),
        ({"price_factor": 0.25}, ValueError, "derived columns .'price_factor'"),
        (cash | {"cash_per_share": 1e9}, ValueError, "cash_per_share must be in"),
        ({"ratio_new_per_old": -2.0}, ValueError, "ratio must be positive"),
        ({"ratio_num": -1, "ratio_den": 1}, ValueError, "ratio must be positive"),
        ({"dataset": "bars_1d"}, ValueError, "one of the spec 4.8 datasets"),
        ({"instrument_id": "ZZ:T00001"}, ValueError, "in no chosen market"),
    ):  # fmt: skip
        with pytest.raises(error, match=words):
            make_snapshot(tmp_path / "x", preset="tiny", events=[injected[0] | wrong])
    no_ratio = {c: v for c, v in injected[0].items() if c != "ratio_new_per_old"}
    for wrong_events, words in (([no_ratio], "ratio_num and ratio_den"), (injected[:1] * 2, "two")):
        with pytest.raises(ValueError, match=words):
            make_snapshot(tmp_path / "x", preset="tiny", events=wrong_events)
    for step in (events._cash, events._ratio, events.given, events.targets, synth._tiny_actions):
        assert not called_names(inspect.getsource(step)) & PLATFORM_MATH, step.__name__


def exit_agrees(package: Path, iid: str) -> dict[str, Any]:
    """`iid`'s one `delistings` row, after checking that its instrument row and bars agree."""
    (out,) = (r for r in rows(package, "delistings") if r["instrument_id"] == iid)
    (listed,) = (r for r in rows(package, "instruments") if r["instrument_id"] == iid)
    held = sorted((b for b in rows(package, "bars") if b["instrument_id"] == iid),
                  key=lambda b: b["session_date"])  # fmt: skip
    assert (listed["delisted_on"], listed["last_session"]) == (
        out["exit_date"], out["last_trading_date"])  # fmt: skip
    assert held[-1]["session_date"] == out["last_trading_date"] == out["ref_date"]
    assert held[-1]["close"] == out["ref_price"]
    assert "0 errors" in pkg._tds("check", str(package), "--level", "full").stdout
    assert a001(read(package, "corporate_actions"), read(package, "bars_1d")) == 0
    return out


def test_injected_delisting_ends_the_listing(tmp_path: Path) -> None:
    # #300, spec 4.8 EventSpec: no bar from the exit on, one delistings row with that exit
    exit_ = {"dataset": "delistings", "instrument_id": "KR:T00003", "exit_date": "2020-03-02"}
    out = exit_agrees(make_snapshot(tmp_path / "t", preset="tiny", events=[exit_]), "KR:T00003")
    assert (out["exit_date"], out["last_trading_date"]) == (
        dt.date(2020, 3, 2), dt.date(2020, 2, 28))  # fmt: skip
    assert out["delist_type"] == delist.EXIT_TYPE[out["exit_value_status"]]  # 4.8 (6) fills it
    early = exit_ | {ID: "KR:T00002", "exit_date": "2020-02-03"}  # before its ticker change
    renamed = make_snapshot(tmp_path / "r", preset="tiny", events=[early])
    spans = [(r["valid_from"], r["valid_to"]) for r in rows(renamed, "instrument_symbols")
             if r[ID] == "KR:T00002"]  # fmt: skip
    assert spans == [(dt.date(2020, 1, 2), exit_agrees(renamed, "KR:T00002")["exit_date"])]
    # small: the given columns as given, the rest by 4.8 (6); an exit later than the drawn one
    short: dict[str, Any] = {"markets": ("KR",), "start": dt.date(2019, 1, 2), "n_kr": 20}
    drawn = rows(make_snapshot(tmp_path / "a", **short), "delistings")
    iid = drawn[0]["instrument_id"]
    given = exit_ | {"instrument_id": iid, "exit_date": "2019-12-02", "ret_policy": -0.25,
                     "exit_value_status": "estimated",
                     "ts_exit_known": "2019-11-01T06:30"}  # fmt: skip
    out = exit_agrees(make_snapshot(tmp_path / "b", **short, events=[given]), iid)
    assert drawn[0]["exit_date"] < out["exit_date"] == dt.date(2019, 12, 2)
    assert (out["exit_value_status"], out["ret_policy"], out["delist_type"]) == (
        "estimated", -0.25, "performance")  # fmt: skip
    assert out["ts_exit_known"] == dt.datetime(2019, 11, 1, 6, 30, tzinfo=UTC)


ID = "instrument_id"


def clear_day(package: Path) -> tuple[str, dt.date]:
    """A traded KR bar that 4.8 (5) does not keep clear: not a listing's first or last, and
    not the session before an ex-date."""
    ex = {(r["instrument_id"], r["ex_date"]) for r in rows(package, "corporate_actions")}
    bars = sorted(rows(package, "bars"), key=lambda b: (b["instrument_id"], b["session_date"]))
    trios = zip(bars, bars[1:], bars[2:], strict=False)
    return next((b[ID], b["session_date"]) for a, b, c in trios
                if a[ID] == b[ID] == c[ID] and b["obs_status"] == c["obs_status"] == "traded"
                and (c[ID], c["session_date"]) not in ex)  # fmt: skip


def test_injected_halt_blanks_its_bar(tmp_path: Path) -> None:
    # #300: a full-day halt on a KR session, as 4.8 (5) makes them; ineligible that day (4.8 (10))
    short: dict[str, Any] = {"markets": ("KR",), "start": dt.date(2019, 1, 2), "n_kr": 20}
    iid, day = clear_day(make_snapshot(tmp_path / "a", **short))
    halt = {"dataset": "tradability_daily", ID: iid, "session_date": day.isoformat(),
            "halted_full_day": True}  # fmt: skip
    package = make_snapshot(tmp_path / "b", **short, events=[halt])
    on = {name: next(r for r in rows(package, name) if (r[ID], r["session_date"]) == (iid, day))
          for name in ("bars", "tradability_daily", "eligibility_daily")}  # fmt: skip
    bar = on["bars"]
    assert [bar[c] for c in ("obs_status", "open", "high", "low", "close", "volume")] == [
        "halted", None, None, None, None, 0.0]  # fmt: skip
    assert (on["tradability_daily"]["halted_full_day"], on["tradability_daily"]["halt_count"]) == (
        True, 0)  # fmt: skip
    assert (on["eligibility_daily"]["is_eligible"], on["eligibility_daily"]["reason"]) == (
        False, "no_price")  # fmt: skip
    assert "0 errors" in pkg._tds("check", str(package), "--level", "full").stdout
    assert a001(read(package, "corporate_actions"), read(package, "bars_1d")) == 0


def test_injected_exits_and_halts_are_refused_with_the_reason(tmp_path: Path) -> None:
    # #300 Decisions: what is not injected, and 4.8 (5)'s sessions kept free of halts
    exit_ = {"dataset": "delistings", ID: "KR:T00003", "exit_date": "2020-03-02"}
    halt = {"dataset": "tradability_daily", ID: "KR:T00003", "session_date": "2020-03-02",
            "halted_full_day": True}  # fmt: skip
    for spec, error, words, preset in (
        (exit_ | {"delist_type": "liquidation"}, ValueError, "liquidating distribution", "tiny"),
        (halt | {"limit_up_close": True}, NotImplementedError, "limit closes and admin_s", "small"),
        (halt | {"admin_status": "normal"}, NotImplementedError, "not injected yet", "small"),
        (halt, NotImplementedError, r"tiny writes no tradability_daily yet \(4.8 \(5\)\)", "tiny"),
        ({"dataset": "fundamentals_events"}, NotImplementedError, "not generated until M2", "tiny"),
        (exit_ | {"ref_price": 1.0}, ValueError, "derived or unknown .'ref_price'", "tiny"),
        (exit_ | {"exit_date": "2020-01-02"}, ValueError, "after its listing's first", "tiny"),
        (exit_ | {"exit_value_status": "seen"}, ValueError, "exit_value_status one of", "tiny"),
        (halt | {ID: "US:T00003"}, ValueError, "KR sessions only", "small"),
        (halt | {"halted_full_day": False}, ValueError, "halted_full_day = True", "small"),
    ):  # fmt: skip
        opts: dict[str, Any] = {"preset": preset}
        with pytest.raises(error, match=words):
            make_snapshot(tmp_path / "x", **opts, events=[spec])
    with pytest.raises(ValueError, match="two injected exits"):
        make_snapshot(tmp_path / "x", preset="tiny", events=[exit_, exit_])
    short: dict[str, Any] = {"markets": ("KR",), "start": dt.date(2019, 1, 2), "n_kr": 20}
    plain = make_snapshot(tmp_path / "a", **short)
    action = next(r for r in rows(plain, "corporate_actions") if r["status"] == "effective")
    before = max(b["session_date"] for b in rows(plain, "bars")
                 if b[ID] == action[ID] and b["session_date"] < action["ex_date"])  # fmt: skip
    gone = next(r for r in rows(plain, "instruments") if r["delisted_on"])
    for iid, day, words in (
        (action[ID], before, r"4.8 \(5\) keeps the session before an ex-date, whose close"),
        (gone[ID], gone["last_session"], r"4.8 \(5\) keeps a listing's last session free of"),
        (gone[ID], gone["delisted_on"], "session_date must be a session of its listing"),
    ):
        with pytest.raises(ValueError, match=words):
            make_snapshot(tmp_path / "b", **short,
                          events=[halt | {ID: iid, "session_date": day}])  # fmt: skip


SHORT: dict[str, Any] = {"start": dt.date(2019, 1, 2), "n_kr": 20, "n_us": 20}
CORE, MINIMAL = "tds:equity-daily-core@1.0", "tds:minimal-daily@1.0"
#: Spec 4.8's core `degrade` values; TDS 7: core needs calendar_sessions, delistings and dense
#: bars with OHLCV and obs_status, so these four cannot keep it, and the other three can.
DROPS_CORE = {"no_ohlc": True, "no_sessions": True, "sparse_bars": True, "no_cum_factors": False,
              "kr_ex_is_record": False, "us_div_split_adjusted_no_dates": False,
              "no_delistings": True, "no_tick_info": False,  # F-15: market_rules is optional
              "late_bars": False}  # #354: no gap of the 4.5 table, valid data  # fmt: skip


@pytest.fixture(scope="module")
def us_dividend_before_split(tmp_path_factory: pytest.TempPathFactory) -> list[dict[str, Any]]:
    """A US cash dividend injected 5 sessions before the first drawn US split, of the same
    instrument, so a split-adjusted amount differs from the raw one."""
    plain = make_snapshot(tmp_path_factory.mktemp("plain") / "p", **SHORT)
    split = next(r for r in rows(plain, "corporate_actions")
                 if r[ID].startswith("US:") and r["kind"] == "split")  # fmt: skip
    days = sorted(b["session_date"] for b in rows(plain, "bars") if b[ID] == split[ID])
    day = days[days.index(split["ex_date"]) - 5]
    return [{"dataset": "corporate_actions", "kind": "cash_dividend", ID: split[ID],
             "ex_date": day.isoformat(), "cash_per_share": 0.5}]  # fmt: skip


def check_full(package: Path) -> str:
    done = pkg._tds("check", str(package), "--level", "full")
    assert done.returncode == 0, done.stdout + done.stderr
    assert re.search(r"\b0 errors\b", done.stdout), done.stdout
    return done.stdout


@pytest.mark.parametrize("value", list(DROPS_CORE))
def test_synth_conforms_degraded_core(
    value: str, tmp_path: Path, us_dividend_before_split: list[dict[str, Any]]
) -> None:
    # spec 4.8, INV-17: each degraded package passes the full check with what it declares,
    # and holds the one gap of the 4.5 table its value names
    package = make_snapshot(tmp_path / value, **SHORT, events=us_dividend_before_split,
                            degrade=[value])  # fmt: skip
    printed = check_full(package)
    manifest = json.loads((package / "tds.json").read_text(encoding="utf-8"))
    kinds = {d["kind"]: d for d in manifest["datasets"]}
    bars = read(package, "bars_1d")
    actions = rows(package, "corporate_actions")
    dividends = [r for r in actions if r["kind"] == "cash_dividend"]
    if value == "no_ohlc":  # F-01
        assert all(bars[c].null_count == len(bars) for c in ("open", "high", "low"))
        assert bars["close"].null_count < len(bars)
    elif value == "no_sessions":  # F-02
        assert "calendar_sessions" not in kinds
    elif value == "sparse_bars":  # F-03: rows only where it traded, no obs_status
        assert kinds["bars"]["params"]["density"] == "sparse"
        assert "obs_status" not in bars.column_names
        assert bars["close"].null_count == 0
    elif value == "no_cum_factors":  # F-04
        assert not {"cum_factor_split", "cum_factor_total"} & set(bars.column_names)
    elif value == "kr_ex_is_record":  # F-05: every KR cash dividend, none elsewhere
        kr = [r for r in dividends if r[ID].startswith("KR:")]
        assert kr
        assert all(r["record_date"] == r["ex_date"] for r in kr)
        assert all(r["record_date"] != r["ex_date"] for r in dividends if r not in kr)
    elif value == "us_div_split_adjusted_no_dates":  # F-09
        us = [r for r in dividends if r[ID].startswith("US:")]
        assert us
        assert all(r["pay_date_status"] == "missing" for r in us)
        for c in ("record_date", "declared_date", "pay_date", "resolution_date"):
            assert all(r[c] is None for r in us), c
        injected = us_dividend_before_split[0]
        (given,) = (r for r in us if r[ID] == injected[ID]
                    and r["ex_date"].isoformat() == injected["ex_date"])  # fmt: skip
        assert given["cash_per_share"] < 0.5  # divided by the later split's ratio
        assert re.search(r"TDS-A004\b", printed), printed  # the warning F-09 counts
    elif value == "late_bars":  # 5.1.2's column rule with no ready_delay, so delta = 0
        assert kinds["bars"]["availability"] == {"column": "ts_available"}
        assert "ready_delay" not in kinds["bars"]["params"]
        assert pc.sum(pc.greater(bars["ts_available"], bars["ts_end"])).as_py() > 0
    elif value == "no_tick_info":  # F-15: no grid information anywhere, the prices as they were
        assert "market_rules" not in kinds
        assert "tick_rule_id" not in rows(package, "instruments")[0]
        plain = make_snapshot(tmp_path / "plain", **SHORT, events=us_dividend_before_split)
        assert "market_rules" in {d["kind"] for d in json.loads(
            (plain / "tds.json").read_text(encoding="utf-8"))["datasets"]}  # fmt: skip
        assert bars.equals(read(plain, "bars_1d"))
    else:  # F-13: instruments still say they left, with no delistings to say how
        assert "delistings" not in kinds
        assert any(r["delisted_on"] for r in rows(package, "instruments"))
    assert (CORE in manifest["profiles"]) is not DROPS_CORE[value]
    assert MINIMAL in manifest["profiles"]
    # the generator's own A001 agrees, also across the halted days sparse bars leave out
    assert a001(read(package, "corporate_actions"), bars) == (
        None if value == "no_cum_factors" else 0)  # fmt: skip


def validate_short(monkeypatch: pytest.MonkeyPatch, out: Path, *more: str) -> None:
    """The command with `--validate` on `small` cut to SHORT's year and counts."""
    short = synth.PRESETS["small"]._replace(start=SHORT["start"], counts={"KR": 20, "US": 20})
    monkeypatch.setitem(synth.PRESETS, "small", short)
    assert main(["--preset", "small", "--out", str(out), "--validate", *more]) == 0


def test_exact_ratios_present(
    small: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # 4.8 (4) [V31-01]: every share event has its exact ratio, the others none
    actions = rows(small, "corporate_actions")
    shares = [r for r in actions if r["kind"] in acts.SHARE_EVENTS]
    ratios = {(r["ratio_num"], r["ratio_den"]) for r in shares}
    assert {(7, 1), (1, 3), (129, 100)} <= ratios  # 1/7, 1/3 and 1.29: no binary fraction
    for r in shares:  # the f64 columns are the quotient (TDS 5.11), so no A010
        assert r["share_factor"] == r["ratio_num"] / r["ratio_den"]
        new_per_old = r["share_factor"] - (r["kind"] == "bonus_issue")
        assert r["ratio_new_per_old"] == pytest.approx(new_per_old, rel=1e-12)
    assert all((r["ratio_num"], r["ratio_den"]) == (None, None) for r in actions
               if r not in shares)  # fmt: skip
    printed = check_full(small)
    assert warned(printed, "A011") == 0  # [V31-04]: every distribution's exit says if it counts
    # the done line, on a short `small`: the counts are those of the rows it wrote
    validate_short(monkeypatch, tmp_path / "cli")
    written = rows(tmp_path / "cli", "corporate_actions")
    last = {r[ID]: r["last_trading_date"] for r in rows(tmp_path / "cli", "delistings")}
    n = sum(r["ratio_num"] is not None for r in written)
    k = sum(r["kind"] == "return_of_capital" and r["ex_date"] > last[r[ID]] for r in written)
    assert n > 0
    assert k > 0
    line = f"exact ratios: {n}, distributions before delisting: {k}, off-grid rows: 0"
    assert line in capsys.readouterr().out.splitlines()
    assert main(["--preset", "tiny", "--out", str(tmp_path / "tiny"), "--validate"]) == 0
    line = "exact ratios: 0, distributions before delisting: 0, off-grid rows: no grid information"
    assert line in capsys.readouterr().out.splitlines()


def test_volume_in_lots_triggers_V011(  # noqa: N802 - the ticket's test name
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # 4.8 (3), (11a), F-16 [V31-16]: value traded in shares, KR volume in lots of 100
    plain = make_snapshot(tmp_path / "plain", **SHORT)
    bars = read(plain, "bars_1d").to_pylist()
    for b in bars:
        halted = b["obs_status"] == "halted"
        typical = 0.0 if halted else (b["high"] + b["low"] + b["close"]) / 3
        assert b["value_traded"] == pytest.approx(b["volume"] * typical, rel=1e-12), b
    printed = check_full(plain)
    assert warned(printed, "V011") == 0
    assert "volume unit unverified" not in printed
    package = make_snapshot(tmp_path / "lots", **SHORT, degrade=["volume_in_lots"])
    for b, lot in zip(bars, read(package, "bars_1d").to_pylist(), strict=True):
        kr = b[ID].startswith("KR:")  # whole lots, the odd shares dropped; nothing else moves
        assert lot == b | {"volume": float(b["volume"] // 100) if kr else b["volume"]}, b
    printed = check_full(package)
    traded = {b[ID] for b in bars if b[ID].startswith("KR:") and b["volume"] >= 100}
    assert warned(printed, "V011") == len(traded) > 0  # one per KR instrument and year
    assert "hint: volume may be in lots" in printed
    assert CORE in json.loads((package / "tds.json").read_text(encoding="utf-8"))["profiles"]
    # the done line: the command names the count, 0 without the value
    validate_short(monkeypatch, tmp_path / "cli", "--degrade", "volume_in_lots")
    assert f"TDS-V011 warnings: {len(traded)}" in capsys.readouterr().out.splitlines()
    validate_short(monkeypatch, tmp_path / "cli")
    assert "TDS-V011 warnings: 0" in capsys.readouterr().out.splitlines()
    # no count where the checker could not judge (no high or low), and the distributions are
    # still counted without `delistings`
    validate_short(monkeypatch, tmp_path / "cli", "--degrade", "no_ohlc,no_delistings")
    printed = capsys.readouterr().out
    assert "TDS-V011 warnings" not in printed
    assert "note: TDS-V011 not checked" in printed
    written = rows(tmp_path / "cli", "corporate_actions")
    paid = sum(r["kind"] == "return_of_capital" for r in written)
    assert f"distributions before delisting: {paid}, " in printed
    assert paid > 0


def test_late_bars_variant_has_late_bars_in_an_overlap_tail(tmp_path: Path) -> None:
    # #354, spec 4.8 (3a): the rows a property test needs to reach 5.1.2's visibility rule
    two_years: dict[str, Any] = SHORT | {"start": dt.date(2018, 1, 2)}
    package = make_snapshot(tmp_path / "late", **two_years, degrade=["late_bars"])
    closes = [r["ts_close"] for r in rows(package, "calendar_sessions")
              if r["calendar_id"] == "XKRX"]  # fmt: skip
    ready = {c.date(): k for k, c in enumerate(closes)}  # KR closes on its session's UTC day
    bars = read(package, "bars_1d").to_pylist()
    kr = [b for b in bars if b[ID].startswith("KR:")]
    # sessions from ready(s) to ts_available: 0 on time, never negative, 1 to 3 when late
    lag = [closes.index(b["ts_available"]) - ready[b["session_date"]] for b in kr]
    assert set(lag) == {0, 1, 2, 3}
    late = sum(k > 0 for k in lag)
    assert 0.004 < late / len(kr) < 0.007, late  # about 0.5%
    assert all(b["ts_available"] == b["ts_end"] for b in bars if not b[ID].startswith("KR:"))
    # the last 20 rows of the 2018 partition hold a late bar, which 2019's rows wait for
    tail = pq.read_table(package / "bars/freq=1d/market=KR/year=2018/part-00000.parquet")
    tail = tail.slice(tail.num_rows - 20).to_pylist()
    assert any(b["ts_available"].year == 2019 for b in tail)
    # no other value differs from the package without the value, and it is byte-identical
    plain = make_snapshot(tmp_path / "plain", **two_years)
    assert read(package, "bars_1d").drop_columns(["ts_available"]).equals(read(plain, "bars_1d"))
    again = make_snapshot(tmp_path / "again", **two_years, degrade=["late_bars"])
    assert files_of(again) == files_of(package)
    other = make_snapshot(tmp_path / "seed", **two_years, seed=1, degrade=["late_bars"])
    assert read(other, "bars_1d")["ts_available"] != read(package, "bars_1d")["ts_available"]


def test_command_names_the_late_bar_count(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # #354's "what should happen", on tiny: 341 KR bars, 323 of them with 3 sessions after
    out = tmp_path / "cli"
    assert main(["--preset", "tiny", "--out", str(out), "--degrade", "late_bars",
                 "--validate"]) == 0  # fmt: skip
    printed = capsys.readouterr().out
    assert "late bars 2\n" in printed  # round(0.005 x 323)
    assert re.search(r"\b0 errors\b", printed)
    (entry,) = (d for d in json.loads((out / "tds.json").read_text(encoding="utf-8"))["datasets"]
                if d["kind"] == "bars")  # fmt: skip
    assert entry["availability"] == {"column": "ts_available"}


def test_degrade_drops_declared_profiles(tmp_path: Path) -> None:
    # spec 4.8: a value drops the profiles it cannot keep, and only those
    tiny: dict[str, Any] = {"preset": "tiny", "markets": ("KR",)}
    both = make_snapshot(tmp_path / "two", **tiny, degrade=["no_cum_factors", "no_delistings"])
    assert json.loads((both / "tds.json").read_text(encoding="utf-8"))["profiles"] == [MINIMAL]
    # counter-example: declared again, core fails the check where the checker sees the gap
    missing = {"no_sessions": "dataset calendar_sessions", "no_delistings": "dataset delistings",
               "sparse_bars": "density=dense",
               "no_ohlc": "column open in bars: null in every row"}  # fmt: skip  # OHLCV (#352)
    for value in (v for v, drops in DROPS_CORE.items() if drops):
        package = make_snapshot(tmp_path / value, **tiny, degrade=[value])
        check_full(package)
        path = package / "tds.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        assert manifest["profiles"] == [MINIMAL]
        path.write_text(json.dumps(manifest | {"profiles": [MINIMAL, CORE]}), encoding="utf-8")
        assert pkg._tds("hash", str(package), "--write").returncode == 0
        done = pkg._tds("check", str(package), "--level", "full")
        assert done.returncode != 0
        said = rf"^error TDS-M008(?: bars_1d)?: {re.escape(CORE)} requires .*"
        assert re.search(said + re.escape(missing[value]), done.stdout, re.M), done.stdout
    for wrong, error, words in (
        (["no_eligibility"], NotImplementedError, r"come with T0.16b \(spec"),
        (["no_ohlcv"], ValueError, "spec 4.8 has"),
        ("no_ohlc", ValueError, "a sequence of values"),
    ):  # fmt: skip
        with pytest.raises(error, match=words):
            make_snapshot(tmp_path / "x", **tiny, degrade=wrong)


def manifest_of(package: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """A package's `markets` and its datasets by name."""
    manifest = json.loads((package / "tds.json").read_text(encoding="utf-8"))
    return manifest["markets"], {d["name"]: d for d in manifest["datasets"]}


def unchecked(package: Path) -> list[str]:
    """The codes `tds check --level full` leaves unchecked, on a package without an error."""
    done = pkg._tds("check", str(package), "--level", "full", "--format", "json")
    summary = json.loads(done.stdout)["summary"]
    assert summary["errors"] == 0, done.stdout
    return list(summary["unchecked"])


def test_small_watermark_is_each_markets_last_session(small: Path) -> None:
    # #390, TDS 3.8: a synthetic package is complete through its period's last session
    markets, _ = manifest_of(small)
    sessions = rows(small, "calendar_sessions")
    assert set(markets) == {"KR", "US", "ZZ"}
    for market, entry in markets.items():
        last = max((r for r in sessions if r["calendar_id"] == entry["calendar_id"]),
                   key=lambda r: r["session_date"])  # fmt: skip
        assert entry["complete_through_session"] == last["session_date"].isoformat(), market
        assert dt.datetime.fromisoformat(entry["complete_through"]) == last["ts_close"], market
    assert markets["KR"]["complete_through"] == "2019-12-30T06:30:00Z"  # TDS 4.2's form


def test_small_coverage_matches_the_rows(small: Path) -> None:
    # #390, TDS 4.3: the keys of 4.2's example, counted here from the rows
    _, datasets = manifest_of(small)
    for name in ("bars_1d", "tradability_daily", "eligibility_daily"):
        table, coverage = read(small, name), datasets[name]["coverage"]
        low, high = pc.min_max(table["session_date"]).as_py().values()
        assert coverage["instruments"] == pc.count_distinct(table[ID]).as_py() == 420, name
        assert (coverage["ts_min"], coverage["ts_max"]) == (low.isoformat(), high.isoformat())
        assert set(coverage["by_market"]) == {"KR", "US", "ZZ"}
        for market, said in coverage["by_market"].items():  # ids are `KR:T00001`
            part = table.filter(pc.equal(pc.utf8_slice_codeunits(table[ID], 0, 2), market))
            first, last = pc.min_max(part["session_date"]).as_py().values()
            assert said == {"instruments": pc.count_distinct(part[ID]).as_py(),
                            "first": first.isoformat(), "last": last.isoformat(),
                            "rows": part.num_rows}, (name, market)  # fmt: skip
    # a dataset without `market=` partitions has no `by_market`; a key needs its column
    assert datasets["instruments"]["coverage"] == {"instruments": 420}
    assert datasets["calendar_sessions"]["coverage"] == {"ts_min": "2015-01-02",
                                                         "ts_max": "2019-12-31"}  # fmt: skip
    assert "coverage" not in datasets["market_rules"]


def test_full_check_judges_d001_on_small(small: Path) -> None:
    # #390: every instrument's dense bars are judged to its last session or the watermark,
    # and D004 compares the coverage. T006 is judged on the bars and stays unchecked for the
    # datasets TDS 8.2 cannot judge from statistics (#192).
    left = unchecked(small)
    assert "TDS-D001" not in left
    assert "TDS-D004" not in left


def test_full_check_judges_k002_on_small(small: Path) -> None:
    # #412: the three datasets TDS 5.3, 5.14 and 5.20 left without a sort declare the one the
    # generator writes them in, so K002 judges every dataset of small
    _, datasets = manifest_of(small)
    assert datasets["instrument_xref"]["sort"] == [ID, "id_type", "id_value", "valid_from"]
    assert datasets["share_counts"]["sort"] == [ID, "count_kind", "as_of_date", "ts_available"]
    assert datasets["eligibility_daily"]["sort"] == ["session_date", ID, "rule_id"]
    assert "TDS-K002" not in unchecked(small)


def test_k002_takes_the_schema_files_sort_when_tds_json_has_none(tmp_path: Path) -> None:
    # #412: the three schema files carry the sort TDS states, so a manifest that leaves it out
    # is judged too; a cut-down small, which has share_counts and eligibility_daily
    package = make_snapshot(tmp_path / "bare", preset="small", end=dt.date(2015, 6, 30),
                            n_kr=8, n_us=8)  # fmt: skip
    path = package / "tds.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    names = {d["name"] for d in manifest["datasets"]}
    assert {"instrument_xref", "share_counts", "eligibility_daily"} <= names
    for dataset in manifest["datasets"]:
        dataset.pop("sort", None)
    path.write_text(json.dumps(manifest), encoding="utf-8")
    assert "TDS-K002" not in unchecked(package)


def test_tiny_has_the_watermark_and_coverage_too(tiny: Path) -> None:
    # #390 "Not sure yet", decided with the owner: tiny takes the same path as small
    markets, datasets = manifest_of(tiny)
    through = {"complete_through_session": "2020-03-31", "complete_through": "2020-03-31T20:00:00Z"}
    assert markets["US"] == synth.MARKETS["US"] | through
    kr = [r for r in rows(tiny, "bars") if r[ID].startswith("KR:")]
    assert datasets["bars_1d"]["coverage"]["by_market"]["KR"] == {
        "instruments": 6, "first": "2020-01-02", "last": "2020-03-31", "rows": len(kr)}  # fmt: skip
    assert "TDS-D001" not in unchecked(tiny)


def test_coverage_of_a_wrong_count_fails_d004(tiny: Path, tmp_path: Path) -> None:
    # counter-example: the checker does compare what the generator declares
    package = make_snapshot(tmp_path / "wrong", preset="tiny")
    path = package / "tds.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    (bars,) = (d for d in manifest["datasets"] if d["name"] == "bars_1d")
    bars["coverage"]["by_market"]["KR"]["rows"] += 1
    path.write_text(json.dumps(manifest), encoding="utf-8")
    done = pkg._tds("check", str(package), "--level", "full")
    assert done.returncode != 0
    assert "TDS-D004" in done.stdout
