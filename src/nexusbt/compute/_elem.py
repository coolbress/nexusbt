"""The transcendental element functions of 5.3.10 2a (`log`, `log1p`, `exp`, `pow`).

Each is compiled once with Numba as a ufunc, and every path calls that compiled ufunc: the
reference kernels too, never its Python source or numpy's own `np.log`, so the reference and a
fast kernel give the same bits in one environment (P-KERNEL). The options are 5.3.10 (5)'s.
"""

from __future__ import annotations

import math

import numpy as np

from nexusbt.compute._jit import vectorize

#: `parallel=False` is the cpu target's own; a ufunc is always built with `error_model="numpy"`
#: (numba's `ufuncbuilder` sets it and takes no option for either), so `log(-1.0)` is NaN.
_OPTIONS = {"nopython": True, "cache": True, "fastmath": False}
_UNARY = ["float64(float64)"]


def _log(x: float) -> float:
    return math.log(x)


def _log1p(x: float) -> float:
    return math.log1p(x)


def _exp(x: float) -> float:
    return math.exp(x)


def _pow(x: float, y: float) -> float:
    return math.pow(x, y)


#: The numpy ufuncs numba builds: fixed once built, they compile nothing more.
log: np.ufunc = vectorize(_UNARY, **_OPTIONS)(_log).ufunc
log1p: np.ufunc = vectorize(_UNARY, **_OPTIONS)(_log1p).ufunc
exp: np.ufunc = vectorize(_UNARY, **_OPTIONS)(_exp).ufunc
power: np.ufunc = vectorize(["float64(float64, float64)"], **_OPTIONS)(_pow).ufunc
