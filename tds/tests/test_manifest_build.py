"""TDS 8.1: `tds manifest build PATH` drafts tds.json for a folder of Parquet files (#258)."""

from __future__ import annotations

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
    (package / "notes" / "sub" / "a.parquet").write_bytes(b"not parquet")
    with pytest.raises(ManifestError, match="is not read as Parquet"):
        build_manifest(package)
    assert not (package / "tds.json").exists()
