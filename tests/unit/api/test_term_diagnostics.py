"""`PipelineResult.term_diagnostics` (spec 5.4.1, 3.5; #249, #536) and one scenario through
`nx.run_pipeline` on the synthetic `tiny` KR package (4.8) with a split, a late bar and zero
denominators (#249's criteria of 2026-11-18).

`tiny`'s closes are hand-checkable: instrument n's close on its k-th listed session is
`10000·n·c[k % 4]`, `c = (1.00, 1.01, 1.02, 1.01)`. So `Returns(3)` over `close` (rows k-2..k,
3.4) is `c[k]/c[k-2] - 1`: 0 for an odd k, 1.02/1.00 - 1 = 0.02 for k % 4 = 2, and
1.00/1.02 - 1 = -1/51 for k % 4 = 0, whatever n. January's KR sessions are k = 0 (01-02) .. 19
(01-31): 01-13 is k = 7, 01-15 k = 9, 01-20 k = 12, 01-22 k = 14, 01-29 k = 17.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

import nexusbt as nx
from nexusbt.compute import _chunks
from nexusbt.factors import Returns
from nexusbt.pipeline import graph_hash
from nexusbt.testing._synth_package import _write
from nexusbt.testing.synth import make_snapshot
from nexusbt_tds.hash import write_hashes

pytestmark = pytest.mark.unit

RET = Returns(3, inputs=[nx.Price.close])
INV = 1 / RET  # x/0 wherever RET is 0
#: A 2:1 split of KR:T00001 on 2020-01-15 (k = 9): the generator halves its raw closes from then.
SPLIT = {"dataset": "corporate_actions", "instrument_id": "KR:T00001", "kind": "split",
         "ex_date": "2020-01-15", "ratio_num": 2, "ratio_den": 1}  # fmt: skip
#: KR:T00002's bar of 2020-01-20 (k = 12) becomes available at the close of 2020-01-22 (k = 14).
LATE, LATE_DAY, SEEN_AT = "KR:T00002", dt.date(2020, 1, 20), "2020-01-22T06:30:00+00:00"
IDS = [f"KR:T0000{n}" for n in range(1, 6)]


def label(term: nx.Term) -> str:
    return f"{str(nx.describe(term)).splitlines()[0]} {graph_hash(term)[:12]}"


@pytest.fixture(scope="module")
def scenario(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """`tiny` KR with SPLIT and the late bar, its bars available by a `ts_available` column."""
    root = make_snapshot(tmp_path_factory.mktemp("s") / "pkg", preset="tiny", markets=("KR",),
                         events=[SPLIT])  # fmt: skip
    manifest = json.loads((root / "tds.json").read_text(encoding="utf-8"))
    (entry,) = (d for d in manifest["datasets"] if d["kind"] == "bars")
    entry["availability"] = {"column": "ts_available"}
    for file in entry["files"]:
        bars = pq.read_table(root / file["path"])
        keys = zip(bars["instrument_id"].to_pylist(), bars["session_date"].to_pylist(), strict=True)
        late = [k == (LATE, LATE_DAY) for k in keys]
        seen = pa.array([dt.datetime.fromisoformat(SEEN_AT) if k else None for k in late],
                        bars["ts_end"].type)  # fmt: skip
        bars = bars.append_column("ts_available", pa.compute.coalesce(seen, bars["ts_end"]))
        file.update(_write(root, file["path"], entry["name"], bars))
    (root / "tds.json").write_text(json.dumps(manifest), encoding="utf-8")
    write_hashes(root)
    return root


@pytest.fixture(autouse=True)
def no_toml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)


def run(package: Path, columns: Mapping[str, nx.Term], start: str, end: str,
        screen: nx.Filter | None = None) -> nx.PipelineResult:  # fmt: skip
    return nx.run_pipeline(nx.Pipeline(columns, screen), start=start, end=end,
                           snapshot=str(package))  # fmt: skip


def test_scenario_values_and_screened_rows(scenario: Path) -> None:
    """Each instrument's `Returns(3)` across the split (k = 10: 0.02, not 5100/10000 - 1) and
    the late bar (KR:T00002 is NaN at k = 12, its own end not yet seen, and 0.02 at k = 14, when
    it is), and the rows `screen=RET > 0` keeps: k % 4 = 2, every instrument."""
    every = run(scenario, {"ret": RET}, "2020-01-13", "2020-01-23").table.to_pylist()
    got = {(r["session_date"], r["instrument_id"]): r["ret"] for r in every}
    day = dt.date(2020, 1, 16)
    assert [got[day, i] for i in IDS] == pytest.approx([0.02] * 5)
    late = [got[LATE_DAY, i] for i in IDS]
    assert math.isnan(late.pop(1))  # KR:T00002
    assert late == pytest.approx([-1 / 51] * 4)
    kept = run(scenario, {"ret": RET, "inv": INV}, "2020-01-13", "2020-01-23", screen=RET > 0)
    rows = kept.table.to_pylist()
    days = (dt.date(2020, 1, 16), dt.date(2020, 1, 22))
    assert [(r["session_date"], r["instrument_id"]) for r in rows] == [
        (d, i) for d in days for i in IDS
    ]
    assert [r["inv"] for r in rows] == pytest.approx([50.0] * 10)


def test_scenario_zero_denominators_counted(scenario: Path) -> None:
    """5.4.1: `1 / RET` divides by 0 at every odd k, 5 listed cells each; at k = 12 KR:T00002's
    divisor is NaN, not 0, and the other four are -1/51: nothing counted. The screen does not
    change the counts."""
    result = run(scenario, {"inv": INV}, "2020-01-13", "2020-01-23", screen=RET > 0)
    days = [dt.date(2020, 1, d) for d in (13, 15, 17, 21, 23)]
    assert result.term_diagnostics.to_pylist() == [
        {"market": "KR", "session_date": d, "term": label(INV), "diagnostic": "DivisionByZero",
         "n": 5} for d in days]  # fmt: skip


def test_monthly_counts_rows_that_are_not_decisions(scenario: Path) -> None:
    """A window over `1 / RET` at the decision of 2020-01-31 (k = 19) reads it at k = 17..19,
    so the x/0 of 01-29 (k = 17), not a decision, is counted there (5.4.1: the row that produced
    the cell); the table itself holds 01-31 only."""
    columns = {"inv3": nx.ops.rolling(INV, 3).sum()}
    result = nx.run_pipeline(nx.Pipeline(columns), start="2020-01-02", end="2020-02-10",
                             freq="monthly", snapshot=str(scenario))  # fmt: skip
    assert set(result.table["session_date"].to_pylist()) == {dt.date(2020, 1, 31)}
    assert result.term_diagnostics.to_pylist() == [
        {"market": "KR", "session_date": dt.date(2020, 1, d), "term": label(INV),
         "diagnostic": "DivisionByZero", "n": 5} for d in (29, 31)]  # fmt: skip


def test_each_diagnostic_counted(scenario: Path) -> None:
    """5.4.1's three: `exp(close)` overflows in each of the 5 cells of every row
    (`InfiniteResult`); a rank grouped by `RET.quantiles(2)` leaves out the 5 cells of group -1
    in k = 0 and 1, where RET has no window yet (`UnknownGroup`); `1 / RET` at k = 3."""
    big, ranked = nx.Price.close.latest.exp(), nx.Price.close.latest.rank(groupby=RET.quantiles(2))
    result = run(scenario, {"big": big, "rank": ranked, "inv": INV}, "2020-01-02", "2020-01-08")
    want = [(d, label(big), "InfiniteResult") for d in (2, 3, 6, 7, 8)]
    want += [(d, label(ranked), "UnknownGroup") for d in (2, 3)]
    want += [(7, label(INV), "DivisionByZero")]
    assert result.term_diagnostics.to_pylist() == [
        {"market": "KR", "session_date": dt.date(2020, 1, d), "term": t, "diagnostic": name,
         "n": 5} for d, t, name in sorted(want)]  # fmt: skip


def test_counts_do_not_depend_on_chunking(scenario: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A budget that splits the quarter into its months gives the same table, byte for byte:
    February's chunk computes `1 / RET` again on January's last rows, the rows its window
    reads before the chunk (5.3.1), and they are counted once."""
    columns = {"inv3": nx.ops.rolling(INV, 3).sum()}
    whole = run(scenario, columns, "2020-01-02", "2020-03-31")
    made: list[list[tuple[int, int]]] = []
    spans = _chunks.spans

    def recorded(*args: Any) -> list[tuple[int, int]]:
        made.append(spans(*args))
        return made[-1]

    monkeypatch.setattr(_chunks, "GB", 2_500)  # the default 4 "GB": 10 kB, about a month here
    monkeypatch.setattr(_chunks, "spans", recorded)
    split = run(scenario, columns, "2020-01-02", "2020-03-31")
    assert len(made[0]) == 3  # January, February, March
    assert ipc(split.term_diagnostics) == ipc(whole.term_diagnostics)
    assert ipc(split.table) == ipc(whole.table)


