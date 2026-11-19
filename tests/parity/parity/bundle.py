"""TDS package → zipline bundle: `make_bundle`, the only conversion point of spec 8.1.

zipline stores a daily price as `round(price x 1000)` in a uint32 and zeroes a row past it.
An instrument whose prices pass that is not dropped: its prices go in divided by 10^n, the
least n that fits, and `reader` multiplies them back (RV-Q08). The sid is the sort order of
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
PRICE_UNITS = 1000  # zipline's bcolz_daily_bars: price x 1000 in a uint32


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


def make_bundle(snapshot_path: Path, market: str) -> str:
    """Ingest `market`'s daily bars of the TDS package at `snapshot_path` as a zipline bundle
    under `ZIPLINE_ROOT`; return its name. Its sessions must be the calendar's."""
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
    name = f"nexusbt-{market}-{Path(snapshot_path).resolve().name}"

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
        adjustment_writer.write()

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
