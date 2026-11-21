"""The transformations behind the metamorphic tests (`_variants`, #255): each changes only what
it is for, on the copy, and leaves a package that `tds check --level full` reads."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from nexusbt.testing.synth import make_snapshot
from nexusbt_tds import check
from property._variants import PRICES, rows_of, scale_prices

pytestmark = pytest.mark.unit


@pytest.fixture(scope="module")
def original(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("synth") / "pkg"
    return make_snapshot(root, preset="small", markets=("KR",), n_kr=8, degrade=())


def files(root: Path) -> dict[str, bytes]:
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def datasets(root: Path) -> dict[str, dict[str, Any]]:
    return {d["name"]: d for d in json.loads((root / "tds.json").read_text("utf-8"))["datasets"]}


def snapshot_id(root: Path) -> str:
    return str(json.loads((root / "tds.json").read_text("utf-8"))["snapshot_id"])


#: What the full check warns of a scaled package, by the side of 1 that k is on: an odd volume
#: over k is not an integer (TDS-V010), a KR price over 8 leaves its tick grid (TDS-V012). 8.3's
#: transformation makes them; M1's pipeline reads neither (#255's Decisions, 2026-11-21).
WARNED = {2**-3: {"TDS-V012"}, 2.0: {"TDS-V010"}, 2.0**10: {"TDS-V010"}}


@pytest.mark.parametrize("k", list(WARNED))
@pytest.mark.parametrize("instrument", ["KR:T00001", "KR:T00006"])  # dividends; a delisting
def test_scale_changes_one_instruments_prices_only(
    original: Path, tmp_path: Path, instrument: str, k: float
) -> None:
    before = files(original)
    at = shutil.copytree(original, tmp_path / "pkg")
    scale_prices(at, instrument, k)
    assert files(original) == before  # the copy is changed, never the original
    for name in datasets(original):
        old, new = rows_of(original, name), rows_of(at, name)
        if name not in PRICES:
            assert new == old, name
            continue
        assert len(new) == len(old), name
        for a, b in zip(old, new, strict=True):
            if a.get("instrument_id") != instrument:
                assert b == a, name
                continue
            for column, value in a.items():
                power = PRICES[name].get(column, 0)
                want = value if value is None or power == 0 else value * k**power
                assert b[column] == want, (name, column)
    assert any(r["instrument_id"] == instrument for r in rows_of(at, "corporate_actions"))
    assert snapshot_id(at) != snapshot_id(original)
    assert not {"/", ":"} & set(snapshot_id(at))
    found = check(at, level="full")  # the hashes and sizes rewritten (H, D004 among them)
    assert found.error_count == 0, [(e.code, e.dataset) for e in found.errors]
    assert {w.code for w in found.warnings} == WARNED[k]


def test_scale_refuses_a_k_that_is_not_a_power_of_two(original: Path, tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="power of two"):
        scale_prices(shutil.copytree(original, tmp_path / "pkg"), "KR:T00001", 3.0)
