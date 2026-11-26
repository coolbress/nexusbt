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

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc

from nexusbt import pipeline
from nexusbt.api import _pipeline, _rerun
from nexusbt.api._pipeline import PipelineResult as PipelineResult
from nexusbt.api._screen import Screen as Screen
from nexusbt.config import Config, load_config
from nexusbt.contracts import (
    ID_COLUMN,
    ConfigError,
    DataProfileWarning,
    PinsPolicy,
    ReplayError,
    SchemaRegistry,
    SessionNotice,
    SnapshotError,
    UntrustedRunError,
)
from nexusbt.data import (
    DataConfig,
    _data_root,
    _snapshot_folder,
    _snapshot_markets,
    dataset_columns,
    open_snapshot,
    table_value_hash,
)
from nexusbt.data import Snapshot as _Snapshot
from nexusbt.pipeline._terms import _project_file

if TYPE_CHECKING:
    from nexusbt.artifacts import RunStore, RunTxn
    from nexusbt.data import Calendar, Explanation, Snapshot
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
class Run:
    """3.8. `rerun` fills `run_id`, `path`, `manifest` and `comparison` (#250); the rest come
    with T3.13a, None on a kind that computes no performance."""

    run_id: str | None = None
    path: Path | None = None
    manifest: Mapping[str, Any] | None = None
    comparison: str | None = None  # `rerun` only: its outputs against the reproduced run's
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
    """3.8 `screen(factor, top=n)`: the top n of one factor per market on `asof` (default each
    market's last snapshot session), among the listed instruments until T2.4's default universe
    (3.6); sealed as a `kind="screen"` run (3.8: an exposure record, whose rows are T2.9's)."""
    if not isinstance(obj, pipeline.Factor):
        what = type(obj).__name__
        raise NotImplementedError(f"screen of a {what} comes with its ticket; a Factor screens")
    other = {k: v for k, v in common.items() if k not in ("snapshot", "save")}  # 3.8's common
    if other.get("purpose") == "research":  # the default run kind (6.2); the others are later
        del other["purpose"]
    given = {"params": params, "anchor": anchor, "book": book,
             "show": None if show == "selected" else show,
             "account": None if account in ("auto", "none") else account, **other}  # fmt: skip
    if refused := sorted(k for k, v in given.items() if v is not None):
        raise NotImplementedError(f"screen(factor) does not take {refused} yet")
    if top is not None and top < 1:
        raise ConfigError(what=f"top = {top} selects nothing", where="argument top",
                          why="screen(factor, top=n) keeps the top n per market (3.8)",
                          fix="top=1 or more, or leave it out for every scored instrument",
                          more="spec 3.8", layer=f"config — argument top={top}")  # fmt: skip
    cfg, snapshot = config(), common.get("snapshot")
    if isinstance(snapshot, _Snapshot):
        opened = snapshot
    else:
        source = DataConfig.from_config(cfg) if snapshot is None else DataConfig(Path(snapshot))
        opened = open_snapshot(source)
    columns: dict[str, pipeline.Term] = {"score": obj, "rank": obj.rank(ascending=False)}
    if top is not None:
        columns["kept"] = obj.top(top)
    picked, days, universe, selected = [], {}, {}, {}
    for m in sorted(opened.markets, key=str.encode):
        days[m] = day = _screen_day(opened.calendar(m), asof)
        found = _pipeline.run(pipeline.Pipeline(columns), start=day, end=day, freq="daily",
                              markets=[m], snapshot=opened, cfg=cfg,
                              registry=schema_registry).table  # fmt: skip
        universe[m] = found.num_rows
        scored = pc.invert(pc.is_nan(found["rank"]))  # no score, no rank
        kept = found.filter(found["kept"] if top is not None else scored)
        selected[m] = kept.num_rows
        picked.append(kept.select(["market", "session_date", "rank", ID_COLUMN, "score"]))
    table = _ranked(pa.concat_tables(picked))
    named = {"factor": pipeline.graph_hash(obj), "top": top}
    params_ = {"asof": None if asof is None else str(asof), "top": top}
    if not common.get("save", True):
        return Screen(table, True, days, universe, selected, opened.id)
    run_id = _seal("screen", named, {}, opened, cfg, params_ | {"markets": None})
    return Screen(table, True, days, universe, selected, opened.id, run_id)


