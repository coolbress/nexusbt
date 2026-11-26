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

#: TDS 7, the profile column of the table, in its order (`tds:fx` without `@`).
CHAPTER_7 = "minimal-daily equity-daily-core panels intraday-bars fx"


def test_every_chapter_7_profile_is_in_the_table() -> None:
    assert list(PROFILES) == [f"tds:{name}@1.0" for name in CHAPTER_7.split()]


def test_a_name_without_version_means_1_0() -> None:
    assert profile_id("tds:minimal-daily") == "tds:minimal-daily@1.0"
    assert profile_id("tds:panels@1.1") == "tds:panels@1.1"


def test_core_stacks_on_minimal_with_raw_dense_daily_bars() -> None:
    minimal, core = PROFILES["tds:minimal-daily@1.0"], PROFILES["tds:equity-daily-core@1.0"]
    daily = ("bars", (("freq", "=1d"), ("price_basis", "")))  # "" : declared, any value
    calendar = ((("calendar_sessions", ()),),)  # C3: every daily profile (#705)
    assert minimal.requires == (((("instruments", ()),),), ((daily,),), calendar)
    raw_dense = ("bars", (("freq", "=1d"), ("price_basis", "=raw"), ("density", "=dense")))
    assert core.requires[:2] == (((("instruments", ()),),), ((raw_dense,),))
    assert [group[0][0][0] for group in core.requires[2:]] == [
        "calendar_sessions",
        "corporate_actions",
        "delistings",
    ]


def test_alternatives_and_experimental_status() -> None:
    together = (("instruments", ()), ("bars", ()))  # TDS 7: `instruments(fx_spot)` + bars
    assert PROFILES["tds:fx@1.0"].requires == (((("fx_rates", ()),), together),)
    assert PROFILES["tds:intraday-bars@1.0"].status == "experimental"
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
        # not declared: checked anyway, and it lacks dense bars and two datasets more (M008)
        "tds:equity-daily-core@1.0": ProfileStatus(False, "manifest", "fail"),
        "tds:no-such@1.0": ProfileStatus(False, "none", "fail"),  # M007
    }
    assert sorted({f.code for f in result.errors}) == ["TDS-M007", "TDS-M008"]
    by_default = check(package, level="manifest")  # without profiles: the declared ones
    assert list(by_default.profiles) == ["tds:minimal-daily@1.0"]


def test_minimal_daily_without_calendar_sessions_is_M008(tmp_path: Path) -> None:
    """C3 (#705): every daily profile requires the calendar, minimal-daily too."""
    manifest, files = build.base()
    build.no_calendar(manifest, files)
    package = Path(build.write(tmp_path, manifest, files))
    result = check(package, level="manifest", profiles=["tds:minimal-daily@1.0"])
    assert [(f.code, f.message) for f in result.errors] == [
        ("TDS-M008", "tds:minimal-daily@1.0 requires dataset calendar_sessions")
    ]
    assert check(package, level="manifest").errors == ()  # declaring none, it opens


def test_manifest_level_never_reports_unchecked_as_pass(tmp_path: Path) -> None:
    package = Path(build.write(tmp_path, *build.base()))  # meets tds:minimal-daily at this level
    met = [name for name, p in PROFILES.items() if name.startswith("tds:minimal") or not p.requires]
    result = check(package, level="manifest", profiles=met)
    assert (result.errors, result.warnings) == ((), ())
    assert {s.result for s in result.profiles.values()} == {"not_checked"}
    assert {"TDS-K001", "TDS-S001", "TDS-H001", "TDS-A003"} <= set(result.unchecked)
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

    def add(m: dict[str, Any]) -> None:
        if not any(d["kind"] == kind for d in m["datasets"]):  # the base's calendar (#705)
            m["datasets"].append(dict(entry))

    return add


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
    # null is not declared (#80 Decisions, item 1): M008, and M003 for no default (#705 C5),
    # no M014
    manifest, files = build.base()
    build.bars(manifest)["params"] = build.DENSE | {"price_basis": None}
    result = check(Path(build.write(tmp_path / "c", manifest, files)), level="manifest")
    assert sorted(f.code for f in result.errors) == ["TDS-M003", "TDS-M008"]
    assert ("TDS-M008", wanted[0]) in [(f.code, f.message) for f in result.errors]


def test_a_package_error_fails_every_profile(tmp_path: Path) -> None:
    (tmp_path / "tds.json").write_text("{not json", encoding="utf-8")
    result = check(tmp_path, level="manifest", profiles=["tds:minimal-daily@1.0"])
    assert [f.code for f in result.errors] == ["TDS-M001"]
    assert result.profiles["tds:minimal-daily@1.0"] == ProfileStatus(False, "manifest", "fail")


