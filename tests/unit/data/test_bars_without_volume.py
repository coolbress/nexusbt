"""#584: bars without `volume` or `value_traded` (4.5 F-18), read through `nx.run_pipeline`.

`degrade=["no_volume"]` leaves both columns out (4.8); a package with `volume` and without
`value_traded`, the generator cannot write, is `tiny` with that column dropped by the root
`conftest.py`'s `package_without_bars_column`."""

from __future__ import annotations

import datetime as dt
import json
import math
import warnings
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pytest

import nexusbt as nx
from nexusbt.factors import VWAP, AverageDollarVolume, AverageTradedValue
from nexusbt.testing.synth import make_snapshot, read

pytestmark = pytest.mark.unit
DAY = "2020-01-06"
CORE = "tds:equity-daily-core@1.0"


@pytest.fixture(autouse=True)
def no_toml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)  # no `nexusbt.toml`: the defaults apply


def bars_on(root: Path, column: str) -> list[Any]:
    """`column` of the bars on DAY, in instrument order (the order of a pipeline's rows)."""
    bars = read(root, "bars_1d")
    bars = bars.filter(pc.equal(bars["session_date"], dt.date.fromisoformat(DAY)))
    return [v for _, v in sorted(zip(bars["instrument_id"].to_pylist(),
                                     bars[column].to_pylist(), strict=True))]  # fmt: skip


def run(root: Path, terms: dict[str, Any]) -> tuple[dict[str, list[Any]], list[str]]:
    """`terms` on DAY through `run_pipeline`, with the F-18 warnings it gave."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = nx.run_pipeline(nx.Pipeline(terms), start=DAY, end=DAY, snapshot=str(root))
    said = [str(w.message) for w in caught if "F-18" in str(w.message)]
    return {k: result.table[k].to_pylist() for k in terms}, said


def records(root: Path) -> set[tuple[str, str | None]]:
    with pytest.warns(UserWarning, match=r"\[E30\] F-18"):
        return {(r.market, r.column) for r in nx.open(str(root)).fallbacks if r.id == "F-18"}


def test_no_volume_reads_nan_with_one_f18(tmp_path: Path) -> None:
    """`no_volume`: `Price.volume`, `volume_unadjusted` and `value_traded` NaN, not pyarrow's
    `ArrowInvalid`, with one E30 at open and a record for each market and column."""
    root = make_snapshot(tmp_path / "p", preset="tiny", degrade=["no_volume"])
    got, said = run(root, {"v": nx.Price.volume.latest, "u": nx.Price.volume_unadjusted.latest,
                           "t": nx.Price.value_traded.latest})  # fmt: skip
    assert set(bars_on(root, "obs_status")) == {"traded"}  # no `no_trade` 0 (3.2) on DAY
    for column in ("v", "u", "t"):
        assert got[column]
        assert all(math.isnan(x) for x in got[column]), column
    [message] = said
    assert all(message.count(f"market {m}, column {c}") == 1
               for m in ("KR", "US") for c in ("volume", "value_traded"))  # fmt: skip
    assert records(root) == {(m, c) for m in ("KR", "US") for c in ("volume", "value_traded")}


def test_value_traded_alone_left_out(
    tmp_path: Path, package_without_bars_column: Callable[[Path, str], None]
) -> None:
    """Bars with `volume` and without `value_traded`: that column NaN, `volume` as stored, one
    E30 naming `value_traded` only."""
    root = make_snapshot(tmp_path / "p", preset="tiny", markets=("KR",))
    package_without_bars_column(root, "value_traded")
    got, said = run(root, {"v": nx.Price.volume.latest, "t": nx.Price.value_traded.latest})
    assert all(math.isnan(x) for x in got["t"])
    assert got["v"] == bars_on(root, "volume")
    [message] = said
    assert "market KR, column value_traded" in message
    assert "column volume," not in message
    assert records(root) == {("KR", "value_traded")}


def test_graph_without_the_column_runs_as_before(tmp_path: Path) -> None:
    """A graph that reads neither column gives what it gives on the whole package, with the
    same one E30."""
    whole = make_snapshot(tmp_path / "w", preset="tiny", markets=("KR",))
    gone = make_snapshot(tmp_path / "g", preset="tiny", markets=("KR",), degrade=["no_volume"])
    before, none = run(whole, {"c": nx.Price.close.latest})
    after, said = run(gone, {"c": nx.Price.close.latest})
    assert not none
    assert after == before
    [message] = said
    assert all(f"market KR, column {c}" in message for c in ("volume", "value_traded"))
    assert records(gone) == {("KR", "volume"), ("KR", "value_traded")}


def test_tiny_has_value_traded_and_no_fallback(tmp_path: Path) -> None:
    """4.8 (3): `tiny`'s `value_traded` is volume x (high + low + close) / 3, read with no
    warning at all (`filterwarnings = error`)."""
    root = make_snapshot(tmp_path / "p", preset="tiny", markets=("KR",))
    got = nx.run_pipeline(nx.Pipeline({"t": nx.Price.value_traded.latest}), start=DAY, end=DAY,
                          snapshot=str(root)).table["t"].to_pylist()  # fmt: skip
    v, h, lo, c = (bars_on(root, k) for k in ("volume", "high", "low", "close"))
    assert got == [a * (b + d + e) / 3 for a, b, d, e in zip(v, h, lo, c, strict=True)]


def traded(root: Path, screen: Any = None) -> nx.PipelineResult:
    """The three terms over traded value on two sessions with a three-row window, F-18's E30
    at open left aside (the tests above read it)."""
    terms = {"adv": AverageDollarVolume(3), "atv": AverageTradedValue(3), "vwap": VWAP(3)}
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message=r".*\[E30\] F-18")
        return nx.run_pipeline(nx.Pipeline(terms, screen=screen), start="2020-01-13",
                               end="2020-01-14", snapshot=str(root))  # fmt: skip


def test_terms_over_volume_nan_without_it(tmp_path: Path) -> None:
    """#667, 4.5 F-18 and 3.4: on `no_volume` `AverageDollarVolume` is NaN in every cell, as
    `AverageTradedValue` and `VWAP` are, not `nansum` of NaN products (0.0); a missing input,
    so nothing in `term_diagnostics` (5.4.1)."""
    root = make_snapshot(tmp_path / "p", preset="tiny", degrade=["no_volume"])
    result = traded(root)
    assert result.table.num_rows
    for column in ("adv", "atv", "vwap"):
        assert all(math.isnan(x) for x in result.table[column].to_pylist()), column
    assert result.term_diagnostics.num_rows == 0


def test_adv_nan_only_in_the_market_f18_records(
    tmp_path: Path, package_without_bars_column: Callable[..., None]
) -> None:
    """#667: KR's bars without `volume`, US's with it: `AverageDollarVolume` NaN in KR alone,
    the market F-18 records; US's values as on the whole package."""
    whole = make_snapshot(tmp_path / "w", preset="tiny")
    root = make_snapshot(tmp_path / "p", preset="tiny")
    package_without_bars_column(root, "volume", market="KR")
    with pytest.raises(ValueError, match="market 'JP'"):  # a market no file has
        package_without_bars_column(root, "volume", market="JP")
    assert {m for m, c in records(root) if c == "volume"} == {"KR"}
    before, after = traded(whole).table, traded(root).table
    kr = pc.equal(after["market"], "KR")
    assert all(math.isnan(x) for x in after.filter(kr)["adv"].to_pylist())
    us = after.filter(pc.invert(kr))["adv"].to_pylist()
    assert us
    assert us == before.filter(pc.equal(before["market"], "US"))["adv"].to_pylist()
    assert all(math.isfinite(x) for x in us)


