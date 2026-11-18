"""3.3's `nx.ops`: `rolling` over a term's values, and the explicit fills `where` and `coalesce`
(5.4.1, INV-12). `composite` comes with `pct_rank` (T2.20).

`rolling` reads a `Factor`'s values, each fixed at its row (5.1.2; #243, Decisions 2026-11-18),
so a window of two rows or more over a term of known non-zero degree is E17 (3.3). Its node is
a `rolling` term; `compute` holds its kernels. `where` and `coalesce` are built from `if_else`
and `isnan`, so they fill only the cells they are given.
"""

from __future__ import annotations

from dataclasses import dataclass

from ._terms import Factor, Filter, _node, _operand

#: The operations of a rolling window (3.3); `std` has ddof 1.
HOW = ("mean", "sum", "std", "min", "max", "median")


@dataclass(frozen=True, slots=True)
class Rolling:
    """`nx.ops.rolling(x, window, min_periods)`; each method is a `Factor`."""

    x: Factor
    window: int
    min_periods: int

    def _of(self, how: str) -> Factor:
        return _node(Factor, "rolling", self.x, how=how, window=self.window,
                     min_periods=self.min_periods, mask=None)  # fmt: skip

    def mean(self) -> Factor:
        return self._of("mean")

    def sum(self) -> Factor:
        return self._of("sum")

    def std(self) -> Factor:
        return self._of("std")

    def min(self) -> Factor:
        return self._of("min")

    def max(self) -> Factor:
        return self._of("max")

    def median(self) -> Factor:
        return self._of("median")


def rolling(x: Factor, window: int, min_periods: int | None = None) -> Rolling:
    """3.3: a backward window of `window` rows over `x`'s values; a row's value needs
    `min_periods` finite cells (default: `window`)."""
    if not isinstance(x, Factor):
        raise TypeError(
            f"nx.ops.rolling reads a Factor's values, not {type(x).__name__}; a column is read"
            " by a built-in factor or @nx.factor(window=..., inputs=[column])"
        )
    least = window if min_periods is None else min_periods
    if any(not isinstance(n, int) or isinstance(n, bool) for n in (window, least)):
        raise TypeError(f"a rolling window takes whole numbers, not {window!r}, {least!r}")
    if not 1 <= least <= window:
        raise ValueError(f"a rolling window takes 1 <= min_periods <= window,"
                         f" not window={window}, min_periods={least}")  # fmt: skip
    return Rolling(x, window, least)


def where(cond: Filter, a: Factor | float, b: Factor | float) -> Factor:
    """3.3: `a` where `cond` is true, `b` where it is false, NaN where it is unknown."""
    return cond.if_else(_operand(a), _operand(b))


def coalesce(*factors: Factor | float) -> Factor:
    """3.3: cell by cell, the first of `factors` that is not NaN; NaN when none is."""
    if not factors:
        raise TypeError("nx.ops.coalesce takes at least one term")
    terms = [_operand(f) for f in factors]
    found = terms[-1]
    for term in reversed(terms[:-1]):
        found = term.isnan().if_else(found, term)
    return found
