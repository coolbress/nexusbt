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
DAY = pa.array([dt.date(2024, 1, 2)])


def instruments(**columns: pa.Array | None) -> pa.Table:
    """One `instruments` row with the non-null columns (TDS 5.1); a column `None` is left out."""
    base = {"instrument_id": ["US:AAA"], "asset_class": ["equity"], "market": ["US"],
            "calendar_id": ["XNYS"], "currency": ["USD"], "listed_on": DAY, "lot_size": [1.0],
            "multiplier": [1.0], "is_synthetic": [False]}  # fmt: skip
    return pa.table({k: v for k, v in (base | columns).items() if v is not None})


def bars_table(**columns: pa.Array | None) -> pa.Table:
    """One daily bar (TDS 5.5); a column `None` is left out."""
    base = {"instrument_id": pa.array(["US:AAA"]), "session_date": DAY, "close": pa.array([10.0])}
    return pa.table({k: v for k, v in (base | columns).items() if v is not None})


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
    """A package that passes the manifest and schema levels: `tds:minimal-daily@1.0`."""
    files = {
        INSTRUMENTS: parquet(instruments(), "instruments"),
        BARS: parquet(bars_table(), "bars_1d"),
    }
    bars_1d = {"params": {"freq": "1d", "price_basis": "raw"}, "availability": {"rule": "ts_end"}}
    datasets: list[tuple[str, str, str, str, dict[str, Any]]] = [
        ("instruments", "instruments", "instruments", INSTRUMENTS, {}),
        ("bars_1d", "bars", "bars/freq=1d", BARS, bars_1d),
    ]
    manifest = {
        "tds_version": "1.0",
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
            | {"files": [{"path": file, "rows": 1, "bytes": len(files[file])}]}
            for name, kind, path, file, extra in datasets
        ],
        "hashes": {"hash_spec": "tds-hash-1"},
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


def _panels(*editions: str) -> Change:
    """US:AAA's January 2024 row of feature panel `f`, a file per edition folder (5.25)."""
    folder = "feature_panels/name=f/edition={}/year=2024/part-{:05}.parquet"
    paths = [folder.format(e, n) for n, e in enumerate(editions)]
    row = {"instrument_id": ["US:AAA"], "period": pa.array([dt.date(2024, 1, 1)])}
    row |= {"as_of_date": pa.array([dt.date(2023, 12, 29)])}
    row |= {"ts_available": pa.array([NEW_YEAR], TS_UTC)}

    def change(m: dict[str, Any], files: Files) -> None:
        m["editions"] = {"default": "strict", "values": {"strict": "s", "compare": "c"}}
        _add("feature_panels", row, *paths)(m, files)

    return change


def _gics(*levels: int) -> Change:
    """US:AAA's GICS rows at `levels`, all effective 2024-01-02 and known 2024-01-01 (5.19)."""
    n = len(levels)
    return _add("classifications", {
        "instrument_id": ["US:AAA"] * n, "scheme": ["gics"] * n,
        "level": pa.array(levels, pa.int8()), "code": [f"c{i}" for i in range(n)],
        "effective_from": pa.array([dt.date(2024, 1, 2)] * n),
        "ts_known_from": pa.array([NEW_YEAR] * n, TS_UTC), "edition": ["both"] * n,
        "pit_quality": ["native"] * n, "source": ["synthetic"] * n,
    })  # fmt: skip


def _bars_on(*days: int) -> Change:
    """US:AAA's daily bars on these days of January 2024, in that order."""
    columns = {"session_date": pa.array([dt.date(2024, 1, d) for d in days])}
    n = len(days)
    return _bars(instrument_id=pa.array(["US:AAA"] * n), close=pa.array([10.0] * n), **columns)


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


