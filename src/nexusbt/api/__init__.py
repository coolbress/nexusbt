"""The top-level `nx.<name>(...)` functions of 3.8, evaluate to open (#61 Decisions).

`**common` is 3.8's common keywords. The result types the functions alone name
live here.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import hashlib
import json
import sys
import warnings
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from nexusbt import pipeline
from nexusbt.api import _pipeline
from nexusbt.api._pipeline import PipelineResult as PipelineResult
from nexusbt.config import Config, load_config
from nexusbt.contracts import DataProfileWarning, PinsPolicy, SchemaRegistry
from nexusbt.data import (
    DataConfig,
    _data_root,
    _snapshot_folder,
    _snapshot_markets,
    dataset_columns,
    open_snapshot,
)
from nexusbt.data import Snapshot as _Snapshot
from nexusbt.pipeline._terms import _project_file

if TYPE_CHECKING:
    from nexusbt.artifacts import RunStore, RunTxn
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


def run_pipeline(
    pipeline: Pipeline,
    *,
    start: _Day,
    end: _Day,
    freq: Literal["daily", "weekly", "monthly"] = "daily",
    markets: Sequence[str] | None = None,
    edition: str | None = None,
    snapshot: str | Snapshot | None = None,
    save: bool = False,
) -> PipelineResult:
    """3.5: the pipeline's columns at each market's decisions from `start` to `end`, the rows
    its screen keeps; `markets` are keys of the snapshot's markets, all of them by default.
    `save=True` seals a run of `kind="pipeline"` (3.8) and gives its id as `run_id`."""
    if edition is not None:  # a PIT dataset's edition: `Snapshot.intervals` (M2)
        raise NotImplementedError("edition= comes with the point-in-time datasets (M2)")
    cfg = config()
    if isinstance(snapshot, _Snapshot):
        opened = snapshot
    else:
        given = DataConfig.from_config(cfg) if snapshot is None else DataConfig(Path(snapshot))
        opened = open_snapshot(given)
    result = _pipeline.run(pipeline, start=start, end=end, freq=freq, markets=markets,
                           snapshot=opened, cfg=cfg, registry=schema_registry)  # fmt: skip
    if not save:
        return result
    params = {"start": str(start), "end": str(end), "freq": freq,
              "markets": list(markets) if markets is not None else None}  # fmt: skip
    run_id = _save_pipeline(result, pipeline, opened, cfg, params)
    return dataclasses.replace(result, run_id=run_id)


def _save_pipeline(
    result: PipelineResult, pipe: Pipeline, opened: Snapshot, cfg: Config, params: dict[str, Any]
) -> str:
    """3.8's `kind="pipeline"`: `pipeline.parquet` and `term_diagnostics.parquet` (5.9.1), and
    `source/` with the entry file, `__main__`'s file or none in an interactive session, and
    the project's modules imported so far (5.9.3; #283, #304). The run's name is the entry
    file's stem. The root pin goes beside the package the snapshot was opened from (4.2)."""
    from nexusbt.artifacts import RunStore  # only a saved run opens the store

    file = getattr(sys.modules.get("__main__"), "__file__", None)
    entry = Path(file) if file else None
    columns = {n: pipeline.graph_hash(t) for n, t in pipe.columns.items()}
    named = {"columns": columns, "screen": pipe.screen and pipeline.graph_hash(pipe.screen)}
    family = cfg.values["research"]["family_id"]
    store = RunStore(Path(cfg.values["runs"]["dir"]), family_id=family)
    graph = hashlib.sha256(json.dumps(named, sort_keys=True).encode()).hexdigest()
    data = DataConfig(_snapshot_folder(opened), pins=PinsPolicy(cfg.values["data"]["pins"]))
    txn = _begin_run(store, opened, data, "pipeline", entry.stem if entry else "interactive",
                     graph_hash=graph, params=params | {"terms": named})  # fmt: skip
    try:
        txn.write_table("pipeline", result.table)
        txn.write_table("term_diagnostics", result.term_diagnostics)
        files = (getattr(m, "__file__", None) for m in list(sys.modules.values()))
        imported = [Path(f) for f in files if isinstance(f, str) and _project_file(f)]
        txn.capture_sources(imported, entry=entry)
        used = params["markets"] or opened.markets
        markets = {m: {"calendar_id": i.calendar_id, "currency": i.currency,
                       "rules_pack": i.rules or "untested"}
                   for m, i in opened.markets.items() if m in used}  # fmt: skip
        txn.set_manifest({"kind": "pipeline", "snapshot_id": opened.id, "markets": markets,
                          "snapshot_semantic_hash": opened.semantic_hash,
                          "snapshot_value_hash": opened.value_hash,
                          "snapshot_physical_hash": opened.physical_hash})  # fmt: skip
    except BaseException:
        txn.abort()
        raise
    return txn.seal().run_id


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
    """A term (3.3): its node tree and structural hash; `nexusbt.factors`: the built-in factors'
    table (3.4, T1.10); other objects with their tickets."""
    if isinstance(obj, pipeline.Term):
        return Description(pipeline.describe_term(obj))
    if getattr(obj, "__name__", None) in ("nexusbt.factors", "nexusbt.pipeline.factors"):
        return Description(pipeline.factors.table())
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


