"""The synthetic generator's stage 4.8 (4), on `synth`'s one random stream: share events and
cash dividends, their amendments and cancellations, and the bars they move."""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
import pyarrow as pa

from nexusbt.contracts import ID_COLUMN as ID
from nexusbt.testing._synth_daily import OHLC, PRODUCER, _snap
from nexusbt.testing._synth_events import _cash, _ratio, given
from nexusbt.testing._synth_package import _TS, Table

YEAR = 252  # sessions: small draws listings over 8 such years before its start, to its end
BP = 10_000  # basis points: small's price steps and cash amounts
_D, _S, _F, _I = pa.date32(), pa.string(), pa.float64(), pa.int64()
#: The TDS 5.11 `corporate_actions` columns the generator writes; the others are all null.
CA = pa.schema({
    "event_id": _S, ID: _S, "kind": _S, "ex_date": _D, "ts_effective": _TS, "record_date": _D,
    "declared_date": _D, "pay_date": _D, "pay_date_status": _S, "resolution_date": _D,
    "resolution_body": _S, "ts_announced": _TS, "ts_terms_available": _TS, "ratio_num": _I,
    "ratio_den": _I, "ratio_new_per_old": _F, "cash_per_share": _F, "currency": _S,
    "gross_or_net": _S, "price_factor": _F, "share_factor": _F, "affects": _S,
    "factor_method": _S, "factor_ref_price": _F, "revision_of": _S, "status": _S, "source": _S,
})  # fmt: skip
STATUS = {"revised": "effective", "cancelled": "cancelled"}  # a later version's status
#: 4.8 (4): each share event's yearly rate and its ratios, (new, old) shares; a bonus issue
#: of 0.29 is 129 shares for 100.
SHARE_EVENTS = {
    "split": (0.005, ((2, 1), (5, 1), (7, 1))),
    "reverse_split": (0.002, ((1, 10), (1, 3))),
    "bonus_issue": (0.001, ((129, 100), (21, 20))),
}


def _at(day: dt.date, hour: int, minute: int) -> dt.datetime:
    return dt.datetime(day.year, day.month, day.day, hour, minute, tzinfo=dt.UTC)


def _utc(value: Any) -> dt.datetime:  # a numpy datetime64[us] in UTC
    naive: dt.datetime = value.item()
    return naive.replace(tzinfo=dt.UTC)


def _terms(kind: str, term: int, ref: float, unit: int, currency: str) -> dict[str, Any]:
    """The terms of one version: `term` is a SHARE_EVENTS index, or for any other kind (a
    dividend, a liquidating return of capital) a cash amount in bp of the previous close."""
    if kind == "cash_dividend":  # whole won or cents, at least one
        return _cash(max(1, round(ref * term / BP * unit)) / unit, ref, currency)
    return _ratio(kind, *SHARE_EVENTS[kind][1][term], ref)


