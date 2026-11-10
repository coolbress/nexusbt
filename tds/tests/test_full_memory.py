"""#309: the `full` level's peak memory is bounded by a row group, not by the dataset."""

from __future__ import annotations

import datetime as dt
import tracemalloc
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from nexusbt_tds import check, keys, refs
from nexusbt_tds import hash as tds_hashes

from .conformance_build import build

GROUP = 2_000  # rows in a row group, and in a batch of each part of the full level
GROUPS = 32  # the dataset is this many row groups


def daily_bars(root: Path, rows: int) -> Path:
    """A package whose `bars_1d` is `rows` daily bars of 2024, distinct keys, in its sort order,
    written in row groups of `GROUP` rows."""
    days = [dt.date(2024, 1, 1) + dt.timedelta(days=d) for d in range(250)]
    ids = [f"US:I{i:05}" for i in range(-(-rows // len(days)))]
    pairs = [(day, i) for day in days for i in ids][:rows]
    table = build.bars_table(instrument_id=pa.array([i for _, i in pairs]),
                             session_date=pa.array([d for d, _ in pairs]),
                             close=pa.array([10.0] * rows))  # fmt: skip
    manifest, files = build.base()
    build.rewrite(manifest, files, build.BARS, table, row_group_size=GROUP)
    return Path(build.write(root, manifest, files))


def test_full_level_peak_memory_is_a_few_row_groups(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The yardstick is one row group read as Python rows, the way `keys`, `refs` and the hashes
    read whole datasets before #309. The full level over 32 such row groups peaks under 4 of
    them (measured 2026-11-10: about 2, the same at 4, 16 and 64 row groups).

    `tracemalloc` sees the Python heap only: a part that held a whole dataset in Arrow buffers,
    never as Python values, would pass. Arrow's pool keeps one peak for the whole process, so
    this test cannot measure it; #309's pull request measured it by hand, flat with the rows."""
    for part in (keys, refs, tds_hashes):
        monkeypatch.setattr(part, "BATCH_ROWS", GROUP)  # 65,536 rows outside the test
    monkeypatch.setattr(tds_hashes, "_MERGE_BYTES", 1 << 18)  # 8 MiB outside it
    package = daily_bars(tmp_path / "pkg", GROUP * GROUPS)
    source = pq.ParquetFile(package / build.BARS)
    assert source.metadata.num_row_groups == GROUPS
    tracemalloc.start()
    source.read_row_group(0).to_pylist()
    row_group = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()
    tracemalloc.start()
    result = check(package, level="full")
    peak = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()
    assert not {"TDS-K001", "TDS-H002"} & {*result.unchecked, *(f.code for f in result.errors)}
    assert any(n.startswith("key check: 1 temporary file(s)") for n in result.notes)  # spilled
    assert peak < 4 * row_group, (peak, row_group)
