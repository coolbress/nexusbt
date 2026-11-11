"""The `full` level reads an instant as integer nanoseconds (#382): `nexusbt_tds` depends on
pyarrow only, and without pandas pyarrow turns no `timestamp[ns]` value that is not a whole
microsecond into a Python value. Each run is a new interpreter, since pyarrow asks for pandas
once in a process."""

from __future__ import annotations

import datetime as dt
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pyarrow as pa
import pytest

from nexusbt_tds.check import INSTANT_CODES

from .conformance_build import build

RUN = """
import importlib.abc, json, sys

class NoPandas(importlib.abc.MetaPathFinder):  # `import pandas` fails, as where it is not installed
    def find_spec(self, name, path, target=None):
        if name.partition(".")[0] == "pandas":
            raise ImportError("pandas is blocked")

if sys.argv[2] == "blocked":
    sys.meta_path.insert(0, NoPandas())
import pyarrow as pa
from nexusbt_tds import check

try:
    converts = bool(pa.array([1], pa.timestamp("ns", "UTC")).to_pylist())
except ValueError:
    converts = False
result = check(sys.argv[1], level="full")
found = [[f.code, f.dataset, f.message] for f in (*result.errors, *result.warnings)]
print(json.dumps({"found": found, "unchecked": result.unchecked, "converts": converts}))
"""
TICK = 1704189600000000001  # 2024-01-02T10:00:00.000000001Z: not a whole microsecond
NS = pa.timestamp("ns", "UTC")


def _quotes(recv: int, availability: str | None = None, *, statistics: bool = False) -> Any:
    """One US:AAA quote at `TICK`, received at `recv`, beside the event of TDS-T001's package.
    Its file has no footer statistics unless `statistics`: without pandas the schema level stops
    on a nanosecond one (`check.py`), before a row is read."""
    rel = "quotes/venue=XNYS/date=2024-01-02/part-00000.parquet"
    columns = {
        "instrument_id": ["US:AAA"], "session_date": build.DAY, "ts_event": pa.array([TICK], NS),
        "sequence": [1], "bid_px": [99], "ask_px": [100], "ts_recv": pa.array([recv], NS),
        **({"ts_available": pa.array([recv + 500], NS)} if availability else {}),
    }  # fmt: skip

    def change(m: dict[str, Any], f: Any) -> None:
        build._add("quotes", columns, rel)(m, f)
        build.rewrite(m, f, rel, pa.table(columns), write_statistics=statistics)
        if availability:
            m["datasets"][-1]["availability"] = availability
        build.CASES["TDS-T001"][1](m, f)  # an `events` row available a second before its event

    return change


def _run(package: Path, pandas: str) -> dict[str, Any]:
    done = subprocess.run(  # noqa: S603 - this interpreter, the script above
        [sys.executable, "-c", RUN, str(package), pandas],
        capture_output=True, text=True, check=False,
    )  # fmt: skip
    assert done.returncode == 0, done.stderr
    said: dict[str, Any] = json.loads(done.stdout)
    return said


@pytest.mark.parametrize("pandas", ["blocked", "installed"])
@pytest.mark.parametrize(
    ("change", "found"),
    [
        (_quotes(TICK + 1), ["TDS-T001"]),  # received a nanosecond after the tick
        (_quotes(TICK - 1), ["TDS-T001", "TDS-T008"]),  # and a nanosecond before it
        # `ts_available` 500 ns after `ts_recv`, a column 5.7 does not give quotes (S005)
        (_quotes(TICK + 1, "ts_recv+PT0.0000005S"), ["TDS-S005", "TDS-T001"]),
        (_quotes(TICK + 1, "ts_recv+PT0.000001S"), ["TDS-S005", "TDS-T001", "TDS-T002"]),
    ],
)
def test_a_tick_that_is_not_a_whole_microsecond_is_judged(
    change: Any, found: list[str], pandas: str, tmp_path: Path
) -> None:
    if pandas == "installed":
        pytest.importorskip("pandas")
    manifest, files = build.base()
    change(manifest, files)
    said = _run(build.write(tmp_path, manifest, files), pandas)
    assert said["converts"] is (pandas == "installed")  # blocked: a pandas-free install's path
    assert sorted(code for code, _, _ in said["found"]) == found, said
    assert ["TDS-T001", "events"] in [f[:2] for f in said["found"]]
    assert [c for c in said["unchecked"] if c in INSTANT_CODES] == []


@pytest.mark.xfail(strict=True, reason="#382: `check.py` reads a footer statistic as a datetime")
def test_a_tick_in_a_file_with_footer_statistics_is_judged_without_pandas(tmp_path: Path) -> None:
    manifest, files = build.base()
    _quotes(TICK + 1, statistics=True)(manifest, files)
    said = _run(build.write(tmp_path, manifest, files), "blocked")
    assert [c for c in said["unchecked"] if c in INSTANT_CODES] == []


def test_an_instant_is_nanoseconds_of_any_unit_and_reads_as_text_in_a_finding() -> None:
    from nexusbt_tds.keys import Instant, _values

    far = pa.array([2**62, None], pa.timestamp("s"))  # past int64 in nanoseconds: not wrapped
    assert _values(far) == [2**62 * 10**9, None]
    assert _values(pa.array([1], pa.timestamp("ms", "UTC"))) == [10**6]
    assert str(Instant(TICK)) == "2024-01-02 10:00:00.000000001+00:00"
    assert str(Instant(TICK - 1)) == str(dt.datetime(2024, 1, 2, 10, tzinfo=dt.UTC))
    assert str(Instant(1_500_000)) == "1970-01-01 00:00:00.001500+00:00"  # as a datetime's text
    assert str(Instant(10**30)) == f"{10**30} ns"  # past year 9999: no calendar date to write
