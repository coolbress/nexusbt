"""#584, #705: bars without `volume` or `value_traded`, read through `nx.run_pipeline`: E18 for
a term that reads them (4.4 step 3; F-18, the fallback once here, retired).

`degrade=["no_volume"]` leaves both columns out (4.8); a package with `volume` and without
`value_traded`, the generator cannot write, is `tiny` with that column dropped by the root
`conftest.py`'s `package_without_bars_column`."""

from __future__ import annotations

import datetime as dt
import json
import math
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


def run(root: Path, terms: dict[str, Any]) -> dict[str, list[Any]]:
    """`terms` on DAY through `run_pipeline` (no warning: the suite makes any an error)."""
    result = nx.run_pipeline(nx.Pipeline(terms), start=DAY, end=DAY, snapshot=str(root))
    return {k: result.table[k].to_pylist() for k in terms}


@pytest.mark.parametrize("term", ["volume", "volume_unadjusted"])
def test_a_term_over_volume_a_minimal_package_lacks_is_e18(term: str, tmp_path: Path) -> None:
    """#705 (48 (c)): `no_volume` declares minimal-daily, which does not require `volume`; it
    opens with no fallback, and a term reading `volume` is E18, not NaN or `ArrowInvalid`."""
    root = make_snapshot(tmp_path / "p", preset="tiny", degrade=["no_volume"])
    assert not nx.open(str(root)).fallbacks
    with pytest.raises(nx.CapabilityError, match=rf"Price\.{term} is not in snapshot .* volume"):
        run(root, {"v": getattr(nx.Price, term).latest})


@pytest.mark.parametrize("term", [nx.Price.value_traded.latest, AverageTradedValue(3)],
                         ids=["value_traded", "atv"])  # fmt: skip
def test_a_term_over_value_traded_the_bars_lack_is_e18(
    term: Any, tmp_path: Path, package_without_bars_column: Callable[[Path, str], None]
) -> None:
    """#705 (F-18 retired): bars with `volume` and without `value_traded` open with no fallback;
    a term reading `value_traded` is E18 saying what to do, and one reading `volume` runs."""
    root = make_snapshot(tmp_path / "p", preset="tiny", markets=("KR",))
    package_without_bars_column(root, "value_traded")
    assert not nx.open(str(root)).fallbacks
    with pytest.raises(nx.CapabilityError) as raised:
        run(root, {"t": term})
    fix = "use a package whose bars hold value_traded, or a graph that does not read it"
    assert fix in str(raised.value)  # no profile requires it, so none is named (#705)
    assert "AverageDollarVolume" not in str(raised.value)
    assert run(root, {"v": nx.Price.volume.latest})["v"] == bars_on(root, "volume")


def test_tiny_has_value_traded_and_no_fallback(tmp_path: Path) -> None:
    """4.8 (3): `tiny`'s `value_traded` is volume x (high + low + close) / 3, read with no
    warning at all (`filterwarnings = error`)."""
    root = make_snapshot(tmp_path / "p", preset="tiny", markets=("KR",))
    got = nx.run_pipeline(nx.Pipeline({"t": nx.Price.value_traded.latest}), start=DAY, end=DAY,
                          snapshot=str(root)).table["t"].to_pylist()  # fmt: skip
    v, h, lo, c = (bars_on(root, k) for k in ("volume", "high", "low", "close"))
    assert got == [a * (b + d + e) / 3 for a, b, d, e in zip(v, h, lo, c, strict=True)]


def traded(root: Path, screen: Any = None) -> nx.PipelineResult:
    """The three terms over traded value on two sessions with a three-row window."""
    terms = {"adv": AverageDollarVolume(3), "atv": AverageTradedValue(3), "vwap": VWAP(3)}
    return nx.run_pipeline(nx.Pipeline(terms, screen=screen), start="2020-01-13",
                           end="2020-01-14", snapshot=str(root))  # fmt: skip


