"""The conformance packages: per check code, a package raising only that code (TDS 8.5, 8.4a).

`python tds/conformance/build.py [OUT]` writes them to `OUT/<code>/{pass,fail}/` (default: this
folder). They are generated, never edited by hand. The data files are one-row Parquet files with
the columns the schema level needs (the M packages are read for sizes only).
"""

from __future__ import annotations

import copy
import datetime as dt
import io
import json
import math
import shutil
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

Files = dict[str, bytes]
Package = tuple[dict[str, Any], Files]
Change = Callable[[dict[str, Any], Files], object]

INSTRUMENTS = "instruments/part-00000.parquet"
BARS = "bars/freq=1d/market=US/year=2024/part-00000.parquet"
CALENDAR = "calendar_sessions/part-00000.parquet"
ROWS = {CALENDAR: 2}  # the base's files hold one row each, the calendar two sessions
DAY = pa.array([dt.date(2024, 1, 2)])


def sessions() -> pa.Table:
    """The base's XNYS sessions of 2024-01-02 and -03 (TDS 5.4), as the exchange publishes
    them: the days the cases' bars fall on."""
    days = [dt.datetime(2024, 1, d, tzinfo=dt.UTC) for d in (2, 3)]
    return pa.table({"calendar_id": ["XNYS"] * 2, "session_date": [d.date() for d in days],
                     "ts_open": pa.array([d.replace(hour=14, minute=30) for d in days], TS_UTC),
                     "ts_close": pa.array([d.replace(hour=21) for d in days], TS_UTC),
                     "session_kind": ["regular"] * 2, "source": ["exchange"] * 2})  # fmt: skip


def instruments(**columns: pa.Array | None) -> pa.Table:
    """One `instruments` row with the non-null columns (TDS 5.1); a column `None` is left out."""
    base = {"instrument_id": ["US:AAA"], "asset_class": ["equity"], "market": ["US"],
            "calendar_id": ["XNYS"], "currency": ["USD"], "listed_on": DAY, "lot_size": [1.0],
            "multiplier": [1.0], "is_synthetic": [False]}  # fmt: skip
    return pa.table({k: v for k, v in (base | columns).items() if v is not None})


def bars_table(**columns: pa.Array | None) -> pa.Table:
    """One daily bar (TDS 5.5); a column `None` is left out. An equity's bars hold all of OHLCV
    (chapter 7, #705): by default `open` and `low` are the whole number at or below `close`,
    `high` the one at or above (10.0 where `close` is not a finite f64), `volume` 100, so that a
    case that breaks `close` breaks that column alone."""
    base = {"instrument_id": pa.array(["US:AAA"]), "session_date": DAY, "close": pa.array([10.0])}
    table = base | columns
    n, close = len(table["instrument_id"] or []), table["close"]
    f64 = close is not None and close.type == pa.float64()
    near = [c if isinstance(c, float) and math.isfinite(c) else 10.0
            for c in (close.to_pylist() if f64 else [None] * n)]  # fmt: skip
    down, up = [float(math.floor(c)) for c in near], [float(math.ceil(c)) for c in near]
    filled = {"open": down, "high": up, "low": down, "volume": [100.0] * n}
    table |= {k: v for k, v in filled.items() if k not in table}
    return pa.table({k: v for k, v in table.items() if v is not None})


def parquet(
    table: pa.Table, dataset: str, *, meta: dict[str, str] | None = None, **opts: Any
) -> bytes:
    """`table` as Parquet with TDS 3.7's key-value metadata (`meta` replaces it)."""
    kv = {"tds.dataset": dataset, "tds.schema_version": "1.0"} if meta is None else meta
    out = io.BytesIO()
    pq.write_table(table.replace_schema_metadata(kv), out, **opts)
    return out.getvalue()


def rewrite(m: dict[str, Any], files: Files, rel: str, table: pa.Table, **opts: Any) -> None:
    """Write `table` to the listed file `rel` and keep its `bytes` in tds.json right."""
    (ds,) = (d for d in m["datasets"] if d["files"][0]["path"] == rel)
    files[rel] = parquet(table, ds["name"], **opts)
    ds["files"][0] |= {"bytes": len(files[rel]), "rows": table.num_rows}


def base() -> Package:
    """A package that passes the manifest and schema levels: `tds:minimal-daily@1.0`, with the
    XNYS sessions of 2024-01-02 and -03 every daily profile requires (TDS 7, #705)."""
    files = {
        INSTRUMENTS: parquet(instruments(), "instruments"),
        BARS: parquet(bars_table(), "bars_1d"),
        CALENDAR: parquet(sessions(), "calendar_sessions"),
    }
    bars_1d = {"params": dict(DENSE), "availability": {"rule": "ts_end"}}  # all declared (C5)
    datasets: list[tuple[str, str, str, str, dict[str, Any]]] = [
        ("instruments", "instruments", "instruments", INSTRUMENTS, {}),
        ("bars_1d", "bars", "bars/freq=1d", BARS, bars_1d),
        ("calendar_sessions", "calendar_sessions", "calendar_sessions", CALENDAR, {}),
    ]
    manifest = {
        "tds_version": "1.0",
        "tds_draft": "2026-11-28",  # TDS 4.2: the text these packages follow (#529)
        "name": "conformance",
        "created": "2026-11-02T00:00:00Z",
        "snapshot_id": "20261102-000000",
        "producer": {"name": "nexusbt-tds conformance", "hints": {}},
        "profiles": ["tds:minimal-daily@1.0"],
        "id_namespaces": {"XNYS": "synthetic test ids"},
        "markets": {
            "US": {"calendar_id": "XNYS", "currency": "USD", "timezone": "America/New_York"}
        },
        "datasets": [
            {"name": name, "kind": kind, "schema_version": "1.0", "path": path, **extra}
            | {"files": [{"path": file, "rows": ROWS.get(file, 1), "bytes": len(files[file])}]}
            for name, kind, path, file, extra in datasets
        ],
        "hashes": {"hash_spec": "tds-hash-2"},
        "writer": {"name": "nexusbt-tds conformance", "row_group_rows": 1},
    }
    return manifest, files


def bars(m: dict[str, Any]) -> dict[str, Any]:
    dataset: dict[str, Any] = m["datasets"][1]
    return dataset


