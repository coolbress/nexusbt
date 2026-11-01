"""The engine is built and checked on the Python of spec 2.1 (#72).

Spec 2.1 names Python 3.13 for the engine (`.python-version`). The five settings read here
have to say that version, so a change to one of them alone fails here instead of leaving
the checks on a version the spec does not name. Not read: `tests/parity/`, which keeps its
own 3.12 (spec 8.1), and `.github/workflows/ci.yml`, whose versions T0.10 (#50) tidies.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SPEC_PYTHON = "3.13"  # spec 2.1


def _toml(relative: str) -> dict[str, Any]:
    return tomllib.loads((ROOT / relative).read_text(encoding="utf-8"))


def test_every_setting_that_names_the_engine_python_says_the_spec_version() -> None:
    root = _toml("pyproject.toml")
    floor = f">={SPEC_PYTHON}"
    settings = [
        (
            ".python-version",
            (ROOT / ".python-version").read_text(encoding="utf-8").strip(),
            SPEC_PYTHON,
        ),
        ("pyproject.toml requires-python", root["project"]["requires-python"], floor),
        (
            "tds/pyproject.toml requires-python",
            _toml("tds/pyproject.toml")["project"]["requires-python"],
            floor,
        ),
        ("pyproject.toml mypy python_version", root["tool"]["mypy"]["python_version"], SPEC_PYTHON),
        ("uv.lock requires-python", _toml("uv.lock")["requires-python"], floor),
    ]
    wrong = [(name, found, wanted) for name, found, wanted in settings if found != wanted]
    assert wrong == []
