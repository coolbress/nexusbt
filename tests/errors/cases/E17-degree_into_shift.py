"""E17, your code: a split-adjusted price level fed to `shift(1)` (3.3, 3.4), refused when the
graph is checked."""

# ruff: noqa: N999 - spec 8.4b names the file `<code>-<condition>.py`; it is run, not imported

from nexusbt.contracts import SchemaRegistry
from nexusbt.pipeline import Price, bind


def case() -> None:
    bind(Price.close.latest.shift(1), SchemaRegistry(columns={}, labels={}))