def _set(key: str, value: Any, *, in_bars: bool = False) -> Change:
    """Set a top-level field of tds.json, or with `in_bars` a field of the bars dataset."""

    def change(m: dict[str, Any], files: Files) -> None:
        (bars(m) if in_bars else m)[key] = value

    return change


def _move_bars(path: str) -> Change:
    """List the bars file at `path`; the file moves with it unless `path` leaves the package."""

    def change(m: dict[str, Any], files: Files) -> None:
        bars(m)["files"][0]["path"] = path
        content = files.pop(BARS)
        if not path.startswith(("/", "..")):
            files[path] = content

    return change


def _keep(m: dict[str, Any], files: Files) -> None:
    """The base package, unchanged."""


def _bars(meta: dict[str, str] | None = None, **columns: pa.Array | None) -> Change:
    """Rewrite the bars file with `columns` changed (`meta`: its key-value metadata)."""
    return lambda m, f: rewrite(m, f, BARS, bars_table(**columns), meta=meta)


def _instruments(*, codes: bool = False, **columns: pa.Array | None) -> Change:
    """Rewrite the instruments file; `codes` lists `category` `ordinary` in `dictionary/codes`."""

    def change(m: dict[str, Any], files: Files) -> None:
        rewrite(m, files, INSTRUMENTS, instruments(**columns))
        if codes:
            _codes(m, files)

    return change


def _add(kind: str, columns: dict[str, Any], *paths: str) -> Change:
    """Add a dataset of `kind` with files at `paths` (one unpartitioned), each holding `columns`."""

    def change(m: dict[str, Any], files: Files) -> None:
        table, entries = pa.table(columns), []
        if kind == "calendar_sessions":  # in place of the base's (#705): one calendar
            m["datasets"] = [d for d in m["datasets"] if d["kind"] != kind]
            files.pop(CALENDAR, None)
        for rel in paths or (f"{kind}/part-00000.parquet",):
            files[rel] = parquet(table, kind)
            entries.append({"path": rel, "rows": table.num_rows, "bytes": len(files[rel])})
        m["datasets"].append({"name": kind, "kind": kind, "schema_version": "1.0", "path": kind}
                             | {"files": entries})  # fmt: skip

    return change


#: TDS 4.4 `dictionary/codes`, listing `category` `ordinary`.
_codes = _add("dictionary/codes", {"field": ["category"], "code": ["ordinary"]})
TS_UTC = pa.timestamp("us", "UTC")
NEW_YEAR = dt.datetime(2024, 1, 1, tzinfo=dt.UTC)


def _bars_on(*days: int) -> Change:
    """US:AAA's daily bars on these days of January 2024, in that order."""
    columns = {"session_date": pa.array([dt.date(2024, 1, d) for d in days])}
    n = len(days)
    return _bars(instrument_id=pa.array(["US:AAA"] * n), close=pa.array([10.0] * n), **columns)


def _no_close(status: str) -> Change:
    """A bar of `status` without a price, volume 0 (5.5 for `halted`), then a traded one with
    them: the dataset holds `close`, which `tds:minimal-daily` requires (M008, #352)."""
    price = pa.array([None, 10.0])
    return _bars(
        instrument_id=pa.array(["US:AAA"] * 2),
        session_date=pa.array([dt.date(2024, 1, 2), dt.date(2024, 1, 3)]),
        open=price, high=price, low=price, close=price, volume=pa.array([0.0, 100.0]),
        obs_status=pa.array([status, "traded"]),
    )  # fmt: skip


def _two_bars(**second: pa.Array) -> Change:
    """A second bars file in the folder, US:AAA's bar of the 3rd with `second` added (S011)."""

    def change(m: dict[str, Any], files: Files) -> None:
        rel = BARS.replace("part-00000", "part-00001")
        files[rel] = parquet(bars_table(session_date=pa.array([dt.date(2024, 1, 3)]), **second),
                             "bars_1d")  # fmt: skip
        bars(m)["files"].append({"path": rel, "rows": 1, "bytes": len(files[rel])})

    return change


def _id_twice(m: dict[str, Any], files: Files) -> None:
    """The instruments file storing `instrument_id` twice (S011)."""
    t = instruments()
    names = [*t.column_names, "instrument_id"]
    twice = pa.Table.from_arrays([*t.columns, t["instrument_id"]], names)
    rewrite(m, files, INSTRUMENTS, twice)


def _ranged(second_from: str) -> Change:
    """The bars as two files named by time range (TDS 3.6), the second from `second_from`."""

    def change(m: dict[str, Any], files: Files) -> None:
        folder, ds = BARS.rsplit("/", 1)[0], bars(m)
        files.pop(BARS)
        ds["files"] = []
        names = ("2024-01-02T00-00-00Z_2024-01-02T23-59-59Z", f"{second_from}_2024-01-03T23-59-59Z")
        for day, name in zip((2, 3), names, strict=True):
            rel = f"{folder}/{name}.parquet"
            table = bars_table(session_date=pa.array([dt.date(2024, 1, day)]))
            files[rel] = parquet(table, "bars_1d")
            ds["files"].append({"path": rel, "rows": 1, "bytes": len(files[rel])})

    return change


def _symbols(second_from: dt.date) -> Change:
    """Ticker AAA: US:AAA from 2024-01-02 until 2024-06-03, then US:BBB from `second_from`."""

    def change(m: dict[str, Any], files: Files) -> None:
        both = pa.concat_tables([instruments(), instruments(instrument_id=pa.array(["US:BBB"]))])
        rewrite(m, files, INSTRUMENTS, both)
        _add("instrument_symbols", {
            "instrument_id": ["US:AAA", "US:BBB"], "symbol_type": ["ticker"] * 2,
            "symbol": ["AAA"] * 2, "venue_mic": ["XNYS"] * 2,
            "valid_from": pa.array([dt.date(2024, 1, 2), second_from]),
            "valid_to": pa.array([dt.date(2024, 6, 3), None]),
            "ts_known_from": pa.array([NEW_YEAR] * 2, TS_UTC),
            "ts_known_to": pa.array([None] * 2, TS_UTC),
        })(m, files)  # fmt: skip

    return change


