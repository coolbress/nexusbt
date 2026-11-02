"""E18, config: a feature outside v1 (`history_mode = "system"`)."""

# ruff: noqa: N999 - spec 8.4b names the file `<code>-<condition>.py`; it is run, not imported

from pathlib import Path

import nexusbt as nx


def case() -> None:
    Path("nexusbt.toml").write_text('[data]\nhistory_mode = "system"\n', encoding="utf-8")
    nx.config()
