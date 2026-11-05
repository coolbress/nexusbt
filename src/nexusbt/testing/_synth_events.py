"""Event injection for the synthetic generator (spec 4.8 `EventSpec`), and the terms of a
corporate action that both injected and random events take.

An `EventSpec` is a dict of TDS column names plus a `"dataset"` key. It injects
`corporate_actions` rows, `delistings` rows and full-day KR halts as `tradability_daily` rows
(#300); `fundamentals_*` are not generated until M2.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator, Mapping, Sequence
from fractions import Fraction
from typing import Any

import numpy as np
import pyarrow as pa

from nexusbt.contracts import ID_COLUMN as ID

SHARE_KINDS = ("split", "reverse_split", "bonus_issue")
KINDS = (*SHARE_KINDS, "cash_dividend")
M2 = ("fundamentals_events", "fundamentals_state")
NEEDS = {"cash_dividend": ("cash_per_share",)}  # a share event needs a ratio, checked below
KEYS = ("dataset", ID, "kind", "ex_date")
#: Columns the generator derives from the terms and the version chain; given ones could
#: contradict them and break A001, so a spec may not set them.
DERIVED = frozenset({"event_id", "revision_of", "status", "price_factor", "share_factor",
                     "affects", "factor_method", "factor_ref_price"})  # fmt: skip
#: #300 Decisions: a delisting's columns a spec may give; 4.8 (6) fills those it leaves out,
#: and the others (its id, last trading day and reference price) follow the bars.
EXIT_GIVEN = frozenset({ID, "exit_date", "exit_value_status", "delist_type", "ret_observed",
                        "ret_policy", "ts_exit_known", "ts_value_available",
                        "pay_date"})  # fmt: skip
EXITS = ("observed", "estimated", "unobserved")  # TDS 5.13 `exit_value_status`
LIMITS = frozenset({"limit_up_close", "limit_down_close", "locked_up", "locked_down",
                    "admin_status"})  # fmt: skip
Days = set[tuple[int, int]]  # (instrument, session index) pairs


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


def exit_value(
    status: str, policy_left: bool, rng: np.random.Generator
) -> tuple[float | None, float | None]:
    """4.8 (6)'s `ret_observed` and `ret_policy`, for a drawn exit and the columns an injected
    one leaves out: an observed -50 %~+30 %, an estimate -50 %~0, and an unobserved -30 %, but
    null for the first, so a holding meets 5.6.13's E13."""
    if status == "observed":
        ret = int(rng.integers(-5000, 3000, endpoint=True)) / 10_000
        return ret, ret
    if status == "estimated":
        return None, int(rng.integers(-5000, 0, endpoint=True)) / 10_000
    return None, None if policy_left else -0.3


def check(
    events: Sequence[Mapping[str, Any]], markets: Sequence[str], schema: pa.Schema,
    tiny: bool = False,
) -> None:  # fmt: skip
    """Refuse an `EventSpec` the generator cannot inject, before anything is written."""
    for spec in events:
        name, kind = spec.get("dataset"), spec.get("kind")
        if name in M2:
            raise NotImplementedError(f"EventSpec dataset {name!r}: not generated until M2")
        if name == "delistings":
            _exit(spec)
        elif name == "tradability_daily":
            _halt(spec, tiny)
        elif name == "corporate_actions":
            _action(spec, kind, schema)
        else:
            raise ValueError(f"EventSpec dataset {name!r}: one of the spec 4.8 datasets")
        if str(spec[ID]).split(":")[0] not in markets:
            raise ValueError(f"EventSpec {dict(spec)}: its instrument is in no chosen market")


def _exit(spec: Mapping[str, Any]) -> None:
    """A delisting gives its instrument and exit, and may give EXIT_GIVEN's columns (#300)."""
    missing = [c for c in (ID, "exit_date") if c not in spec]
    derived = sorted(set(spec) - EXIT_GIVEN - {"dataset"})
    if missing or derived:
        raise ValueError(f"EventSpec {dict(spec)}: missing {missing}; a delisting gives only"
                         f" {sorted(EXIT_GIVEN)}, not derived or unknown {derived}")  # fmt: skip
    if spec.get("delist_type") == "liquidation":
        raise ValueError(f"EventSpec {dict(spec)}: a liquidating distribution is not injected")
    if spec.get("exit_value_status", EXITS[0]) not in EXITS:
        raise ValueError(f"EventSpec {dict(spec)}: exit_value_status one of {EXITS}")


def _halt(spec: Mapping[str, Any], tiny: bool) -> None:
    """A `tradability_daily` row injects a full-day KR halt only (#300)."""
    if tiny:
        raise NotImplementedError(f"EventSpec {dict(spec)}: tiny writes no tradability_daily"
                                  " yet (4.8 (5))")  # fmt: skip
    if set(spec) & LIMITS:
        raise NotImplementedError(f"EventSpec {dict(spec)}: limit closes and admin_status are"
                                  " not injected yet, only full-day halts")  # fmt: skip
    wrong = sorted(set(spec) - {"dataset", ID, "session_date", "halted_full_day"})
    if wrong or spec.get("halted_full_day") is not True or "session_date" not in spec:
        raise ValueError(f"EventSpec {dict(spec)}: a halt gives {ID}, session_date and"
                         f" halted_full_day = True, not derived or unknown {wrong}")  # fmt: skip
    if not str(spec.get(ID)).startswith("KR:"):
        raise ValueError(f"EventSpec {dict(spec)}: halts are on KR sessions only (4.8 (5))")