def schema_registry(snapshot: Snapshot, cfg: Config) -> SchemaRegistry:
    """2.5: what `pipeline` binds column names against, from the opened snapshot and the two
    datasets `[panels]` names."""
    panels = cfg.values["panels"]
    return SchemaRegistry(*dataset_columns(snapshot), panels["feature"], panels["label"])


#: The stub file 3.2 names, which `stubs` writes and `stubs_current` reads.
_STUBS = Path(__file__).parents[1] / "_stubs" / "datasets.pyi"


def stubs(path: Path | None = None) -> Path:
    """`nexusbt stubs` (3.10): rewrite `_stubs/datasets.pyi` (or `path`) with the columns of
    the snapshot `[data]` names, or with the fixed columns alone when it names none."""
    cfg, snapshot = config(), None
    if cfg.values["data"]["path"] or cfg.values["data"]["root"]:
        snapshot = open_snapshot(DataConfig.from_config(cfg))
    path = path or _STUBS
    path.write_text(_stub(snapshot, cfg), encoding="utf-8")
    return path


def stubs_current(snapshot: Snapshot | None, cfg: Config) -> bool:
    """`doctor`'s stubs line (3.2, 3.10): whether `_stubs/datasets.pyi` on disk is what `stubs`
    would write for `snapshot`; with no snapshot, for the fixed columns alone. A missing file
    is stale: `stubs` writes it."""
    return _STUBS.is_file() and _STUBS.read_text(encoding="utf-8") == _stub(snapshot, cfg)


def _stub(snapshot: Snapshot | None, cfg: Config) -> str:
    return pipeline.stub_source(schema_registry(snapshot, cfg) if snapshot is not None else None)


def _begin_run(
    store: RunStore, snapshot: Snapshot, cfg: DataConfig, kind: str, name: str,
    study: str | None = None, **begin: Any,
) -> RunTxn:  # fmt: skip
    """4.4 step 6: a run starts with its pin. (snapshot_id, run_id) goes into the index `pins`
    in the run row's transaction (`RunStore.begin`, the `insert_pin` of `Index.pin`); with
    `[data] pins = "index+root"` also an empty `PINS/<snapshot_id>/<run_id>` under the data
    root, whose failure is E30. `retention` is `managed` only when that root pin was written:
    only then can the producer's clean-up see it (4.2, R3-17)."""
    txn = store.begin(kind, name, study, snapshot_id=snapshot.id,
                      snapshot_semantic_hash=snapshot.semantic_hash, **begin)  # fmt: skip
    retention = "unmanaged"
    if cfg.pins is PinsPolicy.INDEX_ROOT:
        root = _data_root(Path(cfg.path))
        try:
            if root is None:
                raise FileNotFoundError("no data root: no LATEST beside the package")
            if snapshot.id in {"", ".", ".."} or Path(snapshot.id).name != snapshot.id:
                raise ValueError(f"snapshot id {snapshot.id!r} is not one folder name")
            pin = root / "PINS" / snapshot.id / txn.run_id
            pin.parent.mkdir(parents=True, exist_ok=True)
            pin.touch()
            retention = "managed"
        except (OSError, ValueError) as failed:
            reason = getattr(failed, "strerror", None) or str(failed)  # no local path (2.7)
            warnings.warn(str(_unmanaged(snapshot.id, txn.run_id, reason)), stacklevel=2)
    txn.set_manifest({"retention": retention})
    return txn


def _unmanaged(snapshot_id: str, run_id: str, reason: str) -> DataProfileWarning:
    return DataProfileWarning(
        what=f"root pin not written ({reason}); retention: unmanaged",
        where=f"PINS/{snapshot_id}/{run_id} under the data root",
        why="the producer's clean-up sees only the root PINS/, not the index (4.2, R3-17)",
        fix="make the data root writable, or set [data] pins = 'index'",
        more="spec 4.2 and 4.4 step 6; the index pin was written",
        layer=f"data — snapshot {snapshot_id} / PINS / column - / producer -", subject="pins",
    )  # fmt: skip


def open(path: str | Path) -> Snapshot:  # noqa: A001 - the 3.1 name `nx.open`
    """One package folder, or a parent folder whose `LATEST` names one (4.2, V31-PUB-03)."""
    return open_snapshot(DataConfig(Path(path)))
