"""Spec 4.3 to 4.5: the data a graph's features need, what a package gives, the fallbacks."""

from __future__ import annotations

import datetime as dt
import functools
import warnings
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from nexusbt.config.packs import load_pack
from nexusbt.contracts import (
    ID_COLUMN,
    CapabilityError,
    DataProfileWarning,
    FallbacksPolicy,
    SnapshotError,
)
from nexusbt.data._block import OHL, partition_values
from nexusbt.data._block import gone as _gone
from nexusbt.data._coverage import BarsExtent, schedule
from nexusbt.data._datasets import chosen, dataset, doubled
from nexusbt.data._datasets import layer as _layer
from nexusbt_tds.check import Finding
from nexusbt_tds.manifest import Manifest
from nexusbt_tds.profiles import PROFILES, meets, profile_id
from nexusbt_tds.profiles import TRADED as EQUITIES  # the asset classes

#: 4.3's first table, the rows T1.1b decides: a feature → the dataset kinds it needs. F-13
#: (delistings) comes with the features that read it (T3.11).
NEEDS = {
    "price": ("instruments", "bars"),
    "adjusted": ("instruments", "bars", "corporate_actions", "calendar_sessions"),
    "backtest": ("instruments", "bars", "corporate_actions", "calendar_sessions"),
    "grid": ("instruments",),  # limit, stop, exit and price limits: F-15
}
#: The kinds a feature reads without needing them: two of one turn it off all the same (4.3,
#: #551), where none takes the feature's fallback.
READS = {f: needs + {"grid": ("market_rules", "classifications")}.get(f, ())
         for f, needs in NEEDS.items()}  # fmt: skip
#: 4.3's profile table: the profiles the v1 engine reads.
SUPPORTED = frozenset({
    "tds:minimal-daily@1.0", "tds:equity-daily-core@1.0", "tds:equity-daily-research@1.0",
    "tds:panels@1.0", "tds:pit-fundamentals@1.0",
})  # fmt: skip
SAYS = {
    "F-02": "sessions synthesized from exchange_calendars 4.13.2",
    "F-03": "bars expanded to listing period x sessions, empty cells obs_status = missing",
    "F-15": "price grid = currency minor unit",
    "F-16": "volume unit unverified (TDS-V011), no repair",
}
#: The bars columns whose lack is E14 at open or E18 when read, never a fallback (4.4-3; F-01
#: and F-18 retired, #705).
_UNREAD = (*OHL, "volume", "value_traded")


@dataclass(frozen=True, slots=True)
class CapabilityRequest:
    """The features a graph uses (4.3); `datasets` are the dataset kinds they need."""

    features: frozenset[str] = frozenset({"price"})

    def __post_init__(self) -> None:
        if unknown := sorted(set(self.features) - NEEDS.keys()):
            raise ValueError(f"no feature {unknown}; spec 4.3 has {sorted(NEEDS)}")

    @property
    def datasets(self) -> frozenset[str]:
        return frozenset(kind for f in self.features for kind in NEEDS[f])


@dataclass(frozen=True, slots=True)
class DataCapabilities:
    """The features turned on and the declared profiles v1 reads. The cumulative factors come
    from the resolver over the events, whatever the bars hold (spec 5.3.3, #705)."""

    features: frozenset[str]
    supported: frozenset[str]
    #: Bars columns with no value that no declared profile requires: E18 when read (#705).
    unread: frozenset[str] = frozenset()
    #: The same, of one market whose `market=` files hold no value of them (#705).
    unread_in: Mapping[str, frozenset[str]] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class FallbackRecord:
    """One fallback used (4.4-5): its 4.5 id, the dataset it stands in for, market, count, and
    a column, null since no fallback is one column's (F-18 retired, #705; the field stays)."""

    id: str
    dataset: str
    market: str
    count: int
    column: str | None = None