def _sessions(first: int, on: tuple[int, ...] = (2, 3), years: tuple[int, ...] = (2024,)) -> Change:
    """XNYS sessions on days `on` of January of `years` numbered from `first` (TDS 5.4)."""
    days = [dt.datetime(y, 1, d, tzinfo=dt.UTC) for y in years for d in on]
    n = len(days)
    return _add("calendar_sessions", {
        "calendar_id": ["XNYS"] * n, "session_date": pa.array([d.date() for d in days]),
        "ts_open": pa.array([d.replace(hour=14, minute=30) for d in days], TS_UTC),
        "ts_close": pa.array([d.replace(hour=21) for d in days], TS_UTC),
        "session_ord": pa.array(range(first, first + n), pa.int32()),
        "session_kind": ["regular"] * n, "source": ["exchange"] * n,
    })  # fmt: skip


def no_calendar(m: dict[str, Any], files: Files) -> None:
    """The base without its `calendar_sessions`, for a test of a package that has none, and so
    declaring no profile: every daily one requires it (C3, #705)."""
    m["datasets"] = [d for d in m["datasets"] if d["kind"] != "calendar_sessions"]
    m["profiles"] = []
    files.pop(CALENDAR, None)


def _both(*changes: Change) -> Change:
    return lambda m, f: [change(m, f) for change in changes]


def _markets_without(m: dict[str, Any], files: Files) -> None:
    """Three more markets, each without one of the fields a market entry holds (3.8, 4.2, #567)."""
    us = m["markets"]["US"]
    for code, field in (("KR", "calendar_id"), ("JP", "currency"), ("HK", "timezone")):
        m["markets"][code] = {k: v for k, v in us.items() if k != field}


def _crypto(declared: bool) -> Change:
    """Instruments in USDT, outside ISO 4217; `declared` lists it in tds.json `currencies`."""
    usdt = [{"code": "USDT", "kind": "crypto", "decimals": 2}] if declared else []
    return _both(_instruments(currency=pa.array(["USDT"])), _set("currencies", usdt))


def _exits(
    *, delisted: bool, ret_lo: float = 0.0, includes: bool | None = None,
    **times: dt.datetime | None,
) -> Change:  # fmt: skip
    """US:AAA's delisting on 2024-01-02 (5.13), `ret_hi` 0; `delisted` sets
    `instruments.delisted_on` too; `includes`: `ret_observed_includes_distributions`, if any."""
    flag = {"ret_observed_includes_distributions": [includes]} if includes is not None else {}
    exit_ = _add("delistings", {
        "delisting_id": ["US:L1"], "instrument_id": ["US:AAA"], "last_trading_date": DAY,
        "exit_date": DAY, "delist_type": ["merger"], "ref_date": DAY, "ref_price": [10.0],
        "exit_value_status": ["observed"], "ret_lo": [ret_lo], "ret_hi": [0.0],
        "policy_id": ["exit-value-v1"], **flag,
        **{k: pa.array([v], TS_UTC) for k, v in times.items()},
    })  # fmt: skip
    return _both(exit_, _instruments(delisted_on=DAY)) if delisted else exit_


EXITS = {"exit": "ts_exit_known", "value": "ts_value_available"}  # 6.2's two-instant form


def _exited(known: dt.datetime | None, through: str = "2024-01-02", rule: Any = EXITS) -> Change:
    """US:AAA's exit known at `known`, in `delistings` (no `market=` partitions, availability
    `rule`) processed through `through` in US; XNYS sessions on the 2nd and 3rd closing at
    21:00 UTC (TDS 4.3, D003)."""

    def change(m: dict[str, Any], files: Files) -> None:
        _sessions(0)(m, files)
        _exits(delisted=True, ts_exit_known=known, ts_value_available=known)(m, files)
        coverage = {"by_market": {"US": {"processed_through_session": through}}}
        m["datasets"][-1] |= {"availability": rule, "coverage": coverage}

    return change


def _rules(*bands: tuple[Any, Any, Any], until: dt.date | str | None = None) -> Change:
    """Rule set `us-tick` from 2024-01-02: a `tick_band` row per (price_from, price_to, tick),
    valid until `until` (a string: written as text, S002's)."""
    n, (lo, hi, tick) = len(bands), zip(*bands, strict=True)
    to = pa.array([until] * n, pa.string() if isinstance(until, str) else pa.date32())
    return _add("market_rules", {
        "rule_id": ["us-tick"] * n, "market": ["US"] * n, "rule_kind": ["tick_band"] * n,
        "venue_group": ["*"] * n, "valid_from": pa.array([dt.date(2024, 1, 2)] * n),
        "valid_to": to, "price_from": pa.array(lo, pa.float64()),
        "price_to": pa.array(hi, pa.float64()), "tick_size": pa.array(tick),
        "source": ["https://example.test/r"] * n, "verified": [False] * n,
    })  # fmt: skip


#: An `instrument_symbols` row of US:AAA's ticker: symbol, valid from and to, known from and
#: to (ISO dates, None: open). The two-time-axis kind since `classifications` left (#752).
Ticker = tuple[str, str, str | None, str, str | None]


def ticker_table(rows: list[Ticker]) -> pa.Table:
    def day(s: str | None) -> dt.date | None:
        return None if s is None else dt.date.fromisoformat(s)

    def ts(s: str | None) -> dt.datetime | None:
        return None if s is None else dt.datetime.fromisoformat(s).replace(tzinfo=dt.UTC)

    symbol, vf, vt, kf, kt = (list(c) for c in zip(*rows, strict=True))
    return pa.table({
        "instrument_id": ["US:AAA"] * len(rows), "symbol_type": ["ticker"] * len(rows),
        "symbol": symbol, "venue_mic": ["XNYS"] * len(rows),
        "valid_from": pa.array([day(d) for d in vf], pa.date32()),
        "valid_to": pa.array([day(d) for d in vt], pa.date32()),
        "ts_known_from": pa.array([ts(t) for t in kf], TS_UTC),
        "ts_known_to": pa.array([ts(t) for t in kt], TS_UTC),
    })  # fmt: skip


def _symbol_rows(*rows: Ticker) -> Change:
    table = ticker_table(list(rows))
    return _add("instrument_symbols", {name: table[name] for name in table.column_names})


