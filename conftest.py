"""The hypothesis `deep` profile of spec 9.1, registered before `--hypothesis-profile` is read.

At the repository root so that every test path (`tests/`, `tds/tests/`) loads it.
`ci`, the default run's, is the profile hypothesis ships (derandomized, no
deadline, no example database); `deep`, the `engine / property-deep` job's,
is that profile with 9.1's "e.g. 500 cases".

A helper the tests of several folders share is a fixture here; test files do not import each
other (`tests/unit` has no `__init__.py`).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pyarrow.parquet as pq
import pytest
from hypothesis import settings

from nexusbt_tds.hash import write_hashes

settings.register_profile("deep", parent=settings.get_profile("ci"), max_examples=500)


def _drop_bars_column(root: Path, column: str) -> None:
    data = json.loads((root / "tds.json").read_text(encoding="utf-8"))
    for f in next(d for d in data["datasets"] if d["kind"] == "bars")["files"]:
        pq.write_table(pq.read_table(part := root / f["path"]).drop_columns([column]), part)
        f["bytes"] = part.stat().st_size
    (root / "tds.json").write_text(json.dumps(data), encoding="utf-8")
    write_hashes(root)


@pytest.fixture
def package_without_bars_column() -> Callable[[Path, str], None]:
    """Drops one column from every bars file of a synthetic package, then writes its hashes
    again, in place.

    The generator's `degrade` values cannot write a package whose bars have `volume` and no
    `value_traded` (4.8), so this makes one from a package that has both. It takes only the
    path of a package `make_snapshot` wrote (2.7)."""
    return _drop_bars_column
