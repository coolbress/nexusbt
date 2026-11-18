"""P-ADJ (spec 8.3, 5.3.3, INV-11): each registered kernel's shortcut equals the reference
implementation, relative 1e-12, on random events, per-instrument scalars and late cells.

Besides the registry's own kernels, two kernels that exist only in this file stand for the
classes no built-in kernel has yet (T1.9 registers those): a degree-0 ratio and an invariant
count. They are never put in the product registry.
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
    Registered,
    adjusted_window,
    shortcut,
)
from nexusbt.contracts import ResolvedActions
from nexusbt_tds.actions import Effects, Resolution

pytestmark = pytest.mark.property

IDS = ("KR:T00001", "KR:T00002")
ROWS = 12
TS_OPEN = np.arange("2020-01-01", "2020-01-13", dtype="datetime64[D]").astype("datetime64[us]")
#: For this test only: the classes the registry has no kernel of yet.
KERNELS = {
    **REGISTERED,
    "ratio_for_test_only": Registered(lambda x: x[-1] / x[0], AdjustmentClass.DEGREE_0),
    "finite_count_for_test_only": Registered(
        lambda x: np.isfinite(x).sum(axis=0).astype(np.float64), AdjustmentClass.INVARIANT
    ),
}
DEGREE = {AdjustmentClass.DEGREE_0: 0, AdjustmentClass.DEGREE_1: 1, AdjustmentClass.INVARIANT: 0}
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
    raw = np.array(values).reshape(ROWS, len(IDS))
    raw[np.array(late).reshape(ROWS, len(IDS))] = np.nan  # cells not seen at t's `ready` (5.1.2)
    resolved = actions(events)
    for name, entry in KERNELS.items():
        cells, _ = adjusted_window(raw, t, window, resolved, IDS, TS_OPEN, basis)
        np.testing.assert_allclose(
            shortcut(entry, raw, t, window, resolved, IDS, TS_OPEN, basis), entry.kernel(cells),
            rtol=1e-12, equal_nan=True, err_msg=name,
        )  # fmt: skip
        k = np.array(scalars)  # the declared class: a per-instrument scalar k gives k**degree
        np.testing.assert_allclose(
            entry.kernel(cells * k), k ** DEGREE[entry.adjustment] * entry.kernel(cells),
            rtol=1e-12, equal_nan=True, err_msg=name,
        )  # fmt: skip