def test_adv_filter_unknown_without_volume(tmp_path: Path) -> None:
    """#667, 5.4.1: `AverageDollarVolume(3) >= 0` is unknown without `volume`, so false at the
    screen; a 0.0 would keep every row (0 >= 0)."""
    root = make_snapshot(tmp_path / "p", preset="tiny", degrade=["no_volume"])
    assert traded(root).table.num_rows
    assert traded(root, screen=AverageDollarVolume(3) >= 0).table.num_rows == 0


START, END = dt.date(2019, 12, 2), dt.date(2020, 1, 31)  # bars files year=2019 and year=2020
SPLIT = "nexusbt.compute._chunks.spans"


def adv(root: Path, start: str, end: str) -> pa.Table:
    """`AverageDollarVolume(3)` and `Price.volume.latest` in one pipeline (one block per
    chunk, read by both), the open's E30 left aside."""
    terms = {"adv": AverageDollarVolume(3), "v": nx.Price.volume.latest}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # F-18's E30, and F-03's on `sparse_bars`
        result = nx.run_pipeline(nx.Pipeline(terms), start=start, end=end, snapshot=str(root))
    assert result.term_diagnostics.num_rows == 0
    return result.table


def by_session(table: pa.Table, column: str) -> dict[dt.date, list[float]]:
    found: dict[dt.date, list[float]] = {}
    for day, value in zip(table["session_date"].to_pylist(), table[column].to_pylist(),
                          strict=True):  # fmt: skip
        found.setdefault(day, []).append(value)
    return found


