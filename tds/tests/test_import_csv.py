"""TDS 9.5: `import_csv(mapping, out)` writes a package that `tds check` accepts (#257)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pyarrow.parquet as pq
import pytest

from nexusbt_tds import check, import_csv
from nexusbt_tds.cli import main
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
#: An equity's daily bars with all of OHLCV, as core requires them (#705 Decisions 37);
#: minimal-daily asks close alone (#705, 2026-11-22).
WHOLE = """instrument_id,session_date,open,high,low,close,volume
XNYS:AAPL,2024-01-02,187.15,188.44,183.89,185.64,82488700
"""
COUNT = BARS.replace("volume\n", "volume,trade_count\n").replace("82488700\n", "82488700,{}\n")
#: TDS chapter 7's two CSVs; the market and price basis that 7 gives as flags, here in the mapping,
#: with the regular hours the import builds `calendar_sessions` from (#705 Decisions 59).
HOURS = ', open: "09:30", close: "16:00"'
MINIMAL = ("profiles: [tds:minimal-daily@1.0]\n"
           "market: {code: US, calendar_id: XNYS, currency: USD, timezone: America/New_York"
           + HOURS + "}\n"
           "datasets:\n  instruments:\n    file: instruments.csv\n  bars:\n    file: bars.csv\n"
           "    params: {freq: 1d, price_basis: total_adjusted}\n")  # fmt: skip


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
        "bars.csv": "﻿code,date,open,high,low,종가,거래량,note\n"  # a spreadsheet's byte-order mark
                    "AAPL,20240103,184,185,183,184.25,-,\n"
                    "AAPL,20240102,185,186,184,185.64,82488700,x\n",
        "mapping.yaml": """# a comment line
name: "demo: a colon inside quotes"
profiles: ["tds:minimal-daily@1.0"]
market:
  code: US
  calendar_id: XNYS
  currency: USD
  timezone: America/New_York
  open: "09:30"
  close: "16:00"
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
               "market": {"code": "US", "calendar_id": "XNYS", "currency": "USD",
                          "timezone": "America/New_York"},
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
    files = {"instruments.csv": INSTRUMENTS, "mapping.yaml": MINIMAL}
    write(tmp_path / "a", files | {"mapping.yaml": mapping,
                                   "bars.csv": bars.format("2024-01-02T16:00:00")})  # fmt: skip
    with pytest.raises(CsvImportError, match=r"the market's `timezone` is missing"):  # #567
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
        (("market: {code: US, ", "market: {"), BARS, "the market's `code` is missing or not"),
        (("currency: USD, ", ""), BARS, "the market's `currency` is missing or not"),  # #567
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
        (("America/New_York", "[UTC]"), BARS, "the market's `timezone` is missing or not"),
        (("", ""), "instrument_id,close\nXNYS:AAPL,1\n", "no column for session_date, the sort"),
        (("", ""), BARS + "XNYS:AAPL,,1,2\n", "year= partition needs one or more rows"),
        (("", ""), BARS.splitlines()[0] + "\n", "year= partition needs one or more rows"),
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


@pytest.mark.parametrize("tag", ["list<code>", "json", "fixed"])
def test_a_type_csv_does_not_carry_is_not_imported(tag: str) -> None:
    """No kind the import takes has such a column since `trades` left (#752); it still stops."""
    from nexusbt_tds.import_csv import _value

    with pytest.raises(CsvImportError, match=re.escape(f"a {tag} column is not imported")):
        _value("X", tag, {}, {}, "t.csv line 2")


def test_package_defaults_and_layout(tmp_path: Path) -> None:
    """TDS 9: no availability time invented; TDS 3.6 partitions; a folder never written over."""
    mapping = write(tmp_path, {"instruments.csv": INSTRUMENTS, "bars.csv": WHOLE,
                               "mapping.yaml": MINIMAL})  # fmt: skip
    out = import_csv(mapping, tmp_path / "pkg")
    assert rows(out, "instruments")[0]["is_synthetic"] is False
    manifest = json.loads((out / "tds.json").read_text(encoding="utf-8"))
    assert manifest["tds_draft"] == "2026-11-27"  # TDS 4.2 (#529; #752 12e)
    bars = next(d for d in manifest["datasets"] if d["kind"] == "bars")
    assert (bars["pit_quality"], bars["availability"]) == ("backfilled", {"rule": "ts_end"})
    assert bars["files"][0]["path"] == "bars/freq=1d/market=US/year=2024/part-00000.parquet"
    # the folders declared, so 4.5 step 6 hashes them, and each partition listed (#725 203)
    assert [p["name"] for p in bars["partitioning"]] == ["market", "year"]
    assert [p["values"] for p in bars["partitions"]] == [["US", 2024]]
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


