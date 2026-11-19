"""`nx.screen(factor, top=n)`'s result (spec 3.8, 3.9 Screen), T1.13 (#249).

The factor's top n per market on one session, among the listed instruments (3.3's default
domain) until T2.4 brings the investable universe (#249 Decisions, 2026-11-19).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping
from dataclasses import dataclass

import pyarrow as pa

from nexusbt.contracts import ID_COLUMN

#: What the universe is until T2.4: 3.3's default domain, said on every result (#43's notes).
UNIVERSE = "universe: listed (investable comes with T2.4)"


@dataclass(frozen=True, slots=True, eq=False)
class Screen:
    """3.9: `table` is `(market, session_date, rank, instrument_id, score)`, by market and rank;
    `scheduled` is True, as a factor has no schedule to be off; `asof` is each market's session.
    `universe` and `selected` count the listed instruments and the rows kept, per market;
    `run_id` is the sealed `kind="screen"` run (3.8)."""

    table: pa.Table
    scheduled: bool
    asof: Mapping[str, dt.date]
    universe: Mapping[str, int]
    selected: Mapping[str, int]
    snapshot_id: str
    run_id: str | None = None

    def __str__(self) -> str:
        """3.9's shape: the header, a row per selected instrument, the universe line and the
        last line with the run; no `name`, `target_w` or `flags` column yet (#249)."""
        when = " · ".join(f"{m} {d} close" for m, d in self.asof.items())
        lines = [f"factor  screen as of {when}   data {self.snapshot_id}   scheduled",
                 f"{'rank':>4}  {ID_COLUMN:<14}  mkt  score"]  # fmt: skip
        for r in self.table.to_pylist():
            lines.append(f"{r['rank']:>4}  {r[ID_COLUMN]:<14}  {r['market']:<3}  "
                         f"{r['score']:.6g}")  # fmt: skip
        sizes = " / ".join(f"{n} {m}" for m, n in self.universe.items())
        chosen = ", ".join(f"{self.selected[m]}/{n} {m}" for m, n in self.universe.items())
        lines += [UNIVERSE, f"universe {sizes} · selected {chosen} · run {self.run_id}"]
        return "\n".join(lines)
