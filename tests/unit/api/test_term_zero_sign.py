"""A term's value is never -0.0 (spec 5.4.1, #648): through `nx.run_pipeline`, at each kind of
term that makes a value.

`falling` is the synthetic `tiny` KR package (4.8) with every price falling 1% a session, so
`Returns(2)` is below zero in every cell and `Returns(2) * 0.0` is -0.0 in every cell, on any
CPU. A window of those cells holds no +0.0, so which of two equal zeros a minimum or a maximum
picks does not decide the test: before the rule, the three terms of #648's table are -0.0
everywhere.

A package's own -0.0 (TDS allows it; S009 forbids only NaN and ±Inf) is a column cell, not a
term's value: a window over the column reads it as it is, the same in every run; a term made
from it holds +0.0 (#648's Decisions, 2026-11-20).
"""

from __future__ import annotations

import json
import math
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

import nexusbt as nx
from nexusbt.compute import _chunks
from nexusbt.factors import MaxDrawdown, Returns, RollingStd, SimpleMovingAverage
from nexusbt.testing._synth_package import _write
from nexusbt.testing.synth import make_snapshot
from nexusbt_tds.hash import write_hashes

pytestmark = pytest.mark.unit

ZEROS = Returns(2) * 0.0  # -0.0 in every cell of `falling`, as the product's own value
START, END = "2020-01-13", "2020-01-23"  # 9 sessions of 5 instruments: 45 cells a column
#: Built-in kernels that read the volume column as a window: a sum, a standard deviation of
#: equal cells, and a drawdown over a zero peak (NaN, #632).
ON_VOLUME: dict[str, nx.Term] = {
    "sma": SimpleMovingAverage(3, inputs=[nx.Price.volume]),
    "std": RollingStd(3, inputs=[nx.Price.volume]),
    "drawdown": MaxDrawdown(3, inputs=[nx.Price.volume]),
}


def _package(root: Path, change: Callable[[pa.Table], pa.Table]) -> Path:
    """`tiny` KR with its bars rewritten by `change`."""
    root = make_snapshot(root, preset="tiny", markets=("KR",))
    manifest = json.loads((root / "tds.json").read_text(encoding="utf-8"))
    (entry,) = (d for d in manifest["datasets"] if d["kind"] == "bars")
    for file in entry["files"]:
        bars = change(pq.read_table(root / file["path"]))
        file.update(_write(root, file["path"], entry["name"], bars))
    (root / "tds.json").write_text(json.dumps(manifest), encoding="utf-8")
    write_hashes(root)
    return root


def _set(bars: pa.Table, name: str, cells: Any) -> pa.Table:
    return bars.set_column(bars.schema.get_field_index(name), name, pa.array(cells, pa.float64()))


def _fall(bars: pa.Table) -> pa.Table:
    """Each instrument's prices on its k-th bar: `close_0 * 0.99**k`."""
    bars = bars.sort_by([("instrument_id", "ascending"), ("session_date", "ascending")])
    ids, close = bars["instrument_id"].to_pylist(), bars["close"].to_pylist()
    prices, first, k = [], 0.0, 0
    for i, (one, c) in enumerate(zip(ids, close, strict=True)):
        first, k = (c, 0) if i == 0 or ids[i - 1] != one else (first, k + 1)
        prices.append(first * 0.99**k)
    for name in ("open", "high", "low", "close"):
        bars = _set(bars, name, prices)
    return _set(bars, "value_traded", np.multiply(prices, bars["volume"].to_numpy()))


