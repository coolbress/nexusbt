"""Opening snapshots (calls the tds checker), fallbacks, market blocks, L0 cache, calendars, FX."""

from __future__ import annotations

import os
import warnings
from collections import Counter
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import nexusbt_tds as tds
from nexusbt.config.packs import PACKS, load_pack
from nexusbt.contracts import (
    CapabilityError,
    ConfigError,
    DataProfileWarning,
    DecimalRatioPolicy,
    FallbacksPolicy,
    PinsPolicy,
    SnapshotError,
    VerifyPolicy,
)
from nexusbt.data._actions import resolved_actions
from nexusbt.data._block import MarketBlock as MarketBlock
from nexusbt.data._block import block_columns, build_block
from nexusbt.data._calendar import Calendar as Calendar
from nexusbt.data._calendar import read_calendar
from nexusbt.data._capabilities import CapabilityRequest as CapabilityRequest
from nexusbt.data._capabilities import DataCapabilities as DataCapabilities
from nexusbt.data._capabilities import FallbackRecord as FallbackRecord
from nexusbt.data._capabilities import _columns, check_fields, decide, said
from nexusbt.data._coverage import BarsExtent
from nexusbt.data._datasets import chosen, layer
from nexusbt.data._outputs import table_value_hash as table_value_hash
from nexusbt.data._ratios import RatioExclusion as RatioExclusion
from nexusbt.data._ratios import check_ratios
from nexusbt.data._schedule import Schedule as Schedule
from nexusbt.data._schedule import annually as annually
from nexusbt.data._schedule import daily as daily
from nexusbt.data._schedule import decision_grid as decision_grid
from nexusbt.data._schedule import default_clock as default_clock
from nexusbt.data._schedule import every as every
from nexusbt.data._schedule import monthly as monthly
from nexusbt.data._schedule import quarterly as quarterly
from nexusbt.data._schedule import weekly as weekly
from nexusbt.data._stamp import check_files
from nexusbt_tds.hash import (
    declared_semantic_hash,
    declared_value_hash,
    package_hashes,
    resolved_columns,
)
from nexusbt_tds.manifest import Manifest, ManifestError
from nexusbt_tds.schemas.verify import dictionary_schemas, load_schemas

if TYPE_CHECKING:
    import pyarrow as pa

    from nexusbt.config import Config
    from nexusbt.contracts import ResolvedActions
    from nexusbt_tds import ProfileStatus

    #: What `open_snapshot` decided (4.4-5): the profiles' results, the capabilities, the fallbacks.
    Decided = tuple[dict[str, ProfileStatus], DataCapabilities, list[FallbackRecord]]

GENERIC = "_generic"  # the pack `[markets] allow_untested` runs a market without one under (4.7)
#: A010 (exact ratios) never raises E14: the engine's own check at open decides (4.4-2, 4-4).
_NOT_E14 = frozenset({"TDS-A010"})


@dataclass(frozen=True, slots=True)
class DataConfig:
    """What `open_snapshot` needs of `nexusbt.toml` (3.11 `[data]`, `[markets]`).

    `path` is a package folder or a folder with `LATEST` (4.2, V31-PUB-03); `markets` are the
    markets the run needs, each of which must have a rules pack (4.4-4); `stamps` is the folder
    of the verification stamps, `<runs.dir>/.cache/verified` (4.2), None for no stamp; `pins`
    is where a run's pin goes besides the index (4.2, 4.4-6)."""

    path: Path
    verify: VerifyPolicy = VerifyPolicy.MANIFEST
    markets: tuple[str, ...] = ()
    allow_untested: bool = False
    decimal_ratio: DecimalRatioPolicy = DecimalRatioPolicy.EXCLUDE_INSTRUMENT
    fallbacks: FallbacksPolicy = FallbacksPolicy.WARN
    stamps: Path | None = None
    pins: PinsPolicy = PinsPolicy.INDEX_ROOT

    @classmethod
    def from_config(cls, config: Config) -> DataConfig:
        data = config.values["data"]
        if data["path"]:
            path = Path(data["path"])
        elif data["root"]:  # `snapshot = "latest"`: the root, read through its LATEST
            name = data["snapshot"]
            path = Path(data["root"]) / ("" if name == "latest" else name)
        else:
            raise ConfigError(
                what="no snapshot to open", where="nexusbt.toml [data]",
                why="the engine reads one TDS package path (4.2)",
                fix="set [data] path, or [data] root (or $NEXUSBT_DATA_ROOT)", more="spec 3.11",
                layer="config — nexusbt.toml [data] path = none",
            )  # fmt: skip
        allow = bool(config.values["markets"]["allow_untested"])
        ratio = DecimalRatioPolicy(config.values["corporate_actions"]["decimal_ratio"])
        stamps = Path(config.values["runs"]["dir"]) / ".cache" / "verified"
        return cls(path, VerifyPolicy(data["verify"]), allow_untested=allow, decimal_ratio=ratio,
                   fallbacks=FallbacksPolicy(data["fallbacks"]), stamps=stamps,
                   pins=PinsPolicy(data["pins"]))  # fmt: skip