#: TDS 6.3 ③'s pinned example 1: A, A2 (A's correction) and B; without A2, A is still known
#: when B is (T012).
_A = ("A", "2019-01-01", None, "2018-12-01", "2020-03-06")
_A2 = ("A", "2019-01-01", "2020-03-20", "2020-03-06", None)
_B = ("B", "2020-03-20", None, "2020-03-06", None)
DENSE = {"freq": "1d", "price_basis": "raw", "density": "dense", "bar_time": "session"}


def _dense(*days: int) -> Change:
    """Dense daily bars of US:AAA on `days` of January 2024, XNYS sessions on the 2nd and 3rd,
    `last_session` the 3rd (5.5 D001)."""
    n, on = len(days), pa.array([dt.date(2024, 1, d) for d in days])
    return _both(_sessions(0), _instruments(last_session=pa.array([dt.date(2024, 1, 3)])),
                 _set("params", DENSE, in_bars=True),
                 _bars(instrument_id=pa.array(["US:AAA"] * n), session_date=on,
                       close=pa.array([10.0] * n),
                       obs_status=pa.array(["traded"] * n)))  # fmt: skip


#: TDS 4.2's example `coverage`, as the base package's one bar makes it.
COVERAGE = {"instruments": 1, "ts_min": "2024-01-02", "ts_max": "2024-01-02",
            "by_market": {"US": {"instruments": 1, "first": "2024-01-02", "last": "2024-01-02",
                                 "rows": 1}}}  # fmt: skip


def _covered(rows: int = 1, **coverage: Any) -> Change:
    """The bars dataset's `rows` and `coverage` (COVERAGE with `coverage` changed)."""
    return lambda m, f: bars(m).update(rows=rows, coverage=COVERAGE | coverage)


def _processed(through: str) -> Change:
    """The bars processed through `through` in US (TDS 4.3), whose watermark session is the
    bar's day, 2024-01-02 (3.8)."""

    def change(m: dict[str, Any], files: Files) -> None:
        m["markets"]["US"]["complete_through_session"] = "2024-01-02"
        said = {"instruments": 1, "first": "2024-01-02", "last": "2024-01-02", "rows": 1,
                "processed_through_session": through}  # COVERAGE's US, and the field  # fmt: skip
        _covered(by_market={"US": said})(m, files)

    return change


WRONG = "0" * 64


def _hashes(code: str, wrong: bool) -> Change:
    """Write the hashes `code` compares into tds.json (TDS 4.5), the bars one `WRONG` if `wrong`."""

    def change(m: dict[str, Any], files: Files) -> None:
        from nexusbt_tds.hash import package_hashes  # the checker's own hashes, as producers use

        if code != "TDS-H001":  # a dictionary dataset is hashed like any other (TDS 4.4, 4.5)
            _codes(m, files)
        with tempfile.TemporaryDirectory() as tmp:
            hashes = package_hashes(write(Path(tmp), m, files))
        for ds in m["datasets"]:
            last = ds is bars(m) and wrong
            if code in ("TDS-H001", "TDS-H004"):  # the file's bytes, the file's rows (advisory)
                key = "sha256" if code == "TDS-H001" else "value_sha256"
                for f in ds["files"]:
                    f[key] = WRONG if last else hashes["files"][f["path"]][key]
            if code == "TDS-H002":
                ds["value_sha256"] = WRONG if last else hashes["datasets"][ds["name"]]
        if code == "TDS-H003":
            names = ("physical_sha256", "value_sha256", "semantic_sha256")
            m["hashes"].update({k: hashes[k] for k in names})
            if wrong:
                m["hashes"]["semantic_sha256"] = WRONG

    return change


#: The base bars' path partitions, declared (TDS 3.6, 4.5 step 6).
PARTITIONING = [{"name": "market", "type": "code"}, {"name": "year", "type": "i16"}]


def _partitioned(wrong: bool) -> Change:
    """Bars declared partitioned, with their `partitions[]` and `value_sha256` (TDS 4.2) from
    the checker's own hashes; the one partition's hash `WRONG` if `wrong` (H005)."""

    def change(m: dict[str, Any], files: Files) -> None:
        from nexusbt_tds.hash import package_hashes

        bars(m)["partitioning"] = PARTITIONING
        with tempfile.TemporaryDirectory() as tmp:
            hashes = package_hashes(write(Path(tmp), m, files))
        bars(m)["value_sha256"] = hashes["datasets"]["bars_1d"]
        bars(m)["partitions"] = hashes["partitions"]["bars_1d"]
        if wrong:
            bars(m)["partitions"][0]["value_sha256"] = WRONG

    return change


#: The base session's close, 2024-01-02 21:00Z, so that a bar's `ts_end` is its session's (T005).
TS = pa.array([dt.datetime(2024, 1, 2, 21, tzinfo=dt.UTC)], pa.timestamp("us", "UTC"))
VERSION_1_9 = {"tds.dataset": "bars_1d", "tds.schema_version": "1.9"}  # M011: the file says so too
THROUGH = dt.datetime(2024, 1, 2, 21, tzinfo=dt.UTC)  # `markets.US.complete_through` (TDS 3.8)


def _watermark(through: dt.datetime) -> Change:
    """US `complete_through` `through`, and the bar available at its `ts_end` (rule `ts_end`),
    THROUGH, its session's close (T005)."""

    def change(m: dict[str, Any], files: Files) -> None:
        m["markets"]["US"]["complete_through"] = through.isoformat().replace("+00:00", "Z")
        _bars(ts_end=pa.array([THROUGH], pa.timestamp("us", "UTC")))(m, files)

    return change


