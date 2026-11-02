"""The two entry points list their subcommands (3.10, TDS 8.1); a called one is not built yet."""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence

import pytest

from nexusbt.cli.main import main as nexusbt_main
from nexusbt_tds.cli import main as tds_main

Main = Callable[[Sequence[str]], int]

#: Spec 3.10, the command table, in its order.
NEXUSBT = ["init", "config", "doctor", "new", "evaluate", "backtest", "screen", "explain", "sweep"]
NEXUSBT += ["compare", "live", "reconcile", "book", "runs", "rerun", "stubs", "check"]
#: TDS 8.1, the commands its status table marks implemented for `nexusbt-tds` 1.0.x.
TDS = ["check", "hash", "manifest", "describe", "import"]


@pytest.mark.parametrize(
    ("main", "prog", "commands"), [(nexusbt_main, "nexusbt", NEXUSBT), (tds_main, "tds", TDS)]
)
def test_help_lists_the_commands(
    main: Main, prog: str, commands: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit, match="0"):
        main(["--help"])
    out = capsys.readouterr().out
    assert out.startswith(f"usage: {prog} ")
    # a narrow terminal moves a long command's help to the next line: a space or a newline follows
    assert [c for c in commands if not re.search(rf"\n    {c}\s", out)] == []


@pytest.mark.parametrize(("main", "command"), [(nexusbt_main, "backtest"), (tds_main, "hash")])
def test_a_command_is_not_built_yet(main: Main, command: str) -> None:
    with pytest.raises(NotImplementedError, match=command):
        main([command])