def test_adv_nan_where_its_window_reads_the_file_without_volume(
    tmp_path: Path, package_without_bars_column: Callable[..., None]
) -> None:
    """#688 Decisions 1, 2: `volume` left out of the 2019 file only. `AverageDollarVolume(3)`
    is NaN at the sessions whose window reads a 2019 bar (2020's first two) and the whole
    package's value at every later one, where `Price.volume.latest` is the same number."""
    whole = make_snapshot(tmp_path / "w", preset="small", markets=("KR",), n_kr=3, start=START,
                          end=END)  # fmt: skip
    root = make_snapshot(tmp_path / "p", preset="small", markets=("KR",), n_kr=3, start=START,
                         end=END)  # fmt: skip
    package_without_bars_column(root, "volume", year=2019)
    with pytest.raises(ValueError, match="year 2018"):  # a year no file has
        package_without_bars_column(root, "volume", year=2018)
    assert records(root) == {("KR", "volume")}
    before, after = adv(whole, "2020-01-02", "2020-01-31"), adv(root, "2020-01-02", "2020-01-31")
    assert after["v"].to_pylist() == before["v"].to_pylist()
    assert all(math.isfinite(x) for x in after["v"].to_pylist())
    days = sorted(by_session(after, "adv"))
    reaching, inside = days[:2], days[2:]
    assert reaching == [dt.date(2020, 1, 2), dt.date(2020, 1, 3)]
    found, known = by_session(after, "adv"), by_session(before, "adv")
    assert all(math.isnan(x) for d in reaching for x in found[d])
    assert inside
    assert all(found[d] == known[d] for d in inside)
    assert all(math.isfinite(x) for d in inside for x in found[d])


def test_adv_per_cell_equal_over_chunks(
    tmp_path: Path, package_without_bars_column: Callable[..., None],
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    """INV-03 for #688 (P-CHUNK's KINDS has no `AverageDollarVolume`): a run cut into chunks
    at 2020's first session and at each later week equals the run in one chunk, bit for bit,
    the second chunk's windows reading the first chunk's bars of the file without `volume`."""
    root = make_snapshot(tmp_path / "p", preset="small", markets=("KR",), n_kr=3, start=START,
                         end=END)  # fmt: skip
    package_without_bars_column(root, "volume", year=2019)
    monkeypatch.setattr(SPLIT, lambda dates, *_, **__: [(0, len(dates) - 1)])
    one = adv(root, "2019-12-20", "2020-01-31")

    def weeks(dates: Any, *_: Any, **__: Any) -> list[tuple[int, int]]:
        days = list(np.asarray(dates, dtype="datetime64[D]"))
        cuts = [k for k in range(1, len(days)) if days[k].astype(object).year == 2020
                and (days[k - 1].astype(object).year == 2019 or k % 5 == 0)]  # fmt: skip
        return list(zip([0, *cuts], [c - 1 for c in cuts] + [len(days) - 1], strict=True))

    monkeypatch.setattr(SPLIT, weeks)
    cut = adv(root, "2019-12-20", "2020-01-31")
    for column in ("adv", "v"):
        assert cut[column].to_numpy().tobytes() == one[column].to_numpy().tobytes(), column
    assert math.isnan(by_session(one, "adv")[dt.date(2020, 1, 2)][0])
    assert math.isfinite(by_session(one, "adv")[dt.date(2020, 1, 6)][0])


def test_adv_window_with_no_bar_is_not_f18s(tmp_path: Path) -> None:
    """#688 Decisions (its last acceptance criterion, narrowed 2026-11-21 with the owner's
    approval): in a market whose every file lacks `volume`, a
    listed instrument's window that holds no bar at all (`sparse_bars` drops a halt's rows, so
    those sessions are missing) reads no F-18 bar: 3.4's value, 0.0, as on a package with
    `volume`; every other cell of that session is NaN."""
    root = make_snapshot(tmp_path / "p", preset="small", markets=("KR",),
                         degrade=["sparse_bars", "no_volume"])  # fmt: skip
    halt, day = "KR:T00069", "2015-03-18"  # halted 2015-03-16 to at least 03-20 before degrade
    table = adv(root, day, day)
    ids, values = table["instrument_id"].to_pylist(), table["adv"].to_pylist()
    assert halt in ids
    assert values[ids.index(halt)] == 0.0
    assert all(math.isnan(x) for i, x in zip(ids, values, strict=True) if i != halt)


def test_no_volume_drops_the_core_declaration(tmp_path: Path) -> None:
    """4.8: `no_volume` breaks TDS 7's OHLCV, so the package no longer declares core."""
    root = make_snapshot(tmp_path / "p", preset="tiny", markets=("KR",), degrade=["no_volume"])
    declared = json.loads((root / "tds.json").read_text(encoding="utf-8"))["profiles"]
    assert CORE not in declared
    assert CORE in json.loads((make_snapshot(tmp_path / "w", preset="tiny", markets=("KR",))
                               / "tds.json").read_text(encoding="utf-8"))["profiles"]  # fmt: skip
