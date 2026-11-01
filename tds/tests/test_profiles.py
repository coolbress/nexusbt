"""TDS 7: the profile table `PROFILES`, keyed `tds:<name>@<MAJOR.MINOR>`."""

from __future__ import annotations

from nexusbt_tds import PROFILES
from nexusbt_tds.profiles import profile_id

#: TDS 7, the profile column of the table, in its order (`tds:fx` and `tds:alt-events` without `@`).
CHAPTER_7 = (
    "minimal-daily equity-daily-core equity-daily-research panels pit-fundamentals bitemporal"
    " intraday-bars l1-ticks l2-book l3-book futures options crypto fx alt-events"
)


def test_every_chapter_7_profile_is_in_the_table() -> None:
    assert list(PROFILES) == [f"tds:{name}@1.0" for name in CHAPTER_7.split()]


def test_a_name_without_version_means_1_0() -> None:
    assert profile_id("tds:minimal-daily") == "tds:minimal-daily@1.0"
    assert profile_id("tds:panels@1.1") == "tds:panels@1.1"


def test_core_stacks_on_minimal_with_raw_dense_daily_bars() -> None:
    minimal, core = PROFILES["tds:minimal-daily@1.0"], PROFILES["tds:equity-daily-core@1.0"]
    assert minimal.requires == ((("instruments", ()),), (("bars", (("freq", "1d"),)),))
    raw_dense = ("bars", (("freq", "1d"), ("price_basis", "raw"), ("density", "dense")))
    assert core.requires[:2] == ((("instruments", ()),), (raw_dense,))
    assert [group[0][0] for group in core.requires[2:]] == [
        "calendar_sessions",
        "corporate_actions",
        "delistings",
    ]


def test_research_needs_fx_rates_only_with_more_than_one_market() -> None:
    research = PROFILES["tds:equity-daily-research@1.0"]
    assert research.requires_multi_market == ((("fx_rates", ()),),)
    assert ("dictionary/columns", ()) in {need for group in research.requires for need in group}


def test_alternatives_and_experimental_status() -> None:
    l2 = PROFILES["tds:l2-book@1.0"]
    assert l2.requires == ((("book_deltas", (("depth_kind", "mbp"),)), ("book_snapshots", ())),)
    assert l2.status == "experimental"
    assert PROFILES["tds:minimal-daily@1.0"].status == "stable"
