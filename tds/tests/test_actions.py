"""TDS 5.11 / spec 5.3.3a: the corporate-action resolver at a knowledge cutoff (T0.15a)."""

from __future__ import annotations

import datetime as dt
import runpy
from pathlib import Path
from typing import Any

import pyarrow as pa
import pytest

from nexusbt_tds.actions import ActionsError, Effects, chain_digest, changed_chains, resolve

TS = pa.timestamp("us", "UTC")
TYPES = {
    "event_id": pa.string(), "instrument_id": pa.string(), "kind": pa.string(),
    "ex_date": pa.date32(), "ts_effective": TS, "pay_date": pa.date32(),
    "pay_date_status": pa.string(), "ts_announced": TS, "ts_terms_available": TS,
    "ratio_num": pa.int64(), "ratio_den": pa.int64(), "ratio_new_per_old": pa.float64(),
    "cash_per_share": pa.float64(), "currency": pa.string(), "price_factor": pa.float64(),
    "share_factor": pa.float64(), "revision_of": pa.string(), "status": pa.string(),
}  # fmt: skip


def day(n: int) -> dt.datetime:
    return dt.datetime(2024, 1, 1, tzinfo=dt.UTC) + dt.timedelta(days=n)


def ev(event_id: str, inst: str, kind: str, announced: int | None, **kw: Any) -> dict[str, Any]:
    row = {"event_id": event_id, "instrument_id": inst, "kind": kind, "ex_date": day(10).date(),
           "ts_effective": day(10), "pay_date_status": "missing", "status": "effective",
           "ts_announced": None if announced is None else day(announced)}  # fmt: skip
    return row | kw


def table(*rows: dict[str, Any]) -> pa.Table:
    return pa.Table.from_pylist(list(rows), schema=pa.schema(TYPES.items()))


def split(eid: str, r: int, announced: int, **kw: Any) -> dict[str, Any]:
    return ev(eid, "A", "split", announced, ratio_num=r, ratio_den=1, price_factor=1 / r, **kw)


def cash(eid: str, inst: str, amount: float, announced: int | None, **kw: Any) -> dict[str, Any]:
    return ev(eid, inst, "cash_dividend", announced, cash_per_share=amount, price_factor=0.99,
              share_factor=1.0, **kw)  # fmt: skip


EVENTS = table(
    split("a1", 2, 1),
    split("a2", 3, 5, revision_of="a1"),  # amended split ratio
    cash("b1", "B", 100.0, 1),
    cash("b2", "B", 100.0, 5, revision_of="b1", status="cancelled"),  # cancelled dividend
    cash("c1", "C", 100.0, 1, pay_date=day(12).date(), pay_date_status="observed"),
    cash("c2", "C", 120.0, 15, revision_of="c1", pay_date=day(12).date()),  # after payment
    split("d1", 2, 1, instrument_id="D"),  # split + cash dividend on the same day
    cash("d2", "D", 50.0, 1),
    ev("e1", "E", "rights_issue", 1, price_factor=0.95, share_factor=1.0),  # lapsed right
    ev("f1", "F", "other", 1),  # no factor
)
# chain: (event, price factor, share factor, cash) before publication, after v1, after amendment
EXPECTED: dict[str, list[tuple[str | None, float | None, float | None, float | None]]] = {
    "a1": [(None, None, None, None), ("a1", 0.5, 2.0, None), ("a2", 1 / 3, 3.0, None)],
    "b1": [(None, None, None, None), ("b1", 0.99, 1.0, 100.0), ("b2", None, None, None)],
    "c1": [(None, None, None, None), ("c1", 0.99, 1.0, 100.0), ("c2", 0.99, 1.0, 120.0)],
    "d1": [(None, None, None, None), ("d1", 0.5, 2.0, None), ("d1", 0.5, 2.0, None)],
    "d2": [(None, None, None, None), ("d2", 0.99, 1.0, 50.0), ("d2", 0.99, 1.0, 50.0)],
    "e1": [(None, None, None, None), ("e1", 0.95, 1.0, None), ("e1", 0.95, 1.0, None)],
    "f1": [(None, None, None, None), ("f1", None, None, None), ("f1", None, None, None)],
}


def test_resolver_at_cutoffs() -> None:
    at = [resolve(EVENTS, day(n)) for n in (0, 3, 20)]
    for chain, rows in EXPECTED.items():
        got = [
            (r.event_id, r.effects.price_factor, r.effects.share_factor, r.effects.cash_per_share)
            for r in (a.chains[chain] for a in at)
        ]
        assert got == rows, chain
    assert (at[2].chains["b1"].effective, at[2].chains["b1"].status) == (False, "cancelled")
    assert at[2].chains["c1"].effects.pay_date == day(12).date()
    assert resolve(EVENTS, None) == at[2]  # +inf: the whole package's knowledge (A001)
    assert [c for c, _, _ in changed_chains(at[1], at[2])] == ["a1", "b1", "c1"]


