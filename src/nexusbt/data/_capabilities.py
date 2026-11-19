"""Spec 4.3 to 4.5: the data a graph's features need, what a package gives, the fallbacks."""

from __future__ import annotations

import datetime as dt
import warnings
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

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
from nexusbt.data._coverage import bars_by_market, schedule
from nexusbt.data._datasets import chosen, dataset, doubled
from nexusbt.data._datasets import layer as _layer
from nexusbt_tds.check import Finding
from nexusbt_tds.manifest import Manifest

#: 4.3's first table, the rows T1.1b decides: a feature → the dataset kinds it needs. F-01
#: (OHLC) and F-13 (delistings) come with the features that read them (T3.11 for F-13).
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
    """The features turned on, the declared profiles v1 reads, and where the cumulative
    factors come from: the bars' columns, or the resolver from the events (F-04)."""

    features: frozenset[str]
    supported: frozenset[str]
    cum_factors: Literal["columns", "resolver"]


@dataclass(frozen=True, slots=True)
class FallbackRecord:
    """One fallback used (4.4-5): its 4.5 id, the dataset it stands in for, market, count."""

    id: str
    dataset: str
    market: str
    count: int


def decide(
    folder: Path, manifest: Manifest, rules: Mapping[str, str | None],
    found: Sequence[Finding], required: CapabilityRequest | None, policy: FallbacksPolicy,
) -> tuple[DataCapabilities, list[FallbackRecord], tuple[str, ...]]:  # fmt: skip
    """4.4-3: the features on, the fallbacks they take, and the assumptions those add.

    A requested feature the package cannot give is E18; with no request every feature the
    package can give is on. A fallback is E30 under `warn` and E14 under `fail`."""
    data = manifest.data
    kinds = chosen(data)  # a kind with none or two or more left is missing (4.3, #547)
    bars = kinds.get("bars")
    by_market = bars_by_market(folder, bars, kinds.get("instruments"))  # declared, else read
    lacking = {f: [k for k in needs if k not in kinds] for f, needs in NEEDS.items()}
    taken: dict[str, list[FallbackRecord]] = {f: [] for f in NEEDS}
    market_of = _market_of(folder, kinds.get("instruments"))  # TDS K1: ids are opaque
    _declared(folder, data, by_market, market_of)
    f02: Sessions | None = None
    if bars is not None:
        f02 = _sessions(folder, data["markets"], kinds, by_market)
        for f in ("adjusted", "backtest"):
            if f02 is None and "calendar_sessions" not in lacking[f]:  # 4.4-4: one market's
                lacking[f].append("calendar_sessions")
            elif f02 is not None:
                lacking[f] = [k for k in lacking[f] if k != "calendar_sessions"]
                taken[f] += f02[0]
            if bars["params"].get("price_basis") != "raw":
                lacking[f].append("raw bars (price_basis = raw)")
    columns = _columns(folder, bars)
    if bars is not None and (bars["params"].get("density") == "sparse"
                             or "obs_status" not in columns):  # fmt: skip
        taken["backtest"] += [FallbackRecord("F-03", bars["name"], m, int(e.get("rows", 0)))
                              for m, e in by_market.items()]  # fmt: skip
    years = Counter((f.dataset, market_of.get(str((f.key or {}).get(ID_COLUMN)), "-"))
                    for f in found if f.code == "TDS-V011")  # fmt: skip
    taken["backtest"] += [FallbackRecord("F-16", str(d), m, n) for (d, m), n in years.items()]
    taken["grid"] += _no_grid(folder, kinds, rules, by_market, market_of)
    twice = doubled(data)  # two or more left: off, never by a fallback (4.3, #547, #551)
    for f, reads in READS.items():
        lacking[f] += [k for k in twice if k in reads and k not in lacking[f]]
    on = frozenset(f for f in NEEDS if not lacking[f])
    if required is not None and (refused := [f for f in sorted(required.features) if lacking[f]]):
        for kind in dict.fromkeys(k for f in refused for k in READS[f]):
            dataset(data, kind)  # two or more left: E18 naming each (4.3)
        raise _not_in_snapshot(data, {f: lacking[f] for f in refused})
    wanted = NEEDS.keys() if required is None else required.features
    used = list(dict.fromkeys(r for f in sorted(wanted) if f in on for r in taken[f]))
    if bars is not None and f02 is not None and any(r.id == "F-02" for r in used):
        _off_calendar(folder, data, bars, f02[1], market_of)
    if used and policy is FallbacksPolicy.FAIL:
        raise _refused(data, used)
    for id_ in dict.fromkeys(r.id for r in used):
        warnings.warn(str(_warning(data, [r for r in used if r.id == id_])), stacklevel=3)
    whole = {"cum_factor_split", "cum_factor_total"} <= columns
    cum: Literal["columns", "resolver"] = "columns" if whole else "resolver"  # F-04
    supported = frozenset(p for p in data.get("profiles", []) if p in SUPPORTED)
    assumptions = tuple(SAYS[i] for i in ("F-02",) if any(r.id == i for r in used))
    return DataCapabilities(on, supported, cum), used, assumptions