def decide(
    folder: Path, manifest: Manifest, rules: Mapping[str, str | None],
    found: Sequence[Finding], required: CapabilityRequest | None, policy: FallbacksPolicy,
    extent: BarsExtent,
) -> tuple[DataCapabilities, list[FallbackRecord], tuple[str, ...]]:  # fmt: skip
    """4.4-3: the features on, the fallbacks they take, and the assumptions those add.

    A requested feature the package cannot give is E18; with no request every feature the
    package can give is on. A fallback is E30 under `warn` and E14 under `fail`. `extent`
    reads the bars only for what asks it (#568)."""
    data = manifest.data
    kinds = chosen(data)  # a kind with none or two or more left is missing (4.3, #547)
    bars = kinds.get("bars")
    lacking = {f: [k for k in needs if k not in kinds] for f, needs in NEEDS.items()}
    taken: dict[str, list[FallbackRecord]] = {f: [] for f in NEEDS}
    market_of = _market_of(folder, kinds.get("instruments"))  # TDS K1: ids are opaque
    _no_close(folder, data, bars, market_of)  # 4.4-3, before step 4's market checks (#698)
    unread, unread_in = _breaks_profile(folder, data, bars, kinds.get("instruments"))  # #705
    if not extent.partitioned:  # a `market=` partition is the checker's (TDS-M010)
        _declared(folder, data, extent.by_market(), market_of)
    f02 = _calendars(folder, data, kinds, extent, lacking, taken)
    _fallbacks(folder, kinds, rules, found, extent, market_of, taken)
    twice = doubled(data)  # two or more left: off, never by a fallback (4.3, #547, #551)
    for f, reads in READS.items():
        lacking[f] += [k for k in twice if k in reads and k not in lacking[f]]
    on = frozenset(f for f in NEEDS if not lacking[f])
    if required is not None:
        _refuse_features(data, required, lacking)
    wanted = NEEDS.keys() if required is None else required.features
    used = list(dict.fromkeys(r for f in sorted(wanted) if f in on for r in taken[f]))
    _use_fallbacks(folder, data, bars, f02, used, policy, market_of, extent)
    supported = frozenset(p for p in data.get("profiles", []) if p in SUPPORTED)
    assumptions = tuple(SAYS[i] for i in ("F-02",) if any(r.id == i for r in used))
    return DataCapabilities(on, supported, unread, unread_in), used, assumptions


Sessions = tuple[list[FallbackRecord], dict[str, set[dt.date]]]


def _calendars(
    folder: Path, data: Mapping[str, Any], kinds: Mapping[str, Mapping[str, Any]],
    extent: BarsExtent, lacking: dict[str, list[str]], taken: dict[str, list[FallbackRecord]],
) -> Sessions | None:  # fmt: skip
    """4.4-4: the sessions `adjusted` and `backtest` read, held or F-02 (`_sessions`), and the
    raw bars they need (4.3); None without bars, or when no calendar gives the sessions."""
    bars = kinds.get("bars")
    if bars is None:
        return None
    f02 = _sessions(folder, data["markets"], kinds, extent)
    for f in ("adjusted", "backtest"):
        if f02 is None and "calendar_sessions" not in lacking[f]:  # 4.4-4: one market's
            lacking[f].append("calendar_sessions")
        elif f02 is not None:
            lacking[f] = [k for k in lacking[f] if k != "calendar_sessions"]
            taken[f] += f02[0]
        if bars["params"].get("price_basis") != "raw":
            lacking[f].append("raw bars (price_basis = raw)")
    return f02


def _fallbacks(
    folder: Path, kinds: Mapping[str, Mapping[str, Any]], rules: Mapping[str, str | None],
    found: Sequence[Finding], extent: BarsExtent, market_of: Mapping[str, str],
    taken: dict[str, list[FallbackRecord]],
) -> None:  # fmt: skip
    """4.5: F-03, F-16 and F-15, each added to the features that take it; F-03 reads the
    columns of the bars' first file."""
    bars = kinds.get("bars")
    columns = _columns(folder, bars)
    if bars is not None and (bars["params"].get("density") == "sparse"
                             or "obs_status" not in columns):  # fmt: skip
        taken["backtest"] += [FallbackRecord("F-03", bars["name"], m, int(e.get("rows", 0)))
                              for m, e in extent.by_market().items()]  # fmt: skip
    read = bars["name"] if bars is not None else None  # the bars the engine reads (4.3, #547)
    years = Counter((f.dataset, market_of.get(str((f.key or {}).get(ID_COLUMN)), "-"))
                    for f in found if f.code == "TDS-V011" and f.dataset == read)  # fmt: skip
    taken["backtest"] += [FallbackRecord("F-16", str(d), m, n) for (d, m), n in years.items()]
    taken["grid"] += _no_grid(folder, kinds, rules, extent, market_of)


