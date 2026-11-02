"""Spec 8.4b `cases/<code>-<condition>.py`: the smallest code that raises that error, run in
an empty working folder. Only the codes engine code raises today (#52 Decisions, 2026-11-02)."""

from __future__ import annotations

import contextlib
import runpy
import tempfile
from pathlib import Path

from nexusbt.contracts import NexusBTError

FILES = sorted(Path(__file__).parent.glob("E*-*.py"))


def run(file: Path) -> NexusBTError:
    """The error `file`'s `case()` raises in the current folder."""
    try:
        runpy.run_path(str(file))["case"]()
    except NexusBTError as error:
        return error
    raise AssertionError(f"{file.name} raised no 6.6 error")


def raised() -> list[NexusBTError]:
    errors = []
    for file in FILES:
        with tempfile.TemporaryDirectory() as folder, contextlib.chdir(folder):
            errors.append(run(file))
    return errors
