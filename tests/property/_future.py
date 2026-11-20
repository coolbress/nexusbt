"""P-FUT's earlier snapshot (spec 8.3): a copy of a synthetic package with the data after τ
deleted, cut in place (#254, ③a; its test, `test_P_FUT_pipeline`, is ③b's).

Spec 8.3 reads: "between a snapshot with the data after time τ deleted (rows with
`ts_available > τ`: bars, event versions (`ts_known > τ`), delisting recoveries, FX,
fundamentals) and the original snapshot, …". The list is read as examples (#254's Decisions,
2026-11-20): every dataset with an availability instant (TDS 6.2: a manifest `availability`,
or `params.availability_by_column`) loses its rows first known after τ. A row's instant:

- a rule: `ts_end` (null: its session's close), `session_open`, `session_close`;
- a column (`{"column": c}`): `c`; `instrument_symbols`' null falls back to the open of
  `valid_from`'s session (TDS 6.2);
- `corporate_actions`: the existence instant, the earlier of `ts_announced` and the terms
  column, else the effect column, as the generator's `behind` cuts (spec 4.8); a row known by
  τ whose terms come later stays, terms and all, so P-FUT sees whether the resolver hides an
  amount before its terms time (5.3.3a);
- `delistings`: the exit column (null: the open of `exit_date`'s session); an exit known by τ
  whose value comes later stays, value and all;
- `tradability_daily` (`params.availability_by_column`): its session's close, the last of its
  groups. Its pre-open group is known at the open, but a package holds no row of a session
  after its market's watermark (TDS-M016), and the watermark as of τ is the last session
  closed by τ.

A row with no instant (a null with no fallback) stays. Datasets with no availability instant
are left whole, rows after τ included: `instruments`, `instrument_xref`, `calendar_sessions`
and `market_rules`. `instruments` is an after-the-fact static table (spec 5.1's table: "a
static table … `delisted_on`, `last_session` and `name` are not exposed as decision inputs"),
and a producer's package fills its columns the same way; keeping them is what lets P-FUT see
that the engine does not lean on them. Two columns are the exception, for the package to stay
whole: `delisted_on` is emptied for an instrument whose `delistings` row was cut (TDS checks
an exit against it; the generator's `behind` does the same), and `last_session` where it lies
after its market's watermark as of τ, the instrument still trading then (TDS-D001 expects a
bar on every session up to a set `last_session`).

The package's metadata is set as of τ: each market's watermark (TDS 3.8) is its last session
closed by τ, every dataset's `processed_through_session` no later than it, and the coverage of
each dataset that lost rows is read again from its files as the generator writes it.

Files are rewritten only where rows go; a file left with no row is removed with its manifest
entry. Row counts and the hashes are rewritten (`write_hashes`). A τ at or after the package's
end changes nothing, not a byte.
"""

from __future__ import annotations

import datetime as dt
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from nexusbt.testing import _synth_package as pk
from nexusbt_tds.hash import write_hashes

#: The datasets the cut leaves whole: no availability instant in TDS 6.2.
TIMELESS = frozenset({"instruments", "instrument_xref", "calendar_sessions", "market_rules"})