def _column_forms(*, complete: bool) -> Change:
    """`instrument_symbols` under `{"column": "ts_known_from"}` and `delistings` under
    `{"exit": …, "value": …}` (TDS 4.2, 6.2); `complete`: the delistings file holds
    `ts_value_available`, the second column its availability names, and the symbols file
    `ts_known_from`, the one column its availability names (T002 for each otherwise)."""

    def change(m: dict[str, Any], files: Files) -> None:
        known = pa.array([THROUGH], pa.timestamp("us", "UTC"))
        symbols = {"instrument_id": ["US:AAA"], "symbol_type": ["ticker"], "symbol": ["AAA"],
                   "valid_from": DAY}  # fmt: skip
        exits = {"delisting_id": ["US:L1"], "instrument_id": ["US:AAA"], "last_trading_date": DAY,
                 "exit_date": DAY, "ts_exit_known": known, "delist_type": ["merger"],
                 "ref_date": DAY, "ref_price": [10.0], "exit_value_status": ["observed"],
                 "ret_lo": [0.0], "ret_hi": [0.0], "policy_id": ["exit-value-v1"]}  # fmt: skip
        if complete:
            exits["ts_value_available"] = symbols["ts_known_from"] = known
        rewrite(m, files, INSTRUMENTS, instruments(delisted_on=DAY))  # R008: equal to exit_date
        forms = {
            "instrument_symbols": (symbols, {"column": "ts_known_from"}),
            "delistings": (exits, {"exit": "ts_exit_known", "value": "ts_value_available"}),
        }
        for name, (row, availability) in forms.items():
            rel = f"{name}/part-00000.parquet"
            files[rel] = parquet(pa.table(row), name)
            entry = {"path": rel, "rows": 1, "bytes": len(files[rel])}
            m["datasets"].append({"name": name, "kind": name, "schema_version": "1.0",
                                  "path": name, "availability": availability,
                                  "files": [entry]})  # fmt: skip

    return change


def _at(day: int, hour: int = 14, minute: int = 30) -> dt.datetime:
    return dt.datetime(2024, 1, day, hour, minute, tzinfo=dt.UTC)


def _ended(available: dt.datetime) -> Change:
    """US:AAA's bar ending at the 2nd's 21:00 close, available at `available` (rule `column`)."""
    end = pa.array([_at(2, 21, 0)])
    return _both(_set("availability", "column", in_bars=True),
                 _bars(ts_end=end, ts_available=pa.array([available], TS_UTC)))  # fmt: skip


#: TDS 5.11's columns the A codes read, with their types; a 2:1 split of US:AAA on 2024-01-03.
ACTION_TYPES = {"event_id": pa.string(), "instrument_id": pa.string(), "kind": pa.string(),
    "ex_date": pa.date32(), "ts_effective": TS_UTC, "pay_date_status": pa.string(),
    "ts_announced": TS_UTC, "ts_terms_available": TS_UTC, "ratio_num": pa.int64(),
    "ratio_den": pa.int64(), "ratio_new_per_old": pa.float64(), "new_instrument_id": pa.string(),
    "cash_per_share": pa.float64(), "price_factor": pa.float64(), "affects": pa.string(),
    "factor_method": pa.string(), "factor_ref_price": pa.float64(), "revision_of": pa.string(),
    "status": pa.string()}  # fmt: skip
SPLIT = {"event_id": "US:E1", "instrument_id": "US:AAA", "kind": "split",
    "ex_date": dt.date(2024, 1, 3), "ts_effective": _at(3), "pay_date_status": "missing",
    "ts_announced": NEW_YEAR, "ratio_num": 2, "ratio_den": 1, "ratio_new_per_old": 2.0,
    "price_factor": 0.5, "affects": "split_and_total", "factor_method": "ratio",
    "status": "effective"}  # fmt: skip


def action_table(rows: list[dict[str, Any]]) -> pa.Table:
    """`rows` as a `corporate_actions` table; `share_factor` only when a row sets it."""
    extra = {"share_factor": pa.float64()} if any("share_factor" in r for r in rows) else {}
    return pa.Table.from_pylist(rows, pa.schema(ACTION_TYPES | extra))


def _actions(
    *events: dict[str, Any], on: tuple[int, ...] = (2, 3), bars_on: tuple[int, ...] = (),
    with_bbb: bool = False,
) -> Change:  # fmt: skip
    """`events` (each a change of SPLIT) in `corporate_actions`, XNYS sessions on days `on` and
    US:AAA's bars on days `bars_on` (default `on`); `with_bbb` adds instrument US:BBB."""

    def change(m: dict[str, Any], files: Files) -> None:
        n = len(bars_on or on)
        rows = [SPLIT | e for e in events]
        _add("corporate_actions", action_table(rows))(m, files)
        _sessions(0, on)(m, files)
        days = pa.array([dt.date(2024, 1, d) for d in bars_on or on])
        _bars(instrument_id=pa.array(["US:AAA"] * n), session_date=days,
              close=pa.array([10.0] * n))(m, files)  # fmt: skip
        if with_bbb:
            bbb = instruments(instrument_id=pa.array(["US:BBB"]))
            rewrite(m, files, INSTRUMENTS, pa.concat_tables([instruments(), bbb]))

    return change


_REVISED = {"event_id": "US:E2", "revision_of": "US:E1"}
_DIVIDEND = {"kind": "cash_dividend", "cash_per_share": 1.0, "factor_ref_price": 10.0,
             "affects": "total_only", "factor_method": "cash_prev_close", "ratio_num": None,
             "ratio_den": None, "ratio_new_per_old": None}  # fmt: skip
_MERGER = {"kind": "stock_merger", "new_instrument_id": "US:BBB", "price_factor": 1.0,
           "affects": "none", "factor_method": "vendor"}  # fmt: skip
_SPINOFF = {"kind": "spinoff", "new_instrument_id": "US:BBB", "price_factor": 0.8,
            "affects": "total_only", "factor_method": "spinoff_first_close"}  # fmt: skip
_EXIT_DIVIDEND = _actions(_DIVIDEND | {"price_factor": 0.9}, bars_on=(2,))


def _fx(rate: float) -> Change:
    """One USD/KRW fixing at `rate` (5.15)."""
    return _add("fx_rates", {
        "base": ["USD"], "quote": ["KRW"], "rate_kind": ["fixing"], "obs_date": DAY,
        "ts_event": pa.array([NEW_YEAR], TS_UTC), "ts_available": pa.array([NEW_YEAR], TS_UTC),
        "rate": [rate], "source": ["synthetic"],
    })  # fmt: skip


def _traded(volume: float) -> Change:
    """The bar at 10.0 with `value_traded` 1000: `volume` 100 is in shares, 1 in lots of 100."""
    ten = pa.array([10.0])
    return _bars(high=ten, low=ten, volume=pa.array([volume]), value_traded=pa.array([1000.0]))


def _future(**columns: Any) -> Change:
    """US:AAA as a future (5.1) with `columns`."""
    return _instruments(asset_class=pa.array(["future"]), **columns)