#: TDS chapter 7's `instruments.csv` as it stands, without the three 5.1 columns the fills give.
CHAPTER_7 = "\n".join(",".join(r.split(",")[:6]) for r in INSTRUMENTS.splitlines()) + "\n"


def test_minimal_two_csv(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """When I run `tds import csv` on the two CSVs of TDS chapter 7 and then `tds check --level
    full`, then I see it pass with the profile's three results."""
    mapping = write(tmp_path, {"instruments.csv": CHAPTER_7, "bars.csv": WHOLE,
                               "mapping.yaml": MINIMAL})  # fmt: skip
    out = tmp_path / "pkg"
    assert main(["import", "csv", str(mapping), "--out", str(out)]) == 0
    assert f"wrote {out} and {tmp_path / 'import_report.json'}" in capsys.readouterr().out
    assert main(["check", str(out), "--level", "full"]) == 0
    printed = capsys.readouterr().out
    assert "tds:minimal-daily@1.0: declared, verified to schema, not_checked" in printed
    assert "0 errors, 0 warnings at level full" in printed
    manifest = json.loads((out / "tds.json").read_text(encoding="utf-8"))
    bars = next(d for d in manifest["datasets"] if d["kind"] == "bars")
    assert bars["params"] == {
        "freq": "1d",
        "price_basis": "total_adjusted",  # the user's fact
        "bar_time": "session",
        "density": "dense",
    }  # the kind's (#705 C5)
    said = json.loads((tmp_path / "import_report.json").read_text(encoding="utf-8"))
    assert [a for a in said["datasets"]["bars"]["assumed"] if a.startswith("params.")] == [
        "params.bar_time session (a daily bar of the market's session, TDS 5.5)",
        "params.density dense (the import writes a row on each session, TDS 5.5)",
    ]
    assert manifest["markets"]["US"]["timezone"] == "America/New_York"
    assert rows(out, "bars")[0]["close"] == 185.64
    # an import that cannot be read: exit 1 and the reason, no traceback
    assert main(["import", "csv", str(mapping), "--out", str(out)]) == 1
    assert "tds import csv: " in capsys.readouterr().err


@pytest.mark.parametrize("status", ["", ",obs_status"], ids=["close", "close and obs_status"])
def test_a_close_only_equity_passes_minimal_daily(
    status: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """When a stock's price file holds close only and the mapping declares minimal-daily, then
    `tds import csv` and `tds check --level full` pass: the profile asks close alone of every
    row, an equity's too (#705, 2026-11-22), and V004 asks no more of it."""
    bars = f"instrument_id,session_date,close{status}\nXNYS:AAPL,2024-01-02,185.64"
    bars += ",traded\n" if status else "\n"
    mapping = write(tmp_path, {"instruments.csv": CHAPTER_7, "bars.csv": bars,
                               "mapping.yaml": MINIMAL})  # fmt: skip
    out = tmp_path / "pkg"
    assert main(["import", "csv", str(mapping), "--out", str(out)]) == 0
    assert main(["check", str(out), "--level", "full"]) == 0
    printed = capsys.readouterr().out
    assert "tds:minimal-daily@1.0: declared, verified to schema, not_checked" in printed
    assert "0 errors, 0 warnings at level full" in printed
    assert ("obs_status" in rows(out, "bars")[0]) == bool(status)
    assert [r["source"] for r in rows(out, "calendar_sessions")] == ["inferred_from_bar_dates"]


def test_the_calendar_is_built_from_the_bars_dates_and_the_declared_hours(tmp_path: Path) -> None:
    """#705 Decisions 59: a session on each date a bar has, at the market's declared hours in its
    time zone (winter and summer, UTC offsets -5 and -4), nothing else invented; the hours are
    the mapping's, not `markets`'."""
    bars = BARS + "XNYS:AAPL,2024-07-01,210.0,1\n"
    out = import_csv(write(tmp_path, {"instruments.csv": CHAPTER_7, "bars.csv": bars,
                                      "mapping.yaml": MINIMAL}), tmp_path / "pkg")  # fmt: skip
    days = rows(out, "calendar_sessions")
    found = [(str(r["session_date"]), str(r["ts_open"]), str(r["ts_close"])) for r in days]
    assert found == [
        ("2024-01-02", "2024-01-02 14:30:00+00:00", "2024-01-02 21:00:00+00:00"),
        ("2024-07-01", "2024-07-01 13:30:00+00:00", "2024-07-01 20:00:00+00:00"),
    ]
    kinds = {(r["session_kind"], r["is_half_day"], r["source"]) for r in days}
    assert kinds == {("regular", None, "inferred_from_bar_dates")}
    assert "session_ord" not in days[0]
    manifest = json.loads((out / "tds.json").read_text(encoding="utf-8"))
    assert {"open", "close"}.isdisjoint(manifest["markets"]["US"])
    assert check(out, level="full").error_count == 0


def test_the_bars_own_times_make_their_days_sessions(tmp_path: Path) -> None:
    """#705 Decisions 59 (the review of 6-0): a day the bars give `ts_start` and `ts_end` takes
    them, a half day too, so that TDS-T005 holds; a day they give none takes the declared hours;
    `ts_end` alone takes it and the declared open."""
    bars = ("instrument_id,session_date,close,volume,ts_start,ts_end\n"
            "XNYS:AAPL,2024-07-03,221.0,1,2024-07-03T13:30:00Z,2024-07-03T17:00:00Z\n"
            "XNYS:AAPL,2024-07-05,222.0,1,,2024-07-05T19:00:00Z\n"
            "XNYS:AAPL,2024-07-08,223.0,1,,\n")  # fmt: skip
    out = import_csv(write(tmp_path, {"instruments.csv": CHAPTER_7, "bars.csv": bars,
                                      "mapping.yaml": MINIMAL}), tmp_path / "pkg")  # fmt: skip
    found = [(str(r["ts_open"])[11:16], str(r["ts_close"])[11:16])
             for r in rows(out, "calendar_sessions")]  # fmt: skip
    assert found == [("13:30", "17:00"), ("13:30", "19:00"), ("13:30", "20:00")]
    assert check(out, level="full").error_count == 0
    two = bars.replace("XNYS:AAPL,2024-07-08,223.0,1,,", "XNYS:MSFT,2024-07-03,400.0,1,,"
                       "2024-07-03T20:00:00Z")  # fmt: skip
    instruments = CHAPTER_7 + "XNYS:MSFT,equity,US,XNYS,USD,1986-03-13\n"
    other = write(tmp_path / "two", {"instruments.csv": instruments, "bars.csv": two,
                                     "mapping.yaml": MINIMAL})  # fmt: skip
    with pytest.raises(CsvImportError, match="the bars of 2024-07-03 give two ts_end values, "
                       "2024-07-03T17:00:00"):  # fmt: skip
        import_csv(other, tmp_path / "two" / "pkg")


def test_a_calendar_block_without_source_stops(tmp_path: Path) -> None:
    """TDS 5.4 and 9.5 (#705 Decisions 69): `source` is written; the import makes none up."""
    block = "  calendar_sessions:\n    file: sessions.csv\n"
    sessions = "calendar_id,session_date,ts_open,ts_close,session_kind\n" + (
        "XNYS,2024-07-01,2024-07-01T13:30:00Z,2024-07-01T20:00:00Z,regular\n")  # fmt: skip
    files = {"instruments.csv": CHAPTER_7, "bars.csv": BARS, "sessions.csv": sessions}
    mapping = write(tmp_path, files | {"mapping.yaml": MINIMAL + block})
    with pytest.raises(CsvImportError, match=r"sessions\.csv: no column for source"):
        import_csv(mapping, tmp_path / "pkg")


def test_a_dataset_named_calendar_sessions_of_another_kind_stops(tmp_path: Path) -> None:
    # the review of 6-0: the calendar the import writes would take the same name
    named = MINIMAL.replace("  bars:\n    file", "  calendar_sessions:\n    kind: bars\n    file")
    mapping = write(tmp_path, {"instruments.csv": CHAPTER_7, "bars.csv": BARS,
                               "mapping.yaml": named})  # fmt: skip
    with pytest.raises(CsvImportError, match="is not of kind calendar_sessions"):
        import_csv(mapping, tmp_path / "pkg")


WRITE = "write the regular session's hours in the market's local time, `close` the latest"


@pytest.mark.parametrize(("hours", "said"), [
    ("", WRITE), (', open: "9:30", close: "16:00"', WRITE),
    (', open: "16:00", close: "09:30"', "the market's `open` is not before its `close`"),
], ids=["none", "H:MM", "late"])  # fmt: skip
def test_a_mapping_without_hours_stops_saying_what_to_write(
    hours: str, said: str, tmp_path: Path
) -> None:
    # #705 Decisions 59: no hours, or hours not read, stop the import before anything is written
    mapping = write(tmp_path, {"instruments.csv": CHAPTER_7, "bars.csv": BARS,
                               "mapping.yaml": MINIMAL.replace(HOURS, hours)})  # fmt: skip
    with pytest.raises(CsvImportError, match=re.escape(said)):
        import_csv(mapping, tmp_path / "pkg")
    assert not (tmp_path / "pkg").exists()


def test_a_kind_typed_by_105_is_imported(tmp_path: Path) -> None:
    """`tradability_daily` (5.10) had columns of no type, which "is not imported from CSV"."""
    status = ("instrument_id,session_date,status_known,halt_count,ts_available,source\n"
              "XNYS:AAPL,2024-01-02,true,2,2024-01-03T00:00:00Z,exchange\n")  # fmt: skip
    mapping = write(tmp_path, {"instruments.csv": CHAPTER_7, "bars.csv": WHOLE,
                               "status.csv": status,
                               "mapping.yaml": MINIMAL + "  tradability_daily:\n"
                               "    file: status.csv\n"
                               "    availability: {column: ts_available}\n"})  # fmt: skip
    out = tmp_path / "pkg"
    assert main(["import", "csv", str(mapping), "--out", str(out)]) == 0
    assert not check(out, level="full").errors
    assert rows(out, "tradability_daily")[0]["halt_count"] == 2


def test_import_report_written(tmp_path: Path) -> None:
    bars = BARS.replace("volume\n", "volume,note\n").replace("82488700\n", "82488700,x\n")
    mapping = write(tmp_path, {"instruments.csv": CHAPTER_7, "bars.csv": bars,
                               "mapping.yaml": MINIMAL})  # fmt: skip
    out = import_csv(mapping, tmp_path / "pkg")
    report = json.loads((tmp_path / "import_report.json").read_text(encoding="utf-8"))
    assert (report["package"], report["mapping"]) == ("pkg", "mapping.yaml")
    assert not (out / "import_report.json").exists()  # next to the package, not in it (TDS 9)
    entry = report["datasets"]["bars"]
    assert (entry["rows_read"], entry["rows_kept"], entry["rows_dropped"]) == (1, 1, 0)
    assert entry["columns_dropped"] == ["note"]  # not a TDS column: reported, not kept
    assert entry["columns_kept"]["close"] == "close"
    assert "pit_quality = backfilled" in " ".join(entry["assumed"])
    assert "availability rule ts_end" in " ".join(entry["assumed"])
    # decision 7: each manifest default the mapping does not give is named
    assert [a.split(":")[0] for a in report["assumed"]] == ["name", "snapshot_id", "id_namespaces"]
    filled = report["datasets"]["instruments"]["assumed"]
    assert [a.split(" ")[0] for a in filled] == ["multiplier", "is_synthetic", "pit_quality"]
    got = rows(out, "instruments")[0]
    assert (got["multiplier"], got["is_synthetic"]) == (1.0, False)
    assert "lot_size" not in got  # not known: never written as 1 (TDS 5.1, #705 Decisions 12)


def test_values_and_fills(tmp_path: Path) -> None:
    """A constant in `values` wins over the CSV and over a fill; an `asset_class` the fills do
    not name gets none and stays TDS-S001; an index is synthetic."""
    given = "file: instruments.csv\n    values: {lot_size: '100', is_synthetic: 'false'}\n"
    files = {"instruments.csv": CHAPTER_7.replace("equity", "bond"), "bars.csv": BARS,
             "mapping.yaml": MINIMAL.replace("file: instruments.csv\n", given)}  # fmt: skip
    package = import_csv(write(tmp_path / "v", files), tmp_path / "v" / "pkg")
    got = rows(package, "instruments")[0]
    assert (got["lot_size"], got["is_synthetic"], "multiplier" in got) == (100.0, False, False)
    assert {f.code for f in check(package, level="schema").errors} == {"TDS-S001"}
    report = json.loads((tmp_path / "v" / "import_report.json").read_text(encoding="utf-8"))
    assert report["datasets"]["instruments"]["values"] == {"lot_size": "100",
                                                          "is_synthetic": "false"}  # fmt: skip
    index = {"instruments.csv": CHAPTER_7.replace("equity", "index"), "mapping.yaml": MINIMAL}
    package = import_csv(write(tmp_path / "i", index | {"bars.csv": BARS}), tmp_path / "i" / "p")
    assert rows(package, "instruments")[0]["is_synthetic"] is True
    us = {"code": "US", "calendar_id": "XNYS", "currency": "USD", "timezone": "America/New_York"}
    as_json = {"market": us, "datasets": {"instruments": {
        "file": "instruments.csv", "values": {"is_synthetic": True, "lot_size": 10}}}}  # fmt: skip
    (tmp_path / "i" / "m.json").write_text(json.dumps(as_json), encoding="utf-8")
    package = import_csv(tmp_path / "i" / "m.json", tmp_path / "i" / "j" / "p")
    assert (rows(package, "instruments")[0]["is_synthetic"], rows(package, "instruments")[0][
        "lot_size"]) == (True, 10.0)  # fmt: skip
    bad = write(tmp_path / "x", files | {"mapping.yaml": MINIMAL.replace(
        "file: instruments.csv\n", "file: instruments.csv\n    values: {nope: x}\n")})  # fmt: skip
    with pytest.raises(CsvImportError, match=r"datasets\.instruments\.values: unknown nope"):
        import_csv(bad, tmp_path / "x" / "p")


def test_format_names_the_way_out(tmp_path: Path) -> None:
    """TDS 9.5: a `format` must write the value back as read; the error says what to do."""
    ts = MINIMAL.replace(IN_BARS, "    columns: {ts_end: {format: '%Y-%m-%dT%H:%M:%S%z'}}\n"
                         + IN_BARS)  # fmt: skip
    path = write(tmp_path, {"instruments.csv": INSTRUMENTS, "mapping.yaml": ts,
                            "bars.csv": TS.format("2024-01-02T16:00:00+00:00")})  # fmt: skip
    way_out = (
        "is not a ts_us/ns: format '%Y-%m-%dT%H:%M:%S%z' writes it back as "
        "'2024-01-02T16:00:00+0000'; write the value in RFC 3339 (a date as YYYY-MM-DD) and "
        "drop `format`, or give a `format` that writes it back character for character"
    )
    with pytest.raises(CsvImportError, match=re.escape(way_out)):
        import_csv(path, tmp_path / "pkg")
    write(tmp_path, {"bars.csv": TS.format("2024-01-02T16:00:00+0000")})
    assert str(rows(import_csv(path, tmp_path / "ok"), "bars")[0]["ts_end"]).startswith(
        "2024-01-02 16:00:00")  # fmt: skip


def test_report_never_lands_on_an_input(tmp_path: Path) -> None:
    """A report beside the package never replaces the mapping file or a CSV, nor a folder;
    a `values` constant that is not one value is refused, never written as `'None'`."""
    market = {"code": "US", "calendar_id": "XNYS", "currency": "USD", "timezone": "UTC"}
    as_json = {"profiles": [], "market": market,
               "datasets": {"instruments": {"file": "instruments.csv"}}}  # fmt: skip
    write(tmp_path, {"instruments.csv": CHAPTER_7})
    (tmp_path / "import_report.json").write_text(json.dumps(as_json), encoding="utf-8")
    with pytest.raises(CsvImportError, match="is an input or not a file"):
        import_csv(tmp_path / "import_report.json", tmp_path / "pkg")
    assert json.loads((tmp_path / "import_report.json").read_text("utf-8")) == as_json
    (tmp_path / "d" / "import_report.json").mkdir(parents=True)
    (tmp_path / "d" / "m.json").write_text(json.dumps(as_json), encoding="utf-8")
    write(tmp_path / "d", {"instruments.csv": CHAPTER_7})
    with pytest.raises(CsvImportError, match="is an input or not a file"):
        import_csv(tmp_path / "d" / "m.json", tmp_path / "d" / "pkg")
    assert not (tmp_path / "d" / "pkg").exists()  # refused before writing
    # `profiles: []` gets the default, and the report says so
    out = import_csv(tmp_path / "d" / "m.json", tmp_path / "d" / "e" / "pkg")
    report = json.loads((out.parent / "import_report.json").read_text("utf-8"))
    assert report["assumed"][2].startswith('profiles: ["tds:minimal-daily@1.0"]')
    for constant in (None, [1], {"a": 1}):
        as_json["datasets"] = {"instruments": {"file": "instruments.csv",
                                               "values": {"currency": constant}}}  # fmt: skip
        (tmp_path / "d" / "m.json").write_text(json.dumps(as_json), encoding="utf-8")
        with pytest.raises(CsvImportError, match="currency is text, a number or a bool"):
            import_csv(tmp_path / "d" / "m.json", tmp_path / "d" / "f" / "pkg")


#: Three instruments over 2024-01-02..05 (#705 Decisions 112, 113): AAPL listed long before,
#: a gap on the 4th; MSFT listed on the 3rd, one bar on the 4th; CENS listed on its first bar
#: (`listed_on_censored`, its listing day not known), a gap on the 4th.
GAPS_INSTRUMENTS = """instrument_id,asset_class,market,calendar_id,currency,listed_on,\
listed_on_censored,lot_size,multiplier,is_synthetic
XNYS:AAPL,equity,US,XNYS,USD,1980-12-12,false,1,1,false
XNYS:MSFT,equity,US,XNYS,USD,2024-01-03,false,1,1,false
XNYS:CENS,equity,US,XNYS,USD,2024-01-03,true,1,1,false
"""
GAPS_BARS = """instrument_id,session_date,close,volume
XNYS:AAPL,2024-01-02,10,1
XNYS:AAPL,2024-01-03,11,1
XNYS:AAPL,2024-01-05,12,1
XNYS:MSFT,2024-01-04,20,1
XNYS:CENS,2024-01-03,30,1
XNYS:CENS,2024-01-05,31,1
"""


def filled(package: Path) -> list[tuple[object, str]]:
    return sorted((r["instrument_id"], str(r["session_date"])) for r in rows(package, "bars")
                  if r.get("obs_status") == "missing")  # fmt: skip


def test_the_import_fills_a_row_on_each_session_an_instrument_lacks(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """When an instrument has no bar on a session of the calendar, from the later of its
    listed_on and the first session to the last date the market's bars have, then a row with
    obs_status missing and no value is written, and the report counts them."""
    mapping = write(tmp_path, {"instruments.csv": GAPS_INSTRUMENTS, "bars.csv": GAPS_BARS,
                               "mapping.yaml": MINIMAL})  # fmt: skip
    package = tmp_path / "pkg"
    assert main(["import", "csv", str(mapping), "--out", str(package)]) == 0
    assert "; 4 missing session rows filled (see the report)" in capsys.readouterr().out
    four = [("XNYS:AAPL", "2024-01-04"), ("XNYS:CENS", "2024-01-04"),
            ("XNYS:MSFT", "2024-01-03"), ("XNYS:MSFT", "2024-01-05")]  # fmt: skip
    assert filled(package) == four
    # CENS: listed_on is its first bar (censored), so nothing before the 3rd
    assert ("XNYS:CENS", "2024-01-02") not in filled(package)
    missing = [r for r in rows(package, "bars") if r["obs_status"] == "missing"]
    assert {r["close"] for r in missing} == {None}
    assert {r["volume"] for r in missing} == {None}
    assert {r["obs_status"] for r in rows(package, "bars")} == {None, "missing"}  # not made up
    said = json.loads((tmp_path / "import_report.json").read_text(encoding="utf-8"))
    bars = said["datasets"]["bars"]
    assert (bars["rows_read"], bars["rows_kept"], bars["rows_filled"]) == (6, 6, 4)
    assert len(rows(package, "bars")) == 10
    assert any(a.startswith("1 instruments stopped before 2024-01-05 and have no last_session")
               for a in bars["assumed"])  # fmt: skip
    # the import's end is D001's: an instrument with no end runs to the last session a row of
    # its market has, so the stopped one is judged, and passes (TDS 5.5, #705 Decisions 134)
    result = check(package, level="full")
    assert (result.errors, "TDS-D001" in result.unchecked) == ((), False)


def test_daily_bars_without_a_price_basis_are_refused(tmp_path: Path) -> None:
    """Only the user knows how the prices are adjusted (TDS 5.5, #705 C5), so a mapping that
    does not say stops, naming the three values; no package is written."""
    files = {"instruments.csv": GAPS_INSTRUMENTS, "bars.csv": GAPS_BARS,
             "mapping.yaml": MINIMAL.replace(", price_basis: total_adjusted}", "}")}  # fmt: skip
    with pytest.raises(CsvImportError, match=r"price_basis is missing.*raw .*split_adjusted"):
        import_csv(write(tmp_path, files), tmp_path / "pkg")
    assert not (tmp_path / "pkg").exists()


def test_daily_bars_declared_sparse_are_refused(tmp_path: Path) -> None:
    """Daily bars are dense and the import writes a row on each session (TDS 5.5), so a
    mapping that declares them sparse stops, saying what to write; no package is written."""
    sparse = MINIMAL.replace("total_adjusted}", "total_adjusted, density: sparse}")
    files = {"instruments.csv": GAPS_INSTRUMENTS, "bars.csv": GAPS_BARS, "mapping.yaml": sparse}
    with pytest.raises(CsvImportError, match=r"daily bars are dense.*write density: dense"):
        import_csv(write(tmp_path, files), tmp_path / "pkg")
    assert not (tmp_path / "pkg").exists()


def test_last_session_stops_the_fill_and_complete_through_extends_it(tmp_path: Path) -> None:
    """A user's last_session ends an instrument's rows there; a user's complete_through runs
    them to its date over the given calendar, where without it they stop at the last bar."""
    instruments = GAPS_INSTRUMENTS.replace("is_synthetic\n", "is_synthetic,last_session\n")
    instruments = instruments.replace("1,1,false\n", "1,1,false,\n").replace(
        "XNYS:MSFT,equity,US,XNYS,USD,2024-01-03,false,1,1,false,",
        "XNYS:MSFT,equity,US,XNYS,USD,2024-01-03,false,1,1,false,2024-01-04")  # fmt: skip
    sessions = "calendar_id,session_date,ts_open,ts_close,session_kind\n" + "".join(
        f"XNYS,2024-01-0{d},2024-01-0{d}T14:30:00Z,2024-01-0{d}T21:00:00Z,regular\n"
        for d in (2, 3, 4, 5, 8))  # fmt: skip
    block = "  calendar_sessions:\n    file: sessions.csv\n    values: {source: exchange}\n"
    dense = MINIMAL.replace("total_adjusted}", "total_adjusted, density: dense}")
    through = dense.replace(HOURS, ', complete_through: "2024-01-08T21:00:00Z"') + block
    # dense bars hold obs_status on every row: the source's rows say it, the import never does
    traded = GAPS_BARS.replace("volume\n", "volume,obs_status\n").replace(",1\n", ",1,traded\n")
    files = {"instruments.csv": instruments, "bars.csv": traded, "sessions.csv": sessions}
    package = import_csv(write(tmp_path, files | {"mapping.yaml": through}), tmp_path / "pkg")
    assert filled(package) == [("XNYS:AAPL", "2024-01-04"), ("XNYS:AAPL", "2024-01-08"),
                               ("XNYS:CENS", "2024-01-04"), ("XNYS:CENS", "2024-01-08"),
                               ("XNYS:MSFT", "2024-01-03")]  # fmt: skip
    result = check(package, level="full")  # dense, with an end: D001 judges and passes
    assert [f.code for f in result.errors] == []
    assert "TDS-D001" not in result.unchecked
    naive = through.replace("21:00:00Z", "21:00:00")  # read in no host's time zone
    with pytest.raises(CsvImportError, match="is not an RFC 3339 instant with an offset"):
        import_csv(write(tmp_path / "n", files | {"mapping.yaml": naive}), tmp_path / "n" / "p")
    nameless = GAPS_BARS + ",2024-01-04,5,1\n"  # an id left empty: the checker's S003, no crash
    files |= {"bars.csv": nameless, "mapping.yaml": MINIMAL}
    package = import_csv(write(tmp_path / "e", files), tmp_path / "e" / "pkg")
    assert filled(package) == []
    assert "TDS-S003" in [f.code for f in check(package, level="schema").errors]
