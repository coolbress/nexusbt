"""`nexusbt <command>`: the commands of spec 3.10, each calling the api function of the same name.

The skeleton registers the names only. A command that is called raises
`NotImplementedError` until its own ticket lands, as the public names of 2.4 do.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import warnings
import zipfile
from collections.abc import Callable, Sequence
from importlib import metadata
from pathlib import Path
from typing import Any

from nexusbt import api
from nexusbt.api import _doctor as api_doctor
from nexusbt.contracts import RUN_SCHEMA, EngineBugError, NexusBTError

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
    sub = {name: commands.add_parser(name, help=help_text) for name, help_text in COMMANDS}
    sub["init"].add_argument("--data-root", metavar="PATH")
    sub["init"].add_argument("--new-family", metavar="REASON")
    sub["rerun"].add_argument("run_id", metavar="RUN_ID")
    for flag in ("--new-snapshot", "--trust", "--save-detail"):  # 3.10's row
        sub["rerun"].add_argument(flag, action="store_true")
    commands.add_parser("bugreport", help="bundle a run for a bug report").add_argument("run_id")
    with warnings.catch_warnings():  # the printer is put back when the command returns
        warnings.showwarning = _printer(warnings.showwarning)
        try:
            return _run(parser.parse_args(argv))
        except EngineBugError as bug:  # 6.6 E46, from any command: exit code 2
            print(bug, file=sys.stderr)
            return 2
        except NexusBTError as error:  # 3.10: a user error is exit code 1
            print(error, file=sys.stderr)
            return 1


#: The first line of 6.6's shape, `{ClassName} [{code}]`, which the engine's warnings carry.
_SHAPE = re.compile(r"[A-Z]\w* \[E\d+\]")


def _printer(python: Callable[..., None]) -> Callable[..., None]:
    """3.10 (#649): a 6.6 warning on standard error as its own lines, as an error is, without
    Python's `file:line: UserWarning:` and the source line. Python applies the person's filters
    (`-W`, `PYTHONWARNINGS`; by default a text once per place) before it prints, so which
    warnings print is as before (#684); any other warning goes to `python`, Python's printer."""

    def show(message: Warning | str, category: type[Warning], *rest: Any, **kw: Any) -> None:
        text = str(message)
        if _SHAPE.match(text):
            print(text, file=sys.stderr)
        else:
            python(message, category, *rest, **kw)

    return show


def _run(args: argparse.Namespace) -> int:
    if args.command == "bugreport":
        print(_bundle(args.run_id))
        return 0
    if args.command == "init":
        print(api_doctor.init(args.data_root, new_family=args.new_family))
        return 0
    if args.command == "doctor":
        print(api_doctor.doctor())
        return 0
    if args.command == "stubs":
        print(api.stubs())
        return 0
    if args.command == "rerun":  # 3.10; E15 and E31 come out as a user error, exit code 1
        if args.save_detail:  # 5.9.4's tier (3): no kind writes `detail/` yet
            raise NotImplementedError("nexusbt rerun --save-detail: tier-3 outputs come later")
        run = api.rerun(args.run_id, new_snapshot=args.new_snapshot, trust=args.trust)
        print(f"run {run.run_id} from {args.run_id}\n{run.comparison}")  # the line says if equal
        # 3.10 (#655): the code follows the comparison line; a new snapshot's run (3.8) is 0
        differ = str(run.comparison).startswith("outputs differ")
        return 4 if differ and not args.new_snapshot else 0
    raise NotImplementedError(f"nexusbt {args.command}: not built yet (its ticket is in spec 10.1)")