def test_unlisted_cell_read_as_unknown_through_the_api(scenario: Path) -> None:
    """#563 through the public call: KR:T00006 lists on 2020-02-18, so the day before is no cell
    of it, and `isnan().as_factor().shift(1) > 0` is unknown for it that day, not true."""
    term = nx.Price.close.latest.isnan().as_factor().shift(1) > 0
    rows = run(scenario, {"x": term}, "2020-02-18", "2020-02-18").table.to_pylist()
    assert {r["instrument_id"]: r["x"] for r in rows} == {**dict.fromkeys(IDS, False),
                                                         "KR:T00006": None}  # fmt: skip


def ipc(table: pa.Table) -> bytes:
    sink = pa.BufferOutputStream()
    with pa.ipc.new_stream(sink, table.schema) as writer:
        writer.write_table(table)
    return bytes(sink.getvalue())


SCRIPT = """
import hashlib, sys, pyarrow as pa, nexusbt as nx
from nexusbt.factors import Returns
ret = Returns(3, inputs=[nx.Price.close])
r = nx.run_pipeline(nx.Pipeline({"ret": ret, "inv": 1 / ret}, screen=ret > 0),
                    start="2020-01-02", end="2020-03-31", snapshot=sys.argv[1])
for t in (r.table, r.term_diagnostics):
    sink = pa.BufferOutputStream()
    with pa.ipc.new_stream(sink, t.schema) as w:
        w.write_table(t)
    print(hashlib.sha256(bytes(sink.getvalue())).hexdigest())
"""


