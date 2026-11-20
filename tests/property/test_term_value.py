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


NAN = np.float64(np.nan).view(np.int64)  # an unlisted cell's NaN, as `term_value` writes it


@given(st.lists(st.tuples(CELL, st.booleans()), min_size=1, max_size=64))
@example([(int(MINUS), True), (int(PLUS), True), (0x7FF8000000000123, True),
          (-0x0007FFFFFFFFFFFF, True), (int(MINUS), False)])  # fmt: skip
def test_only_a_minus_zero_changes(drawn: list[tuple[int, bool]]) -> None:
    """A listed cell keeps its bits but -0.0's; an unlisted one is NaN (5.3.1)."""
    cells, listed = np.array([c for c, _ in drawn]), np.array([v for _, v in drawn])
    got = term_value(cells.view(np.float64), listed).view(np.int64)
    want = np.where(listed, np.where(cells == MINUS, PLUS, cells), NAN)
    assert got.tolist() == want.tolist()
