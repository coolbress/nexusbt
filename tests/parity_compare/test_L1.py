"""Spec 8.1's L1 comparison, the engine side: it reads what `parity.run` left in
`.scratch/parity/small` and never imports zipline (2.5, R-64). Each case writes its row
into the evidence file and prints it, so the `engine / parity` log shows `max_rel`.
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import json
import platform
import sys
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
    both sides, or the same infinity, agrees; any other non-finite cell does not. `n` counts
    the cells, `n_values` the finite pairs held to the tolerance."""
    both = np.isfinite(ours) & np.isfinite(theirs)
    same = (ours == theirs) | (np.isnan(ours) & np.isnan(theirs))
    one = int((~both & ~same).sum())
    diff = np.abs(ours - theirs)[both]
    rel = diff / np.maximum(np.abs(theirs[both]), ABS)  # near 0, relative to the 1e-9 floor
    within = one == 0 and bool((diff <= ABS + REL * np.abs(theirs[both])).all())
    return {"id": case_id, "metric": metric, "n": int(ours.size), "n_values": int(both.sum()),
            "nonfinite_disagreeing": one,
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
    **{f"lag_{k}": (k + 1, "total", "level") for k in range(11)},  # rows t-k to t
}  # fmt: skip
#: Fixed by the first run on `small` (ADR 0045): (cells compared, of them through m, left out)
EXPECTED: dict[str, dict[str, tuple[int, int, int]]] = {
    "returns_2": {"KR": (58117, 0, 142), "US": (98621, 0, 1)},
    "returns_21": {"KR": (55469, 0, 2790), "US": (98608, 0, 14)},
    "rsi": {"KR": (56290, 0, 1969), "US": (98608, 0, 14)},
    **{c: {"KR": (53968, 0, 4291), "US": (98608, 0, 14)}
       for c in ("returns_252", "annualized_volatility", "momentum_12_1", "sma_ratio")},
    "close_above": {"KR": (58207, 280, 52), "US": (98622, 492, 0)},
    **{c: {"KR": (58259, 280, 0), "US": (98622, 492, 0)}
       for c in ("close_latest", "sma_20", "sma_200", "ewma", "vwap")},
    "average_dollar_volume": {"KR": (58259, 0, 0), "US": (98622, 0, 0)},
    **{f"lag_{k}": {"KR": (58259 - kr, 280, kr), "US": (98622 - k, 492, k)} for k, kr in
       enumerate((0, 142, 284, 426, 568, 709, 850, 990, 1130, 1270, 1410))},
}  # fmt: skip
ENGINE_ONLY = {"KR": 87, "US": 126}  # engine rows on and after a last session: no zipline D
#: L1-b's rows compared around a cash or a share event's ex-date, after (B) (ADR 0045)
COVERAGE = {"KR": {"cash": 1900, "share": 36}, "US": {"cash": 5838, "share": 24}}


def engine_terms(market: str) -> dict[str, Any]:
    """The engine's terms of parity.l1's cases, default inputs; the user factors from the
    same source file as zipline's, through `nexusbt.compat.zipline`. zipline's built-in windows
    give a value from one observation: the engine's `min_periods=1` (3.4, #868)."""
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
    sys.modules[spec.name] = users  # as `import` does: a class read by name is found (#690)
    spec.loader.exec_module(users)
    return {"close_latest": USEquityPricing.close.latest,
            **{f"returns_{w}": Returns(w) for w in (2, 21, 252)},
            "annualized_volatility": AnnualizedVolatility(min_periods=1),
            "rsi": RSI(min_periods=1),
            **users.build(CustomFactor, USEquityPricing, THRESHOLDS[market]),
            **{f"sma_{w}": SMA(w, min_periods=1) for w in (20, 200)}, "ewma": EWMA(30, 0.9),
            "average_dollar_volume": AverageDollarVolume(63),
            "vwap": VWAP(20, min_periods=1)}  # fmt: skip


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
    """ADR 0045 (B): rows whose `window` rows hold, after their first, the ex-date of an event
    whose final version is not known at the row's decision (on the first row it adjusts no
    row the value reads); for the split basis, share events only."""
    pending, _ = actions(snapshot, market)
    if basis == "split":
        pending = pending[pending["affects"] == "split_and_total"]
    days = pd.DatetimeIndex(sorted(sessions(snapshot, market)))
    hit = reach(frame, pending.assign(first=days.get_indexer(pending["ex_date"])), window - 1)
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
    kept = both[~left_out(both, snapshot, market, 11, "total")]  # lag_10's rows
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
    elif kind == "filter":  # the engine's own Filter; on the eve, its close x m > X (A)
        eve = (both["close_latest"] * m > THRESHOLDS[market]).to_numpy(float)
        ours = np.where(both[f"m_{basis}"].notna(), eve, ours)
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