@pytest.fixture(scope="module")
def falling(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return _package(tmp_path_factory.mktemp("s") / "pkg", _fall)


def _volume(zero: float) -> Callable[[pa.Table], pa.Table]:
    return lambda bars: _set(bars, "volume", np.full(len(bars), zero))


@pytest.fixture(scope="module")
def minus_zero(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The package with every volume -0.0."""
    return _package(tmp_path_factory.mktemp("v") / "pkg", _volume(-0.0))


@pytest.fixture(scope="module")
def plus_zero(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The package with every volume +0.0."""
    return _package(tmp_path_factory.mktemp("v") / "pkg", _volume(0.0))


@pytest.fixture(autouse=True)
def no_toml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)


def run(package: Path, columns: Mapping[str, nx.Term], start: str = START,
        end: str = END) -> pa.Table:  # fmt: skip
    return nx.run_pipeline(nx.Pipeline(dict(columns)), start=start, end=end,
                           snapshot=str(package)).table  # fmt: skip


def zero_signs(package: Path, columns: Mapping[str, nx.Term]) -> dict[str, list[bool]]:
    """Each column's zero cells, `True` where the zero's sign bit is set; every column must
    hold some zero, so a test cannot pass on no cell."""
    table = run(package, columns)
    found = {name: [math.copysign(1.0, v) < 0 for v in table[name].to_pylist() if v == 0]
             for name in columns}  # fmt: skip
    assert all(found.values()), found
    return found


def bits(table: pa.Table) -> dict[str, list[int]]:
    """Each float column's cells as their 64 bits, NaN's payload and a zero's sign included."""
    return {name: np.asarray(table[name].to_numpy(zero_copy_only=False)).view(np.int64).tolist()
            for name in table.column_names if pa.types.is_float64(table[name].type)}  # fmt: skip


def test_the_three_terms_of_648_have_no_negative_zero(falling: Path) -> None:
    """#648's table: `rolling(...).max()`, `rolling(...).min()` and `MaxDrawdown` of falling
    returns. Every cell is a zero (the drawdown's at the peak, `0 / peak` with a peak below 0),
    and none is -0.0."""
    columns = {"t3": nx.ops.rolling(ZEROS, 5).max(), "t4": nx.ops.rolling(ZEROS, 5).min(),
               "t11": MaxDrawdown(2, inputs=[Returns(2)])}  # fmt: skip
    assert zero_signs(falling, columns) == {name: [False] * 45 for name in columns}


def test_arithmetic_has_no_negative_zero(falling: Path) -> None:
    """A product (`-x * 0.0`), a negation of +0.0 and a cross-section `demean` of -0.0 cells
    (`x - mean`: -0.0 - 0.0)."""
    columns = {"mul": ZEROS, "neg": -(nx.Price.close.latest * 0.0), "demean": ZEROS.demean()}
    assert zero_signs(falling, columns) == {name: [False] * 45 for name in columns}


def test_a_user_function_output_has_no_negative_zero(falling: Path) -> None:
    """`@nx.factor` returning `close * -0.0` (3.3), -0.0 for every positive close."""

    @nx.factor(1, [nx.Price.close])
    def negative_zero(close: Any) -> Any:
        return close[-1] * -0.0

    assert zero_signs(falling, {"user": negative_zero}) == {"user": [False] * 45}


def test_a_column_read_by_latest_is_plus_zero(minus_zero: Path) -> None:
    """`Price.volume.latest` is a term: the package's -0.0 is +0.0 there."""
    found = zero_signs(minus_zero, {"volume": nx.Price.volume.latest})
    assert found == {"volume": [False] * 45}


def test_a_kernel_over_a_column_window_gives_the_bits_of_plus_zero(
    minus_zero: Path, plus_zero: Path
) -> None:
    """Built-in kernels reading the volume column as a window give, over -0.0 cells, the bits
    they give over +0.0 cells (#632: a kernel does not see a zero's sign; #648: its value is
    +0.0)."""
    minus, plus = bits(run(minus_zero, ON_VOLUME)), bits(run(plus_zero, ON_VOLUME))
    assert minus == plus
    assert set(plus["sma"]) == set(plus["std"]) == {0}  # +0.0 in every cell


def test_a_user_function_sees_the_package_zero_and_returns_plus_zero(minus_zero: Path) -> None:
    """`@nx.factor` over the volume column reads the package's -0.0 in its window: it returns
    -0.0 where `np.signbit` says so and 1.0 where not, and the -0.0 it returns is +0.0 as the
    term's value."""

    @nx.factor(2, [nx.Price.volume])
    def signed(volume: Any) -> Any:
        return np.where(np.signbit(volume[-1]), -0.0, 1.0)

    assert zero_signs(minus_zero, {"user": signed}) == {"user": [False] * 45}


def test_a_package_zero_gives_the_same_bits_in_any_chunking(
    minus_zero: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """INV-03: the package's -0.0 is read the same in every chunk, so a budget that cuts the
    quarter into months gives the same bits as one chunk."""
    columns = {"latest": nx.Price.volume.latest, **ON_VOLUME}
    whole = bits(run(minus_zero, columns, "2020-01-02", "2020-03-31"))
    made: list[int] = []
    spans = _chunks.spans

    def recorded(*args: Any) -> list[tuple[int, int]]:
        made.append(len(found := spans(*args)))
        return found

    monkeypatch.setattr(_chunks, "GB", 2_500)  # about a month of `tiny` a chunk
    monkeypatch.setattr(_chunks, "spans", recorded)
    assert bits(run(minus_zero, columns, "2020-01-02", "2020-03-31")) == whole
    assert made[0] > 1
