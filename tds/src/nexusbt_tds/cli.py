"""`tds <command>`: the commands TDS 8.1 marks implemented for nexusbt-tds 1.0.x.

`check` and `describe` are built; another command raises `NotImplementedError` until its own
ticket lands. Exit codes are TDS 8.1's: 0 pass, 1 errors, 2 warnings with `--strict`, 64 usage,
66 input missing, 70 checker internal error.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import NoReturn

from .check import CheckResult, check
from .manifest import ManifestError, read_manifest

#: TDS 8.1, in its order; `derive` and `export` are planned there, not implemented.
COMMANDS: tuple[tuple[str, str], ...] = (
    ("check", "check a package against its declared profiles"),
    ("hash", "compute the file, dataset and package hashes"),
    ("manifest", "scan a folder and draft tds.json"),
    ("describe", "a summary of coverage, columns and profiles"),
    ("import", "build a package from another format (csv)"),
)
OK, ERRORS, WARNINGS, USAGE, NO_INPUT, INTERNAL = 0, 1, 2, 64, 66, 70


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
            sub.add_argument("--sample-rows", type=int, help="full level only")
        elif name == "describe":
            sub.add_argument("path", type=Path)
            sub.add_argument("dataset", nargs="?")
    args = parser.parse_args(argv)
    if args.command not in ("check", "describe"):
        raise NotImplementedError(f"tds {args.command}: not built yet (its ticket is in spec 10.1)")
    if not args.path.exists():
        print(f"tds {args.command}: {args.path}: no such file or folder", file=sys.stderr)
        return NO_INPUT
    try:
        return _check(args) if args.command == "check" else _describe(args)
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
    )
    sys.stdout.write(result.to_jsonl() if args.format == "json" else _text(result))
    if result.errors:
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
    lines.append(
        f"{len(result.errors)} errors, {len(result.warnings)} warnings at level {result.level};"
        f" {len(result.unchecked)} rules not checked at this level"
    )
    return "\n".join(lines) + "\n"


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
