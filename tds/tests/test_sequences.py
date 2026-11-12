"""TDS-V032: gaps in `sequence` where the vendor promised consecutive numbers (#348's
`## Decision`, TDS 5.6~5.8). Each test names the #432 "When … then …" line it covers."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

import pyarrow as pa
import pytest

from nexusbt_tds import check
from nexusbt_tds.check import Finding
from nexusbt_tds.manifest import read_manifest
from nexusbt_tds.sequences import check_sequences

from .conformance_build import build

#: Absent: no `sequence_consecutive_within` in `params`.
ABSENT = object()


def write(root: Path, change: Any) -> Path:
    manifest, files = build.base()
    change(manifest, files)
    return Path(build.write(root, manifest, files))


def judge(
    tmp_path: Path,
    days: dict[str, dict[str, list[Any]]],
    within: object = (),
    kind: str = "book_deltas",
) -> list[Finding]:
    """V032's lines on a package whose dataset of `kind` holds, per partition `date`
    (`venue=XNYS`), the given columns; `within` is the declared list, or `ABSENT`."""
    m, files = build.base()
    entries = []
    for day, columns in days.items():
        n = len(columns["sequence"])
        table = pa.table({"session_date": [dt.date.fromisoformat(day)] * n, **columns})
        rel = f"{kind}/venue=XNYS/date={day}/part-00000.parquet"
        files[rel] = build.parquet(table, kind)
        entries.append({"path": rel, "rows": n, "bytes": len(files[rel])})
    params = {} if within is ABSENT else {"sequence_consecutive_within": within}
    m["datasets"].append({"name": kind, "kind": kind, "schema_version": "1.0", "path": kind,
                          "params": params, "files": entries})  # fmt: skip
    blind: set[str] = set()
    found = check_sequences(read_manifest(build.write(tmp_path, m, files)), None, blind)
    assert blind == set()
    assert {(f.code, f.severity, f.dataset) for f in found} <= {("TDS-V032", "warning", kind)}
    return found


def gaps(found: list[Finding]) -> list[tuple[Any, ...]]:
    """(key, count, message) of each V032 line."""
    return [(f.key, f.count, f.message) for f in found]


DAY = "2024-01-02"
PART = {"venue": "XNYS", "date": DAY}


def seq(*numbers: int, **columns: Any) -> dict[str, Any]:
    return {"sequence": pa.array(numbers, pa.int64()), **columns}


def test_a_difference_of_0_is_not_a_gap(tmp_path: Path) -> None:
    # When a book_deltas dataset declares [] and a partition runs 5, 6, 6, 7, then no V032.
    assert judge(tmp_path, {DAY: seq(5, 6, 6, 7)}, []) == []


def test_one_line_per_group_with_the_missing_count_and_the_first_gap(tmp_path: Path) -> None:
    # When the same partition runs 5, 6, 9, then one line, count 2, the gap 6 → 9.
    assert gaps(judge(tmp_path, {DAY: seq(9, 5, 6)}, [])) == [
        (PART, 2, "2 missing sequence number(s); first gap 6 -> 9")
    ]


def test_listed_columns_split_the_partition_and_the_key_names_partition_values_first(
    tmp_path: Path,
) -> None:
    # When a dataset declares ["x_dbn_channel_id"] and each channel runs without a gap while
    # the instruments interleave, then no V032; a gap in one channel is that channel's line.
    channels = {"instrument_id": ["A", "B", "A", "B", "A"], "x_dbn_channel_id": [1, 2, 1, 2, 1]}
    days = {DAY: seq(10, 70, 11, 71, 12, **channels),
            "2024-01-03": seq(10, 70, 11, 75, 14, **channels)}  # fmt: skip
    found = judge(tmp_path, days, ["x_dbn_channel_id"], kind="trades")
    assert gaps(found) == [
        ({"venue": "XNYS", "date": "2024-01-03", "x_dbn_channel_id": 1}, 2,
         "2 missing sequence number(s); first gap 11 -> 14"),
        ({"venue": "XNYS", "date": "2024-01-03", "x_dbn_channel_id": 2}, 4,
         "4 missing sequence number(s); first gap 70 -> 75"),
    ]  # fmt: skip
    assert list(found[0].key or ()) == ["venue", "date", "x_dbn_channel_id"]
    # the same rows under [] are one group per partition: 12 -> 70 is a gap of 57 on day 1;
    # day 2 adds 11 -> 14 (2) and 70 -> 75 (4) to 14 -> 70 (55)
    assert [f.count for f in judge(tmp_path / "all", days, [], kind="quotes")] == [57, 61]


def test_a_listed_partition_column_adds_nothing_to_the_group(tmp_path: Path) -> None:
    assert gaps(judge(tmp_path, {DAY: seq(1, 3)}, ["venue"])) == [
        (PART, 1, "1 missing sequence number(s); first gap 1 -> 3")
    ]


def test_book_deltas_snapshot_rows_are_left_out(tmp_path: Path) -> None:
    # When a partition starts with a `clear` row at sequence 0 and snapshot `add` rows numbered
    # out of order, all `is_snapshot = true`, then they give no V032 (#348's Databento example).
    numbers = (0, 761, 757, 756, 754, 755, 1000, 1001)
    snapshot = [True] * 6 + [False] * 2
    assert judge(tmp_path, {DAY: seq(*numbers, is_snapshot=snapshot)}, []) == []
    # only book_deltas has the column: on trades the same rows are all counted, sorted
    # 0, 754 … 757, 761, 1000, 1001: 753 + 3 + 238 missing
    found = judge(tmp_path / "trades", {DAY: seq(*numbers, is_snapshot=snapshot)}, [], "trades")
    assert [f.message for f in found] == ["994 missing sequence number(s); first gap 0 -> 754"]


def test_no_declaration_or_another_kind_gives_no_V032(tmp_path: Path) -> None:
    # When a dataset has no sequence_consecutive_within, then no V032.
    assert judge(tmp_path / "absent", {DAY: seq(1, 5)}, ABSENT) == []
    # The key on a dataset of another kind is ignored.
    assert judge(tmp_path / "status", {DAY: seq(1, 5)}, [], kind="trading_status_events") == []


def _declared(within: object, **params: object) -> Any:
    """A `trades` dataset (`venue=XNYS`, one row) declaring `within`, plus `params`."""
    row = {"instrument_id": ["US:AAA"], "sequence": pa.array([1], pa.int64())}
    return build._both(build._add("trades", row, f"trades/venue=XNYS/date={DAY}/p.parquet"),
                       lambda m, f: m["datasets"][-1].update(
                           params={"sequence_consecutive_within": within, **params}))  # fmt: skip


@pytest.mark.parametrize(
    ("within", "said"),
    [  # When the list holds `sequence` or a name twice, then TDS-M001.
        (["sequence"], '"sequence" does not match'),
        (["x_dbn_channel_id", "x_dbn_channel_id"], "'x_dbn_channel_id' is listed twice"),
        ("instrument_id", "is not a JSON array"),
        ([1], "1 is not a JSON string"),
    ],
)
def test_the_manifest_schema_gives_the_key_its_shape(
    within: object, said: str, tmp_path: Path
) -> None:
    errors = check(write(tmp_path, _declared(within)), level="manifest").errors
    assert [(e.code, said in e.message) for e in errors] == [("TDS-M001", True)]
    assert errors[0].message.startswith("$.datasets[2].params.sequence_consecutive_within")


def test_the_other_params_keys_stay_open(tmp_path: Path) -> None:
    pkg = write(tmp_path, _declared([], depth=5, continuity=["any"]))
    assert check(pkg, level="manifest").errors == ()


def test_a_listed_column_missing_from_a_footer_is_S001(tmp_path: Path) -> None:
    # When the list names a column no file has, then TDS-S001 at the `schema` level; a listed
    # partition column is not an error.
    errors = check(write(tmp_path, _declared(["x_dbn_channel_id", "venue"])), level="schema")
    listed = [e for e in errors.errors if "x_dbn_channel_id" in e.message or "venue" in e.message]
    assert [(e.code, e.message, e.file) for e in listed] == [
        ("TDS-S001", "column x_dbn_channel_id in params.sequence_consecutive_within is missing",
         f"trades/venue=XNYS/date={DAY}/p.parquet")
    ]  # fmt: skip

    # on a kind V032 does not read, the key is ignored
    def bars(m: dict[str, Any], f: Any) -> None:
        m["datasets"][1]["params"]["sequence_consecutive_within"] = ["x_y"]

    assert check(write(tmp_path / "bars", bars), level="schema").errors == ()


def test_an_unreadable_file_leaves_V032_unchecked(tmp_path: Path) -> None:
    m, files = build.base()
    rel = f"trades/venue=XNYS/date={DAY}/part-00000.parquet"
    files[rel] = b"not parquet"
    m["datasets"].append({"name": "trades", "kind": "trades", "schema_version": "1.0",
                          "path": "trades", "params": {"sequence_consecutive_within": []},
                          "files": [{"path": rel, "bytes": len(files[rel])}]})  # fmt: skip
    blind: set[str] = set()
    assert check_sequences(read_manifest(build.write(tmp_path, m, files)), None, blind) == []
    assert blind == {"TDS-V032"}


def test_a_file_without_a_listed_column_leaves_V032_unchecked(tmp_path: Path) -> None:
    # review: its rows would otherwise fall into one group of null channel and show false gaps
    m, files = build.base()
    entries = []
    for n, columns in enumerate([seq(1, 9), seq(2, 10, x_dbn_channel_id=[1, 2])]):
        rel = f"trades/venue=XNYS/date={DAY}/part-{n:05}.parquet"
        files[rel] = build.parquet(pa.table(columns), "trades")
        entries.append({"path": rel, "bytes": len(files[rel])})
    within = {"sequence_consecutive_within": ["x_dbn_channel_id"]}
    m["datasets"].append({"name": "trades", "kind": "trades", "schema_version": "1.0",
                          "path": "trades", "files": entries, "params": within})  # fmt: skip
    blind: set[str] = set()
    assert check_sequences(read_manifest(build.write(tmp_path, m, files)), None, blind) == []
    assert blind == {"TDS-V032"}