def _actions(
    market: str, ids: Sequence[str], first: Sequence[int], last: Sequence[int],
    sessions: Table, bars: dict[str, list[Any]], rng: np.random.Generator,
    mics: Sequence[str | None], injected: Mapping[Key, Mapping[str, Any]], currency: str,
    random: bool = True,
) -> tuple[pa.Table, list[tuple[int, int, str]]]:  # fmt: skip
    """4.8 (4): share events and quarterly cash dividends, ~1 % amended and ~0.5 % cancelled,
    besides the `injected` ones (`EventSpec`); only those without `random` (tiny).

    The latest version of each event moves the raw prices (onto the KR grid again) and volumes
    in `bars` from its ex-date on, and its price factor the cumulative factors (TDS 5.11's A001
    at c = +inf). Returns the rows and each moving event's (instrument, ex-date index, kind).
    """
    moved = []
    days, opens, closes = sessions["session_date"], sessions["ts_open"], sessions["ts_close"]
    keys, drawn, fate = _draw(first, last, rng, set(injected)) if random else ([], {}, {})
    unit = 1 if market == "KR" else 100
    rows, later = [], []
    for x, (k, e) in enumerate(sorted([*keys, *injected])):  # close[e-1] moved already
        spec, fated = injected.get((k, e)), fate.get((k, e))
        kind, term = (spec["kind"], 0) if spec else drawn[k, e]
        a = max(first[k], e - 10)  # announced 10 sessions before
        ref, ex, effective = float(bars["close"][k][e - first[k] - 1]), days[e].item(), opens[e]
        row = dict.fromkeys(CA.names) | {
            "event_id": f"{market}:E{x + 1:06d}", ID: ids[k], "kind": kind, "ex_date": ex,
            "ts_effective": _utc(effective), "declared_date": days[a].item(), "pay_date": ex,
            "pay_date_status": "observed", "ts_announced": _utc(closes[a]), "source": PRODUCER,
            "status": "announced" if fated == "cancelled" else "effective",
        }  # fmt: skip
        midway = _utc(closes[a] + (effective - closes[a]) // 2)  # after the first, before ex
        if spec:
            record = days[e + 1].item() if e + 1 < len(days) else None
            row |= given(spec, ref, currency, record, row["declared_date"], CA)
        else:
            row |= _terms(kind, term, ref, unit, currency)
        if kind == "cash_dividend" and not spec:
            row |= _dividend(row, e, sessions, market == "KR", rng)
        rows.append(row)
        latest = row
        if fated == "revised":
            final, midway = _revise(kind, term, row["pay_date"], midway, rng)
            latest = row | _terms(kind, final, ref, unit, currency)
        terms = row["ts_terms_available"]  # a later version does not publish the amount earlier
        if fated:
            later.append(latest | {"revision_of": row["event_id"], "ts_announced": midway,
                                   "ts_terms_available": terms if terms and terms > midway
                                   else None, "status": STATUS[fated]})  # fmt: skip
        if fated != "cancelled":
            _move(bars, k, e - first[k], latest, kind in SHARE_EVENTS, mics[k])
            moved.append((k, e, kind))
    for x, row in enumerate(later, len(rows) + 1):  # numbered after every first version
        row["event_id"] = f"{market}:E{x:06d}"
    return pa.Table.from_pylist(rows + later, schema=CA), moved


Key = tuple[int, int]  # (instrument, ex-date session index)


def _draw(
    first: Sequence[int], last: Sequence[int], rng: np.random.Generator, skip: set[Key]
) -> tuple[list[Key], dict[Key, tuple[str, int]], dict[Key, str]]:
    """4.8 (4)'s events, (instrument, ex-date index) → (kind, term) in key order, none on a
    `skip` day (an injected event's), and the fate of the amended and cancelled ones."""
    live = [k for k in range(len(first)) if last[k] > first[k]]  # an ex-date needs close[e-1]
    years = sum(last[k] - first[k] + 1 for k in live) / YEAR
    drawn: dict[tuple[int, int], tuple[str, int]] = {}  # (k, ex-date index) → kind, term
    for kind, (rate, ratios) in SHARE_EVENTS.items():
        for _ in range(max(1, round(rate * years)) if live else 0):
            k = live[int(rng.integers(len(live)))]
            e = int(rng.integers(first[k] + 1, last[k], endpoint=True))
            drawn.setdefault((k, e), (kind, int(rng.integers(len(ratios)))))
    for k in rng.choice(live, round(0.3 * len(live)), replace=False).tolist():
        for e in range(first[k] + int(rng.integers(1, 63, endpoint=True)), last[k] + 1, 63):
            drawn.setdefault((k, e), ("cash_dividend", int(rng.integers(20, 150, endpoint=True))))
    for key in skip:  # spec 4.8: no random event on an injected event's day (that instrument)
        drawn.pop(key, None)
    keys, order = sorted(drawn), rng.permutation(len(drawn)).tolist()
    revised, cancelled = max(1, round(0.01 * len(keys))), max(1, round(0.005 * len(keys)))
    shares = [x for x in order if drawn[keys[x]][0] in SHARE_EVENTS][:1]  # a ratio amended too
    order = shares + [x for x in order if x not in shares]
    fate = {keys[x]: "revised" for x in order[:revised]}
    fate |= {keys[x]: "cancelled" for x in order[revised : revised + cancelled]}
    return keys, drawn, fate


def _dividend(
    row: Mapping[str, Any], e: int, sessions: Table, kr: bool, rng: np.random.Generator
) -> dict[str, Any]:
    """A cash dividend's dates, its late terms and `resolution_body` (4.8 (4))."""
    terms = None  # half of KR dividends publish their amount 30~60 days after ex
    if kr and rng.integers(2):
        late = dt.timedelta(int(rng.integers(30, 60, endpoint=True)))
        terms = _utc(sessions["ts_close"][e]) + late
    # #220 Decisions: a year-end dividend (ex-date in Q4) meeting 0.8 / board 0.2, any other
    # board, and 5 % of all of them null
    body = None if rng.integers(100) < 5 else "board"
    if body and row["ex_date"].month >= 10 and rng.integers(10) < 8:
        body = "meeting"
    fixed = terms.date() if terms else row["declared_date"]  # the amount's resolution
    days = sessions["session_date"]
    return {"pay_date": fixed + dt.timedelta(30),  # 5.6.11: a month after it
            "record_date": days[e + 1].item() if e + 1 < len(days) else None,
            "resolution_body": body, "ts_terms_available": terms,
            "resolution_date": fixed if body else None}  # fmt: skip


def _revise(
    kind: str, term: int, paid: dt.date, midway: dt.datetime, rng: np.random.Generator
) -> tuple[int, dt.datetime]:
    """An amendment's term and announcement: the next ratio, or 5~30 bp more, half of those
    announced a week after payment."""
    ratios = SHARE_EVENTS.get(kind, (0, ()))[1]
    if ratios:
        return (term + 1) % len(ratios), midway
    final = term + int(rng.integers(5, 30, endpoint=True))
    return final, _at(paid + dt.timedelta(7), 0, 0) if rng.integers(2) else midway


def _move(
    bars: dict[str, list[Any]], k: int, s: int, version: Mapping[str, Any], share: bool,
    venue: str | None,
) -> None:  # fmt: skip
    """Instrument `k`'s bars from its `s`-th on, moved by one event's factors; an event
    without a factor (`unavailable`) leaves them, and A001 does not compare its session."""
    if version["price_factor"] is None:
        return
    for name in ("open", "high", "low", "close", "cum_factor_total") + (
        ("cum_factor_split",) if share else ()
    ):  # fmt: skip
        bars[name][k][s:] *= version["price_factor"]
        if name in OHLC:
            bars[name][k][s:] = _snap(bars[name][k][s:], bars["session_date"][k][s:], venue)
    bars["volume"][k][s:] = np.round(bars["volume"][k][s:] * version["share_factor"])
