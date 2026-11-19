"""#564: a package without `coverage` (TDS 4.3, optional) opens; what F-02 and the fallback
records read from it comes from the bars themselves (spec 4.5 F-02: "from the first to the last
day of `bars`"; 4.6: the market from the `market=` partition)."""

from __future__ import annotations

import json
import warnings
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from nexusbt.data import CapabilityRequest, DataConfig, open_snapshot
from nexusbt.testing.synth import make_snapshot
from nexusbt_tds import check, import_csv

#: TDS chapter 7's two CSVs and the mapping of `tds/tests/test_import_csv.py::test_minimal_two_csv`.
INSTRUMENTS = """instrument_id,asset_class,market,calendar_id,currency,listed_on
XNYS:AAPL,equity,US,XNYS,USD,1980-12-12
"""
BARS = """instrument_id,session_date,close,volume
XNYS:AAPL,2024-01-02,185.64,82488700
"""
MINIMAL = """profiles: [tds:minimal-daily@1.0]
market: {code: US, calendar_id: XNYS, currency: USD, timezone: America/New_York}
datasets:
  instruments:
    file: instruments.csv
  bars:
    file: bars.csv
    params: {freq: 1d, price_basis: total_adjusted}
"""


def test_chapter_7_csv_package_opens_and_reads_its_close(tmp_path: Path) -> None:
    """When I import TDS chapter 7's two CSVs and open the package, then the close of
    XNYS:AAPL on 2024-01-02 reads 185.64 (#564: it was `KeyError: 'coverage'`)."""
    for name, text in (("instruments.csv", INSTRUMENTS), ("bars.csv", BARS),
                       ("mapping.yaml", MINIMAL)):  # fmt: skip
        (tmp_path / name).write_text(text, encoding="utf-8")
    pkg = import_csv(tmp_path / "mapping.yaml", tmp_path / "pkg")
    assert check(pkg, level="full").error_count == 0
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # F-02's E30 for the synthesized XNYS sessions
        snap = open_snapshot(DataConfig(path=pkg))
        day = np.array(["2024-01-02"], dtype="datetime64[D]")
        block = snap.market_block("US", ["close"], day)
    assert block.instrument_ids == ("XNYS:AAPL",)
    assert block.values["close"].tolist() == [[185.64]]


def no_coverage(data: dict[str, Any]) -> None:
    for d in data["datasets"]:
        d.pop("coverage", None)


def processed_only(data: dict[str, Any]) -> None:
    """TDS 4.3: `by_market.<m>` may hold `processed_through_session` alone."""
    for d in data["datasets"]:
        by_market = d.get("coverage", {}).get("by_market", {})
        for m, e in by_market.items():
            by_market[m] = {"processed_through_session": e.get("last", "2020-01-31")}


#: degrade, markets, the feature asked for: each fallback whose record reads the bars' extent.
CASES = {"F-02": (["no_sessions"], ("KR", "US"), "backtest"),
         "F-03": (["sparse_bars"], ("KR", "US"), "backtest"),
         "F-15": (["no_tick_info"], ("KR", "ZZ"), "grid")}  # fmt: skip


@pytest.mark.parametrize("edit", [no_coverage, processed_only])
@pytest.mark.parametrize("case", CASES)
def test_bars_extent_read_from_the_bars_without_coverage(
    tmp_path: Path, case: str, edit: Callable[[dict[str, Any]], None]
) -> None:
    """When `coverage` is left out of each dataset, or holds `processed_through_session` alone,
    then the package opens with the same fallbacks, and the same calendar, as with it."""
    degrade, markets, feature = CASES[case]
    path = make_snapshot(tmp_path / "s", preset="tiny", markets=markets, degrade=degrade)
    cfg = DataConfig(path=path, allow_untested=True)
    asked = CapabilityRequest(frozenset({feature}))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # each case's E30
        declared = open_snapshot(cfg, required=asked)
        days = {m: declared.calendar(m).dates.tolist() for m in markets}
        data = json.loads((path / "tds.json").read_text(encoding="utf-8"))
        edit(data)
        (path / "tds.json").write_text(json.dumps(data), encoding="utf-8")
        read = open_snapshot(cfg, required=asked)
        assert {m: read.calendar(m).dates.tolist() for m in markets} == days
    assert case in {r.id for r in declared.fallbacks}
    assert read.fallbacks == declared.fallbacks
