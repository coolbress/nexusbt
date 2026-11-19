"""`nx.run_pipeline` and its `PipelineResult` (spec 3.5), T1.13 (#249).

`api` is the one layer that joins the chains (2.5): it binds the graph against the snapshot
(so E17 and E7 come before anything is read), gives each market its own decision grid
(`market_local`, 3.5), sizes the chunks (5.3.8), hands the executor the market's blocks, ready
times and corporate actions (5.3.1, 5.3.3), and keeps the rows `Pipeline(screen=)` keeps.
"""

from __future__ import annotations

import datetime as dt
import functools
import importlib
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import pyarrow as pa

from nexusbt.contracts import ID_COLUMN, ConfigError, SchemaRegistry
from nexusbt.data import DataConfig, Schedule, Snapshot, open_snapshot
from nexusbt.pipeline import Classifier, Filter, Pipeline, bind, graph_hash

if TYPE_CHECKING:
    from nexusbt.config import Config
    from nexusbt.pipeline import Term

Freq = Literal["daily", "weekly", "monthly"]
_KEYS = ("session_date", "market", ID_COLUMN)  # 3.5's sort order
_UTC = pa.timestamp("us", tz="UTC")


@dataclass(frozen=True, slots=True, eq=False)
class PipelineResult:
    """3.5: `table` is `(market, session_date, decision_ts, instrument_id, <columns…>)`, sorted
    by `(session_date, market, instrument_id)`, the rows `screen` keeps."""

    table: pa.Table

    def to_polars(self) -> Any:
        return importlib.import_module("polars").from_arrow(self.table)  # optional (3.5)

    def to_pandas(self) -> Any:
        return self.table.to_pandas()

    def __arrow_c_stream__(self, requested_schema: object | None = None) -> object:
        """Zero-copy export (6.4, R5-02)."""
        return self.table.__arrow_c_stream__(requested_schema)


def run(
    pipeline: Pipeline,
    *,
    start: str | dt.date,
    end: str | dt.date,
    freq: Freq,
    markets: Sequence[str] | None,
    snapshot: str | Snapshot | None,
    cfg: Config,
    registry: Callable[[Snapshot, Config], SchemaRegistry],
) -> PipelineResult:
    """3.5's `nx.run_pipeline`, given the resolved `nexusbt.toml` and how `api` builds the
    schema registry it binds against (2.5)."""
    if not pipeline.columns:  # 3.5: the rows are `<columns…>` at the decisions
        raise ValueError("a pipeline for run_pipeline names one column or more")
    opened = _open(snapshot, cfg)
    bind(pipeline, registry(opened, cfg))  # E17, E7 before any value is read (2.5)
    terms = [*pipeline.columns.values(), *([pipeline.screen] if pipeline.screen else [])]
    nodes = _nodes(terms)
    _refuse_across_markets(nodes)
    fields = _price_fields(nodes)
    every = sorted(opened.markets, key=str.encode)
    names = dict.fromkeys(markets if markets is not None else every)  # each market once
    periods: dict[str, tuple[int, int]] = {}
    unrun: list[ConfigError] = []
    for m in names:  # 3.5: each market's own sessions (E9 for a date that is not one, 5.1.6)
        try:
            periods[m] = opened.calendar(m).align(start, end)
        except ConfigError as none:  # no session of m in the period: m has no rows
            unrun.append(none)
    if not periods:  # no market has a session: the period is wrong
        raise unrun[0]
    tables = [_market(pipeline, terms, fields, opened, m, p, freq, cfg) for m, p in periods.items()]
    found = [t for t in tables if t is not None]
    table = pa.concat_tables(found) if found else _empty(pipeline)
    return PipelineResult(table.sort_by([(k, "ascending") for k in _KEYS]))


def _open(snapshot: str | Snapshot | None, cfg: Config) -> Snapshot:
    if isinstance(snapshot, Snapshot):
        return snapshot
    if snapshot is not None:  # a path, read as `nx.open` reads it (4.2)
        return open_snapshot(DataConfig(path=Path(snapshot)))
    return open_snapshot(DataConfig.from_config(cfg))


