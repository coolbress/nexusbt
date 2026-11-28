"""A package `tds import csv` writes, opened by the engine: `Price.close` is the source's close.

#736 wrote `obs_status = missing` on the rows it filled and left the source's rows null; the
engine read a null `obs_status` as `missing` and hid every close (#725 Decisions 128 to 131).
A null `obs_status` states nothing: the row's values are read as stored."""

from __future__ import annotations

import importlib
from pathlib import Path

import numpy as np
import pytest

from nexusbt.data import DataConfig, open_snapshot
from nexusbt_tds import import_csv
from nexusbt_tds.check import CheckResult

INSTRUMENTS = """instrument_id,asset_class,market,calendar_id,currency,listed_on,lot_size,\
multiplier,is_synthetic
XNYS:AAPL,equity,US,XNYS,USD,2024-01-02,1,1,false
XNYS:MSFT,equity,US,XNYS,USD,2024-01-02,1,1,false
"""
MARKET = 'code: US, calendar_id: XNYS, currency: USD, timezone: America/New_York, open: "09:30"'
MAPPING = f"""profiles: [tds:minimal-daily@1.0]
market: {{{MARKET}, close: "16:00"}}
datasets:
  instruments:
    file: instruments.csv
  bars:
    file: bars.csv
    params: {{freq: 1d, price_basis: total_adjusted}}
"""
DAYS = np.array(["2024-01-02", "2024-01-03", "2024-01-04"], dtype="datetime64[D]")
NAN = float("nan")


@pytest.fixture(autouse=True)
def unchecked(monkeypatch: pytest.MonkeyPatch) -> None:
    """The import's own `full` would refuse the S006 and V004 packages here (#866); these
    tests are of what the engine reads from them, so the import keeps them."""
    passed = CheckResult(level="full", errors=(), warnings=())
    module = importlib.import_module("nexusbt_tds.import_csv")  # the package's name: a function
    # by keyword: a positional "check" before a value reads as `tds check P` (2.7's trace)
    monkeypatch.setattr(module, name="check", value=lambda *_, **__: passed)


def closes(tmp_path: Path, bars: str) -> list[list[float]]:
    for name, text in (("instruments.csv", INSTRUMENTS), ("bars.csv", bars),
                       ("mapping.yaml", MAPPING)):  # fmt: skip
        (tmp_path / name).write_text(text, encoding="utf-8")
    package = import_csv(tmp_path / "mapping.yaml", tmp_path / "pkg")
    block = open_snapshot(DataConfig(path=package)).market_block("US", ["close"], DAYS)
    assert block.instrument_ids == ("XNYS:AAPL", "XNYS:MSFT")
    return [list(r) for r in block.values["close"]]


@pytest.mark.parametrize(
    ("bars", "expected"),
    [
        (  # close only, no day missing: nothing filled, no obs_status column
            "instrument_id,session_date,close\nXNYS:AAPL,2024-01-02,10\nXNYS:AAPL,2024-01-03,11\n"
            "XNYS:AAPL,2024-01-04,12\nXNYS:MSFT,2024-01-02,20\nXNYS:MSFT,2024-01-03,21\n"
            "XNYS:MSFT,2024-01-04,22\n",
            [[10, 20], [11, 21], [12, 22]],
        ),
        (  # close only, MSFT's 3rd missing: filled `missing`, the source's rows null
            "instrument_id,session_date,close\nXNYS:AAPL,2024-01-02,10\nXNYS:AAPL,2024-01-03,11\n"
            "XNYS:AAPL,2024-01-04,12\nXNYS:MSFT,2024-01-02,20\nXNYS:MSFT,2024-01-04,22\n",
            [[10, 20], [11, NAN], [12, 22]],
        ),
        (  # the source gives obs_status, some null: a stated `missing` hides, a null states none
            "instrument_id,session_date,close,obs_status\nXNYS:AAPL,2024-01-02,10,traded\n"
            "XNYS:AAPL,2024-01-03,11,\nXNYS:AAPL,2024-01-04,12,missing\n"
            "XNYS:MSFT,2024-01-02,20,\nXNYS:MSFT,2024-01-03,21,traded\nXNYS:MSFT,2024-01-04,,\n",
            [[10, 20], [11, 21], [NAN, NAN]],
        ),
        (  # a value outside TDS 5.5's four (S006 at `schema`) is hidden, not taken as unstated
            "instrument_id,session_date,close,obs_status\nXNYS:AAPL,2024-01-02,10,traded\n"
            "XNYS:AAPL,2024-01-03,11,trade\nXNYS:AAPL,2024-01-04,12,traded\n"
            "XNYS:MSFT,2024-01-02,20,traded\nXNYS:MSFT,2024-01-03,21,traded\n"
            "XNYS:MSFT,2024-01-04,22,traded\n",
            [[10, 20], [NAN, 21], [12, 22]],
        ),
    ],
)  # fmt: skip
def test_price_close_is_the_imported_close(
    tmp_path: Path, bars: str, expected: list[list[float]]
) -> None:
    np.testing.assert_array_equal(closes(tmp_path, bars), expected)
