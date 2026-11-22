"""#583: the `Price` columns 3.2 derives from bars `close` and `volume`, and `open`, `high`,
`low` a package leaves out (4.5 F-01), read through `nx.run_pipeline`."""

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
import pyarrow.parquet as pq
import pytest
import yaml

import nexusbt as nx
from nexusbt.testing import synth
from nexusbt.testing.synth import make_snapshot, read
from nexusbt_tds.hash import write_hashes

DAY = "2020-01-06"
GOLDEN = Path(__file__).parents[2] / "golden" / "cases"
OHL = ("open", "high", "low")
#: `small` KR's `KR:T00004` goes ex a cash dividend on 2019-05-24 (halted that day and the
#: next); the window 2019-05-20 .. 2019-05-28 is seven sessions.
STOCK, LAST = "KR:T00004", "2019-05-28"
HALTED, NO_TRADE = dt.date(2019, 5, 20), dt.date(2019, 5, 21)  # each keeps its close


def total_at(package: Path, day: dt.date) -> float:
    """`STOCK`'s running total factor on `day`: the product of the total steps the generator
    applied to its prices on or before it (`synth.APPLIED`, #705), the engine's resolver not
    asked, as the bars' `cum_factor_total` held it before #705."""
    out = 1.0
    for iid, ex, basis, factor, _ in synth.APPLIED[package.resolve()]["KR"]:
        if (iid, basis) == (STOCK, "total") and ex <= day:
            out *= factor
    return out


@pytest.fixture(autouse=True)
def no_toml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)  # no `nexusbt.toml`: the defaults apply


def run(root: Path, terms: dict[str, Any], day: str = DAY) -> dict[str, dict[str, Any]]:
    """`terms` at `day` through `run_pipeline`: column → instrument → value."""
    table = nx.run_pipeline(nx.Pipeline(terms), start=day, end=day, snapshot=str(root)).table
    ids = table["instrument_id"].to_pylist()
    return {k: dict(zip(ids, table[k].to_pylist(), strict=True)) for k in terms}


def latest(root: Path, column: str, day: str = DAY) -> dict[str, Any]:
    return run(root, {"x": getattr(nx.Price, column).latest}, day)["x"]


def bars_on(root: Path, column: str, day: str = DAY) -> dict[str, Any]:
    bars = read(root, "bars_1d")
    bars = bars.filter(pc.equal(bars["session_date"], dt.date.fromisoformat(day)))
    return dict(zip(bars["instrument_id"].to_pylist(), bars[column].to_pylist(), strict=True))


def rewrite(root: Path, kind: str, change: Callable[[dict[str, Any]], Any]) -> None:
    """Each row of the `kind` dataset through `change` (None drops it), hashes written again."""
    data = json.loads((root / "tds.json").read_text(encoding="utf-8"))
    for f in next(d for d in data["datasets"] if d["kind"] == kind)["files"]:
        table = pq.read_table(part := root / f["path"])
        rows = [r for r in map(change, table.to_pylist()) if r is not None]
        pq.write_table(pa.Table.from_pylist(rows, schema=table.schema), part)
        f.update(bytes=part.stat().st_size, rows=len(rows))
    (root / "tds.json").write_text(json.dumps(data), encoding="utf-8")
    write_hashes(root)


def without_ohl(root: Path, market: str, *, drop: bool, stats: bool = True) -> None:
    """`market`'s bars files without `open`, `high`, `low` (`drop`) or with them null in every
    row; `stats=False` writes them without footer statistics."""
    data = json.loads((root / "tds.json").read_text(encoding="utf-8"))
    entry = next(d for d in data["datasets"] if d["kind"] == "bars")
    for f in (f for f in entry["files"] if f"market={market}" in f["path"]):
        table = pq.read_table(part := root / f["path"])
        for c in OHL:
            at = table.schema.get_field_index(c)
            table = table.set_column(at, c, pa.nulls(len(table), pa.float64()))
        table = table.drop_columns(list(OHL)) if drop else table
        pq.write_table(table, part, write_statistics=stats)
        f["bytes"] = part.stat().st_size
    (root / "tds.json").write_text(json.dumps(data), encoding="utf-8")
    write_hashes(root)