def _sessions(first: int, on: tuple[int, int] = (2, 3)) -> Change:
    """XNYS sessions on days `on` of January 2024 numbered from `first` (TDS 5.4)."""
    days = [dt.datetime(2024, 1, d, tzinfo=dt.UTC) for d in on]
    return _add("calendar_sessions", {
        "calendar_id": ["XNYS"] * 2, "session_date": pa.array([d.date() for d in days]),
        "ts_open": pa.array([d.replace(hour=14, minute=30) for d in days], TS_UTC),
        "ts_close": pa.array([d.replace(hour=21) for d in days], TS_UTC),
        "session_ord": pa.array([first, first + 1], pa.int32()), "session_kind": ["regular"] * 2,
    })  # fmt: skip


def _both(*changes: Change) -> Change:
    return lambda m, f: [change(m, f) for change in changes]


def _crypto(declared: bool) -> Change:
    """Instruments in USDT, outside ISO 4217; `declared` lists it in tds.json `currencies`."""
    usdt = [{"code": "USDT", "kind": "crypto", "decimals": 2}] if declared else []
    return _both(_instruments(currency=pa.array(["USDT"])), _set("currencies", usdt))


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
            if code == "TDS-H001":
                for f in ds["files"]:
                    f["sha256"] = WRONG if last else hashes["files"][f["path"]]["sha256"]
            if code == "TDS-H002":
                ds["value_sha256"] = WRONG if last else hashes["datasets"][ds["name"]]
        if code == "TDS-H003":
            names = ("physical_sha256", "value_sha256", "semantic_sha256")
            m["hashes"].update({k: hashes[k] for k in names})
            if wrong:
                m["hashes"]["semantic_sha256"] = WRONG

    return change


TS = pa.array([0], pa.timestamp("us", "UTC"))
VERSION_1_9 = {"tds.dataset": "bars_1d", "tds.schema_version": "1.9"}  # M011: the file says so too
THROUGH = dt.datetime(2024, 1, 2, 21, tzinfo=dt.UTC)  # `markets.US.complete_through` (TDS 3.8)


def _watermark(ts_end: dt.datetime) -> Change:
    """US `complete_through` THROUGH, and the bar available at its `ts_end` (rule `ts_end`)."""

    def change(m: dict[str, Any], files: Files) -> None:
        m["markets"]["US"]["complete_through"] = THROUGH.isoformat().replace("+00:00", "Z")
        _bars(ts_end=pa.array([ts_end], pa.timestamp("us", "UTC")))(m, files)

    return change


def _column_forms(*, complete: bool) -> Change:
    """`instrument_symbols` under `{"column": "ts_known_from"}` and `delistings` under
    `{"exit": …, "value": …}` (TDS 4.2, 6.2); `complete`: the delistings file holds
    `ts_value_available`, the second column its availability names (T002 otherwise)."""

    def change(m: dict[str, Any], files: Files) -> None:
        known = pa.array([THROUGH], pa.timestamp("us", "UTC"))
        symbols = {"instrument_id": ["US:AAA"], "symbol_type": ["ticker"], "symbol": ["AAA"],
                   "valid_from": DAY, "ts_known_from": known}  # fmt: skip
        exits = {"delisting_id": ["US:L1"], "instrument_id": ["US:AAA"], "last_trading_date": DAY,
                 "exit_date": DAY, "ts_exit_known": known, "delist_type": ["merger"],
                 "ref_date": DAY, "ref_price": [10.0], "exit_value_status": ["observed"],
                 "ret_lo": [0.0], "ret_hi": [0.0], "policy_id": ["exit-value-v1"]}  # fmt: skip
        if complete:
            exits["ts_value_available"] = known
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