@dataclass(frozen=True, slots=True)
class MarketInfo:
    """One `markets` entry of tds.json (TDS 3.8) and the rules pack it runs under (4.7):
    `"KR@1"`, `"_generic@1"` under `allow_untested`, or None when it has none."""

    calendar_id: str
    currency: str
    timezone: str
    complete_through_session: str | None
    rules: str | None


@dataclass(frozen=True, slots=True)
class DailyCoverage:
    """One market's `coverage.by_market` entry of the daily bars (TDS 4.3), for `doctor`;
    None where the package does not declare the key (each is optional)."""

    first: str | None
    last: str | None
    instruments: int | None
    rows: int | None


@dataclass(frozen=True, slots=True)
class PITBlock: ...


@dataclass(frozen=True, slots=True)
class EventTables: ...


@dataclass(frozen=True, slots=True)
class FxSeries: ...


@dataclass(frozen=True, slots=True)
class Explanation: ...


class Snapshot:
    """An opened TDS package (2.4 `data.Snapshot`); a member that raises waits for its ticket.

    `warnings` counts the checker's warnings per TDS code (4.4-2); `assumptions` are the
    sentences a run manifest records, such as an untested market's (4.7); `ca_exclusions`
    are the instruments 5.6.1 excludes for an event without a usable exact ratio (4.4-4);
    `unchecked` are the TDS codes the check level did not judge (4.4-5, the manifest's
    `data.unchecked`); `daily` and `daily_columns` are the daily bars' coverage per market and
    column count, as `doctor` prints them (3.10)."""

    def __init__(
        self,
        manifest: Manifest,
        hashes: Mapping[str, str],
        markets: Mapping[str, MarketInfo],
        warnings: Mapping[str, int],
        assumptions: tuple[str, ...],
        ca_exclusions: tuple[RatioExclusion, ...],
        decided: Decided,
        *,
        unchecked: tuple[str, ...] = (),
        daily: Mapping[str, DailyCoverage] | None = None,
        daily_columns: int = 0,
    ) -> None:
        self._manifest, self._hashes, self._markets = manifest, hashes, markets
        self.warnings, self.assumptions = dict(warnings), assumptions
        self.ca_exclusions, self._decided = ca_exclusions, decided
        self.unchecked, self.daily, self.daily_columns = unchecked, dict(daily or {}), daily_columns

    @property
    def id(self) -> str:
        return str(self._manifest.data["snapshot_id"])

    @property
    def semantic_hash(self) -> str:
        return self._hashes["semantic_sha256"]

    @property
    def value_hash(self) -> str:
        return self._hashes["value_sha256"]

    @property
    def physical_hash(self) -> str:
        return self._hashes["physical_sha256"]

    @property
    def profiles(self) -> dict[str, ProfileStatus]:
        """Per profile, declared and checked to which level (4.3); supported: `capabilities`."""
        return dict(self._decided[0])

    @property
    def capabilities(self) -> DataCapabilities:
        return self._decided[1]

    @property
    def fallbacks(self) -> list[FallbackRecord]:
        return list(self._decided[2])

    def _recorded(self) -> dict[str, Any]:
        """4.4-5: what a run manifest keeps of the open, as it is: `data.profiles`,
        `data.capabilities`, `data.unchecked`, `data.fallbacks` (`[]` for none; #687) and
        `assumptions`, with one sentence per fallback (1.2). Names, codes and counts only."""
        caps = self.capabilities
        data = {
            "profiles": {n: {"declared": p.declared, "verified_level": p.verified_level,
                             "result": p.result} for n, p in self.profiles.items()},
            "capabilities": {"features": sorted(caps.features),
                             "supported": sorted(caps.supported)},
            "unchecked": list(self.unchecked),
            "fallbacks": [{"id": f.id, "dataset": f.dataset, "market": f.market, "count": f.count,
                           "column": f.column} for f in self.fallbacks],
        }  # fmt: skip
        return {"data": data, "assumptions": [*self.assumptions, *said(self.fallbacks)]}

    @property
    def markets(self) -> Mapping[str, MarketInfo]:
        return self._markets

    def calendar(self, market: str) -> Calendar:
        """The sessions of `market` and the time each of its rows freezes (5.1.1, 5.1.2)."""
        if market not in self._markets:
            raise _no_pack(market, self._manifest, False)
        return read_calendar(self._manifest, market)

    def market_block(
        self, market: str, fields: Sequence[str], sessions: object, *, overlap: int = 0
    ) -> MarketBlock:
        """The dense block of the daily bars' `fields` over the calendar rows from the first to
        the last of `sessions`, after up to `overlap` rows of the previous chunk (5.3.1).
        `close_tr` on an adjusted-price package is E18 (4.3), at the first chunk's read."""
        self._check_fields(fields, market)
        return build_block(self._manifest, self.calendar(market), fields, sessions, overlap)

    def _check_fields(self, fields: Sequence[str], market: str | None = None) -> None:
        """E18 for a bars column the graph reads that this package cannot give (4.3, 4.4-3):
        `close_tr` without raw prices, or a column with no value in the bars or in `market`'s.
        `run_pipeline` calls it once the graph is built, before any value (#705); not public."""
        check_fields(self._manifest.data, self.capabilities, fields, market)

    def block_columns(self, market: str, sessions: object) -> tuple[str, ...]:
        """The instruments `market_block` would hold over `sessions`, no bar read: what a run
        counts to size its chunks (5.3.8)."""
        return block_columns(self._manifest, market, sessions)

    def intervals(
        self,
        kind: str,
        fields: Sequence[str],
        market: str,
        cutoffs: object,
        history_mode: str = "economic",
    ) -> PITBlock:
        raise NotImplementedError

    def actions(self, market: str, cutoff: object) -> ResolvedActions:
        """`market`'s corporate-action chains as known at `cutoff` (5.3.3a)."""
        return resolved_actions(self._manifest, market, cutoff)

    def events(self, market: str, start: object, end: object) -> EventTables:
        raise NotImplementedError

    def fx(self) -> FxSeries:
        raise NotImplementedError

    def instruments(self, market: str) -> pa.Table:
        raise NotImplementedError

    def explain(self, instrument_id: str, field: str, ts: object) -> Explanation:
        raise NotImplementedError