def test_the_columns_chapter_7_names_per_profile() -> None:
    # TDS 7, the "required" cell of each row that names a column, by the dataset that holds it
    raw_dense = "bars(freq=1d, price_basis=raw, density=dense)"
    core = {raw_dense: "close obs_status"}
    # and in a dataset that holds an equity or etf instrument (#705 Decisions 37); minimal-daily
    # asks close alone (#705, 2026-11-22)
    traded = {
        name.removeprefix("tds:").removesuffix("@1.0"): {
            describe((need,)): " ".join(columns) for need, columns in profile.traded
        }
        for name, profile in PROFILES.items()
        if profile.traded
    }
    ohlv = "open high low volume"
    assert traded == {"equity-daily-core": {raw_dense: ohlv}}
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
        "panels": {"feature_panels": "ts_available", "label_panels": "ts_available"},
        "intraday-bars": {"bars(freq<1d)": "ts_start ts_end session_date"},
    }


CORE, MINIMAL = "tds:equity-daily-core@1.0", "tds:minimal-daily@1.0"
_OHLCV = ("open", "high", "low", "close", "volume")


def _core(
    tmp_path: Path, columns: dict[str, Any], profile: str = CORE, level: Any = "schema",
    asset: str = "equity", declared: bool = False,
) -> CheckResult:  # fmt: skip
    """`profile` checked (and `declared`, in place of minimal-daily) on a package with core's
    datasets and one traded, whole daily bar of an `asset` instrument, its bars' `columns`
    replaced (`None`: left out)."""
    manifest, files = build.base()
    manifest["profiles"] = [profile] if declared else manifest["profiles"]
    build._instruments(asset_class=pa.array([asset]))(manifest, files)
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
    # TDS 7: core's bars hold `obs_status` (#352) and, holding an equity, OHLCV (#705)
    result = _core(tmp_path / "a", {column: None})
    found = [f for f in result.errors if f.code == "TDS-M008"]
    rows = "" if column == "obs_status" else " (equity or etf rows)"
    assert [f.message for f in found] == [f"{CORE} requires column {column} in bars{rows}: missing"]
    assert found[0].dataset == "bars_1d"
    assert result.profiles[CORE] == ProfileStatus(False, "schema", "fail")
    # the manifest level reads no footer: not_checked, never an error
    below = _core(tmp_path / "b", {column: None}, level="manifest")
    assert below.errors == ()
    assert below.profiles[CORE] == ProfileStatus(False, "manifest", "not_checked")
    # counter-example: the same bars of an index, which needs only `close` (#705 Decisions 39).
    # Core is checked, not declared, so `obs_status` on every row (S001, S003) is not asked:
    # 5.5's null cell reads the declared profiles, as V004 does (#705 Decisions 129).
    index = [f.code for f in _core(tmp_path / "c", {column: None}, asset="index").errors]
    assert index == (["TDS-M008"] if column == "obs_status" else [])
    # and the same bars of the equity under minimal-daily, which asks close alone (2026-11-22)
    assert _core(tmp_path / "d", {column: None}, MINIMAL).errors == ()
    assert [f.code for f in result.errors] == ["TDS-M008"]


@pytest.mark.parametrize(
    ("profile", "found", "absent"), [(CORE, ["TDS-S003"], ["TDS-S001"]), (MINIMAL, [], [])]
)
def test_obs_status_is_on_every_row_where_a_declared_profile_requires_it(
    profile: str, found: list[str], absent: list[str], tmp_path: Path
) -> None:
    """TDS 5.5 and 7 (#705 Decisions 128, 129): a valued row's null `obs_status` states no
    state, which minimal-daily allows; core and above hold it on every row (S003), and left
    out of the file it is S001."""
    null = {"obs_status": pa.array([None], pa.string())}
    codes = [f.code for f in _core(tmp_path / "a", null, profile, declared=True).errors]
    assert [c for c in codes if c.startswith("TDS-S")] == found
    gone = [f.code for f in _core(tmp_path / "b", {"obs_status": None}, profile, declared=True)
            .errors]  # fmt: skip
    assert [c for c in gone if c.startswith("TDS-S")] == absent


@pytest.mark.parametrize(("profile", "found"), [(CORE, ["TDS-V004"]), (MINIMAL, [])])
def test_a_traded_equity_without_volume_is_V004_where_a_declared_profile_requires_it(
    profile: str, found: list[str], tmp_path: Path
) -> None:
    # V004 reads open, high, low and volume of the datasets M008 requires them of (#705)
    two = {c: pa.array([10.0, 10.0]) for c in _OHLCV} | {
        "instrument_id": pa.array(["US:AAA", "US:AAA"]),
        "session_date": pa.array([dt.date(2024, 1, 2), dt.date(2024, 1, 3)]),
        "obs_status": pa.array(["traded", "traded"]),
        "volume": pa.array([None, 100.0]),
    }
    result = _core(tmp_path, two, profile, level="full", declared=True)
    assert [f.code for f in result.errors if f.code.startswith("TDS-V")] == found