def _refuse_across_markets(nodes: Sequence[Term]) -> None:
    """A term with `across_markets=True` gathers several markets' rows at a decision (5.3.1
    step 6), which this ticket leaves to T4.3 (#249 Decisions, 2026-11-19)."""
    if any(dict(t.params).get("across_markets") for t in nodes):
        raise NotImplementedError(
            "run_pipeline does not support across_markets=True yet: gathering the markets' "
            "rows at a decision comes with T4.3 (spec 5.3.1 step 6)"
        )


def _price_fields(nodes: Sequence[Term]) -> list[str]:
    """The daily-bar columns the graph reads; another dataset's block comes with its ticket."""
    read = [dict(t.params) for t in nodes if t.op == "column"]
    if other := sorted({f"{c['dataset']}.{c['column']}" for c in read if c["dataset"] != "Price"}):
        raise NotImplementedError(f"run_pipeline reads Price columns only so far, not {other}")
    return sorted({c["column"] for c in read})


def _nodes(terms: Sequence[Term]) -> list[Term]:
    """Every node of the graph once, the columns included."""
    from nexusbt.compute._plan import children  # imported here: see `_market`

    found: dict[str, Term] = {}
    todo = list(terms)
    while todo:
        term = todo.pop()
        if found.setdefault(graph_hash(term), term) is term:
            todo += children(term)
    return list(found.values())


def _market(
    pipeline: Pipeline, terms: list[Term], fields: list[str], snapshot: Snapshot, market: str,
    period: tuple[int, int], freq: Freq, cfg: Config,
) -> pa.Table | None:  # fmt: skip
    """One market's rows on its own calendar (3.5 `market_local`), or None with no decision.
    `compute` is imported here, not by `import nexusbt`: its kernels compile with a cache that
    an installed wheel's zip import cannot place (`tests/test_built_wheel.py`)."""
    from nexusbt.compute._chunks import lookback, most_alive, spans
    from nexusbt.compute._executor import Actions, execute
    from nexusbt.compute._screen import screened

    calendar = snapshot.calendar(market)
    first, last = period
    rows = Schedule(freq).rows(calendar)
    rows = rows[(rows >= first) & (rows <= last)]
    if not rows.size:
        return None
    dates = calendar.dates
    width = len(snapshot.block_columns(market, dates[: last + 1]))  # the most, for every chunk
    budget = float(cfg.values["compute"]["memory_budget_gb"])
    chunks = spans(dates[first : last + 1], width, most_alive(terms), budget, lookback(terms))
    actions = Actions(functools.partial(snapshot.actions, market), calendar.ts_open)
    frames = execute(
        terms, rows.tolist(), [(a + first, b + first) for a, b in chunks],
        lambda a, b: snapshot.market_block(market, fields, dates[a : b + 1]),
        calendar.ready, tiebreak=cfg.values["portfolio"]["tiebreak"], actions=actions,
    )  # fmt: skip
    kept = screened(pipeline, frames)
    cells = next(iter(kept.values()))
    at = cells["row"].to_numpy()
    head = {
        "market": pa.array([market] * len(at), pa.string()),
        "session_date": pa.array(dates[at].astype("datetime64[D]"), pa.date32()),
        "decision_ts": pa.array(calendar.ready[at].astype("datetime64[us]"), _UTC),
        ID_COLUMN: cells[ID_COLUMN],
    }
    return pa.table(head | {name: t["value"] for name, t in kept.items()})


def _empty(pipeline: Pipeline) -> pa.Table:
    """No decision in any market: the columns, no row; a column's type by its term's kind."""

    def kind(term: Term) -> pa.DataType:
        if isinstance(term, Filter):
            return pa.bool_()
        return pa.int32() if isinstance(term, Classifier) else pa.float64()

    fixed = [("market", pa.string()), ("session_date", pa.date32()), ("decision_ts", _UTC),
             (ID_COLUMN, pa.string())]  # fmt: skip
    return pa.schema(fixed + [(n, kind(t)) for n, t in pipeline.columns.items()]).empty_table()
