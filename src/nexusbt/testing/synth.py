"""The synthetic TDS package generator (spec 4.8), part 1: the hand-authored `tiny` preset.

`tiny` is a table set by hand: the holidays, listings, tickers and prices below are literals or
fixed cycles, with no random numbers. It writes `instruments`, `instrument_symbols`,
`calendar_sessions` and dense daily `bars` (cumulative factors 1.0). The hashes in `tds.json`
and `--validate`'s check are the `tds` command's, run as a separate process: spec 2.5 draws
no arrow from `testing` to `nexusbt_tds`, so this module does not import it.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
import sysconfig
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Literal

import pyarrow as pa
import pyarrow.parquet as pq

from nexusbt.contracts import ID_COLUMN as ID

START, END = dt.date(2020, 1, 2), dt.date(2020, 3, 31)  # the tiny period (4.8 table)
#: The tds.json `markets` entries. ZZ: a test market without a rules pack (4.8).
MARKETS = {
    "KR": {"calendar_id": "XKRX", "currency": "KRW", "timezone": "Asia/Seoul"},
    "US": {"calendar_id": "XNYS", "currency": "USD", "timezone": "America/New_York"},
    "ZZ": {"calendar_id": "XZZZ", "currency": "XTS", "timezone": "America/New_York"},
}
NAMESPACES = {"KR": "synthetic KR", "US": "synthetic US", "ZZ": "synthetic test market"}
#: The period's weekday holidays, set by hand; XZZZ copies the XNYS sessions (4.8).
HOLIDAYS = {
    "XKRX": {dt.date(2020, 1, 24), dt.date(2020, 1, 27)},  # Seollal and its substitute day
    "XNYS": {dt.date(2020, 1, 20), dt.date(2020, 2, 17)},  # MLK Day, Presidents' Day
}
US_DST = dt.date(2020, 3, 8)  # US daylight saving starts: 14:30Z-21:00Z becomes 13:30Z-20:00Z
#: Per market 6 instruments `T00001`..`T00006`. T00002 (RENAMED) changes ticker on TICKER_CHANGE
#: and the last, listed on LATE_LISTING, takes its old ticker (symbol reuse, 4.8 (2)).
COUNT, RENAMED, TICKER_CHANGE, LATE_LISTING = 6, 2, dt.date(2020, 2, 14), dt.date(2020, 2, 18)
CYCLE = (100, 101, 102, 101)  # close = base x CYCLE[k % 4] / 100 on the k-th listed session
PRODUCER = "nexusbt-synth"
HINTS = {
    "TDS-M008": "nexusbt-synth part 1 declares tds:minimal-daily only: corporate actions and"
    " delistings come with part 2 (spec 4.8)",
    "TDS-K011": "nexusbt-synth numbers each calendar's sessions from 0 within the preset period",
}
ROW_GROUP = 100_000
_TS = pa.timestamp("us", tz="UTC")


def _at(day: dt.date, hour: int, minute: int) -> dt.datetime:
    return dt.datetime(day.year, day.month, day.day, hour, minute, tzinfo=dt.UTC)


def _sessions(calendar: str) -> list[dt.date]:
    holidays = HOLIDAYS["XNYS" if calendar == "XZZZ" else calendar]
    days = (START + dt.timedelta(n) for n in range((END - START).days + 1))
    return [d for d in days if d.weekday() < 5 and d not in holidays]


def _hours(calendar: str, day: dt.date) -> tuple[dt.datetime, dt.datetime]:
    if calendar == "XKRX":  # 06:00Z before 2016-08-01, outside every preset period here
        return _at(day, 0, 0), _at(day, 6, 30)
    shift = 1 if day >= US_DST else 0
    return _at(day, 14 - shift, 30), _at(day, 21 - shift, 0)


def _listed_on(n: int) -> dt.date:
    return LATE_LISTING if n == COUNT else START


def _ticker(market: str, n: int) -> str:
    return f"Q{market}{n:02d}"


def _tables(market: str) -> dict[str, list[dict[str, Any]]]:
    calendar, currency = MARKETS[market]["calendar_id"], MARKETS[market]["currency"]
    ids = [(n, f"{market}:T{n:05d}") for n in range(1, COUNT + 1)]
    renamed, late = ids[RENAMED - 1][1], ids[COUNT - 1][1]
    instruments = [
        {ID: iid, "asset_class": "equity", "category": "common", "market": market,
         "calendar_id": calendar, "currency": currency, "name": f"synthetic {iid}",
         "listed_on": _listed_on(n), "lot_size": 1.0, "multiplier": 1.0, "is_synthetic": False}
        for n, iid in ids
    ]  # fmt: skip
    old, new = _ticker(market, RENAMED), _ticker(market, RENAMED * 11)
    spans: list[tuple[str, str, dt.date, dt.date | None]]
    spans = [(iid, _ticker(market, n), START, None) for n, iid in ids if iid not in (renamed, late)]
    spans += [(renamed, old, START, TICKER_CHANGE), (renamed, new, TICKER_CHANGE, None)]
    spans += [(late, old, LATE_LISTING, None)]
    symbols = [
        {ID: iid, "symbol_type": "ticker", "symbol": symbol, "venue_mic": None, "ts_known_to": None,
         "valid_from": day, "valid_to": end, "ts_known_from": _at(day, 0, 0), "source": PRODUCER}
        for iid, symbol, day, end in sorted(spans, key=lambda s: (s[0], s[2]))
    ]  # fmt: skip
    days = _sessions(calendar)
    bars = []
    for n, iid in ids:
        close = None
        for k, day in enumerate(d for d in days if d >= _listed_on(n)):
            price = n * CYCLE[k % 4] * 100.0 if market == "KR" else n * CYCLE[k % 4] / 10
            open_ = price if close is None else close
            ts_open, ts_close = _hours(calendar, day)
            bars.append({
                ID: iid, "session_date": day, "ts_start": ts_open,
                "ts_end": ts_close, "open": open_, "high": max(open_, price),
                "low": min(open_, price), "close": price, "volume": 1000.0 * n,
                "obs_status": "traded", "cum_factor_split": 1.0, "cum_factor_total": 1.0,
            })  # fmt: skip
            close = price
    bars.sort(key=lambda b: (b["session_date"], b[ID]))
    return {"instruments": instruments, "instrument_symbols": symbols, "bars_1d": bars}


def _calendar(calendar: str) -> list[dict[str, Any]]:
    return [
        {"calendar_id": calendar, "session_date": day, "ts_open": ts_open, "ts_close": ts_close,
         "session_ord": k, "is_half_day": False, "session_kind": "regular", "source": PRODUCER}
        for k, day in enumerate(_sessions(calendar))
        for ts_open, ts_close in [_hours(calendar, day)]
    ]  # fmt: skip


_TYPES = {
    "listed_on": pa.date32(), "session_date": pa.date32(), "valid_from": pa.date32(),
    "valid_to": pa.date32(), "ts_known_from": _TS, "ts_known_to": _TS, "ts_start": _TS,
    "ts_end": _TS, "ts_open": _TS, "ts_close": _TS, "session_ord": pa.int32(),
    "venue_mic": pa.string(),
}  # fmt: skip


def _write(root: Path, rel: str, name: str, records: list[dict[str, Any]]) -> dict[str, Any]:
    columns = list(records[0])
    schema = pa.schema(
        [(c, _TYPES.get(c) or pa.array([r[c] for r in records]).type) for c in columns],
        metadata={"tds.dataset": name, "tds.schema_version": "1.0"},
    )
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(records, schema), path, row_group_size=ROW_GROUP)
    return {"path": rel, "rows": len(records), "bytes": path.stat().st_size}


def _tds(*args: str) -> subprocess.CompletedProcess[str]:
    """The `tds` command beside this interpreter, as its own process (a development dependency
    until T1.1a: without nexusbt-tds installed, FileNotFoundError)."""
    command = [str(Path(sysconfig.get_path("scripts")) / "tds"), *args]
    return subprocess.run(command, capture_output=True, text=True, check=False)  # noqa: S603


def make_snapshot(
    root: Path,
    *,
    preset: Literal["tiny", "small", "full", "full_ci"] = "small",
    seed: int = 0,
    snapshot_id: str = "synth-0001",
    markets: Sequence[str] = ("KR", "US"),
) -> Path:
    """Write the synthetic TDS package `preset` to `root` and its hashes into `tds.json`.

    Byte-identical for the same arguments. Files are written in place and nothing in `root` is
    deleted, so a `root` used with other markets keeps their files. Only `tiny` exists so far
    (`small` is the second part of #58); `seed` is unused by `tiny`, which has no randomness.
    """
    if preset != "tiny":
        raise NotImplementedError(f"preset {preset!r}: only 'tiny' is built so far (spec 4.8)")
    root, chosen = Path(root), [m for m in MARKETS if m in markets]
    if not chosen or set(markets) - set(MARKETS):
        raise ValueError(f"markets {list(markets)}: choose one or more of {sorted(MARKETS)}")
    tables: dict[str, list[dict[str, Any]]] = {}
    for market in chosen:
        for name, records in _tables(market).items():
            tables.setdefault(name, []).extend(records)
    files = {
        name: [_write(root, f"{name}/part-00000.parquet", name, sorted(
            tables[name], key=lambda r: tuple(str(r[k]) for k in key)))]
        for name, key in (("instruments", [ID]), ("instrument_symbols", [ID, "valid_from"]))
    }  # fmt: skip
    sessions = [r for c in sorted(MARKETS[m]["calendar_id"] for m in chosen) for r in _calendar(c)]
    files["calendar_sessions"] = [
        _write(root, "calendar_sessions/part-00000.parquet", "calendar_sessions", sessions)
    ]
    files["bars_1d"] = [
        _write(root, f"bars/freq=1d/market={m}/year=2020/part-00000.parquet", "bars_1d",
               [b for b in tables["bars_1d"] if b[ID].startswith(f"{m}:")])
        for m in chosen
    ]  # fmt: skip
    bars = {"kind": "bars", "path": "bars/freq=1d", "availability": {"rule": "ts_end"}, "params":
            {"freq": "1d", "price_basis": "raw", "density": "dense", "bar_time": "session"},
            "columns": [{"name": c, "type": "ts_us"} for c in ("ts_start", "ts_end")]}  # fmt: skip
    manifest = {
        "tds_version": "1.0", "name": f"synth-{preset}", "created": f"{END}T00:00:00Z",
        "snapshot_id": snapshot_id, "producer": {"name": PRODUCER, "hints": HINTS},
        "profiles": ["tds:minimal-daily@1.0"],
        "id_namespaces": {m: NAMESPACES[m] for m in chosen},
        "markets": {m: MARKETS[m] for m in chosen},
        "datasets": [
            {"name": name, "kind": name, "path": name, "schema_version": "1.0",
             **(bars if name == "bars_1d" else {}), "files": entries}
            for name, entries in files.items()
        ],
        "hashes": {"hash_spec": "tds-hash-1"},
        "writer": {"name": PRODUCER, "row_group_rows": ROW_GROUP},
    }  # fmt: skip
    (root / "tds.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    done = _tds("hash", str(root), "--write")
    if done.returncode != 0:
        raise RuntimeError(f"tds hash --write {root} exited {done.returncode}: {done.stderr}")
    return root


def main(argv: Sequence[str] | None = None) -> int:
    """`python -m nexusbt.testing.synth --preset P --out DIR [--markets KR,US,ZZ] --validate`."""
    parser = argparse.ArgumentParser(prog="python -m nexusbt.testing.synth")
    parser.add_argument("--preset", choices=["tiny", "small", "full", "full_ci"], default="tiny")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--markets", default="KR,US")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--validate", action="store_true", help="then run tds check --level full")
    args = parser.parse_args(argv)
    root = make_snapshot(
        args.out, preset=args.preset, seed=args.seed, markets=args.markets.split(",")
    )
    manifest = json.loads((root / "tds.json").read_text(encoding="utf-8"))
    for ds in manifest["datasets"]:
        print(f"{ds['name']} {sum(f['rows'] for f in ds['files'])} rows")
    for name in ("value_sha256", "semantic_sha256"):
        print(f"{name} {manifest['hashes'][name]}")
    if not args.validate:
        return 0
    done = _tds("check", str(root), "--level", "full")
    sys.stdout.write(done.stdout)
    sys.stderr.write(done.stderr)
    return done.returncode


if __name__ == "__main__":
    sys.exit(main())
