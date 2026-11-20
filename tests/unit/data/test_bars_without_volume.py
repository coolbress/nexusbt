"""#584: bars without `volume` or `value_traded` (4.5 F-18), read through `nx.run_pipeline`.

`degrade=["no_volume"]` leaves both columns out (4.8); a package with `volume` and without
`value_traded`, the generator cannot write, is `tiny` with that column dropped here."""

from __future__ import annotations

import datetime as dt
import json
import math
import warnings
from pathlib import Path
from typing import Any

import pyarrow.compute as pc
import pyarrow.parquet as pq
import pytest

import nexusbt as nx
from nexusbt.testing.synth import make_snapshot, read
from nexusbt_tds.hash import write_hashes

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


def without(root: Path, column: str) -> None:
    """Every bars file of the package rewritten without `column`, the hashes written again."""
    data = json.loads((root / "tds.json").read_text(encoding="utf-8"))
    for f in next(d for d in data["datasets"] if d["kind"] == "bars")["files"]:
        pq.write_table(pq.read_table(part := root / f["path"]).drop_columns([column]), part)
        f["bytes"] = part.stat().st_size
    (root / "tds.json").write_text(json.dumps(data), encoding="utf-8")
    write_hashes(root)


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


def test_value_traded_alone_left_out(tmp_path: Path) -> None:
    """Bars with `volume` and without `value_traded`: that column NaN, `volume` as stored, one
    E30 naming `value_traded` only."""
    root = make_snapshot(tmp_path / "p", preset="tiny", markets=("KR",))
    without(root, "value_traded")
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


def test_no_volume_drops_the_core_declaration(tmp_path: Path) -> None:
    """4.8: `no_volume` breaks TDS 7's OHLCV, so the package no longer declares core."""
    root = make_snapshot(tmp_path / "p", preset="tiny", markets=("KR",), degrade=["no_volume"])
    declared = json.loads((root / "tds.json").read_text(encoding="utf-8"))["profiles"]
    assert CORE not in declared
    assert CORE in json.loads((make_snapshot(tmp_path / "w", preset="tiny", markets=("KR",))
                               / "tds.json").read_text(encoding="utf-8"))["profiles"]  # fmt: skip
