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


@pytest.mark.parametrize("code", list(build.CASES))
def test_M_codes(code: str, tmp_path: Path) -> None:
    package = tmp_path / "pkg"
    assert codes(build.write(package / "fail", *build.package(code, "fail"))) == [code]
    assert codes(build.write(package / "pass", *build.package(code, "pass"))) == []


def test_profiles_must_be_strings(tmp_path: Path) -> None:
    assert codes(write(tmp_path, lambda m, f: m.update(profiles=[123]))) == ["TDS-M001"]


@pytest.mark.parametrize(("key", "where"), [("files", "dataset"), ("bytes", "file")])
def test_M003_minimal_dataset_and_file_fields(key: str, where: str, tmp_path: Path) -> None:
    def drop(m: dict[str, Any], f: Any) -> None:
        (build.bars(m) if where == "dataset" else build.bars(m)["files"][0]).pop(key)

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