Sessions = tuple[list[FallbackRecord], dict[str, set[dt.date]]]


def _sessions(
    folder: Path, markets: Mapping[str, Mapping[str, Any]],
    kinds: Mapping[str, Mapping[str, Any]], by_market: Mapping[str, Mapping[str, Any]],
) -> Sessions | None:  # fmt: skip
    """F-02 for each market of the bars whose `calendar_id` `calendar_sessions` lacks (4.4-4):
    its sessions from the first to the last day of its bars, as records and as dates; None
    when exchange_calendars does not know such a calendar (then E18 for what needs them)."""
    held = {str(c) for c in _values(folder, kinds.get("calendar_sessions"), "calendar_id")}
    gap = {m: e for m, e in by_market.items() if markets[m]["calendar_id"] not in held}
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
    dates: Mapping[str, set[dt.date]], market_of: Mapping[str, str],
) -> None:  # fmt: skip
    """4.5 F-02: a bar of a synthesized market on a day that is not one of its sessions is E14
    `TDS-R003`, the check the checker leaves blind without `calendar_sessions`."""
    off: list[dict[str, Any]] = []
    for f in bars["files"]:  # filtered in Arrow: only the off rows reach Python
        t = pq.read_table(folder / f["path"], columns=[ID_COLUMN, "session_date"])
        for m, days in dates.items():
            # the ids' value type: a dictionary-encoded column holds strings too (TDS 3.2)
            value = pa.types.is_dictionary(t[ID_COLUMN].type)
            kind = t[ID_COLUMN].type.value_type if value else t[ID_COLUMN].type
            ids = pa.array([i for i, x in market_of.items() if x == m], kind)
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
    by_market: Mapping[str, Mapping[str, Any]], market_of: Mapping[str, str],
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
    return [FallbackRecord("F-15", "market_rules", m, int(by_market.get(m, {}).get(
        "instruments", 0))) for m in bare if m not in sourced]  # fmt: skip


def _warning(data: Mapping[str, Any], records: Sequence[FallbackRecord]) -> DataProfileWarning:
    first = records[0]
    return DataProfileWarning(
        what=f"fallback {first.id} used: {SAYS[first.id]} for "
             f"{', '.join(r.market for r in records)}",
        where="; ".join(f"dataset {r.dataset}, market {r.market}, {r.count}" for r in records),
        why="a fallback changes what a term means (4.5)",
        fix="[data] fallbacks = 'fail' to stop instead", more="spec 4.5; tds check --level full",
        layer=_layer(data, first.dataset), subject=first.id,
    )  # fmt: skip


def _refused(data: Mapping[str, Any], used: Sequence[FallbackRecord]) -> SnapshotError:
    ids = ", ".join(dict.fromkeys(r.id for r in used))
    return SnapshotError(
        what=f"fallback {ids} needed and [data] fallbacks = 'fail'",
        where=", ".join(f"{r.dataset} ({r.market})" for r in used),
        why="a fallback changes what a term means (4.5)",
        fix="use a snapshot with those datasets, or [data] fallbacks = 'warn' (recorded)",
        more="spec 4.4 step 3 and 4.5", layer=_layer(data, used[0].dataset),
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
