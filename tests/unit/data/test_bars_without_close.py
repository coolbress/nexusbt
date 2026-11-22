"""#698: a bars file without a `close` column stops the open with E14 (spec 4.3, 4.4 step 3),
naming the market and the column, whatever the run reads; pyarrow's error never reaches the
person. Since #705 Decisions 48 and 50, also a close null in every row, and a column a declared
profile requires."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

import nexusbt as nx
from nexusbt.contracts import SnapshotError
from nexusbt.testing.synth import make_snapshot
from nexusbt_tds.hash import write_hashes

Drop = Callable[..., None]


def _run(pkg: Path, column: str, markets: list[str] | None = None) -> None:
    pipeline = nx.Pipeline({"c": getattr(nx.Price, column).latest})
    nx.run_pipeline(pipeline, start="2020-01-06", end="2020-01-08", markets=markets,
                    snapshot=str(pkg))  # fmt: skip


@pytest.mark.parametrize("column", ["close", "close_tr", "close_unadjusted", "volume"])
def test_a_run_over_price_stops_with_e14_naming_market_and_close(
    column: str, tmp_path: Path, package_without_bars_column: Drop
) -> None:
    """#698's reproduction reversed: every `Price` column, `volume` too (4.3 puts the E14 on
    `Price.*` and `run_pipeline` as a whole), stops with E14 in 6.6's shape."""
    pkg = make_snapshot(tmp_path / "pkg", preset="tiny")
    package_without_bars_column(pkg, "close")
    with pytest.raises(SnapshotError) as raised:
        _run(pkg, column)
    text = str(raised.value)
    assert text.startswith("SnapshotError [E14]")
    assert "the bars of market KR have no close column" in text
    assert "column close" in text
    assert "ArrowInvalid" not in text
    assert "FieldRef" not in text


def test_a_run_of_another_market_stops_too(
    tmp_path: Path, package_without_bars_column: Drop
) -> None:
    """#698 Decisions (2026-11-22): the E14 is the open's, so a run that reads only US stops
    on the KR file without close."""
    pkg = make_snapshot(tmp_path / "pkg", preset="tiny")
    package_without_bars_column(pkg, "close", market="KR")
    with pytest.raises(SnapshotError, match="the bars of market KR have no close column"):
        _run(pkg, "close", markets=["US"])


def _null(pkg: Path, column: str, *, statistics: bool = True, keep: int = 0) -> None:
    """`column` of every bars file null in every row but the first `keep`, footers written with
    or without statistics."""
    data = json.loads((pkg / "tds.json").read_text(encoding="utf-8"))
    for f in next(d for d in data["datasets"] if d["kind"] == "bars")["files"]:
        table = pq.read_table(part := pkg / f["path"])
        at = table.schema.get_field_index(column)
        kept = table[column].slice(0, keep).cast(pa.float64())
        values = pa.concat_arrays([*kept.chunks, pa.nulls(len(table) - len(kept), pa.float64())])
        pq.write_table(table.set_column(at, column, values), part, write_statistics=statistics)
        f["bytes"] = part.stat().st_size
    (pkg / "tds.json").write_text(json.dumps(data), encoding="utf-8")
    write_hashes(pkg)


@pytest.mark.parametrize("statistics", [True, False], ids=["footer", "no statistics"])
def test_a_close_null_in_every_row_is_missing_e14(statistics: bool, tmp_path: Path) -> None:
    """#705 Decisions 50 (in place of #698's item 3): a close with no value is a missing close,
    as TDS-M008 reads it; a file without statistics has that column read, never passed."""
    pkg = make_snapshot(tmp_path / "pkg", preset="tiny", degrade=["no_ohlc"])  # minimal only
    _null(pkg, "close", statistics=statistics)
    with pytest.raises(SnapshotError) as raised:
        _run(pkg, "close")
    assert str(raised.value).startswith("SnapshotError [E14]")
    assert "the bars hold no value of close" in str(raised.value)


def test_a_close_with_one_value_opens_without_statistics(tmp_path: Path) -> None:
    # counter-example: one value is not "null in every row", read from the column itself
    pkg = make_snapshot(tmp_path / "pkg", preset="tiny")
    _null(pkg, "close", statistics=False, keep=1)
    nx.open(str(pkg))


