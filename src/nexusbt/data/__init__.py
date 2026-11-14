"""Opening snapshots (calls the tds checker), fallbacks, market blocks, L0 cache, calendars, FX."""

from __future__ import annotations

import os
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import nexusbt_tds as tds
from nexusbt.config.packs import PACKS, load_pack
from nexusbt.contracts import (
    CapabilityError,
    ConfigError,
    DecimalRatioPolicy,
    SnapshotError,
    VerifyPolicy,
)
from nexusbt.data._ratios import RatioExclusion as RatioExclusion
from nexusbt.data._ratios import check_ratios
from nexusbt_tds.hash import package_hashes
from nexusbt_tds.manifest import Manifest, ManifestError

if TYPE_CHECKING:
    import pyarrow as pa

    from nexusbt.config import Config
    from nexusbt.contracts import ResolvedActions
    from nexusbt_tds import ProfileStatus

GENERIC = "_generic"  # the pack `[markets] allow_untested` runs a market without one under (4.7)
#: A010 (exact ratios) never raises E14: the engine's own check at open decides (4.4-2, 4-4).
_NOT_E14 = frozenset({"TDS-A010"})


@dataclass(frozen=True, slots=True)
class DataConfig:
    """What `open_snapshot` needs of `nexusbt.toml` (3.11 `[data]`, `[markets]`).

    `path` is a package folder or a folder with `LATEST` (4.2, V31-PUB-03); `markets` are the
    markets the run needs, each of which must have a rules pack (4.4-4)."""

    path: Path
    verify: VerifyPolicy = VerifyPolicy.MANIFEST
    markets: tuple[str, ...] = ()
    allow_untested: bool = False
    decimal_ratio: DecimalRatioPolicy = DecimalRatioPolicy.EXCLUDE_INSTRUMENT

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
        return cls(path, VerifyPolicy(data["verify"]), allow_untested=allow, decimal_ratio=ratio)


@dataclass(frozen=True, slots=True)
class CapabilityRequest: ...


@dataclass(frozen=True, slots=True)
class DataCapabilities: ...


@dataclass(frozen=True, slots=True)
class FallbackRecord: ...


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
class Calendar: ...


@dataclass(frozen=True, slots=True)
class MarketBlock: ...


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
    are the instruments 5.6.1 excludes for an event without a usable exact ratio (4.4-4)."""

    def __init__(
        self,
        manifest: Manifest,
        hashes: Mapping[str, str],
        markets: Mapping[str, MarketInfo],
        warnings: Mapping[str, int],
        assumptions: tuple[str, ...],
        ca_exclusions: tuple[RatioExclusion, ...] = (),
    ) -> None:
        self._manifest, self._hashes, self._markets = manifest, hashes, markets
        self.warnings, self.assumptions = dict(warnings), assumptions
        self.ca_exclusions = ca_exclusions

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
        raise NotImplementedError

    @property
    def capabilities(self) -> DataCapabilities:
        raise NotImplementedError

    @property
    def fallbacks(self) -> list[FallbackRecord]:
        raise NotImplementedError

    @property
    def markets(self) -> Mapping[str, MarketInfo]:
        return self._markets

    def calendar(self, market: str) -> Calendar:
        raise NotImplementedError

    def market_block(self, market: str, fields: Sequence[str], sessions: object) -> MarketBlock:
        raise NotImplementedError

    def intervals(
        self,
        kind: str,
        fields: Sequence[str],
        market: str,
        cutoffs: object,
        edition: str,
        history_mode: str = "economic",
    ) -> PITBlock:
        raise NotImplementedError

    def actions(self, market: str, cutoff: object) -> ResolvedActions:
        raise NotImplementedError

    def events(self, market: str, start: object, end: object) -> EventTables:
        raise NotImplementedError

    def fx(self) -> FxSeries:
        raise NotImplementedError

    def instruments(self, market: str) -> pa.Table:
        raise NotImplementedError

    def share_counts(self, market: str, cutoffs: object) -> PITBlock:
        raise NotImplementedError

    def explain(self, instrument_id: str, field: str, ts: object) -> Explanation:
        raise NotImplementedError


def _package(path: Path) -> Path:
    """The package folder: `path` itself, or the snapshot its `LATEST` names, read once (4.2)."""
    if (path / "tds.json").is_file() or not (path / "LATEST").is_file():
        return path
    name = (path / "LATEST").read_text(encoding="utf-8").strip()
    if not name or Path(name).is_absolute() or ".." in Path(name).parts:
        raise ValueError(f"LATEST in {path} names {name!r}, outside the data root")
    return path / name


def open_snapshot(cfg: DataConfig, *, required: CapabilityRequest | None = None) -> Snapshot:
    """Open one TDS package: the checker at `cfg.verify`, its errors as E14 (4.4-1, 2), and
    a rules pack for each market `cfg.markets` names (4.4-4). Capabilities: T1.1b."""
    try:
        folder = _package(Path(cfg.path))
    except (OSError, ValueError) as unread:
        raise _unread(str(cfg.path), str(unread)) from None
    result = tds.check(folder, level=cfg.verify.value)
    errors = [f for f in result.errors if f.code not in _NOT_E14]
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
    declared = manifest.data["hashes"]  # trusted as declared below `full`, which checks them
    whole = {"semantic_sha256", "value_sha256", "physical_sha256"} <= declared.keys()
    hashes = declared if whole else package_hashes(folder)
    markets = {m: _market(m, e, cfg.allow_untested) for m, e in manifest.data["markets"].items()}
    for m in cfg.markets:
        if markets.get(m) is None or markets[m].rules is None:
            raise _no_pack(m, manifest, m in markets)
    excluded, literal = check_ratios(manifest, cfg.markets, cfg.decimal_ratio)
    generic = [m for m, info in markets.items() if str(info.rules).startswith(GENERIC)]
    untested = tuple(f"untested market rules: {m}" for m in generic)
    if literal:  # 5.6.1's report header line for `decimal_ratio = "literal"`
        untested += (f"decimal ratios used literally: {literal} events",)
    warnings = Counter(f.code for f in result.warnings)
    return Snapshot(manifest, hashes, markets, warnings, untested, excluded)


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