_FUTURE = {"root": pa.array(["AA"]), "ts_expiry": pa.array([NEW_YEAR], TS_UTC),
           "settlement_type": pa.array(["cash"])}  # fmt: skip

#: Code → (pass change, fail change). M005, M011 and S005 are warnings: their fail package warns.
VALUE_PARTITIONING = [{"name": "market", "type": "code"}, {"name": "item", "type": "code"}]


def _valued(*placed: tuple[str, str]) -> Change:
    """Value tables (TDS 5.28): per (kind, item), US:AAA's one row of 2024-01-02 at
    `<kind>/market=US/item=<item>/`, with `partitions[]` and `value_sha256` from the checker's
    own hashes (4.2), so that only the item names are judged."""
    tables = {
        "values": {"instrument_id": ["US:AAA"], "date": DAY, "value": [1.0]},
        "market_values": {"date": DAY, "value": [1.0]},
        "symbol_values": {"instrument_id": ["US:AAA"], "value": [1.0]},
    }

    def change(m: dict[str, Any], files: Files) -> None:
        from nexusbt_tds.hash import package_hashes

        entries: dict[str, dict[str, Any]] = {}
        for kind, item in placed:
            rel, table = f"{kind}/market=US/item={item}/part-00000.parquet", pa.table(tables[kind])
            files[rel] = parquet(table, kind)
            entry = entries.setdefault(kind, {
                "name": kind, "kind": kind, "schema_version": "1.0", "path": kind,
                "partitioning": VALUE_PARTITIONING, "files": []})  # fmt: skip
            entry["files"].append({"path": rel, "rows": 1, "bytes": len(files[rel])})
        m["datasets"] += entries.values()
        with tempfile.TemporaryDirectory() as tmp:
            hashes = package_hashes(write(Path(tmp), m, files))
        for entry in entries.values():
            entry["partitions"] = hashes["partitions"][entry["name"]]
            entry["value_sha256"] = hashes["datasets"][entry["name"]]

    return change