def test_table_is_byte_identical_across_order_and_processes(scenario: Path,
                                                            tmp_path: Path) -> None:  # fmt: skip
    """INV-09: the same tables, byte for byte, when `tds.json` lists its datasets in reverse
    order (#547) and when the run is repeated in a fresh process."""
    result = run(scenario, {"ret": RET, "inv": INV}, "2020-01-02", "2020-03-31", screen=RET > 0)
    mine = [hashlib.sha256(ipc(t)).hexdigest() for t in (result.table, result.term_diagnostics)]
    reordered = tmp_path / "reordered"
    reordered.mkdir()
    for path in scenario.rglob("*"):
        if path.is_file():
            (reordered / path.relative_to(scenario)).parent.mkdir(parents=True, exist_ok=True)
            (reordered / path.relative_to(scenario)).write_bytes(path.read_bytes())
    manifest = json.loads((reordered / "tds.json").read_text(encoding="utf-8"))
    manifest["datasets"].reverse()
    (reordered / "tds.json").write_text(json.dumps(manifest), encoding="utf-8")
    write_hashes(reordered)
    for package in (scenario, reordered):
        args = [sys.executable, "-c", SCRIPT, str(package)]
        done = subprocess.run(  # noqa: S603 - this interpreter and the literal above
            args, capture_output=True, text=True, check=True, cwd=tmp_path
        )
        assert done.stdout.split() == mine
