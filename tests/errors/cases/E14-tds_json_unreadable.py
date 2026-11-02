"""E14, data: `[data] path` names a folder with no tds.json, so its markets cannot be read."""

# ruff: noqa: N999 - spec 8.4b names the file `<code>-<condition>.py`; it is run, not imported

from pathlib import Path

import nexusbt as nx


def case() -> None:
    Path("nexusbt.toml").write_text(f"[data]\npath = '{Path.cwd() / 'snap'}'\n", encoding="utf-8")
    nx.config()
