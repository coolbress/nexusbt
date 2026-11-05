"""Event injection for the synthetic generator (spec 4.8 `EventSpec`), and the terms of a
corporate action that both injected and random events take.

An `EventSpec` is a dict of TDS column names plus a `"dataset"` key. So far it injects
`corporate_actions` rows only: `delistings` and `tradability_daily` come with a later pull
request of #220, and `fundamentals_*` are not generated until M2.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping, Sequence
from fractions import Fraction
from typing import Any

import numpy as np
import pyarrow as pa

from nexusbt.contracts import ID_COLUMN as ID

SHARE_KINDS = ("split", "reverse_split", "bonus_issue")
KINDS = (*SHARE_KINDS, "cash_dividend")
LATER = ("delistings", "tradability_daily")  # 4.8 names them; a later pull request (#220)
M2 = ("fundamentals_events", "fundamentals_state")
NEEDS = {"cash_dividend": ("cash_per_share",)}  # a share event needs a ratio, checked below
KEYS = ("dataset", ID, "kind", "ex_date")
#: Columns the generator derives from the terms and the version chain; given ones could
#: contradict them and break A001, so a spec may not set them.
DERIVED = frozenset({"event_id", "revision_of", "status", "price_factor", "share_factor",
                     "affects", "factor_method", "factor_ref_price"})  # fmt: skip


def _cash(cash: float, ref: float, currency: str) -> dict[str, Any]:
    """A cash dividend's terms, `cash` per share on the previous close `ref`: m = 1 - D / ref."""
    return {"cash_per_share": cash, "currency": currency, "gross_or_net": "gross",
            "price_factor": 1 - cash / ref, "share_factor": 1.0, "affects": "total_only",
            "factor_method": "cash_prev_close", "factor_ref_price": ref}  # fmt: skip


def _ratio(kind: str, num: int, den: int, ref: float) -> dict[str, Any]:
    """A share event's terms: `num` new shares for `den` old ones."""
    return {"ratio_num": num, "ratio_den": den, "price_factor": den / num,
            "ratio_new_per_old": (num - den) / den if kind == "bonus_issue" else num / den,
            "share_factor": num / den, "affects": "split_and_total", "factor_method": "ratio",
            "factor_ref_price": ref}  # fmt: skip


def check(events: Sequence[Mapping[str, Any]], markets: Sequence[str], schema: pa.Schema) -> None:
    """Refuse an `EventSpec` the generator cannot inject, before anything is written."""
    for spec in events:
        name, kind = spec.get("dataset"), spec.get("kind")
        if name in M2:
            raise NotImplementedError(f"EventSpec dataset {name!r}: not generated until M2")
        if name in LATER:
            raise NotImplementedError(f"EventSpec dataset {name!r}: not injected yet (#220)")
        if name != "corporate_actions":
            raise ValueError(f"EventSpec dataset {name!r}: one of the spec 4.8 datasets")
        missing = [c for c in (*KEYS, *NEEDS.get(str(kind), ())) if c not in spec]
        if kind in SHARE_KINDS and not ({"ratio_num", "ratio_den"} <= set(spec)
                                        or "ratio_new_per_old" in spec):  # fmt: skip
            missing.append("ratio_num and ratio_den, or ratio_new_per_old")
        unknown = sorted(set(spec) - set(schema.names) - {"dataset"} | set(spec) & DERIVED)
        if kind not in KINDS or missing or unknown:
            raise ValueError(f"EventSpec {dict(spec)}: kind one of {KINDS}, missing {missing},"
                             f" unknown or derived columns {unknown}")  # fmt: skip
        if str(spec[ID]).split(":")[0] not in markets:
            raise ValueError(f"EventSpec {dict(spec)}: its instrument is in no chosen market")


def targets(
    events: Sequence[Mapping[str, Any]], ids: Sequence[str], days: Any, first: Sequence[int],
    last: Sequence[int],
) -> dict[tuple[int, int], Mapping[str, Any]]:  # fmt: skip
    """The injected events on these instruments, by (instrument, ex-date session index)."""
    out: dict[tuple[int, int], Mapping[str, Any]] = {}
    market, dates = ids[0].split(":")[0] if ids else "", np.asarray(days, "datetime64[D]")
    for spec in (s for s in events if str(s[ID]).split(":")[0] == market):
        ex = np.datetime64(_value(spec["ex_date"], pa.date32()), "D")
        e, k = int(np.searchsorted(dates, ex)), ids.index(spec[ID]) if spec[ID] in ids else -1
        if k < 0 or e >= len(dates) or dates[e] != ex or not first[k] < e <= last[k]:
            msg = "ex_date must be a session of its listing after the first (a factor needs one)"
            raise ValueError(f"EventSpec {dict(spec)}: {msg}")
        if (k, e) in out:
            raise ValueError(f"EventSpec {dict(spec)}: two injected events on that day")
        out[k, e] = spec
    return out


def given(
    spec: Mapping[str, Any], ref: float, currency: str, record: dt.date | None,
    declared: dt.date, schema: pa.Schema,
) -> dict[str, Any]:  # fmt: skip
    """An injected event's columns: its terms from the ratio or amount given; for a dividend
    the record date (the next session), its terms known at the announcement and so paid 30
    days after it (4.8 (4)), the resolution body unknown; then the spec's columns as given."""
    if spec["kind"] == "cash_dividend":
        cash = float(spec["cash_per_share"])
        if not 0 < cash < ref:  # else the factor 1 - D / ref is not positive
            raise ValueError(f"EventSpec {dict(spec)}: cash_per_share must be in (0, {ref})")
        paid = {"record_date": record, "pay_date": declared + dt.timedelta(30)}
        out = _cash(cash, ref, currency) | paid
    else:
        if "ratio_num" in spec:
            num, den = int(spec["ratio_num"]), int(spec["ratio_den"])
        else:  # new shares per old one, 1/3 read as 1/3; a bonus issue's extra shares (5.11)
            r = Fraction(str(spec["ratio_new_per_old"])).limit_denominator()
            num, den = (r + (spec["kind"] == "bonus_issue")).as_integer_ratio()
        if num <= 0 or den <= 0:
            raise ValueError(f"EventSpec {dict(spec)}: the ratio must be positive")
        out = _ratio(spec["kind"], num, den, ref)
    return out | {c: _value(v, schema.field(c).type) for c, v in spec.items() if c in schema.names}


def _value(value: Any, kind: pa.DataType) -> Any:
    """An ISO text in a date or timestamp column as a date or a UTC datetime; others as given."""
    if isinstance(value, str) and pa.types.is_date(kind):
        return dt.date.fromisoformat(value)
    if isinstance(value, str) and pa.types.is_timestamp(kind):  # no offset: UTC, never local
        at = dt.datetime.fromisoformat(value)
        return at.replace(tzinfo=dt.UTC) if at.tzinfo is None else at.astimezone(dt.UTC)
    return value
