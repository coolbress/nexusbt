"""Spec 8.1's L1 comparison, the engine side: it reads what `parity.run` left in
`.scratch/parity/small` and never imports zipline (2.5, R-64). Each case writes its row
into the evidence file and prints it, so the `engine / parity` log shows `max_rel`.
"""

from __future__ import annotations

import datetime as dt
import json
import platform
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow.dataset as ds
import pytest

pytestmark = pytest.mark.parity

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / ".scratch" / "parity" / "small"
RUN = "uv run --project tests/parity python -m parity.run --suite all --fixture small"
OHLC = ("open", "high", "low", "close")
UINT32_MAX, PRICE_UNITS = 2**32 - 1, 1000  # zipline stores a price x 1000 in a uint32
REL = ABS = 1e-9  # |a - b| <= 1e-9 + 1e-9 |b| (8.1 table)


@pytest.fixture(scope="module")
def manifest() -> dict[str, Any]:
    path = OUT / "manifest.json"
    if not path.exists():
        pytest.fail(f"{path} is missing: run `{RUN}` first (spec 8.1)")
    found: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return found


def evidence(manifest: dict[str, Any], case: dict[str, Any], capsys: pytest.CaptureFixture[str]
             ) -> None:  # fmt: skip
    """Put `case` into this run's evidence file (spec 8.1) and print it to the job log."""
    day = dt.datetime.now(dt.UTC).strftime("%Y%m%d")
    name = f"{day}-{manifest['commit']}-{manifest['suite']}-{manifest['fixture']}.json"
    path = ROOT / "tests" / "parity" / "evidence" / name
    scaled = sorted(i for m in manifest["markets"].values() for i in m["scaled"])
    found = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"cases": []}
    found |= {
        "suite": manifest["suite"], "zipline_version": manifest["zipline_version"],
        "fixture_semantic_hash": manifest["fixture_semantic_hash"],
        "note": "parity does not imply realism",
        "scaled_instruments": {"count": len(scaled), "ids": scaled},
        "cases": [c for c in found["cases"] if c["id"] != case["id"]] + [case],
        "environment": manifest["environment"] | {"engine_python": platform.python_version()},
    }  # fmt: skip
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(found, indent=2) + "\n", encoding="utf-8")
    with capsys.disabled():
        print(f"\n{case['id']} {case['metric']}: n={case['n']} max_abs={case['max_abs']:.3g}"
              f" max_rel={case['max_rel']:.3g} tolerance={case['tolerance']} pass={case['pass']}"
              f" → {path.relative_to(ROOT)}")  # fmt: skip


def compare(case_id: str, metric: str, ours: np.ndarray, theirs: np.ndarray) -> dict[str, Any]:
    """8.1's row for one case: zipline's values `theirs` against the engine's `ours`."""
    diff = np.abs(ours - theirs)
    rel = diff / np.maximum(np.abs(theirs), np.finfo(float).tiny)
    within = bool((diff <= ABS + REL * np.abs(theirs)).all())
    return {"id": case_id, "metric": metric, "n": int(ours.size),
            "max_abs": float(diff.max(initial=0.0)), "max_rel": float(rel.max(initial=0.0)),
            "tolerance": f"{ABS} + {REL}|b|", "pass": within}  # fmt: skip


def test_price_scale_for_uint32_overflow(
    manifest: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    """8.1, RV-Q08: an instrument whose price x 1000 passes a uint32 is kept with a price scale;
    zipline reads its raw bars back equal to the package's once the scale is undone."""
    scaled = manifest["markets"]["KR"]["scaled"]
    assert scaled, "small's KR prices reach about 19,600,000: some instrument must be scaled"
    keys = ["instrument_id", "session_date"]
    ours = ds.dataset(Path(manifest["snapshot"]) / "bars", format="parquet", partitioning="hive"
                      ).to_table(columns=[*keys, *OHLC]).to_pandas()  # fmt: skip
    ours = ours.assign(instrument_id=ours["instrument_id"].astype(str),
                       session_date=pd.to_datetime(ours["session_date"]))  # fmt: skip
    ours = ours[ours["instrument_id"].isin(list(scaled)) & ours["close"].notna()]  # priced bars
    theirs = pd.read_parquet(OUT / "readback-KR.parquet")
    theirs = theirs.assign(session_date=pd.to_datetime(theirs["session_date"]))
    joined = ours.merge(theirs[[*keys, *OHLC]], on=keys, suffixes=("", "_zipline"))
    assert len(joined) == len(ours), "every priced bar of a scaled instrument reads back"
    for iid, n in scaled.items():  # the scale is needed, and it is the least that fits
        high = float(ours.loc[ours["instrument_id"] == iid, "high"].max())
        assert high * PRICE_UNITS >= UINT32_MAX > high / 10**n * PRICE_UNITS, iid
        assert high / 10 ** (n - 1) * PRICE_UNITS >= UINT32_MAX, iid
    for name in OHLC:
        ours_, theirs_ = joined[name].to_numpy(float), joined[f"{name}_zipline"].to_numpy(float)
        case = compare(f"L3-scale-KR-{name}", f"raw {name}, scale undone", ours_, theirs_)
        evidence(manifest, case, capsys)
        assert case["pass"], case
