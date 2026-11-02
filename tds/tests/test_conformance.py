"""TDS 8.5 / spec 8.4a: per code, the fail package raises only that code, the pass package none."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pyarrow as pa
import pytest

from nexusbt_tds import ProfileStatus, check
from nexusbt_tds.check import Level

from .conformance_build import build

#: The S codes the `schema` level reports.
S_CODES = [f"TDS-S{n:03}" for n in range(1, 11)]


def codes(path: Path, level: Level = "manifest", **kwargs: Any) -> list[str]:
    result = check(path, level=level, **kwargs)
    return [f.code for f in (*result.errors, *result.warnings)]


def write(root: Path, change: Any = None) -> Path:
    manifest, files = build.base()
    if change:
        change(manifest, files)
    return Path(build.write(root, manifest, files))


def add_bars_file(path: str, size: int = 1) -> Any:
    return lambda m, f: build.bars(m)["files"].append({"path": path, "bytes": size})


@pytest.mark.parametrize("code", [f"TDS-M{n:03}" for n in range(1, 15)])
def test_M_codes(code: str, tmp_path: Path) -> None:
    package = tmp_path / "pkg"
    assert codes(build.write(package / "fail", *build.package(code, "fail"))) == [code]
    assert codes(build.write(package / "pass", *build.package(code, "pass"))) == []
    assert codes(package / "fail", "schema") == [code]  # also at the CLI's default level


@pytest.mark.parametrize("code", S_CODES)
def test_S_codes(code: str, tmp_path: Path) -> None:
    fail = build.write(tmp_path / "fail", *build.package(code, "fail"))
    assert codes(fail, "schema") == [code]
    assert codes(fail) == []  # the manifest level reads no Parquet
    assert codes(build.write(tmp_path / "pass", *build.package(code, "pass")), "schema") == []


def test_schema_level_reports_rows_not_checked(tmp_path: Path) -> None:
    result = check(write(tmp_path / "year=x"), level="schema")  # a folder above: no partition
    assert (result.errors, result.warnings) == ((), ())
    assert result.profiles == {
        "tds:minimal-daily@1.0": ProfileStatus(True, "schema", "not_checked")
    }
    assert {"TDS-K001", "TDS-R001", "TDS-T001", "TDS-H001"} <= set(result.unchecked)  # rows
    assert "TDS-S009" in result.unchecked  # NaN is not in the footers
    assert not set(S_CODES) - {"TDS-S009"} & set(result.unchecked)
    broken = build.write(tmp_path / "broken", *build.package("TDS-S002", "fail"))
    assert check(broken, level="schema").profiles["tds:minimal-daily@1.0"].result == "fail"


def test_a_rule_without_statistics_is_not_checked(tmp_path: Path) -> None:
    def blind(m: dict[str, Any], f: Any) -> None:
        build.rewrite(m, f, build.INSTRUMENTS, build.instruments(), write_statistics=False)

    assert "TDS-S003" not in check(write(tmp_path), level="schema").unchecked
    result = check(write(tmp_path, blind), level="schema")
    assert "TDS-S003" in result.unchecked
    assert result.errors == ()


def _classes(*values: str, **opts: Any) -> Any:
    """The instruments file with one row per `asset_class` value."""
    rows = pa.concat_tables([build.instruments(asset_class=pa.array([v])) for v in values])
    return lambda m, f: build.rewrite(m, f, build.INSTRUMENTS, rows, **opts)


@pytest.mark.parametrize(
    ("change", "found", "unchecked"),
    [  # a footer shows a column's minimum and maximum: its values when they are equal
        (_classes("equity", "fund"), [], True),  # one row group: `etf` and `zzz` may lie between
        (_classes("equity", "fund", row_group_size=1), [], False),  # every value is a min
        (_classes("equity", "zzz"), ["TDS-S006"], True),
        (_classes("equity", write_statistics=False), [], True),
        (lambda m, f: build.rewrite(m, f, build.INSTRUMENTS, build.instruments(
            asset_class=pa.array([None], pa.string()))), ["TDS-S003"], False),  # nulls only
    ],
)  # fmt: skip
def test_enum_values_the_footer_cannot_show_are_not_checked(
    change: Any, found: list[str], unchecked: bool, tmp_path: Path
) -> None:
    result = check(write(tmp_path, change), level="schema")
    assert [f.code for f in result.errors] == found
    assert ("TDS-S006" in result.unchecked) is unchecked


def test_an_open_list_is_not_checked_alike_and_a_bad_dictionary_excuses_nothing(
    tmp_path: Path,
) -> None:
    two = pa.concat_tables(  # one row group, `common` to `unit`: what lies between is unknown
        [build.instruments(category=pa.array([v])) for v in ("common", "unit")]
    )
    package = write(tmp_path / "two", lambda m, f: build.rewrite(m, f, build.INSTRUMENTS, two))
    assert "TDS-S007" in check(package, level="schema").unchecked

    def bad_dictionary(m: dict[str, Any], f: Any) -> None:
        build._instruments(codes=True, category=pa.array(["ordinary"]))(m, f)
        rel = "dictionary/codes/part-00000.parquet"
        f[rel] = build.parquet(pa.table({"label": ["x"]}), "dictionary/codes")  # no field, code
        m["datasets"][-1]["files"][0]["bytes"] = len(f[rel])

    result = check(write(tmp_path / "bad", bad_dictionary), level="schema")
    assert [w.code for w in result.warnings] == ["TDS-S007"]


@pytest.mark.parametrize(
    ("value", "found"),
    [("vendor:lean", []), ("vendor:", ["TDS-S007"]), ("lean", ["TDS-S007"]), ("ticker", [])],
)
def test_a_placeholder_in_a_value_list_is_any_name(
    value: str, found: list[str], tmp_path: Path
) -> None:  # `vendor:<name>`: a rule chosen in #117
    table = pa.table({"instrument_id": ["US:AAA"], "symbol_type": [value], "symbol": ["AAA"]})
    rel = "instrument_symbols/part-00000.parquet"

    def add(m: dict[str, Any], f: Any) -> None:
        f[rel] = build.parquet(table, "instrument_symbols")
        m["datasets"].append({"name": "instrument_symbols", "kind": "instrument_symbols",
                              "schema_version": "1.0", "path": "instrument_symbols",
                              "files": [{"path": rel, "bytes": len(f[rel])}]})  # fmt: skip

    result = check(write(tmp_path, add), level="schema")
    assert [w.code for w in result.warnings] == found


_bars, TS, VERSION_1_9 = build._bars, build.TS, build.VERSION_1_9


@pytest.mark.parametrize(
    ("change", "expected"),
    [  # the rules chosen in #56, which TDS 3.2, 3.6 and the schema files leave open
        (_bars(ts_end=TS.cast(pa.timestamp("ns", "UTC"))), []),  # `ts_us/ns`: either unit
        (lambda m, f: (build.bars(m).update(columns=[{"name": "ts_end", "type": "ts_ns"}]),
                       _bars(ts_end=TS)(m, f)), ["TDS-S004"]),  # unless tds.json names one
        (_bars(ts_end=TS.cast(pa.timestamp("us"))), ["TDS-S004"]),  # no UTC
        (lambda m, f: build.rewrite(m, f, build.BARS, build.bars_table(ts_end=TS),
                                    use_deprecated_int96_timestamps=True), ["TDS-S004"]),
        (_bars(obs_status=pa.array([None], pa.string())), []),  # "no if dense": not dense
        (lambda m, f: (build.bars(m)["params"].update(density="dense"),
                       _bars(obs_status=pa.array([None], pa.string()))(m, f)), ["TDS-S003"]),
        (lambda m, f: build.bars(m)["params"].update(freq="1m"), ["TDS-S001", "TDS-S001"]),
        (build._move_bars(build.BARS.replace("year=2024", "year=20x4")), ["TDS-S008"]),
        (build._move_bars(build.BARS.replace("market=US", "market=")), ["TDS-S008"]),
        (lambda m, f: (build.bars(m).update(partitioning=[{"name": "year", "type": "date"}])),
         ["TDS-S008"]),  # a declared partition type comes first
        (_bars(meta={"tds.dataset": b"\xff", "tds.schema_version": "1.0"}), ["TDS-S010"]),
        (lambda m, f: build.rewrite(m, f, build.BARS, build.bars_table().append_column(
            "close", pa.array([1.0]))), []),  # a column written twice: no crash
        (lambda m, f: (build.bars(m).update(schema_version="1.9"),
                       _bars(VERSION_1_9, note=pa.array(["a"]))(m, f)), []),  # M011: ignored
        (lambda m, f: (build.bars(m).update(schema_version="2.0"),
                       _bars(close=pa.array(["1"]))(m, f)), []),  # M009: not read as 1.0
    ],
)  # fmt: skip
def test_schema_rules(change: Any, expected: list[str], tmp_path: Path) -> None:
    found = codes(write(tmp_path, change), "schema")
    assert [c for c in found if not c.startswith("TDS-M")] == expected  # M010, M008: not S rules


@pytest.mark.parametrize(
    "path",
    [
        "../outside.parquet",
        "bars/../../outside.parquet",
        "OUTSIDE",
        "C:\\x.parquet",
        "link",
        "a\0b",
    ],
)
def test_M012_path_escape(path: str, tmp_path: Path) -> None:
    outside = tmp_path / "outside.parquet"
    outside.write_bytes(b"x")
    package = write(tmp_path / "pkg", add_bars_file(str(outside) if path == "OUTSIDE" else path))
    (package / "link").symlink_to(outside)  # a symbolic link leading out of the package
    assert [c for c in codes(package) if c != "TDS-M005"] == ["TDS-M012"]


def test_M012_link_inside_the_package_is_safe(tmp_path: Path) -> None:
    package = write(tmp_path, add_bars_file("link", len(build.base()[1][build.INSTRUMENTS])))
    (package / "link").symlink_to(package / build.INSTRUMENTS)
    assert codes(package) == []


def test_M013_duplicate_path(tmp_path: Path) -> None:
    def twice(m: dict[str, Any], f: Any) -> None:
        again = dict(m["datasets"][0]["files"][0])
        again["path"] = "instruments/./part-00000.parquet"  # the same file, spelled differently
        build.bars(m)["files"].append(again)

    assert codes(write(tmp_path, twice)) == ["TDS-M013"]


@pytest.mark.parametrize(
    ("where", "value"),
    [
        ("availability", {"rule": "next_session_close"}),
        ("availability", {"rule": "ts_end+15min"}),
        ("availability", {"rule": 15}),
        ("availability", "ts_end_when_ready"),  # a bare rule string is read too
        ("hashes", {"hash_spec": ["tds-hash-1"]}),  # not a string: a finding, never a crash
        ("params", {"freq": "1d", "availability_by_column": {"is_halted": "pre_open"}}),
        ("hashes", {"hash_spec": "tds-hash-2"}),
    ],
)
def test_M014_unknown_required_rule(where: str, value: object, tmp_path: Path) -> None:
    def change(m: dict[str, Any], f: Any) -> None:
        (m if where == "hashes" else build.bars(m))[where] = value

    assert codes(write(tmp_path, change)) == ["TDS-M014"]


KNOWN_RULES = "column ts_end ts_end+PT15M session_open session_close next_session_open"
KNOWN_RULES += " next_session_open(known_on) ts_recv ts_recv+PT0.5S ts_recv_else(ts_event+PT1S)"


@pytest.mark.parametrize("rule", KNOWN_RULES.split())
def test_known_availability_rules_pass(rule: str, tmp_path: Path) -> None:
    package = write(tmp_path, lambda m, f: build.bars(m).update(availability={"rule": rule}))
    assert codes(package) == []


def test_M010_coverage_names_an_undeclared_market(tmp_path: Path) -> None:
    by_market: dict[str, Any] = {"coverage": {"by_market": {"US": {}, "JP": {}}}}
    assert codes(write(tmp_path, lambda m, f: build.bars(m).update(by_market))) == ["TDS-M010"]


def test_profiles_must_be_strings(tmp_path: Path) -> None:
    assert codes(write(tmp_path, lambda m, f: m.update(profiles=[123]))) == ["TDS-M001"]


@pytest.mark.parametrize(
    ("key", "where"), [("files", "dataset"), ("path", "file"), ("bytes", "file")]
)
def test_M003_minimal_dataset_and_file_fields(key: str, where: str, tmp_path: Path) -> None:
    def drop(m: dict[str, Any], f: Any) -> None:
        (build.bars(m) if where == "dataset" else build.bars(m)["files"][0]).pop(key)
        if key in ("files", "path"):
            f.pop(build.BARS)  # no longer listed: it would be M005

    assert codes(write(tmp_path, drop)) == ["TDS-M003"]


@pytest.mark.parametrize(
    ("price_basis", "bars_missing"), [("raw", False), ("total_adjusted", True)]
)
def test_core_requires_raw_dense_daily_bars(
    price_basis: str, bars_missing: bool, tmp_path: Path
) -> None:
    params = {"freq": "1d", "price_basis": price_basis, "density": "dense"}
    package = write(tmp_path, lambda m, f: build.bars(m).update(params=params))
    result = check(package, level="manifest", profiles=["tds:equity-daily-core@1.0"])
    assert ("dataset bars" in " ".join(e.message for e in result.errors)) is bars_missing


def test_producer_hint_travels_with_its_code(tmp_path: Path) -> None:
    manifest, files = build.package("TDS-M003", "fail")
    manifest["producer"]["hints"] = {"TDS-M003": "re-run the export", "TDS-M006": "unused"}
    (error,) = check(build.write(tmp_path, manifest, files), level="manifest").errors
    assert (error.code, error.hint) == ("TDS-M003", "re-run the export")
    assert error.to_dict()["hint"] == "re-run the export"


def test_jsonl_ends_with_the_summary(tmp_path: Path) -> None:
    package = build.write(tmp_path, *build.package("TDS-M003", "fail"))
    *findings, last = check(package, level="manifest").to_jsonl().splitlines()
    assert [line.count('"code": "TDS-M003"') for line in findings] == [1]
    assert last.startswith('{"summary": {"errors": 1, "warnings": 0, "level": "manifest"')
