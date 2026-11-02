"""TDS 8.5 / spec 8.4a: per code, the fail package raises only that code, the pass package none."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from nexusbt_tds import check

from .conformance_build import build


def codes(path: Path, **kwargs: Any) -> list[str]:
    result = check(path, level="manifest", **kwargs)
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
