"""A term's value in a cell (spec 5.4.1, #648): -0.0 becomes +0.0, and nothing else moves.

Over float64 cells drawn by their bits (finite numbers, subnormals, NaN with any payload and
sign) and both zeros, every listed cell that is not -0.0 and not ±inf keeps its 64 bits; -0.0
becomes the bits of +0.0.
"""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import example, given
from hypothesis import strategies as st

from nexusbt.compute._executor import term_value

pytestmark = pytest.mark.property

PLUS, MINUS = np.float64(0.0).view(np.int64), np.float64(-0.0).view(np.int64)
INF = np.float64(np.inf).view(np.int64)


def _not_inf(bits: int) -> bool:
    return bool(bits & ~MINUS != INF)  # the sign bit cleared: +inf's bits for ±inf


#: Both zeros, a quiet NaN of each sign, a signalling NaN and the smallest subnormal.
SPECIAL = [int(PLUS), int(MINUS), 0x7FF8000000000000, -0x0008000000000000, 0x7FF0000000000001, 1]
#: A cell as its bits: any float64 but ±inf, with SPECIAL drawn often.
CELL = st.one_of(st.sampled_from(SPECIAL), st.integers(-(2**63), 2**63 - 1).filter(_not_inf))


@given(st.lists(CELL, min_size=1, max_size=64))
@example([int(MINUS), int(PLUS), 0x7FF8000000000123, -0x0007FFFFFFFFFFFF])
def test_only_a_minus_zero_changes(cells: list[int]) -> None:
    found = np.array(cells, dtype=np.int64).view(np.float64)
    got = term_value(found, np.ones(len(cells), dtype=np.bool_)).view(np.int64)
    want = np.where(np.array(cells) == MINUS, PLUS, np.array(cells))
    assert got.tolist() == want.tolist()
