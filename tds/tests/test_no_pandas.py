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

from nexusbt_tds import check
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
result = check(sys.argv[1], level=sys.argv[3])
found = [[f.code, f.dataset, f.message] for f in (*result.errors, *result.warnings)]
print(json.dumps({"found": found, "unchecked": result.unchecked, "converts": converts,
                  "notes": list(result.notes)}))
"""
TICK = 1704189600000000001  # 2024-01-02T10:00:00.000000001Z: not a whole microsecond
NS = pa.timestamp("ns", "UTC")


CLOSE = TICK - 1 + 11 * 3600 * 10**9  # 21:00, the session close and `build.THROUGH`


def _quotes(recv: int, availability: str | None = None, *, end: int | None = None) -> Any:
    """One US:AAA quote at `TICK`, received at `recv`, beside the event of TDS-T001's package;
    with `end`, the daily bar ends then, under a calendar and the US watermark `build.THROUGH`.
    The files have pyarrow's footer statistics, which the schema level and T006 read."""
    rel = "quotes/venue=XNYS/date=2024-01-02/part-00000.parquet"
    columns = {
        "instrument_id": ["US:AAA"], "session_date": build.DAY, "ts_event": pa.array([TICK], NS),
        "sequence": [1], "bid_px": [99], "ask_px": [100], "ts_recv": pa.array([recv], NS),
        **({"ts_available": pa.array([recv + 500], NS)} if availability else {}),
    }  # fmt: skip

    def change(m: dict[str, Any], f: Any) -> None:
        build._add("quotes", columns, rel)(m, f)
        if availability:
            m["datasets"][-1]["availability"] = availability
        if end is not None:
            m["markets"]["US"]["complete_through"] = build.THROUGH.isoformat()
            build._sessions(0)(m, f)
            build.rewrite(m, f, build.BARS, build.bars_table(ts_end=pa.array([end], NS)))
        build.CASES["TDS-T001"][1](m, f)  # an `events` row available a second before its event

    return change


