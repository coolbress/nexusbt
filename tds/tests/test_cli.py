"""TDS 8.1, 8.4: `tds check` exit codes and its JSON Lines output; `tds describe`."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from nexusbt_tds import cli

from .conformance_build import build

CONFORMANCE = Path(__file__).parents[1] / "conformance"
FINDING_KEYS = {"code", "severity", "message", "dataset", "file", "key", "count", "hint"}


def package(tmp_path: Path, code: str, side: str) -> str:
    return str(build.write(tmp_path / code / side, *build.package(code, side)))


def run(argv: list[str]) -> int:
    try:
        return cli.main(argv)
    except SystemExit as exit_:
        return int(exit_.code or 0)


def test_exit_codes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    clean, warns = package(tmp_path, "TDS-M005", "pass"), package(tmp_path, "TDS-M005", "fail")
    assert run(["check", clean]) == 0
    assert run(["check", package(tmp_path, "TDS-M012", "fail")]) == 1
    assert run(["check", warns]) == 0
    assert run(["check", warns, "--strict"]) == 2
    assert run(["check", clean, "--level", "every"]) == 64
    assert run(["check"]) == 64
    assert run(["check", str(tmp_path / "missing")]) == 66

    def broken(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("checker fault")

    monkeypatch.setattr(cli, "check", broken)
    assert run(["check", clean]) == 70


def test_jsonl_output_schema(capsys: pytest.CaptureFixture[str]) -> None:
    # spec 10.1 T0.13a "done means", on the package committed under tds/conformance
    argv = ["check", str(CONFORMANCE / "TDS-M012" / "fail"), "--format", "json"]
    assert run([*argv, "--level", "manifest"]) == 1
    finding, last = (json.loads(line) for line in capsys.readouterr().out.splitlines())
    assert {"code", "severity", "message"} <= set(finding) <= FINDING_KEYS
    assert (finding["code"], finding["severity"]) == ("TDS-M012", "error")
    summary = last["summary"]
    assert set(summary) == {"errors", "warnings", "level", "profiles", "unchecked"}
    assert (summary["errors"], summary["warnings"], summary["level"]) == (1, 0, "manifest")
    assert summary["profiles"] == {
        "tds:minimal-daily@1.0": {"declared": True, "verified_level": "manifest", "result": "fail"}
    }
    assert "TDS-K001" in summary["unchecked"]


def test_summary_counts_errors_max_errors_does_not_print(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    manifest, files = build.base()
    for key in ("snapshot_id", "writer", "hashes"):  # three TDS-M003 errors
        manifest.pop(key)
    path = str(build.write(tmp_path, manifest, files))
    argv = ["check", path, "--level", "manifest", "--format", "json", "--max-errors", "1"]
    assert run(argv) == 1
    *findings, last = (json.loads(line) for line in capsys.readouterr().out.splitlines())
    assert [f["code"] for f in findings] == ["TDS-M003"]
    assert last["summary"]["errors"] == 3
    assert run([*argv[:-1], "0", "--format", "text"]) == 1  # none printed, still a failure
    assert capsys.readouterr().out.splitlines()[-1].startswith("3 errors, 0 warnings")
    assert run([*argv[:-1], "-1"]) == 1  # a negative limit prints none, never "all but one"
    *findings, last = (json.loads(line) for line in capsys.readouterr().out.splitlines())
    assert (findings, last["summary"]["errors"]) == ([], 3)


@pytest.mark.parametrize("code", ["TDS-S002", "TDS-S006"])
def test_schema_level_done_means(code: str, capsys: pytest.CaptureFixture[str]) -> None:
    # spec 10.1 T0.13c "done means": `tds check tds/conformance/TDS-S002/fail --format json`;
    # #117 asks the same of TDS-S006 (its fail package: the code and exit code 1)
    argv = ["check", str(CONFORMANCE / code / "fail"), "--format", "json"]
    assert run(argv) == 1  # as written: no `--level`, the CLI's default is `schema` (TDS 8.1)
    *findings, last = (json.loads(line) for line in capsys.readouterr().out.splitlines())
    assert [f["code"] for f in findings] == [code]
    assert last["summary"]["level"] == "schema"


def test_committed_packages_match_the_generator(tmp_path: Path) -> None:
    build.build(tmp_path)

    def tree(root: Path) -> dict[str, bytes]:
        files = (p for p in root.glob("TDS-*/**/*") if p.is_file())
        return {p.relative_to(root).as_posix(): p.read_bytes() for p in files}

    assert tree(CONFORMANCE) == tree(tmp_path), "run: uv run python tds/conformance/build.py"


def test_describe(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = package(tmp_path, "TDS-M005", "pass")
    assert run(["describe", root]) == 0
    out = capsys.readouterr().out
    assert "profiles: tds:minimal-daily@1.0" in out
    assert "bars_1d [bars 1.0]" in out
    assert run(["describe", root, "no_such_dataset"]) == 66
