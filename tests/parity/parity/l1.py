"""Spec 8.1's L1-a, L1-b and L1-d on zipline's side: the pipeline over a market's bundles, each row
moved to the engine's session (zipline's output for D is the engine's `prev_session(D)`).

Default inputs on both sides; the level factors (SMA, EWMA, VWAP, AverageDollarVolume) read
the engine's `Price.close`, so zipline reads them from the bundle without dividends (RV-I02).
"""

from __future__ import annotations

from typing import Any

import pandas as pd
from zipline.data import bundles
from zipline.pipeline import CustomFactor, Pipeline, SimplePipelineEngine
from zipline.pipeline.data import EquityPricing
from zipline.pipeline.domain import KR_EQUITIES, US_EQUITIES
from zipline.pipeline.factors import (
    RSI,
    VWAP,
    AnnualizedVolatility,
    AverageDollarVolume,
    ExponentialWeightedMovingAverage,
    Returns,
    SimpleMovingAverage,
)
from zipline.pipeline.loaders import EquityPricingLoader

from parity.bundle import BUNDLES, reader
from parity.user_factors import build

DOMAINS = {"KR": KR_EQUITIES, "US": US_EQUITIES}
THRESHOLDS = {"KR": 50_000.0, "US": 50.0}  # close > X, near each market's median price
WARMUP = 260  # sessions before the first row: the longest window is 253


def total_cases(market: str) -> dict[str, Any]:
    """The cases read from the bundle with dividends: zipline's default close."""
    pricing = EquityPricing.specialize(DOMAINS[market])
    return {"close_latest": pricing.close.latest,
            **{f"returns_{w}": Returns(window_length=w) for w in (2, 21, 252)},
            "annualized_volatility": AnnualizedVolatility(), "rsi": RSI(),
            **build(CustomFactor, pricing, THRESHOLDS[market]), **l1d_cases(pricing)}  # fmt: skip


def l1d_cases(pricing: Any) -> dict[str, Any]:
    """8.1's L1-d (ADR 0046) on a ratio within one bar, which no adjustment moves; the groups
    are the quintiles of another. The mask keeps NaN out of zipline's grouped rank."""
    x = pricing.close.latest / pricing.open.latest
    groups = (pricing.high.latest / pricing.low.latest).quantiles(5)
    return {"l1d_x": x, "l1d_range": pricing.high.latest / pricing.low.latest,
            "l1d_top": x.top(20, mask=x > 1.0),
            "l1d_rank": x.rank("ordinal", mask=x.notnan(), groupby=groups),
            "l1d_zscore": x.zscore(), "l1d_pct": x.percentile_between(10, 90),
            "l1d_quantiles": x.quantiles(5)}  # fmt: skip


def split_cases(market: str) -> dict[str, Any]:
    """The level cases, read from the bundle without dividends."""
    close = EquityPricing.specialize(DOMAINS[market]).close
    return {**{f"sma_{w}": SimpleMovingAverage(inputs=[close], window_length=w) for w in (20, 200)},
            "ewma": ExponentialWeightedMovingAverage(inputs=[close], window_length=30,
                                                     decay_rate=0.9),
            "average_dollar_volume": AverageDollarVolume(window_length=63),
            "vwap": VWAP(window_length=20)}  # fmt: skip


def run(name: str, cases: dict[str, Any], market: str) -> pd.DataFrame:
    """`cases` over the bundle `name`, from WARMUP sessions in, by engine session."""
    bundle, bars, data = BUNDLES[name], reader(name), bundles.load(name)
    loader = EquityPricingLoader.without_fx(bars, data.adjustment_reader)
    engine = SimplePipelineEngine(lambda column: loader, data.asset_finder, DOMAINS[market])
    days = bars.sessions
    out = engine.run_pipeline(Pipeline(cases, domain=DOMAINS[market]), days[WARMUP], days[-1])
    out.index.names = ["session_date", "asset"]
    out = out.reset_index()
    out["session_date"] = days[days.get_indexer(out["session_date"]) - 1]  # prev_session(D)
    ids = {sid: iid for iid, sid in bundle.sids.items()}
    out.insert(1, "instrument_id", [ids[a.sid] for a in out.pop("asset")])
    return out
