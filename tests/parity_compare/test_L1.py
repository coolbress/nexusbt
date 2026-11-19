"""Spec 8.1's L1 comparison, the engine side: it reads what `parity.run` left in
`.scratch/parity/small` and never imports zipline (2.5, R-64). Each case writes its row
into the evidence file and prints it, so the `engine / parity` log shows `max_rel`.
"""

from __future__ import annotations

import datetime as dt
import importlib.util
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
    """Put `case` into this run's evidence file (spec 8.1) and print it to the job log; the
    cases of an earlier `parity.run` in the same file are dropped."""
    day = dt.datetime.now(dt.UTC).strftime("%Y%m%d")
    name = f"{day}-{manifest['commit']}-{manifest['suite']}-{manifest['fixture']}.json"
    path = ROOT / "tests" / "parity" / "evidence" / name
    scaled = sorted(i for m in manifest["markets"].values() for i in m["scaled"])
    found = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    if found.get("run") != manifest["started"]:
        found = {"cases": []}
    found |= {
        "run": manifest["started"],
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
        print(f"\n{path.relative_to(ROOT)}: {found['note']}; {len(scaled)} scaled instruments")
        print(f"{case['id']} {case['metric']}: n={case['n']} max_abs={case['max_abs']:.3g}"
              f" max_rel={case['max_rel']:.3g} tolerance={case['tolerance']} pass={case['pass']}"
              f" → {path.relative_to(ROOT)}")  # fmt: skip


def compare(case_id: str, metric: str, ours: np.ndarray, theirs: np.ndarray) -> dict[str, Any]:
    """8.1's row for one case: zipline's values `theirs` against the engine's `ours`. NaN on
    both sides agrees; NaN on one side does not."""
    both = np.isfinite(ours) & np.isfinite(theirs)
    one = int((np.isnan(ours) != np.isnan(theirs)).sum())
    diff = np.abs(ours - theirs)[both]
    rel = diff / np.maximum(np.abs(theirs[both]), ABS)  # near 0, relative to the 1e-9 floor
    within = one == 0 and bool((diff <= ABS + REL * np.abs(theirs[both])).all())
    return {"id": case_id, "metric": metric, "n": int(ours.size), "nan_on_one_side": one,
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
    highs = ours[ours["instrument_id"].str.startswith("KR:")].groupby("instrument_id")["high"].max()
    for iid, high in highs.items():  # every KR instrument fits, scaled by the least n needed
        n = scaled.get(iid, 0)
        assert high / 10**n * PRICE_UNITS < UINT32_MAX, iid
        assert n == 0 or high / 10 ** (n - 1) * PRICE_UNITS >= UINT32_MAX, iid
    ours = ours[ours["instrument_id"].isin(list(scaled)) & ours["close"].notna()]  # priced bars
    theirs = pd.read_parquet(OUT / "readback-KR.parquet")
    theirs = theirs.assign(session_date=pd.to_datetime(theirs["session_date"]))
    joined = ours.merge(theirs[[*keys, *OHLC]], on=keys, suffixes=("", "_zipline"))
    assert len(joined) == len(ours), "every priced bar of a scaled instrument reads back"
    for name in OHLC:
        ours_, theirs_ = joined[name].to_numpy(float), joined[f"{name}_zipline"].to_numpy(float)
        case = compare(f"L3-scale-KR-{name}", f"raw {name}, scale undone", ours_, theirs_)
        evidence(manifest, case, capsys)
        assert case["pass"], case


KEYS = ["session_date", "instrument_id"]
THRESHOLDS = {"KR": 50_000.0, "US": 50.0}  # parity.l1's `close > X`
#: case id → (rows its value reads, the bundle zipline reads it from, how the eve compares)
CASES: dict[str, tuple[int, str, str]] = {
    "close_latest": (1, "total", "level"), "returns_2": (2, "total", "ratio"),
    "returns_21": (21, "total", "ratio"), "returns_252": (252, "total", "ratio"),
    "annualized_volatility": (253, "total", "ratio"), "rsi": (15, "total", "ratio"),
    "momentum_12_1": (253, "total", "ratio"), "sma_ratio": (200, "total", "ratio"),
    "close_above": (1, "total", "filter"), "sma_20": (20, "split", "level"),
    "sma_200": (200, "split", "level"), "ewma": (30, "split", "level"),
    "average_dollar_volume": (63, "split", "ratio"), "vwap": (20, "split", "level"),
    **{f"lag_{k}": (11, "total", "level") for k in range(11)},
}  # fmt: skip
#: Fixed by the first run on `small` (ADR 0045): (cells compared, of them through m, left out)
EXPECTED: dict[str, dict[str, tuple[int, int, int]]] = {
    "close_latest": {"KR": (58117, 280, 142), "US": (98621, 492, 1)},
    "returns_2": {"KR": (57975, 0, 284), "US": (98620, 0, 2)},
    "returns_21": {"KR": (55339, 0, 2920), "US": (98608, 0, 14)},
    "rsi": {"KR": (56150, 0, 2109), "US": (98608, 0, 14)},
    **{c: {"KR": (53968, 0, 4291), "US": (98608, 0, 14)}
       for c in ("returns_252", "annualized_volatility", "momentum_12_1", "sma_ratio")},
    "close_above": {"KR": (58065, 280, 194), "US": (98621, 492, 1)},
    **{c: {"KR": (58259, 280, 0), "US": (98622, 492, 0)}
       for c in ("sma_20", "sma_200", "ewma", "vwap")},
    "average_dollar_volume": {"KR": (58259, 0, 0), "US": (98622, 0, 0)},
    **{f"lag_{k}": {"KR": (56710, 280, 1549), "US": (98611, 492, 11)} for k in range(11)},
}  # fmt: skip
ENGINE_ONLY = {"KR": 87, "US": 126}  # engine rows on and after a last session: no zipline D
#: L1-b's rows compared around a cash or a share event's ex-date, after (B) (ADR 0045)
COVERAGE = {"KR": {"cash": 1762, "share": 36}, "US": {"cash": 5837, "share": 24}}


def engine_terms(market: str) -> dict[str, Any]:
    """The engine's terms of parity.l1's cases, default inputs; the user factors from the
    same source file as zipline's, through `nexusbt.compat.zipline`."""
    from nexusbt.compat.zipline import CustomFactor, USEquityPricing
    from nexusbt.factors import (
        EWMA,
        RSI,
        SMA,
        VWAP,
        AnnualizedVolatility,
        AverageDollarVolume,
        Returns,
    )

    path = ROOT / "tests" / "parity" / "parity" / "user_factors.py"
    spec = importlib.util.spec_from_file_location("parity_user_factors", path)
    assert spec is not None
    assert spec.loader is not None
    users = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(users)
    return {"close_latest": USEquityPricing.close.latest,
            **{f"returns_{w}": Returns(w) for w in (2, 21, 252)},
            "annualized_volatility": AnnualizedVolatility(), "rsi": RSI(),
            **users.build(CustomFactor, USEquityPricing, THRESHOLDS[market]),
            **{f"sma_{w}": SMA(w) for w in (20, 200)}, "ewma": EWMA(30, 0.9),
            "average_dollar_volume": AverageDollarVolume(63), "vwap": VWAP(20)}  # fmt: skip


def actions(snapshot: Path, market: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """`market`'s corporate actions: each version's ex-date with the time its chain's final
    version is known (ADR 0045 (B)), and the final effective events' price factors by
    (instrument, ex-date), total and split (A)."""
    ca = ds.dataset(snapshot / "corporate_actions").to_table().to_pandas()
    ca = ca[ca["instrument_id"].str.startswith(f"{market}:")]
    ca = ca.assign(root=ca["revision_of"].fillna(ca["event_id"]),
                   ex_date=pd.to_datetime(ca["ex_date"]))  # fmt: skip
    final = ca.sort_values("ts_announced").groupby("root").tail(1).set_index("root")
    known = final["ts_announced"].combine(final["ts_terms_available"], lambda a, b: max(a, b)
                                          if pd.notna(b) else a)  # fmt: skip
    pending = ca[["instrument_id", "ex_date", "affects"]].assign(known=ca["root"].map(known))
    live = final[(final["status"] == "effective") & final["price_factor"].notna()]
    split = live["price_factor"].where(live["affects"] == "split_and_total", 1.0)
    m = live.assign(m_total=live["price_factor"], m_split=split).groupby(
        ["instrument_id", "ex_date"])[["m_total", "m_split"]].prod()  # fmt: skip
    return pending, m.reset_index()


@pytest.fixture(scope="module")
def l1(manifest: dict[str, Any]) -> dict[str, pd.DataFrame]:
    """Each market's engine rows beside zipline's (`_merge` says which side has the row),
    with the eve factors `m_total` and `m_split` and each row's session position."""
    import nexusbt as nx

    found = {}
    for market in THRESHOLDS:
        theirs = pd.read_parquet(OUT / f"L1-{market}.parquet")
        start, end = theirs["session_date"].min(), theirs["session_date"].max()
        table = nx.run_pipeline(nx.Pipeline(engine_terms(market)), start=str(start.date()),
                                end=str(end.date()), markets=[market],
                                snapshot=manifest["snapshot"]).table.to_pandas()  # fmt: skip
        ours = table.assign(session_date=pd.to_datetime(table["session_date"]),
                            instrument_id=table["instrument_id"].astype(str))  # fmt: skip
        days = pd.DatetimeIndex(sorted(sessions(Path(manifest["snapshot"]), market)))
        pos = days.get_indexer(ours["session_date"])
        ours = ours.assign(pos=pos, next=days[np.minimum(pos + 1, len(days) - 1)])
        _, m = actions(Path(manifest["snapshot"]), market)
        ours = ours.merge(m.rename(columns={"ex_date": "next"}), on=["instrument_id", "next"],
                          how="left")  # fmt: skip
        found[market] = ours.merge(theirs, on=KEYS, how="left", suffixes=("", "_zipline"),
                                   indicator=True)  # fmt: skip
    return found


def sessions(snapshot: Path, market: str) -> set[pd.Timestamp]:
    bars = ds.dataset(snapshot / "bars", partitioning="hive").to_table(
        columns=["instrument_id", "session_date"]).to_pandas()  # fmt: skip
    mine = bars[bars["instrument_id"].astype(str).str.startswith(f"{market}:")]
    return set(pd.to_datetime(mine["session_date"]))


def left_out(frame: pd.DataFrame, snapshot: Path, market: str, window: int, basis: str
             ) -> np.ndarray:  # fmt: skip
    """ADR 0045 (B): rows whose `window` rows hold the ex-date of an event whose final
    version is not known at the row's decision; for the split basis, share events only."""
    pending, _ = actions(snapshot, market)
    if basis == "split":
        pending = pending[pending["affects"] == "split_and_total"]
    days = pd.DatetimeIndex(sorted(sessions(snapshot, market)))
    hit = reach(frame, pending.assign(first=days.get_indexer(pending["ex_date"])), window)
    return np.asarray(frame.index.isin(hit.loc[hit["decision_ts"] < hit["known"], "index"]))


def reach(frame: pd.DataFrame, events: pd.DataFrame, rows: int) -> pd.DataFrame:
    """The rows of `frame` (its index as `index`) at positions `first` to `first + rows - 1`
    of each event's instrument, beside the event."""
    spread = events.reset_index(drop=True)
    spread = spread.loc[spread.index.repeat(rows)].assign(
        pos=lambda f: f["first"] + f.groupby(level=0).cumcount())  # fmt: skip
    return frame[["instrument_id", "pos", "decision_ts"]].reset_index().merge(
        spread, on=["instrument_id", "pos"])  # fmt: skip


def coverage(frame: pd.DataFrame, snapshot: Path, market: str) -> dict[str, int]:
    """L1-b's compared rows whose 11 lags, or whose eve, reach a final effective event's
    ex-date, by kind: what is left of L1-b once (B) is left out."""
    both = frame[frame["_merge"] == "both"].reset_index(drop=True)
    kept = both[~left_out(both, snapshot, market, 11, "total")]
    _, m = actions(snapshot, market)
    days = pd.DatetimeIndex(sorted(sessions(snapshot, market)))
    events = m.assign(first=days.get_indexer(m["ex_date"]) - 1,
                      kind=np.where(m["m_split"] != 1.0, "share", "cash"))  # fmt: skip
    hit = reach(kept, events, 12)
    return {k: int(hit.loc[hit["kind"] == k, "index"].nunique()) for k in ("cash", "share")}


def check(frame: pd.DataFrame, snapshot: Path, market: str, case: str) -> dict[str, Any]:
    """One case: (A) the eve through m, (B) and (C) left out (ADR 0045, spec 8.1)."""
    window, basis, kind = CASES[case]
    both = frame[frame["_merge"] == "both"].reset_index(drop=True)
    m = both[f"m_{basis}"].fillna(1.0).to_numpy()
    ours = both[case].astype(float).to_numpy()
    if kind == "level":
        ours = ours * m
    elif kind == "filter":
        ours = np.where(both[case].isna(), np.nan, both["close_latest"] * m > THRESHOLDS[market])
    out = left_out(both, snapshot, market, window, basis) | (kind == "filter") & both[case].isna()
    keep = ~out
    found = compare(f"L1-{market}-{case}", f"{kind}, {basis}", ours[keep],
                    both[f"{case}_zipline"].astype(float).to_numpy()[keep])  # fmt: skip
    via_m = int((both[f"m_{basis}"].notna() & keep & (kind != "ratio")).sum())
    return found | {"via_m": via_m, "left_out": int(out.sum())}


def run_cases(cases: list[str], l1: dict[str, pd.DataFrame], manifest: dict[str, Any],
              capsys: pytest.CaptureFixture[str]) -> None:  # fmt: skip
    snapshot, failed = Path(manifest["snapshot"]), []
    for market, frame in l1.items():
        assert int((frame["_merge"] == "left_only").sum()) == ENGINE_ONLY[market], market
        for case in cases:
            found = check(frame, snapshot, market, case)
            evidence(manifest, found, capsys)
            counts = (found["n"], found["via_m"], found["left_out"])
            if not found["pass"] or EXPECTED.get(case, {}).get(market) != counts:
                failed.append((market, case, counts, found["pass"]))
    assert not failed, failed


def test_L1a_price_terms_default_inputs(  # noqa: N802 - spec 8.1's name
    l1: dict[str, pd.DataFrame], manifest: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    """8.1 L1-a: built-in and user price terms, default inputs on both sides."""
    run_cases([c for c in CASES if not c.startswith("lag_")], l1, manifest, capsys)


def test_L1b_adjustment_windows(  # noqa: N802 - spec 8.1's name
    l1: dict[str, pd.DataFrame], manifest: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    """8.1 L1-b: the adjusted close 0 to 10 sessions back, `USEquityPricing.close` against
    `Price.close_tr`, across splits, reverse splits and dividends."""
    run_cases([c for c in CASES if c.startswith("lag_")], l1, manifest, capsys)
    found = {market: coverage(frame, Path(manifest["snapshot"]), market)
             for market, frame in l1.items()}  # fmt: skip
    with capsys.disabled():
        print(f"\nL1-b rows compared around an ex-date, after (B): {found}")
    assert found == COVERAGE
