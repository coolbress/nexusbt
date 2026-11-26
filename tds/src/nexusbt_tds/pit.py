"""The two-time-axis rectangle lookup (TDS 6.3 ③, spec 5.3.6): the one implementation, which
the checker's T012 and the engine's `data` both use.

A row is visible at known time `cutoff` on date `date` when `ts_known_from <= cutoff <
ts_known_to` and `valid_from <= date < valid_to` hold together (`instrument_symbols`, the one
two-time-axis kind since `classifications` left, #752); a null end is open. Picking the row
known last and then testing its effective period would let a row announced in advance hide
the one in effect.
"""

from __future__ import annotations

import datetime as dt

import pyarrow as pa
import pyarrow.compute as pc

#: The effective-period columns of `instrument_symbols`.
EFFECTIVE = (("valid_from", "valid_to"),)


def rect_lookup(rows: pa.Table, cutoff: dt.datetime, date: dt.date) -> pa.Table:
    """The rows of `rows` visible at (`cutoff`, `date`), in their order. A null
    `ts_known_from` is not visible: 5.2's default (the session open of `valid_from`) needs a
    calendar, so the caller fills it first. One row per discriminating key is the data's
    promise (T012); this function returns what is there."""
    start, end = EFFECTIVE[0]

    def inside(lo: str, hi: str, at: object) -> pc.Expression:
        upper = pc.field(hi)
        return (pc.field(lo) <= pc.scalar(at)) & (upper.is_null() | (upper > pc.scalar(at)))

    keep = inside("ts_known_from", "ts_known_to", cutoff) & inside(start, end, date)
    return rows.filter(keep)
