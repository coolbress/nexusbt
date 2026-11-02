"""`tds/conformance/build.py`, loaded by path: the tests build its packages into `tmp_path`."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_PATH = Path(__file__).parents[1] / "conformance" / "build.py"
_SPEC = importlib.util.spec_from_file_location("tds_conformance_build", _PATH)
if _SPEC is None or _SPEC.loader is None:
    raise ImportError(f"cannot load {_PATH}")
build = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(build)
