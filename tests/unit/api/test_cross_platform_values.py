"""One measurement across the two platforms in use (#867 item 3; spec 5.3.10, 5.9.4).

CI runs on Linux and the maintainer's machine is macOS. 5.3.10 makes no bit promise between
environments and says the tolerance between them "is set by measurement". This test is that
measurement for a small synthetic pipeline run whose columns go through the kernels the
engine has: a window mean, a standard deviation, an exponential mean, a ratio, a logarithm
and the cross-sectional rank and z-score.

`cross_platform_values.json`, next to this file, holds the run's value hash (5.9.4, TDS 4.5)
and every float cell as `float.hex`, written by `python tests/unit/api/
test_cross_platform_values.py`. The test passes when this platform gives the same value hash.
When it does not, it warns with the first column and row that differ and by how much, and
then requires every cell within L1-a's `|a-b| ≤ 1e-9 + 1e-9·|b|` (8.1), the tolerance 5.9.4
gives a run without NAV in another environment.
"""

from __future__ import annotations

import json
import math
import os
import sys
import tempfile
import warnings
from pathlib import Path
from typing import Any

import pyarrow as pa
import pytest

import nexusbt as nx
from nexusbt.api._pipeline import KEYS
from nexusbt.data import table_value_hash
from nexusbt.factors import EWMA, SMA, AnnualizedVolatility, DailyReturns, RollingStd
from nexusbt.testing.synth import make_snapshot

pytestmark = pytest.mark.unit

RECORD = Path(__file__).with_name("cross_platform_values.json")
ABS_TOL = REL_TOL = 1e-9  # 8.1's L1-a, as `rerun` uses it (5.9.4)
START, END = "2020-01-02", "2020-02-28"


def _pipeline() -> nx.Pipeline:
    close = nx.Price.close.latest
    returns = DailyReturns()
    return nx.Pipeline({
        "close": close,
        "sma": SMA(10),
        "std": RollingStd(10),
        "ewma": EWMA(10, decay_rate=0.8),
        "vol": AnnualizedVolatility(10),
        "log_close": close.log(),
        "ratio": close / SMA(10),
        "rank": returns.rank(),
        "z": returns.zscore(),
    })  # fmt: skip


def _run(root: Path) -> pa.Table:
    """The run on the synthetic `tiny` package (4.8), in a folder without `nexusbt.toml`."""
    package = make_snapshot(root / "pkg", preset="tiny")
    here = Path.cwd()
    os.chdir(root)
    try:
        result = nx.run_pipeline(_pipeline(), start=START, end=END, snapshot=str(package))
    finally:
        os.chdir(here)
    return result.table


def _floats(table: pa.Table) -> dict[str, list[str | None]]:
    """Each float column's cells as `float.hex`, rows in the key order of 3.5."""
    table = table.sort_by([(k, "ascending") for k in KEYS])
    found: dict[str, list[str | None]] = {}
    for field in table.schema:
        if pa.types.is_floating(field.type):
            cells = table[field.name].to_pylist()
            found[field.name] = [None if v is None else float.hex(v) for v in cells]
    return found


def _not_floats(table: pa.Table) -> pa.Table:
    """The columns that are not floats (the keys and `decision_ts`), compared exactly."""
    return table.select([f.name for f in table.schema if not pa.types.is_floating(f.type)])


def _record(table: pa.Table) -> dict[str, Any]:
    return {
        "platform": sys.platform,
        "value_sha256": table_value_hash(table, KEYS),
        "rows_sha256": table_value_hash(_not_floats(table), KEYS),
        "rows": table.num_rows,
        "floats": _floats(table),
    }


def _first_beyond(was: dict[str, Any], now: dict[str, Any]) -> tuple[str, int, float] | None:
    """The first (column, row, |a-b|) beyond L1-a's tolerance, NaN agreeing with NaN."""
    for name, cells in was["floats"].items():
        for row, (a, b) in enumerate(zip(cells, now["floats"][name], strict=True)):
            if a is None or b is None:
                if a != b:
                    return name, row, math.inf
                continue
            x, y = float.fromhex(a), float.fromhex(b)
            if (math.isnan(x) and math.isnan(y)) or x == y:
                continue
            if not abs(x - y) <= ABS_TOL + REL_TOL * abs(y):
                return name, row, abs(x - y)
    return None


def _first_differ(was: dict[str, Any], now: dict[str, Any]) -> str:
    for name, cells in was["floats"].items():
        for row, (a, b) in enumerate(zip(cells, now["floats"][name], strict=True)):
            if a != b:
                x = math.nan if a is None else float.fromhex(a)
                y = math.nan if b is None else float.fromhex(b)
                return f"{name} row {row}: recorded {a}, here {b} (|a-b| = {abs(x - y):.3g})"
    return "no float cell differs; another column's value differs"


@pytest.mark.filterwarnings("default::UserWarning")  # pyproject's "error" would fail within it
def test_the_recorded_values_hold_on_this_platform(tmp_path: Path) -> None:
    """#867 item 3: the value hash recorded on one platform, here; otherwise the same keys and
    every float cell within L1-a's tolerance, and a warning naming the first cell that differs,
    which pytest's warnings summary shows in the CI log."""
    was = json.loads(RECORD.read_text(encoding="utf-8"))
    now = _record(_run(tmp_path))
    assert now["rows"] == was["rows"]
    assert now["rows_sha256"] == was["rows_sha256"]  # the same rows: only floats may differ
    assert list(now["floats"]) == list(was["floats"])
    if now["value_sha256"] == was["value_sha256"]:
        return
    warnings.warn(
        f"value hash differs from the one recorded on {was['platform']} "
        f"(here {now['platform']}): {_first_differ(was, now)}",
        stacklevel=1,
    )
    assert _first_beyond(was, now) is None, _first_beyond(was, now)


@pytest.mark.parametrize(("times", "beyond"), [(0.0, False), (0.5, False), (2.0, True)])
def test_the_tolerance_path_finds_the_first_cell_beyond_it(times: float, beyond: bool) -> None:
    """The path a differing platform takes, on the record itself: a cell moved by half
    L1-a's tolerance is within it, and by twice it is the cell named."""
    was = json.loads(RECORD.read_text(encoding="utf-8"))
    now = json.loads(json.dumps(was))
    row = next(i for i, c in enumerate(was["floats"]["std"]) if c and c != "nan")
    x = float.fromhex(was["floats"]["std"][row])
    now["floats"]["std"][row] = float.hex(x + times * (ABS_TOL + REL_TOL * abs(x)))
    found = _first_beyond(was, now)
    assert (found is not None) is beyond
    assert found is None or found[:2] == ("std", row)


def _dump(record: dict[str, Any]) -> str:
    """The record as JSON with one line per float column, so that a change reads by column."""
    head = {k: v for k, v in record.items() if k != "floats"}
    lines = [f"  {json.dumps(k)}: {json.dumps(v)}," for k, v in head.items()]
    columns = [f"    {json.dumps(k)}: {json.dumps(v)}" for k, v in record["floats"].items()]
    return "{\n" + "\n".join(lines) + '\n  "floats": {\n' + ",\n".join(columns) + "\n  }\n}\n"


if __name__ == "__main__":  # writes the record on this platform
    with tempfile.TemporaryDirectory() as tmp:
        RECORD.write_text(_dump(_record(_run(Path(tmp)))), encoding="utf-8")