def dropped_rows(
    snapshot: Snapshot, found: Collection[tuple[str, str, str, int]]
) -> list[dict[str, Any]]:
    """#866, INV-12: the bars a run's blocks left out (`MarketBlock.dropped`), counted by
    dataset and cause, as the run manifest's `data.dropped` keeps them; one E30 when any."""
    counts = Counter((dataset, cause) for dataset, cause, _, _ in found)
    records = [{"dataset": d, "cause": c, "count": n} for (d, c), n in sorted(counts.items())]
    if records:
        named = "; ".join(f"dataset {d}: " + ", ".join(f"{r['cause']} {r['count']}" for r in
                          records if r["dataset"] == d)
                          for d in dict.fromkeys(r["dataset"] for r in records))  # fmt: skip
        warnings.warn(str(DataProfileWarning(
            what=f"bars left out of the run: {named}", where=named,
            why="a bar of an instrument `instruments` lacks, or on a day that is no session of "
                "its market's calendar, is not read (4.4)",
            fix="tds check <package> --level full names each row",
            more="spec 4.4; INV-12", layer=layer(snapshot._manifest.data, min(counts)[0]),
            subject="dropped bars",
        )), stacklevel=4)  # fmt: skip  # the caller of `run_pipeline`
    return records


def dataset_columns(snapshot: Snapshot) -> dict[str, tuple[tuple[str, str | None], ...]]:
    """Per dataset name, its (column, TDS type) pairs as `nexusbt_tds` resolves them, in that
    order.

    The column set is `hash.resolved_columns`, the one the value hash and the checker read
    (#144, #331): the engine resolves nothing itself (INV-17)."""
    manifest = snapshot._manifest
    schemas = {**load_schemas(), **dictionary_schemas()}
    columns = {}
    for ds in manifest.datasets:
        schema = schemas.get(str(ds.get("kind")))
        resolved = resolved_columns(ds, schema.columns if schema else ())
        columns[str(ds.get("name"))] = tuple((c.name, c.type) for c in resolved)
    return columns


