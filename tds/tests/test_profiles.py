"""TDS 7, 8.2: the profile table `PROFILES`, and a profile's three results, never a false pass."""

from __future__ import annotations

from pathlib import Path

from nexusbt_tds import PROFILES, ProfileStatus, check
from nexusbt_tds.profiles import profile_id

from .conformance_build import build

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


def test_profile_three_results(tmp_path: Path) -> None:
    package = Path(build.write(tmp_path, *build.base()))  # declares tds:minimal-daily@1.0
    asked = ["tds:minimal-daily", "tds:equity-daily-core@1.0", "tds:no-such@1.0"]
    result = check(package, level="manifest", profiles=asked)
    assert result.profiles == {
        "tds:minimal-daily@1.0": ProfileStatus(True, "manifest", "not_checked"),
        # not declared: checked anyway, and it lacks calendar_sessions and two more (M008)
        "tds:equity-daily-core@1.0": ProfileStatus(False, "manifest", "fail"),
        "tds:no-such@1.0": ProfileStatus(False, "none", "fail"),  # M007
    }
    assert sorted({f.code for f in result.errors}) == ["TDS-M007", "TDS-M008"]
    by_default = check(package, level="manifest")  # without profiles: the declared ones
    assert list(by_default.profiles) == ["tds:minimal-daily@1.0"]


def test_manifest_level_never_reports_unchecked_as_pass(tmp_path: Path) -> None:
    package = Path(build.write(tmp_path, *build.base()))  # meets tds:minimal-daily at this level
    met = [name for name, p in PROFILES.items() if name.startswith("tds:minimal") or not p.requires]
    result = check(package, level="manifest", profiles=met)
    assert (result.errors, result.warnings) == ((), ())
    assert {s.result for s in result.profiles.values()} == {"not_checked"}
    assert {"TDS-K001", "TDS-S001", "TDS-H001", "TDS-A001"} <= set(result.unchecked)
    assert not [c for c in result.unchecked if c.startswith("TDS-M0") and c < "TDS-M015"]
    summary = result.summary()
    assert summary["level"] == "manifest"
    assert "pass" not in str(summary["profiles"])


def test_a_package_error_fails_every_profile(tmp_path: Path) -> None:
    (tmp_path / "tds.json").write_text("{not json", encoding="utf-8")
    result = check(tmp_path, level="manifest", profiles=["tds:minimal-daily@1.0"])
    assert [f.code for f in result.errors] == ["TDS-M001"]
    assert result.profiles["tds:minimal-daily@1.0"] == ProfileStatus(False, "manifest", "fail")
