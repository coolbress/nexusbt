"""#583: the `Price` columns 3.2 derives from bars `close` and `volume`, and `open`, `high`,
`low` a package leaves out (4.5 F-01), read through `nx.run_pipeline`."""

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
import pyarrow.parquet as pq
import pytest
import yaml

import nexusbt as nx
from nexusbt.testing.synth import make_snapshot, read
from nexusbt_tds.hash import write_hashes

DAY = "2020-01-06"
GOLDEN = Path(__file__).parents[2] / "golden" / "cases"
OHL = ("open", "high", "low")
#: `small` KR's `KR:T00004` goes ex a cash dividend on 2019-05-24 (halted that day and the
#: next); the window 2019-05-20 .. 2019-05-28 is seven sessions.
STOCK, LAST = "KR:T00004", "2019-05-28"
HALTED, NO_TRADE = dt.date(2019, 5, 20), dt.date(2019, 5, 21)  # each keeps its close


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
    from the package's bars `close` and `cum_factor_total`, NaN where halted or missing; the
    same window of `close`, split-adjusted only, differs before the ex date."""
    bars = read(small, "bars_1d").filter(pc.field("instrument_id") == STOCK)
    bars = bars.filter((pc.field("session_date") >= HALTED)
                       & (pc.field("session_date") <= dt.date.fromisoformat(LAST)))  # fmt: skip
    raw = np.array(bars["close"].to_pylist(), dtype=float)
    total = np.array(bars["cum_factor_total"].to_pylist(), dtype=float)
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
    then, now = (bars_on(small, "cum_factor_total", d)[STOCK] for d in (str(NO_TRADE), LAST))
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
            "close": None if i == 240 else 100.0 + i, "cum_factor_split": 1.0,
            "cum_factor_total": 1.0, "obs_status": "halted" if i == 240 else "traded"}  # fmt: skip

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


def f01(caught: list[warnings.WarningMessage]) -> list[str]:
    return [str(w.message) for w in caught if "F-01" in str(w.message)]


def test_f01_by_market_when_null_in_every_row(tmp_path: Path) -> None:
    """4.5 F-01, by market: US holds `open`, `high`, `low` null in every row, KR holds them;
    one E30 at open names US's three columns once each, the record is US's, KR's open read."""
    root = make_snapshot(tmp_path / "p", preset="tiny")
    without_ohl(root, "US", drop=False)
    with pytest.warns(UserWarning, match="F-01") as caught:  # E30, said at open (4.5)
        snapshot = nx.open(str(root))
    [message] = f01(caught.list)
    assert all(message.count(f"market US, column {c}") == 1 for c in OHL), message
    assert "KR" not in message
    records = {(r.market, r.column) for r in snapshot.fallbacks if r.id == "F-01"}
    assert records == {("US", c) for c in OHL}
    with pytest.warns(UserWarning, match="F-01"):  # the run opens the package again
        kr = [v for i, v in run(root, {"o": nx.Price.open.latest})["o"].items() if "KR" in i]
    assert kr
    assert not any(math.isnan(v) for v in kr)


def test_f01_once_per_run_when_columns_left_out(tmp_path: Path, monkeypatch: Any) -> None:
    """4.5 F-01: bars files without the columns give NaN, not pyarrow's `ArrowInvalid`, with
    one E30 for the run however many chunks it computes (here two)."""
    from nexusbt.compute import _chunks

    root = make_snapshot(tmp_path / "p", preset="tiny", markets=("KR",))
    without_ohl(root, "KR", drop=True)
    monkeypatch.setattr(_chunks, "spans", lambda dates, *_: [(0, 1), (2, len(dates) - 1)])
    pipe = nx.Pipeline({c: getattr(nx.Price, c).latest for c in OHL})
    with pytest.warns(UserWarning, match="F-01") as caught:
        table = nx.run_pipeline(pipe, start=DAY, end="2020-01-10", snapshot=str(root)).table
    assert len(f01(caught.list)) == 1
    assert len(table) > 5
    assert all(math.isnan(v) for c in OHL for v in table[c].to_pylist())


def test_f01_when_one_year_file_lacks_them(tmp_path: Path) -> None:
    """4.5 F-01 holds for a market when any of its files lacks the columns, not only when every
    file does: 2019's file without them, 2020's with them, is E30 with the 2019 rows."""
    root = make_snapshot(tmp_path / "p", preset="small", markets=("KR",), n_kr=2,
                         start=dt.date(2019, 12, 2), end=dt.date(2020, 1, 31))  # fmt: skip
    data = json.loads((root / "tds.json").read_text(encoding="utf-8"))
    bars = next(d for d in data["datasets"] if d["kind"] == "bars")
    [f2019] = [f for f in bars["files"] if "year=2019" in f["path"]]
    table = pq.read_table(part := root / f2019["path"]).drop_columns(list(OHL))
    pq.write_table(table, part)
    f2019["bytes"] = part.stat().st_size
    (root / "tds.json").write_text(json.dumps(data), encoding="utf-8")
    write_hashes(root)
    with pytest.warns(UserWarning, match="F-01") as caught:
        snapshot = nx.open(str(root))
    assert f"column open, {len(table)}" in f01(caught.list)[0]
    assert {r.column for r in snapshot.fallbacks if r.id == "F-01"} == set(OHL)


def test_f01_undecided_without_footer_statistics(tmp_path: Path) -> None:
    """Without footer statistics, null in every row is not known without reading the rows,
    which open does not do: no F-01, the cells NaN as stored."""
    root = make_snapshot(tmp_path / "p", preset="tiny", markets=("KR",))
    without_ohl(root, "KR", drop=False, stats=False)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        values = latest(root, "open")
    assert not f01(caught)
    assert all(math.isnan(v) for v in values.values())