def _data_root(path: Path) -> Path | None:
    """The data root: the folder holding `LATEST`, given or the package's parent (4.2); None
    for a package alone, which another producer may give (no `LATEST`, no `PINS/`)."""
    for folder in (path, path.parent):
        if (folder / "LATEST").is_file():
            return folder
    return None


def _snapshot_folder(snapshot: Snapshot) -> Path:
    """The package folder `snapshot` was opened from; its data root is beside it (4.2)."""
    return Path(snapshot._manifest.root)


def _package(path: Path) -> Path:
    """The package folder: `path` itself, or the snapshot its `LATEST` names, read once (4.2)."""
    if (path / "tds.json").is_file() or not (path / "LATEST").is_file():
        return path
    name = (path / "LATEST").read_text(encoding="utf-8").strip()
    if not name or Path(name).is_absolute() or ".." in Path(name).parts:
        raise ValueError(f"LATEST in {path} names {name!r}, outside the data root")
    return path / name


def open_snapshot(
    cfg: DataConfig, *, required: CapabilityRequest | None = None, sha256: bool = False
) -> Snapshot:
    """Open one TDS package: the checker at `cfg.verify`, its errors as E14 (4.4-1, 2), and
    a rules pack for each market `cfg.markets` names (4.4-4), then the features `required` names
    with their fallbacks (4.4-3; with no request, every feature the package can give).

    `sha256` is for `rerun`, `reconcile`, `live` and `fill`: at least `schema`, and each file's
    sha256, skipped for a file whose identity `cfg.stamps` holds (4.4-1, R3-16)."""
    try:
        folder = _package(Path(cfg.path))
    except (OSError, ValueError) as unread:
        raise _unread(str(cfg.path), str(unread)) from None
    level = VerifyPolicy.SCHEMA if sha256 and cfg.verify is VerifyPolicy.MANIFEST else cfg.verify
    result = tds.check(folder, level=level.value)
    errors = [f for f in result.errors if f.code not in _NOT_E14]
    if sha256 and not errors and level is not VerifyPolicy.FULL:  # `full` hashed every file
        errors = check_files(folder, tds.read_manifest(folder), cfg.stamps)
    if errors:
        try:
            data = tds.read_manifest(folder).data
        except ManifestError:  # no readable tds.json: no snapshot id or producer to name
            data = {}
        first, producer = errors[0], data.get("producer")
        raise SnapshotError.from_check(
            path=str(folder), counts=Counter(f.code for f in errors), dataset=first.dataset or "-",
            file=first.file or "-", key=str(first.key or "-"), hint=first.message,
            snapshot_id=str(data.get("snapshot_id", folder.name)),
            producer_hints={first.code: first.hint} if first.hint else None,  # producer.hints
            producer=str(producer.get("name", "-")) if isinstance(producer, dict) else "-",
        )  # fmt: skip
    manifest = tds.read_manifest(folder)
    # Below `full` the row bytes are trusted as declared, tds.json's metadata is not (ADR 0042)
    declared, semantic = manifest.data["hashes"], declared_semantic_hash(folder)
    whole = semantic and {"value_sha256", "physical_sha256"} <= declared.keys()
    if whole and declared_value_hash(folder) != declared["value_sha256"]:
        raise _disagreeing_value_hash(folder, manifest)
    hashes = {**declared, "semantic_sha256": semantic} if whole else package_hashes(folder)
    markets = {m: _market(m, e, cfg.allow_untested) for m, e in manifest.data["markets"].items()}
    for m in cfg.markets:
        if markets.get(m) is None or markets[m].rules is None:
            raise _no_pack(m, manifest, m in markets)
    excluded, literal = check_ratios(manifest, cfg.markets, cfg.decimal_ratio)
    generic = [m for m, info in markets.items() if str(info.rules).startswith(GENERIC)]
    untested = tuple(f"untested market rules: {m}" for m in generic)
    if literal:  # 5.6.1's report header line for `decimal_ratio = "literal"`
        untested += (f"decimal ratios used literally: {literal} events",)
    rules = {m: info.rules for m, info in markets.items()}
    kinds = chosen(manifest.data)
    bars = kinds.get("bars")  # the one daily bars dataset, or none (4.3)
    extent = BarsExtent(folder, bars, kinds.get("instruments"))
    caps, used = decide(folder, manifest, rules, result.warnings, required,
                        cfg.fallbacks, extent)  # fmt: skip
    warnings = Counter(f.code for f in result.warnings)
    decided = (result.profiles, caps, used)
    covered = (bars or {}).get("coverage", {}).get("by_market", {})
    daily = {m: DailyCoverage(e.get("first"), e.get("last"), e.get("instruments"), e.get("rows"))
             for m, e in covered.items()}  # fmt: skip
    return Snapshot(manifest, hashes, markets, warnings, untested, excluded, decided,
                    unchecked=tuple(result.unchecked), daily=daily,
                    daily_columns=len(_columns(folder, bars)))  # fmt: skip


