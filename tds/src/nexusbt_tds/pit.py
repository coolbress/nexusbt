"""The two-time-axis rectangle lookup (TDS 6.3 ③, spec 5.3.6): the one implementation, which
the checker's T012 and the engine's `data` both use.

A row is visible at known time `cutoff` on date `date` when `ts_known_from <= cutoff <
ts_known_to` and `effective_from <= date < effective_to` hold together (`valid_from`,
`valid_to` in `instrument_symbols`); a null end is open. Picking the row known last and then
testing its effective period would let a row announced in advance hide the one in effect.
"""

from __future__ import annotations

import datetime as dt

import pyarrow as pa
import pyarrow.compute as pc

#: The effective-period columns: `classifications`, `universe_membership`; `instrument_symbols`.
EFFECTIVE = (("effective_from", "effective_to"), ("valid_from", "valid_to"))
#: The `classifications` edition filters (5.19): the rows of an edition and of `both`.
EDITIONS = {"strict": ("strict", "both"), "compare": ("compare", "both")}


def rect_lookup(
    rows: pa.Table, cutoff: dt.datetime, date: dt.date, *, edition: str | None = None
) -> pa.Table:
    """The rows of `rows` visible at (`cutoff`, `date`), in their order. `edition` `strict` or
    `compare` keeps that filter's rows, and `strict` drops rows whose `pit_quality` is
    `backfilled`. A null `ts_known_from` is not visible: 5.2's default (the session open of
    `valid_from`) needs a calendar, so the caller fills it first. One row per discriminating
    key is the data's promise (T012); this function returns what is there."""
    start, end = next(p for p in EFFECTIVE if p[0] in rows.column_names)

    def inside(lo: str, hi: str, at: object) -> pc.Expression:
        upper = pc.field(hi)
        return (pc.field(lo) <= pc.scalar(at)) & (upper.is_null() | (upper > pc.scalar(at)))

    keep = inside("ts_known_from", "ts_known_to", cutoff) & inside(start, end, date)
    if edition is not None:
        keep &= pc.field("edition").isin(list(EDITIONS[edition]))
        if edition == "strict" and "pit_quality" in rows.column_names:
            quality = pc.coalesce(pc.field("pit_quality"), pc.scalar(""))
            keep &= quality != pc.scalar("backfilled")
    return rows.filter(keep)
