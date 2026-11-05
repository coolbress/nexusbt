"""TDS 9.5: `import_csv(mapping, out)` writes a package that `tds check` accepts (#257)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pyarrow.parquet as pq
import pytest

from nexusbt_tds import check, import_csv
from nexusbt_tds.import_csv import CsvImportError

#: TDS chapter 7's `instruments.csv` with the three columns 5.1 requires that it leaves out; the
#: importer's fills for them come with the next part of #257 (decision 3).
INSTRUMENTS = """instrument_id,asset_class,market,calendar_id,currency,listed_on,lot_size,\
multiplier,is_synthetic
XNYS:AAPL,equity,US,XNYS,USD,1980-12-12,1,1,false
"""
BARS = """instrument_id,session_date,close,volume
XNYS:AAPL,2024-01-02,185.64,82488700
"""
COUNT = BARS.replace("volume\n", "volume,trade_count\n").replace("82488700\n", "82488700,{}\n")
#: TDS chapter 7's two CSVs; the market and price basis that 7 gives as flags, here in the mapping.
MINIMAL = """profiles: [tds:minimal-daily@1.0]
market: {code: US, calendar_id: XNYS, currency: USD, timezone: America/New_York}
datasets:
  instruments:
    file: instruments.csv
  bars:
    file: bars.csv
    params: {freq: 1d, price_basis: total_adjusted}
"""


def write(folder: Path, files: dict[str, str]) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        (folder / name).write_text(text, encoding="utf-8")
    return folder / "mapping.yaml"


def rows(package: Path, dataset: str) -> list[dict[str, object]]:
    manifest = json.loads((package / "tds.json").read_text(encoding="utf-8"))
    (entry,) = (d for d in manifest["datasets"] if d["name"] == dataset)
    return [r for f in entry["files"] for r in pq.read_table(package / f["path"]).to_pylist()]


def test_mapping_template_and_format(tmp_path: Path) -> None:
    mapping = write(tmp_path, {
        "instruments.csv": INSTRUMENTS,
        "bars.csv": "﻿code,date,종가,거래량,note\n"  # a spreadsheet's byte-order mark
                    "AAPL,20240103,184.25,-,\nAAPL,20240102,185.64,82488700,x\n",
        "mapping.yaml": """# a comment line
name: "demo: a colon inside quotes"
profiles: ["tds:minimal-daily@1.0"]
market: {code: US, calendar_id: XNYS, currency: USD, timezone: America/New_York}
datasets:
  instruments:
    file: instruments.csv
  bars:
    file: bars.csv   # a comment after a value
    params: {freq: 1d, price_basis: 'raw'}
    missing_values: ["-"]
    columns:
      instrument_id: {from: code, template: "XNYS:{value}"}
      session_date: {from: date, format: "%Y%m%d"}
      close:
        from: 종가
      volume: {from: 거래량}
