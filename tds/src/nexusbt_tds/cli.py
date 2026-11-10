"""`tds <command>`: the commands TDS 8.1 marks implemented for nexusbt-tds 1.0.x.

`check`, `hash`, `manifest build`, `describe` and `import csv` are built. Exit codes are TDS
8.1's: 0 pass, 1 errors, 2 warnings with `--strict`, 64 usage, 66 input missing, 70 checker
internal error.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import NoReturn

from .check import CheckResult, check
from .draft import build_manifest
from .hash import HashError, package_hashes, spilled_note, write_hashes
from .import_csv import REPORT, CsvImportError, import_csv
from .manifest import MANIFEST, ManifestError, read_manifest

#: TDS 8.1, in its order; `derive` and `export` are planned there, not implemented.
COMMANDS: tuple[tuple[str, str], ...] = (
    ("check", "check a package against its declared profiles"),
    ("hash", "compute the file, dataset and package hashes"),
    ("manifest", "scan a folder and draft tds.json"),
    ("describe", "a summary of coverage, columns and profiles"),
    ("import", "build a package from another format (csv)"),
)
OK, ERRORS, WARNINGS, USAGE, NO_INPUT, INTERNAL = 0, 1, 2, 64, 66, 70
_TMP = "folder for the value hash's and K001's temporary sorted runs (default: beside the package)"


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        self.print_usage(sys.stderr)
        self.exit(USAGE, f"{self.prog}: error: {message}\n")


def main(argv: Sequence[str] | None = None) -> int:
    parser = _Parser(prog="tds", description=__doc__.split("\n", 1)[0])
    commands = parser.add_subparsers(dest="command", metavar="COMMAND", required=True)
    for name, help_text in COMMANDS:
        sub = commands.add_parser(name, help=help_text)
        if name == "check":
            sub.add_argument("path", type=Path)
            sub.add_argument("--profile", action="append", help="repeatable; default: declared")
            sub.add_argument(  # TDS 8.1: `schema`, also once `full` is built (#56 Decisions)
                "--level", choices=["manifest", "schema", "full"], default="schema"
            )
            sub.add_argument("--datasets", help="comma-separated dataset names")
            sub.add_argument("--max-errors", type=int, default=1000)
            sub.add_argument("--format", choices=["text", "json"], default="text")
            sub.add_argument("--strict", action="store_true", help="exit 2 on warnings")
            sub.add_argument("--tmp-dir", type=Path, help=_TMP)
        elif name == "describe":
            sub.add_argument("path", type=Path)
            sub.add_argument("dataset", nargs="?")
        elif name == "hash":
            sub.add_argument("path", type=Path)
            sub.add_argument("--write", action="store_true", help="write the hashes into tds.json")
            sub.add_argument("--tmp-dir", type=Path, help=_TMP)
        elif name == "import":
            sub.add_argument("source", choices=["csv"])  # TDS 8.1: the others are planned
            sub.add_argument("path", type=Path, metavar="MAPPING")
            sub.add_argument("--out", type=Path, required=True, help="the new package folder")
        elif name == "manifest":
            sub.add_argument("action", choices=["build"])
            sub.add_argument("path", type=Path)
    args = parser.parse_args(argv)
    run = {"check": _check, "describe": _describe, "hash": _hash, "import": _import,
           "manifest": _manifest}[args.command]  # fmt: skip
    if not args.path.exists():
        print(f"tds {args.command}: {args.path}: no such file or folder", file=sys.stderr)
        return NO_INPUT
    try:
        return run(args)
    except Exception as exc:  # TDS 8.1: a checker fault is 70, never a pass or a data error
        print(f"tds {args.command}: internal error: {exc!r}", file=sys.stderr)
        return INTERNAL


def _check(args: argparse.Namespace) -> int:
    result = check(
        args.path,
        level=args.level,
        profiles=args.profile,
        datasets=args.datasets.split(",") if args.datasets else None,
        max_errors=args.max_errors,
        tmp_dir=args.tmp_dir,
    )
    sys.stdout.write(result.to_jsonl() if args.format == "json" else _text(result))
    if result.failed:
        return ERRORS
    return WARNINGS if result.warnings and args.strict else OK


def _text(result: CheckResult) -> str:
    lines = []
    for f in (*result.errors, *result.warnings):
        head = " ".join(x for x in (f.severity, f.code, f.dataset, f.file) if x)
        lines.append(f"{head}: {f.message}")
        if f.hint:
            lines.append(f"  hint: {f.hint}")
    for name, s in result.profiles.items():
        declared = "declared" if s.declared else "not declared"
        lines.append(f"{name}: {declared}, verified to {s.verified_level}, {s.result}")
    lines += [f"note: {note}" for note in result.notes]
    lines.append(
        f"{result.error_count} errors, {len(result.warnings)} warnings at level {result.level};"
        f" {len(result.unchecked)} rules not checked at this level"
    )
    return "\n".join(lines) + "\n"


def _hash(args: argparse.Namespace) -> int:
    """Package hashes, then `<dataset> <value_sha256>`, then `<file> <sha256> <value_sha256>`."""
    spilled: list[Path] = []
    try:
        run = write_hashes if args.write else package_hashes
        hashes = run(args.path, tmp_dir=args.tmp_dir, spilled=spilled)
    except (ManifestError, HashError) as exc:
        print(f"tds hash: {exc}", file=sys.stderr)
        return ERRORS
    finally:
        if spilled:
            print(f"tds hash: {spilled_note(spilled)}", file=sys.stderr)
    for name in ("physical_sha256", "value_sha256", "semantic_sha256"):
        print(f"{name} {hashes[name]}")
    for name, value in sorted(hashes["datasets"].items()):
        print(f"{name} {value}")
    for path, file in sorted(hashes["files"].items()):
        print(f"{path} {file['sha256']} {file['value_sha256']}")
    return OK


def _import(args: argparse.Namespace) -> int:
    try:
        out = import_csv(args.path, args.out)
    except CsvImportError as exc:
        print(f"tds import csv: {exc}", file=sys.stderr)
        return ERRORS
    print(f"wrote {out} and {out.parent / REPORT}")
    return OK


def _manifest(args: argparse.Namespace) -> int:
    try:
        draft = build_manifest(args.path)
    except ManifestError as exc:
        print(f"tds manifest build: {exc}", file=sys.stderr)
        return ERRORS
    print(f"wrote {draft.root / MANIFEST}; fill in what its TODO lists, then run `tds check`")
    return OK


def _describe(args: argparse.Namespace) -> int:
    try:
        manifest = read_manifest(args.path)
    except ManifestError as exc:
        print(f"tds describe: TDS-M001 {exc}", file=sys.stderr)
        return ERRORS
    data = manifest.data
    datasets = [d for d in manifest.datasets if args.dataset in (None, d.get("name"))]
    if args.dataset and not datasets:
        print(f"tds describe: no dataset {args.dataset!r} in tds.json", file=sys.stderr)
        return NO_INPUT
    print(f"{data.get('name')} {data.get('snapshot_id')} (tds {data.get('tds_version')})")
    print("profiles: " + (", ".join(manifest.profiles) or "none"))
    for ds in datasets:
        cov = ds.get("coverage")
        cov = cov if isinstance(cov, dict) else {}
        span = f"{cov.get('ts_min', '?')}..{cov.get('ts_max', '?')}"
        files, columns = ds.get("files") or [], ds.get("columns") or []
        print(f"  {ds.get('name')} [{ds.get('kind')} {ds.get('schema_version')}]", end=" ")
        print(f"rows={ds.get('rows')} {span} files={len(files)} columns={len(columns)}")
        if args.dataset:
            for column in columns:
                if isinstance(column, dict):
                    print(f"    {column.get('name')} {column.get('type')}")
    return OK