#: L1-d (ADR 0046): x = close / open within one bar, its groups the quintiles of high / low
#: NEAR: two x apart by at most this, relative, may swap order (the sides differ by ~4e-16)
L1D_TOP, L1D_Q, L1D_PCT, NEAR = 20, 5, (10.0, 90.0), 1e-14
L1D_CASES = ("top", "rank", "zscore", "pct", "quantiles")
#: Fixed by the first run on `small` (ADR 0046): (cells compared, left out)
L1D_EXPECTED: dict[str, dict[str, tuple[int, int]]] = {
    "top": {"KR": (58237, 22), "US": (98612, 10)},
    "rank": {"KR": (42448, 15811), "US": (73683, 24939)},
    "zscore": {"KR": (55877, 2382), "US": (92814, 5808)},
    "pct": {"KR": (58240, 19), "US": (98604, 18)},
    "quantiles": {"KR": (56294, 1965), "US": (96681, 1941)},
}


@pytest.fixture(scope="module")
def l1d(manifest: dict[str, Any], tmp_path_factory: pytest.TempPathFactory
        ) -> dict[str, pd.DataFrame]:  # fmt: skip
    """Each market's engine L1-d rows, with `tiebreak = "id"` (8.1), beside zipline's."""
    import nexusbt as nx
    from nexusbt import Price

    x, high_low = Price.close.latest / Price.open.latest, Price.high.latest / Price.low.latest
    terms = {"x": x, "range": high_low, "top": x.top(L1D_TOP, mask=x > 1.0),
             "rank": x.rank("ordinal", mask=x.notnan(), groupby=high_low.quantiles(L1D_Q)),
             "zscore": x.zscore(), "pct": x.percentile_between(*L1D_PCT),
             "quantiles": x.quantiles(L1D_Q)}  # fmt: skip
    folder = tmp_path_factory.mktemp("l1d")
    (folder / "nexusbt.toml").write_text('[portfolio]\ntiebreak = "id"\n', encoding="utf-8")
    found = {}
    with pytest.MonkeyPatch.context() as patch:
        patch.chdir(folder)
        for market in THRESHOLDS:
            theirs = pd.read_parquet(OUT / f"L1-{market}.parquet")
            theirs = theirs[[*KEYS, *(f"l1d_{c}" for c in terms)]]
            days = theirs["session_date"]
            table = nx.run_pipeline(nx.Pipeline(terms), start=str(days.min().date()),
                                    end=str(days.max().date()), markets=[market],
                                    snapshot=manifest["snapshot"]).table.to_pandas()  # fmt: skip
            ours = table.assign(session_date=pd.to_datetime(table["session_date"]),
                                instrument_id=table["instrument_id"].astype(str))  # fmt: skip
            both = ours.merge(theirs, on=KEYS, how="left", indicator=True)
            found[market] = both.sort_values(KEYS, ignore_index=True)  # groupby's order
    return found


def mean_rank(v: np.ndarray) -> np.ndarray:
    return np.asarray(pd.Series(v).rank(method="average"), dtype=float)