def cut_after(root: Path, tau: dt.datetime) -> dict[str, int]:
    """Delete, in the package at `root`, every row first known after `tau` (an aware
    instant); return the rows deleted per dataset."""
    manifest = json.loads((root / "tds.json").read_text(encoding="utf-8"))
    entries = {d["name"]: d for d in manifest["datasets"]}
    instruments = _read(root, entries["instruments"])
    sessions = _sessions(root, entries["calendar_sessions"], instruments)
    marks = _through(manifest, root, entries, tau)
    deleted: dict[str, int] = {}
    exits_cut: set[str] = set()
    for name, entry in entries.items():
        if name in TIMELESS or not (entry.get("availability") or _by_column(entry)):
            continue
        kept = []
        for f in entry["files"]:
            rows = pq.read_table(part := root / f["path"])
            keep = pa.array([t is None or t <= tau for t in _instants(name, entry, rows, sessions)])
            deleted[name] = deleted.get(name, 0) + rows.num_rows - pc.sum(keep).as_py()
            if name == "delistings":
                exits_cut |= set(rows.filter(pc.invert(keep))["instrument_id"].to_pylist())
            if pc.all(keep).as_py():
                kept.append(f)
            elif (left := rows.filter(keep)).num_rows:
                pq.write_table(left, part)
                kept.append(f | {"bytes": part.stat().st_size, "rows": left.num_rows})
            else:
                part.unlink()
        entry["files"] = kept
    if not any(deleted.values()) and not any(marks.values()):
        return deleted  # nothing after τ: the package is left as it was, byte for byte
    for name, entry in entries.items():  # every dataset is processed through τ's watermark
        _cover(root, entry, marks, again=bool(deleted.get(name)))
    _as_of(root, entries["instruments"], exits_cut, manifest["markets"], marks)
    for market, day in marks.items():
        manifest["markets"][market] |= day
    (root / "tds.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    write_hashes(root)
    return deleted


def _through(manifest: Any, root: Path, entries: Any, tau: dt.datetime) -> dict[str, Any]:
    """Each market's watermark as of `tau` (TDS 3.8): its last session closed by then."""
    calendar = _read(root, entries["calendar_sessions"]).to_pylist()
    found: dict[str, Any] = {}
    for market, about in manifest["markets"].items():
        closed = [r for r in calendar
                  if r["calendar_id"] == about["calendar_id"] and r["ts_close"] <= tau]  # fmt: skip
        last = max(closed, key=lambda r: r["session_date"])
        mark = min(last["session_date"].isoformat(), about["complete_through_session"])
        if mark == about["complete_through_session"]:
            found[market] = {}  # τ at or after the package's end: the watermark stays
            continue
        found[market] = {"complete_through_session": mark,
                         "complete_through": f"{last['ts_close']:%Y-%m-%dT%H:%M:%SZ}"}  # fmt: skip
    return found


def _cover(root: Path, entry: dict[str, Any], through: Mapping[str, Any], *, again: bool) -> None:
    """`entry`'s `coverage` (TDS 4.3): read again from its files when it lost rows (`again`),
    as the generator writes it (`_coverage`); and in every dataset, each market's
    `processed_through_session` no later than the market's watermark as of τ (TDS-M016)."""
    old = entry.get("coverage", {}).get("by_market", {})
    new = json.loads(json.dumps(entry.get("coverage", {})))
    if again:
        parts: dict[str | None, list[pa.Table]] = {}
        for f in entry["files"]:
            market = next((p[7:] for p in Path(f["path"]).parts if p.startswith("market=")), None)
            parts.setdefault(market, []).append(pq.read_table(root / f["path"]))
        tables = {m: pa.concat_tables(t) for m, t in parts.items()}
        new = pk._coverage(tables).get("coverage", {}) if tables else {}
    for market, held in old.items():
        if "processed_through_session" in held:
            day = through.get(market, {}).get("complete_through_session")
            mark = min(held["processed_through_session"], day or held["processed_through_session"])
            new.setdefault("by_market", {}).setdefault(market, {})["processed_through_session"] = (
                mark
            )
    if new or "coverage" in entry:
        entry["coverage"] = new


def _by_column(entry: Mapping[str, Any]) -> Mapping[str, str]:
    found: Mapping[str, str] = (entry.get("params") or {}).get("availability_by_column", {})
    return found


def _read(root: Path, entry: Mapping[str, Any]) -> pa.Table:
    return pa.concat_tables([pq.read_table(root / f["path"]) for f in entry["files"]])


def _sessions(root: Path, entry: Mapping[str, Any], instruments: pa.Table) -> dict[Any, Any]:
    """`(instrument_id, session_date)` → `(ts_open, ts_close)` by the instrument's calendar."""
    calendar = _read(root, entry).to_pylist()
    times = {(r["calendar_id"], r["session_date"]): (r["ts_open"], r["ts_close"]) for r in calendar}
    of = dict(zip(instruments["instrument_id"].to_pylist(),
                  instruments["calendar_id"].to_pylist(), strict=True))  # fmt: skip
    return {"times": times, "calendar": of}


def _session(sessions: Mapping[str, Any], instrument: str, day: Any, edge: int) -> Any:
    found = sessions["times"].get((sessions["calendar"].get(instrument), day))
    return found[edge] if found else None


def _instants(name: str, entry: Mapping[str, Any], rows: pa.Table, sessions: Any) -> list[Any]:
    """Each row's first-known instant (the module's list), None where it has none."""
    known = entry.get("availability") or {"rule": "session_close"}  # by column: see the top
    known = {"rule": known} if isinstance(known, str) else known
    table = rows.to_pylist()
    if "terms" in known:
        return [min((t for t in (r["ts_announced"], r[known["terms"]]) if t is not None),
                    default=r[known["effect"]]) for r in table]  # fmt: skip
    if "exit" in known:
        return [r[known["exit"]] or _session(sessions, r["instrument_id"], r["exit_date"], 0)
                for r in table]  # fmt: skip
    if "column" in known:
        column = known["column"]
        if name == "instrument_symbols":
            return [r[column] or _session(sessions, r["instrument_id"], r["valid_from"], 0)
                    for r in table]  # fmt: skip
        return [r[column] for r in table]
    rule = known["rule"]
    if rule == "ts_end":
        return [r["ts_end"] or _session(sessions, r["instrument_id"], r["session_date"], 1)
                for r in table]  # fmt: skip
    if rule in ("session_open", "session_close"):
        edge = 0 if rule == "session_open" else 1
        return [_session(sessions, r["instrument_id"], r["session_date"], edge) for r in table]
    raise NotImplementedError(f"availability {known} of {name} is not cut here")


def _as_of(
    root: Path, entry: Mapping[str, Any], exits_cut: set[str], markets: Mapping[str, Any],
    marks: Mapping[str, Any],
) -> None:  # fmt: skip
    """`instruments`' two exceptions: `delisted_on` empty for an exit cut, and `last_session`
    empty where it lies after its market's watermark as of τ (still trading then: TDS-D001
    reads a set `last_session` as the end of the bars it expects)."""
    watermark = {m: dt.date.fromisoformat(marks[m].get("complete_through_session")
                                          or markets[m]["complete_through_session"])
                 for m in markets}  # fmt: skip
    for f in entry["files"]:
        rows = pq.read_table(part := root / f["path"])
        ends = zip(rows["last_session"].to_pylist(), rows["market"].to_pylist(), strict=True)
        later = [s is not None and s > watermark.get(m, s) for s, m in ends]
        gone = pc.is_in(rows["instrument_id"], value_set=pa.array(sorted(exits_cut), pa.string()))
        for column, hit in (("delisted_on", gone), ("last_session", pa.array(later))):
            at = rows.schema.get_field_index(column)
            empty = pc.if_else(hit, pa.scalar(None, rows[column].type), rows[column])
            rows = rows.set_column(at, rows.schema.field(at), empty)
        pq.write_table(rows, part)
        f.update(bytes=part.stat().st_size)
