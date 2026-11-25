"""TDS 5.5 (#705 Decisions 35, 36): `cum_factor_split` and `cum_factor_total` left the standard.

A package that still holds them gets TDS-S005, a warning, from the checker's existing rule, and
an unknown column is not in the value hash (TDS 4.5): the package hashes as if they were not there.
"""

from __future__ import annotations

from pathlib import Path

import pyarrow as pa

from nexusbt_tds import check
from nexusbt_tds.hash import package_hashes

from .conformance_build import build

LEFT = ("cum_factor_split", "cum_factor_total")


def _package(root: Path, *, with_left: bool) -> Path:
    manifest, files = build.base()
    if with_left:
        build._bars(**{name: pa.array([1.0]) for name in LEFT})(manifest, files)
    return Path(build.write(root, manifest, files))


def test_a_package_still_holding_the_two_columns_gets_s005_only(tmp_path: Path) -> None:
    result = check(_package(tmp_path, with_left=True), level="schema")
    assert result.errors == ()
    assert sorted(f.message for f in result.warnings if f.code == "TDS-S005") == [
        f"unknown column {name} (not `x_`)" for name in LEFT
    ]


def test_the_two_columns_move_no_value_hash(tmp_path: Path) -> None:
    held = package_hashes(_package(tmp_path / "held", with_left=True))
    without = package_hashes(_package(tmp_path / "without", with_left=False))
    assert held["datasets"] == without["datasets"]
    assert held["value_sha256"] == without["value_sha256"]
