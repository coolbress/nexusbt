"""`python -m parity.run --suite all --fixture small` (spec 8.1, 9.1).

Writes the CI fixture, synthetic `small` with prices to 3 decimals (4.8 (5a)), through the
engine's own environment; ingests a zipline bundle per market; and leaves for
`tests/parity_compare` the bars zipline reads back (`readback-<market>.parquet`) and
`manifest.json`, under `.scratch/parity/<fixture>/`.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from collections.abc import Sequence
from importlib.metadata import version
from pathlib import Path

import pandas as pd

from parity.bundle import BUNDLES, CALENDARS, make_bundle, reader

ROOT = Path(__file__).resolve().parents[3]  # the repository


def tool(name: str, *args: str) -> str:
    """Run `name` from PATH with `args` in the repository, outside this environment; its
    output."""
    found = shutil.which(name)
    if found is None:
        raise SystemExit(f"{name} is not on PATH")
    env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
    done = subprocess.run([found, *args], cwd=ROOT, env=env, check=True,  # noqa: S603 - a tool from PATH, this repository's paths
                          capture_output=True, text=True)  # fmt: skip
    return done.stdout


def fixture(out: Path) -> Path:
    """`small` with `price_decimals=3` (4.8 (5a)), made by the engine's generator in the
    engine's environment: this one never imports nexusbt."""
    snapshot = out / "snapshot"
    tool("uv", "run", "--project", str(ROOT), "python", "-m", "nexusbt.testing.synth",
         "--preset", "small", "--price-decimals", "3", "--out", str(snapshot))  # fmt: skip
    return snapshot


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m parity.run")
    parser.add_argument("--suite", choices=["L1", "all"], default="all")
    parser.add_argument("--fixture", choices=["small"], default="small")
    parser.add_argument("--out", type=Path, default=ROOT / ".scratch" / "parity")
    args = parser.parse_args(argv)
    began, out = time.perf_counter(), args.out / args.fixture
    started = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
    snapshot = fixture(out)
    os.environ["ZIPLINE_ROOT"] = str(out / "zipline")
    markets = {}
    for market in CALENDARS:
        name = make_bundle(snapshot, market)
        bars = reader(name)
        sids = {sid: iid for iid, sid in BUNDLES[name].sids.items()}
        long = pd.concat({c: f.stack() for c, f in bars.frames.items()}, axis=1)
        long.index.names = ["session_date", "sid"]
        long = long.reset_index().dropna(subset=["close"])
        long.insert(0, "instrument_id", long.pop("sid").map(sids))
        long.to_parquet(out / f"readback-{market}.parquet", index=False)
        markets[market] = {"bundle": name, "scaled": BUNDLES[name].scales}
        print(f"{market}: {len(sids)} instruments, {len(BUNDLES[name].scales)} scaled")
    hashes = json.loads((snapshot / "tds.json").read_text(encoding="utf-8"))["hashes"]
    manifest = {
        "suite": args.suite, "fixture": args.fixture, "snapshot": str(snapshot), "started": started,
        "commit": tool("git", "rev-parse", "--short", "HEAD").strip(),
        "fixture_semantic_hash": hashes["semantic_sha256"],
        "zipline_version": version("zipline-reloaded"), "markets": markets,
        "environment": {"python": platform.python_version(), "platform": sys.platform,
                        "pandas": version("pandas"), "numpy": version("numpy")},
        "seconds": round(time.perf_counter() - began, 1),
    }  # fmt: skip
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"parity.run {args.suite} {args.fixture}: {manifest['seconds']} s, {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
