"""Imitates zipline names; no zipline import (spec 2.3, 2.5)."""

from __future__ import annotations

import warnings
from collections.abc import Callable, Sequence
from types import FunctionType
from typing import Any, ClassVar, NoReturn

import numpy as np

from nexusbt.pipeline import BoundColumn, Factor, Filter, factor
from nexusbt.pipeline._terms import _constant, _impure, _readable

__all__ = ["CustomFactor", "USEquityPricing"]


class USEquityPricing:
    """zipline's `USEquityPricing`. Its `close` carries zipline's adjustment DB, splits and
    dividends, so here it is the total-return close `Price.close_tr` (spec 3.4, A-39)."""

    close: ClassVar[BoundColumn] = BoundColumn.of("Price", "close_tr")


_NOT_CARRIED = {
    "outputs": "several outputs are not in this shim; write one CustomFactor for each output",
    "params": "compute parameters are not in this shim; write the value into compute, or use"
    " @nx.factor, whose keyword values bind with f(n=63)",
    "domain": "the engine computes each market of the run; choose the markets with"
    " run_pipeline(markets=...) and remove the domain line",
}
_DEFAULT_ONLY: dict[str, tuple[Callable[[Any], bool], str]] = {
    "dtype": (lambda v: np.dtype(v) == np.float64, "this shim's CustomFactor is float64 only"),
    "missing_value": (lambda v: isinstance(v, float) and np.isnan(v),
                      "a cell compute leaves unwritten is NaN here; remove missing_value"),
    "ndim": (lambda v: v == 2, "compute's windows are two-dimensional (rows, instruments)"),
}  # fmt: skip


def _kept(fn: FunctionType) -> str:
    """A method's source and that of each function it keeps along `__wrapped__` (#596): under a
    project `functools.wraps` decorator its own source is the inner function's, and the method
    body is the function the inner one keeps. A plain method gives its source alone."""
    parts, seen, kept = [_readable(fn)], {id(fn)}, getattr(fn, "__wrapped__", None)
    while isinstance(kept, FunctionType) and id(kept) not in seen:
        seen.add(id(kept))
        parts.append(_readable(kept))
        kept = getattr(kept, "__wrapped__", None)
    return "\n".join(parts)


class _NotPassed:
    """What `compute` gets as `today` and `assets`: reading it stops with the reason (#251)."""

    def _refuse(self, *_: object) -> NoReturn:
        raise TypeError("nexusbt.compat.zipline does not pass today and assets to compute; the"
                        " engine passes a user function its windows only (#251)")  # fmt: skip

    __getattr__ = __getitem__ = __len__ = __iter__ = __bool__ = _refuse


class CustomFactor:
    """zipline's `CustomFactor`: a subclass with `inputs`, `window_length` and
    `compute(self, today, assets, out, *inputs)`; calling it makes the engine's user window
    function (`@nx.factor`, spec 3.3), which is the Factor returned.

    - `compute` gets each input's window `(window_length, n)`, last row the computation day,
      and writes the result into `out`, which starts as NaN; its return value is not read, as in
      zipline. `self` is the class. A class without `compute` stops when it is called.
    - `today` and `assets` are not passed: the engine passes a user function its windows only
      (#251). Reading an attribute or an item of them, their length, iterating or testing them
      stops with that reason; another use (`today == x`, `today + x`) is not caught.
    - What `compute` reads through `self` is in the term's hash when it is a constant or a
      method (its source); other data, a list or an array, is E24 with the L1 cache off, as a
      non-constant global is (spec 6.5 (6)).
    - `window_safe` is taken and means nothing: whether a Factor input may be read over a window
      is the engine's degree rule alone (E17, spec 3.3, 3.4). It refuses a price level and lets a
      ratio and a rank of prices pass; zipline refuses by the flag instead, so a ratio
      CustomFactor without it passes here and is refused there.
    - A class setting `outputs`, `params` or `domain`, or a `dtype`, `missing_value` or `ndim`
      other than zipline's default, stops where it is defined: the shim does not carry them out,
      and leaving them out would change the result.
    """

    inputs: ClassVar[Sequence[BoundColumn | Factor]] = ()
    window_length: ClassVar[int] = 0
    mask: ClassVar[Filter | None] = None
    window_safe: ClassVar[bool] = False

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """An attribute the shim does not carry out, and whose loss would change the result,
        stops the class here, where it is defined (#251)."""
        super().__init_subclass__(**kwargs)
        for name, why in _NOT_CARRIED.items():
            if name in vars(cls):
                raise TypeError(f"{cls.__name__}.{name}: {why}")
        for name, (taken, why) in _DEFAULT_ONLY.items():
            if name in vars(cls) and not taken(vars(cls)[name]):
                raise TypeError(f"{cls.__name__}.{name} = {vars(cls)[name]!r}: {why}")

    def __new__(  # type: ignore[misc]  # zipline's call makes a term, so typed code sees a Factor
        cls,
        inputs: Sequence[BoundColumn | Factor] | None = None,
        window_length: int | None = None,
        mask: Filter | None = None,
    ) -> Factor:
        compute = getattr(cls, "compute", None)
        if not isinstance(compute, FunctionType):
            raise TypeError(f"{cls.__name__} defines no compute(self, today, assets, out, *inputs)")
        named = {k: v for c in reversed(cls.__mro__) for k, v in vars(c).items()
                 if not k.startswith("__") and k not in ("inputs", "mask")}  # fmt: skip
        # what compute may read through `self`: constants and methods' source are hashed; other
        # data is E24 with the L1 cache off, as a non-constant global is (6.5 (6), #561)
        source = {k: _kept(v) for k, v in named.items() if isinstance(v, FunctionType)}
        constants = {k: v for k, v in named.items() if _constant(v)}
        hashed = tuple(sorted((constants | source).items()))
        skip = (*constants, *source)  # and a type, such as zipline's `dtype`
        class_data = {k: v for k, v in named.items()
                      if k not in skip and not isinstance(v, type)} or None  # fmt: skip

        def run(*windows: Any) -> Any:
            _ = hashed, class_data  # read here, so they are in the term's hash and E24 check
            out = np.full(windows[0].shape[1], np.nan)
            compute(cls, _NotPassed(), _NotPassed(), out, *windows)
            return out

        run.__name__ = run.__qualname__ = cls.__name__
        term = factor(
            window_length if window_length is not None else cls.window_length,
            list(inputs if inputs is not None else cls.inputs),
            mask=mask if mask is not None else cls.mask,
        )
        with warnings.catch_warnings():  # E24 names the class's attributes, said below
            warnings.filterwarnings("ignore", message=r"(?s).*reads global 'class_data';")
            made = term(run)
        if class_data:
            warnings.warn(str(_impure(cls.__name__, sorted(class_data))), stacklevel=2)
        return made
