"""Spec T0.5b, the market rules packs' seed tables (4.7); expected rows are the 4.7 text."""

from __future__ import annotations

from pathlib import Path

import pytest

from nexusbt.config.packs import SEEDS, Row, in_effect, rule_listing, scope, seed

BANS = "shorting/kr_short_bans_v1.csv"
KR_TICKS, US_TICKS = "ticks/kr_tick_table_v1.csv", "ticks/us_tick_table_v1.csv"


def test_ban_table_scope_grammar() -> None:
    assert scope("all") == ("all", ())
    assert scope("index:KOSPI200,KOSDAQ150") == ("index", ("KOSPI200", "KOSDAQ150"))
    assert scope("classification:is_financial=true") == ("classification", ("is_financial", "true"))
    for bad in ["", "ALL", "index:", "index:a,", "classification:x", "sector:bank"]:
        with pytest.raises(ValueError, match="scope"):
            scope(bad)
    rows = seed(BANS)
    assert [scope(r["scope"])[0] for r in rows] == ["all", "classification"] + ["all"] * 4
    partial = [r for r in rows if r["valid_from"] == "2021-05-03"]
    assert [r["except_universe_ids"] for r in partial] == ["index:KOSPI200,index:KOSDAQ150"]


def test_ban_intervals_half_open() -> None:
    bans = seed(BANS)
    # [2008-10-01, 2009-06-01): the end date is the first day shorts are allowed again
    assert [r["scope"] for r in in_effect(bans, "2009-05-31")] == ["all"]
    financial = ["classification:is_financial=true"]
    assert [r["scope"] for r in in_effect(bans, "2009-06-01")] == financial
    assert in_effect(bans, "2008-09-30") == []
    assert len(in_effect(bans, "2008-10-01")) == 1
    assert in_effect(bans, "2025-03-31") == []  # full resumption on 3.31 (FSC 2025-03-21)
    assert len(in_effect(bans, "2025-03-30")) == 1
    open_ended = [{"valid_from": "", "valid_to": ""}]  # an empty bound is unbounded
    assert in_effect(open_ended, "1900-01-01") == open_ended


def tick(rows: list[Row], day: str, group: str, price: float) -> float:
    """The one row's tick for `price` in `group` on `day`; bands are [price_from, price_to)."""
    found = [
        float(r["tick"])
        for r in in_effect(rows, day)
        if r["venue_group"] == group
        and float(r["price_from"]) <= price < float(r["price_to"] or "inf")
    ]
    assert len(found) == 1, (day, group, price, found)
    return found[0]


def test_etf_venue_group_tick() -> None:
    kr = seed(KR_TICKS)
    for day in ["2015-01-02", "2023-01-25", "2026-10-30"]:
        for price in [500, 1_999, 4_000, 60_000, 300_000, 700_000]:
            assert tick(kr, day, "ETF", price) == 5  # ETF, ETN, ELW: 5 won at every band
    etf = [r for r in kr if r["venue_group"] == "ETF"]
    assert {r["verified"] for r in etf} == {"true"}
    # the 2023-01-25 table, common to KOSPI, KOSDAQ and KONEX
    bands = {1_999: 1, 2_000: 5, 19_999: 10, 20_000: 50, 199_999: 100, 499_999: 500, 500_000: 1000}
    assert {p: tick(kr, "2023-01-25", "*", p) for p in bands} == bands
    assert tick(kr, "2023-01-24", "KOSPI", 1_999) == 5  # the old table: 5 won from 1,000 won
    assert tick(kr, "2023-01-24", "KOSDAQ", 600_000) == 100
    assert tick(kr, "2010-10-01", "KOSPI", 999) == 5  # no 1-won band before 2010-10-04


