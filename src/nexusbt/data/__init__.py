"""Opening snapshots (calls the tds checker), fallbacks, market blocks, L0 cache, calendars, FX."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from nexusbt.contracts import SnapshotError

if TYPE_CHECKING:
    import pyarrow as pa

    from nexusbt.config import Config
    from nexusbt.contracts import ResolvedActions
    from nexusbt_tds import ProfileStatus  # a development dependency until T1.1a (#61 Decisions)


@dataclass(frozen=True, slots=True)
class DataConfig: ...


@dataclass(frozen=True, slots=True)
class CapabilityRequest: ...


@dataclass(frozen=True, slots=True)
class DataCapabilities: ...


@dataclass(frozen=True, slots=True)
class FallbackRecord: ...


@dataclass(frozen=True, slots=True)
class MarketInfo: ...


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
    """An opened TDS package (2.4 `data.Snapshot`); each member raises until its ticket."""

    @property
    def id(self) -> str:
        raise NotImplementedError

    @property
    def semantic_hash(self) -> str:
        raise NotImplementedError

    @property
    def value_hash(self) -> str:
        raise NotImplementedError

    @property
    def physical_hash(self) -> str:
        raise NotImplementedError

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
        raise NotImplementedError

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


def open_snapshot(cfg: DataConfig, *, required: CapabilityRequest | None = None) -> Snapshot:
    raise NotImplementedError


def _snapshot_markets(config: Config) -> dict[str, str] | None:
    """The `markets` object (name → currency) of the package `[data]` points at, or None.

    `path` (a package, or a parent with `LATEST`) before `root` + `snapshot` (4.2, 3.11).
    T1.1a's `open_snapshot` replaces this helper. `nexusbt-tds` stays a development dependency
    (#45 Decisions 4) and is imported here only, inside the call; it moves to the run-time
    dependencies with T1.1a.
    """
    from nexusbt_tds.manifest import ManifestError, read_manifest

    data = config.values["data"]
    try:
        if data["path"]:
            folder = Path(data["path"])
            if not (folder / "tds.json").is_file() and (folder / "LATEST").is_file():
                folder /= (folder / "LATEST").read_text(encoding="utf-8").strip()
        elif data["root"]:
            root, name = Path(data["root"]), data["snapshot"]
            if name == "latest":  # resolved once per call (4.2)
                name = (root / "LATEST").read_text(encoding="utf-8").strip()
            folder = root / name
        else:
            return None
        declared = read_manifest(folder).data.get("markets")
    except (OSError, ManifestError) as error:
        raise SnapshotError(
            what=f"no readable tds.json for [data]: {error}", where="nexusbt.toml [data]",
            why="the markets come from the snapshot's tds.json", fix="check [data] path or root",
            more="spec 4.2",
        ) from None  # fmt: skip
    entries = declared.items() if isinstance(declared, dict) else ()
    return {name: str(entry.get("currency")) for name, entry in entries if isinstance(entry, dict)}