def _screen_day(calendar: Calendar, asof: _Day | None) -> dt.date:
    """`asof`, or the market's last session before it with an E9 notice (5.1.6); the last
    session of the snapshot when not given (3.8)."""
    dates = calendar.dates
    if asof is None:
        found: dt.date = dates[-1].astype("datetime64[D]").item()
        return found
    wanted = np.datetime64(str(asof), "D")
    row = int(np.searchsorted(dates, wanted, "right")) - 1
    if row < 0 or wanted > dates[-1]:  # before the data, or after its last session
        raise ConfigError(what=f"asof {asof} is outside the {calendar.market} sessions",
                          where="argument asof", why="a screen is on one session (3.8)",
                          fix=f"choose asof from {dates[0]} to {dates[-1]}", more="spec 5.1.6",
                          layer=f"config — argument asof={asof}")  # fmt: skip
    day: dt.date = dates[row].astype("datetime64[D]").item()
    if day != wanted.item():
        warnings.warn(str(SessionNotice(
            what=f"asof {asof} is not a {calendar.market} session; using {day}",
            where="argument asof", why="a screen is on a session", fix=f"asof='{day}'",
            more="spec 6.6 E9", subject="asof", layer=f"config — argument asof={asof}",
        )), stacklevel=3)  # fmt: skip
    return day


def _ranked(table: pa.Table) -> pa.Table:
    """By market and rank, the rank as an integer (an ordinal rank of a finite score)."""
    ranks = pc.cast(table["rank"], pa.int64())
    table = table.set_column(table.schema.get_field_index("rank"), "rank", ranks)
    return table.sort_by([("market", "ascending"), ("rank", "ascending")])


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
    if isinstance(snapshot, _Snapshot) and _rerun.ACTIVE is None:
        opened = snapshot
    else:  # in a rerun, at least `schema` and each file's sha256, as 3.8 says
        folder = _snapshot_folder(snapshot) if isinstance(snapshot, _Snapshot) else snapshot
        given = DataConfig.from_config(cfg) if folder is None else DataConfig(Path(folder))
        try:
            opened = open_snapshot(given, sha256=_rerun.ACTIVE is not None)
        except SnapshotError as unread:  # the package moved, or a file's bytes differ
            _rerun.not_opened(unread, Path(given.path))
            raise
        _rerun.check_snapshot(opened)
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
    """3.8's `kind="pipeline"`: `pipeline.parquet` and `term_diagnostics.parquet` (5.9.1)."""
    columns = {n: pipeline.graph_hash(t) for n, t in pipe.columns.items()}
    named = {"columns": columns, "screen": pipe.screen and pipeline.graph_hash(pipe.screen)}
    tables = {"pipeline": (result.table, _pipeline.KEYS),
              "term_diagnostics": (result.term_diagnostics, _pipeline.COUNT_KEYS)}  # fmt: skip
    return _seal("pipeline", named, tables, opened, cfg, params)