#: Code → (pass change, fail change). M005, M011 and S005 are warnings: their fail package warns.
CASES: dict[str, tuple[Change, Change]] = {
    "TDS-M001": (_keep, lambda m, f: m.clear()),  # `[]` is written, see write()
    "TDS-M002": (_set("tds_version", "1.4"), _set("tds_version", "2.0")),
    "TDS-M003": (_keep, lambda m, f: m.pop("snapshot_id")),
    "TDS-M004": (_keep, lambda m, f: f.pop(BARS)),
    "TDS-M005": (_keep, lambda m, f: f.update({"notes.txt": b"not listed\n"})),
    "TDS-M006": (_keep, lambda m, f: f.update({BARS: f[BARS] + b"!"})),
    "TDS-M007": (
        _set("profiles", ["tds:minimal-daily"]),
        _set("profiles", ["tds:no-such-profile@1.0"]),
    ),
    "TDS-M008": (
        _set("profiles", ["tds:minimal-daily@1.0", "tds:fx@1.0"]),
        _set("profiles", ["tds:minimal-daily@1.0", "tds:alt-events@1.0"]),
    ),
    "TDS-M009": (
        _set("schema_version", "1.0", in_bars=True),
        _set("schema_version", "2.0", in_bars=True),
    ),
    "TDS-M010": (_keep, _move_bars(BARS.replace("market=US", "market=ZZ"))),
    "TDS-M011": (
        _set("schema_version", "1.0", in_bars=True),
        lambda m, f: (_set("schema_version", "1.9", in_bars=True)(m, f), _bars(VERSION_1_9)(m, f)),
    ),
    "TDS-M012": (_move_bars(BARS.replace("year=", "./year=")), _move_bars("../outside.parquet")),
    "TDS-M013": (_keep, lambda m, f: bars(m)["files"].append(dict(bars(m)["files"][0]))),
    "TDS-M014": (
        _set("availability", {"rule": "ts_end+PT15M"}, in_bars=True),
        _set("availability", {"rule": "ts_end_when_ready"}, in_bars=True),
    ),
    "TDS-S001": (_bars(ts_end=TS), _bars(session_date=None)),
    "TDS-S002": (_keep, _bars(close=pa.array(["10.0"]))),
    "TDS-S003": (
        lambda m, f: rewrite(m, f, INSTRUMENTS, instruments(name=pa.array([None], pa.string()))),
        lambda m, f: rewrite(
            m, f, INSTRUMENTS, instruments(lot_size=pa.array([None], pa.float64()))
        ),
    ),
    "TDS-S004": (_bars(ts_end=TS), _bars(ts_end=TS.cast(pa.timestamp("us")))),
    "TDS-S005": (_bars(x_cf_note=pa.array(["a"])), _bars(note=pa.array(["a"]))),
    "TDS-S006": (
        _instruments(asset_class=pa.array(["etf"])),
        _instruments(asset_class=pa.array(["stock"])),
    ),
    "TDS-S007": (
        _instruments(codes=True, category=pa.array(["ordinary"])),
        _instruments(category=pa.array(["ordinary"])),
    ),
    "TDS-S008": (_keep, _bars(market=pa.array(["US"]))),
    "TDS-S009": (_bars(close=pa.array([-1e300])), _bars(close=pa.array([math.inf]))),
    "TDS-S010": (
        _keep,  # `tds.dataset` is the dataset's name, `bars_1d` (TDS 3.7)
        _bars(meta={"tds.dataset": "bars", "tds.schema_version": "1.0"}),  # the kind, not the name
    ),
    "TDS-T002": (_column_forms(complete=True), _column_forms(complete=False)),
    "TDS-T006": (_watermark(THROUGH), _watermark(THROUGH + dt.timedelta(microseconds=1))),
    "TDS-D002": (_keep, _bars(session_date=pa.array([dt.date(2024, 1, 1)]))),  # before listed_on
    "TDS-K001": (  # GICS sector and industry on one day (5.19), a key in two editions: no K001
        lambda m, f: (_gics(1, 3)(m, f), _panels("strict", "compare")(m, f)),
        _panels("strict", "strict"),  # one key twice in one folder
    ),
    "TDS-K002": (_bars_on(2, 3), _bars_on(3, 2)),
    "TDS-K003": (_keep, _bars(session_date=pa.array([dt.date(2025, 1, 2)]))),  # in year=2024
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
    **{
        code: (_hashes(code, False), _hashes(code, True))
        for code in ("TDS-H001", "TDS-H002", "TDS-H003")
    },
}


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
