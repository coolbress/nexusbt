"""TDS 7, 8.2: the profile table `PROFILES`, and a profile's three results, never a false pass."""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pyarrow as pa
import pytest

from nexusbt_tds import PROFILES, CheckResult, ProfileStatus, check
from nexusbt_tds.profiles import describe, profile_id

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


def test_the_columns_chapter_7_names_per_profile() -> None:
    # TDS 7, the "required" cell of each row that names a column, by the dataset that holds it
    raw_dense = "bars(freq=1d, price_basis=raw, density=dense)"
    core = {raw_dense: "open high low close volume obs_status"}
    recorded = ("events", "fundamentals_events")  # #397 Decisions
    named = {
        name.removeprefix("tds:").removesuffix("@1.0"): {
            describe((need,)): " ".join(columns) for need, columns in profile.columns
        }
        for name, profile in PROFILES.items()
        if profile.columns
    }
    assert named == {
        "minimal-daily": {"bars(freq=1d, price_basis)": "close"},
        "equity-daily-core": core,
        "equity-daily-research": core,  # "above +"
        "panels": {"feature_panels": "ts_available", "label_panels": "ts_available"},
        "pit-fundamentals": {
            "fundamentals_events": "fact_id doc_id",
            "fundamentals_state": "lineage_id",
        },
        "bitemporal": dict.fromkeys(recorded, "ts_recorded"),
        "intraday-bars": {"bars(freq<1d)": "ts_start ts_end session_date"},
        "l1-ticks": {"trades": "ts_event sequence", "quotes": "ts_event sequence"},
        "l2-book": {"book_deltas(depth_kind=mbp)": "is_last"},
        "l3-book": {"book_deltas(depth_kind=mbo)": "order_id"},
        "alt-events": {"events": "ts_available", "series_observations": "ts_available"},
    }


CORE, MINIMAL = "tds:equity-daily-core@1.0", "tds:minimal-daily@1.0"
_OHLCV = ("open", "high", "low", "close", "volume")


def _core(
    tmp_path: Path, columns: dict[str, Any], profile: str = CORE, level: Any = "schema"
) -> CheckResult:
    """`profile` checked on a package with core's datasets and one traded, whole daily bar,
    its bars' `columns` replaced (`None`: left out)."""
    manifest, files = build.base()
    build.bars(manifest)["params"] = dict(build.DENSE)
    whole = dict.fromkeys(_OHLCV, pa.array([10.0])) | {"obs_status": pa.array(["traded"])}
    build.rewrite(manifest, files, build.BARS, build.bars_table(**(whole | columns)))
    for kind in ("calendar_sessions", "corporate_actions", "delistings"):
        _add(kind)(manifest)
    return check(Path(build.write(tmp_path, manifest, files)), level=level, profiles=[profile])


def test_a_whole_core_package_has_no_error(tmp_path: Path) -> None:
    result = _core(tmp_path, {})
    assert result.errors == ()
    assert result.profiles[CORE] == ProfileStatus(False, "schema", "not_checked")


@pytest.mark.parametrize("column", ["open", "high", "low", "volume", "obs_status"])
def test_core_bars_without_a_required_column_are_M008(column: str, tmp_path: Path) -> None:
    # TDS 7: core's bars hold OHLCV and `obs_status` (#352); the footer shows it
    result = _core(tmp_path / "a", {column: None})
    found = [f for f in result.errors if f.code == "TDS-M008"]
    assert [f.message for f in found] == [f"{CORE} requires column {column} in bars: missing"]
    assert found[0].dataset == "bars_1d"
    assert result.profiles[CORE] == ProfileStatus(False, "schema", "fail")
    # the manifest level reads no footer: not_checked, never an error
    below = _core(tmp_path / "b", {column: None}, level="manifest")
    assert below.errors == ()
    assert below.profiles[CORE] == ProfileStatus(False, "manifest", "not_checked")
    # counter-example: the same bars under minimal-daily, which names only `close`. Dense bars
    # without `obs_status` are S001 under any profile (5.5 "no if dense"), beside core's M008.
    others = [f.code for f in _core(tmp_path / "c", {column: None}, MINIMAL).errors]
    assert others == (["TDS-S001"] if column == "obs_status" else [])
    assert [f.code for f in result.errors] == [*others, "TDS-M008"]


