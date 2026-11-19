"""TDS package → zipline bundle: `make_bundle`, the only conversion point of spec 8.1.

zipline stores a daily price as `round(price x 1000)` cast to a uint32, without a check on
that product, so a price past about 4,294,967 is stored wrong. Such an instrument is kept:
its prices go in divided by 10^n, the least n that fits, and `reader` multiplies them back
(RV-Q08). The sid is the sort order of
the market's `instrument_id`. Splits and dividends come with L1-b (#252).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.dataset as ds
from zipline.data import bundles
from zipline.data.bcolz_daily_bars import UINT32_MAX
from zipline.data.in_memory_daily_bars import InMemoryDailyBarReader

OHLC = ["open", "high", "low", "close"]
CALENDARS = {"KR": "XKRX", "US": "XNYS"}  # each market alone (8.1); ZZ has no zipline calendar
PRICE_UNITS = 1000  # zipline's bcolz_daily_bars: price x 1000 cast to a uint32, unchecked


@dataclass(frozen=True)
class Bundle:
    """What a bundle holds beside zipline's files: the sid of each instrument and the n of
    each scaled one."""

    market: str
    sids: dict[str, int]
    scales: dict[str, int]


#: The bundles `make_bundle` registered in this process, by name.
BUNDLES: dict[str, Bundle] = {}


def price_scale(high: float) -> int:
    """The least n for which `high / 10^n x 1000` fits zipline's uint32."""
    n = 0
    while high / 10**n * PRICE_UNITS >= UINT32_MAX:
        n += 1
    return n


def _events(root: Path, market: str) -> pd.DataFrame:
    """The latest version of each of `market`'s corporate actions, without the cancelled ones
    and those without a factor (TDS 5.11)."""
    found = ds.dataset(root / "corporate_actions").to_table().to_pandas()
    found = found[found["instrument_id"].str.startswith(f"{market}:")]
    found = found.assign(root=found["revision_of"].fillna(found["event_id"]))
    found = found.sort_values("ts_announced").groupby("root").tail(1)
    found = found[(found["status"] == "effective") & found["price_factor"].notna()]
    dates = ["ex_date", "record_date", "declared_date", "pay_date"]
    return found.assign(**{d: pd.to_datetime(found[d].fillna(found["ex_date"])) for d in dates})


def make_bundle(snapshot_path: Path, market: str, *, dividends: bool = True) -> str:
    """Ingest `market`'s daily bars of the TDS package at `snapshot_path` as a zipline bundle
    under `ZIPLINE_ROOT`, with its splits (ratio 1/rho) and, unless `dividends` is False, its
    cash events (zipline computes 1 - D / previous close); return its name. Its sessions must
    be the calendar's. Without dividends, zipline's close is the engine's `Price.close`."""
    bars = ds.dataset(Path(snapshot_path) / "bars", format="parquet",
                      partitioning="hive").to_table().to_pandas()  # fmt: skip
    bars = bars.assign(session_date=pd.to_datetime(bars["session_date"]),
                       instrument_id=bars["instrument_id"].astype(str))  # fmt: skip
    bars = bars[bars["instrument_id"].str.startswith(f"{market}:")]
    ids = sorted(bars["instrument_id"].unique())
    sids = {iid: k for k, iid in enumerate(ids)}
    groups = {i: g.set_index("session_date").sort_index() for i, g in bars.groupby("instrument_id")}
    scales = {iid: price_scale(float(g["high"].max())) for iid, g in groups.items()}
    days = pd.DatetimeIndex(sorted(bars["session_date"].unique()))
    name = f"nexusbt-{market}-{Path(snapshot_path).resolve().name}{'' if dividends else '-split'}"
    events = _events(Path(snapshot_path), market)
    events = events.assign(sid=events["instrument_id"].map(sids))
    share = events["affects"] == "split_and_total"

    def ingest(environ: Any, asset_db_writer: Any, minute_bar_writer: Any,
               daily_bar_writer: Any, adjustment_writer: Any, calendar: Any,
               start_session: Any, end_session: Any, *args: Any) -> None:  # fmt: skip
        sessions = calendar.sessions_in_range(start_session, end_session)
        if not sessions.equals(days):
            raise ValueError(f"{market}: the package's sessions are not {calendar.name}'s")
        asset_db_writer.write(
            equities=pd.DataFrame({
                "symbol": ids, "asset_name": ids, "exchange": CALENDARS[market],
                "start_date": [groups[i].index[0] for i in ids],
                "end_date": [groups[i].index[-1] for i in ids],
            }, index=range(len(ids))),
            exchanges=pd.DataFrame({"exchange": [CALENDARS[market]],
                                    "canonical_name": [CALENDARS[market]],
                                    "country_code": [market]}),
        )  # fmt: skip
        frames = ((sids[i], (groups[i][OHLC].fillna(0.0) / 10 ** scales[i])
                   .assign(volume=groups[i]["volume"].fillna(0.0))) for i in ids)  # fmt: skip
        daily_bar_writer.write(frames, assets=set(sids.values()), show_progress=False)
        splits = events[share].assign(ratio=events["ratio_den"] / events["ratio_num"],
                                      effective_date=events["ex_date"])  # fmt: skip
        cash = events[~share & dividends]
        cash = cash.assign(amount=cash["cash_per_share"] / cash["instrument_id"].map(
            lambda i: 10 ** scales[i]))  # fmt: skip
        adjustment_writer.write(
            splits=splits[["sid", "effective_date", "ratio"]],
            dividends=cash[["sid", "ex_date", "declared_date", "record_date", "pay_date",
                            "amount"]],
        )  # fmt: skip

    bundles.register(name, ingest, calendar_name=CALENDARS[market], start_session=days[0],
                     end_session=days[-1])  # fmt: skip
    bundles.ingest(name, os.environ, show_progress=False)
    BUNDLES[name] = Bundle(market, sids, {i: n for i, n in scales.items() if n})
    return name


class ScaledDailyBarReader(InMemoryDailyBarReader):  # type: ignore[misc]
    """A bundle's bars with each scaled instrument's prices multiplied back, and the `frames`
    that zipline 3.2.1's `get_value` reads but the class never sets (8.1's reader bug)."""

    @property
    def frames(self) -> dict[str, pd.DataFrame]:
        frames: dict[str, pd.DataFrame] = self._frames
        return frames


def reader(name: str) -> ScaledDailyBarReader:
    """The bars of the bundle `name`, as zipline reads them, with its price scales undone."""
    bundle, bars = BUNDLES[name], bundles.load(name).equity_daily_bar_reader
    sids, sessions = pd.Index(sorted(bundle.sids.values())), bars.sessions
    arrays = bars.load_raw_arrays([*OHLC, "volume"], sessions[0], sessions[-1], sids)
    frames = {c: pd.DataFrame(a, index=sessions, columns=sids)
              for c, a in zip([*OHLC, "volume"], arrays, strict=True)}  # fmt: skip
    for iid, n in bundle.scales.items():
        for c in OHLC:
            frames[c][bundle.sids[iid]] *= 10**n
    currency = pd.Series({"KR": "KRW", "US": "USD"}[bundle.market], index=sids)
    return ScaledDailyBarReader(frames, bars.trading_calendar, currency)
