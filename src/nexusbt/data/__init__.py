"""Opening snapshots (calls the tds checker), fallbacks, market blocks, L0 cache, calendars, FX."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pyarrow as pa

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
