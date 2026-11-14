"""The synthetic generator's stage 4.8 (6), on `synth`'s one random stream: a `delistings` row
for every listing that ends in the period, and the liquidating distributions before some."""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
import pyarrow as pa

from nexusbt.contracts import ID_COLUMN as ID
from nexusbt.testing import _synth_events as ev
from nexusbt.testing._synth_actions import _D, _F, _S, CA, _terms, _utc
from nexusbt.testing._synth_daily import PRODUCER
from nexusbt.testing._synth_package import _TS, Table

#: The TDS 5.13 `delistings` columns the generator writes.
DL = pa.schema({
    "delisting_id": _S, ID: _S, "last_trading_date": _D, "exit_date": _D, "ts_exit_known": _TS,
    "delist_type": _S, "ref_date": _D, "ref_price": _F, "exit_value_status": _S,
    "ret_observed": _F, "ret_observed_includes_distributions": pa.bool_(),
    "ts_value_available": _TS, "ret_policy": _F, "ret_lo": _F, "ret_hi": _F, "policy_id": _S,
    "pay_date": _D,
})  # fmt: skip
#: 4.8 (6): the exit value status by a draw from 0 to 9, and the type each status gets.
EXIT = ("observed",) * 5 + ("estimated",) * 3 + ("unobserved",) * 2
EXIT_TYPE = {"observed": "acquisition_cash", "estimated": "performance", "unobserved": "unknown"}


def _delistings(
    market: str, ids: Sequence[str], first: Sequence[int], last: Sequence[int],
    sessions: Table, bars: dict[str, list[Any]], rng: np.random.Generator,
    injected: Mapping[int, Mapping[str, Any]], currency: str,
) -> tuple[pa.Table, pa.Table, list[dt.date | None]]:  # fmt: skip
    """4.8 (6): a `delistings` row for every listing that ends in the period, with 4.8 (4)'s
    liquidating distribution on ~10 % of those not `injected` (whose columns replace drawn ones).

    Returns those rows, the distributions' `corporate_actions` rows and each `delisted_on`.
    """
    days, opens, closes = sessions["session_date"], sessions["ts_open"], sessions["ts_close"]
    gone = [k for k in range(len(ids)) if last[k] < len(days) - 1]
    room = [k for k in gone if last[k] + 2 < len(days) and k not in injected]  # for the ex-date
    count = min(len(room), max(1, round(0.1 * len(gone))))
    paid = set(rng.choice(room, count, replace=False).tolist()) if count else set()
    unit = 1 if market == "KR" else 100
    delisted: list[dt.date | None] = [None] * len(ids)
    rows, payouts, policy_left = [], [], True  # the first unobserved row keeps ret_policy null
    for n, k in enumerate(gone, 1):
        x, ref = last[k] + (2 if k in paid else 1), float(bars["close"][k][-1])  # exit session
        spec = injected.get(k, {})
        status = spec.get("exit_value_status") or EXIT[int(rng.integers(10))]
        ret, policy = ev.exit_value(status, policy_left, rng)
        policy_left = policy_left and status != "unobserved"
        known = None  # half of the observed values publish 20~90 days after the exit
        if status == "observed" and rng.integers(2):
            known = _utc(opens[x]) + dt.timedelta(int(rng.integers(20, 90, endpoint=True)))
        out: dt.date = days[x].item()
        delisted[k], told = out, max(first[k], x - 10)  # known 10 sessions before
        rows.append({
            "delisting_id": f"{market}:D{n:05d}", ID: ids[k], "exit_date": out,
            "last_trading_date": days[last[k]].item(), "ts_exit_known": _utc(closes[told]),
            "delist_type": "liquidation" if k in paid else EXIT_TYPE[status],
            "ref_date": days[last[k]].item(), "ref_price": ref, "exit_value_status": status,
            "ret_observed": ret, "ts_value_available": known, "ret_policy": policy,
            "ret_observed_includes_distributions": bool(rng.integers(2)) if k in paid else None,
            "ret_lo": -1.0, "ret_hi": 0.0, "policy_id": "exit-value-v1",
            "pay_date": out + dt.timedelta(30) if status == "observed" else None,
        } | ev.columns(spec, DL))  # fmt: skip
        if k in paid:  # a return of capital of 20~80 % of the last close, ex-date the next day
            ex = days[last[k] + 1].item()
            payouts.append(dict.fromkeys(CA.names) | {
                "event_id": f"{market}:L{n:05d}", ID: ids[k], "kind": "return_of_capital",
                "ex_date": ex, "ts_effective": _utc(opens[last[k] + 1]), "pay_date": ex
                + dt.timedelta(30), "declared_date": days[told].item(), "status": "effective",
                "pay_date_status": "observed", "ts_announced": _utc(closes[told]),
                "source": PRODUCER,
            } | _terms("cash_dividend", int(rng.integers(2000, 8000, endpoint=True)), ref,
                       unit, currency))  # fmt: skip
    return (pa.Table.from_pylist(rows, schema=DL), pa.Table.from_pylist(payouts, schema=CA),
            delisted)  # fmt: skip
