"""Spec 4.3 to 4.5: the data a graph's features need, what a package gives, the fallbacks."""

from __future__ import annotations

import warnings
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import pyarrow.parquet as pq

from nexusbt.config.packs import load_pack
from nexusbt.contracts import (
    ID_COLUMN,
    CapabilityError,
    DataProfileWarning,
    FallbacksPolicy,
    SnapshotError,
)
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
    kinds = {d["kind"]: d for d in reversed(data["datasets"])}  # the first of each kind
    bars = kinds.get("bars")
    by_market = bars["coverage"]["by_market"] if bars else {}
    lacking = {f: [k for k in needs if k not in kinds] for f, needs in NEEDS.items()}
    taken: dict[str, list[FallbackRecord]] = {f: [] for f in NEEDS}
    sessions = bars is not None and "calendar_sessions" not in kinds
    f02 = _sessions(data["markets"], by_market) if sessions else None
    for f in ("adjusted", "backtest"):
        if f02 is not None:
            lacking[f].remove("calendar_sessions")
            taken[f] += f02
        if bars is not None and bars["params"].get("price_basis") != "raw":
            lacking[f].append("raw bars (price_basis = raw)")
    columns = _columns(folder, bars)
    if bars is not None and (bars["params"].get("density") == "sparse"
                             or "obs_status" not in columns):  # fmt: skip
        taken["backtest"] += [FallbackRecord("F-03", bars["name"], m, int(e.get("rows", 0)))
                              for m, e in by_market.items()]  # fmt: skip
    years = Counter((f.dataset, str((f.key or {}).get(ID_COLUMN)).split(":")[0])
                    for f in found if f.code == "TDS-V011")  # fmt: skip
    taken["backtest"] += [FallbackRecord("F-16", str(d), m, n) for (d, m), n in years.items()]
    taken["grid"] += _no_grid(folder, kinds, rules, by_market)
    on = frozenset(f for f in NEEDS if not lacking[f])
    if required is not None and (refused := [f for f in sorted(required.features) if lacking[f]]):
        raise _not_in_snapshot(data, {f: lacking[f] for f in refused})
    wanted = NEEDS.keys() if required is None else required.features
    used = list(dict.fromkeys(r for f in sorted(wanted) if f in on for r in taken[f]))
    if used and policy is FallbacksPolicy.FAIL:
        raise _refused(data, used)
    for id_ in dict.fromkeys(r.id for r in used):
        warnings.warn(str(_warning(data, [r for r in used if r.id == id_])), stacklevel=3)
    whole = {"cum_factor_split", "cum_factor_total"} <= columns
    cum: Literal["columns", "resolver"] = "columns" if whole else "resolver"  # F-04
    supported = frozenset(p for p in data.get("profiles", []) if p in SUPPORTED)
    assumptions = tuple(SAYS[i] for i in ("F-02",) if any(r.id == i for r in used))
    return DataCapabilities(on, supported, cum), used, assumptions


def _sessions(
    markets: Mapping[str, Mapping[str, Any]], by_market: Mapping[str, Mapping[str, Any]]
) -> list[FallbackRecord] | None:
    """F-02: each market's sessions from the first to the last day of its bars, or None when
    exchange_calendars does not know a market's calendar (then E18 for what needs them)."""
    import exchange_calendars as xcals  # only a package without sessions pays its import

    known = set(xcals.get_calendar_names())
    if any(markets[m]["calendar_id"] not in known for m in by_market):
        return None
    out = []
    for m, e in by_market.items():
        sessions = xcals.get_calendar(markets[m]["calendar_id"]).sessions_in_range(
            e["first"], e["last"])  # fmt: skip
        out.append(FallbackRecord("F-02", "calendar_sessions", m, len(sessions)))
    return out


def _columns(folder: Path, dataset: Mapping[str, Any] | None) -> set[str]:
    """The columns of a dataset's first file, read from its footer."""
    if dataset is None or not dataset["files"]:
        return set()
    return set(pq.read_schema(folder / dataset["files"][0]["path"]).names)


def _no_grid(
    folder: Path, kinds: Mapping[str, Mapping[str, Any]], rules: Mapping[str, str | None],
    by_market: Mapping[str, Mapping[str, Any]],
) -> list[FallbackRecord]:  # fmt: skip
    """F-15: a market with a pack and no grid anywhere: no instrument tick column, no
    `market_rules` rows of the market and no `tick_table` or `base_unit` in its pack."""
    ticks = {"tick_size", "tick_rule_id"} & _columns(folder, kinds.get("instruments"))
    ruled = kinds.get("market_rules", {}).get("coverage", {}).get("by_market", {})
    out = []
    for m, pack in rules.items():
        if pack is None:  # a market without a pack runs nothing (4.4-4)
            continue
        grid = load_pack(pack.split("@")[0])["grid"]
        if not ({"tick_table", "base_unit"} & grid.keys() or ticks or m in ruled):
            count = int(by_market.get(m, {}).get("instruments", 0))
            out.append(FallbackRecord("F-15", "market_rules", m, count))
    return out


def _layer(data: Mapping[str, Any], dataset: str) -> str:
    producer = data.get("producer")
    name = str(producer.get("name", "-")) if isinstance(producer, dict) else "-"
    return f"data — snapshot {data['snapshot_id']} / {dataset} / column - / producer {name}"


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
