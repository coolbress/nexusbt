"""The 2.4 `nx.compute._kernels` seam: window and cross-section kernels, arrays in, arrays out.

Arguments and results are numpy arrays (or Arrow arrays sharing their buffers), int and float
scalars and integer codes: no Python objects, callbacks or dicts, so another implementation, a
Numba fast kernel or a Rust crate, replaces a kernel with the same signature (R3-26, ADR-0016).

These are the reference. A sum is the left fold in ascending row order, `acc = acc + x[r]` from
0.0 (5.3.10 (1), ADR-0019 definition A), as an explicit loop: never numpy's pairwise `np.sum`,
whose order changes with the array's length and alignment (5.3.10 (4)). A transcendental
function is the compiled element function of `_elem` (5.3.10 2a).
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

from nexusbt.compute import _elem

F64 = npt.NDArray[np.float64]

#: Integer codes of the one-argument transcendental functions, for `elementwise`: each code is
#: its function's position in `_UNARY`.
LOG, LOG1P, EXP = 0, 1, 2
_UNARY = ("log", "log1p", "exp")


def fold_sum(x: F64) -> float:
    """The left fold of `x` in order, from 0.0."""
    acc = 0.0
    for value in x.tolist():
        acc = acc + value
    return acc


def window_sum(values: F64, window: int, rows: npt.NDArray[np.int64]) -> F64:
    """For each row r of `rows`, the left fold of `values[r-window+1 .. r]` per column; NaN
    where the window starts before row 0, as nothing is there to read."""
    if window < 1:
        raise ValueError(f"a window has at least one row, not {window}")
    if rows.size and int(rows.max()) >= len(values):
        raise ValueError(f"rows must lie before row {len(values)}, not {rows.max()}")
    out = np.full((len(rows), values.shape[1]), np.nan)
    for i, r in enumerate(rows.tolist()):
        if r - window + 1 < 0:
            continue
        acc = np.zeros(values.shape[1])
        for s in range(r - window + 1, r + 1):
            acc = acc + values[s]  # each column is its own left fold
        out[i] = acc
    return out


def elementwise(code: int, x: F64) -> F64:
    """`log`, `log1p` or `exp` of each element, by its code, with the compiled function."""
    if not 0 <= code < len(_UNARY):
        raise ValueError(f"no element function has code {code}")
    found: F64 = getattr(_elem, _UNARY[code])(x)  # looked up at the call: the one compiled ufunc
    return found


def power(base: F64, exponent: F64) -> F64:
    """`base ** exponent` element by element, with the compiled function."""
    found: F64 = _elem.power(base, exponent)
    return found