def test_share_factor_explicit_not_inferred() -> None:
    events = table(
        ev("r", "A", "rights_issue", 1, price_factor=0.9),  # no share_factor: not 1/0.9
        ev("s", "B", "split", 1, ratio_num=5, ratio_den=2, ratio_new_per_old=9.0),
        ev("x", "C", "split", 1, ratio_num=5, ratio_den=2, share_factor=4.0),  # explicit wins
        ev("b", "D", "stock_dividend", 1, ratio_new_per_old=0.05),  # b -> 1 + b
        ev("m", "E", "stock_merger", 1, ratio_new_per_old=0.4, price_factor=1.0),
    )
    got = {k: v.effects.share_factor for k, v in resolve(events, day(20)).chains.items()}
    assert got == {"r": None, "s": 2.5, "x": 4.0, "b": 1.05, "m": None}


def test_revision_cycle_A007() -> None:
    with pytest.raises(ActionsError, match="TDS-A007"):
        resolve(table(split("p", 2, 1, revision_of="q"), split("q", 3, 2, revision_of="p")), None)
    with pytest.raises(ActionsError, match="TDS-A007"):
        resolve(table(split("p", 2, 1, revision_of="p")), None)
    with pytest.raises(ActionsError, match="no event `z`"):
        resolve(table(split("p", 2, 1, revision_of="z")), None)


def test_late_terms_revision_visible_at_ex_date() -> None:
    late = table(cash("t", "A", 100.0, 1, ts_terms_available=day(15)))
    at_ex = resolve(late, day(10)).chains["t"]
    assert (at_ex.event_id, at_ex.effective, at_ex.terms_pending) == ("t", True, True)
    assert (at_ex.effects.cash_per_share, at_ex.effects.price_factor) == (None, None)
    after = resolve(late, day(16)).chains["t"]
    assert (after.terms_pending, after.effects.cash_per_share) == (False, 100.0)
    assert (after.ts_known, after.ts_terms) == (day(1), day(15))


def test_existence_time_ignores_effective_when_announced() -> None:
    events = table(cash("k", "A", 100.0, 12), cash("n", "B", 100.0, None))  # n: no times
    assert resolve(events, day(11)).chains["k"].event_id is None  # not at ts_effective (day 10)
    assert resolve(events, day(12)).chains["k"].event_id == "k"
    assert resolve(events, day(10)).chains["n"].ts_known == day(10)  # both null: ts_effective


def test_late_discovered_event_flagged() -> None:
    events = table(cash("late", "A", 100.0, 12), cash("on_time", "B", 100.0, 1))
    chains = resolve(events, day(20)).chains
    assert (chains["late"].late_discovered, chains["on_time"].late_discovered) == (True, False)


def test_announced_status_has_effect_until_its_effective_time() -> None:
    events = table(cash("s", "A", 100.0, 1, status="announced"))
    before, after = (resolve(events, day(n)).chains["s"] for n in (9, 10))
    assert (before.effective, before.stale_announced, before.effects.cash_per_share) == (
        True, False, 100.0)  # fmt: skip
    assert (after.effective, after.stale_announced, after.effects) == (False, True, Effects())


def test_chain_digest_includes_all_revisions_and_times() -> None:
    rows = [
        split("a1", 2, 1),
        split("a2", 3, 5, revision_of="a1"),
        split("a3", 4, 6, revision_of="a2"),
    ]
    end = dt.date(2024, 12, 31)
    base = chain_digest(table(*rows), end)
    assert chain_digest(table(*reversed(rows)), end) == base
    middle = [rows[0], split("a2", 5, 5, revision_of="a1"), rows[2]]
    assert chain_digest(table(*middle), end) != base
    timed = [rows[0], rows[1] | {"ts_terms_available": day(7)}, rows[2]]
    assert chain_digest(table(*timed), end) != base
    later = cash("z", "B", 1.0, 1, ex_date=dt.date(2025, 3, 3), ts_effective=day(430))
    assert chain_digest(table(*rows, later), end) == base
    assert chain_digest(table(*rows, later), dt.date(2025, 12, 31)) != base


def test_example_prints_table(capsys: pytest.CaptureFixture[str]) -> None:
    runpy.run_path(
        str(Path(__file__).parents[1] / "examples" / "action_chain.py"), run_name="__main__"
    )
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].split() == ["cutoff", "revision", "price_factor", "share_factor", "entitlement"]
    assert [line.split()[1] for line in lines[1:]] == ["unknown", "d1", "d2"]
