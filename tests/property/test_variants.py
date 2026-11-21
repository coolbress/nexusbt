"""The transformations behind the metamorphic tests (`_variants`, #255): each changes only what
it is for, on the copy, and leaves a package that `tds check --level full` reads."""

from __future__ import annotations

import datetime as dt
import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from nexusbt.testing.synth import make_snapshot
from nexusbt_tds import check
from property._variants import (
    PRICES,
    append_action,
    drop_instrument,
    neutral_split,
    rows_of,
    scale_prices,
)

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


def test_a_neutral_split_is_one_row_more(original: Path, tmp_path: Path) -> None:
    before = files(original)
    at = shutil.copytree(original, tmp_path / "pkg")
    row = neutral_split(at, "KR:T00003", dt.date(2017, 6, 1))
    assert (row["ratio_num"], row["ratio_den"], row["price_factor"]) == (1, 1, 1.0)
    bars = [r for r in rows_of(at, "bars_1d") if r["instrument_id"] == "KR:T00003"]
    (eve,) = (r for r in bars if r["session_date"] == dt.date(2017, 5, 31))
    assert row["factor_ref_price"] == eve["close"]  # the session before the ex-date
    assert row["event_id"] not in {r["event_id"] for r in rows_of(at, "corporate_actions")}
    append_action(at, row)
    assert files(original) == before
    old, new = rows_of(original, "corporate_actions"), rows_of(at, "corporate_actions")
    assert len(new) == len(old) + 1
    assert [r for r in new if r["event_id"] != row["event_id"]] == old  # the same order
    assert [r for r in new if r["event_id"] == row["event_id"]] == [row]
    changed = {f for f, b in files(at).items() if before.get(f) != b}
    assert changed == {"tds.json", datasets(at)["corporate_actions"]["files"][0]["path"]}
    assert snapshot_id(at) != snapshot_id(original)
    found = check(at, level="full")
    assert (found.error_count, [w.code for w in found.warnings]) == (0, [])


@pytest.fixture(scope="module")
def nine(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("synth") / "nine"
    return make_snapshot(root, preset="small", markets=("KR",), n_kr=9, degrade=())


@pytest.mark.parametrize("instrument", ["KR:T00003", "KR:T00009"])  # KR:T00009 is delisted
def test_dropping_an_instrument_deletes_its_rows_only(
    nine: Path, tmp_path: Path, instrument: str
) -> None:
    before = files(nine)
    at = shutil.copytree(nine, tmp_path / "pkg")
    drop_instrument(at, instrument)
    assert files(nine) == before
    for name in datasets(nine):
        old, new = rows_of(nine, name), rows_of(at, name)
        assert new == [r for r in old if r.get("instrument_id") != instrument], name
    assert any(r["instrument_id"] == instrument for r in rows_of(nine, "delistings")) == (
        instrument == "KR:T00009"
    )
    assert snapshot_id(at) != snapshot_id(nine)
    found = check(at, level="full")
    assert (found.error_count, [w.code for w in found.warnings]) == (0, [])
