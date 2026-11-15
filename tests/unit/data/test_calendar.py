"""A market's calendar (spec 5.1.1) and the freeze time of its rows (5.1.2), T1.3 (#235)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from nexusbt.contracts import CapabilityError, SnapshotError
from nexusbt.data import DataConfig, open_snapshot
from nexusbt.testing.synth import make_snapshot

pytestmark = pytest.mark.unit

MINUTE = np.timedelta64(1, "m")


def bars_declared(source: Path, at: Path, **fields: Any) -> Path:
    """A copy of `source` whose bars entry in tds.json takes `fields` (availability, params)."""
    shutil.copytree(source, at)
    data = json.loads((at / "tds.json").read_text(encoding="utf-8"))
    bars = next(d for d in data["datasets"] if d["kind"] == "bars")
    bars.update(fields | {"params": bars["params"] | fields.get("params", {})})
    (at / "tds.json").write_text(json.dumps(data), encoding="utf-8")
    return at


def delay(path: Path) -> np.timedelta64:
    calendar = open_snapshot(DataConfig(path=path)).calendar("KR")
    assert (calendar.ready == calendar.ts_close + calendar.ready_delay).all()
    return calendar.ready_delay


def test_ready_delay_from_availability_rule(tmp_path: Path) -> None:
    """5.1.2: delta is 0 under `ts_end`, the duration under `ts_end+<duration>`, and
    `params.ready_delay` (0 when absent) under the column rule."""
    tiny = make_snapshot(tmp_path / "tiny", preset="tiny")
    kr = open_snapshot(DataConfig(path=tiny)).calendar("KR")
    assert (kr.calendar_id, len(kr.dates), kr.ready_delay) == ("XKRX", 62, 0 * MINUTE)
    assert (kr.dates[0], kr.ts_open[0], kr.ready[0]) == (
        np.datetime64("2020-01-02"), np.datetime64("2020-01-02T00:00"),
        np.datetime64("2020-01-02T06:30"),
    )  # fmt: skip
    assert kr.session_ord.tolist() == list(range(62))  # the package's own numbers (3.7)
    us = open_snapshot(DataConfig(path=tiny)).calendar("US")
    assert (us.calendar_id, us.ready[0]) == ("XNYS", np.datetime64("2020-01-02T21:00"))
    assert delay(bars_declared(tiny, tmp_path / "a", availability="ts_end+PT5M")) == 5 * MINUTE
    ruled = bars_declared(tiny, tmp_path / "b", availability={"rule": "ts_end+P1DT1H0.5S"})
    assert delay(ruled) == np.timedelta64(25 * 3600 * 10**6 + 500_000, "us")
    late = make_snapshot(tmp_path / "late", preset="tiny", degrade=["late_bars"])
    assert delay(late) == 0 * MINUTE  # the column rule with no `ready_delay`
    assert delay(bars_declared(late, tmp_path / "c", params={"ready_delay": "PT5M"})) == 5 * MINUTE
    # under a rule the rule decides, not a stray `ready_delay`
    assert delay(bars_declared(tiny, tmp_path / "d", params={"ready_delay": "PT5M"})) == 0 * MINUTE
    with pytest.raises(CapabilityError, match="market JP is not in the snapshot"):
        open_snapshot(DataConfig(path=tiny)).calendar("JP")
    wrongs: list[dict[str, Any]] = [
        {"availability": "session_close"},  # none of 5.1.2's three
        {"availability": "ts_end+P1M"},  # a month has no fixed length
        {"availability": {"column": "ts_available"}, "params": {"ready_delay": "5 minutes"}},
    ]
    for n, wrong in enumerate(wrongs):
        with pytest.raises(SnapshotError, match="gives no delay"):
            delay(bars_declared(tiny, tmp_path / f"wrong{n}", **wrong))


def test_calendar_without_sessions_is_the_library_s(tmp_path: Path) -> None:
    """4.5 F-02: a package without `calendar_sessions` takes the sessions of exchange_calendars
    over its bars' period, numbered from 0 (3.7)."""
    bare = make_snapshot(tmp_path / "bare", preset="tiny", degrade=["no_sessions"])
    with pytest.warns(UserWarning, match="F-02"):
        kr = open_snapshot(DataConfig(path=bare)).calendar("KR")
    assert (len(kr.dates), kr.dates[0], kr.dates[-1]) == (
        62, np.datetime64("2020-01-02"), np.datetime64("2020-03-31"))  # fmt: skip
    assert np.datetime64("2020-01-24") not in kr.dates  # Seollal
    assert (kr.ts_close[1], kr.session_ord[-1]) == (np.datetime64("2020-01-03T06:30"), 61)
