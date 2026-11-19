"""E16, config: an `adjustment` other than "degree 0" and "degree 1" (3.3), refused when the
term is built."""

# ruff: noqa: N999 - spec 8.4b names the file `<code>-<condition>.py`; it is run, not imported

import nexusbt as nx
from nexusbt.pipeline import Price


def case() -> None:
    nx.factor(window=2, inputs=[Price.close], adjustment="invariant")  # type: ignore[arg-type]
