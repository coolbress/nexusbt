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
from nexusbt_tds import check, import_csv
from nexusbt_tds.hash import write_hashes

#: TDS chapter 7's two CSVs, with the instrument in market ZZ, and a mapping declaring only US.
INSTRUMENTS = """instrument_id,asset_class,market,calendar_id,currency,listed_on
XNYS:AAPL,equity,ZZ,XNYS,USD,1980-12-12
"""
BARS = "instrument_id,session_date,close,volume\nXNYS:AAPL,2024-01-02,185.64,82488700\n"
MINIMAL = """profiles: [tds:minimal-daily@1.0]
market: {code: US, calendar_id: XNYS, currency: USD, timezone: America/New_York}
datasets:
  instruments:
    file: instruments.csv
  bars:
    file: bars.csv
    params: {freq: 1d, price_basis: total_adjusted}
"""


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


def undeclared_market_package(tmp_path: Path) -> Path:
    """The CSVs above imported, and the bars file moved out of its `market=` partition, so
    that the engine takes the bars' market from `instruments` (#564)."""
    for name, text in (("instruments.csv", INSTRUMENTS), ("bars.csv", BARS),
                       ("mapping.yaml", MINIMAL)):  # fmt: skip
        (tmp_path / name).write_text(text, encoding="utf-8")
    pkg = import_csv(tmp_path / "mapping.yaml", tmp_path / "pkg")
    data = json.loads((pkg / "tds.json").read_text(encoding="utf-8"))
    bars = next(d for d in data["datasets"] if d["kind"] == "bars")
    del bars["coverage"]  # its `by_market.US` would name the partition moved away (#566)
    (entry,) = bars["files"]
    moved = entry["path"].replace("market=US/", "")
    (pkg / moved).parent.mkdir(parents=True)
    (pkg / entry["path"]).rename(pkg / moved)
    entry["path"] = moved
    (pkg / "tds.json").write_text(json.dumps(data), encoding="utf-8")
    write_hashes(pkg)
    return pkg


@pytest.mark.parametrize("verify", list(VerifyPolicy))
def test_an_instrument_of_an_undeclared_market_stops_the_open_naming_m010(
    verify: VerifyPolicy, tmp_path: Path
) -> None:
    """When the bars have no `market=` partition and their instrument names a market `markets`
    does not declare, then the open stops with E14 naming TDS-M010, the market and the
    instrument, at every `verify` level: at `manifest` the checker reads no rows, so the engine
    finds it where it takes the market from `instruments` (spec 4.4-4)."""
    pkg = undeclared_market_package(tmp_path)
    assert check(pkg, level="manifest").error_count == 0
    with pytest.raises(SnapshotError, match="TDS-M010") as raised:
        open_snapshot(DataConfig(path=pkg, verify=verify))
    assert "[E14]" in str(raised.value)
    assert "'XNYS:AAPL'" in str(raised.value)
    assert "market 'ZZ'" in str(raised.value)
