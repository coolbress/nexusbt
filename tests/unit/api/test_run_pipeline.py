"""`nx.run_pipeline` (spec 3.5, T1.13, #249) on the synthetic `tiny` package (4.8): the result
table's shape and order, the screen's rows, the markets it runs, the adjusted values through the
public call, and the graph bound before anything is computed."""

from __future__ import annotations

import datetime as dt
import json
import math
from collections.abc import Sequence
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
import yaml

import nexusbt as nx
from nexusbt.factors import SMA
from nexusbt.testing._synth_package import _write
from nexusbt.testing.synth import make_snapshot, write_actions
from nexusbt_tds.hash import write_hashes

pytestmark = pytest.mark.unit

CASES = Path(__file__).parents[2] / "golden" / "cases"
ID = "KR:T00001"


@pytest.fixture(scope="module")
def tiny(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return make_snapshot(tmp_path_factory.mktemp("tiny") / "pkg", preset="tiny")


@pytest.fixture(autouse=True)
def no_toml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A working folder without `nexusbt.toml`: the 3.11 defaults."""
    monkeypatch.chdir(tmp_path)


def run(
    pipe: nx.Pipeline, package: Path, start: str, end: str, markets: Sequence[str] | None = None
) -> pa.Table:
    result = nx.run_pipeline(pipe, start=start, end=end, markets=markets, snapshot=str(package))
    return result.table


def test_output_schema_and_sort(tiny: Path) -> None:
    """3.5: `(market, session_date, decision_ts, instrument_id, <columns…>)` with those types,
    sorted by `(session_date, market, instrument_id)`, both markets' rows stacked."""
    pipe = nx.Pipeline({"close": nx.Price.close.latest, "sma": SMA(5)})
    table = run(pipe, tiny, "2020-02-03", "2020-02-07")
    assert table.schema.names == ["market", "session_date", "decision_ts", "instrument_id",
                                  "close", "sma"]  # fmt: skip
    assert table.schema.types == [pa.string(), pa.date32(), pa.timestamp("us", tz="UTC"),
                                  pa.string(), pa.float64(), pa.float64()]  # fmt: skip
    names = ("session_date", "market", "instrument_id")
    keys = list(zip(*(table[c].to_pylist() for c in names), strict=True))
    assert keys == sorted(keys)
    assert len(set(keys)) == len(keys)
    assert set(table["market"].to_pylist()) == {"KR", "US"}
    assert {k[0] for k in keys} == {dt.date(2020, 2, d) for d in range(3, 8)}


def test_screen_rows_filtered(tiny: Path) -> None:
    """3.5, R3-13: a row is kept where the screen is true; false and unknown rows are not
    there. `SMA(5) > 25000` is unknown in the first four sessions, where SMA(5) is NaN (5.4.1),
    and false for the instruments priced below it."""
    columns = {"close": nx.Price.close.latest, "sma": SMA(5)}
    every = run(nx.Pipeline(columns), tiny, "2020-01-02", "2020-01-31").to_pylist()
    screened = nx.Pipeline(columns, screen=SMA(5) > 25_000)
    kept = run(screened, tiny, "2020-01-02", "2020-01-31").to_pylist()
    assert [r for r in every if math.isnan(r["sma"])]  # unknown rows exist
    assert [r for r in every if r["sma"] <= 25_000]  # false rows exist
    assert kept
    assert kept == [r for r in every if r["sma"] > 25_000]  # NaN > x is False in Python too


def test_markets_from_snapshot(tiny: Path, tmp_path: Path) -> None:
    """3.5: `markets` are keys of the snapshot's markets, all of them when not given, each
    once; each market's rows are on its own calendar, so 2020-01-20, a KR session and a US
    holiday, gives KR's rows and none of US's."""
    pipe, day = nx.Pipeline({"close": nx.Price.close.latest}), "2020-01-02"
    found = run(pipe, tiny, day, day)
    assert sorted(set(found["market"].to_pylist())) == ["KR", "US"]
    assert set(run(pipe, tiny, "2020-01-20", "2020-01-20")["market"].to_pylist()) == {"KR"}
    only = run(pipe, tiny, day, day, markets=["US", "US"])
    assert set(only["market"].to_pylist()) == {"US"}
    us = sorted(i for i in found["instrument_id"].to_pylist() if i.startswith("US:"))
    assert only["instrument_id"].to_pylist() == us
    kr = make_snapshot(tmp_path / "kr", preset="tiny", markets=("KR",))
    assert set(run(pipe, kr, day, day)["market"].to_pylist()) == {"KR"}
    with pytest.raises(nx.NexusBTError, match="JP"):
        run(pipe, tiny, day, day, markets=["JP"])


def t07(at: Path) -> Path:
    """`tiny` KR with KR:T00001's bars and events those of the golden case T-07 (8.2): the
    closes, volumes and `cum_factor_*` of its eight rows, `C = 5` after them."""
    case = yaml.safe_load((CASES / "T-07.yaml").read_text())
    root = make_snapshot(at, preset="tiny", markets=("KR",))
    write_actions(root, case["corporate_actions"])
    manifest = json.loads((root / "tds.json").read_text(encoding="utf-8"))
    (entry,) = (d for d in manifest["datasets"] if d["kind"] == "bars")
    (file,) = entry["files"]
    rows = pq.read_table(root / file["path"]).to_pylist()
    given = {dt.date.fromisoformat(b["session_date"]): b for b in case["bars"]}
    for row in (r for r in rows if r["instrument_id"] == ID):
        bar = given.get(row["session_date"], {"cum_factor_split": 5.0})
        row.update({k: v for k, v in bar.items() if k != "session_date"})
        row["cum_factor_total"] = row["cum_factor_split"]
    schema = pq.read_schema(root / file["path"])
    file.update(_write(root, file["path"], entry["name"], pa.Table.from_pylist(rows, schema)))
    (root / "tds.json").write_text(json.dumps(manifest), encoding="utf-8")
    write_hashes(root)
    return root


def test_values_reach_the_api_adjusted(tmp_path: Path) -> None:
    """#249: over T-07's bars, `SMA(3)` of `close` is the case's `sma` through the public call:
    52.0 on 2020-01-07, not the 86.33 of the closes as traded across the 2:1 split."""
    table = run(nx.Pipeline({"sma": SMA(3)}), t07(tmp_path), "2020-01-06", "2020-01-13")
    got = {(r["session_date"], r["instrument_id"]): r["sma"] for r in table.to_pylist()}
    case = yaml.safe_load((CASES / "T-07.yaml").read_text())
    for row in (r for r in case["expected"] if r["window"] == 3):
        assert got[dt.date.fromisoformat(row["session"]), ID] == pytest.approx(row["sma"])
    assert got[dt.date(2020, 1, 7), ID] == pytest.approx(52.0)


def test_graph_bound_before_planning(tiny: Path) -> None:
    """#499, #249 Decisions: `run_pipeline` binds the graph before it plans, so a price level
    through `shift` is E17 before any value is computed."""
    with pytest.raises(nx.TermDomainError):
        run(nx.Pipeline({"x": nx.Price.close.latest.shift(1)}), tiny, "2020-01-02", "2020-01-31")


def test_a_period_without_any_session_is_refused(tiny: Path) -> None:
    """5.1.6: a period that holds no session of any market is refused, not an empty table:
    2020-01-04 is a Saturday in both calendars."""
    with pytest.raises(nx.ConfigError, match="E16"):
        run(nx.Pipeline({"close": nx.Price.close.latest}), tiny, "2020-01-04", "2020-01-04")


def test_monthly_without_a_decision_is_an_empty_table(tiny: Path) -> None:
    """3.7: `monthly` decides on a month's last session, so 2020-01-02..10 holds no decision:
    the table has 3.5's columns, each of its kind's type, and no row."""
    pipe = nx.Pipeline({"close": nx.Price.close.latest, "up": nx.Price.close.latest > 0})
    result = nx.run_pipeline(pipe, start="2020-01-02", end="2020-01-10", freq="monthly",
                             snapshot=str(tiny))  # fmt: skip
    assert result.table.num_rows == 0
    assert result.table.schema == pa.schema([
        ("market", pa.string()), ("session_date", pa.date32()),
        ("decision_ts", pa.timestamp("us", tz="UTC")), ("instrument_id", pa.string()),
        ("close", pa.float64()), ("up", pa.bool_()),
    ])  # fmt: skip


def test_a_pipeline_without_columns_is_refused(tiny: Path) -> None:
    """3.5's rows are `<columns…>` at the decisions: a pipeline naming none says so."""
    with pytest.raises(ValueError, match="one column or more"):
        run(nx.Pipeline({}, screen=SMA(5) > 0), tiny, "2020-01-02", "2020-01-31")


def test_across_markets_not_supported_yet(tiny: Path) -> None:
    """#249 Decisions 2026-11-19: a term with `across_markets=True` is T4.3's; `run_pipeline`
    says so before anything is computed rather than giving one market's values."""
    pipe = nx.Pipeline({"r": nx.Price.close.latest.rank(across_markets=True)})
    with pytest.raises(NotImplementedError, match="does not support across_markets=True yet"):
        run(pipe, tiny, "2020-01-02", "2020-01-31")