def _seal(
    kind: str, named: dict[str, Any], tables: Mapping[str, tuple[pa.Table, Sequence[str]]],
    opened: Snapshot, cfg: Config, params: dict[str, Any],
) -> str:  # fmt: skip
    """A run of `kind` (3.8) with `tables` (5.9.1), each with the key its value hash orders rows
    by (5.9.2 `outputs`, TDS 4.5), and `source/` with the entry file,
    `__main__`'s file or none in an interactive session, and the project's modules imported so
    far (5.9.3; #283, #304). The run's name is the entry file's stem. The root pin goes beside
    the package the snapshot was opened from (4.2)."""
    from nexusbt.artifacts import RunStore  # only a saved run opens the store
    from nexusbt.artifacts._runstore import run_h6

    file = getattr(sys.modules.get("__main__"), "__file__", None)
    entry = Path(file) if file else None
    family = cfg.values["research"]["family_id"]
    store = RunStore(Path(cfg.values["runs"]["dir"]), family_id=family)
    graph = hashlib.sha256(json.dumps(named, sort_keys=True).encode()).hexdigest()
    data = DataConfig(_snapshot_folder(opened), pins=PinsPolicy(cfg.values["data"]["pins"]))
    h6 = run_h6(graph, params | {"terms": named}, None, opened.semantic_hash)
    txn = _begin_run(store, opened, data, kind, entry.stem if entry else "interactive",
                     graph_hash=graph, params=params | {"terms": named},
                     **_rerun.index_columns(kind, h6))  # fmt: skip
    try:
        for name, (table, key) in tables.items():
            txn.write_table(name, table, value_sha256=table_value_hash(table, key))
        files = {n: getattr(m, "__file__", None) for n, m in list(sys.modules.items())}
        modules = {n: Path(f) for n, f in files.items() if isinstance(f, str) and _project_file(f)}
        # a rerun's project is its `source/`, so the new run keeps the same paths (5.9.3)
        project = _rerun.project()
        txn.capture_sources(modules.values(), project=project, entry=entry,
                            outside=_rerun.outside(modules, project))  # fmt: skip
        used = params["markets"] or opened.markets
        markets = {m: {"calendar_id": i.calendar_id, "currency": i.currency,
                       "rules_pack": i.rules or "untested"}
                   for m, i in opened.markets.items() if m in used}  # fmt: skip
        txn.set_manifest({"kind": kind, "snapshot_id": opened.id, "markets": markets,
                          "snapshot_semantic_hash": opened.semantic_hash,
                          "snapshot_value_hash": opened.value_hash,
                          "snapshot_physical_hash": opened.physical_hash,
                          **opened._recorded()})  # fmt: skip
    except BaseException:
        txn.abort()
        raise
    run_id = txn.seal().run_id
    _rerun.sealed(run_id)
    return run_id


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
    """3.8: the run's `source/` again in a new process (5.9.3), its outputs compared by value
    and bytes (5.9.4); a sealed run of another machine only with `trust=True` (2.6, E31)."""
    from nexusbt.artifacts._environment import same_machine

    folder = Path(config().values["runs"]["dir"]).resolve() / run_id
    if Path(run_id).name != run_id or not (folder / "SEALED").is_file():  # one folder of runs/
        raise ReplayError(
            what=f"run {run_id} is not a sealed run folder", where=f"run {run_id}",
            why="a rerun needs the run it reproduces", fix="nx.runs() lists the runs",
            more="spec 5.9.1", subject=f"run {run_id}", layer=f"data — run {run_id} / manifest",
        )  # fmt: skip
    if not trust and not same_machine(_rerun.read(folder)["environment"]["machine_id"]):
        raise UntrustedRunError(
            what=f"run {run_id} was created on another machine; its source/ will be executed",
            where=f"run folder {run_id}", why="running code you did not read is unsafe",
            fix="nx.rerun(id, trust=True) after reading source/", more="spec 2.6, 5.9.3",
            subject=f"run {run_id}", layer="config — argument trust=False",
        )  # fmt: skip
    new_id, line = _rerun.rerun(folder, new_snapshot=new_snapshot)
    path = folder.parent / new_id
    return Run(run_id=new_id, path=path, manifest=_rerun.read(path), comparison=line)


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
    """`nexusbt.toml` of the working folder, resolved against the snapshot `[data]` points at;
    in a rerun, the one its `source/` keeps (3.8: "parameters, config and lock")."""
    here = Path("nexusbt.toml") if Path("nexusbt.toml").is_file() else None
    path = _rerun.config_file() or here
    markets = _snapshot_markets(load_config(path))
    return load_config(path, markets=markets) if markets else load_config(path)


def schema_registry(snapshot: Snapshot, cfg: Config) -> SchemaRegistry:
    """2.5: what `pipeline` binds column names against, from the opened snapshot."""
    return SchemaRegistry(dataset_columns(snapshot))


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
