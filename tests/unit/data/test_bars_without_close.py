"""#698: a bars file without a `close` column stops the open with E14 (spec 4.3, 4.4 step 3),
naming the market and the column, whatever the run reads; pyarrow's error never reaches the
person. Only an absent column: one null in every row is data (#698 Decisions, item 3)."""

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


def test_a_close_null_in_every_row_is_data_not_e14(tmp_path: Path) -> None:
    """#698 Decisions, item 3: a close column with no value opens; `Price.close` is NaN there,
    as for any missing bar (the checker's M008 calls it missing, at `schema` and above)."""
    pkg = make_snapshot(tmp_path / "pkg", preset="tiny")
    data = json.loads((pkg / "tds.json").read_text(encoding="utf-8"))
    for f in next(d for d in data["datasets"] if d["kind"] == "bars")["files"]:
        table = pq.read_table(part := pkg / f["path"])
        at = table.schema.get_field_index("close")
        pq.write_table(table.set_column(at, "close", pa.nulls(len(table), pa.float64())), part)
        f["bytes"] = part.stat().st_size
    (pkg / "tds.json").write_text(json.dumps(data), encoding="utf-8")
    write_hashes(pkg)
    pipeline = nx.Pipeline({"c": nx.Price.close.latest})
    result = nx.run_pipeline(pipeline, start="2020-01-06", end="2020-01-08", snapshot=str(pkg))
    values = result.table["c"].to_pylist()
    assert values
    assert all(v is None or v != v for v in values)  # NaN or null, never a price