def test_us_pre_decimal_rows() -> None:
    us = seed(US_TICKS)
    assert tick(us, "1997-06-23", "*", 20) == 1 / 8
    for group in ["NYSE", "NASDAQ"]:
        assert tick(us, "1997-06-24", group, 20) == 1 / 16
    assert tick(us, "2001-01-29", "NYSE", 20) == 0.01  # decimalisation is per market
    assert tick(us, "2001-04-08", "NASDAQ", 20) == 1 / 16
    assert tick(us, "2001-04-09", "NASDAQ", 20) == 0.01
    assert tick(us, "2026-10-30", "NYSE", 0.5) == 0.0001  # Reg NMS Rule 612 below $1
    fractions = [r for r in us if float(r["tick"]) in (1 / 8, 1 / 16)]
    assert len(fractions) == 3
    assert {r["verified"] for r in fractions} == {"false"}
    assert {r["verified"] for r in us if r not in fractions} == {"true"}


def test_seed_tables_marked_unverified() -> None:
    tables = {name: seed(name) for name in SEEDS}  # every row has a source and a verified flag
    limits = tables["limits/kr_price_limits_v1.csv"]
    assert {r["verified"] for r in limits} == {"false"}  # all secondary evidence (R7-06)
    kospi = [(r["valid_from"], r["limit_ratio"]) for r in limits if r["market"] == "KOSPI"]
    assert kospi == [("1995-04-01", "0.06"), ("1996-11-25", "0.08"), ("1998-03-02", "0.12"),
                     ("1998-12-07", "0.15"), ("2015-06-15", "0.30")]  # fmt: skip
    assert in_effect(limits, "1995-03-31") == []  # fixed amounts before then: no row
    assert [r["limit_ratio"] for r in limits if r["market"] == "KONEX"] == ["0.15"]
    # costs: no seed values yet (OI-03), so `realistic` finds no verified row and stops (E23)
    assert tables["costs/default_v1.csv"] == tables["costs/venue_groups_v1.csv"] == []
    kr = tables[KR_TICKS]
    kosdaq_top = [r for r in kr if r["venue_group"] == "KOSDAQ" and r["price_from"] == "500000"]
    assert [r["verified"] for r in kosdaq_top] == ["false"]  # disagrees with the broker table
    assert {r["verified"] for r in kr if r["valid_to"] == "2010-10-04"} == {"false"}


def test_rule_listing_has_source_and_verified() -> None:
    applied = {
        BANS: in_effect(seed(BANS), "2021-06-01"),
        KR_TICKS: in_effect(seed(KR_TICKS), "2009-01-02"),
    }
    listing = rule_listing(applied)
    assert [(e.table, e.valid_from, e.valid_to) for e in listing.rows][:1] == [
        (BANS, "2021-05-03", "2023-11-06")
    ]
    assert all(e.source.startswith("https://") for e in listing.rows)
    # 1 ban row (verified) + 10 pre-2010 tick rows (KOSPI 6, KOSDAQ 4) and 1 ETF row
    assert (listing.unverified, listing.total) == (10, 12)
    assert listing.ratio == "10/12"
    assert "verified = false: 10/12" in str(listing)
    assert rule_listing({}).ratio == "0/0"


def test_broken_seed_rows_are_refused(tmp_path: Path) -> None:
    head = "valid_from,valid_to,scope,except_universe_ids,source,verified\n"
    (tmp_path / "shorting").mkdir()
    for row, what in [
        ("2020-01-01,2021-01-01,all,,s,yes", "verified"),
        ("2020-01-01,2021-01-01,all,,,true", "no source"),
        ("2021-01-01,2020-01-01,all,,s,true", "half-open"),
        ("2020-01-01,2020-01-01,all,,s,true", "half-open"),
        ("2020-01-01,,all,KOSPI200,s,true", "except_universe_ids"),
        ("2020-01-01,,every,,s,true", "scope"),
    ]:
        (tmp_path / BANS).write_text(head + row + "\n", encoding="utf-8")
        with pytest.raises(ValueError, match=what):
            seed(BANS, tmp_path)
    (tmp_path / BANS).write_text("valid_from,scope,source,verified\n", encoding="utf-8")
    with pytest.raises(ValueError, match="columns"):
        seed(BANS, tmp_path)
