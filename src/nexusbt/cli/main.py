"""`nexusbt <command>`: the commands of spec 3.10, each calling the api function of the same name.

The skeleton registers the names only. A command that is called raises
`NotImplementedError` until its own ticket lands, as the public names of 2.4 do.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence

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


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="nexusbt", description=__doc__.split("\n", 1)[0])
    commands = parser.add_subparsers(dest="command", metavar="COMMAND", required=True)
    for name, help_text in COMMANDS:
        commands.add_parser(name, help=help_text)
    args = parser.parse_args(argv)
    raise NotImplementedError(f"nexusbt {args.command}: not built yet (its ticket is in spec 10.1)")