@pytest.fixture(scope="module")
def tiny(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return make_snapshot(tmp_path_factory.mktemp("tiny") / "p", preset="tiny", markets=("KR",))


@pytest.fixture(scope="module")
def small(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """`small` KR, `STOCK` halted on `HALTED` and without trades on `NO_TRADE` (volume null),
    both bars keeping their close."""
    root = make_snapshot(tmp_path_factory.mktemp("small") / "p", preset="small", markets=("KR",))
    edits: dict[dt.date, dict[str, Any]] = {
        HALTED: {"obs_status": "halted"},
        NO_TRADE: {"obs_status": "no_trade", "volume": None},
    }
    rewrite(root, "bars", lambda r: r | edits.get(r["session_date"], {})
            if r["instrument_id"] == STOCK else r)  # fmt: skip
    return root


def window_cells(root: Path, column: str, size: int, day: str) -> list[float]:
    """`STOCK`'s `Price.<column>` window of `size` rows ending at `day`, as `day` reads it: the
    first cell of the window of k rows, k = size .. 1, through one `run_pipeline`."""

    def first(x: Any) -> Any:
        return x[0]

    terms = {f"w{k}": nx.factor(window=k, inputs=[getattr(nx.Price, column)])(first)
             for k in range(size, 0, -1)}  # fmt: skip
    found = run(root, terms, day)
    return [found[f"w{k}"][STOCK] for k in range(size, 0, -1)]


@pytest.mark.parametrize(
    ("column", "source"),
    [("close_tr", "close"), ("close_unadjusted", "close"), ("volume_unadjusted", "volume")],
)
def test_derived_columns_read_their_bars_source(tiny: Path, column: str, source: str) -> None:
    """3.2: a window of one row has no event inside, so the value is the bar's source column."""
    assert latest(tiny, column) == pytest.approx(bars_on(tiny, source), nan_ok=True)


def test_close_tr_window_with_a_dividend_is_3_2_formula(small: Path) -> None:
    """3.2: a `close_tr` window over an ex date is `raw[s]·C_total[t]/C_total[s]`, computed here
    from the package's bars `close` and the total steps the generator applied to them (its
    record, #705), NaN where halted or missing; the same window of `close`, split-adjusted
    only, differs before the ex date."""
    bars = read(small, "bars_1d").filter(pc.field("instrument_id") == STOCK)
    bars = bars.filter((pc.field("session_date") >= HALTED)
                       & (pc.field("session_date") <= dt.date.fromisoformat(LAST)))  # fmt: skip
    raw = np.array(bars["close"].to_pylist(), dtype=float)
    total = np.array([total_at(small, d) for d in bars["session_date"].to_pylist()])
    hidden = np.isin(bars["obs_status"].to_pylist(), ["halted", "missing"])
    assert len(raw) == 7
    assert total[0] != total[-1]  # the dividend lies in the window
    found = window_cells(small, "close_tr", 7, LAST)
    assert found == pytest.approx(np.where(hidden, np.nan, raw * total[-1] / total), nan_ok=True)
    assert window_cells(small, "close", 7, LAST)[1] != pytest.approx(found[1])


def test_halted_session_hides_derived_prices(small: Path) -> None:
    """3.2: a halted session's price cells are NaN, its bar's close notwithstanding."""
    assert bars_on(small, "close", str(HALTED))[STOCK] is not None
    for column in ("close_tr", "close_unadjusted"):
        assert math.isnan(latest(small, column, str(HALTED))[STOCK])


def test_no_trade_session_keeps_its_close(small: Path) -> None:
    """3.2: a session without trades takes its close, as stored in `close_unadjusted` and
    adjusted to t in a `close_tr` window (the dividend after it applies)."""
    close = bars_on(small, "close", str(NO_TRADE))[STOCK]
    assert latest(small, "close_unadjusted", str(NO_TRADE))[STOCK] == close
    then, now = (total_at(small, d) for d in (NO_TRADE, dt.date.fromisoformat(LAST)))
    assert window_cells(small, "close_tr", 6, LAST)[0] == pytest.approx(close * now / then)


def test_no_trade_session_volume_unadjusted_is_zero(small: Path) -> None:
    """3.2: a session without trades has volume 0, its bar's null volume notwithstanding."""
    assert bars_on(small, "volume", str(NO_TRADE))[STOCK] is None
    assert latest(small, "volume_unadjusted", str(NO_TRADE))[STOCK] == 0.0


def test_t12_returns_on_its_default_input(tmp_path: Path) -> None:
    """T-12 (8.2) through `run_pipeline`: `Returns(232).shift(21)` on its default input
    `close_tr` (3.4). `tiny` is too short, so `small` KR over 263+ sessions, one instrument
    with no event, its close P[i] = 100 + i by axis row i and halted at row 240."""
    case = yaml.safe_load((GOLDEN / "T-12.yaml").read_text())
    root = make_snapshot(tmp_path / "p", preset="small", markets=("KR",), n_kr=4,
                         start=dt.date(2018, 1, 2), end=dt.date(2019, 3, 29))  # fmt: skip
    dates = [str(d) for d in nx.open(str(root)).calendar("KR").dates]
    listed = sorted(read(root, "instruments").to_pylist(), key=lambda r: r["instrument_id"])
    one = next(r["instrument_id"] for r in listed
               if str(r["listed_on"]) <= dates[0] and r.get("delisted_on") is None)  # fmt: skip
    rewrite(root, "corporate_actions", lambda r: None if r["instrument_id"] == one else r)

    def change(row: dict[str, Any]) -> dict[str, Any]:
        i = dates.index(str(row["session_date"]))
        return row if row["instrument_id"] != one else row | {
            "close": None if i == 240 else 100.0 + i,
            "obs_status": "halted" if i == 240 else "traded"}  # fmt: skip

    rewrite(root, "bars", change)
    pipe = nx.Pipeline({"m": nx.factors.Returns(232).shift(21)})
    table = nx.run_pipeline(pipe, start=dates[251], end=dates[262], snapshot=str(root)).table
    mine = table.filter(pc.field("instrument_id") == one)
    found = dict(zip(map(str, mine["session_date"].to_pylist()), mine["m"].to_pylist(),
                     strict=True))  # fmt: skip
    for row in case["expected"]:
        got = found[dates[row["row"]]]
        assert got == pytest.approx(row["returns_232_shift_21"], abs=5e-7, nan_ok=True), row


def test_close_tr_refused_on_adjusted_prices(tmp_path: Path, monkeypatch: Any) -> None:
    """4.3: on an adjusted-price package `close_tr` is E18 before any value is computed;
    `close` is the package's value."""
    from nexusbt.compute._executor import _Chunk

    root = make_snapshot(tmp_path / "p", preset="tiny", markets=("KR",))
    data = json.loads((root / "tds.json").read_text(encoding="utf-8"))
    data["profiles"] = ["tds:minimal-daily@1.0"]
    bars = next(d for d in data["datasets"] if d["kind"] == "bars")
    bars["params"]["price_basis"] = "total_adjusted"
    (root / "tds.json").write_text(json.dumps(data), encoding="utf-8")
    write_hashes(root)
    computed: list[object] = []
    monkeypatch.setattr(_Chunk, "compute", lambda *a: computed.append(a))
    with pytest.raises(nx.CapabilityError, match="economic labels need raw prices") as refused:
        latest(root, "close_tr")
    assert "price_basis = total_adjusted" in str(refused.value)
    assert not computed
    monkeypatch.undo()
    assert latest(root, "close") == pytest.approx(bars_on(root, "close"), nan_ok=True)


def test_a_market_whose_files_hold_no_open_is_e18_when_a_run_over_it_reads_it(
    tmp_path: Path,
) -> None:
    """#705 (2026-11-22, F-01 retired): US's files hold `open`, `high`, `low` null in every row,
    KR's hold them. The package opens without a fallback; a run over US reading `open` is E18
    naming the market, before any value; KR's run reads its opens."""
    root = make_snapshot(tmp_path / "p", preset="tiny")
    without_ohl(root, "US", drop=False)
    assert not nx.open(str(root)).fallbacks
    with pytest.raises(nx.CapabilityError, match="the bars of market US hold no value of open"):
        run(root, {"o": nx.Price.open.latest})
    kr = nx.run_pipeline(nx.Pipeline({"o": nx.Price.open.latest}), start=DAY, end=DAY,
                         markets=["KR"], snapshot=str(root)).table["o"].to_pylist()  # fmt: skip
    assert kr
    assert not any(math.isnan(v) for v in kr)


@pytest.mark.parametrize("column", OHL)
def test_a_term_over_a_column_left_out_is_e18_before_any_value(
    column: str, tmp_path: Path, monkeypatch: Any
) -> None:
    """#705 Decisions 48 (c): a minimal-daily package whose bars files leave out `open`, `high`
    and `low` opens, and a run reading one stops with E18 naming the
    column and the profile that holds it, before any chunk is computed (not NaN, not pyarrow's
    `ArrowInvalid`)."""
    from nexusbt.compute import _chunks

    root = make_snapshot(tmp_path / "p", preset="tiny", markets=("KR",), degrade=["no_ohlc"])
    without_ohl(root, "KR", drop=True)
    computed: list[object] = []

    def spans(*args: object) -> list[tuple[int, int]]:
        computed.append(args)
        return []

    monkeypatch.setattr(_chunks, "spans", spans)
    pipe = nx.Pipeline({"c": nx.Price.close.latest, "x": getattr(nx.Price, column).latest})
    with pytest.raises(nx.CapabilityError) as raised:
        nx.run_pipeline(pipe, start=DAY, end="2020-01-10", snapshot=str(root))
    text = str(raised.value)
    assert text.startswith("CapabilityError [E18]")
    assert f"Price.{column} is not in snapshot" in text
    assert "tds:equity-daily-core@1.0 requires it" in text
    assert not computed


@pytest.mark.parametrize("drop", [True, False], ids=["left out", "null"])
def test_one_year_file_without_open(drop: bool, tmp_path: Path) -> None:
    """#705 (2026-11-22): 2019's file without `open`, `high`, `low`, 2020's with them, breaks
    TDS 3.6 (every file of a dataset has the same columns): E14 at open, whatever the profile.
    The same columns null in every row of 2019's file are data, as a halted session's null is:
    the package opens and 2019's opens read NaN."""
    root = make_snapshot(tmp_path / "p", preset="small", markets=("KR",), n_kr=2,
                         start=dt.date(2019, 12, 2), end=dt.date(2020, 1, 31))  # fmt: skip
    data = json.loads((root / "tds.json").read_text(encoding="utf-8"))
    bars = next(d for d in data["datasets"] if d["kind"] == "bars")
    [f2019] = [f for f in bars["files"] if "year=2019" in f["path"]]
    table = pq.read_table(part := root / f2019["path"])
    for c in OHL:
        table = table.set_column(table.schema.get_field_index(c), c, pa.nulls(len(table)))
    pq.write_table(table.drop_columns(list(OHL)) if drop else table, part)
    f2019["bytes"] = part.stat().st_size
    (root / "tds.json").write_text(json.dumps(data), encoding="utf-8")
    write_hashes(root)
    if drop:
        with pytest.raises(nx.SnapshotError, match="has no column high, low, open, which other"):
            nx.open(str(root))
        return
    found = latest(root, "open", day="2019-12-30")
    assert found
    assert all(math.isnan(v) for v in found.values())


def test_a_column_without_footer_statistics_is_read_then_e18(tmp_path: Path) -> None:
    """Without footer statistics, null in every row is not in the footer, so open reads that
    one column (#705 Decisions 50): null in every row, a run reading it is E18, never NaN
    passed on in silence."""
    root = make_snapshot(tmp_path / "p", preset="tiny", markets=("KR",), degrade=["no_ohlc"])
    without_ohl(root, "KR", drop=False, stats=False)
    with pytest.raises(nx.CapabilityError, match=r"Price\.open is not in snapshot"):
        latest(root, "open")