def _market(name: str, entry: Mapping[str, Any], allow_untested: bool) -> MarketInfo:
    """A pack is the market's only when its `calendar_ids` hold the market's calendar (4.7)."""
    rules = None
    if name in PACKS and name != GENERIC:
        pack = load_pack(name)["pack"]
        if entry.get("calendar_id") in pack["calendar_ids"]:
            rules = f"{name}@{pack['version']}"
    if rules is None and allow_untested:
        rules = f"{GENERIC}@{load_pack(GENERIC)['pack']['version']}"
    return MarketInfo(
        str(entry.get("calendar_id")), str(entry.get("currency")), str(entry.get("timezone")),
        entry.get("complete_through_session"), rules,
    )  # fmt: skip


def _no_pack(market: str, manifest: Manifest, declared: bool) -> CapabilityError:
    supported = ", ".join(p for p in PACKS if p != GENERIC)
    what = f"no market rules pack for {market}; supported: {supported}"
    if not declared:
        what = f"market {market} is not in the snapshot ({', '.join(manifest.data['markets'])})"
    return CapabilityError(
        what=what, where=f"snapshot {manifest.data['snapshot_id']} markets",
        why="a market runs under the rules pack of its calendar (4.7)",
        fix="set [markets] allow_untested = true to run with generic rules (recorded)",
        more="spec 4.4 step 4 and 4.7; python -m nexusbt.config.packs --describe KR",
        layer="config — nexusbt.toml [markets] allow_untested = false",
    )  # fmt: skip


def _disagreeing_value_hash(folder: Path, manifest: Manifest) -> SnapshotError:
    """E14 `TDS-H003` (ADR 0042, #455): the declared dataset value hashes do not hash to the
    declared package value hash, so `full` would refuse the package; which is wrong is unknown."""
    data, producer = manifest.data, manifest.data.get("producer")
    return SnapshotError.from_check(
        path=str(folder), counts={"TDS-H003": 1}, dataset="-", file="-", key="-",
        hint="hashes.value_sha256 differs from the value computed from the declared dataset"
        " value hashes (no row read)",
        snapshot_id=str(data["snapshot_id"]),
        producer=str(producer.get("name", "-")) if isinstance(producer, dict) else "-",
    )  # fmt: skip


def _unread(at: str, what: str, where: str = "the path given") -> SnapshotError:
    return SnapshotError(
        what=what, where=where, why="a snapshot is a folder with tds.json, or LATEST names one",
        fix="check [data] path or root", more=f"tds check {at} --level full; spec 4.2",
        layer=f"data — snapshot {at} / tds.json / column - / producer -",  # #52 (3): `-`
    )  # fmt: skip


def _snapshot_markets(config: Config) -> dict[str, str] | None:
    """The `markets` object (name → currency) of the package `[data]` points at, or None.

    `path` (a package, or a parent with `LATEST`) before `root` + `snapshot` (4.2, 3.11);
    only tds.json is read, unchecked, for `load_config`'s market names.
    """
    data = config.values["data"]
    at = data["path"] or data["root"]
    where = "nexusbt.toml [data] path" if data["path"] else "nexusbt.toml [data] root"
    if not data["path"] and data["root"] == os.environ.get("NEXUSBT_DATA_ROOT"):
        where = "$NEXUSBT_DATA_ROOT"  # `[data] root` unwritten: the variable gave it (3.11)
    if not at:
        return None
    try:
        manifest = tds.read_manifest(_package(DataConfig.from_config(config).path))
    except ValueError as outside:  # LATEST names a folder outside the root
        raise _unread(at, str(outside), where) from None
    except (OSError, ManifestError) as unread:
        raise _unread(at, f"no readable tds.json for [data]: {unread}", where) from None
    declared = manifest.data.get("markets")
    entries = declared.items() if isinstance(declared, dict) else ()
    return {name: str(entry.get("currency")) for name, entry in entries if isinstance(entry, dict)}