@pytest.mark.parametrize("column", ["open", "volume"])
def test_a_declared_profiles_column_is_e14_at_open(column: str, tmp_path: Path) -> None:
    """#705 Decisions 48 (b): `tiny` declares core, which requires an equity's open, high, low
    and volume (TDS 7); a package that breaks it is E14 at open, never F-01 or F-18."""
    pkg = make_snapshot(tmp_path / "pkg", preset="tiny")
    _null(pkg, column)
    with pytest.raises(SnapshotError) as raised:
        nx.open(str(pkg))
    text = str(raised.value)
    assert f"the bars hold no value of {column}, which tds:equity-daily-core@1.0 requires" in text
    assert "or declare tds:minimal-daily@1.0" in text


def test_a_minimal_package_without_open_opens(tmp_path: Path) -> None:
    # counter-example (#705 Decisions 48 (c)): minimal-daily asks close alone; the run reads it
    pkg = make_snapshot(tmp_path / "pkg", preset="tiny", degrade=["no_ohlc"])
    pipeline = nx.Pipeline({"c": nx.Price.close.latest})
    with pytest.warns(UserWarning, match=r"\[E30\] F-01"):  # F-01's E30 leaves in plan item 4b
        result = nx.run_pipeline(pipeline, start="2020-01-06", end="2020-01-08", snapshot=str(pkg))
    values = result.table["c"].to_pylist()
    assert any(v is not None and v == v for v in values)


def test_core_bars_of_indices_alone_need_no_open_but_a_read_is_e18(tmp_path: Path) -> None:
    """#705 Decisions 39 and 48: core asks open of bars naming an equity or etf; bars of
    indices alone open without it, and a term reading it is E18 (c), not NaN."""
    pkg = make_snapshot(tmp_path / "pkg", preset="tiny")  # declares core
    data = json.loads((pkg / "tds.json").read_text(encoding="utf-8"))
    for f in next(d for d in data["datasets"] if d["kind"] == "instruments")["files"]:
        table = pq.read_table(part := pkg / f["path"])
        at = table.schema.get_field_index("asset_class")
        pq.write_table(table.set_column(at, "asset_class", pa.array(["index"] * len(table))), part)
        f["bytes"] = part.stat().st_size
    (pkg / "tds.json").write_text(json.dumps(data), encoding="utf-8")
    _null(pkg, "open")  # writes the hashes
    with pytest.warns(UserWarning, match=r"\[E30\] F-01"):  # opens: no E14 (until 4b, F-01)
        nx.open(str(pkg))
    with (
        pytest.warns(UserWarning, match=r"\[E30\] F-01"),
        pytest.raises(nx.CapabilityError, match=r"Price\.open is"),
    ):
        _run(pkg, "open")


def test_a_file_the_check_cannot_read_is_left_to_the_checker(tmp_path: Path) -> None:
    """A bars file storing `close` twice, without statistics, cannot be read for that column:
    the check raises neither E14 nor pyarrow's error, and leaves it to TDS-S011."""
    from nexusbt.data._capabilities import _breaks_profile

    (tmp_path / "bars").mkdir()
    twice = pa.table([pa.array([1.0]), pa.array([None], pa.float64())], names=["close", "close"])
    pq.write_table(twice, tmp_path / "bars" / "a.parquet", write_statistics=False)
    bars = {"name": "bars_1d", "params": {}, "files": [{"path": "bars/a.parquet"}]}
    data = {"profiles": ["tds:minimal-daily@1.0"], "snapshot_id": "s"}
    assert _breaks_profile(tmp_path, data, bars, None) == frozenset()
    # the review of 4a-ii: an `open` it cannot read never hides the E14 of a close with no value
    columns = [pa.array([None], pa.float64()), pa.array([1.0]), pa.array([1.0])]
    no_close = pa.table(columns, names=["close", "open", "open"])
    pq.write_table(no_close, tmp_path / "bars" / "a.parquet", write_statistics=["close"])
    with pytest.raises(SnapshotError, match="the bars hold no value of close"):
        _breaks_profile(tmp_path, data | {"layers": {}}, bars, None)
