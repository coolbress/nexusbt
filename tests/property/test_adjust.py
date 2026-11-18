"""P-ADJ (spec 8.3, 5.3.3, INV-11): each registered kernel's shortcut equals the reference
implementation, relative 1e-12, on random events, per-instrument scalars and late cells.

The reference of a degree-0 or degree-1 kernel is the window adjusted on a price or volume
basis, and a per-instrument scalar k scales its value by k**degree. An invariant kernel is
"computed on raw values" (5.3.3): its reference is the raw window, a cell before an event whose
`price_factor` is none still NaN (#241, Decisions 2026-11-18), and no scalar rule applies, a sum
of values scaling with them (#242, Decisions 2026-11-18).
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from nexusbt.compute._kernels_ref import (
    REGISTERED,
    AdjustmentClass,
    adjusted_window,
    shortcut,
)
from nexusbt.contracts import ResolvedActions
from nexusbt_tds.actions import Effects, Resolution

pytestmark = pytest.mark.property

IDS = ("KR:T00001", "KR:T00002")
ROWS = 12
TS_OPEN = np.arange("2020-01-01", "2020-01-13", dtype="datetime64[D]").astype("datetime64[us]")
DEGREE = {AdjustmentClass.DEGREE_0: 0, AdjustmentClass.DEGREE_1: 1}
FACTOR = st.one_of(st.none(), st.floats(0.1, 10.0))  # None: "none" (4.6)
EVENT = st.tuples(st.integers(0, len(IDS) - 1), st.integers(1, ROWS - 1), FACTOR, FACTOR,
                  st.sampled_from(["split_and_total", "total_only"]), st.booleans())  # fmt: skip


def actions(events: list[tuple[int, int, float | None, float | None, str, bool]]) -> Any:
    """The chains a cutoff resolves: effective, each with its price and share factor, or
    known with its terms pending (5.3.4: the resolver empties the amounts)."""
    chains = {}
    for i, (c, row, m, q, affects, pending) in enumerate(events):
        day = TS_OPEN[row].astype(dt.datetime).replace(tzinfo=dt.UTC)
        effects = Effects() if pending else Effects(price_factor=m, share_factor=q)
        chains[f"E{i}"] = Resolution(
            f"E{i}", IDS[c], f"E{i}", "effective", day, effective=True, terms_pending=pending,
            effects=effects, affects=affects,
        )  # fmt: skip
    return ResolvedActions(chains)


@given(
    events=st.lists(EVENT, max_size=6),
    values=st.lists(st.floats(1.0, 1000.0), min_size=ROWS * len(IDS), max_size=ROWS * len(IDS)),
    late=st.lists(st.booleans(), min_size=ROWS * len(IDS), max_size=ROWS * len(IDS)),
    scalars=st.tuples(st.floats(0.1, 10.0), st.floats(0.1, 10.0)),
    window=st.integers(1, ROWS),
    data=st.data(),
)
def test_P_ADJ_kernel_classes(  # noqa: N802 - spec 10.1's name
    events: list[Any], values: list[float], late: list[bool], scalars: tuple[float, float],
    window: int, data: st.DataObject,
) -> None:  # fmt: skip
    t = data.draw(st.integers(window - 1, ROWS - 1))
    basis = data.draw(st.sampled_from(["split", "total", "volume"]))
    price = data.draw(st.sampled_from(["split", "total"]))  # an invariant kernel's NaN rule
    raw = np.array(values).reshape(ROWS, len(IDS))
    raw[np.array(late).reshape(ROWS, len(IDS))] = np.nan  # cells not seen at t's `ready` (5.1.2)
    resolved = actions(events)
    for name, entry in REGISTERED.items():
        invariant = entry.adjustment is AdjustmentClass.INVARIANT
        on = price if invariant else basis
        cells, _ = adjusted_window(raw, t, window, resolved, IDS, TS_OPEN, on)
        if invariant:  # raw values, NaN where the reference leaves a cell NaN
            cells = np.where(np.isnan(cells), np.nan, raw[t - window + 1 : t + 1])
        np.testing.assert_allclose(
            shortcut(entry, raw, t, window, resolved, IDS, TS_OPEN, on), entry.kernel(cells),
            rtol=1e-12, equal_nan=True, err_msg=name,
        )  # fmt: skip
        if invariant:
            continue
        k = np.array(scalars)  # the declared class: a per-instrument scalar k gives k**degree
        np.testing.assert_allclose(
            entry.kernel(cells * k), k ** DEGREE[entry.adjustment] * entry.kernel(cells),
            rtol=1e-12, equal_nan=True, err_msg=name,
        )  # fmt: skip


SPLIT = st.tuples(st.integers(0, len(IDS) - 1), st.integers(1, ROWS - 1), st.floats(0.1, 10.0))


@given(
    splits=st.lists(SPLIT, max_size=6),
    close=st.lists(st.floats(1.0, 1000.0), min_size=ROWS * len(IDS), max_size=ROWS * len(IDS)),
    volume=st.lists(st.floats(1.0, 1e6), min_size=ROWS * len(IDS), max_size=ROWS * len(IDS)),
    window=st.integers(1, ROWS),
    data=st.data(),
)
def test_P_ADJ_dollar_volume_unmoved_by_pure_splits(  # noqa: N802 - P-ADJ, spec 8.3's name
    splits: list[tuple[int, int, float]], close: list[float], volume: list[float], window: int,
    data: st.DataObject,
) -> None:  # fmt: skip
    """3.4 calls `AverageDollarVolume` invariant, "value = price x volume": under pure splits
    (`share_factor = 1/price_factor`), the split-adjusted close times the adjusted volume is the
    raw product, and the kernel gives the raw product's value (#242, Decisions 2026-11-18)."""
    t = data.draw(st.integers(window - 1, ROWS - 1))
    resolved = actions([(c, row, m, 1 / m, "split_and_total", False) for c, row, m in splits])
    p, v = (np.array(x).reshape(ROWS, len(IDS)) for x in (close, volume))
    adjusted_close, _ = adjusted_window(p, t, window, resolved, IDS, TS_OPEN, "split")
    adjusted_volume, _ = adjusted_window(v, t, window, resolved, IDS, TS_OPEN, "volume")
    product = adjusted_close * adjusted_volume
    raw = (p * v)[t - window + 1 : t + 1]
    np.testing.assert_allclose(product, raw, rtol=1e-12)
    kernel = REGISTERED["AverageDollarVolume"].kernel
    np.testing.assert_allclose(kernel(product), kernel(raw), rtol=1e-12)
