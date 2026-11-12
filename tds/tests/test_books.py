"""TDS-V031 on a book rebuilt from `book_deltas` by #347's rules (TDS 5.8)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

import pyarrow as pa
import pytest

from nexusbt_tds.books import check_books
from nexusbt_tds.check import Finding
from nexusbt_tds.manifest import read_manifest

from .conformance_build import build

T0 = dt.datetime(2024, 1, 2, 14, 30, tzinfo=dt.UTC)
#: (action, side, price, size, is_last[, order_id[, instrument_id]])
Row = tuple[Any, ...]


def judge(
    tmp_path: Path,
    days: dict[str, list[Row]],
    kind: str = "mbp",
    carry: bool = False,
    snapshot: int = 0,
) -> tuple[list[Finding], list[str]]:
    """V031's lines and notes on a package whose `book_deltas` holds `days` (`venue=XNYS`); the
    first `snapshot` rows of each day are `is_snapshot` rows."""
    m, files = build.base()
    entries = []
    for day, rows in days.items():
        full = [(*r, *(None, "US:AAA")[len(r) - 5 :]) for r in rows]
        rel = f"book_deltas/venue=XNYS/date={day}/part-00000.parquet"
        table = pa.table({
            "instrument_id": [r[6] for r in full],
            "session_date": [dt.date.fromisoformat(day)] * len(full),
            "ts_event": pa.array([T0 + dt.timedelta(seconds=n) for n in range(len(full))],
                                 pa.timestamp("ns", "UTC")),
            "sequence": list(range(len(full))),
            "action": [r[0] for r in full], "side": [r[1] for r in full],
            "price": pa.array([r[2] for r in full], pa.float64()),
            "size": pa.array([r[3] for r in full], pa.float64()),
            "order_id": pa.array([r[5] for r in full], pa.int64()),
            "is_snapshot": [n < snapshot for n in range(len(full))],
            "is_last": [r[4] for r in full],
        })  # fmt: skip
        files[rel] = build.parquet(table, "book_deltas")
        entries.append({"path": rel, "rows": len(full), "bytes": len(files[rel])})
    params = {"depth_kind": kind} | ({"continuity": "carry"} if carry else {})
    m["datasets"].append({"name": "book_deltas", "kind": "book_deltas", "schema_version": "1.0",
                          "path": "book_deltas", "params": params, "files": entries})  # fmt: skip
    blind: set[str] = set()
    notes: list[str] = []
    found = check_books(read_manifest(build.write(tmp_path, m, files)), None, blind, notes)
    assert blind == ({"TDS-V031"} if kind not in ("mbp", "mbo") else set())
    return found, notes


def crossed(found: list[Finding]) -> list[tuple[Any, ...]]:
    """(session_date, instrument_id, first crossed ts_event, count) of each V031 line."""
    assert {(f.code, f.severity) for f in found} <= {("TDS-V031", "warning")}
    return [(f.key["session_date"], f.key["instrument_id"], f.key["ts_event"], f.count)
            for f in found if f.key]  # fmt: skip


def at(n: int) -> str:
    return str(T0 + dt.timedelta(seconds=n))


def test_mbp_crossed_after_is_last(tmp_path: Path) -> None:
    rows = [("add", "bid", 101, 1, False), ("add", "ask", 100, 1, True)]
    found, notes = judge(tmp_path, {"2024-01-02": rows})
    assert crossed(found) == [("2024-01-02", "US:AAA", at(1), 1)]
    assert notes == []


def test_mbp_size_is_the_new_total_and_only_0_or_null_removes(tmp_path: Path) -> None:
    rows = [
        ("add", "bid", 101, 2, True),  # one side only: not judged
        ("cancel", "bid", 101, 1, False),  # a non-zero cancel keeps the level
        ("add", "ask", 100, 1, True),  # crossed 1
        ("cancel", "bid", 101, 0, True),
        ("add", "bid", 101, 1, True),  # crossed 2
        ("modify", "bid", 101, None, True),
        ("modify", "bid", 101, 3, True),  # crossed 3
    ]
    assert crossed(judge(tmp_path, {"2024-01-02": rows})[0]) == [("2024-01-02", "US:AAA", at(2), 3)]


def test_mbo_orders(tmp_path: Path) -> None:
    rows = [
        ("add", "bid", 101, 5, True, 1),
        ("add", "ask", 100, 5, True, 2),  # crossed 1
        ("cancel", "bid", 101, 2, True, 1),  # reduced to 3: crossed 2
        ("cancel", "ask", 100, 9, True, 99),  # unknown order: ignored, crossed 3
        ("modify", "bid", 99, 3, True, 1),  # price replaced: not crossed
        ("modify", "bid", 102, 1, True, 7),  # unknown order inserted: crossed 4
        ("cancel", "bid", 102, None, True, 7),  # null size removes it
        ("cancel", "bid", 99, 3, True, 1),  # at least the remaining size removes it
        ("add", "bid", 101, 1, True, 8),  # crossed 5
        ("cancel", "bid", 101, 5, True, 8),
    ]
    assert crossed(judge(tmp_path, {"2024-01-02": rows}, "mbo")[0]) == [
        ("2024-01-02", "US:AAA", at(1), 5)
    ]


@pytest.mark.parametrize("kind", ["mbp", "mbo"])
def test_clear_empties_and_trade_fill_none_change_nothing(kind: str, tmp_path: Path) -> None:
    rows = [
        ("clear", "none", None, None, False),  # the start of the file
        ("add", "bid", 101, 1, False, 1),  # is_snapshot rows, by the same table
        ("add", "ask", 100, 1, True, 2),  # crossed 1
        ("trade", "bid", 101, 1, True, 1),  # crossed 2: the order is not reduced
        ("fill", "ask", 100, 0, True, 2),  # crossed 3: the level is not removed
        ("none", "none", None, None, True),  # crossed 4
        ("clear", "none", None, None, True),  # in the middle of the day
        ("add", "ask", 100, 1, True, 3),  # the bid went with the clear: not crossed
    ]
    found, _ = judge(tmp_path, {"2024-01-02": rows}, kind, snapshot=3)
    assert crossed(found) == [("2024-01-02", "US:AAA", at(2), 4)]


def test_judged_after_each_is_last_row_never_mid_batch(tmp_path: Path) -> None:
    rows = [
        ("add", "bid", 99, 1, False),
        ("add", "ask", 100, 1, True),
        ("add", "bid", 101, 1, False),  # crossed inside the batch only
        ("cancel", "bid", 101, 0, False),
        ("none", "none", None, None, True),  # is_last on a separate `none` row
        ("add", "bid", 101, 1, False),
        ("none", "none", None, None, True),  # crossed 1
    ]
    assert crossed(judge(tmp_path, {"2024-01-02": rows})[0]) == [("2024-01-02", "US:AAA", at(6), 1)]


def test_locked_or_one_sided_book_is_not_crossed(tmp_path: Path) -> None:
    rows = [
        ("add", "bid", 100, 1, False),
        ("add", "ask", 100, 1, True),  # locked
        ("cancel", "ask", 100, 0, False),
        ("add", "bid", 102, 1, True),  # no ask level
    ]
    assert judge(tmp_path, {"2024-01-02": rows}) == ([], [])


def test_one_line_per_instrument(tmp_path: Path) -> None:
    rows = [
        ("add", "bid", 101, 1, False, None, "US:AAA"),
        ("add", "bid", 101, 1, False, None, "US:BBB"),
        ("add", "ask", 100, 1, True, None, "US:BBB"),  # BBB crossed 1
        ("add", "ask", 100, 1, True, None, "US:AAA"),  # AAA crossed 1
        ("none", "none", None, None, True, None, "US:BBB"),  # BBB crossed 2
    ]
    assert crossed(judge(tmp_path, {"2024-01-02": rows})[0]) == [
        ("2024-01-02", "US:BBB", at(2), 2),
        ("2024-01-02", "US:AAA", at(3), 1),
    ]


def test_an_unknown_depth_kind_leaves_V031_unchecked(tmp_path: Path) -> None:
    rows = [("add", "bid", 101, 1, False), ("add", "ask", 100, 1, True)]
    found, notes = judge(tmp_path, {"2024-01-02": rows}, "l2")
    assert found == []
    assert notes == ["TDS-V031 not checked on book_deltas: depth_kind 'l2' is not mbp or mbo"]


@pytest.mark.parametrize("carry", [True, False])
def test_carry_starts_from_the_previous_partition(carry: bool, tmp_path: Path) -> None:
    days: dict[str, list[Row]] = {
        "2024-01-02": [
            ("add", "bid", 101, 1, True),
            ("add", "ask", 100, 1, False),  # a batch left open: not carried
        ],
        "2024-01-03": [
            ("none", "none", None, None, True),  # the carried bid alone: not crossed
            ("add", "ask", 100, 1, True),  # crossed 1, with the carried bid
        ],
    }
    found, notes = judge(tmp_path, days, carry=carry)
    assert crossed(found) == ([("2024-01-03", "US:AAA", at(1), 1)] if carry else [])
    assert len(notes) == carry
    assert all("XNYS date 2024-01-02 judged from a partial book" in n for n in notes)
