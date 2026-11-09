"""The corporate-action resolver (TDS 5.11 resolution procedure, spec 5.3.3a): one pure function.

`resolve(events, cutoff)` ties `corporate_actions` rows into `revision_of` chains and gives, per
chain, the version known at `cutoff` and its four effects. The engine (`Snapshot.actions`) and
the checker (A001, `cutoff=None` = +inf) both call it. `chain_digest` is the chain hash the L0
cache key holds (spec 5.3.9)."""

from __future__ import annotations

import dataclasses
import datetime as dt
import hashlib
from collections.abc import Mapping
from typing import Any

import pyarrow as pa

from .hash import canonical_json

#: Kinds whose null `share_factor` is built from the ratio columns (TDS 5.11).
SPLIT_LIKE = frozenset(
    {"split", "reverse_split", "stock_dividend", "bonus_issue", "capital_reduction"}
)


class ActionsError(ValueError):
    """The events cannot be tied into chains: a `revision_of` cycle (TDS-A007) or a dangling one."""


@dataclasses.dataclass(frozen=True)
class Effects:
    """Price factor, share factor, entitlement and settlement; None is "none" (TDS 5.11 step 4)."""

    price_factor: float | None = None
    share_factor: float | None = None
    cash_per_share: float | None = None
    currency: str | None = None
    gross_or_net: str | None = None
    new_instrument_id: str | None = None
    ratio_new_per_old: float | None = None
    pay_date: dt.date | None = None
    pay_date_status: str | None = None


@dataclasses.dataclass(frozen=True)
class Resolution:
    """One chain at a cutoff. `event_id` None: no version is known yet ("unknown").

    `effective`: the version has effect (`effective`, or `announced` before its `ts_effective`).
    `stale_announced`: `announced` with `ts_effective <= cutoff`, no effect (engine E30).
    `terms_pending`: known but `ts_terms > cutoff`: price and quantity wait, the entitlement is of
    unknown amount. `late_discovered`: the chain's first version was known after it took effect.
    `effects` are what applies at the cutoff: empty unless effective, amounts empty while pending.
    """

    chain_id: str
    instrument_id: str
    event_id: str | None = None
    status: str | None = None
    ts_effective: dt.datetime | None = None
    ts_known: dt.datetime | None = None
    ts_terms: dt.datetime | None = None
    effective: bool = False
    stale_announced: bool = False
    terms_pending: bool = False
    late_discovered: bool = False
    effects: Effects = Effects()


@dataclasses.dataclass(frozen=True)
class ResolvedActions:
    chains: Mapping[str, Resolution]  # by chain id (the root's `event_id`), ascending


Row = dict[str, Any]


def _ts_known(row: Row) -> dt.datetime:
    times = [t for t in (row.get("ts_announced"), row.get("ts_terms_available")) if t is not None]
    effective: dt.datetime = row["ts_effective"]
    return min(times) if times else effective


def _ts_terms(row: Row) -> dt.datetime:
    terms: dt.datetime | None = row.get("ts_terms_available")
    return terms if terms is not None else _ts_known(row)


def _share_factor(row: Row) -> float | None:
    if row.get("share_factor") is not None:
        return float(row["share_factor"])
    if row["kind"] not in SPLIT_LIKE:
        return None  # never the reciprocal of the price factor
    num, den, r = row.get("ratio_num"), row.get("ratio_den"), row.get("ratio_new_per_old")
    if num is not None and den is not None:
        return float(num / den)
    if r is None:
        return None
    return float(1 + r if row["kind"] in ("stock_dividend", "bonus_issue") else r)


def _effects(row: Row) -> Effects:
    fields = {f.name: row.get(f.name) for f in dataclasses.fields(Effects)}
    return Effects(**(fields | {"share_factor": _share_factor(row)}))


def _chains(rows: list[Row]) -> dict[str, list[Row]]:
    by_id = {r["event_id"]: r for r in rows}
    chains: dict[str, list[Row]] = {}
    for row in rows:
        seen, node = {row["event_id"]}, row
        while (parent := node.get("revision_of")) is not None:
            if parent in seen:
                raise ActionsError(f"TDS-A007: `revision_of` cycle through `{parent}`")
            if parent not in by_id:
                raise ActionsError(f"`{node['event_id']}` revises no event `{parent}`")
            seen.add(parent)
            node = by_id[parent]
        chains.setdefault(node["event_id"], []).append(row)
    return {k: sorted(v, key=lambda r: r["event_id"]) for k, v in sorted(chains.items())}


def _resolve(chain_id: str, versions: list[Row], cutoff: dt.datetime | None) -> Resolution:
    first = min(versions, key=_ts_known)  # stable: ties keep ascending `event_id`
    known = [r for r in versions if cutoff is None or _ts_known(r) <= cutoff]
    out = Resolution(chain_id, first["instrument_id"])
    if not known:
        return out
    row = max(reversed(known), key=_ts_known)  # ties: the last in ascending `event_id`
    after = cutoff is None or row["ts_effective"] <= cutoff
    pending = cutoff is not None and _ts_terms(row) > cutoff
    effective = row["status"] == "effective" or (row["status"] == "announced" and not after)
    effects = _effects(row) if effective else Effects()
    if pending:
        amounts = ("price_factor", "share_factor", "cash_per_share", "ratio_new_per_old")
        effects = dataclasses.replace(effects, **dict.fromkeys(amounts))
    return dataclasses.replace(
        out, event_id=row["event_id"], status=row["status"], ts_effective=row["ts_effective"],
        ts_known=_ts_known(row), ts_terms=_ts_terms(row), effective=effective,
        stale_announced=row["status"] == "announced" and after, terms_pending=pending,
        late_discovered=_ts_known(first) > first["ts_effective"], effects=effects,
    )  # fmt: skip


def resolve(events: pa.Table, cutoff: dt.datetime | None) -> ResolvedActions:
    """Each chain's version known at `cutoff` (None: +inf, the whole package) and its effects."""
    chains = _chains(events.to_pylist())
    return ResolvedActions({k: _resolve(k, v, cutoff) for k, v in chains.items()})


def changed_chains(
    before: ResolvedActions, after: ResolvedActions
) -> list[tuple[str, Resolution | None, Resolution | None]]:
    """Chains whose version or applied effects differ between two cutoffs (correction entries)."""
    pairs = (
        (c, before.chains.get(c), after.chains.get(c)) for c in {*before.chains, *after.chains}
    )
    return sorted((c, a, b) for c, a, b in pairs if a != b)


def _plain(value: Any) -> Any:
    return value.isoformat() if isinstance(value, dt.date) else value


def chain_digest(events: pa.Table, year_end: dt.date) -> str:
    """sha256 of every version of each chain with a version effective on or before `year_end`.

    `events` are one market's rows. Each version gives `event_id`, `ts_known`, `ts_terms`,
    `status`, `ts_effective` and its four effects, so a middle version's amendment or a changed
    publication time changes the digest (spec 5.3.9, INV-05)."""
    chains = []
    for chain_id, versions in _chains(events.to_pylist()).items():
        if all(r["ex_date"] > year_end for r in versions):
            continue
        entries = [
            {"event_id": r["event_id"], "status": r["status"], "ts_known": _plain(_ts_known(r)),
             "ts_terms": _plain(_ts_terms(r)), "ts_effective": _plain(r["ts_effective"]),
             "effects": {k: _plain(v) for k, v in dataclasses.asdict(_effects(r)).items()}}
            for r in versions
        ]  # fmt: skip
        chains.append({"chain_id": chain_id, "versions": entries})
    return hashlib.sha256(canonical_json(chains).encode("utf-8")).hexdigest()
