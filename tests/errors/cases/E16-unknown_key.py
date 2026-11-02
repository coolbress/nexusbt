"""E16, config: a misspelt key in nexusbt.toml."""

# ruff: noqa: N999 - spec 8.4b names the file `<code>-<condition>.py`; it is run, not imported

from pathlib import Path

import nexusbt as nx


def case() -> None:
    Path("nexusbt.toml").write_text("[execution]\nmax_participaton = 0.1\n", encoding="utf-8")
    nx.config()
