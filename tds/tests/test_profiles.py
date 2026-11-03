"""TDS 7, 8.2: the profile table `PROFILES`, and a profile's three results, never a false pass."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

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
    daily = ("bars", (("freq", "=1d"), ("price_basis", "")))  # "" : declared, any value
    assert minimal.requires == (((("instruments", ()),),), ((daily,),))
    raw_dense = ("bars", (("freq", "=1d"), ("price_basis", "=raw"), ("density", "=dense")))
    assert core.requires[:2] == (((("instruments", ()),),), ((raw_dense,),))
    assert [group[0][0][0] for group in core.requires[2:]] == [
        "calendar_sessions",
        "corporate_actions",
        "delistings",
    ]


def test_research_needs_fx_rates_only_with_more_than_one_market() -> None:
    research = PROFILES["tds:equity-daily-research@1.0"]
    assert research.requires_multi_market == (((("fx_rates", ()),),),)
    assert (("dictionary/columns", ()),) in {alt for group in research.requires for alt in group}


def test_alternatives_and_experimental_status() -> None:
    l2 = PROFILES["tds:l2-book@1.0"]
    mbp = ("book_deltas", (("depth_kind", "=mbp"),))
    assert l2.requires == (((mbp,), (("book_snapshots", ()),)),)
    together = (("instruments", ()), ("bars", ()))  # TDS 7: `instruments(fx_spot)` + bars
    assert PROFILES["tds:fx@1.0"].requires == (((("fx_rates", ()),), together),)
    assert l2.status == "experimental"
    assert PROFILES["tds:minimal-daily@1.0"].status == "stable"


def test_a_typo_in_the_profile_table_fails_loudly() -> None:
    # a condition the table cannot read must not drop out and loosen the profile
    from nexusbt_tds.profiles import _needs

    with pytest.raises(ValueError, match="Freq"):
        _needs("bars:Freq=1d")


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


def _m008(tmp_path: Path, profile: str, change: Callable[[dict[str, Any]], object]) -> list[str]:
    manifest, files = build.base()
    change(manifest)
    package = Path(build.write(tmp_path, manifest, files))
    result = check(package, level="manifest", profiles=[profile])
    return [f.message for f in result.errors if f.code == "TDS-M008"]


def _bars_params(**params: str) -> Callable[[dict[str, Any]], object]:
    return lambda m: build.bars(m).update(params=params, path="bars")


def _add(kind: str) -> Callable[[dict[str, Any]], object]:
    entry = {"name": kind, "kind": kind, "schema_version": "1.0", "path": kind, "files": []}
    return lambda m: m["datasets"].append(dict(entry))


@pytest.mark.parametrize(
    ("freq", "met"),
    [(f, True) for f in ("1h", "30m", "1s", "23h")]
    + [(f, False) for f in ("1d", "24h", "1440m", "0h", "1w", "1mo", "1 h", "")],
)
def test_intraday_bars_need_bars_under_one_day(freq: str, met: bool, tmp_path: Path) -> None:
    # TDS 7 `bars(freq<1d)`; #80 Decisions: `<n>h`, `<n>m` or `<n>s` under one day
    def change(m: dict[str, Any]) -> None:
        _add("calendar_sessions")(m)
        _bars_params(freq=freq)(m)

    found = _m008(tmp_path, "tds:intraday-bars@1.0", change)
    assert found == ([] if met else ["tds:intraday-bars@1.0 requires dataset bars(freq<1d)"])


def test_intraday_bars_without_freq_is_not_met(tmp_path: Path) -> None:
    def change(m: dict[str, Any]) -> None:
        _add("calendar_sessions")(m)
        build.bars(m)["params"] = {}

    assert _m008(tmp_path, "tds:intraday-bars@1.0", change)


def test_fx_is_fx_rates_or_instruments_with_bars(tmp_path: Path) -> None:
    # TDS 7: "`fx_rates` or `instruments(fx_spot)` + bars"; fx_spot is a row value (full level)
    fx = "tds:fx@1.0"
    assert _m008(tmp_path / "a", fx, lambda m: None) == []  # instruments + bars
    no_bars = _m008(tmp_path / "b", fx, lambda m: m["datasets"].pop(1))
    assert no_bars == [f"{fx} requires dataset fx_rates or instruments + bars"]

    def only_fx_rates(m: dict[str, Any]) -> None:
        m["datasets"].clear()
        _add("fx_rates")(m)

    assert _m008(tmp_path / "c", fx, only_fx_rates) == []


def test_minimal_daily_needs_a_declared_price_basis(tmp_path: Path) -> None:
    # TDS 7: "Any `price_basis` (declaration required)"
    minimal = "tds:minimal-daily@1.0"
    adjusted = _bars_params(freq="1d", price_basis="total_adjusted")
    assert _m008(tmp_path / "a", minimal, adjusted) == []
    wanted = [f"{minimal} requires dataset bars(freq=1d, price_basis)"]
    assert _m008(tmp_path / "b", minimal, _bars_params(freq="1d")) == wanted
    # null is not declared (#80 Decisions, item 1): M008 alone, no M014
    manifest, files = build.base()
    build.bars(manifest)["params"] = {"freq": "1d", "price_basis": None}
    result = check(Path(build.write(tmp_path / "c", manifest, files)), level="manifest")
    assert [(f.code, f.message) for f in result.errors] == [("TDS-M008", wanted[0])]


def test_a_package_error_fails_every_profile(tmp_path: Path) -> None:
    (tmp_path / "tds.json").write_text("{not json", encoding="utf-8")
    result = check(tmp_path, level="manifest", profiles=["tds:minimal-daily@1.0"])
    assert [f.code for f in result.errors] == ["TDS-M001"]
    assert result.profiles["tds:minimal-daily@1.0"] == ProfileStatus(False, "manifest", "fail")
