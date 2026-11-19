"""Where an E30 fallback warning points (4.4 step 3, 4.5): at the code that called
`open_snapshot`, whichever step of the capability decision took the fallback (#558)."""

from __future__ import annotations

import inspect
import warnings
from pathlib import Path

import pytest

from nexusbt.data import DataConfig, open_snapshot
from nexusbt.data._capabilities import CapabilityRequest
from nexusbt.testing.synth import make_snapshot


@pytest.mark.parametrize(
    ("fallback", "degrade"),
    [("F-02", "no_sessions"), ("F-03", "sparse_bars"), ("F-01", "no_ohlc")],
)
def test_e30_points_at_open_snapshots_caller(tmp_path: Path, fallback: str, degrade: str) -> None:
    path = make_snapshot(tmp_path / "snap", preset="tiny", degrade=[degrade])
    with warnings.catch_warnings(record=True) as got:
        warnings.simplefilter("always")
        line = _line() + 1
        open_snapshot(DataConfig(path=path), required=CapabilityRequest(frozenset({"backtest"})))
    said = [w for w in got if f"[E30] {fallback}" in str(w.message)]
    assert said, f"no E30 warning for {fallback}"
    assert [(Path(w.filename).name, w.lineno) for w in said] == [(Path(__file__).name, line)]


def _line() -> int:
    """The line this is called from."""
    frame = inspect.currentframe()
    assert frame is not None
    assert frame.f_back is not None
    return frame.f_back.f_lineno