def _action(spec: Mapping[str, Any], kind: Any, schema: pa.Schema) -> None:
    """A corporate action gives its kind, ex-date and terms, and no DERIVED column."""
    missing = [c for c in (*KEYS, *NEEDS.get(str(kind), ())) if c not in spec]
    if kind in SHARE_KINDS and not ({"ratio_num", "ratio_den"} <= set(spec)
                                    or "ratio_new_per_old" in spec):  # fmt: skip
        missing.append("ratio_num and ratio_den, or ratio_new_per_old")
    unknown = sorted(set(spec) - set(schema.names) - {"dataset"} | set(spec) & DERIVED)
    if kind not in KINDS or missing or unknown:
        raise ValueError(f"EventSpec {dict(spec)}: kind one of {KINDS}, missing {missing},"
                         f" unknown or derived columns {unknown}")  # fmt: skip


def targets(
    events: Sequence[Mapping[str, Any]], ids: Sequence[str], days: Any, first: Sequence[int],
    last: Sequence[int],
) -> dict[tuple[int, int], Mapping[str, Any]]:  # fmt: skip
    """The injected events on these instruments, by (instrument, ex-date session index)."""
    out: dict[tuple[int, int], Mapping[str, Any]] = {}
    for spec, k, e in _on(events, "corporate_actions", "ex_date", ids, days):
        if k < 0 or e is None or not first[k] < e <= last[k]:
            msg = "ex_date must be a session of its listing after the first (a factor needs one)"
            raise ValueError(f"EventSpec {dict(spec)}: {msg}")
        if (k, e) in out:
            raise ValueError(f"EventSpec {dict(spec)}: two injected events on that day")
        out[k, e] = spec
    return out


def exits(
    events: Sequence[Mapping[str, Any]], ids: Sequence[str], days: Any, first: Sequence[int],
    last: list[int],
) -> dict[int, Mapping[str, Any]]:  # fmt: skip
    """The injected delistings on these instruments, by instrument. Each sets its listing's
    `last` session to the one before its exit, as 4.8 (6)'s exits are."""
    out: dict[int, Mapping[str, Any]] = {}
    for spec, k, x in _on(events, "delistings", "exit_date", ids, days):
        if k < 0 or x is None or x <= first[k]:
            raise ValueError(f"EventSpec {dict(spec)}: exit_date must be a session of the period"
                             " after its listing's first")  # fmt: skip
        if k in out:
            raise ValueError(f"EventSpec {dict(spec)}: two injected exits")
        last[k], out[k] = x - 1, spec
    return out


def halts(
    events: Sequence[Mapping[str, Any]], ids: Sequence[str], days: Any, first: Sequence[int],
    last: Sequence[int], moved: Sequence[tuple[int, int, str]],
) -> Days:  # fmt: skip
    """The injected full-day halts on these instruments, (instrument, session index). None
    may fall where 4.8 (5) keeps halts off; an ex-date itself may be halted."""
    before, out = {(k, e - 1) for k, e, _ in moved}, set()
    for spec, k, d in _on(events, "tradability_daily", "session_date", ids, days):
        if k < 0 or d is None or not first[k] <= d <= last[k]:
            raise ValueError(f"EventSpec {dict(spec)}: session_date must be a session of its"
                             " listing")  # fmt: skip
        rule = ("the session before an ex-date, whose close the factor uses" if (k, d) in before
                else "a listing's last session" if d == last[k] else None)  # fmt: skip
        if rule or (k, d) in out:
            why = f"4.8 (5) keeps {rule} free of halts" if rule else "two injected halts"
            raise ValueError(f"EventSpec {dict(spec)}: {why}")
        out.add((k, d))
    return out


def _on(
    events: Sequence[Mapping[str, Any]], dataset: str, column: str, ids: Sequence[str],
    days: Any,
) -> Iterator[tuple[Mapping[str, Any], int, int | None]]:  # fmt: skip
    """Each spec of `dataset` in this market with its instrument's index (-1 when it is not
    one of `ids`) and the index of the session on its `column` date (None when it is none)."""
    market, dates = ids[0].split(":")[0] if ids else "", np.asarray(days, "datetime64[D]")
    for spec in events:
        if spec["dataset"] == dataset and str(spec[ID]).split(":")[0] == market:
            day = np.datetime64(_value(spec[column], pa.date32()), "D")
            x = int(np.searchsorted(dates, day))
            yield (spec, ids.index(spec[ID]) if spec[ID] in ids else -1,
                   x if x < len(dates) and dates[x] == day else None)  # fmt: skip


def columns(spec: Mapping[str, Any], schema: pa.Schema) -> dict[str, Any]:
    """A spec's columns of `schema`, ISO texts read as dates and times."""
    return {c: _value(v, schema.field(c).type) for c, v in spec.items() if c in schema.names}


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
    return out | columns(spec, schema)


def _value(value: Any, kind: pa.DataType) -> Any:
    """An ISO text in a date or timestamp column as a date or a UTC datetime; others as given."""
    if isinstance(value, str) and pa.types.is_date(kind):
        return dt.date.fromisoformat(value)
    if isinstance(value, str) and pa.types.is_timestamp(kind):  # no offset: UTC, never local
        at = dt.datetime.fromisoformat(value)
        return at.replace(tzinfo=dt.UTC) if at.tzinfo is None else at.astimezone(dt.UTC)
    return value
