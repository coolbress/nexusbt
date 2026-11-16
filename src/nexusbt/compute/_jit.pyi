from collections.abc import Callable
from typing import Any

import numpy as np

class _Vectorized:
    @property
    def ufunc(self) -> np.ufunc: ...

def vectorize(
    signatures: list[str], **options: Any
) -> Callable[[Callable[..., float]], _Vectorized]: ...