def bucket(v: np.ndarray, inside: np.ndarray, rule: str) -> np.ndarray:
    """Each cell's quintile among the finite `inside` cells, -1 elsewhere: 5.4.3's mean-rank
    `ceil(r q / n)` (in integers, as 2r) or zipline's `qcut` edges, both 1..q."""
    out, ok = np.full(len(v), -1), np.isfinite(v) & inside
    if rule == "5.4.3":
        twice_r = (2 * mean_rank(v[ok])).astype(int)
        out[ok] = np.clip(-(-twice_r * L1D_Q // (2 * ok.sum())), 1, L1D_Q)
    else:
        out[ok] = pd.qcut(v[ok], L1D_Q, labels=False) + 1
    return out


def between(v: np.ndarray, inside: np.ndarray, rule: str) -> np.ndarray:
    """`percentile_between(10, 90)` among the finite `inside` cells: 5.4.2's mean-rank
    percentile or zipline's values between numpy's linear percentiles."""
    out, ok = np.zeros(len(v), bool), np.isfinite(v) & inside
    lo, hi = L1D_PCT
    if rule == "5.4.2":
        n = ok.sum()
        p = 100 * (mean_rank(v[ok]) - 1) / (n - 1) if n > 1 else np.full(n, 100.0)
        out[ok] = (lo <= p) & (p <= hi)
    else:
        out[ok] = (np.percentile(v[ok], lo) <= v[ok]) & (v[ok] <= np.percentile(v[ok], hi))
    return out


def top(v: np.ndarray, ids: np.ndarray, inside: np.ndarray) -> np.ndarray:
    """The first 20 of the `inside` cells with x > 1 by x descending, then `instrument_id`."""
    ok = np.flatnonzero(np.isfinite(v) & (v > 1.0) & inside)
    out = np.zeros(len(v), bool)
    out[ok[np.lexsort((ids[ok], -v[ok]))[:L1D_TOP]]] = True
    return out


def l1d_left_out(f: pd.DataFrame) -> dict[str, np.ndarray]:
    """ADR 0046: one session's cells left out of each case, from the input values alone (x,
    high / low, the ids and which rows zipline has), never from either engine's output."""
    shared = (f["_merge"] == "both").to_numpy()
    every = np.ones(len(f), bool)
    ids, x = f["instrument_id"].to_numpy(str), f["x"].to_numpy(float)
    hl = f["range"].to_numpy(float)
    xs = np.sort(x[np.isfinite(x)])
    gap = np.diff(xs)
    close = (gap > 0) & (gap <= NEAR * np.abs(xs[1:]))
    near = np.isin(x, np.r_[xs[:-1][close], xs[1:][close]])
    groups = bucket(hl, every, "5.4.3"), bucket(hl, shared, "qcut")
    out = {"quantiles": bucket(x, every, "5.4.3") != bucket(x, shared, "qcut"),
           "pct": between(x, every, "5.4.2") != between(x, shared, "value"),
           "top": top(x, ids, every) != top(x, ids, shared),
           "rank": rank(x, ids, groups[0], every) != rank(x, ids, groups[1], shared)}  # fmt: skip
    out = {case: (left | near) & shared for case, left in out.items()}  # near: order can flip
    moving = (~shared & np.isfinite(x)).any()  # a finite cell zipline lacks moves the mean
    return out | {"zscore": np.full(len(f), moving) & shared}


def rank(v: np.ndarray, ids: np.ndarray, groups: np.ndarray, inside: np.ndarray) -> np.ndarray:
    """Each cell's ordinal rank within its group among the finite `inside` cells, by x then
    `instrument_id` (3.7's `"id"`), 0 elsewhere."""
    ok = np.flatnonzero(np.isfinite(v) & inside & (groups >= 1))
    order = ok[np.lexsort((ids[ok], v[ok], groups[ok]))]
    out = np.zeros(len(v))
    out[order] = pd.Series(groups[order]).groupby(groups[order]).cumcount().to_numpy() + 1
    return out


def test_L1d_top_rank_zscore_percentile_quantiles(  # noqa: N802 - spec 8.1's name
    l1d: dict[str, pd.DataFrame], manifest: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    """8.1 L1-d: sets and ranks exact, `zscore` within L1-a's tolerance (ADR 0046), the cells
    where zipline's rules answer differently left out and counted."""
    failed = []
    for market, frame in l1d.items():
        shared = frame[frame["_merge"] == "both"]
        for column in ("x", "range"):  # the rules read the engine's input as zipline's
            same = compare(column, "input", shared[column].to_numpy(float),
                           shared[f"l1d_{column}"].to_numpy(float))  # fmt: skip
            assert same["pass"], (market, same)
        days = [(f, l1d_left_out(f)) for _, f in frame.groupby("session_date")]
        for case in L1D_CASES:
            keep = np.concatenate([(f["_merge"] == "both").to_numpy() & ~o[case] for f, o in days])
            out = int(sum(o[case].sum() for _, o in days))
            ours, theirs = frame[case].to_numpy(float), frame[f"l1d_{case}"].to_numpy(float)
            if case in ("top", "pct"):  # the set of true cells: the engine's unknown is not true
                ours, theirs = (ours == 1).astype(float), (theirs == 1).astype(float)
            if case == "quantiles":
                theirs = np.where(theirs >= 0, theirs + 1, -1)
            found = compare(f"L1-{market}-l1d_{case}", "exact" if case != "zscore" else "value",
                            ours[keep], theirs[keep])  # fmt: skip
            if case != "zscore":
                found["pass"] = found["nonfinite_disagreeing"] == 0 and found["max_abs"] == 0
                found["tolerance"] = "exact"
            found["left_out"] = out
            evidence(manifest, found, capsys)
            if not found["pass"] or L1D_EXPECTED.get(case, {}).get(market) != (found["n"], out):
                failed.append((market, case, found["n"], out, found["pass"]))
    assert not failed, failed


def test_L1d_known_differences_listed() -> None:  # noqa: N802 - spec 8.1's name
    """8.1, T1.18: `KNOWN_DIFFERENCES.md` lists V31-21's Filter `~` on a missing value, the
    tie-break of `top` and `rank("ordinal")` (V31-29), and what L1-d found (ADR 0046)."""
    listed = (ROOT / "tests" / "parity" / "KNOWN_DIFFERENCES.md").read_text(encoding="utf-8")
    for item in ("missing values under Filter\n  `~`",
                 'tie-breaking of `top` and `rank("ordinal")`', "`MaxDrawdown`", "`VWAP`",
                 "## Found by L1-d (ADR 0046", "`quantiles`",
                 "`percentile_between`", "`zscore`", "`rank(groupby=)`"):  # fmt: skip
        assert item in listed, item