@pytest.mark.parametrize("term", [AverageDollarVolume(3), VWAP(3)], ids=["adv", "vwap"])
def test_terms_over_volume_are_e18_without_it(term: Any, tmp_path: Path) -> None:
    """#705: on `no_volume`, `AverageDollarVolume` and `VWAP` read `volume` it holds no value
    of: E18 at graph build (once NaN in every cell, with F-18)."""
    root = make_snapshot(tmp_path / "p", preset="tiny", degrade=["no_volume"])
    with pytest.raises(nx.CapabilityError):
        nx.run_pipeline(nx.Pipeline({"x": term}), start=DAY, end=DAY, snapshot=str(root))


def test_adv_over_a_market_without_volume_is_e18(
    tmp_path: Path, package_without_bars_column: Callable[..., None]
) -> None:
    """#667, #705: KR's files hold `volume` null in every row, US's hold it: a run reading
    `AverageDollarVolume` over KR is E18, over US the whole package's values."""
    whole = make_snapshot(tmp_path / "w", preset="tiny")
    root = make_snapshot(tmp_path / "p", preset="tiny")
    # null, not left out: some files without it break TDS 3.6, E14 at open (#705)
    package_without_bars_column(root, "volume", market="KR", null=True)
    with pytest.raises(ValueError, match="market 'JP'"):  # a market no file has
        package_without_bars_column(root, "volume", market="JP")
    with pytest.raises(nx.CapabilityError, match="the bars of market KR hold no value of volume"):
        traded(root)
    us = nx.run_pipeline(nx.Pipeline({"adv": AverageDollarVolume(3)}), start="2020-01-13",
                         end="2020-01-14", markets=["US"], snapshot=str(root)).table  # fmt: skip
    before = traded(whole).table.filter(pc.equal(traded(whole).table["market"], "US"))
    assert us["adv"].to_pylist() == before["adv"].to_pylist()


START, END = dt.date(2019, 12, 2), dt.date(2020, 1, 31)  # bars files year=2019 and year=2020
SPLIT = "nexusbt.compute._chunks.spans"


def adv(root: Path, start: str, end: str) -> pa.Table:
    """`AverageDollarVolume(3)` and `Price.volume.latest` in one pipeline (one block per
    chunk, read by both)."""
    terms = {"adv": AverageDollarVolume(3), "v": nx.Price.volume.latest}
    result = nx.run_pipeline(nx.Pipeline(terms), start=start, end=end, snapshot=str(root))
    assert result.term_diagnostics.num_rows == 0
    return result.table


def by_session(table: pa.Table, column: str) -> dict[dt.date, list[float]]:
    found: dict[dt.date, list[float]] = {}
    for day, value in zip(table["session_date"].to_pylist(), table[column].to_pylist(),
                          strict=True):  # fmt: skip
        found.setdefault(day, []).append(value)
    return found


def test_adv_per_cell_equal_over_chunks(
    tmp_path: Path, package_without_bars_column: Callable[..., None],
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    """INV-03 for #688 (P-CHUNK's KINDS has no `AverageDollarVolume`): a run cut into chunks
    at 2020's first session and at each later week equals the run in one chunk, bit for bit,
    the second chunk's windows reading the first chunk's bars of the file whose `volume` is
    null in every row; those windows average their known cells (#705 Decisions 57, which
    narrows #688)."""
    root = make_snapshot(tmp_path / "p", preset="small", markets=("KR",), n_kr=3, start=START,
                         end=END)  # fmt: skip
    package_without_bars_column(root, "volume", year=2019, null=True)  # 3.6 (#705)
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
    assert math.isfinite(by_session(one, "adv")[dt.date(2020, 1, 2)][0])
    assert math.isfinite(by_session(one, "adv")[dt.date(2020, 1, 6)][0])


def test_no_volume_drops_the_core_declaration(tmp_path: Path) -> None:
    """4.8: `no_volume` breaks TDS 7's OHLCV, so the package no longer declares core."""
    root = make_snapshot(tmp_path / "p", preset="tiny", markets=("KR",), degrade=["no_volume"])
    declared = json.loads((root / "tds.json").read_text(encoding="utf-8"))["profiles"]
    assert CORE not in declared
    assert CORE in json.loads((make_snapshot(tmp_path / "w", preset="tiny", markets=("KR",))
                               / "tds.json").read_text(encoding="utf-8"))["profiles"]  # fmt: skip
