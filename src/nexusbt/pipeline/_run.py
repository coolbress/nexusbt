"""Running a user term's function (3.3, 5.3.7): its call on the input windows, the E8 a row
before the window gives, the check of its declared `adjustment` (E17, E45), and the user's line
the messages point at (6.6 header). What a user function reads, for the hash and E24, is in
`_terms`, which names these again for its importers (#800)."""

from __future__ import annotations

import inspect
import math
import re
import sys
import traceback
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
import numpy.typing as npt

from nexusbt.contracts import SkippedWorkNotice, TermDomainError, WindowError

if TYPE_CHECKING:
    from ._terms import Term

_OUT_OF_WINDOW = re.compile(r"index (-?\d+) is out of bounds for axis 0 with size (\d+)")


def call_user(
    term: Term, windows: Sequence[Any], n: int, fn: Callable[..., Any] | None = None
) -> npt.NDArray[np.float64]:
    """A user term's function (`fn`, else the one it was built from) on its input windows
    (5.3.7), its result as float64 `(n,)`. A row before the window is `WindowError` (E8)
    suggesting the window it needs, as is a result of another shape or of a non-numeric dtype;
    any other exception is the user's, as raised, through frames hidden from its traceback
    (`__tracebackhide__`, R-42), as the executor's on the way here are."""
    __tracebackhide__ = True
    params, fn = dict(term.params), fn or term.function
    if fn is None:
        raise ValueError(f"no function given for the user term {params['function']}")
    name, window = params["function"], params["window"]
    try:
        got = np.asarray(fn(*windows, **dict(params.get("bound", ()))))
    except IndexError as error:
        found = _OUT_OF_WINDOW.fullmatch(str(error))
        if found is None or int(found[2]) != window:
            raise
        k = int(found[1])
        needed = -k if k < 0 else k + 1
        frame = traceback.extract_tb(error.__traceback__)[-1]
        at = f"{Path(frame.filename).name}:{frame.lineno}"
        names = list(inspect.signature(fn).parameters)
        column = names[0] if len(term.inputs) == 1 and names else "an input"
        raise _window_error(name, at, f"reads {column}[{k}] but window={window}",
                            f"@nx.factor(window={needed}, ...)") from error  # fmt: skip
    if got.shape != (n,) or got.dtype != np.float64:
        at = _user_line().split(" in ")[0]
        raise _window_error(name, at, f"returned {got.dtype} {got.shape}, not float64 ({n},)",
                            "return one float64 number for each column of the window")  # fmt: skip
    return got


#: 3.3 `adjustment`: one instrument's input windows are multiplied by this fixed constant.
SCALE = 2.0


def check_adjustment(
    term: Term, windows: Sequence[Any], got: npt.NDArray[np.float64], ids: Sequence[str],
    scales: Sequence[float], fn: Callable[..., Any] | None = None,
) -> bool:  # fmt: skip
    """3.3: test a user term's declared `adjustment` on the `windows` (unchanged copies of the
    ones the function was given) and its result `got`, on the first column whose result is
    finite and not 0, each input's column multiplied by its scale (`_degree.input_scales`):
    E17 when the declaration does not hold; False when no column could tell (NaN and 0 are the
    same under any scaling), True once checked."""
    params = dict(term.params)
    declared = params["adjustment"]
    found = np.flatnonzero(np.isfinite(got) & (got != 0))
    if not found.size:
        return False
    j = int(found[0])
    scaled = [np.array(w, dtype=np.float64) for w in windows]
    for window, scale in zip(scaled, scales, strict=True):
        window[:, j] *= scale
    again = call_user(term, scaled, len(got), fn)[j]
    expected = got[j] * (SCALE if declared == "degree 1" else 1.0)
    if abs(again - expected) <= 1e-12 * max(1.0, abs(expected)):
        return True
    name, at = params["function"], def_line(fn or term.function)
    other = "degree 1" if declared == "degree 0" else "degree 0"
    return_ = "change" if declared == "degree 0" else f"scale by {SCALE:g}"
    raise TermDomainError(
        what=f"{name} is declared adjustment='{declared}' but its result for {ids[j]} went from"
        f" {got[j]!r} to {again!r} when {ids[j]}'s prices were scaled by {SCALE:g}",
        where=f"factor {name}",
        why=f"a declared '{declared}' result does not {return_} under that scaling, and the"
        " refusal of shift and window inputs (3.4) reads the declaration",
        fix=f"remove adjustment=..., or declare '{other}' if that is what {name} is",
        more="spec 3.3 (adjustment), 3.4 and 6.6 (E17)",
        layer=f"your code — {at} in {name}",
        at=at,
        subject=name,
    )


def def_line(fn: object) -> str:
    """`file:line` of a function's `def`; `-` for a callable that is not a plain function."""
    code = getattr(fn, "__code__", None)
    return f"{Path(code.co_filename).name}:{code.co_firstlineno}" if code else "-"


#: Why a declaration was not checked, by whether its inputs' degrees are known (E45).
UNCHECKED = {
    True: ("every result it gave in this run was NaN or 0, which any scaling leaves as it is,"
           " so it cannot tell degree 0 from degree 1",
           "run it over rows where it gives finite, non-zero values, or remove adjustment=..."),
    False: ("an input has no known degree in the price factor (3.4), so the engine cannot say"
            " what that input is when prices are scaled", "remove adjustment=..."),
}  # fmt: skip


def unchecked(name: str, declared: str, at: str, scalable: bool) -> SkippedWorkNotice:
    """6.6 no silent failure: a declaration the run could not check (E45)."""
    why, fix = UNCHECKED[scalable]
    return SkippedWorkNotice(
        what=f"skipped 1 declaration check for reason declaration_unchecked: {name}'s"
        f" adjustment='{declared}' was not checked",
        where=f"factor {name}",
        why=why,
        fix=fix,
        more="spec 3.3 (adjustment) and 6.6 (no silent failure)",
        layer=f"your code — {at} in {name}",
        at=at,
        subject=name,
    )


def _window_error(name: str, at: str, what: str, fix: str) -> WindowError:
    return WindowError(
        what=f"{name} {what}",
        where=f"factor {name}",
        why="the function's window is the rows and shape the engine loads for it",
        fix=fix,
        more="spec 3.3 and 5.3.7 (windows)",
        layer=f"your code — {at} in {name}",
        at=at,
        subject=name,
    )


def _user_line() -> str:
    """`file:line in function` of the first frame outside the engine (6.6 header)."""
    frame, engine = sys._getframe(1), Path(__file__).parents[1]
    while Path(frame.f_code.co_filename).is_relative_to(engine) and frame.f_back is not None:
        frame = frame.f_back
    name = frame.f_code.co_name
    where = f"{Path(frame.f_code.co_filename).name}:{frame.f_lineno}"
    return f"{where} in {name if name.isidentifier() else 'module'}"


def _pasteable(value: object) -> str:
    """`value` as Python a user can paste into a call (#624): `repr`, but a NaN or an infinity,
    whose `repr` (`nan`, `inf`) is not Python, as `float("nan")`, `float("inf")` or
    `float("-inf")`, also inside a tuple or a frozenset of bound values (6.5 (6))."""
    if isinstance(value, float) and not math.isfinite(value):
        return f'float("{value}")'
    if isinstance(value, tuple):
        shown = ", ".join(map(_pasteable, value))
        return f"({shown},)" if len(value) == 1 else f"({shown})"
    if isinstance(value, frozenset) and value:
        return f"frozenset({{{', '.join(map(_pasteable, value))}}})"
    return repr(value)