def _refuse_features(
    data: Mapping[str, Any], required: CapabilityRequest, lacking: Mapping[str, list[str]]
) -> None:
    """4.4-3: a requested feature the package cannot give is E18."""
    if refused := [f for f in sorted(required.features) if lacking[f]]:
        for kind in dict.fromkeys(k for f in refused for k in READS[f]):
            dataset(data, kind)  # two or more left: E18 naming each (4.3)
        raise _not_in_snapshot(data, {f: lacking[f] for f in refused})


def _use_fallbacks(
    folder: Path, data: Mapping[str, Any], bars: Mapping[str, Any] | None,
    f02: Sessions | None, used: Sequence[FallbackRecord], policy: FallbacksPolicy,
    market_of: Mapping[str, str], extent: BarsExtent,
) -> None:  # fmt: skip
    """4.4-3: the fallbacks used, after F-02's check of the bars against its sessions (4.5):
    E14 under `fail`, one E30 for each id under `warn`."""
    if bars is not None and f02 is not None and any(r.id == "F-02" for r in used):
        _off_calendar(folder, data, bars, f02[1], market_of, extent)
    if used and policy is FallbacksPolicy.FAIL:
        raise _refused(data, used)
    for id_ in dict.fromkeys(r.id for r in used):  # stacklevel: decide's caller's caller
        warnings.warn(str(_warning(data, [r for r in used if r.id == id_])), stacklevel=4)


def _sessions(
    folder: Path, markets: Mapping[str, Mapping[str, Any]],
    kinds: Mapping[str, Mapping[str, Any]], extent: BarsExtent,
) -> Sessions | None:  # fmt: skip
    """F-02 for each market of the bars whose `calendar_id` `calendar_sessions` lacks (4.4-4):
    its sessions from the first to the last day of its bars, as records and as dates; None
    when exchange_calendars does not know such a calendar (then E18 for what needs them).
    The bars are read only when a declared market's calendar is not held."""
    held = {str(c) for c in _values(folder, kinds.get("calendar_sessions"), "calendar_id")}
    if all(e["calendar_id"] in held for e in markets.values()):
        return [], {}
    gap = {m: e for m, e in extent.by_market().items() if markets[m]["calendar_id"] not in held}
    if not gap:
        return [], {}
    import exchange_calendars as xcals  # only a package without sessions pays its import

    if any(markets[m]["calendar_id"] not in xcals.get_calendar_names() for m in gap):
        return None
    out, dates = [], {}
    for m, e in gap.items():
        # bounded by the bars, not by the library's default of 20 years before today
        days = schedule(markets[m]["calendar_id"], e).index
        out.append(FallbackRecord("F-02", "calendar_sessions", m, len(days)))
        dates[m] = {d.date() for d in days}
    return out, dates


def _off_calendar(
    folder: Path, data: Mapping[str, Any], bars: Mapping[str, Any],
    dates: Mapping[str, set[dt.date]], market_of: Mapping[str, str], extent: BarsExtent,
) -> None:  # fmt: skip
    """4.5 F-02: a bar of a synthesized market on a day that is not one of its sessions is E14
    `TDS-R003`, the check the checker leaves blind without `calendar_sessions`; over the rows
    `extent` read, one table per bars file with the ids as strings (TDS 3.2)."""
    off: list[dict[str, Any]] = []
    for t in extent.tables():  # filtered in Arrow: only the off rows reach Python
        for m, days in dates.items():
            ids = pa.array([i for i, x in market_of.items() if x == m], pa.string())
            held = pa.array(sorted(days), pa.date32()).cast(t["session_date"].type)
            outside = pc.invert(pc.is_in(t["session_date"], held))
            off += t.filter(pc.and_(pc.is_in(t[ID_COLUMN], ids), outside)).to_pylist()
    if off:
        producer = data.get("producer")
        raise SnapshotError.from_check(
            path=str(folder), counts={"TDS-R003": len(off)}, dataset=bars["name"], file="-",
            key=str({ID_COLUMN: off[0][ID_COLUMN], "session_date": str(off[0]["session_date"])}),
            hint=f"{len(off)} row(s) on a day not a session of the synthesized calendar (F-02)",
            snapshot_id=str(data["snapshot_id"]),
            producer=str(producer.get("name", "-")) if isinstance(producer, dict) else "-",
        )  # fmt: skip