""",
    })  # fmt: skip
    out = import_csv(mapping, tmp_path / "pkg")
    got = rows(out, "bars")
    assert [(r["instrument_id"], str(r["session_date"]), r["volume"]) for r in got] == [
        ("XNYS:AAPL", "2024-01-02", 82488700.0),  # sorted by session_date (TDS 5.5)
        ("XNYS:AAPL", "2024-01-03", None),  # `-` is missing only because the mapping says so
    ]
    assert check(out, level="full").error_count == 0
    name = json.loads((out / "tds.json").read_text("utf-8"))["name"]
    assert name == "demo: a colon inside quotes"
    # JSON is YAML too, and is read first
    as_json = {"profiles": ["tds:minimal-daily@1.0"],
               "market": {"code": "US", "calendar_id": "XNYS", "currency": "USD"},
               "datasets": {"instruments": {"file": "instruments.csv"}}}  # fmt: skip
    (tmp_path / "m.json").write_text(json.dumps(as_json), encoding="utf-8")
    assert rows(import_csv(tmp_path / "m.json", tmp_path / "json"), "instruments")
    as_json["datasets"] = {"instruments": {"file": "instruments.csv",
                                           "columns": {"listed_on": {"format": 5}}}}  # fmt: skip
    (tmp_path / "m.json").write_text(json.dumps(as_json), encoding="utf-8")
    with pytest.raises(CsvImportError, match=r"listed_on: format is text"):  # not a TypeError
        import_csv(tmp_path / "m.json", tmp_path / "json5")
    # outside the subset: an error naming the line, never a guess
    (tmp_path / "anchor.yaml").write_text("profiles: &p [x]\n", encoding="utf-8")
    with pytest.raises(CsvImportError, match=r"line 1: .*write this part as JSON"):
        import_csv(tmp_path / "anchor.yaml", tmp_path / "anchor")


def test_offsetless_time_requires_timezone(tmp_path: Path) -> None:
    bars = "instrument_id,session_date,close,ts_end\nXNYS:AAPL,2024-01-02,185.64,{}\n"
    mapping = MINIMAL.replace(", timezone: America/New_York", "")
    files = {"instruments.csv": INSTRUMENTS, "mapping.yaml": mapping}
    write(tmp_path / "a", files | {"bars.csv": bars.format("2024-01-02T16:00:00")})
    with pytest.raises(CsvImportError, match=r"bars.csv line 2: ts_end .* needs a timezone"):
        import_csv(tmp_path / "a" / "mapping.yaml", tmp_path / "a" / "pkg")
    write(tmp_path / "b", files | {"bars.csv": bars.format("2024-01-02T16:00:00-05:00")})
    out = import_csv(tmp_path / "b" / "mapping.yaml", tmp_path / "b" / "pkg")
    assert str(rows(out, "bars")[0]["ts_end"]) == "2024-01-02 21:00:00+00:00"
    write(tmp_path / "t", files | {"bars.csv": bars.format("2024-01-02t16:00:00-05:00")})
    out = import_csv(tmp_path / "t" / "mapping.yaml", tmp_path / "t" / "pkg")  # RFC 3339's `t`
    assert str(rows(out, "bars")[0]["ts_end"]) == "2024-01-02 21:00:00+00:00"
    # with the market's timezone, a local time is read in it; one in a DST overlap is S004
    write(tmp_path / "c", {**files, "mapping.yaml": MINIMAL, "bars.csv": bars.format(
        "2024-01-02T16:00:00") + "XNYS:AAPL,2024-11-03,1,2024-11-03T01:30:00\n"})  # fmt: skip
    with pytest.raises(CsvImportError, match=r"line 3: .*daylight-saving overlap \(TDS-S004\)"):
        import_csv(tmp_path / "c" / "mapping.yaml", tmp_path / "c" / "pkg")
    write(tmp_path / "d", {**files, "mapping.yaml": MINIMAL, "bars.csv": bars.format(
        "2024-03-10T02:30:00")})  # fmt: skip  # a skipped hour: never shifted (#257 decision 6)
    with pytest.raises(CsvImportError, match=r"line 2: .*daylight-saving gap"):
        import_csv(tmp_path / "d" / "mapping.yaml", tmp_path / "d" / "pkg")


TS = "instrument_id,session_date,close,ts_end\nXNYS:AAPL,2024-01-02,1,{}\n"
IN_BARS = "    params:"  # where a key is put into the bars block
DATE = "    columns: {session_date: {format: '%Y%m%d'}}\n" + IN_BARS


def key(text: str) -> tuple[str, str]:
    return IN_BARS, f"    {text}\n{IN_BARS}"


@pytest.mark.parametrize(
    ("change", "bars", "error"),
    [
        (("market: {code: US, ", "market: {"), BARS, "`market` needs at least a `code`"),
        ((MINIMAL[MINIMAL.index("datasets:") :], "datasets: {}\n"), BARS, "`datasets` needs one"),
        (("  instruments:\n    file: instruments.csv\n", "  instruments: x\n"), BARS, "is not a"),
        (key("files: x"), BARS, "datasets.bars: unknown files"),
        (key("kind: nope"), BARS, "kind 'nope' has no TDS schema file"),
        (key("columns: [close]"), BARS, "datasets.bars.columns is not a block"),
        (key("columns: {close: x}"), BARS, "datasets.bars.columns.close is not a block"),
        (key("columns: {nope: {from: close}}"), BARS, "datasets.bars.columns: unknown nope"),
        (key("columns: {close: {from: price}}"), BARS, "bars.csv: no column for close"),
        (("{freq: 1d, price_basis: total_adjusted}", "x"), BARS, "params is not a block"),
        (("file: bars.csv", "file: gone.csv"), BARS, "datasets.bars: [Errno 2]"),
        (("", ""), BARS + "XNYS:AAPL,2024-01-03\n", "line 3: 2 fields, the header has 4"),
        (("", ""), BARS.replace("185.64", "abc"), "'abc' is not a f64"),
        (("", ""), BARS.replace("82488700", "1_000"), "'1_000' is not a f64"),
        (("", ""), BARS.replace("185.64", " 5"), "' 5' is not a f64"),
        (("", ""), COUNT.format("1.5"), "'1.5' is not a i64"),
        (("", ""), COUNT.format("9223372036854775808"), "is not a i64"),
        ((IN_BARS, DATE), BARS.replace("2024-01-02", "2024013"), "'2024013' is not a date"),
        (("", ""), BARS.replace("2024-01-02", "20240102"), "'20240102' is not a date"),
        (("", ""), BARS.replace("2024-01-02", "2024-W01-2"), "'2024-W01-2' is not a date"),
        (("America/New_York", "[UTC]"), BARS, "the market's `timezone` is text"),
        (("", ""), "instrument_id,close\nXNYS:AAPL,1\n", "no column for session_date, the sort"),
        (("", ""), BARS + "XNYS:AAPL,,1,2\n", "year= partition needs one or more rows"),
        (("", ""), BARS.splitlines()[0] + "\n", "year= partition needs one or more rows"),
        (key("kind: trades"), "conditions\nX\n", "a list<code> column is not imported"),
        (key("kind: events"), "value\n1\n", "partition event_type= is not imported"),
        (key("missing_values: NA"), BARS, "missing_values is a list"),
        (("", ""), TS.format("2024-01-02"), "'2024-01-02' is not a ts_us"),  # not RFC 3339
        (("", ""), TS.format("2024-01-02T21:00:00.123456789Z"), "is not a ts_us"),  # below us
        (("", ""), BARS.replace("volume", "close"), "column close given twice"),
        (
            ("    params:", "    columns: {instrument_id: {template: X}}\n    params:"),
            BARS,
            "template needs {value}",
        ),
        (("    file: bars.csv\n", ""), BARS, "datasets.bars: `file` is missing"),
        (("freq: 1d, ", ""), BARS, "partitions for params.freq None"),  # not guessed
        (("America/New_York", "Mars/Base"), TS.format("2024-01-02T16:00:00"), "unknown timezone"),
    ],
)
def test_input_that_cannot_be_read_stops(
    tmp_path: Path, change: tuple[str, str], bars: str, error: str
) -> None:
    path = write(tmp_path, {"instruments.csv": INSTRUMENTS, "bars.csv": bars,
                            "mapping.yaml": MINIMAL.replace(*change)})  # fmt: skip
    with pytest.raises(CsvImportError, match=re.escape(error)):
        import_csv(path, tmp_path / "pkg")
    assert not (tmp_path / "pkg").exists()  # stopped before writing anything


def test_package_defaults_and_layout(tmp_path: Path) -> None:
    """TDS 9: no availability time invented; TDS 3.6 partitions; a folder never written over."""
    mapping = write(tmp_path, {"instruments.csv": INSTRUMENTS, "bars.csv": BARS,
                               "mapping.yaml": MINIMAL})  # fmt: skip
    out = import_csv(mapping, tmp_path / "pkg")
    assert rows(out, "instruments")[0]["is_synthetic"] is False
    manifest = json.loads((out / "tds.json").read_text(encoding="utf-8"))
    bars = next(d for d in manifest["datasets"] if d["kind"] == "bars")
    assert (bars["pit_quality"], bars["availability"]) == ("backfilled", {"rule": "ts_end"})
    assert bars["files"][0]["path"] == "bars/freq=1d/market=US/year=2024/part-00000.parquet"
    assert check(out, level="full").error_count == 0
    with pytest.raises(CsvImportError, match="not empty"):  # never writes over a folder
        import_csv(mapping, out)
    counted = write(tmp_path / "n", {"instruments.csv": INSTRUMENTS, "bars.csv": COUNT.format(5),
                                     "mapping.yaml": MINIMAL})  # fmt: skip
    assert rows(import_csv(counted, tmp_path / "n" / "pkg"), "bars")[0]["trade_count"] == 5
    # a header-only, unpartitioned CSV: one file of no rows
    empty = write(tmp_path / "e", {"instruments.csv": INSTRUMENTS.splitlines()[0] + "\n",
                                   "mapping.yaml": MINIMAL.split("  bars:")[0]})  # fmt: skip
    assert rows(import_csv(empty, tmp_path / "e" / "pkg"), "instruments") == []
