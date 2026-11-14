"""The top-level `nx.<name>(...)` functions of 3.8, evaluate to open (#61 Decisions).

`**common` is 3.8's common keywords. The result types the functions alone name
live here.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from nexusbt import pipeline
from nexusbt.config import Config, load_config
from nexusbt.data import DataConfig, _snapshot_markets, open_snapshot

if TYPE_CHECKING:
    from nexusbt.data import Explanation, Snapshot
    from nexusbt.pipeline import BoundColumn, Factor, Filter, Pipeline, Term

_Day = str | dt.date
_Scenario = Literal["gross", "cost0x", "cost2x", "delist_lo", "delist_hi", "capacity"]


# Empty until their tickets; kept as a table.
# fmt: off
@dataclass(frozen=True, slots=True)
class Strategy: ...
@dataclass(frozen=True, slots=True)
class CostModel: ...
@dataclass(frozen=True, slots=True)
class Split: ...
@dataclass(frozen=True, slots=True)
class Book: ...
@dataclass(frozen=True, slots=True)
class FactorReport: ...
@dataclass(frozen=True, slots=True)
class Run: ...
@dataclass(frozen=True, slots=True)
class Screen: ...
@dataclass(frozen=True, slots=True)
class Orders: ...
@dataclass(frozen=True, slots=True)
class BookUpdate: ...
@dataclass(frozen=True, slots=True)
class ReconcileReport: ...
@dataclass(frozen=True, slots=True)
class SweepResult: ...
@dataclass(frozen=True, slots=True)
class Comparison: ...
@dataclass(frozen=True, slots=True)
class DecisionExplanation: ...
@dataclass(frozen=True, slots=True)
class CheckReport: ...
@dataclass(frozen=True, slots=True)
class RunTable: ...
@dataclass(frozen=True, slots=True)
class Preregistration: ...
# fmt: on


def evaluate(
    term: Factor | Mapping[str, Factor],
    *,
    target: str | BoundColumn = "fwd_return",
    freq: Literal["monthly", "weekly", "daily"] = "monthly",
    horizons: Sequence[int | Literal["next"]] = ("next",),
    quantiles: int = 5,
    universe: Filter | None = None,
    by: Sequence[Literal["market", "year", "segment"]] = ("market",),
    delisting: Literal["observed_then_policy", "observed_only", "lo", "hi"] | None = None,
    save_signal: bool = False,  # 3.8 and 5.8 (#82)
    **common: Any,
) -> FactorReport:
    raise NotImplementedError


def backtest(
    strategy: Strategy,
    *,
    capital: float | None = None,
    base_ccy: str | None = None,
    clock: str | None = None,
    sleeves: Mapping[str, float] | None = None,
    costs: CostModel | None = None,
    delisting: str | None = None,
    params: Mapping[str, Any] | None = None,
    preset: Literal["realistic", "zipline"] = "realistic",
    offsets: int | None = None,
    scenarios: bool | Sequence[_Scenario] = True,
    save_signal: bool = False,
    method: Literal["linear", "walk_forward", "cpcv", "cscv"] | Split = "linear",
    grid: Mapping[str, Sequence[Any]] | None = None,
    select: Literal["net_sharpe", "cagr", "calmar"] = "net_sharpe",
    preview: bool = False,
    **common: Any,
) -> Run:
    raise NotImplementedError


def screen(
    obj: Strategy | Factor | Pipeline,
    *,
    asof: _Day | None = None,
    top: int | None = None,
    params: Mapping[str, Any] | None = None,
    anchor: _Day | None = None,
    show: Literal["selected", "all", "held+near"] = "selected",
    near: int = 10,
    book: Book | str | None = None,
    account: Literal["auto", "none", "book", "backtest"] = "auto",
    **common: Any,
) -> Screen:
    raise NotImplementedError


def live(
    strategy: Strategy,
    *,
    book: Book | str,
    asof: _Day | None = None,
    params: Mapping[str, Any] | None = None,
    snapshot: str | Snapshot | None = None,
) -> Orders:
    raise NotImplementedError


def fill(
    book: Book | str,
    orders: Orders | None = None,
    *,
    at: Literal["next_open"] = "next_open",
    snapshot: str | Snapshot | None = None,
) -> BookUpdate:
    raise NotImplementedError


def reconcile(
    book: Book | str, *, restate: bool = False, snapshot: str | Snapshot | None = None
) -> ReconcileReport:
    raise NotImplementedError


def sweep(
    strategy: Strategy,
    *,
    grid: Mapping[str, Sequence[Any]] | None = None,
    pbo_blocks: int = 16,
    **backtest_kwargs: Any,
) -> SweepResult:
    raise NotImplementedError


def compare(
    *items: str | Run | Strategy, metrics: Sequence[str] | None = None, **backtest_kwargs: Any
) -> Comparison:
    raise NotImplementedError


def explain(
    obj: Term | Strategy,
    instrument_id: str,
    date: _Day,
    *,
    snapshot: str | Snapshot | None = None,
    edition: Literal["strict", "compare"] | None = None,
    params: Mapping[str, Any] | None = None,
) -> Explanation | DecisionExplanation:
    raise NotImplementedError


def check(
    obj: Term | Pipeline | Strategy,
    *,
    probes: int = 0,
    seed: int = 0,
    start_probe: bool = False,
    verbose: bool = False,
) -> CheckReport:
    raise NotImplementedError


@dataclass(frozen=True, slots=True)
class Description:
    """`nx.describe`'s result; `print` shows its text."""

    text: str

    def __str__(self) -> str:
        return self.text


def describe(obj: object | None = None) -> Description:
    """A term (3.3) for now: its node tree and structural hash; other objects with their tickets."""
    if isinstance(obj, pipeline.Term):
        return Description(pipeline.describe_term(obj))
    raise NotImplementedError


def runs(*, study: str | None = None, kind: str | None = None, limit: int = 50) -> RunTable:
    raise NotImplementedError


def rerun(run_id: str, *, new_snapshot: bool = False, trust: bool = False) -> Run:
    raise NotImplementedError


def book(spec: str) -> Book:
    raise NotImplementedError


def override(
    book: Book | str,
    instrument_id: str,
    kind: Literal["no_trade", "reduce_only", "close"],
    *,
    from_: _Day | None = None,
    until: _Day | None = None,
    note: str = "",
) -> BookUpdate:
    raise NotImplementedError


def record_fills(book: Book | str, csv: str | Path) -> BookUpdate:
    raise NotImplementedError


def cash_flow(
    book: Book | str,
    amount: float,
    *,
    ccy: str,
    sleeve: str,
    session: _Day | None = None,
    note: str = "",
) -> BookUpdate:
    raise NotImplementedError


def preregister(
    strategy: Strategy | Factor,
    *,
    metric: Literal["net_sharpe", "cagr", "ic_mean", "dsr"],
    threshold: float,
    segment: str = "validation",
    note: str = "",
) -> Preregistration:
    raise NotImplementedError


def config() -> Config:
    """`nexusbt.toml` of the working folder, resolved against the snapshot `[data]` points at."""
    path = Path("nexusbt.toml") if Path("nexusbt.toml").is_file() else None
    markets = _snapshot_markets(load_config(path))
    return load_config(path, markets=markets) if markets else load_config(path)


def open(path: str | Path) -> Snapshot:  # noqa: A001 - the 3.1 name `nx.open`
    """One package folder, or a parent folder whose `LATEST` names one (4.2, V31-PUB-03)."""
    return open_snapshot(DataConfig(Path(path)))