def test_a_column_null_in_every_row_is_lacking(tmp_path: Path) -> None:
    # the `no_ohlc` shape: the column is there and holds no value (#352, decided 2026-11-11)
    null = pa.nulls(1, pa.float64())
    result = _core(tmp_path / "a", {"open": null})
    assert [f.message for f in result.errors] == [
        f"{CORE} requires column open in bars: null in every row"
    ]
    assert _core(tmp_path / "b", {"open": null}, MINIMAL).errors == ()
    wanted = [f"{MINIMAL} requires column close in bars: null in every row"]
    no_close = _core(tmp_path / "c", {"close": null}, MINIMAL)
    assert [f.message for f in no_close.errors if f.code == "TDS-M008"] == wanted


def test_a_column_with_one_value_or_no_row_is_not_lacking(tmp_path: Path) -> None:
    # a null beside a value is a row's matter (5.5: null prices on a halted bar), not M008's
    two = {c: pa.array([None, 10.0]) for c in _OHLCV} | {
        "instrument_id": pa.array(["US:AAA", "US:AAA"]),
        "session_date": pa.array([dt.date(2024, 1, 2), dt.date(2024, 1, 3)]),
        "obs_status": pa.array(["halted", "traded"]),
    }
    assert [f.code for f in _core(tmp_path / "a", two).errors] == []
    empty = {name: column.slice(0, 0) for name, column in two.items()}
    for name, bars in (("b", empty), ("c", empty | {"open": None})):  # no row lacks nothing
        result = _core(tmp_path / name, bars)
        assert (result.errors, result.notes) == ((), ())


def test_a_column_without_statistics_is_a_note_not_an_error(tmp_path: Path) -> None:
    manifest, files = build.base()
    build.rewrite(manifest, files, build.BARS, build.bars_table(), write_statistics=False)
    result = check(Path(build.write(tmp_path, manifest, files)), level="schema")
    assert [f.code for f in result.errors if f.code == "TDS-M008"] == []
    assert result.notes == (
        f"TDS-M008 not checked for column close of bars_1d ({MINIMAL}): no statistics",
    )


def test_bitemporal_needs_ts_recorded_where_the_dataset_is_present(tmp_path: Path) -> None:
    # TDS 7: "(on top of other profiles)": no dataset of its own, a column in those it names
    bitemporal = "tds:bitemporal@1.0"
    manifest, files = build.base()
    assert check(Path(build.write(tmp_path / "a", manifest, files)), level="schema",
                 profiles=[bitemporal]).errors == ()  # fmt: skip
    build._event()(manifest, files)
    result = check(Path(build.write(tmp_path / "b", manifest, files)), level="schema",
                   profiles=[bitemporal], datasets=["events"])  # fmt: skip
    assert [f.message for f in result.errors if f.code == "TDS-M008"] == [
        f"{bitemporal} requires column ts_recorded in events: missing"
    ]
    named = check(tmp_path / "b", level="schema", profiles=[bitemporal], datasets=["bars_1d"])
    assert [f.code for f in named.errors] == []  # --datasets: only the named ones are read


BITEMPORAL = "tds:bitemporal@1.0"


def test_bitemporal_fundamentals_events_without_ts_recorded_is_M008(tmp_path: Path) -> None:
    # #397 Decisions: the profile names the two datasets whose schema carries `ts_recorded` (5.17)
    manifest, files = build.base()
    build._facts("F1")(manifest, files)  # fundamentals_events and _state, without ts_recorded
    result = check(Path(build.write(tmp_path / "a", manifest, files)), level="schema",
                   profiles=[BITEMPORAL])  # fmt: skip
    assert [f.message for f in result.errors if f.code == "TDS-M008"] == [
        f"{BITEMPORAL} requires column ts_recorded in fundamentals_events: missing"
    ]  # and none for fundamentals_state, whose schema has no `ts_recorded`
    manifest, files = build.base()
    build._facts("F1", ts_recorded=pa.array([build.NEW_YEAR], build.TS_UTC))(manifest, files)
    held = check(Path(build.write(tmp_path / "b", manifest, files)), level="schema",
                 profiles=[BITEMPORAL])  # fmt: skip
    assert (held.errors, [f.code for f in held.warnings if "ts_recorded" in f.message]) == ((), [])


def test_bitemporal_classifications_written_to_their_schema_are_clean(tmp_path: Path) -> None:
    # #397: `classifications` carries its recorded time as `ts_known_from` (5.1.5), no M008/S005
    manifest, files = build.base()
    build._classified(build._A)(manifest, files)
    result = check(Path(build.write(tmp_path, manifest, files)), level="schema",
                   profiles=[BITEMPORAL])  # fmt: skip
    assert (result.errors, [f.code for f in result.warnings if f.code == "TDS-S005"]) == ((), [])