def _run(package: Path, pandas: str, level: str = "full") -> dict[str, Any]:
    done = subprocess.run(  # noqa: S603 - this interpreter, the script above
        [sys.executable, "-c", RUN, str(package), pandas, level],
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
        (_quotes(TICK + 1, end=CLOSE), ["TDS-T001"]),  # at the watermark and the close
        (_quotes(TICK + 1, end=CLOSE + 1), ["TDS-T001", "TDS-T005", "TDS-T006"]),  # 1 ns after
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
    found = sorted(["TDS-M015", *found])  # quotes are experimental (TDS 5.7)
    assert sorted(code for code, _, _ in said["found"]) == found, said
    assert ["TDS-T001", "events"] in [f[:2] for f in said["found"]]
    assert [c for c in said["unchecked"] if c in INSTANT_CODES] == []
    late = [message for code, _, message in said["found"] if code == "TDS-T006"]
    assert all("available until 2024-01-02T21:00:00.000000001+00:00" in m for m in late), late


_LAST = dt.datetime(9999, 12, 31, 23, 59, 59, 999999, tzinfo=dt.UTC)


@pytest.mark.parametrize(
    ("rule", "ts_end", "until"),
    [  # T006 from the footer statistics, the delay in nanoseconds
        ("ts_end", pa.array([CLOSE], NS), None),  # at the watermark: not after it
        ("ts_end+PT0.000000001S", pa.array([CLOSE], NS), "2024-01-02T21:00:00.000000001+00:00"),
        ("ts_end+P1D", pa.array([_LAST], build.TS_UTC), "253402387199999999000 ns"),  # year 10000
    ],
)
def test_T006_counts_a_delay_in_nanoseconds_and_names_an_instant_past_year_9999(
    rule: str, ts_end: pa.Array, until: str | None, tmp_path: Path
) -> None:
    manifest, files = build.base()
    manifest["markets"]["US"]["complete_through"] = build.THROUGH.isoformat()
    build.bars(manifest)["availability"] = {"rule": rule}
    build.rewrite(manifest, files, build.BARS, build.bars_table(ts_end=ts_end))
    result = check(build.write(tmp_path, manifest, files), level="schema")
    late = [f.message for f in result.errors if f.code == "TDS-T006"]
    assert [m.split(",")[0] for m in late] == ([f"available until {until}"] if until else [])
    assert "TDS-T006" not in result.unchecked


def test_a_footer_arrow_gives_no_schema_for_leaves_its_statistics_unknown() -> None:
    from types import SimpleNamespace as Fake

    from nexusbt_tds.check import _stat

    def no_schema() -> None:
        raise pa.ArrowNotImplementedError("a Parquet type with no Arrow type")

    statistics = Fake(has_null_count=True, num_values=1, has_min_max=True)
    group = Fake(column=lambda i: Fake(statistics=statistics))
    schema = Fake(column=lambda i: Fake(path="ts_end"), to_arrow_schema=no_schema)
    meta = Fake(num_columns=1, schema=schema, row_group=lambda g: group)
    assert _stat(meta, 0, "ts_end", dt.datetime) is None


_FAR = "9999-12-31"  # an open end written as a date: past int64 in nanoseconds (year 2262)


@pytest.mark.parametrize(
    ("change", "found"),
    [  # the two places that put instants back in an Arrow table
        (build._classified((*build._A[:4], _FAR, *build._A[5:]),
                           (*build._B[:4], _FAR, *build._B[5:])), "TDS-T012"),
        (build._actions({"ts_terms_available": dt.datetime.fromisoformat(_FAR + "T00Z")}),
         "TDS-A008"),
    ],
)  # fmt: skip
def test_an_instant_past_int64_nanoseconds_is_judged(
    change: Any, found: str, tmp_path: Path
) -> None:
    manifest, files = build.base()
    change(manifest, files)
    result = check(build.write(tmp_path, manifest, files), level="full")
    said = (*result.errors, *result.warnings)  # A008 is a warning
    assert [f.code for f in said] == [found]
    assert {"TDS-T012", "TDS-A001"} & set(result.unchecked) == set()
    if found == "TDS-T012":  # the corner both rows are seen at, as before
        assert "at known time 2020-03-06T00:00:00+00:00 on 2020-03-20, 2 rows" in said[0].message


def test_an_instant_is_nanoseconds_of_any_unit_and_reads_as_text_in_a_finding() -> None:
    from nexusbt_tds.keys import Instant, _values

    far = pa.array([2**62, None], pa.timestamp("s"))  # past int64 in nanoseconds: not wrapped
    assert _values(far) == [2**62 * 10**9, None]
    assert _values(pa.array([1], pa.timestamp("ms", "UTC"))) == [10**6]
    assert str(Instant(TICK)) == "2024-01-02 10:00:00.000000001+00:00"
    assert str(Instant(TICK - 1)) == str(dt.datetime(2024, 1, 2, 10, tzinfo=dt.UTC))
    assert str(Instant(1_500_000)) == "1970-01-01 00:00:00.001500+00:00"  # as a datetime's text
    assert str(Instant(10**30)) == f"{10**30} ns"  # past year 9999: no calendar date to write


TIME = pa.time64("ns")


@pytest.mark.parametrize(
    ("tag", "kind", "read"),
    [
        ("ts_ns", pa.timestamp("s"), True),  # any unit or zone: S004's
        ("ts_ns", pa.int64(), False),
        ("ts_us", pa.list_(NS), False),
        ("date", pa.date32(), True),
        ("date", pa.string(), True),  # no time in it: the codes that need a date skip it (#366)
        ("date", pa.date64(), False),
        ("date", pa.struct([("t", pa.duration("ns"))]), False),
        ("date", pa.map_(pa.string(), TIME), False),
    ],
)
def test_a_time_column_is_read_only_as_its_own_type(
    tag: str, kind: pa.DataType, read: bool
) -> None:
    from nexusbt_tds.hash import TIME_TYPES

    assert TIME_TYPES[tag](kind) is read


def test_an_instant_column_of_another_type_is_named_in_this_process(tmp_path: Path) -> None:
    """The guards go by type, so they run here, pandas or not; the subprocess runs above are
    not counted by coverage."""
    manifest, files = build.base()
    build._bars(ts_end=pa.array([1], TIME))(manifest, files)
    result = check(build.write(tmp_path, manifest, files), level="full")
    assert "TDS-S002" in [f.code for f in result.errors]
    assert set(INSTANT_CODES) <= set(result.unchecked)
    said = [n for n in result.notes if n.startswith(", ".join(INSTANT_CODES))]
    assert len(said) == 1
    assert "ts_end is time64[ns], TDS type ts_us/ns" in said[0]


def test_the_value_hash_refuses_only_a_time_column_holding_another_time_type() -> None:
    from nexusbt_tds.hash import HashError, _values

    assert _values(pa.chunked_array([pa.array([1])]), "ts_ns", "ts_end") == [1]  # as before
    with pytest.raises(HashError, match=r"ts_end is time64\[ns\], TDS type ts_ns"):
        _values(pa.chunked_array([pa.array([1], TIME)]), "ts_ns", "ts_end")


@pytest.mark.parametrize("level", ["schema", "full"])
@pytest.mark.parametrize(
    ("change", "column"),
    [  # an instant or a date column of a type that is not its own (#389)
        (build._bars(ts_end=pa.array([1], TIME)), "ts_end is time64[ns]"),
        (build._bars(session_date=pa.array([1], TIME)), "session_date is time64[ns]"),
        (build._instruments(listed_on=pa.array([1], TIME)), "listed_on is time64[ns]"),
        (build._bars(ts_end=pa.array([1], pa.duration("ns"))), "ts_end is duration[ns]"),
        (build._bars(ts_end=pa.array([[TICK]], pa.list_(NS))), "ts_end is list<element: timestamp"),
        (build._bars(ts_end=pa.array([{"t": TICK}], pa.struct([("t", NS)]))),
         "ts_end is struct<t: timestamp"),
    ],
    ids=["ts_end-time64", "session_date-time64", "listed_on-time64", "ts_end-duration",
         "ts_end-list", "ts_end-struct"],
)  # fmt: skip
def test_a_column_of_another_type_is_S002_and_the_same_without_pandas(
    change: Any, column: str, level: str, tmp_path: Path
) -> None:
    pytest.importorskip("pandas")
    manifest, files = build.base()
    change(manifest, files)
    package = build.write(tmp_path, manifest, files)
    blocked, installed = (_run(package, pandas, level) for pandas in ("blocked", "installed"))
    assert "TDS-S002" in [code for code, _, _ in blocked["found"]], blocked
    del blocked["converts"], installed["converts"]
    assert blocked == installed  # findings, `unchecked` and notes
    if level == "full":  # a value the schema does not type is not compared, and the note says so
        assert set(INSTANT_CODES) <= set(blocked["unchecked"]), blocked
        said = [n for n in blocked["notes"] if n.startswith(", ".join(INSTANT_CODES))]
        assert len(said) == 1, blocked["notes"]
        assert column in said[0]