def _columns(folder: Path, dataset: Mapping[str, Any] | None) -> set[str]:
    """The columns of a dataset's first file, read from its footer."""
    if dataset is None or not dataset["files"]:
        return set()
    return set(pq.read_schema(folder / dataset["files"][0]["path"]).names)


def _values(folder: Path, dataset: Mapping[str, Any] | None, *columns: str) -> list[Any]:
    """The rows of `columns` in every file of a dataset, as tuples (one column: its values)."""
    out: list[Any] = []
    for f in dataset["files"] if dataset is not None else ():
        table = pq.read_table(folder / f["path"], columns=list(columns))
        rows = zip(*(table[c].to_pylist() for c in columns), strict=True)
        out += [r[0] if len(columns) == 1 else r for r in rows]
    return out


def _declared(
    folder: Path, data: Mapping[str, Any], by_market: Mapping[str, Any],
    market_of: Mapping[str, str],
) -> None:  # fmt: skip
    """Spec 4.4-4 (#567): a market of the bars that `markets` does not declare is E14
    `TDS-M010`. Only a market taken from `instruments` (bars without `market=`) reaches here
    at `verify = "manifest"`: the checker reads that column from `schema` on (TDS 8.2)."""
    undeclared = sorted(m for m in by_market if m not in data["markets"])
    if not undeclared:
        return
    market = undeclared[0]
    ids = sorted(i for i, m in market_of.items() if m == market)
    first = ids[0] if ids else "-"
    producer = data.get("producer")
    raise SnapshotError.from_check(
        path=str(folder), counts={"TDS-M010": len(undeclared)}, dataset="instruments",
        file="-", key=str({ID_COLUMN: first, "market": market}), column="market",
        hint=f"instrument {first!r} names market {market!r}, not declared in tds.json "
             f"`markets` (TDS 3.8); declare the market or correct `instruments.market`",
        snapshot_id=str(data["snapshot_id"]),
        producer=str(producer.get("name", "-")) if isinstance(producer, dict) else "-",
    )  # fmt: skip


def _market_of(folder: Path, instruments: Mapping[str, Any] | None) -> dict[str, str]:
    """instrument_id → its `market` from the declared `instruments` files (TDS K1)."""
    return dict(_values(folder, instruments, ID_COLUMN, "market"))


def _no_grid(
    folder: Path, kinds: Mapping[str, Mapping[str, Any]], rules: Mapping[str, str | None],
    extent: BarsExtent, market_of: Mapping[str, str],
) -> list[FallbackRecord]:  # fmt: skip
    """F-15: a market with a pack where no instrument has a usable source of 4.3's grid chain
    (#453): a non-null `instruments.tick_size`; a `tick_rule_id`, of a `classifications` row
    of that scheme or of `instruments`, that is the `rule_id` of a `market_rules` `tick_band`
    rule set (5.6.4a); `tick_band` rows of the market; a `tick_table` or `base_unit` in its
    pack. Dates are not read: whether a row applies on a day is the grid lookup's (T3.24)."""
    # a market without a pack is not here: nothing runs there (4.4-4)
    packed = {m: load_pack(p.split("@")[0])["grid"] for m, p in rules.items() if p is not None}
    bare = [m for m, grid in packed.items() if not {"tick_table", "base_unit"} & grid.keys()]
    if not bare:
        return []
    rows = _values(folder, kinds.get("market_rules"), "rule_id", "market", "rule_kind")
    bands = [(r, m) for r, m, kind in rows if kind == "tick_band"]
    named = {r for r, _ in bands}
    sourced: set[str | None] = {m for _, m in bands}
    instruments = kinds.get("instruments")
    held = [c for c in ("tick_size", "tick_rule_id") if c in _columns(folder, instruments)]
    for i, *ticks in _values(folder, instruments, ID_COLUMN, *held) if held else ():
        tick = dict(zip(held, ticks, strict=True))
        if tick.get("tick_size") is not None or tick.get("tick_rule_id") in named:
            sourced.add(market_of.get(i))
    for f in kinds.get("classifications", {}).get("files", []) if named else ():  # only then
        table = pq.read_table(folder / f["path"], columns=[ID_COLUMN, "code"],
                              filters=[("scheme", "=", "tick_rule_id")])  # fmt: skip
        ids, codes = table[ID_COLUMN].to_pylist(), table["code"].to_pylist()
        sourced |= {market_of.get(i) for i, c in zip(ids, codes, strict=True) if c in named}
    unsourced = [m for m in bare if m not in sourced]
    by_market = extent.by_market() if unsourced else {}  # read for the records' counts only
    return [FallbackRecord("F-15", "market_rules", m, int(by_market.get(m, {}).get(
        "instruments", 0))) for m in unsourced]  # fmt: skip


