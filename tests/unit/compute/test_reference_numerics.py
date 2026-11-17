"""5.3.10's reference numerics: left-fold sums and compiled element functions, T1.7b (#240)."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from nexusbt.compute import _crosssection, _elem, _kernels

pytestmark = pytest.mark.unit

#: The left fold drops each 1 into 1e16 and ends at 0.0; numpy's pairwise sum keeps seven.
DIVERGES = np.array([1e16, 1, 1, 1, 1, 1, 1, 1, -1e16, 0, 0, 0, 0, 0, 0, 0], dtype=np.float64)
#: Ascending, the 1 is lost in 1e16: 0.0; descending, the 1e16s cancel first: 1.0.
ORDERED = np.array([1.0, 1e16, -1e16])

#: 5.3.10 (4): numpy reductions whose order is pairwise or not stated (`std`, `var` and `dot`
#: sum inside), called as `np.x(...)`, `a.x(...)` or a bare imported `x(...)`, and `@`.
PAIRWISE = {"sum", "mean", "nansum", "nanmean", "reduce", "cumsum", "average", "std", "var",
            "nanstd", "nanvar", "prod", "nanprod", "dot", "matmul", "einsum", "inner"}  # fmt: skip


def pairwise_calls(source: str) -> list[str]:
    found = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call):
            name = getattr(node.func, "attr", getattr(node.func, "id", None))
            if name in PAIRWISE:
                found.append(ast.unparse(node.func))
        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.MatMult):
            found.append("@")
    return found


def test_left_fold_order_defined() -> None:
    """A case where `np.sum` differs: the reference gives the left fold in ascending order,
    ADR-0019 definition A."""
    assert np.sum(DIVERGES) == 7.0  # the case tells the two orders apart
    assert _kernels.fold_sum(DIVERGES) == 0.0
    assert _kernels.fold_sum(ORDERED) == 0.0  # descending would give 1.0
    values = np.column_stack([np.r_[5.0, DIVERGES], np.r_[5.0, np.ones(16)]])
    found = _kernels.window_sum(values, 16, np.array([16, 3], dtype=np.int64))
    assert found[0].tolist() == [0.0, 16.0]  # rows 1 to 16, each column its own fold
    assert np.isnan(found[1]).all()  # the window of row 3 starts before row 0
    assert _kernels.window_sum(ORDERED[:, None], 3, np.array([2]))[0, 0] == 0.0


@pytest.mark.parametrize(
    ("window", "rows", "message"),
    [(0, [1], "at least one row"), (2, [3], r"before row 3, not 3")],
)
def test_window_sum_refuses_a_window_or_row_it_cannot_read(
    window: int, rows: list[int], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        _kernels.window_sum(np.zeros((3, 1)), window, np.array(rows, dtype=np.int64))


def test_no_numpy_pairwise_in_reference() -> None:
    """5.3.10 (4): the reference kernels sum with an explicit loop, never a numpy reduction."""
    for module in (_kernels, _elem, _crosssection):
        assert pairwise_calls(Path(str(module.__file__)).read_text()) == []
    source = "np.sum(x)\nx.mean(axis=0)\nnp.add.reduce(x)\nnp.var(x)\nsum(x)\na @ b"
    assert pairwise_calls(source) == ["np.sum", "x.mean", "np.add.reduce", "np.var", "sum", "@"]


def test_transcendental_uses_compiled_elementwise(monkeypatch: pytest.MonkeyPatch) -> None:
    """5.3.10 2a: each element function is a Numba-compiled float64 ufunc, and the reference
    kernels call it rather than numpy's own function or the Python source."""
    pairs = {"log": _kernels.LOG, "log1p": _kernels.LOG1P, "exp": _kernels.EXP, "power": None}
    x = np.array([0.5, 1.0, 2.0, 1e-300, 700.0])
    for name, code in pairs.items():
        compiled = getattr(_elem, name)
        assert isinstance(compiled, np.ufunc)
        assert compiled not in (np.log, np.log1p, np.exp, np.power)
        assert compiled.types == (["d->d"] if code is not None else ["dd->d"])  # not object `O`
        calls: list[str] = []

        def spy(*args: Any, _f: np.ufunc = compiled, _n: str = name, _c: list[str] = calls) -> Any:
            _c.append(_n)
            return _f(*args)

        monkeypatch.setattr(_elem, name, spy)
        if code is None:
            found = _kernels.power(x, np.full_like(x, 1.5))
            expected = compiled(x, np.full_like(x, 1.5))
        else:
            found, expected = _kernels.elementwise(code, x), compiled(x)
        assert calls == [name]
        assert found.tobytes() == expected.tobytes()
    with np.errstate(invalid="ignore"):  # error_model="numpy": NaN, not an exception
        assert np.isnan(_kernels.elementwise(_kernels.LOG, np.array([-1.0])))[0]
    with pytest.raises(ValueError, match="code 3"):
        _kernels.elementwise(3, x)


def test_element_sources_agree_with_compiled() -> None:
    """The Python sources run too, so coverage counts them (9.1 `ci / test`); the bit promise is
    the compiled ufunc's alone, so they agree within rounding."""
    for source, compiled in [(_elem._log, _elem.log), (_elem._log1p, _elem.log1p),
                             (_elem._exp, _elem.exp)]:  # fmt: skip
        assert source(2.0) == pytest.approx(compiled(2.0), rel=1e-15)
    assert _elem._pow(2.0, 1.5) == pytest.approx(_elem.power(2.0, 1.5), rel=1e-15)
