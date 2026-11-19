"""#567: a `markets` entry holds `calendar_id`, `currency` and `timezone` (TDS 3.8, 4.2); a
package without one is the checker's TDS-M003, so the open stops with E14 (4.4-1, 2), never a
`KeyError` or a market read as the text `"None"`."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from nexusbt.contracts import SnapshotError, VerifyPolicy
from nexusbt.data import DataConfig, open_snapshot
from nexusbt.testing.synth import make_snapshot


@pytest.mark.parametrize("verify", list(VerifyPolicy))
@pytest.mark.parametrize("field", ["calendar_id", "currency", "timezone"])
def test_a_market_without_a_field_stops_the_open_naming_m003(
    field: str, verify: VerifyPolicy, tmp_path: Path
) -> None:
    """When `markets.US.<field>` is deleted from a package without `calendar_sessions` (the
    issue's steps), then `open_snapshot` raises E14 naming TDS-M003, at every `verify` level."""
    path = make_snapshot(tmp_path / "s", preset="tiny", degrade=["no_sessions"])
    data = json.loads((path / "tds.json").read_text(encoding="utf-8"))
    del data["markets"]["US"][field]
    (path / "tds.json").write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(SnapshotError, match="TDS-M003") as raised:
        open_snapshot(DataConfig(path=path, verify=verify))
    assert "[E14]" in str(raised.value)
    assert f"markets.US: field {field!r} is missing" in str(raised.value)
