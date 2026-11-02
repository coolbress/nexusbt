"""The synthetic TDS package generator (spec 4.8): the `tiny` and `small` presets.

`tiny` is a table set by hand: the holidays, listings, tickers and prices below are literals or
fixed cycles, with no random numbers. `small` follows 4.8's generation rules (1) to (3) with
`numpy.random.Generator(PCG64(seed))`. Both write `instruments`, `instrument_symbols`, an empty
`instrument_xref`, `calendar_sessions` and dense daily `bars` (cumulative factors 1.0). The
hashes in `tds.json` and `--validate`'s check are the `tds` command's, run as a separate
process: spec 2.5 draws no arrow from `testing` to `nexusbt_tds`, so this module does not
import it.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
import sysconfig
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal

import exchange_calendars as xc
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from nexusbt.contracts import ID_COLUMN as ID

START, END = dt.date(2020, 1, 2), dt.date(2020, 3, 31)  # the tiny period (4.8 table)
SMALL = (dt.date(2015, 1, 2), dt.date(2019, 12, 31))  # the small period
SMALL_COUNTS = {"KR": 120, "US": 180, "ZZ": 120}  # 4.8 table; ZZ takes 6 to 120
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
KR_CLOSE = dt.date(2016, 8, 1)  # KRX closes at 06:30Z from this day, at 06:00Z before (4.8 (1))
#: Per market 6 instruments `T00001`..`T00006`. T00002 (RENAMED) changes ticker on TICKER_CHANGE
#: and the last, listed on LATE_LISTING, takes its old ticker (symbol reuse, 4.8 (2)).
COUNT, RENAMED, TICKER_CHANGE, LATE_LISTING = 6, 2, dt.date(2020, 2, 14), dt.date(2020, 2, 18)
CYCLE = (100, 101, 102, 101)  # close = base x CYCLE[k % 4] / 100 on the k-th listed session
YEAR = 252  # sessions: small draws listings over 8 such years before its start, to its end
PRODUCER = "nexusbt-synth"
HINTS = {
    "TDS-M008": "nexusbt-synth declares tds:minimal-daily only until it generates corporate"
    " actions and delistings (spec 4.8 (4), (6))",
    "TDS-K011": "nexusbt-synth numbers each calendar's sessions from 0 within the preset period",
}
ROW_GROUP = 100_000
_TS = pa.timestamp("us", tz="UTC")
Table = dict[str, Any]  # column name → values, in schema order


def _at(day: dt.date, hour: int, minute: int) -> dt.datetime:
    return dt.datetime(day.year, day.month, day.day, hour, minute, tzinfo=dt.UTC)


def _sessions(calendar: str) -> list[dt.date]:
    holidays = HOLIDAYS["XNYS" if calendar == "XZZZ" else calendar]
    days = (START + dt.timedelta(n) for n in range((END - START).days + 1))
    return [d for d in days if d.weekday() < 5 and d not in holidays]


def _hours(calendar: str, day: dt.date) -> tuple[dt.datetime, dt.datetime]:
    if calendar == "XKRX":
        return _at(day, 0, 0), _at(day, 6, 30 if day >= KR_CLOSE else 0)
    shift = 1 if day >= US_DST else 0
    return _at(day, 14 - shift, 30), _at(day, 21 - shift, 0)


def _listed_on(n: int) -> dt.date:
    return LATE_LISTING if n == COUNT else START


def _ticker(market: str, n: int) -> str:
    return f"Q{market}{n:02d}"


def _columns(records: list[dict[str, Any]]) -> Table:
    return {c: [r[c] for r in records] for c in records[0]}


def _symbols(spans: Sequence[tuple[str, str, dt.date, dt.date | None]]) -> Table:
    """`instrument_symbols` rows from (instrument, ticker, valid from, valid to) spans."""
    return _columns([
        {ID: iid, "symbol_type": "ticker", "symbol": symbol, "venue_mic": None, "ts_known_to": None,
         "valid_from": day, "valid_to": end, "ts_known_from": _at(day, 0, 0), "source": PRODUCER}
        for iid, symbol, day, end in sorted(spans, key=lambda s: (s[0], s[2]))
    ])  # fmt: skip


def _instruments(market: str, ids: Sequence[str], listed: Sequence[dt.date], **more: Any) -> Table:
    calendar, currency = MARKETS[market]["calendar_id"], MARKETS[market]["currency"]
    return {ID: list(ids), "asset_class": ["equity"] * len(ids), "category": ["common"] * len(ids),
            "market": [market] * len(ids), "calendar_id": [calendar] * len(ids),
            "currency": [currency] * len(ids), "name": [f"synthetic {i}" for i in ids],
            "listed_on": list(listed), **more, "lot_size": [1.0] * len(ids),
            "multiplier": [1.0] * len(ids), "is_synthetic": [False] * len(ids)}  # fmt: skip


def _tiny(market: str) -> dict[str, Table]:
    calendar = MARKETS[market]["calendar_id"]
    ids = [(n, f"{market}:T{n:05d}") for n in range(1, COUNT + 1)]
    renamed, late = ids[RENAMED - 1][1], ids[COUNT - 1][1]
    instruments = _instruments(market, [i for _, i in ids], [_listed_on(n) for n, _ in ids])
    old, new = _ticker(market, RENAMED), _ticker(market, RENAMED * 11)
    spans: list[tuple[str, str, dt.date, dt.date | None]]
    spans = [(iid, _ticker(market, n), START, None) for n, iid in ids if iid not in (renamed, late)]
    spans += [(renamed, old, START, TICKER_CHANGE), (renamed, new, TICKER_CHANGE, None)]
    spans += [(late, old, LATE_LISTING, None)]
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
    return {"instruments": instruments, "instrument_symbols": _symbols(spans),
            "bars_1d": _columns(bars)}  # fmt: skip


def _tiny_calendar(calendar: str) -> Table:
    return _columns([
        {"calendar_id": calendar, "session_date": day, "ts_open": ts_open, "ts_close": ts_close,
         "session_ord": k, "is_half_day": False, "session_kind": "regular", "source": PRODUCER}
        for k, day in enumerate(_sessions(calendar))
        for ts_open, ts_close in [_hours(calendar, day)]
    ])  # fmt: skip


def _small_calendar(calendar: str, start: dt.date, end: dt.date) -> Table:
    """4.8 (1): exchange_calendars sessions; KR times fixed, US times and half days as given."""
    cal = xc.get_calendar("XNYS" if calendar == "XZZZ" else calendar, start=start, end=end)
    sched = cal.schedule.loc[str(start) : str(end)]
    days = sched.index.to_numpy().astype("datetime64[D]")
    opens = sched["open"].dt.tz_localize(None).to_numpy().astype("datetime64[us]")
    closes = sched["close"].dt.tz_localize(None).to_numpy().astype("datetime64[us]")
    half = closes - opens < np.timedelta64(390, "m")  # NYSE early closes
    if calendar == "XKRX":  # 4.8's fixed times, not the library's late opens; no half days
        late, half = days >= np.datetime64(KR_CLOSE), np.zeros(len(days), bool)
        opens = days.astype("datetime64[us]")
        closes = opens + np.where(late, 390, 360).astype("timedelta64[m]")
    return {"calendar_id": [calendar] * len(days), "session_date": days, "ts_open": opens,
            "ts_close": closes, "session_ord": np.arange(len(days)), "is_half_day": half,
            "session_kind": ["regular"] * len(days), "source": [PRODUCER] * len(days)}  # fmt: skip


def _small(market: str, n: int, sessions: Table, rng: np.random.Generator) -> dict[str, Table]:
    """4.8 (2) and (3): listings, ticker histories and dense raw bars of `n` instruments."""
    days, opens, closes = sessions["session_date"], sessions["ts_open"], sessions["ts_close"]
    first: list[int] = []  # each instrument's first and last session index in the period
    last: list[int] = []
    while len(first) < n:  # uniform listing, exponential life of mean 8 years
        listing = int(rng.integers(-8 * YEAR, len(days)))
        exit_ = listing + int(np.ceil(rng.exponential(8 * YEAR)))
        if exit_ >= 0:
            first.append(max(listing, 0))
            last.append(min(exit_, len(days) - 1))
    ids = [f"{market}:T{k:05d}" for k in range(1, n + 1)]
    gone = [j < len(days) - 1 for j in last]
    instruments = _instruments(
        market, ids, [days[i].item() for i in first],
        listed_on_censored=[i == 0 for i in first],
        last_session=[days[j].item() if g else None for j, g in zip(last, gone, strict=True)],
    )  # fmt: skip
    end = [days[j + 1].item() if g else None for j, g in zip(last, gone, strict=True)]
    tickers = [f"Q{market}{k:04d}" for k in range(1, n + 1)]
    spans = {k: [(ids[k], tickers[k], days[first[k]].item(), end[k])] for k in range(n)}
    long = [k for k in range(n) if last[k] - first[k] > 2]
    freed = []  # (session index the old ticker is free from, ticker)
    for k in rng.choice(long, min(len(long), max(1, round(0.01 * n))), replace=False):  # changes
        at = int(rng.integers(first[k] + 1, last[k]))
        spans[k] = [(ids[k], tickers[k], days[first[k]].item(), days[at].item()),
                    (ids[k], f"R{market}{k + 1:04d}", days[at].item(), end[k])]  # fmt: skip
        freed.append((at, tickers[k]))
    freed += [(last[k] + 1, tickers[k]) for k in range(n) if gone[k] and len(spans[k]) == 1]
    late = [k for k in rng.permutation(n) if first[k] > 0 and len(spans[k]) == 1]
    for _ in range(max(1, round(0.005 * n))):  # another id reuses an old ticker
        pair = next(((k, f) for k in late for f in freed if f[0] < first[k]), None)
        if pair is None:
            break
        k, (_, old) = pair
        spans[k] = [(ids[k], old, *spans[k][0][2:])]
        late.remove(k)
        freed = [f for f in freed if f[1] != old]
    bars: dict[str, list[Any]] = {}
    for k in range(n):  # 4.8 (3): log returns, open from the previous close, OHLC enclosed
        i, j = first[k], last[k] + 1
        sigma = rng.uniform(0.01, 0.04)
        price = rng.uniform(1e3, 1e6) if market == "KR" else rng.uniform(2, 500)
        close = price * np.exp(np.cumsum(rng.normal(0.0003, sigma, j - i)))
        open_ = np.concatenate([[price], close[:-1]]) * np.exp(rng.normal(0, sigma / 2, j - i))
        wick = np.exp(np.abs(rng.normal(0, sigma / 2, (2, j - i))))
        for name, values in {
            ID: [ids[k]] * (j - i), "session_date": days[i:j], "ts_start": opens[i:j],
            "ts_end": closes[i:j], "open": open_, "high": np.maximum(open_, close) * wick[0],
            "low": np.minimum(open_, close) / wick[1], "close": close,
            "volume": np.floor(rng.lognormal(10, 1, j - i)), "obs_status": ["traded"] * (j - i),
            "cum_factor_split": np.ones(j - i), "cum_factor_total": np.ones(j - i),
        }.items():  # fmt: skip
            bars.setdefault(name, []).append(values)
    table = pa.table({c: np.concatenate(v) for c, v in bars.items()})
    order = [("session_date", "ascending"), (ID, "ascending")]
    return {"instruments": instruments, "bars_1d": table.sort_by(order),
            "instrument_symbols": _symbols([s for v in spans.values() for s in v])}  # fmt: skip


_TYPES = {
    "listed_on": pa.date32(), "session_date": pa.date32(), "valid_from": pa.date32(),
    "valid_to": pa.date32(), "last_session": pa.date32(), "ts_known_from": _TS,
    "ts_known_to": _TS, "ts_start": _TS, "ts_end": _TS, "ts_open": _TS, "ts_close": _TS,
    "session_ord": pa.int32(), "venue_mic": pa.string(), "listed_on_censored": pa.bool_(),
}  # fmt: skip
#: TDS 5.3 `instrument_xref`, written empty (4.8 (2)).
XREF = {c: pa.string() for c in (ID, "id_type", "id_value", "link_quality", "source")}
XREF |= {"valid_from": pa.date32(), "valid_to": pa.date32()}


def _arrow(table: Table | pa.Table) -> pa.Table:
    if isinstance(table, pa.Table):
        return table.cast(pa.schema([(c, _TYPES.get(c, t)) for c, t in zip(
            table.column_names, table.schema.types, strict=True)]))  # fmt: skip
    return pa.table({c: pa.array(v, _TYPES.get(c)) for c, v in table.items()})


def _write(root: Path, rel: str, name: str, table: pa.Table) -> dict[str, Any]:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    meta = {"tds.dataset": name, "tds.schema_version": "1.0"}
    pq.write_table(table.replace_schema_metadata(meta), path, row_group_size=ROW_GROUP)
    return {"path": rel, "rows": table.num_rows, "bytes": path.stat().st_size}


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
    start: dt.date | None = None,
    end: dt.date | None = None,
    markets: Sequence[str] = ("KR", "US"),
    n_kr: int | None = None,
    n_us: int | None = None,
    events: Sequence[Mapping[str, Any]] = (),
    overrides: Mapping[str, Any] | None = None,
    degrade: Sequence[str] = (),
) -> Path:
    """Write the synthetic TDS package `preset` to `root` and its hashes into `tds.json`.

    Byte-identical for the same arguments. Files are written in place and nothing in `root` is
    deleted, so a `root` used with other markets keeps their files. `tiny` is hand-set and
    takes none of `seed`, `start`, `end`, `n_kr`, `n_us`; `full`, `full_ci`, `events`,
    `overrides` and `degrade` come with later tickets (spec 10.1: T0.7, T0.8c, T0.16a).
    """
    if preset not in ("tiny", "small") or events or overrides or degrade:
        raise NotImplementedError("only presets tiny and small, without events, overrides or"
                                  " degrade, are built so far (spec 4.8)")  # fmt: skip
    root, chosen = Path(root), [m for m in MARKETS if m in markets]
    if not chosen or set(markets) - set(MARKETS):
        raise ValueError(f"markets {list(markets)}: choose one or more of {sorted(MARKETS)}")
    if preset == "tiny" and any(v is not None for v in (start, end, n_kr, n_us)):
        raise ValueError("tiny is set by hand: start, end, n_kr and n_us apply to small only")
    first, final = (start or SMALL[0], end or SMALL[1]) if preset == "small" else (START, END)
    counts = SMALL_COUNTS | {k: v for k, v in (("KR", n_kr), ("US", n_us)) if v is not None}
    # one stream per market from PCG64(seed), so a market's rows do not depend on the others
    rngs = dict(zip(MARKETS, np.random.Generator(np.random.PCG64(seed)).spawn(3), strict=True))
    calendars, tables = {}, {}
    for m in chosen:
        cal = MARKETS[m]["calendar_id"]
        if preset == "tiny":
            calendars[cal], tables[m] = _tiny_calendar(cal), _tiny(m)
        else:
            calendars[cal] = _small_calendar(cal, first, final)
            tables[m] = _small(m, counts[m], calendars[cal], rngs[m])

    def joined(name: str, key: list[str]) -> pa.Table:
        table = pa.concat_tables([_arrow(tables[m][name]) for m in chosen])
        return table.sort_by([(k, "ascending") for k in key])

    sessions = pa.concat_tables([_arrow(calendars[c]) for c in sorted(calendars)])
    files = {
        name: [_write(root, f"{name}/part-00000.parquet", name, table)]
        for name, table in (
            ("instruments", joined("instruments", [ID])),
            ("instrument_symbols", joined("instrument_symbols", [ID, "valid_from"])),
            ("instrument_xref", pa.schema(XREF).empty_table()),
            ("calendar_sessions", sessions),
        )
    }  # fmt: skip
    files["bars_1d"] = []
    for m in chosen:
        bars = _arrow(tables[m]["bars_1d"])
        years = pa.compute.year(bars["session_date"]).to_numpy()
        for year in sorted(set(years.tolist())):
            files["bars_1d"].append(_write(
                root, f"bars/freq=1d/market={m}/year={year}/part-00000.parquet", "bars_1d",
                bars.filter(years == year)))  # fmt: skip
    bars = {"kind": "bars", "path": "bars/freq=1d", "availability": {"rule": "ts_end"}, "params":
            {"freq": "1d", "price_basis": "raw", "density": "dense", "bar_time": "session"},
            "columns": [{"name": c, "type": "ts_us"} for c in ("ts_start", "ts_end")]}  # fmt: skip
    unstated = ((ID, "id"), ("id_type", "code"), ("link_quality", "code"), ("source", "string"))
    xref = {"columns": [{"name": c, "type": t} for c, t in unstated]}  # types 5.3 leaves out
    manifest = {
        "tds_version": "1.0", "name": f"synth-{preset}", "created": f"{final}T00:00:00Z",
        "snapshot_id": snapshot_id, "producer": {"name": PRODUCER, "hints": HINTS},
        "profiles": ["tds:minimal-daily@1.0"],
        "id_namespaces": {m: NAMESPACES[m] for m in chosen},
        "markets": {m: MARKETS[m] for m in chosen},
        "datasets": [
            {"name": name, "kind": name, "path": name, "schema_version": "1.0",
             **{"bars_1d": bars, "instrument_xref": xref}.get(name, {}), "files": entries}
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


if __name__ == "__main__":  # pragma: no cover - run by `python -m`, a separate process
    sys.exit(main())
