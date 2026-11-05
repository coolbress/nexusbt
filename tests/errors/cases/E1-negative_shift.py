"""E1, your code: `shift(k < 0)` reads the future (6.5 check 1)."""

# ruff: noqa: N999 - spec 8.4b names the file `<code>-<condition>.py`; it is run, not imported

from nexusbt.factors import Returns


def case() -> None:
    Returns(21).shift(-1)
