"""#564: a package without `coverage` (TDS 4.3, optional) opens; what the fallback records
read from it comes from the bars themselves (4.6: the market from the `market=` partition)."""

from __future__ import annotations

import json
import warnings
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow.parquet as pq
import pytest

from nexusbt.contracts import ID_COLUMN
from nexusbt.data import CapabilityRequest, DataConfig, open_snapshot
from nexusbt.testing.synth import make_snapshot
from nexusbt_tds import check, import_csv
from nexusbt_tds.hash import write_hashes

#: TDS chapter 7's two CSVs and the mapping of `tds/tests/test_import_csv.py::test_minimal_two_csv`.
INSTRUMENTS = """instrument_id,asset_class,market,calendar_id,currency,listed_on
XNYS:AAPL,equity,US,XNYS,USD,1980-12-12
"""
BARS = """instrument_id,session_date,open,high,low,close,volume
XNYS:AAPL,2024-01-02,187.15,188.44,183.89,185.64,82488700
"""  # an equity's whole bars; minimal-daily asks close alone (TDS 7, #705)
MINIMAL = """profiles: [tds:minimal-daily@1.0]
market:
  code: US
  calendar_id: XNYS
  currency: USD
  timezone: America/New_York
  open: "09:30"
  close: "16:00"
datasets:
  instruments:
    file: instruments.csv
  bars:
    file: bars.csv
    params: {freq: 1d, price_basis: total_adjusted}
"""


@pytest.mark.parametrize("declared", [False, True], ids=["coverage removed", "as imported"])
def test_chapter_7_csv_package_opens_and_reads_its_close(tmp_path: Path, declared: bool) -> None:
    """When I import TDS chapter 7's two CSVs and open the package, then the close of
    XNYS:AAPL on 2024-01-02 reads 185.64 (#564: it was `KeyError: 'coverage'`), with the
    `coverage` the importer writes (#566) and without it."""
    for name, text in (("instruments.csv", INSTRUMENTS), ("bars.csv", BARS),
                       ("mapping.yaml", MINIMAL)):  # fmt: skip
        (tmp_path / name).write_text(text, encoding="utf-8")
    pkg = import_csv(tmp_path / "mapping.yaml", tmp_path / "pkg")
    if not declared:
        data = json.loads((pkg / "tds.json").read_text(encoding="utf-8"))
        no_coverage(data)
        (pkg / "tds.json").write_text(json.dumps(data), encoding="utf-8")
    assert check(pkg, level="full").error_count == 0
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # the import's calendar: no F-02 since #705
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
CASES = {"F-03": (["sparse_bars"], ("KR", "US"), "backtest"),  # F-02 retired (#705)
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


def test_bars_files_of_two_string_encodings_are_read_together(tmp_path: Path) -> None:
    """When one bars file writes `instrument_id` dictionary-encoded and another plain (the same
    TDS 3.2 type) and `coverage` is left out, then F-03 counts the same rows as with it (F-02,
    which counted sessions, retired, #705)."""
    path = make_snapshot(tmp_path / "s", preset="tiny", degrade=["sparse_bars"])
    backtest = CapabilityRequest(frozenset({"backtest"}))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # F-03's E30
        declared = open_snapshot(DataConfig(path=path), required=backtest).fallbacks
        data = json.loads((path / "tds.json").read_text(encoding="utf-8"))
        no_coverage(data)
        bars = next(d for d in data["datasets"] if d["kind"] == "bars")
        first = bars["files"][0]
        table = pq.read_table(path / first["path"])
        at = table.schema.get_field_index(ID_COLUMN)
        pq.write_table(table.set_column(at, ID_COLUMN, table[ID_COLUMN].dictionary_encode()),
                       path / first["path"])  # fmt: skip
        first["bytes"] = (path / first["path"]).stat().st_size
        (path / "tds.json").write_text(json.dumps(data), encoding="utf-8")
        write_hashes(path)
        assert open_snapshot(DataConfig(path=path), required=backtest).fallbacks == declared
