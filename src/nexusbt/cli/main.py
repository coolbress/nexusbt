"""`nexusbt <command>`: the commands of spec 3.10, each calling the api function of the same name.

The skeleton registers the names only. A command that is called raises
`NotImplementedError` until its own ticket lands, as the public names of 2.4 do.
"""

from __future__ import annotations

import argparse
import json
import sys
import zipfile
from collections.abc import Sequence
from importlib import metadata
from pathlib import Path

from nexusbt.contracts import RUN_SCHEMA, EngineBugError

#: Spec 3.10, the command table, in its order.
COMMANDS: tuple[tuple[str, str], ...] = (
    ("init", "write a commented nexusbt.toml template"),
    ("config", "check the config file, or show the values in effect"),
    ("doctor", "report on the snapshot, its profiles, fallbacks, caches and stubs"),
    ("new", "create a factor or strategy file from a template"),
    ("evaluate", "evaluate a factor"),
    ("backtest", "run a backtest"),
    ("screen", "today's selection"),
    ("explain", "a term's value, or a strategy's decision path"),
    ("sweep", "a parameter grid"),
    ("compare", "a variant table over files or runs"),
    ("live", "fill pending orders, then today's decision"),
    ("reconcile", "compare a paper book with its records"),
    ("book", "manual instructions on a book"),
    ("runs", "list, render or prune runs"),
    ("rerun", "run a saved run again"),
    ("stubs", "regenerate the .pyi stubs"),
    ("check", "run the probes on a file"),
)


#: `demo`'s reproduction: the sample engine bug of 6.6 E46.
_DEMO = 'python -c "import nexusbt as nx; raise nx.EngineBugError.example()"'


def _version(distribution: str) -> str | None:
    try:
        return metadata.version(distribution)
    except metadata.PackageNotFoundError:
        return None


def _bundle(run_id: str) -> Path:
    """`./bugreport-<id>.zip`: the reproduction command, the manifest and the versions (6.6
    E46; the format is #52's Decisions, 2026-11-02). A saved run's folder comes with T1.14a."""
    if run_id != "demo":
        raise NotImplementedError("nexusbt bugreport of a saved run: run folders come with T1.14a")
    manifest = {"schema": RUN_SCHEMA, "run_id": run_id, "synthetic": True}
    versions = {name: _version(name) for name in ("nexusbt", "nexusbt-tds")}
    path = Path.cwd() / f"bugreport-{run_id}.zip"
    with zipfile.ZipFile(path, "w") as bundle:
        bundle.writestr("command.txt", _DEMO + "\n")
        bundle.writestr("manifest.json", json.dumps(manifest, indent=2))
        bundle.writestr("versions.json", json.dumps(versions | {"python": sys.version}, indent=2))
    return path


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="nexusbt", description=__doc__.split("\n", 1)[0])
    commands = parser.add_subparsers(dest="command", metavar="COMMAND", required=True)
    for name, help_text in COMMANDS:
        commands.add_parser(name, help=help_text)
    commands.add_parser("bugreport", help="bundle a run for a bug report").add_argument("run_id")
    try:
        return _run(parser.parse_args(argv))
    except EngineBugError as bug:  # 6.6 E46, from any command: exit code 2
        print(bug, file=sys.stderr)
        return 2


def _run(args: argparse.Namespace) -> int:
    if args.command == "bugreport":
        print(_bundle(args.run_id))
        return 0
    raise NotImplementedError(f"nexusbt {args.command}: not built yet (its ticket is in spec 10.1)")
