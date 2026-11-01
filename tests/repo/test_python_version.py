"""The engine is built and checked on the Python that spec 2.1 names (#72).

The expected version is read from spec 2.1's "Python: **X.Y**" line, not written here, so
the settings follow the spec. A change to one of the five settings alone fails here. Not
read: `.github/workflows/ci.yml`, whose versions T0.10 (#50) tidies.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "docs/spec/engine-spec-v3.4.md"


def _spec_python() -> str:
    text = SPEC.read_text(encoding="utf-8")
    section = text[text.index("### 2.1 ") : text.index("### 2.2 ")]
    found = re.findall(r"^- Python: \*\*(\d+\.\d+)\*\*", section, flags=re.MULTILINE)
    assert len(found) == 1, f"spec 2.1 should have one 'Python: **X.Y**' line, found {found}"
    return str(found[0])


def _toml(relative: str) -> dict[str, Any]:
    return tomllib.loads((ROOT / relative).read_text(encoding="utf-8"))


def test_every_setting_that_names_the_engine_python_says_the_spec_2_1_version() -> None:
    python = _spec_python()
    floor = f">={python}"
    root = _toml("pyproject.toml")
    # tests/parity/ is left out: spec 2.1 and 8.1 keep it on its own Python 3.12.
    settings = [
        (".python-version", (ROOT / ".python-version").read_text(encoding="utf-8").strip(), python),
        ("pyproject.toml requires-python", root["project"]["requires-python"], floor),
        (
            "tds/pyproject.toml requires-python",
            _toml("tds/pyproject.toml")["project"]["requires-python"],
            floor,
        ),
        ("pyproject.toml mypy python_version", root["tool"]["mypy"]["python_version"], python),
        ("uv.lock requires-python", _toml("uv.lock")["requires-python"], floor),
    ]
    wrong = [(name, found, wanted) for name, found, wanted in settings if found != wanted]
    assert wrong == []
