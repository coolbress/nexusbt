"""#309: the `full` level's peak memory is bounded by a row group, not by the dataset."""

from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

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


# Run in a process of its own, where no coverage is measured: `tracemalloc` counts every
# allocation of its process, not only the checker's, and the peak reached 8 row groups in CI
# (#359). The check runs once before the measured one: a process's first full-level check
# imports 18 modules (`pyarrow.compute` among them), 3.7 MB that stay, about 6 row groups.
MEASURE = """
import json, sys, tracemalloc
from pathlib import Path
import pyarrow.parquet as pq
from nexusbt_tds import check, keys, refs
from nexusbt_tds import hash as tds_hashes

package, bars, group = Path(sys.argv[1]), sys.argv[2], int(sys.argv[3])
for part in (keys, refs, tds_hashes):
    part.BATCH_ROWS = group  # 65,536 rows outside the test
tds_hashes._MERGE_BYTES = 1 << 18  # 8 MiB outside it
source = pq.ParquetFile(package / bars)
tracemalloc.start()
source.read_row_group(0).to_pylist()
row_group = tracemalloc.get_traced_memory()[1]
tracemalloc.stop()
check(package, level="full")  # the imports of the first one
tracemalloc.start()
result = check(package, level="full")
peak = tracemalloc.get_traced_memory()[1]
tracemalloc.stop()
print(json.dumps({
    "row_group": row_group, "peak": peak, "coverage": "coverage" in sys.modules,
    "codes": sorted({*result.unchecked, *(f.code for f in result.errors)}),
    "notes": list(result.notes),
}))
"""


def test_full_level_peak_memory_is_a_few_row_groups(tmp_path: Path) -> None:
    """The yardstick is one row group read as Python rows, the way `keys`, `refs` and the hashes
    read whole datasets before #309. The full level over 32 such row groups peaks under 4 of
    them (measured 2026-11-10: about 2, the same at 4, 16 and 64 row groups).

    `tracemalloc` sees the Python heap only: a part that held a whole dataset in Arrow buffers,
    never as Python values, would pass. Arrow's pool keeps one peak for the whole process, so
    this test cannot measure it; #309's pull request measured it by hand, flat with the rows."""
    package = daily_bars(tmp_path / "pkg", GROUP * GROUPS)
    assert pq.ParquetFile(package / build.BARS).metadata.num_row_groups == GROUPS
    env = {k: v for k, v in os.environ.items() if not k.startswith("COVERAGE_")}
    done = subprocess.run(  # noqa: S603 - this interpreter, the script above
        [sys.executable, "-c", MEASURE, str(package), build.BARS, str(GROUP)],
        env=env, capture_output=True, text=True, check=False,
    )  # fmt: skip
    assert done.returncode == 0, done.stderr
    seen = json.loads(done.stdout)
    assert not seen["coverage"], "coverage is loaded where the peak is measured (#359)"
    assert not {"TDS-K001", "TDS-H002"} & {*seen["codes"]}
    assert any(n.startswith("key check: 1 temporary file(s)") for n in seen["notes"])  # spilled
    assert seen["peak"] < 4 * seen["row_group"], (seen["peak"], seen["row_group"])
