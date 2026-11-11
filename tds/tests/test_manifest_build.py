"""TDS 8.1: `tds manifest build PATH` drafts tds.json for a folder of Parquet files (#258)."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from nexusbt_tds import build_manifest, import_csv
from nexusbt_tds.cli import main
from nexusbt_tds.manifest import ManifestError

from .test_import_csv import BARS, CHAPTER_7, MINIMAL, write

BARS_FILE = "bars/freq=1d/market=US/year=2024/part-00000.parquet"
MINUTE_FILE = "bars/freq=1m/market=US/date=2024-01-02/part-00000.parquet"


def folder(tmp_path: Path) -> tuple[Path, dict[str, Any]]:
    """A folder of Parquet files with no tds.json, and the manifest its writer gave it."""
    mapping = write(tmp_path, {"instruments.csv": CHAPTER_7, "bars.csv": BARS,
                               "mapping.yaml": MINIMAL})  # fmt: skip
    package = import_csv(mapping, tmp_path / "pkg")
    written = json.loads((package / "tds.json").read_text(encoding="utf-8"))
    (package / "tds.json").unlink()
    return package, written


def findings(package: Path, capsys: pytest.CaptureFixture[str]) -> tuple[int, list[Any]]:
    capsys.readouterr()
    code = main(["check", str(package), "--level", "manifest", "--format", "json"])
    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    return code, [(f["code"], f.get("dataset"), f["message"]) for f in lines[:-1]]


def test_draft_lists_files_and_stats(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """When I run `tds manifest build` in a folder with a few Parquet files, then I see a
    `tds.json` draft written."""
    package, written = folder(tmp_path)
    assert main(["manifest", "build", str(package)]) == 0
    assert f"wrote {package / 'tds.json'}" in capsys.readouterr().out
    draft = json.loads((package / "tds.json").read_text(encoding="utf-8"))
    bars, instruments = draft["datasets"]  # in name order
    assert (bars["name"], bars["kind"], bars["schema_version"], bars["path"]) == (
        "bars", "bars", "1.0", "bars")  # fmt: skip
    assert (instruments["name"], instruments["kind"]) == ("instruments", "instruments")
    size = (package / BARS_FILE).stat().st_size
    sha256 = hashlib.sha256((package / BARS_FILE).read_bytes()).hexdigest()
    (file,) = bars["files"]
    assert (file["path"], file["rows"], file["bytes"], file["sha256"]) == (
        BARS_FILE, 1, size, sha256)  # fmt: skip
    assert (bars["rows"], instruments["rows"]) == (1, 1)
    # the hashes of the data alone are the ones the files' writer computed
    assert draft["hashes"]["physical_sha256"] == written["hashes"]["physical_sha256"]
    assert instruments["value_sha256"] == written["datasets"][0]["value_sha256"]
    assert "semantic_sha256" not in draft["hashes"]  # it covers fields the draft leaves open
    assert draft["writer"]["name"].startswith("parquet-cpp-arrow")
    # a tds.json that is there is never replaced; a folder with no Parquet file has no draft
    before = (package / "tds.json").read_bytes()
    assert main(["manifest", "build", str(package)]) == 1
    assert "tds.json is already there" in capsys.readouterr().err
    assert (package / "tds.json").read_bytes() == before
    (tmp_path / "empty").mkdir()
    assert main(["manifest", "build", str(tmp_path / "empty")]) == 1
    assert not (tmp_path / "empty" / "tds.json").exists()
    assert main(["manifest", "build", str(tmp_path / "missing")]) == 66
    with pytest.raises(SystemExit, match="64"):  # TDS 8.1: a usage error
        main(["manifest", "draft", str(package)])


def test_todo_fields_flagged(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """When I fill in the `TODO`s, then I see `tds check` pass; until then each one left is
    reported (INV-17)."""
    package, _ = folder(tmp_path)
    draft = dict(build_manifest(package).data)
    assert [line.split(":")[0] for line in draft["TODO"]] == [
        "profiles", "id_namespaces", "markets", "datasets[].availability", "datasets[].params",
        "datasets[].columns", "hashes"]  # fmt: skip
    code, found = findings(package, capsys)
    assert code == 1
    assert [f for f in found if f[0] == "TDS-M003"] == [
        ("TDS-M003", None, f"required manifest field {key!r} is missing")
        for key in ("profiles", "id_namespaces", "markets")
    ]
    assert ("TDS-M014", "bars", "unknown availability rule 'TODO'") in found
    assert "availability" not in draft["datasets"][1]  # instruments: no instant (TDS 5.1)

    draft["profiles"] = ["tds:minimal-daily@1.0"]
    draft["id_namespaces"] = {"XNYS": "ids as the files give them"}
    (package / "tds.json").write_text(json.dumps(draft), encoding="utf-8")
    assert [f[0] for f in findings(package, capsys)[1]].count("TDS-M003") == 1  # markets

    draft["markets"] = {"US": {"calendar_id": "XNYS", "currency": "USD"}}
    draft["datasets"][0] |= {"availability": {"rule": "ts_end"},
                             "params": {"freq": "1d", "price_basis": "total_adjusted"}}  # fmt: skip
    del draft["TODO"]
    (package / "tds.json").write_text(json.dumps(draft), encoding="utf-8")
    assert main(["check", str(package)]) == 0
    assert main(["hash", str(package), "--write"]) == 0
    capsys.readouterr()
    assert main(["check", str(package), "--level", "full"]) == 0
    assert "0 errors, 0 warnings at level full" in capsys.readouterr().out


def two_freqs(package: Path, names: dict[str, str | None]) -> None:
    """Rewrite the daily file and add a one-minute one, each stating `names[freq]` or no name."""
    day = pq.read_table(package / BARS_FILE)
    at = [dt.datetime(2024, 1, 2, 14, 30 + i, tzinfo=dt.UTC) for i in (0, 1)]
    minute = day.append_column("ts_start", pa.array(at[:1], pa.timestamp("us", "UTC")))
    minute = minute.append_column("ts_end", pa.array(at[1:], pa.timestamp("us", "UTC")))
    for rel, rows in ((BARS_FILE, day), (MINUTE_FILE, minute)):
        said = names[rel.split("/")[1][5:]]
        meta = {"tds.schema_version": "1.0"} | ({"tds.dataset": said} if said else {})
        (package / rel).parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(rows.replace_schema_metadata(meta), package / rel)


def filled(package: Path, draft: dict[str, Any]) -> None:
    """Write the draft with its `TODO`s filled in, the `freq` only where the draft left it."""
    bars = {"availability": {"rule": "ts_end"}, "params": {"price_basis": "total_adjusted"}}
    for entry in (d for d in draft["datasets"] if d.get("kind") == "bars"):
        freq = {"freq": entry["path"][-2:]} | entry.get("params", {})
        entry |= bars | {"params": bars["params"] | freq}
    draft |= {"profiles": [], "id_namespaces": {"XNYS": "ids as the files give them"},
              "markets": {"US": {"calendar_id": "XNYS", "currency": "USD"}}}  # fmt: skip
    del draft["TODO"]
    (package / "tds.json").write_text(json.dumps(draft), encoding="utf-8")


def test_folder_with_two_datasets_of_one_kind(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """#371: `bars/freq=1d/...` and `bars/freq=1m/...` are two datasets in the draft, by the name
    the files state, else by `freq=`; any other mix of partition keys is one, said in `TODO`."""
    package, _ = folder(tmp_path)
    # (1) the files say their dataset: one dataset per name, each with the path of its files
    two_freqs(package, {"1d": "daily", "1m": "minute"})
    draft = dict(build_manifest(package).data)
    assert [(d["name"], d.get("kind"), d["path"], [f["path"] for f in d["files"]], d.get("params"))
            for d in draft["datasets"] if d.get("kind") == "bars"] == [
        ("daily", "bars", "bars/freq=1d", [BARS_FILE], None),
        ("minute", "bars", "bars/freq=1m", [MINUTE_FILE], None)]  # fmt: skip
    assert not [line for line in draft["TODO"] if "mixes" in line]
    filled(package, draft)
    assert main(["check", str(package)]) == 0  # level schema: S010 reads the names
    (package / "tds.json").unlink()
    # (2) no name in the files: one dataset per `freq=` value, as TDS 4.2 lists `bars_1d`
    two_freqs(package, {"1d": None, "1m": None})
    draft = dict(build_manifest(package).data)
    assert [(d["name"], d["kind"], d["path"], [f["path"] for f in d["files"]], d["params"])
            for d in draft["datasets"] if d.get("kind") == "bars"] == [
        ("bars_1d", "bars", "bars/freq=1d", [BARS_FILE], {"freq": "1d"}),
        ("bars_1m", "bars", "bars/freq=1m", [MINUTE_FILE], {"freq": "1m"})]  # fmt: skip
    filled(package, draft)
    assert main(["check", str(package), "--level", "manifest"]) == 0
    capsys.readouterr()
    assert main(["check", str(package), "--format", "json"]) == 1  # level schema
    errors = [json.loads(line) for line in capsys.readouterr().out.splitlines()[:-1]]
    # the one thing left is the files': they still state no name (3.7), which no draft can add
    assert {(f["code"], f["file"]) for f in errors if f["severity"] == "error"} == {
        ("TDS-S010", BARS_FILE), ("TDS-S010", MINUTE_FILE)}  # fmt: skip
    (package / "tds.json").unlink()
    # one name and one file with none: the name's dataset, and the `freq=` one for the other
    two_freqs(package, {"1d": "daily", "1m": None})
    assert [(d["name"], d["path"]) for d in build_manifest(package).data["datasets"]] == [
        ("bars_1m", "bars/freq=1m"),
        ("daily", "bars/freq=1d"),
        ("instruments", "instruments"),
    ]
    (package / "tds.json").unlink()
    # (3) any other mix of first keys: one dataset, and `TODO` names the folder and the keys
    for rel in ("notes/b=2/a.parquet", "notes/a=1/a.parquet", "notes/a=1/c=3/b.parquet"):
        (package / rel).parent.mkdir(parents=True)
        pq.write_table(pa.table({"x": [1]}), package / rel)
    draft = dict(build_manifest(package).data)
    notes = draft["datasets"][3]
    assert (notes["name"], notes["path"], notes["rows"], "params" in notes) == (
        "notes", "notes", 3, False)  # fmt: skip
    assert draft["TODO"][0] == (
        "datasets[] to split: notes mixes the partition keys a, b; a dataset has one layout"
        " (TDS 3.6), so list each layout's files as a dataset of its own"
    )
    (package / "tds.json").unlink()
    # the edges: two names in one partition folder both keep the folder as path; a `freq=` with
    # no value, or a file of that name, is no split; one `freq=` value alone is rule (2) too; a
    # name the files state that a `freq=` value gives too is refused
    for rel, said in (("odd/freq=1d/a.parquet", "p"), ("odd/freq=1d/b.parquet", "q"),
                      ("gap/freq=/a.parquet", None), ("gap/freq=1d/a.parquet", None),
                      ("flat/freq=1d.parquet", None), ("solo/freq=1d/a.parquet", None),
                      ("wide/freq=1d/a.parquet", "w"), ("wide/freq=1m/a.parquet", "w"),
                      ("wide/freq=1m/b.parquet", "v")):  # fmt: skip
        (package / rel).parent.mkdir(parents=True, exist_ok=True)
        rows = pa.table({"x": [1]}).replace_schema_metadata({"tds.dataset": said} if said else None)
        pq.write_table(rows, package / rel)
    paths = {d["name"]: d["path"] for d in build_manifest(package).data["datasets"]}
    assert (paths["p"], paths["q"], paths["gap"]) == ("odd", "odd", "gap")
    assert (paths["flat"], paths["solo_1d"]) == ("flat", "solo/freq=1d")
    assert (paths["w"], paths["v"]) == ("wide", "wide")  # a name over two folders, one shared
    (package / "tds.json").unlink()
    two_freqs(package, {"1d": None, "1m": "bars_1d"})
    with pytest.raises(ManifestError, match="the dataset name bars_1d"):
        build_manifest(package)


def test_folder_the_schema_files_do_not_name(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A file of an unknown kind is listed, with `kind` left out (TDS-M003) and said in TODO."""
    package, _ = folder(tmp_path)
    (package / "notes" / "sub").mkdir(parents=True)
    pq.write_table(pa.table({"x": [1, 2]}), package / "notes" / "sub" / "a.parquet")
    draft = build_manifest(package).data
    notes = draft["datasets"][2]
    assert (notes["name"], notes["path"], notes["rows"]) == ("notes_sub", "notes/sub", 2)
    assert (notes.get("kind"), notes["availability"]) == (None, "TODO")
    assert sorted(notes["files"][0]) == ["bytes", "path", "rows", "sha256"]  # no value hash
    assert draft["TODO"][0] == "datasets[].kind: one of the TDS 5 kinds, for notes_sub"
    missing = ("TDS-M003", "notes_sub", "dataset field 'kind' is missing")
    assert missing in findings(package, capsys)[1]
    # a file that is no dataset's: at the top, or in a plain folder under a `key=value` one
    for odd in ("top.parquet", "bars/freq=1d/plain/b.parquet"):
        (package / "tds.json").unlink(missing_ok=True)
        (package / odd).parent.mkdir(exist_ok=True)
        (package / "notes" / "sub" / "a.parquet").replace(package / odd)
        with pytest.raises(ManifestError, match="a folder of its own"):
            build_manifest(package)
        (package / odd).replace(package / "notes" / "sub" / "a.parquet")
    # rows that are not the kind's (an integer id), metadata that is not text: a draft all the same
    odd_rows = pa.table({"instrument_id": [1, 2]}).replace_schema_metadata({b"blob": b"\xff\xfe"})
    pq.write_table(odd_rows, package / "instruments" / "part-00000.parquet")
    assert "value_sha256" not in build_manifest(package).data["datasets"][1]
    (package / "tds.json").unlink()
    # two folders under one name (`notes/sub`, `notes_sub`), a tds.json that links to nowhere
    (package / "notes_sub").mkdir()
    pq.write_table(pa.table({"x": [1]}), package / "notes_sub" / "a.parquet")
    with pytest.raises(ManifestError, match="two folders give the dataset name notes_sub"):
        build_manifest(package)
    (package / "notes_sub" / "a.parquet").unlink()
    (package / "tds.json").symlink_to(tmp_path / "elsewhere.json")
    with pytest.raises(ManifestError, match="already there"):
        build_manifest(package)
    (package / "tds.json").unlink()
    assert not (tmp_path / "elsewhere.json").exists()
    (package / "notes" / "sub" / "a.parquet").write_bytes(b"not parquet")
    with pytest.raises(ManifestError, match="is not read as Parquet"):
        build_manifest(package)
    assert not (package / "tds.json").exists()
