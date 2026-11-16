"""The Numba entry points the engine compiles with; `_jit.pyi` gives them their types (spec 9.1
`ci / typecheck`): numba ships `py.typed` but leaves these unannotated."""

from __future__ import annotations

from numba import vectorize

__all__ = ["vectorize"]
