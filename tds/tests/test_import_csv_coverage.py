"""TDS 4.2, 4.3: `tds import csv` writes each dataset's `coverage` block (#566)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from nexusbt_tds import check, import_csv
from nexusbt_tds.hash import write_hashes

from .test_import_csv import BARS, CHAPTER_7, MINIMAL, write


def datasets(package: Path) -> dict[str, dict[str, Any]]:
    manifest = json.loads((package / "tds.json").read_text(encoding="utf-8"))
    return {d["name"]: d for d in manifest["datasets"]}


def test_chapter_7_bars_carry_their_coverage(tmp_path: Path) -> None:
    """When I import TDS chapter 7's two CSVs, then the bars declare what 4.2's example does,
    dates as `YYYY-MM-DD`."""
    mapping = write(tmp_path, {"instruments.csv": CHAPTER_7, "bars.csv": BARS,
                               "mapping.yaml": MINIMAL})  # fmt: skip
    got = datasets(import_csv(mapping, tmp_path / "pkg"))
    assert got["bars"]["coverage"] == {
        "instruments": 1, "ts_min": "2024-01-02", "ts_max": "2024-01-02",
        "by_market": {"US": {"instruments": 1, "first": "2024-01-02", "last": "2024-01-02",
                             "rows": 1}},
    }  # fmt: skip
    # instruments: no `market=` partition, no date column 4.3 names: the count alone
    assert got["instruments"]["coverage"] == {"instruments": 1}


def codes(package: Path) -> set[str]:
    """The codes `tds check --level full` reports, D004 judged (not left `unchecked`)."""
    result = check(package, level="full")
    assert "TDS-D004" not in result.unchecked
    return {f.code for f in (*result.errors, *result.warnings)}


def test_instruments_are_distinct_ids_not_a_sum_of_partitions(tmp_path: Path) -> None:
    """One instrument in two `year=` partitions counts once, and `tds check --level full`
    reads the block as the rows have it (no TDS-D004)."""
    bars = BARS + "XNYS:AAPL,2023-12-29,192.53,42628800\n"
    mapping = write(tmp_path, {"instruments.csv": CHAPTER_7, "bars.csv": bars,
                               "mapping.yaml": MINIMAL})  # fmt: skip
    out = import_csv(mapping, tmp_path / "pkg")
    bars_entry = datasets(out)["bars"]
    assert len(bars_entry["files"]) == 2  # year=2023, year=2024
    assert bars_entry["coverage"] == {
        "instruments": 1, "ts_min": "2023-12-29", "ts_max": "2024-01-02",
        "by_market": {"US": {"instruments": 1, "first": "2023-12-29", "last": "2024-01-02",
                             "rows": 2}},
    }  # fmt: skip
    assert "TDS-D004" not in codes(out)
    manifest = json.loads((out / "tds.json").read_text(encoding="utf-8"))  # the check reads it
    next(d for d in manifest["datasets"] if d["name"] == "bars")["coverage"]["instruments"] = 2
    (out / "tds.json").write_text(json.dumps(manifest), encoding="utf-8")
    assert "TDS-D004" in codes(out)


def test_coverage_leaves_the_hashes_as_they_were(tmp_path: Path) -> None:
    """TDS 4.5: `coverage` is in none of the three hashes, so a package keeps them with the
    block removed (the physical one covers the data files only, not tds.json)."""
    mapping = write(tmp_path, {"instruments.csv": CHAPTER_7, "bars.csv": BARS,
                               "mapping.yaml": MINIMAL})  # fmt: skip
    out = import_csv(mapping, tmp_path / "pkg")
    manifest = json.loads((out / "tds.json").read_text(encoding="utf-8"))
    assert all("coverage" in d for d in manifest["datasets"])
    for d in manifest["datasets"]:
        del d["coverage"]
    (out / "tds.json").write_text(json.dumps(manifest), encoding="utf-8")
    without = write_hashes(out)
    for key in ("semantic_sha256", "value_sha256", "physical_sha256"):
        assert without[key] == manifest["hashes"][key], key


SYMBOLS = "instrument_id,symbol_type,symbol,venue_mic,valid_from,ts_known_from\n"
SYMBOL = "XNYS:AAPL,ticker,AAPL,XNYS,2024-01-02,2024-01-02T00:00:00Z\n"


@pytest.mark.parametrize("symbols", [SYMBOLS + SYMBOL, SYMBOLS], ids=["one row", "no row"])
def test_kinds_without_a_session_date_and_empty_ones_check_clean(
    tmp_path: Path, symbols: str
) -> None:
    """`instrument_symbols` (no `session_date`, no `market=` partition) gets `instruments`; an
    empty dataset the count alone; neither is TDS-D004 at `full`."""
    delistings = "delisting_id,instrument_id,exit_date\n"  # no rows, no `market=` partition
    mapping = write(tmp_path, {
        "instruments.csv": CHAPTER_7, "bars.csv": BARS, "symbols.csv": symbols,
        "delistings.csv": delistings,
        "mapping.yaml": MINIMAL + "  instrument_symbols:\n    file: symbols.csv\n"
        "    availability: {column: ts_known_from}\n"
        "  delistings:\n    file: delistings.csv\n"
        "    availability: {exit: ts_exit_known, value: ts_value_available}\n",
    })  # fmt: skip
    out = import_csv(mapping, tmp_path / "pkg")
    got = datasets(out)
    n = symbols.count("\n") - 1
    assert got["instrument_symbols"]["coverage"] == {"instruments": n}
    assert got["delistings"]["coverage"] == {"instruments": 0}
    assert "TDS-D004" not in codes(out)
