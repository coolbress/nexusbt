"""#568: the bars' extent (spec 4.5 F-02, F-03, F-15) is read from the bars files only when a
fallback uses it, and once per open. A test counts the engine's Parquet row reads of the bars
files: `read_table` and `ParquetFile`. The footer (`read_schema`, `read_metadata`) is not
counted: whether `obs_status` is a column decides F-03, so it is read at every open."""

from __future__ import annotations

import json
import warnings
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq
import pytest

from nexusbt.data import CapabilityRequest, DataConfig, open_snapshot
from nexusbt.testing.synth import make_snapshot
from nexusbt_tds import import_csv

#: The engine's Parquet entry points that read rows; each module calls them as `pq.<name>`.
ROWS = ("read_table", "ParquetFile")
FOOTER = ("read_schema", "read_metadata")
BACKTEST = CapabilityRequest(frozenset({"backtest"}))


@pytest.fixture
def reads(monkeypatch: pytest.MonkeyPatch) -> Counter[str]:
    """Path → row reads of it, through `pyarrow.parquet` (a call inside another is not counted
    again)."""
    counted: Counter[str] = Counter()
    depth = [0]

    def counting(name: str, real: Callable[..., Any]) -> Callable[..., Any]:
        def call(source: Any, *args: Any, **kwargs: Any) -> Any:
            if depth[0] == 0 and name in ROWS:
                counted[Path(str(source)).resolve().as_posix()] += 1
            depth[0] += 1
            try:
                return real(source, *args, **kwargs)
            finally:
                depth[0] -= 1

        return call

    for name in ROWS + FOOTER:  # a footer read opens a `ParquetFile` inside: not a row read
        monkeypatch.setattr(pq, name, counting(name, getattr(pq, name)))
    return counted


def bars_files(path: Path) -> list[str]:
    data = json.loads((path / "tds.json").read_text(encoding="utf-8"))
    bars = next(d for d in data["datasets"] if d["kind"] == "bars")
    return [(path / f["path"]).resolve().as_posix() for f in bars["files"]]


def without_coverage(path: Path) -> None:
    data = json.loads((path / "tds.json").read_text(encoding="utf-8"))
    for d in data["datasets"]:
        d.pop("coverage", None)
    (path / "tds.json").write_text(json.dumps(data), encoding="utf-8")


def opened(
    path: Path, reads: Counter[str], markets: tuple[str, ...],
    asked: CapabilityRequest | None = BACKTEST,
) -> dict[str, int]:  # fmt: skip
    """Open the package and read each market's calendar: the row reads of each bars file,
    counted from the open on."""
    reads.clear()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # each fallback's E30
        snap = open_snapshot(DataConfig(path=path, allow_untested=True), required=asked)
        for m in markets:
            snap.calendar(m)
    return {f: reads[f] for f in bars_files(path)}


def test_no_fallback_reads_no_bars_file(tmp_path: Path, reads: Counter[str]) -> None:
    """When a package has `calendar_sessions`, dense bars with `obs_status`, a grid source and
    no `coverage`, then opening it and reading its calendars reads no bars file."""
    path = make_snapshot(tmp_path / "s", preset="tiny", markets=("KR", "US"))
    without_coverage(path)
    assert opened(path, reads, ("KR", "US")) == dict.fromkeys(bars_files(path), 0)


#: degrade, markets, the feature asked for: each fallback whose record reads the bars' extent
#: (the cases of `test_open_without_coverage.py`).
CASES = {"F-02": (["no_sessions"], ("KR", "US"), "backtest"),
         "F-03": (["sparse_bars"], ("KR", "US"), "backtest"),
         "F-15": (["no_tick_info"], ("KR", "ZZ"), "grid")}  # fmt: skip


@pytest.mark.parametrize("case", CASES)
def test_a_fallback_reads_each_bars_file_once(
    tmp_path: Path, reads: Counter[str], case: str
) -> None:
    """When `coverage` is left out and F-02, F-03 or F-15 is taken, then opening the package
    and reading every market's calendar reads each bars file once (F-02 read it three times:
    for its extent, for its off-calendar check and again for each calendar)."""
    degrade, markets, feature = CASES[case]
    path = make_snapshot(tmp_path / "s", preset="tiny", markets=markets, degrade=degrade)
    without_coverage(path)
    asked = CapabilityRequest(frozenset({feature}))
    assert opened(path, reads, markets, asked) == dict.fromkeys(bars_files(path), 1)


def test_f02_with_coverage_reads_each_bars_file_once(tmp_path: Path, reads: Counter[str]) -> None:
    """When `coverage` is declared and F-02 is taken, then only its off-calendar check reads
    the bars, once per file."""
    path = make_snapshot(tmp_path / "s", preset="tiny", degrade=["no_sessions"])
    assert opened(path, reads, ("KR", "US")) == dict.fromkeys(bars_files(path), 1)


@pytest.mark.parametrize("case", CASES)
def test_fallbacks_warnings_and_calendars_are_those_of_the_declared_coverage(
    tmp_path: Path, case: str
) -> None:
    """When `coverage` is left out, then the fallbacks recorded, their E30 warnings and every
    market's calendar are those of the package with its `coverage`, which reads no extent."""
    degrade, markets, feature = CASES[case]
    path = make_snapshot(tmp_path / "s", preset="tiny", markets=markets, degrade=degrade)
    cfg, asked = DataConfig(path=path, allow_untested=True), CapabilityRequest(frozenset({feature}))

    def seen() -> tuple[Any, ...]:
        with warnings.catch_warnings(record=True) as said:
            warnings.simplefilter("always")
            snap = open_snapshot(cfg, required=asked)
            days = {m: snap.calendar(m).dates.tolist() for m in markets}
        e30 = [str(w.message) for w in said if "fallback" in str(w.message)]
        return snap.fallbacks, e30, days

    declared = seen()
    without_coverage(path)
    assert declared[1]  # each case says its E30
    assert seen() == declared


#: TDS chapter 7's two CSVs and their mapping, as `test_open_without_coverage.py` imports them.
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


def test_imported_package_reads_no_bars_file_at_open(tmp_path: Path, reads: Counter[str]) -> None:
    """When `tds import csv` writes a package (with `coverage`, #566) and it is opened with
    every feature it can give and its calendar read, then no bars file is read: the calendar
    F-02 synthesizes is bounded by the declared extent."""
    for name, text in (("instruments.csv", INSTRUMENTS), ("bars.csv", BARS),
                       ("mapping.yaml", MINIMAL)):  # fmt: skip
        (tmp_path / name).write_text(text, encoding="utf-8")
    pkg = import_csv(tmp_path / "mapping.yaml", tmp_path / "pkg")
    assert opened(pkg, reads, ("US",), None) == dict.fromkeys(bars_files(pkg), 0)
