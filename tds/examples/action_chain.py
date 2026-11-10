"""One instrument's dividend chain resolved at three cutoffs.

Run `uv run python tds/examples/action_chain.py`. Version d1 (100 per share) is announced on
Jan 2; d2 amends it to 120 on Jan 16, after payment."""

import datetime as dt

import pyarrow as pa

from nexusbt_tds.actions import resolve


def at(day: int) -> dt.datetime:
    return dt.datetime(2024, 1, 1, tzinfo=dt.UTC) + dt.timedelta(days=day)


# `from_pylist` takes its columns from the first row's keys, so the base names `revision_of`.
version = {"instrument_id": "SYN1", "kind": "cash_dividend", "ex_date": at(10).date(),
           "ts_effective": at(10), "pay_date": at(12).date(), "pay_date_status": "observed",
           "currency": "KRW", "share_factor": 1.0, "status": "effective",
           "revision_of": None}  # fmt: skip
events = pa.Table.from_pylist([
    version | {"event_id": "d1", "ts_announced": at(1), "cash_per_share": 100.0,
               "price_factor": 0.99},
    version | {"event_id": "d2", "ts_announced": at(15), "cash_per_share": 120.0,
               "price_factor": 0.988, "revision_of": "d1"},
])  # fmt: skip

if __name__ == "__main__":
    widths = (12, 10, 14, 14, 0)
    print(f"{'cutoff':<12}{'revision':<10}{'price_factor':<14}{'share_factor':<14}entitlement")
    for day in (0, 3, 20):
        r = resolve(events, at(day)).chains["d1"]
        e = r.effects
        cash = "-" if e.cash_per_share is None else f"{e.cash_per_share:g} {e.currency}/share"
        row = [str(at(day).date()), r.event_id or "unknown", e.price_factor, e.share_factor, cash]
        print(
            "".join(f"{'-' if v is None else v!s:<{w}}" for v, w in zip(row, widths, strict=True))
        )