def said(records: Sequence[FallbackRecord]) -> list[str]:
    """One sentence per fallback id, as its E30 says it: the manifest's `assumptions` (1.2)."""
    ids = dict.fromkeys(r.id for r in records)
    return [f"fallback {i} used: {SAYS[i]} for "
            f"{', '.join(dict.fromkeys(r.market for r in records if r.id == i))}"
            for i in ids]  # fmt: skip


def _warning(data: Mapping[str, Any], records: Sequence[FallbackRecord]) -> DataProfileWarning:
    first = records[0]
    return DataProfileWarning(
        what=said(records)[0],
        where="; ".join(f"dataset {r.dataset}, market {r.market}, "
                        f"{f'column {r.column}, ' if r.column else ''}{r.count}" for r in records),
        why="a fallback changes what a term means (4.5)",
        fix="[data] fallbacks = 'fail' to stop instead", more="spec 4.5; tds check --level full",
        layer=_layer(data, first.dataset), subject=first.id,
    )  # fmt: skip


def _no_close(
    folder: Path, data: Mapping[str, Any], bars: Mapping[str, Any] | None,
    market_of: Mapping[str, str],
) -> None:  # fmt: skip
    """4.3 and 4.4-3 (#698): a bars file without a `close` column is E14 at open, whatever the
    run reads: no fallback stands in for it (4.5), and since TDS C1 (#705) every equity daily
    profile requires it. A close null in every row is `_breaks_profile`'s (#705 Decisions 50)."""
    if bars is None:
        return
    for f in bars["files"]:
        if "close" in pq.read_schema(folder / f["path"]).names:
            continue
        market = partition_values(f["path"], bars.get("partitioning", [])).get("market")
        if market is None:  # no `market=`: its instruments' markets (TDS K1)
            try:
                ids = pq.read_table(folder / f["path"], columns=[ID_COLUMN])[ID_COLUMN]
            except (pa.ArrowException, KeyError):  # no id column, or two: the checker's
                ids = pa.array([])
            market = ", ".join(sorted({market_of.get(str(i), "-") for i in ids.to_pylist()}))
            market = market or "-"
        raise SnapshotError(
            what=f"the bars of market {market} have no close column",
            where=f"dataset {bars['name']}, file {f['path']}, column close",
            why="Price.* reads close, and no fallback stands in for it (4.3, 4.5)",
            fix=f"write close in {f['path']} and every other bars file (TDS 5.5 and 7)",
            more=f"tds check {folder} --level full; spec 4.3 and 4.4 step 3",
            layer=_layer(data, str(bars["name"])),
        )  # fmt: skip


