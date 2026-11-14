"""4.4 step 4's exact ratios, checked at every open (TDS 5.11 A010; spec 5.6.1, R3-06, #188)."""

from __future__ import annotations

import datetime as dt
import math
from collections.abc import Collection, Iterator, Sequence
from dataclasses import dataclass
from typing import Any

import pyarrow.parquet as pq

from nexusbt.contracts import ID_COLUMN as ID
from nexusbt.contracts import AccountingDataError, DecimalRatioPolicy
from nexusbt_tds.actions import SPLIT_LIKE
from nexusbt_tds.adjustments import SHARE_KINDS
from nexusbt_tds.keys import listed
from nexusbt_tds.manifest import Manifest

#: The `corporate_actions` columns read (TDS 5.11).
COLUMNS = ("event_id", ID, "kind", "ratio_num", "ratio_den", "ratio_new_per_old",
           "share_factor", "ts_announced", "ts_terms_available", "ts_effective", "revision_of",
           "status")  # fmt: skip
#: 5.6.1's share-changing events, the ones an instrument is excluded for.
EXCLUDING = frozenset({"split", "reverse_split", "bonus_issue", "stock_dividend",
                       "capital_reduction", "rights_issue", "spinoff", "stock_merger",
                       "mixed_merger"})  # fmt: skip
REL_TOL = 1e-12  # A010's own threshold (TDS 5.11), applied at open (4.4-4)


@dataclass(frozen=True, slots=True)
class RatioExclusion:
    """An (instrument, event) 5.6.1 excludes the instrument for, from `visible` = v(e) on
    (`ts_announced`, else `ts_terms_available`, else `ts_effective`) to the end of the run;
    `cause` is `ca_ratio_missing` or `ca_ratio_disagrees` (#188)."""

    instrument_id: str
    event_id: str
    cause: str
    visible: dt.datetime


def check_ratios(
    manifest: Manifest, markets: Collection[str], policy: DecimalRatioPolicy
) -> tuple[tuple[RatioExclusion, ...], int]:
    """4.4-4 on the rows of `markets` (all when none is named): E13 for only one of ratio_num
    and ratio_den, or either <= 0; then each live share event without an exact ratio, or with
    one off its f64 column, follows `policy`. Returns the exclusions and the events read
    literally."""
    rows = list(_rows(manifest, "corporate_actions", COLUMNS))
    if markets:
        market = {r[ID]: r["market"] for r in _rows(manifest, "instruments", (ID, "market"))}
        rows = [r for r in rows if market.get(r[ID]) in markets]
    invalid = [r["event_id"] for r in rows if _malformed(r["ratio_num"], r["ratio_den"])]
    if invalid:
        raise _e13(manifest, invalid, "only one of ratio_num/ratio_den, or either <= 0")
    revised = {r["revision_of"] for r in rows}  # an older version gives way to the latest
    live = [r for r in rows if r["event_id"] not in revised and r["status"] != "cancelled"]
    doubtful = [(r, cause) for r in live if (cause := _doubt(r))]
    if doubtful and policy is DecimalRatioPolicy.REQUIRE_EXACT:
        ids = [r["event_id"] for r, _ in doubtful]
        raise _e13(manifest, ids, "no exact ratio, or one off its f64 column")
    if policy is DecimalRatioPolicy.LITERAL:
        return (), len(doubtful)
    return tuple(RatioExclusion(r[ID], r["event_id"], cause, _visible(r))
                 for r, cause in doubtful), 0  # fmt: skip


def _malformed(num: int | None, den: int | None) -> bool:
    if num is None or den is None:
        return (num is None) != (den is None)
    return num <= 0 or den <= 0


def _doubt(r: dict[str, Any]) -> str | None:
    """5.6.1's cause for a share event's ratio, None when it is exact and agrees."""
    kind, num, den, f64 = r["kind"], r["ratio_num"], r["ratio_den"], _f64(r)
    if kind not in EXCLUDING:
        return None
    if num is None:  # both missing: `_malformed` took one-sided rows
        return "ca_ratio_missing" if kind in SHARE_KINDS or f64 is not None else None
    if f64 is not None and not math.isclose(num / den, f64, rel_tol=REL_TOL):
        return "ca_ratio_disagrees"
    return None


def _f64(r: dict[str, Any]) -> float | None:
    """The f64 column the exact ratio is the quotient of: `share_factor` for split-like kinds,
    else `ratio_new_per_old` (plus the old share for a bonus issue or stock dividend)."""
    if r["kind"] in SPLIT_LIKE and r["share_factor"] is not None:
        return float(r["share_factor"])
    ratio = r["ratio_new_per_old"]
    if ratio is None:
        return None
    return float(1 + ratio if r["kind"] in ("stock_dividend", "bonus_issue") else ratio)


def _visible(r: dict[str, Any]) -> dt.datetime:
    shown: dt.datetime = r["ts_announced"] or r["ts_terms_available"] or r["ts_effective"]
    return shown.astimezone(dt.UTC)  # TDS time columns are UTC (`ts_us`)


def _rows(manifest: Manifest, kind: str, columns: Sequence[str]) -> Iterator[dict[str, Any]]:
    """`columns` of each row of the datasets of `kind`, None where a file lacks the column."""
    for ds in (d for d in manifest.datasets if d.get("kind") == kind):
        for rel, parts in listed(manifest.root, ds):
            path = manifest.root / rel
            present = [c for c in columns if c in pq.read_schema(path).names]
            for row in pq.read_table(path, columns=present).to_pylist():
                yield dict.fromkeys(columns) | parts | row


def _e13(manifest: Manifest, events: Sequence[str], what: str) -> AccountingDataError:
    shown = ", ".join(events[:10]) + (f" and {len(events) - 10} more" if len(events) > 10 else "")
    producer = manifest.data.get("producer")
    name = producer.get("name", "-") if isinstance(producer, dict) else "-"
    snapshot = manifest.data.get("snapshot_id", manifest.root.name)
    return AccountingDataError(
        what=f"{len(events)} corporate action(s) with {what}: {shown}",
        where=f"snapshot {snapshot} corporate_actions",
        why="share quantities are computed from the exact ratio only (5.6.1, TDS 5.11 A010)",
        fix="correct the rows in the producer's package and build it again; a missing or"
        " disagreeing ratio follows [corporate_actions] decimal_ratio (5.6.1)",
        more="spec 4.4 step 4 and 5.6.1; tds check <package> --level full",
        layer=f"data — snapshot {snapshot} / corporate_actions / column ratio_num, ratio_den"
        f" / producer {name}",
    )
