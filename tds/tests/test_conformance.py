"""TDS 8.5 / spec 8.4a: per code, the fail package raises only that code, the pass package none."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from nexusbt_tds import ProfileStatus, check, keys, refs
from nexusbt_tds.check import Level
from nexusbt_tds.manifest import read_manifest

from .conformance_build import build

#: The S codes the `schema` level reports.
S_CODES = [f"TDS-S{n:03}" for n in range(1, 11)]


def codes(path: Path, level: Level = "manifest", **kwargs: Any) -> list[str]:
    result = check(path, level=level, **kwargs)
    return [f.code for f in (*result.errors, *result.warnings)]


def write(root: Path, change: Any = None) -> Path:
    manifest, files = build.base()
    if change:
        change(manifest, files)
    return Path(build.write(root, manifest, files))


def add_bars_file(path: str, size: int = 1) -> Any:
    return lambda m, f: build.bars(m)["files"].append({"path": path, "bytes": size})


@pytest.mark.parametrize("code", [f"TDS-M{n:03}" for n in range(1, 15)])
def test_M_codes(code: str, tmp_path: Path) -> None:
    package = tmp_path / "pkg"
    assert codes(build.write(package / "fail", *build.package(code, "fail"))) == [code]
    assert codes(build.write(package / "pass", *build.package(code, "pass"))) == []
    assert codes(package / "fail", "schema") == [code]  # also at the CLI's default level


@pytest.mark.parametrize("code", [*S_CODES, "TDS-T002", "TDS-T006", "TDS-D002"])  # 8.2
def test_S_codes(code: str, tmp_path: Path) -> None:
    fail = build.write(tmp_path / "fail", *build.package(code, "fail"))
    assert codes(fail, "schema") == [code]
    assert codes(fail) == []  # the manifest level reads no Parquet
    assert codes(build.write(tmp_path / "pass", *build.package(code, "pass")), "schema") == []


K_CODES = ["TDS-K001", "TDS-K002", "TDS-K003", "TDS-K004", "TDS-K010", "TDS-K011"]


@pytest.fixture(params=["whole", "a row per batch"])
def keys_batches(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    """The K codes twice: files read in one batch, and one row per batch (#309): same findings."""
    if request.param == "a row per batch":
        monkeypatch.setattr(keys, "BATCH_ROWS", 1)


@pytest.mark.usefixtures("keys_batches")
@pytest.mark.parametrize("code", K_CODES)
def test_K_codes(code: str, tmp_path: Path) -> None:
    fail = check(build.write(tmp_path / "fail", *build.package(code, "fail")), level="full")
    assert [f.code for f in (*fail.errors, *fail.warnings)] == [code]
    assert code not in fail.unchecked
    assert codes(tmp_path / "fail", "schema") == []  # the schema level reads no rows
    passed = check(build.write(tmp_path / "pass", *build.package(code, "pass")), level="full")
    assert (passed.errors, passed.warnings, code in passed.unchecked) == ((), (), False)


def _custom_in_year(m: dict[str, Any], f: Any) -> None:  # no schema: no key, sort, date column
    build._add("x_custom", {"a": [1]})(m, f)
    rel = "x_custom/year=2024/part-00000.parquet"
    f[rel] = f.pop("x_custom/part-00000.parquet")
    m["datasets"][-1]["files"][0]["path"] = rel


MARCH = dt.datetime(2024, 3, 1, tzinfo=dt.UTC)


def _symbols(edit: Any) -> Any:
    """K010's fail package (AAA, then BBB on ticker AAA) with its rows changed by `edit`."""

    def change(m: dict[str, Any], f: Any) -> None:
        build.CASES["TDS-K010"][1](m, f)
        rel = "instrument_symbols/part-00000.parquet"
        rows = (table := pq.read_table(pa.BufferReader(f[rel]))).to_pylist()
        edit(rows)
        build.rewrite(m, f, rel, pa.Table.from_pylist(rows, table.schema))

    return change


def _unknown(rows: list[Any]) -> None:  # AAA known until March, BBB from null: the calendar's
    rows[0]["ts_known_to"], rows[1]["ts_known_from"] = MARCH, None


def _unknown_then_found(rows: list[Any]) -> None:  # A00 vs AAA undecided; A00 vs BBB overlap
    rows[0]["ts_known_to"] = MARCH
    rows.insert(
        0, rows[0] | {"instrument_id": "US:A00", "ts_known_from": None, "ts_known_to": None}
    )


def _no_venue(m: dict[str, Any], f: Any) -> None:  # a symbol column missing: K010 not judged
    build.CASES["TDS-K010"][1](m, f)
    rel = "instrument_symbols/part-00000.parquet"
    table = pq.read_table(pa.BufferReader(f[rel])).drop_columns(["venue_mic"])
    build.rewrite(m, f, rel, table)


def _ranges(*names: str) -> Any:
    """K004's pass package with its bars files named `names`; a third holds US:BBB on 01-03."""

    def change(m: dict[str, Any], f: Any) -> None:
        build.CASES["TDS-K004"][0](m, f)
        folder, entries = build.BARS.rsplit("/", 1)[0], build.bars(m)["files"]
        if len(names) == 3:
            day = pa.array([dt.date(2024, 1, 3)])
            table = build.bars_table(instrument_id=pa.array(["US:BBB"]), session_date=day)
            f[f"{folder}/third"] = build.parquet(table, "bars_1d")
            entries.append({"path": f"{folder}/third", "bytes": len(f[f"{folder}/third"])})
        for entry, name in zip(entries, names, strict=True):
            f[f"{folder}/{name}.parquet"] = f.pop(entry["path"])
            entry["path"] = f"{folder}/{name}.parquet"

    return change


_A = "2024-01-02T00-00-00Z_2024-01-04T00-00-00Z"  # B and C lie inside A, apart from each other
_B = "2024-01-03T00-00-00Z_2024-01-03T01-00-00Z"
_C = "2024-01-03T05-00-00Z_2024-01-03T06-00-00Z"


def _listed_twice(m: dict[str, Any], f: Any) -> None:  # M013: its rows are read once
    build.bars(m)["files"].append(dict(build.bars(m)["files"][0]))


def _weekly(m: dict[str, Any], f: Any) -> None:  # TDS 5.5: only `freq<1d` is intraday
    build.CASES["TDS-K002"][1](m, f)
    build.bars(m)["params"]["freq"] = "1w"


def _not_parquet(m: dict[str, Any], f: Any) -> None:  # S010: no rows read, no K code judged
    f[build.BARS] = b"not parquet\n"
    build.bars(m)["files"][0]["bytes"] = len(f[build.BARS])


@pytest.mark.usefixtures("keys_batches")
@pytest.mark.parametrize(
    ("change", "errors", "unchecked"),
    [
        (_listed_twice, [], []),
        (_ranges("part-00000", "part-00001"), [], []),  # no range in the name
        (_ranges(_A, _B, _C), ["TDS-K004"] * 2, []),
        (_custom_in_year, [], ["TDS-K001", "TDS-K002", "TDS-K003"]),
        (_symbols(_unknown), [], ["TDS-K010"]),
        (_symbols(_unknown_then_found), ["TDS-K010"], []),
        (_no_venue, [], ["TDS-K001", "TDS-K002", "TDS-K010"]),  # venue_mic is in key and sort
        (_weekly, ["TDS-K002"], []),
        (_not_parquet, [], K_CODES),
        (lambda m, f: f.pop(build.BARS), [], []),  # M004: a missing file has no rows
        (_ranges("2024-01-02T25-00-00Z_2024-01-02T26-00-00Z", _B), [], []),  # hour 25: no range
        (lambda m, f: _named_twice(m, f), [], K_CODES),  # which `instrument_id`? rows unseen
    ],
)
def test_key_rules_edges(
    change: Any, errors: list[str], unchecked: list[str], tmp_path: Path
) -> None:
    result = check(write(tmp_path, change), level="full")
    assert [f.code for f in result.errors if f.code in K_CODES] == errors
    assert [c for c in K_CODES if c in result.unchecked] == unchecked


def test_keys_read_the_named_datasets_and_only_their_key_columns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """TDS 8.1 `--datasets` bounds what `keys` reads (#309): of the named datasets, the key,
    sort and date columns, in batches; a broken file of another dataset hides nothing."""
    read: list[list[str]] = []
    batches = pq.ParquetFile.iter_batches

    def record(self: pq.ParquetFile, *args: Any, columns: Any = None, **kw: Any) -> Any:
        read.append(sorted(columns))
        return batches(self, *args, columns=columns, **kw)

    monkeypatch.setattr(pq.ParquetFile, "iter_batches", record)
    blind: set[str] = set()
    m = read_manifest(write(tmp_path / "broken", _not_parquet))  # bars unreadable, not named
    assert keys.check_keys(m, ["instruments"], blind) == []
    assert blind == set()
    assert read == [["instrument_id"]]  # its key and its sort; no date folder, no date
    read.clear()
    assert keys.check_keys(read_manifest(write(tmp_path / "ok")), ["bars_1d"], blind) == []
    assert read == [["instrument_id", "session_date"]]  # daily bars: no close, no volume


def test_classification_levels_not_duplicate(tmp_path: Path) -> None:
    manifest, files = build.package("TDS-K001", "pass")  # GICS level 1 and 3, same day (5.19)
    rows = pq.read_table(pa.BufferReader(files["classifications/part-00000.parquet"])).to_pylist()
    assert {r["level"] for r in rows} == {1, 3}
    assert len({(r["effective_from"], r["ts_known_from"]) for r in rows}) == 1
    assert codes(build.write(tmp_path, manifest, files), "full") == []


R_CODES = [f"TDS-R{n:03}" for n in range(1, 10)]


@pytest.fixture(params=["whole", "a row per batch"])
def refs_batches(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    """The R codes twice: files read in one batch, and one row per batch (#309): same findings."""
    if request.param == "a row per batch":
        monkeypatch.setattr(refs, "BATCH_ROWS", 1)


@pytest.mark.usefixtures("refs_batches")
@pytest.mark.parametrize("code", R_CODES)
def test_R_codes(code: str, tmp_path: Path) -> None:
    test_K_codes(code, tmp_path)  # the same contract: once in its fail package, judged in both


def _no_instruments(m: dict[str, Any], f: Any) -> None:  # a calendar but no instruments table
    build.CASES["TDS-R003"][1](m, f)
    f.pop(build.INSTRUMENTS)
    m["datasets"] = [d for d in m["datasets"] if d["kind"] != "instruments"]


def _without(kind: str, change: Any) -> Any:
    """`change`, then the dataset of `kind` removed with its files."""

    def out(m: dict[str, Any], f: Any) -> None:
        change(m, f)
        (gone,) = (d for d in m["datasets"] if d["kind"] == kind)
        m["datasets"].remove(gone)
        for entry in gone["files"]:
            f.pop(entry["path"])

    return out


def _twice(m: dict[str, Any], f: Any) -> None:  # an earlier delisting read last: the latest counts
    build.CASES["TDS-R008"][0](m, f)
    rel = "delistings/part-00000.parquet"
    rows = (table := pq.read_table(pa.BufferReader(f[rel]))).to_pylist()
    rows.append(rows[0] | {"delisting_id": "US:L0", "exit_date": dt.date(2020, 1, 2)})
    build.rewrite(m, f, rel, pa.Table.from_pylist(rows, table.schema))


def _no_exits(m: dict[str, Any], f: Any) -> None:  # delisted_on set, delistings with no rows
    build.CASES["TDS-R008"][0](m, f)
    rel = "delistings/part-00000.parquet"
    table = pq.read_table(pa.BufferReader(f[rel]))
    build.rewrite(m, f, rel, table.slice(0, 0))


_MOM = build._panels("strict", mom=[0.1], x_note=["n"])  # a feature column and an extension


def _empty_panel(m: dict[str, Any], f: Any) -> None:  # the `mom` panel with its row removed
    _MOM(m, f)
    rel = "feature_panels/name=f/edition=strict/year=2024/part-00000.parquet"
    build.rewrite(m, f, rel, pq.read_table(pa.BufferReader(f[rel])).slice(0, 0))


_NO_CAL = ["TDS-R002", "TDS-R003"]  # the base package has no calendar_sessions
_NO_EXITS = ["TDS-R008"]  # nor delistings


@pytest.mark.usefixtures("refs_batches")
@pytest.mark.parametrize(
    ("change", "errors", "unchecked"),
    [
        (_no_instruments, [], ["TDS-R001", "TDS-R003", *_NO_EXITS]),
        (_not_parquet, [], R_CODES),
        (  # an instruments table with no rows: every id is missing, not unchecked
            lambda m, f: build.rewrite(m, f, build.INSTRUMENTS, build.instruments().slice(0, 0)),
            ["TDS-R001"],
            [*_NO_CAL, *_NO_EXITS],
        ),
        (  # any of the four currency columns
            build._instruments(settlement_currency=pa.array(["usd"])),
            ["TDS-R004"],
            [*_NO_CAL, *_NO_EXITS],
        ),
        (_no_exits, ["TDS-R008"], _NO_CAL),  # R008: delisted_on set, no delistings row
        (_twice, [], _NO_CAL),  # delisted twice; delisted_on is the latest exit_date
        (build._exits(delisted=False), ["TDS-R008"], _NO_CAL),  # a delisting, delisted_on null
        (_without("fundamentals_events", build._facts("F9")), [], [*_NO_CAL, *_NO_EXITS]),
        (_MOM, ["TDS-R009"], [*_NO_CAL, *_NO_EXITS]),  # no dictionary/columns: `mom` missing
        (_empty_panel, ["TDS-R009"], [*_NO_CAL, *_NO_EXITS]),  # columns from the footer
        (  # a delisting but no instruments table: R008 has nothing to compare
            _without("instruments", build._exits(delisted=False)),
            [],
            ["TDS-R001", *_NO_CAL, "TDS-R008"],
        ),
        (  # `mom` described for the dataset `feature_panels` (4.4); `x_note` needs no entry
            build._both(
                _MOM,
                build._add(
                    "dictionary/columns", {"dataset": ["feature_panels"], "column": ["mom"]}
                ),
            ),
            [],
            [*_NO_CAL, *_NO_EXITS],
        ),
    ],
)
def test_reference_rules_edges(
    change: Any, errors: list[str], unchecked: list[str], tmp_path: Path
) -> None:
    result = check(write(tmp_path, change), level="full")
    found = [f.code for f in (*result.errors, *result.warnings)]  # R005 and R007 warn
    assert [c for c in found if c in R_CODES] == errors
    assert [c for c in R_CODES if c in result.unchecked] == unchecked


def test_refs_with_datasets_reads_the_named_and_the_lookup_columns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """TDS 8.1 `--datasets` bounds what `refs` reads (#309): the named datasets, and of the
    tables they point to only the lookup columns."""
    read: list[tuple[bool, list[str]]] = []  # (a bars file?, the columns asked for)
    batches = pq.ParquetFile.iter_batches

    def record(self: pq.ParquetFile, *args: Any, columns: Any = None, **kw: Any) -> Any:
        read.append(("close" in self.schema_arrow.names, sorted(columns or [])))
        return batches(self, *args, columns=columns, **kw)

    monkeypatch.setattr(pq.ParquetFile, "iter_batches", record)
    blind: set[str] = set()
    m = read_manifest(write(tmp_path / "broken", _not_parquet))  # bars unreadable, not named
    assert refs.check_refs(m, ["instruments"], blind) == []
    assert "TDS-R001" not in blind  # a broken file of a dataset not read hides nothing
    assert [bars for bars, _ in read] == [False, False]  # instruments: as lookup, as named
    read.clear()
    assert refs.check_refs(read_manifest(write(tmp_path / "ok")), ["bars_1d"], set()) == []
    ((_, instruments),) = [r for r in read if not r[0]]  # once, as the lookup
    assert set(instruments) <= set(refs.LOOKUPS["instruments"])
    assert [bars for bars, _ in read].count(True) == 1


def _named_twice(m: dict[str, Any], f: Any) -> None:  # a bars file storing `instrument_id` twice
    t = build.bars_table()
    names = [*t.column_names, "instrument_id"]
    build.rewrite(m, f, build.BARS, pa.Table.from_arrays([*t.columns, t["instrument_id"]], names))


@pytest.mark.usefixtures("refs_batches")
@pytest.mark.parametrize(
    ("change", "unchecked"),
    [  # the full level ends with a result, not a traceback (#309's review)
        (build._bars(currency=pa.array([["USD"]])), [*_NO_CAL, *_NO_EXITS]),  # a list: no code
        (
            build._bars(calendar_id=pa.array([["X"]]), item=pa.array([{"a": 1}])),
            [*_NO_CAL, *_NO_EXITS],
        ),
        (_named_twice, R_CODES),  # which `instrument_id`? unseen, as an unreadable file
    ],
)
def test_refs_on_columns_it_cannot_compare(
    change: Any, unchecked: list[str], tmp_path: Path
) -> None:
    result = check(write(tmp_path, change), level="full")
    assert not [f.code for f in (*result.errors, *result.warnings) if f.code in R_CODES]
    assert [c for c in R_CODES if c in result.unchecked] == unchecked


@pytest.mark.parametrize(
    ("change", "dataset", "dictionary"),
    [
        (build._panels("strict", mom=[0.1], size=[2.0]), "feature_panels", "dictionary/columns"),
        (
            _without("dictionary/items", build._facts("F1")),
            "fundamentals_state",
            "dictionary/items",
        ),
    ],
)
def test_R009_names_the_missing_dictionary_once_per_dataset(
    change: Any, dataset: str, dictionary: str, tmp_path: Path
) -> None:
    result = check(write(tmp_path, change), level="full")
    r009 = [f for f in result.errors if f.code == "TDS-R009"]
    assert [f.dataset for f in r009 if f.dataset == dataset] == [dataset]  # not one per column
    assert all(f"no {dictionary}" in f.message for f in r009)


@pytest.mark.parametrize("code", ["TDS-H001", "TDS-H002", "TDS-H003"])
def test_H_codes(code: str, tmp_path: Path) -> None:
    fail = build.write(tmp_path / "fail", *build.package(code, "fail"))
    assert codes(fail, "full") == [code]
    assert codes(fail, "schema") == []  # the schema level reads no rows and hashes nothing
    assert codes(build.write(tmp_path / "pass", *build.package(code, "pass")), "full") == []


@pytest.mark.parametrize("code", ["TDS-H002", "TDS-H003"])
def test_H002_H003_are_judged_on_a_package_with_a_dictionary(code: str, tmp_path: Path) -> None:
    manifest, files = build.package(code, "pass")
    assert "dictionary/codes" in {d["kind"] for d in manifest["datasets"]}  # TDS 4.4, 4.5
    result = check(build.write(tmp_path, manifest, files), level="full")
    assert not {"TDS-H002", "TDS-H003"} & set(result.unchecked)


def test_a_wrong_dictionary_value_hash_is_H002(tmp_path: Path) -> None:
    manifest, files = build.package("TDS-H002", "pass")  # every value hash right, then one wrong
    next(d for d in manifest["datasets"] if d["kind"] == "dictionary/codes")["value_sha256"] = (
        "0" * 64
    )
    result = check(build.write(tmp_path, manifest, files), level="full")
    assert [(f.code, f.dataset) for f in result.errors] == [("TDS-H002", "dictionary/codes")]


def test_datasets_named_bound_the_hashes_and_leave_H003_unchecked(tmp_path: Path) -> None:
    manifest, files = build.package("TDS-H003", "fail")  # a wrong package hash, then H002 too
    named = next(d for d in manifest["datasets"] if d["kind"] == "dictionary/codes")
    named["value_sha256"] = "0" * 64
    result = check(build.write(tmp_path, manifest, files), level="full", datasets=[named["name"]])
    assert [(f.code, f.dataset) for f in result.errors] == [("TDS-H002", named["name"])]
    assert "TDS-H003" in result.unchecked
    assert "TDS-H002" not in result.unchecked
    assert any(n.startswith("TDS-H003 not checked") for n in result.notes)


def test_a_file_listed_twice_in_a_named_dataset_is_not_hashed_twice(tmp_path: Path) -> None:
    def twice(m: dict[str, Any], f: Any) -> None:  # M013's; its rows are not the dataset's twice
        build.bars(m)["files"] *= 2
        build.bars(m)["value_sha256"] = "0" * 64

    result = check(write(tmp_path / "pkg", twice), level="full", datasets=["bars_1d"])
    assert "TDS-H002" not in [f.code for f in result.errors]
    assert "TDS-H002" in result.unchecked


def test_full_level_says_where_sorted_runs_went(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("nexusbt_tds.hash.BATCH_ROWS", 1)  # a run per row: a temporary file
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    days = pa.array([dt.date(2024, 1, 2), dt.date(2024, 1, 3)])
    ids, close = pa.array(["US:AAA"] * 2), pa.array([1.0, 2.0])
    two = _bars(instrument_id=ids, session_date=days, close=close)
    result = check(write(tmp_path / "pkg", two), level="full", tmp_dir=scratch)
    assert (result.errors, list(scratch.iterdir())) == ((), [])
    (said,) = [n for n in result.notes if str(scratch) in n]  # one line names the folder
    assert "temporary file(s) of sorted rows" in said
    assert said.endswith("removed")


def test_full_level_checks_only_the_keys_references_and_hashes_so_far(tmp_path: Path) -> None:
    result = check(write(tmp_path / "pkg"), level="full")
    assert (result.errors, result.warnings) == ((), ())
    # spec 8.2, no false pass: the other full-level rules are not built, so no profile is `full`
    assert result.profiles == {
        "tds:minimal-daily@1.0": ProfileStatus(True, "schema", "not_checked")
    }
    assert {"TDS-T001", "TDS-H004"} <= set(result.unchecked)
    judged = {*K_CODES, *R_CODES, "TDS-H001", "TDS-H002", "TDS-H003"} - {*_NO_CAL, *_NO_EXITS}
    assert not judged & set(result.unchecked)
    assert {*_NO_CAL, *_NO_EXITS} <= set(result.unchecked)  # no calendar_sessions, delistings
    # a column whose type is declared nowhere: no value hash, so H002 and H003 are not checked
    untyped = check(write(tmp_path / "untyped", _bars(x_cf_note=pa.array([[1]]))), level="full")
    assert {"TDS-H002", "TDS-H003"} <= set(untyped.unchecked)
    assert "TDS-H001" not in untyped.unchecked


def test_a_file_listed_twice_gets_one_H001(tmp_path: Path) -> None:
    def twice(m: dict[str, Any], f: Any) -> None:  # M013, and the same wrong sha256 on both
        entry = build.bars(m)["files"][0] | {"sha256": "0" * 64}
        build.bars(m)["files"] = [entry, dict(entry)]

    assert codes(write(tmp_path / "pkg", twice), "full") == ["TDS-M013", "TDS-H001"]


def test_full_level_reads_no_file_outside_the_package(tmp_path: Path) -> None:
    def outside(m: dict[str, Any], f: Any) -> None:  # M012's absolute path, with a sha256
        build.bars(m)["files"].append({"path": "/etc/hosts", "bytes": 1, "sha256": "0" * 64})

    result = check(write(tmp_path / "pkg", outside), level="full")
    assert [f.code for f in result.errors] == ["TDS-M012"]  # no H001: /etc/hosts is not read
    assert {"TDS-H002", "TDS-H003"} <= set(result.unchecked)


def test_full_level_reports_where_the_hash_cannot_be_taken(tmp_path: Path) -> None:
    odd = check(write(tmp_path, lambda m, f: build.bars(m).update(params=["x"])), level="full")
    assert {"TDS-H002", "TDS-H003"} <= set(odd.unchecked)  # a result, not an exception


def test_schema_level_reports_rows_not_checked(tmp_path: Path) -> None:
    result = check(write(tmp_path / "year=x"), level="schema")  # a folder above: no partition
    assert (result.errors, result.warnings) == ((), ())
    assert result.profiles == {
        "tds:minimal-daily@1.0": ProfileStatus(True, "schema", "not_checked")
    }
    assert {"TDS-K001", "TDS-R001", "TDS-T001", "TDS-H001"} <= set(result.unchecked)  # rows
    assert "TDS-S009" in result.unchecked  # NaN is not in the footers
    assert not set(S_CODES) - {"TDS-S009"} & set(result.unchecked)
    broken = build.write(tmp_path / "broken", *build.package("TDS-S002", "fail"))
    assert check(broken, level="schema").profiles["tds:minimal-daily@1.0"].result == "fail"


def test_a_rule_without_statistics_is_not_checked(tmp_path: Path) -> None:
    def blind(m: dict[str, Any], f: Any) -> None:
        build.rewrite(m, f, build.INSTRUMENTS, build.instruments(), write_statistics=False)

    assert "TDS-S003" not in check(write(tmp_path), level="schema").unchecked
    result = check(write(tmp_path, blind), level="schema")
    assert "TDS-S003" in result.unchecked
    assert result.errors == ()


def test_a_kind_without_a_schema_file_is_not_checked(tmp_path: Path) -> None:
    def custom(m: dict[str, Any], f: Any) -> None:
        rel = "x_custom/part-00000.parquet"
        f[rel] = build.parquet(pa.table({"anything": [1]}), "x_custom")
        entry = {"path": rel, "bytes": len(f[rel])}
        m["datasets"].append({"name": "x_custom", "kind": "x_custom", "schema_version": "1.0",
                              "path": "x_custom", "files": [entry]})  # fmt: skip

    result = check(write(tmp_path / "custom", custom), level="schema")
    assert (result.errors, result.warnings) == ((), ())
    assert set(S_CODES) <= set(result.unchecked)  # not a silent pass

    def under_dictionary(m: dict[str, Any], f: Any) -> None:  # the kind decides, not the path
        custom(m, f)
        m["datasets"][-1]["path"] = "dictionary/x"

    unchecked = check(write(tmp_path / "d", under_dictionary), level="schema").unchecked
    assert set(S_CODES) <= set(unchecked)
    # `dictionary/codes` (TDS 4.4) has no schema file either, and hides nothing
    package = build.write(tmp_path / "codes", *build.package("TDS-S007", "pass"))
    assert not set(S_CODES) - {"TDS-S009"} & set(check(package, level="schema").unchecked)


def test_a_required_list_column_leaves_S003_unchecked(tmp_path: Path) -> None:
    import pyarrow.parquet as pq

    from nexusbt_tds.check import _check_column
    from nexusbt_tds.schemas.verify import Column

    pq.write_table(pa.table({"tags": pa.array([["a"]], pa.list_(pa.string()))}), tmp_path / "t")
    meta = pq.ParquetFile(tmp_path / "t").metadata
    blind: set[str] = set()
    column = Column("tags", "list<code>", False)  # no schema file has one yet (trades: nullable)
    assert list(_check_column(meta, meta.schema.to_arrow_schema(), column, True, None, blind)) == []
    assert blind == {"TDS-S003"}  # a list has no top-level null count
    blind.clear()
    list(_check_column(meta, meta.schema.to_arrow_schema(), column, False, None, blind))
    assert blind == set()  # a nullable one hides nothing


def test_a_listed_file_that_is_not_parquet_is_S010(tmp_path: Path) -> None:
    def text(m: dict[str, Any], f: Any) -> None:
        f[build.BARS] = b"not parquet\n"
        build.bars(m)["files"][0]["bytes"] = len(f[build.BARS])

    result = check(write(tmp_path, text), level="schema")
    assert [(e.code, e.file) for e in result.errors] == [("TDS-S010", build.BARS)]
    assert "not a Parquet file" in result.errors[0].message
    assert "TDS-S010" not in result.unchecked
    assert "TDS-S001" in result.unchecked  # nothing else in it can be read
    # a changed size names the cause (M006): S010 is then not judged, and not passed either
    broken = build.write(tmp_path / "m006", *build.package("TDS-M006", "fail"))
    assert "TDS-S010" in check(broken, level="schema").unchecked


def test_a_file_listed_twice_gets_each_S_finding_once(tmp_path: Path) -> None:
    def twice(m: dict[str, Any], f: Any) -> None:
        _bars(close=pa.array(["10.0"]))(m, f)  # S002
        again = dict(build.bars(m)["files"][0])
        again["path"] = build.BARS.replace("year=", "./year=")  # the same file, spelled otherwise
        build.bars(m)["files"].append(again)

    assert codes(write(tmp_path, twice), "schema") == ["TDS-M013", "TDS-S002"]


def _classes(*values: str, **opts: Any) -> Any:
    """The instruments file with one row per `asset_class` value."""
    rows = pa.concat_tables([build.instruments(asset_class=pa.array([v])) for v in values])
    return lambda m, f: build.rewrite(m, f, build.INSTRUMENTS, rows, **opts)


@pytest.mark.parametrize(
    ("change", "found", "unchecked"),
    [  # a footer shows a column's minimum and maximum: its values when they are equal
        (_classes("equity", "fund"), [], True),  # one row group: `etf` and `zzz` may lie between
        (_classes("equity", "fund", row_group_size=1), [], False),  # every value is a min
        (_classes("equity", "zzz"), ["TDS-S006"], True),
        (_classes("equity", write_statistics=False), [], True),
        (lambda m, f: build.rewrite(m, f, build.INSTRUMENTS, build.instruments(
            asset_class=pa.array([None], pa.string()))), ["TDS-S003"], False),  # nulls only
    ],
)  # fmt: skip
def test_enum_values_the_footer_cannot_show_are_not_checked(
    change: Any, found: list[str], unchecked: bool, tmp_path: Path
) -> None:
    result = check(write(tmp_path, change), level="schema")
    assert [f.code for f in result.errors] == found
    assert ("TDS-S006" in result.unchecked) is unchecked


def test_an_open_list_is_not_checked_alike_and_a_bad_dictionary_excuses_nothing(
    tmp_path: Path,
) -> None:
    two = pa.concat_tables(  # one row group, `common` to `unit`: what lies between is unknown
        [build.instruments(category=pa.array([v])) for v in ("common", "unit")]
    )
    package = write(tmp_path / "two", lambda m, f: build.rewrite(m, f, build.INSTRUMENTS, two))
    assert "TDS-S007" in check(package, level="schema").unchecked

    no_columns = build.parquet(pa.table({"label": ["x"]}), "dictionary/codes")  # no field, code
    for name, content in (("no-columns", no_columns), ("not-parquet", b"not parquet\n")):

        def bad_dictionary(m: dict[str, Any], f: Any, content: bytes = content) -> None:
            build._instruments(codes=True, category=pa.array(["ordinary"]))(m, f)
            rel = "dictionary/codes/part-00000.parquet"
            f[rel] = content
            m["datasets"][-1]["files"][0]["bytes"] = len(f[rel])

        result = check(write(tmp_path / name, bad_dictionary), level="schema")
        assert [w.code for w in result.warnings] == ["TDS-S007"], name


@pytest.mark.parametrize(
    ("value", "found"),
    [("vendor:lean", []), ("vendor:", ["TDS-S007"]), ("lean", ["TDS-S007"]), ("ticker", [])],
)
def test_a_placeholder_in_a_value_list_is_any_name(
    value: str, found: list[str], tmp_path: Path
) -> None:  # `vendor:<name>`: a rule chosen in #117
    table = pa.table({"instrument_id": ["US:AAA"], "symbol_type": [value], "symbol": ["AAA"]})
    rel = "instrument_symbols/part-00000.parquet"

    def add(m: dict[str, Any], f: Any) -> None:
        f[rel] = build.parquet(table, "instrument_symbols")
        m["datasets"].append({"name": "instrument_symbols", "kind": "instrument_symbols",
                              "schema_version": "1.0", "path": "instrument_symbols",
                              "files": [{"path": rel, "bytes": len(f[rel])}]})  # fmt: skip

    result = check(write(tmp_path, add), level="schema")
    assert [w.code for w in result.warnings] == found


@pytest.mark.parametrize(
    ("value", "found"),
    [("committee", ["TDS-S006"]), ("board", []), ("meeting", []), (None, [])],
)
def test_resolution_body_is_a_closed_list(
    value: str | None, found: list[str], tmp_path: Path
) -> None:  # TDS 5.11, #140: `meeting` or `board`, null when the producer does not know
    table = pa.table({
        "event_id": ["E1"], "instrument_id": ["KR:AAA"], "kind": ["cash_dividend"],
        "ex_date": pa.array([build.TS[0].as_py().date()], pa.date32()), "ts_effective": build.TS,
        "pay_date_status": ["observed"], "resolution_body": pa.array([value], pa.string()),
        "affects": ["total_only"], "factor_method": ["cash_prev_close"], "status": ["effective"],
    })  # fmt: skip
    rel = "corporate_actions/part-00000.parquet"

    def add(m: dict[str, Any], f: Any) -> None:
        f[rel] = build.parquet(table, "corporate_actions")
        m["datasets"].append({"name": "corporate_actions", "kind": "corporate_actions",
                              "schema_version": "1.0", "path": "corporate_actions",
                              "files": [{"path": rel, "bytes": len(f[rel])}]})  # fmt: skip

    result = check(write(tmp_path, add), level="schema")
    assert [f.code for f in (*result.errors, *result.warnings)] == found
    assert "TDS-S006" not in result.unchecked


END, TICK, HOUR = build.THROUGH, dt.timedelta(microseconds=1), dt.timedelta(hours=1)


def _ts(value: dt.datetime | None, unit: str = "us") -> pa.Array:
    return pa.array([value], pa.timestamp(unit, "UTC"))


def _rule(rule: str, through: bool = True, opts: Any = None, **columns: Any) -> Any:
    """The bars under availability `rule`, US `complete_through` END unless not `through`."""

    def change(m: dict[str, Any], f: Any) -> None:
        if through:
            m["markets"]["US"]["complete_through"] = END.isoformat()
        build.bars(m)["availability"] = {"rule": rule}
        build.rewrite(m, f, build.BARS, build.bars_table(**columns), **(opts or {}))

    return change


def _custom(m: dict[str, Any], f: Any) -> None:
    """Bars T006 can pass, and a US dataset of a kind with no rule: its instants are unknown."""
    _rule("ts_end", ts_end=_ts(END))(m, f)
    rel = "x_custom/market=US/part-00000.parquet"
    f[rel] = build.parquet(pa.table({"ts_end": _ts(END + HOUR)}), "x_custom")
    entry = {"path": rel, "bytes": len(f[rel])}
    m["datasets"].append({"name": "x_custom", "kind": "x_custom", "schema_version": "1.0",
                          "path": "x_custom", "files": [entry]})  # fmt: skip


@pytest.mark.parametrize(
    ("change", "found", "unchecked"),
    [  # #181 Decisions (1): the availability instant from the statistics, against the watermark
        (_rule("ts_end", ts_end=_ts(END)), [], False),  # at the watermark: not after it
        (_rule("ts_end", ts_end=_ts(END + TICK)), ["TDS-T006"], False),
        (_rule("ts_end", ts_end=_ts(END + TICK, "ns")), ["TDS-T006"], False),
        (_rule("ts_end+PT1H", ts_end=_ts(END - HOUR)), [], False),
        (_rule("ts_end+PT1H", ts_end=_ts(END - HOUR + TICK)), ["TDS-T006"], False),
        (_rule("column", ts_available=_ts(END + TICK)), ["TDS-T006"], False),
        (lambda m, f: (_rule("ts_end", ts_end=_ts(END), ts_available=_ts(END + TICK))(m, f),
                       build.bars(m).update(availability={"column": "ts_available"})),
         ["TDS-T006"], False),  # 4.2's `{"column": "ts_available"}`, the same rule
        (_custom, [], True),
        (_rule("ts_end", through=False, ts_end=_ts(END + HOUR)), [], True),  # no watermark
        (_rule("ts_end", opts={"write_statistics": False}, ts_end=_ts(END + HOUR)), [], True),
        (_rule("ts_end", ts_end=_ts(None)), [], True),  # null: the session close (TDS 6.2)
        (_rule("ts_end"), [], True),  # no ts_end column at all: every bar's is the close
        (_rule("session_close"), [], True),  # the calendar's rows, not a footer
        (_rule("ts_end+P1M", ts_end=_ts(END - HOUR)), [], True),  # a month has no fixed length
    ],
)  # fmt: skip
def test_T006_from_the_statistics(
    change: Any, found: list[str], unchecked: bool, tmp_path: Path
) -> None:
    result = check(write(tmp_path, change), level="schema")
    assert [f.code for f in result.errors] == found
    assert ("TDS-T006" in result.unchecked) is unchecked
    assert ("TDS-T006" in check(tmp_path, level="full").unchecked) is unchecked


def _state(ts_known_from: dt.datetime, availability: object) -> Any:
    """A US `fundamentals_state` row known at `ts_known_from`, US `complete_through` END."""

    def change(m: dict[str, Any], f: Any) -> None:
        _rule("ts_end", ts_end=_ts(END))(m, f)  # bars T006 can pass
        rel = "fundamentals_state/market=US/part-00000.parquet"
        row = {"instrument_id": ["US:AAA"], "item": ["revenue"], "period_end": build.DAY,
               "ts_known_from": _ts(ts_known_from), "period_kind": ["FY"],
               "statement_basis": ["consolidated"], "value": [1.0], "unit": ["USD"],
               "scale": pa.array([0], pa.int8()), "strict_eligible": [True],
               "vendor_input": [False], "resolution_policy": ["fund-resolution-v1"]}  # fmt: skip
        f[rel] = build.parquet(pa.table(row), "fundamentals_state")
        m["datasets"].append({"name": "fundamentals_state", "kind": "fundamentals_state",
                              "schema_version": "1.0", "path": "fundamentals_state",
                              "availability": availability,
                              "files": [{"path": rel, "bytes": len(f[rel])}]})  # fmt: skip

    return change


@pytest.mark.parametrize(
    ("change", "found", "unchecked"),
    [  # TDS 4.2 `{"column": "ts_known_from"}`: T006 reads that column's statistics (#276)
        (_state(END, {"column": "ts_known_from"}), [], False),
        (_state(END + TICK, {"column": "ts_known_from"}), ["TDS-T006"], False),
        (_state(END + TICK, None), [], True),  # no availability: its instant is unknown
    ],
)
def test_T006_reads_the_named_column(
    change: Any, found: list[str], unchecked: bool, tmp_path: Path
) -> None:
    result = check(write(tmp_path, change), level="schema")
    assert [f.code for f in result.errors] == found
    assert {f.dataset for f in result.errors} <= {"fundamentals_state"}
    assert ("TDS-T006" in result.unchecked) is unchecked


def _action(terms: dt.datetime | None, announced: dt.datetime | None = None) -> Any:
    """A US cash dividend effective an hour after END, its terms public at `terms`."""

    def change(m: dict[str, Any], f: Any) -> None:
        _rule("ts_end", ts_end=_ts(END))(m, f)  # bars T006 can pass
        rel = "corporate_actions/market=US/part-00000.parquet"
        row = {"event_id": ["US:E1"], "instrument_id": ["US:AAA"], "kind": ["cash_dividend"],
               "ex_date": build.DAY, "ts_effective": _ts(END + HOUR),
               "ts_terms_available": _ts(terms), "ts_announced": _ts(announced),
               "pay_date_status": ["confirmed"], "affects": ["cash"], "factor_method": ["none"],
               "status": ["active"]}  # fmt: skip
        f[rel] = build.parquet(pa.table(row), "corporate_actions")
        form = {"effect": "ts_effective", "terms": "ts_terms_available"}
        m["datasets"].append({"name": "corporate_actions", "kind": "corporate_actions",
                              "schema_version": "1.0", "path": "corporate_actions",
                              "availability": form,
                              "files": [{"path": rel, "bytes": len(f[rel])}]})  # fmt: skip

    return change


@pytest.mark.parametrize(
    ("change", "found", "unchecked"),
    [  # 6.2: the effect instant is not an availability instant; T006 reads the terms only
        (_action(terms=END), [], False),  # announced, effective after the watermark: no T006
        (_action(terms=END + TICK), ["TDS-T006"], False),
        (_action(terms=None, announced=END), [], True),  # the fallback is in the rows
    ],
)
def test_T006_reads_the_terms_of_a_corporate_action(
    change: Any, found: list[str], unchecked: bool, tmp_path: Path
) -> None:
    result = check(write(tmp_path, change), level="schema")
    assert [f.code for f in result.errors] == found
    assert ("TDS-T006" in result.unchecked) is unchecked


def _days(*days: dt.date, ids: tuple[str, ...] = ("US:AAA",), **listing: Any) -> Any:
    """Bars on `days` of `ids`, instruments (`listing`: their columns) and an XNYS calendar."""
    sessions = pa.table({
        "calendar_id": ["XNYS", "XNYS"], "session_date": [dt.date(2024, 1, 2), dt.date(2024, 1, 4)],
        "ts_open": _ts(END).take([0, 0]), "ts_close": _ts(END).take([0, 0]),
        "session_kind": ["regular", "regular"],
    })  # fmt: skip
    rel = "calendar_sessions/part-00000.parquet"

    def change(m: dict[str, Any], f: Any) -> None:
        bars = [(pa.array([i]), pa.array([d])) for i in ids for d in days]
        rows = [build.bars_table(instrument_id=i, session_date=d) for i, d in bars]
        build.rewrite(m, f, build.BARS, pa.concat_tables(rows))
        rows = [build.instruments(instrument_id=pa.array([i]), **listing) for i in ids]
        build.rewrite(m, f, build.INSTRUMENTS, pa.concat_tables(rows))
        f[rel] = build.parquet(sessions, "calendar_sessions")
        m["datasets"].append({"name": "calendar_sessions", "kind": "calendar_sessions",
                              "schema_version": "1.0", "path": "calendar_sessions",
                              "files": [{"path": rel, "bytes": len(f[rel])}]})  # fmt: skip

    return change


JAN = [dt.date(2024, 1, d) for d in range(1, 9)]  # JAN[2]: listed_on; 2..4: calendar sessions
JAN.insert(0, dt.date(2023, 12, 31))  # JAN[d] is January d


@pytest.mark.parametrize(
    ("change", "found"),
    [  # #181 Decisions (2): the calendar's first and last session, one instrument's listing
        (_days(JAN[2], JAN[4]), []),
        (_days(JAN[3]), []),  # not a session, inside the range: the rows', the full level's
        (_days(JAN[2], JAN[5]), ["TDS-D002"]),  # after the calendar's last session
        (_days(JAN[1], ids=("US:AAA", "US:BBB")), ["TDS-D002"]),  # before its first: any ids
        (_days(JAN[2], listed_on=pa.array([JAN[3]])), ["TDS-D002"]),  # before listed_on
        (_days(JAN[4], delisted_on=pa.array([JAN[3]])), ["TDS-D002"]),  # after delisted_on
        (_days(JAN[3], delisted_on=pa.array([JAN[3]])), []),  # on delisted_on
        (_days(JAN[2], ids=("US:AAA", "US:BBB"), listed_on=pa.array([JAN[3]])), []),  # two ids
        (lambda m, f: (_days(JAN[2], listed_on=pa.array([JAN[3]]))(m, f), build.rewrite(
            m, f, build.INSTRUMENTS, pa.concat_tables([build.instruments(listed_on=pa.array(
                [JAN[3]])), build.instruments(instrument_id=pa.array(["US:BBB"]))]))), []),
        # ^ the instruments' one row group holds two ids: its listed_on is not one instrument's
        (build._bars(session_date=pa.array([JAN[1]])), ["TDS-D002"]),  # no calendar: listing
        (lambda m, f: build.rewrite(m, f, build.BARS, build.bars_table(
            session_date=pa.array([JAN[1]])), write_statistics=False), []),
    ],
)  # fmt: skip
def test_D002_from_the_statistics(change: Any, found: list[str], tmp_path: Path) -> None:
    result = check(write(tmp_path, change), level="schema")
    assert [f.code for f in result.errors] == found
    assert "TDS-D002" in result.unchecked  # its rows: a non-session day inside the range


_bars, TS, VERSION_1_9 = build._bars, build.TS, build.VERSION_1_9


@pytest.mark.parametrize(
    ("change", "expected"),
    [  # the rules chosen in #56, which TDS 3.2, 3.6 and the schema files leave open
        (_bars(ts_end=TS.cast(pa.timestamp("ns", "UTC"))), []),  # `ts_us/ns`: either unit
        (lambda m, f: (build.bars(m).update(columns=[{"name": "ts_end", "type": "ts_ns"}]),
                       _bars(ts_end=TS)(m, f)), ["TDS-S004"]),  # unless tds.json names one
        (_bars(ts_end=TS.cast(pa.timestamp("us"))), ["TDS-S004"]),  # no UTC
        (lambda m, f: build.rewrite(m, f, build.BARS, build.bars_table(ts_end=TS),
                                    use_deprecated_int96_timestamps=True), ["TDS-S004"]),
        (_bars(obs_status=pa.array([None], pa.string())), []),  # "no if dense": not dense
        (lambda m, f: (build.bars(m)["params"].update(density="dense"),
                       _bars(obs_status=pa.array([None], pa.string()))(m, f)), ["TDS-S003"]),
        (lambda m, f: build.bars(m)["params"].update(freq="1m"), ["TDS-S001", "TDS-S001"]),
        (build._move_bars(build.BARS.replace("year=2024", "year=20x4")), ["TDS-S008"]),
        (build._move_bars(build.BARS.replace("year=2024", "year=" + "".join(
            chr(ord(d) + 0xFEE0) for d in "2024"))), ["TDS-S008"]),  # full-width digits
        (build._move_bars(build.BARS.replace("year=2024", "year=02024")), ["TDS-S008"]),
        (build._move_bars(build.BARS.replace("year=2024", "year=-0")), ["TDS-S008"]),
        (build._move_bars(build.BARS.replace("year=2024", "year=-1")), []),  # ASCII, no zero
        (build._move_bars(build.BARS.replace("market=US", "market=")), ["TDS-S008"]),
        (lambda m, f: (build.bars(m).update(partitioning=[{"name": "year", "type": "date"}])),
         ["TDS-S008"]),  # a declared partition type comes first
        (_bars(meta={"tds.dataset": b"\xff", "tds.schema_version": "1.0"}), ["TDS-S010"]),
        (_bars(meta={}), ["TDS-S010"]),  # no key-value metadata at all
        (_bars(meta={"tds.dataset": "bars_1d"}), ["TDS-S010"]),  # no tds.schema_version
        (lambda m, f: (build.bars(m).update(columns=[{"name": "momentum", "type": "f64"}]),
                       _bars(momentum=pa.array(["1"]))(m, f)), ["TDS-S002"]),  # #144: declared
        (lambda m, f: (build.bars(m).update(columns=[{"name": "momentum", "type": "f64"}]),
                       _bars(momentum=pa.array([1.0]))(m, f)), []),  # a declared column is known
        (lambda m, f: build.rewrite(m, f, build.BARS, build.bars_table().append_column(
            "close", pa.array([1.0]))), []),  # a column written twice: no crash
        (lambda m, f: (build.bars(m).update(schema_version="1.9"),
                       _bars(VERSION_1_9, note=pa.array(["a"]))(m, f)), []),  # M011: ignored
        (lambda m, f: (build.bars(m).update(schema_version="2.0"),
                       _bars(close=pa.array(["1"]))(m, f)), []),  # M009: not read as 1.0
    ],
)  # fmt: skip
def test_schema_rules(change: Any, expected: list[str], tmp_path: Path) -> None:
    found = codes(write(tmp_path, change), "schema")
    assert [c for c in found if not c.startswith("TDS-M")] == expected  # M010, M008: not S rules


@pytest.mark.parametrize(
    "path",
    [
        "../outside.parquet",
        "bars/../../outside.parquet",
        "OUTSIDE",
        "C:\\x.parquet",
        "link",
        "a\0b",
    ],
)
def test_M012_path_escape(path: str, tmp_path: Path) -> None:
    outside = tmp_path / "outside.parquet"
    outside.write_bytes(b"x")
    package = write(tmp_path / "pkg", add_bars_file(str(outside) if path == "OUTSIDE" else path))
    (package / "link").symlink_to(outside)  # a symbolic link leading out of the package
    assert [c for c in codes(package) if c != "TDS-M005"] == ["TDS-M012"]


def test_M012_link_inside_the_package_is_safe(tmp_path: Path) -> None:
    package = write(tmp_path, add_bars_file("link", len(build.base()[1][build.INSTRUMENTS])))
    (package / "link").symlink_to(package / build.INSTRUMENTS)
    assert codes(package) == []


def test_M013_duplicate_path(tmp_path: Path) -> None:
    def twice(m: dict[str, Any], f: Any) -> None:
        again = dict(m["datasets"][0]["files"][0])
        again["path"] = "instruments/./part-00000.parquet"  # the same file, spelled differently
        build.bars(m)["files"].append(again)

    assert codes(write(tmp_path, twice)) == ["TDS-M013"]


@pytest.mark.parametrize(
    ("where", "value"),
    [
        ("availability", {"rule": "next_session_close"}),
        ("availability", {"rule": "ts_end+15min"}),
        ("availability", {"rule": 15}),
        ("availability", "ts_end_when_ready"),  # a bare rule string is read too
        ("availability", {"known": "ts_known_from"}),  # none of 4.2's forms (#276)
        ("availability", {"column": "ts_known_from", "terms": "ts_terms_available"}),
        ("availability", {"exit": "ts_exit_known"}),  # half of the two-instant form
        ("availability", {"column": 1}),
        ("availability", 15),
        ("hashes", {"hash_spec": ["tds-hash-1"]}),  # not a string: a finding, never a crash
        (
            "params",
            {"freq": "1d", "price_basis": "raw", "availability_by_column": {"is_halted": "x"}},
        ),
        ("hashes", {"hash_spec": "tds-hash-2"}),
    ],
)
def test_M014_unknown_required_rule(where: str, value: object, tmp_path: Path) -> None:
    def change(m: dict[str, Any], f: Any) -> None:
        (m if where == "hashes" else build.bars(m))[where] = value

    assert codes(write(tmp_path, change)) == ["TDS-M014"]


#: TDS 5.5's lists; closed and affecting execution by the maintainer's decision (#80 Decisions).
BARS_PARAMS = {
    "price_basis": ("raw", "split_adjusted", "total_adjusted"),
    "density": ("dense", "sparse"),
    "bar_time": ("session", "utc_day", "interval"),
}


@pytest.mark.parametrize(
    ("param", "value"),
    [(param, value) for param, values in BARS_PARAMS.items() for value in values],
)
def test_listed_bars_params_pass(param: str, value: str, tmp_path: Path) -> None:
    assert codes(write(tmp_path, lambda m, f: build.bars(m)["params"].update({param: value}))) == []


@pytest.mark.parametrize(
    ("param", "value"),
    [
        ("price_basis", "dividend_adjusted"),
        ("density", "Dense"),
        ("bar_time", 1),
    ],
)
def test_M014_unknown_closed_bars_param(param: str, value: object, tmp_path: Path) -> None:
    result = check(
        write(tmp_path, lambda m, f: build.bars(m)["params"].update({param: value})),
        level="manifest",
    )
    assert [(f.code, f.dataset) for f in result.errors] == [("TDS-M014", "bars_1d")]
    assert param in result.errors[0].message


def test_a_null_closed_param_is_no_value(tmp_path: Path) -> None:
    # JSON null is not declared, not a new value: no M014 (#80 Decisions, item 1)
    package = write(tmp_path, lambda m, f: build.bars(m)["params"].update(density=None))
    assert codes(package) == []


def test_closed_params_belong_to_bars_only(tmp_path: Path) -> None:
    # TDS 5.5 lists them for `bars`; another kind's `params` are not read for them
    package = write(tmp_path, lambda m, f: m["datasets"][0].update(params={"density": "x"}))
    assert codes(package) == []
    odd = write(tmp_path / "odd", lambda m, f: build.bars(m).update(kind=["bars"]))
    assert "TDS-M014" not in codes(odd)  # a kind that is not a string: findings, not a crash


KNOWN_RULES = "column ts_end ts_end+PT15M session_open session_close next_session_open"
KNOWN_RULES += " next_session_open(known_on) ts_recv ts_recv+PT0.5S ts_recv_else(ts_event+PT1S)"


@pytest.mark.parametrize("rule", KNOWN_RULES.split())
def test_known_availability_rules_pass(rule: str, tmp_path: Path) -> None:
    package = write(tmp_path, lambda m, f: build.bars(m).update(availability={"rule": rule}))
    assert codes(package) == []


@pytest.mark.parametrize(
    "form",
    [  # TDS 4.2, 6.2: the column forms (#276)
        {"column": "ts_available"},
        {"column": "ts_known_from"},
        {"effect": "ts_effective", "terms": "ts_terms_available"},
        {"exit": "ts_exit_known", "value": "ts_value_available"},
    ],
)
def test_availability_column_forms_pass(form: dict[str, str], tmp_path: Path) -> None:
    assert codes(write(tmp_path, lambda m, f: build.bars(m).update(availability=form))) == []


def test_M010_coverage_names_an_undeclared_market(tmp_path: Path) -> None:
    by_market: dict[str, Any] = {"coverage": {"by_market": {"US": {}, "JP": {}}}}
    assert codes(write(tmp_path, lambda m, f: build.bars(m).update(by_market))) == ["TDS-M010"]


def test_profiles_must_be_strings(tmp_path: Path) -> None:
    assert codes(write(tmp_path, lambda m, f: m.update(profiles=[123]))) == ["TDS-M001"]


@pytest.mark.parametrize(
    ("key", "where"), [("files", "dataset"), ("path", "file"), ("bytes", "file")]
)
def test_M003_minimal_dataset_and_file_fields(key: str, where: str, tmp_path: Path) -> None:
    def drop(m: dict[str, Any], f: Any) -> None:
        (build.bars(m) if where == "dataset" else build.bars(m)["files"][0]).pop(key)
        if key in ("files", "path"):
            f.pop(build.BARS)  # no longer listed: it would be M005

    assert codes(write(tmp_path, drop)) == ["TDS-M003"]


@pytest.mark.parametrize(
    ("price_basis", "bars_missing"), [("raw", False), ("total_adjusted", True)]
)
def test_core_requires_raw_dense_daily_bars(
    price_basis: str, bars_missing: bool, tmp_path: Path
) -> None:
    params = {"freq": "1d", "price_basis": price_basis, "density": "dense"}
    package = write(tmp_path, lambda m, f: build.bars(m).update(params=params))
    result = check(package, level="manifest", profiles=["tds:equity-daily-core@1.0"])
    assert ("dataset bars" in " ".join(e.message for e in result.errors)) is bars_missing


def test_producer_hint_travels_with_its_code(tmp_path: Path) -> None:
    manifest, files = build.package("TDS-M003", "fail")
    manifest["producer"]["hints"] = {"TDS-M003": "re-run the export", "TDS-M006": "unused"}
    (error,) = check(build.write(tmp_path, manifest, files), level="manifest").errors
    assert (error.code, error.hint) == ("TDS-M003", "re-run the export")
    assert error.to_dict()["hint"] == "re-run the export"


def test_jsonl_ends_with_the_summary(tmp_path: Path) -> None:
    package = build.write(tmp_path, *build.package("TDS-M003", "fail"))
    *findings, last = check(package, level="manifest").to_jsonl().splitlines()
    assert [line.count('"code": "TDS-M003"') for line in findings] == [1]
    assert last.startswith('{"summary": {"errors": 1, "warnings": 0, "level": "manifest"')
