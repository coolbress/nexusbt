"""`Snapshot.actions(market, cutoff)` (spec 5.3.3a): one market's corporate actions through the
one resolver, `nexusbt_tds.actions.resolve`; the engine resolves nothing itself."""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from nexusbt.contracts import ID_COLUMN as ID
from nexusbt.contracts import ResolvedActions
from nexusbt.data._datasets import dataset
from nexusbt_tds.actions import resolve

if TYPE_CHECKING:
    from nexusbt_tds.manifest import Manifest


def resolved_actions(manifest: Manifest, market: str, cutoff: object) -> ResolvedActions:
    """The chains of `market`'s instruments at `cutoff`: an aware datetime, a numpy
    `datetime64` in UTC (as `Calendar.ready`), or None for the whole package (+inf)."""
    events = _rows(manifest, dataset(manifest.data, "corporate_actions"))
    instruments = _rows(manifest, dataset(manifest.data, "instruments"))
    if events is None or instruments is None:
        return ResolvedActions({})
    ids = instruments.filter(pc.equal(instruments["market"], market))[ID]
    return ResolvedActions(resolve(events.filter(pc.is_in(events[ID], ids)), _at(cutoff)).chains)


def _rows(manifest: Manifest, entry: Mapping[str, Any] | None) -> pa.Table | None:
    tables = [pq.read_table(manifest.root / f["path"]) for f in (entry or {}).get("files", [])]
    return pa.concat_tables(tables, promote_options="default") if tables else None


def _at(cutoff: object) -> dt.datetime | None:
    if cutoff is None:
        return None
    if isinstance(cutoff, np.datetime64):
        naive: dt.datetime = cutoff.astype("datetime64[us]").item()
        return naive.replace(tzinfo=dt.UTC)
    if isinstance(cutoff, dt.datetime) and cutoff.tzinfo is not None:
        return cutoff
    raise TypeError(f"a cutoff is an aware datetime, a UTC datetime64 or None, not {cutoff!r}")