def _breaks_profile(
    folder: Path, data: Mapping[str, Any], bars: Mapping[str, Any] | None,
    instruments: Mapping[str, Any] | None,
) -> tuple[frozenset[str], dict[str, frozenset[str]]]:  # fmt: skip
    """4.4-3 (#705 Decisions 48, 50): E14 at open when a bars file lacks a column another holds,
    or the bars hold no value of `close` or of a column a declared profile requires of them
    (TDS 7), as TDS-M008 reads it: in no file, or null in every row of the dataset. `open`,
    `high`, `low` and `volume` are required where the bars name an equity or etf. Else the
    columns of `_UNREAD` with no value, in the dataset and by market, which a term reading them
    meets as E18 (48 (c))."""
    if bars is None:
        return frozenset(), {}
    params: Mapping[str, Any] = g if isinstance(g := bars.get("params"), dict) else {}
    need: dict[str, str] = {"close": "every engine feature (4.3)"}
    traded: dict[str, str] = {}
    declared = (profile_id(x) for x in data.get("profiles", []) if isinstance(x, str))
    for p in (PROFILES[x] for x in declared if x in PROFILES):
        for named, into in ((p.columns, need), (p.traded, traded)):
            for (kind, conditions), columns in named:
                if kind == "bars" and all(meets(params, *c) for c in conditions):
                    into.update({c: p.name for c in columns if c not in into})
    files = [(folder / f["path"], pq.ParquetFile(folder / f["path"]).metadata)
             for f in bars["files"]]  # fmt: skip
    _same_columns(data, bars, files)
    lacks = functools.cache(functools.partial(_no_value, files))
    try:
        lacking = [(c, why) for c, why in need.items() if lacks(c)]
        if not lacking and (gaps := [(c, why) for c, why in traded.items() if lacks(c)]):
            lacking = gaps if _names_traded(folder, instruments, files) else []
    except (pa.ArrowException, KeyError):  # a column twice or of another type: the checker's
        return frozenset(), {}  # S codes say it (TDS-S002, TDS-S011), as its own M008 leaves
    for column, why in lacking[:1]:
        raise SnapshotError(
            what=f"the bars hold no value of {column}, which {why} requires",
            where=f"dataset {bars['name']}, column {column}: in no file, or null in every row",
            why="no fallback repairs a package that breaks what it declares (4.4 step 3)",
            fix=f"write {column} in the bars"
            + ("" if column == "close" else ", or declare tds:minimal-daily@1.0, which asks "
               "close alone (TDS 7)"),
            more=f"tds check {folder} --level schema; spec 4.4 step 3",
            layer=_layer(data, str(bars["name"])),
        )  # fmt: skip
    try:  # after the E14, so a column the check cannot read never hides it
        unread = frozenset(c for c in _UNREAD if lacks(c))
        return unread, _unread_by_market(bars, files, unread)
    except (pa.ArrowException, KeyError):
        return frozenset(), {}


Footers = Sequence[tuple[Path, pq.FileMetaData]]


def _no_value(files: Footers, column: str) -> bool:
    """TDS-M008's reading over `files`: `column` in none, or null in every row of files that
    have rows; a file without footer statistics has that one column read (#705 Decisions 50)."""
    for path, meta in files:
        if column not in meta.schema.names or _gone(meta, column):
            continue
        at = meta.schema.names.index(column)
        stats = [meta.row_group(g).column(at).statistics for g in range(meta.num_row_groups)]
        if all(s is not None and s.has_null_count for s in stats):
            return False  # the footer counts fewer nulls than rows: a value
        if pq.read_table(path, columns=[column])[column].null_count < meta.num_rows:
            return False
    return any(meta.num_rows for _, meta in files)


def _names_traded(folder: Path, instruments: Mapping[str, Any] | None, files: Footers) -> bool:
    """Whether the bars' `instrument_id` names an `equity` or `etf` of `instruments` (TDS 7)."""
    classes = _values(folder, instruments, ID_COLUMN, "asset_class")
    want = pa.array(sorted({i for i, a in classes if a in EQUITIES and isinstance(i, str)}),
                    pa.string())  # fmt: skip
    for path, meta in files if len(want) else ():
        if ID_COLUMN in meta.schema.names:
            ids = pq.read_table(path, columns=[ID_COLUMN])[ID_COLUMN].cast(pa.string())
            if pc.any(pc.is_in(ids, value_set=want)).as_py():
                return True
    return False


def _same_columns(data: Mapping[str, Any], bars: Mapping[str, Any], files: Footers) -> None:
    """E14 at open for a bars file without a column another file of the dataset holds: every
    file of one dataset has the same columns (TDS 3.6, TDS-S011), whatever the profile (#705,
    2026-11-22). A file without `close` is `_no_close`'s, before this."""
    names = [set(meta.schema.to_arrow_schema().names) for _, meta in files]  # S011's, not leaves
    held = set().union(*names)
    for f, own in zip(bars["files"], names, strict=True):
        if lacked := sorted(held - own):
            rel = f["path"]
            raise SnapshotError(
                what=f"a bars file has no column {', '.join(lacked)}, which other files hold",
                where=f"dataset {bars['name']}, file {rel}",
                why="every file of one dataset has the same columns (TDS 3.6, TDS-S011); no "
                    "fallback stands in for the missing ones (4.4 step 3)",
                fix=f"write {', '.join(lacked)} in {rel}, or leave it out of every file",
                more="tds check <package> --level schema; spec 4.4 step 3",
                layer=_layer(data, str(bars["name"])),
            )  # fmt: skip