CASES: dict[str, tuple[Change, Change]] = {
    "TDS-M001": (_keep, lambda m, f: m.clear()),  # `[]` is written, see write()
    "TDS-M002": (_set("tds_version", "1.4"), _set("tds_version", "2.0")),
    "TDS-M003": (_keep, _both(lambda m, f: m.pop("snapshot_id"), _markets_without)),
    "TDS-M004": (_keep, lambda m, f: f.pop(BARS)),
    "TDS-M005": (_keep, lambda m, f: f.update({"notes.txt": b"not listed\n"})),
    "TDS-M006": (_keep, lambda m, f: f.update({BARS: f[BARS] + b"!"})),
    "TDS-M007": (
        _set("profiles", ["tds:minimal-daily"]),
        _set("profiles", ["tds:no-such-profile@1.0"]),
    ),
    "TDS-M008": (  # minimal-daily without `calendar_sessions` (C3, #705)
        _set("profiles", ["tds:minimal-daily@1.0", "tds:fx@1.0"]),
        _both(no_calendar, _set("profiles", ["tds:minimal-daily@1.0"])),
    ),
    "TDS-M009": (
        _set("schema_version", "1.0", in_bars=True),
        _set("schema_version", "2.0", in_bars=True),
    ),
    "TDS-M010": (  # a `market=` path, and from `schema` on an instruments row (8.2, #567)
        _keep,
        _both(
            _move_bars(BARS.replace("market=US", "market=ZZ")),
            _instruments(market=pa.array(["ZZ"])),
        ),
    ),
    "TDS-M011": (
        _set("schema_version", "1.0", in_bars=True),
        lambda m, f: (_set("schema_version", "1.9", in_bars=True)(m, f), _bars(VERSION_1_9)(m, f)),
    ),
    "TDS-M012": (_move_bars(BARS.replace("year=", "./year=")), _move_bars("../outside.parquet")),
    "TDS-M013": (_keep, lambda m, f: bars(m)["files"].append(dict(bars(m)["files"][0]))),
    "TDS-M014": (
        _set("availability", {"rule": "ts_end+PT15M"}, in_bars=True),
        _both(  # an unknown rule name, and an object that is none of 6.2's forms (#276)
            _set("availability", {"rule": "ts_end_when_ready"}, in_bars=True),
            lambda m, f: m["datasets"][0].update(availability={"known": "ts_known_from"}),
        ),
    ),
    "TDS-M016": (_processed("2024-01-02"), _processed("2024-01-01")),  # rows after it (#192)
    "TDS-M017": (_keep, _set("tds_draft", "2026-11-13")),  # an older draft text (#529)
    # TDS 5.28 (#752): an item name outside 3.1's rule; one item in two value tables
    "TDS-M018": (_valued(("values", "per_ttm")), _valued(("values", "PER"))),
    "TDS-M019": (
        _valued(("values", "per"), ("market_values", "base_rate")),
        _valued(("values", "per"), ("market_values", "per")),
    ),
    "TDS-S001": (_bars(ts_end=TS), _bars(session_date=None)),
    "TDS-S002": (_keep, _bars(close=pa.array(["10.0"]))),
    "TDS-S003": (
        lambda m, f: rewrite(m, f, INSTRUMENTS, instruments(name=pa.array([None], pa.string()))),
        lambda m, f: rewrite(
            m, f, INSTRUMENTS, instruments(multiplier=pa.array([None], pa.float64()))
        ),
    ),
    "TDS-S004": (_bars(ts_end=TS), _bars(ts_end=TS.cast(pa.timestamp("us")))),
    "TDS-S005": (  # an `x_` column, then one with no `x_`
        _bars(x_cf_note=pa.array(["a"])),
        _bars(note=pa.array(["a"])),
    ),
    "TDS-S006": (  # bars' `obs_status`: `asset_class` is open since #705 B3
        _keep,
        _bars(obs_status=pa.array(["trade"])),
    ),
    "TDS-S007": (
        _instruments(codes=True, category=pa.array(["ordinary"])),
        _instruments(category=pa.array(["ordinary"])),
    ),
    "TDS-S008": (_keep, _bars(market=pa.array(["US"]))),
    "TDS-S009": (_bars(vwap=pa.array([-1e300])), _bars(vwap=pa.array([math.inf]))),  # no V001
    "TDS-S011": (  # two bars files of the same columns; then one with value_traded, an id twice
        _two_bars(),
        _both(_two_bars(value_traded=pa.array([1000.0])), _id_twice),
    ),
    "TDS-S010": (
        _keep,  # `tds.dataset` is the dataset's name, `bars_1d` (TDS 3.7)
        _bars(meta={"tds.dataset": "bars", "tds.schema_version": "1.0"}),  # the kind, not the name
    ),
    "TDS-T002": (_column_forms(complete=True), _column_forms(complete=False)),
    "TDS-T006": (_watermark(THROUGH), _watermark(THROUGH - dt.timedelta(microseconds=1))),
    "TDS-T001": (  # available at the bar's end, then a second before it
        _ended(_at(2, 21, 0)),
        _ended(_at(2, 20, 59)),
    ),
    "TDS-T005": (  # XNYS on the 2nd: 14:30 to 21:00
        _both(_sessions(0), _bars(ts_start=pa.array([_at(2)]), ts_end=pa.array([_at(2, 21, 0)]))),
        _both(_sessions(0), _bars(ts_start=pa.array([_at(2)]), ts_end=pa.array([_at(2, 20, 0)]))),
    ),
    "TDS-T003": (  # tick bands that meet, then overlap
        _rules((0.0, 1.0, 0.0001), (1.0, None, 0.01)),
        _rules((0.0, 1.0, 0.0001), (0.5, None, 0.01)),
    ),
    "TDS-T004": (  # valid one day, then ending where it starts
        _rules((0.0, None, 0.01), until=dt.date(2024, 1, 3)),
        _rules((0.0, None, 0.01), until=dt.date(2024, 1, 2)),
    ),
    "TDS-T012": (_symbol_rows(_A, _A2, _B), _symbol_rows((*_A[:4], None), _B)),
    "TDS-T010": (
        _instruments(last_session=DAY),
        _instruments(last_session=pa.array([dt.date(2024, 1, 1)])),
    ),
    "TDS-T011": (
        _exits(delisted=True, ts_exit_known=_at(2), ts_value_available=_at(2)),
        _exits(delisted=True, ts_exit_known=_at(2), ts_value_available=_at(2, 14, 0)),
    ),
    "TDS-D002": (  # before listed_on, on a session (R003)
        _keep,
        _both(_sessions(0, (1, 2, 3)), _bars(session_date=pa.array([dt.date(2024, 1, 1)]))),
    ),
    "TDS-D001": (_dense(2, 3), _dense(2)),  # the 3rd missing
    "TDS-D003": (_exited(_at(2, 21, 0)), _exited(_at(3))),  # known after the 2nd's close (#425)
    "TDS-D004": (_covered(), _covered(instruments=2)),
    "TDS-K001": (_bars_on(2, 3), _bars_on(2, 2)),  # US:AAA's bar on the 2nd twice
    "TDS-K002": (_bars_on(2, 3), _bars_on(3, 2)),
    "TDS-K003": (  # a 2025 session's bar in the year=2024 file
        _keep,
        _both(
            _sessions(0, (2, 3), years=(2024, 2025)),
            _instruments(listed_on=pa.array([dt.date(2025, 1, 2)])),  # no 2024 row is due: D001
            _bars(session_date=pa.array([dt.date(2025, 1, 2)])),
        ),
    ),
    "TDS-K004": (_ranged("2024-01-03T00-00-00Z"), _ranged("2024-01-02T12-00-00Z")),
    "TDS-K010": (_symbols(dt.date(2024, 6, 3)), _symbols(dt.date(2024, 6, 1))),
    "TDS-K011": (_sessions(0), _sessions(1)),
    "TDS-R001": (_keep, _bars(instrument_id=pa.array(["US:ZZZ"]))),
    "TDS-R002": (_sessions(0), _both(_sessions(0), _instruments(calendar_id=pa.array(["XKRX"])))),
    "TDS-R003": (  # 2024-01-03 lies between the sessions, so it is not D002's
        _sessions(0, (2, 4)),
        _both(_sessions(0, (2, 4)), _bars(session_date=pa.array([dt.date(2024, 1, 3)]))),
    ),
    "TDS-R004": (_crypto(True), _crypto(False)),
    "TDS-R005": (
        _instruments(venue_mic=pa.array(["XNYS"])),
        _instruments(venue_mic=pa.array(["xnys"])),
    ),
    "TDS-R006": (
        _instruments(underlying_instrument_id=pa.array(["US:AAA"])),
        _instruments(underlying_instrument_id=pa.array(["US:ZZZ"])),
    ),
    "TDS-R008": (_exits(delisted=True), _exits(delisted=False)),  # an exit, no delisted_on
    "TDS-A003": (
        _actions({"price_factor": None, "factor_method": "unavailable"}),
        _actions({"price_factor": None}),
    ),
    "TDS-A004": (  # 1 - 1.0/10.0 = 0.9
        _actions(_DIVIDEND | {"price_factor": 0.9}),
        _actions(_DIVIDEND | {"price_factor": 0.95}),
    ),
    "TDS-A005": (  # sessions on the 2nd and 4th: the 3rd is no session
        _actions({"ex_date": dt.date(2024, 1, 4), "ts_effective": _at(4)}, on=(2, 4)),
        _actions({}, on=(2, 4)),
    ),
    "TDS-A006": (
        _actions(_MERGER, with_bbb=True),
        _actions(_MERGER | {"new_instrument_id": None}, with_bbb=True),
    ),
    "TDS-A007": (
        _actions({}, _REVISED),
        _actions({"revision_of": "US:E2"}, _REVISED),
    ),
    "TDS-A008": (
        _actions({"ts_terms_available": _at(2)}),
        _actions({"ts_terms_available": _at(3, 15)}),  # after the 14:30 open it takes effect
    ),
    "TDS-A009": (  # the 3rd's close is 21:00; a spinoff is no A008, its share count stays
        _actions(_SPINOFF | {"ts_terms_available": _at(3, 21, 0)}, with_bbb=True),
        _actions(_SPINOFF | {"ts_terms_available": _at(3, 20, 0)}, with_bbb=True),
    ),
    "TDS-A010": (  # missing, one-sided, zero, 1/8 against ratio_new_per_old 2.0
        _actions({"share_factor": 2.0}),
        _actions(
            {"ratio_num": None, "ratio_den": None},
            {"event_id": "US:E2", "ratio_den": None},
            {"event_id": "US:E3", "ratio_num": 0},
            {"event_id": "US:E4", "ratio_num": 1, "ratio_den": 8},
        ),
    ),
    "TDS-A011": (  # a dividend on the 3rd, after the last trading day, the 2nd
        _both(_exits(delisted=True, includes=True), _EXIT_DIVIDEND),
        _both(_exits(delisted=True), _EXIT_DIVIDEND),
    ),
    "TDS-V001": (
        _bars(open=pa.array([10.0]), high=pa.array([11.0]), low=pa.array([9.0])),
        _bars(open=pa.array([10.0]), high=pa.array([11.0]), low=pa.array([10.5])),
    ),
    "TDS-V002": (
        _both(_instruments(asset_class=pa.array(["index"])), _bars(close=pa.array([-1.0]))),
        _bars(close=pa.array([-1.0])),
    ),
    "TDS-V004": (_no_close("halted"), _no_close("traded")),
    "TDS-V005": (_fx(1400.0), _fx(0.0)),
    "TDS-V010": (_bars(volume=pa.array([2.0])), _bars(volume=pa.array([2.5]))),
    "TDS-V011": (_traded(100.0), _traded(1.0)),  # R = 1000 / (volume * 10): 1, then 100
    "TDS-V012": (  # a tick of 0.0001: f64 jitter within 1e-9 relative, then half a tick off
        _both(
            _instruments(tick_size=pa.array([0.0001])), _bars(close=pa.array([0.6768000000000001]))
        ),
        _both(_instruments(tick_size=pa.array([0.0001])), _bars(close=pa.array([0.67685]))),
    ),
    "TDS-V020": (_future(**_FUTURE), _future(**_FUTURE | {"root": None})),
    "TDS-V040": (_exits(delisted=True, ret_lo=-0.5), _exits(delisted=True, ret_lo=0.5)),
    **{
        code: (_hashes(code, False), _hashes(code, True))
        for code in ("TDS-H001", "TDS-H002", "TDS-H003", "TDS-H004")
    },
    "TDS-H005": (_partitioned(False), _partitioned(True)),
}

