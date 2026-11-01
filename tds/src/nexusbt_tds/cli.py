"""`tds <command>`: the commands TDS 8.1 marks implemented for nexusbt-tds 1.0.x.

The skeleton registers the names only. A command that is called raises
`NotImplementedError` until its own ticket lands.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence

#: TDS 8.1, in its order; `derive` and `export` are planned there, not implemented.
COMMANDS: tuple[tuple[str, str], ...] = (
    ("check", "check a package against its declared profiles"),
    ("hash", "compute the file, dataset and package hashes"),
    ("manifest", "scan a folder and draft tds.json"),
    ("describe", "a summary of coverage, columns and profiles"),
    ("import", "build a package from another format (csv)"),
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tds", description=__doc__.split("\n", 1)[0])
    commands = parser.add_subparsers(dest="command", metavar="COMMAND", required=True)
    for name, help_text in COMMANDS:
        commands.add_parser(name, help=help_text)
    args = parser.parse_args(argv)
    raise NotImplementedError(f"tds {args.command}: not built yet (its ticket is in spec 10.1)")