def _unread_by_market(
    bars: Mapping[str, Any], files: Footers, unread: frozenset[str]
) -> dict[str, frozenset[str]]:
    """The columns of `_UNREAD` that every `market=` file of a market holds no value of, while the
    dataset holds one: E18 when a run over that market reads them (#705, 2026-11-22). Some
    files of a market (a year) without a value are data, as a halted session's null is; bars
    not partitioned by market are judged as a whole (`unread`)."""
    by: dict[str, list[tuple[Path, pq.FileMetaData]]] = {}
    for f, footer in zip(bars["files"], files, strict=True):
        market = partition_values(f["path"], bars.get("partitioning", [])).get("market")
        if market is None:
            return {}
        by.setdefault(market, []).append(footer)
    gaps = {m: frozenset(c for c in _UNREAD if c not in unread and _no_value(held, c))
            for m, held in by.items()}  # fmt: skip
    return {m: cols for m, cols in gaps.items() if cols}


def _refused(data: Mapping[str, Any], used: Sequence[FallbackRecord]) -> SnapshotError:
    ids = ", ".join(dict.fromkeys(r.id for r in used))
    return SnapshotError(
        what=f"fallback {ids} needed and [data] fallbacks = 'fail'",
        where=", ".join(f"{r.dataset} ({r.market})" for r in used),
        why="a fallback changes what a term means (4.5)",
        fix="use a snapshot with those datasets, or [data] fallbacks = 'warn' (recorded)",
        more="spec 4.4 step 3 and 4.5", layer=_layer(data, used[0].dataset),
    )  # fmt: skip


def check_fields(
    data: Mapping[str, Any], caps: DataCapabilities, fields: Sequence[str],
    market: str | None = None,
) -> None:  # fmt: skip
    """4.3: `close_tr` needs the `adjusted` feature (raw bars, corporate actions, sessions); an
    adjusted-price package gives `close` as it is and refuses `close_tr` with E18. A column the
    bars hold no value of, in the dataset or in `market`'s files, is E18 too (4.4-3, #705)."""
    bars = chosen(data).get("bars") or {}
    here = caps.unread_in.get(market, frozenset()) if market is not None else frozenset()
    read = {f: f.removesuffix("_unadjusted") for f in fields}  # `volume_unadjusted` is volume's
    for asked, column in ((f, c) for f, c in read.items() if c in caps.unread | here):
        of = f" of market {market}" if column in here else ""
        raise CapabilityError(
            what=f"Price.{asked} is not in snapshot {data['snapshot_id']}: the bars{of} hold "
                 f"no value of {column}",
            where=f"dataset {bars.get('name', 'bars')}, column {column}: in no file, or null "
                  f"in every row{of}",
            why="no fallback stands in for it, and no profile the package declares requires "
                "it (4.4 step 3; TDS 7)",
            fix=f"use a package whose bars hold {column}"
            + ("" if column == "value_traded" else " (tds:equity-daily-core@1.0 requires it of "
               "equities and etfs)") + ", or a graph that does not read it",
            more="spec 4.4 step 3; TDS 7", layer=_layer(data, str(bars.get("name", "bars"))),
        )  # fmt: skip
    if "close_tr" not in fields or "adjusted" in caps.features:
        return
    basis = bars.get("params", {}).get("price_basis", "-")
    raise CapabilityError(
        what=f"Price.close_tr is not in snapshot {data['snapshot_id']}: economic labels need "
             "raw prices and corporate actions",
        where=f"dataset {bars.get('name', 'bars')} price_basis = {basis}",
        why="close_tr is the raw close with cash dividends added back from corporate_actions "
            "(3.2); it needs raw bars, corporate_actions and calendar_sessions (4.3)",
        fix="use a snapshot whose bars have price_basis = raw, with corporate_actions and "
            "calendar_sessions; or read Price.close, the package's adjusted value",
        more="spec 3.2 and 4.3", layer=_layer(data, str(bars.get("name", "bars"))),
    )  # fmt: skip


def _not_in_snapshot(data: Mapping[str, Any], lacking: Mapping[str, list[str]]) -> CapabilityError:
    first = next(iter(lacking.values()))[0]
    return CapabilityError(
        what="; ".join(f"{f} needs {', '.join(k)}, not in snapshot" for f, k in lacking.items()),
        where=f"snapshot {data['snapshot_id']} datasets",
        why="a feature without its data or a fallback is refused, not substituted (4.3)",
        fix="use a snapshot whose profiles include those datasets",
        more="spec 4.3 and 4.5; tds check --level manifest", layer=_layer(data, first),
    )  # fmt: skip