@pytest.mark.parametrize(("held", "lacking"), [("US:IDX", False), ("US:AAA", True)])
def test_a_bars_dataset_needs_open_high_low_volume_only_for_its_own_equities(
    held: str, lacking: bool, tmp_path: Path
) -> None:
    # #705 Decisions 37: read per dataset from its `instrument_id`; an index carries close only
    manifest, files = build.base()
    build.bars(manifest)["params"] = dict(build.DENSE)  # core's, which minimal-daily is not
    index = build.instruments(instrument_id=pa.array(["US:IDX"]), asset_class=pa.array(["index"]))
    both = pa.concat_tables([build.instruments(), index])
    build.rewrite(manifest, files, build.INSTRUMENTS, both)
    rel, table = "levels/part-00000.parquet", pa.table({"instrument_id": [held], "close": [4.0],
                                                         "session_date": build.DAY, "open": [4.0],
                                                         "high": [4.0]})  # fmt: skip
    files[rel] = build.parquet(table, "levels")
    entry = {"path": rel, "rows": 1, "bytes": len(files[rel])}
    manifest["datasets"].append(build.bars(manifest) | {"name": "levels", "path": "levels",
                                                         "files": [entry]})  # fmt: skip
    result = check(Path(build.write(tmp_path, manifest, files)), level="schema", profiles=[CORE])
    rows = " (equity or etf rows)"
    traded = [f for f in result.errors if rows in f.message]  # core's other needs aside
    assert [f.message for f in traded] == [
        f"{CORE} requires column {c} in bars{rows}: missing" for c in ("low", "volume")
    ] * lacking  # the second dataset holds open and high, not low or volume
    assert {f.dataset for f in traded} <= {"levels"}


def test_bars_ids_that_are_no_text_are_the_schema_checks_not_a_crash(tmp_path: Path) -> None:
    # the second review of #705's 3a: bars ids that cannot be cast to string (exit 70 before)
    manifest, files = build.base()
    build._bars(instrument_id=pa.array([b"\xff"], pa.binary()))(manifest, files)
    result = check(Path(build.write(tmp_path, manifest, files)), level="schema")
    assert [f.code for f in result.errors] == ["TDS-S002"]


@pytest.mark.parametrize("ids", [["US:AAA", None], [1, 2]], ids=["a null id", "integer ids"])
def test_ids_of_another_kind_are_the_schema_checks_not_a_crash(
    ids: list[Any], tmp_path: Path
) -> None:
    # the fresh-context review of #705's 3a: these stopped the checker (exit 70)
    manifest, files = build.base()
    kind = pa.int64() if isinstance(ids[0], int) else pa.string()
    rows = pa.concat_tables([build.instruments(instrument_id=pa.array([i], kind)) for i in ids])
    build.rewrite(manifest, files, build.INSTRUMENTS, rows)
    if isinstance(ids[0], int):
        build._bars(instrument_id=pa.array([1]))(manifest, files)
    result = check(Path(build.write(tmp_path, manifest, files)), level="schema")
    assert "TDS-M008" not in {f.code for f in result.errors}  # the bars hold OHLCV anyway


def test_a_column_null_in_every_row_is_lacking(tmp_path: Path) -> None:
    # the `no_ohlc` shape: the column is there and holds no value (#352, decided 2026-11-11)
    null = pa.nulls(1, pa.float64())
    result = _core(tmp_path / "a", {"open": null})
    assert [f.message for f in result.errors] == [
        f"{CORE} requires column open in bars (equity or etf rows): null in every row"
    ]
    assert _core(tmp_path / "b", {"open": null}, MINIMAL, asset="index").errors == ()
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
    assert result.notes == (  # close alone, an equity's too (#705, 2026-11-22)
        f"TDS-M008 not checked for column close of bars_1d ({MINIMAL}): no statistics",
    )


def test_a_profile_column_is_looked_for_only_in_the_datasets_named(tmp_path: Path) -> None:
    manifest, files = build.base()
    build._bars(close=None)(manifest, files)  # minimal-daily's `close` gone from the bars
    root = Path(build.write(tmp_path, manifest, files))
    found = check(root, level="schema", profiles=[MINIMAL], datasets=["bars_1d"])
    assert [f.message for f in found.errors if f.code == "TDS-M008"] == [
        f"{MINIMAL} requires column close in bars: missing"
    ]
    other = check(root, level="schema", profiles=[MINIMAL], datasets=["instruments"])
    assert [f.code for f in other.errors] == []  # --datasets: only the named ones are read