#: Code → the datasets its fail package breaks: the checker reports that code once for each,
#: and nothing else (TDS 8.2: one failing example per code, which may break several datasets).
#: `None`: a finding of the package as a whole.
# fmt: off
FAILS: dict[str, tuple[str | None, ...]] = {
    **dict.fromkeys([
        "TDS-M001", "TDS-M002", "TDS-M005", "TDS-M007", "TDS-M008", "TDS-R008",
        "TDS-H003", "TDS-M017",
    ], (None,)),
    "TDS-M003": (None,) * 4,  # snapshot_id, and a market without each of its three fields
    "TDS-S011": ("instruments", "bars_1d"),
    **dict.fromkeys([
        "TDS-M004", "TDS-M006", "TDS-M009", "TDS-M010", "TDS-M011", "TDS-M012", "TDS-M013",
        "TDS-S001", "TDS-S002", "TDS-S004", "TDS-S005", "TDS-S008", "TDS-S009", "TDS-S010",
        "TDS-T006", "TDS-D002", "TDS-K002", "TDS-K003", "TDS-K004", "TDS-R001", "TDS-R003",
        "TDS-H001", "TDS-H002", "TDS-H004", "TDS-H005", "TDS-S006",
    ], ("bars_1d",)),
    **dict.fromkeys([
        "TDS-S003", "TDS-S007", "TDS-R002", "TDS-R004", "TDS-R005", "TDS-R006",
    ], ("instruments",)),
    "TDS-M014": ("bars_1d", "instruments"),  # the unknown rule, the unknown object
    "TDS-M016": ("bars_1d",),
    "TDS-M018": ("values",),
    "TDS-M019": ("market_values",),  # named on the second table holding the item
    "TDS-T002": ("delistings", "instrument_symbols"),  # the two-instant form, the one-column
    **dict.fromkeys(["TDS-D001", "TDS-D004"], ("bars_1d",)),
    **dict.fromkeys(["TDS-T001", "TDS-T005", "TDS-K001"], ("bars_1d",)),
    "TDS-T010": ("instruments",),
    "TDS-T011": ("delistings",),
    "TDS-D003": ("delistings",),
    **dict.fromkeys(["TDS-T003", "TDS-T004"], ("market_rules",)),
    "TDS-T012": ("instrument_symbols",),
    "TDS-K010": ("instrument_symbols",),
    "TDS-K011": ("calendar_sessions",),
    **dict.fromkeys(
        [f"TDS-A00{n}" for n in range(3, 10)], ("corporate_actions",)
    ),
    "TDS-A010": ("corporate_actions",) * 4,  # one finding per way a ratio is wrong
    "TDS-A011": ("delistings",),
    **dict.fromkeys(
        ["TDS-V001", "TDS-V002", "TDS-V004", "TDS-V010", "TDS-V011", "TDS-V012"], ("bars_1d",)
    ),
    "TDS-V005": ("fx_rates",),
    "TDS-V020": ("instruments",),
    "TDS-V040": ("delistings",),
}
# fmt: on
#: Code → the datasets its fail package breaks from the `schema` level on, where they differ
#: from `FAILS`: that level reads rows the `manifest` level does not (TDS 8.2).
AT_SCHEMA: dict[str, tuple[str | None, ...]] = {"TDS-M010": ("bars_1d", "instruments")}


def package(code: str, side: str) -> Package:
    manifest, files = base()
    CASES[code][side == "fail"](manifest, files)
    return manifest, files


def write(root: Path, manifest: dict[str, Any], files: Files) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    text = json.dumps(manifest, sort_keys=True) if manifest else "[]"  # one line: a small diff
    (root / "tds.json").write_text(text + "\n", encoding="utf-8")
    for rel, content in sorted(files.items()):
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_bytes(content)
    return root


def build(out: Path) -> None:
    for code in CASES:
        for side in ("pass", "fail"):
            shutil.rmtree(out / code / side, ignore_errors=True)
            write(out / code / side, *copy.deepcopy(package(code, side)))


if __name__ == "__main__":
    build(Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent)
