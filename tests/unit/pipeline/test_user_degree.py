"""A user function's declared degree (spec 3.3 `adjustment`, 3.4, 6.6; #246, Decisions
2026-11-18 and 2026-11-19): E16 for a value other than the two, E17 where #499's refusal reads
the declaration, E17 when the scaling check finds it does not hold, E45 when no row could check
it."""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest

import nexusbt as nx
from nexusbt.compute._executor import execute
from nexusbt.contracts import SchemaRegistry
from nexusbt.data._block import MarketBlock
from nexusbt.pipeline import BoundColumn, bind, graph_hash

CLOSE = BoundColumn.of("Price", "close")


def _ratio(close: Any) -> Any:
    return close[-1] / close[0]


def test_an_unknown_adjustment_is_E16_and_a_declaration_is_hashed() -> None:  # noqa: N802
    """3.3, 6.6 E16: `adjustment` takes "degree 0" or "degree 1" (an argument outside them is a
    `ConfigError` when the term is built); a declaration is part of the term, so its hash; no
    declaration leaves the hash as it was."""
    for wrong in ("invariant", "degree 2", "Degree 0"):
        with pytest.raises(nx.ConfigError, match=f"adjustment={wrong!r}") as caught:
            nx.factor(window=2, inputs=[CLOSE], adjustment=wrong)(_ratio)  # type: ignore[arg-type]
        assert caught.value.code == "E16"
    plain = nx.factor(window=2, inputs=[CLOSE])(_ratio)
    zero = nx.factor(window=2, inputs=[CLOSE], adjustment="degree 0")(_ratio)
    assert graph_hash(zero) != graph_hash(plain)
    assert "adjustment" not in dict(plain.params)


def _last(close: Any) -> Any:
    return close[-1]


def test_a_declared_degree_1_is_refused_through_shift_and_a_window() -> None:
    """3.3, 3.4, #499's check: a user function declared degree 1 is E17 through `shift(k ≥ 1)`
    and as the `Factor` input of a window of two rows or more; one declared degree 0, and one
    with no declaration, are not refused."""
    registry = SchemaRegistry(columns={})
    level = nx.factor(window=1, inputs=[CLOSE], adjustment="degree 1")(_last)
    for fed in (level.shift(1), nx.factor(window=2, inputs=[level])(_ratio)):
        with pytest.raises(nx.TermDomainError, match="_last") as caught:
            bind(fed, registry)
        assert caught.value.code == "E17"
    for adjustment in ("degree 0", None):
        ratio = nx.factor(window=2, inputs=[CLOSE], adjustment=adjustment)(_ratio)
        bind(ratio.shift(1), registry)
        bind(nx.factor(window=2, inputs=[ratio])(_ratio), registry)


def run(terms: list[Any], close: Any, spans: list[tuple[int, int]] | None = None,
        column: str = "close") -> Any:  # fmt: skip
    """`execute` at every row over two instruments' `close` (rows by 2) as `column`, bars on
    time, no corporate actions, in the chunks `spans` (one chunk by default)."""
    n = len(close)
    dates = np.datetime64("2020-01-01") + np.arange(n).astype("timedelta64[D]")
    ready = (dates + np.timedelta64(16, "h")).astype("datetime64[us]")

    def read(a: int, b: int) -> MarketBlock:  # the block of rows a..b, as a chunk reads it
        rows = slice(a, b + 1)
        return MarketBlock("KR", dates[rows], 0, ("KR:A", "KR:B"),
                           {column: np.asarray(close, float)[rows]}, np.ones((b + 1 - a, 2), bool),
                           np.zeros((b + 1 - a, 2), np.int8),
                           np.repeat(ready[rows, None], 2, axis=1))  # fmt: skip

    return execute(terms, range(n), spans or [(0, n - 1)], read, ready)


CLOSES = np.arange(10)[:, None] + np.array([[100.0, 1000.0]])


def test_a_declaration_that_does_not_hold_is_E17() -> None:  # noqa: N802
    """3.3, 6.6 E17: with one instrument's input windows scaled by 2, a function declared
    degree 0 whose result changes, or declared degree 1 whose result does not double, is E17
    naming the function and the declaration; a declaration that holds runs."""
    cases: list[tuple[Any, Any, Any]] = [(_last, "degree 0", "degree 1"),
                                         (_ratio, "degree 1", "degree 0")]  # fmt: skip
    for fn, wrong, right in cases:
        term = nx.factor(window=2, inputs=[CLOSE], adjustment=wrong)(fn)
        with pytest.raises(nx.TermDomainError, match=f"{fn.__name__} is declared "
                           f"adjustment='{wrong}'") as caught:  # fmt: skip
            run([term], CLOSES)
        assert caught.value.code == "E17"
        run([nx.factor(window=2, inputs=[CLOSE], adjustment=right)(fn)], CLOSES)


def _std(returns: Any) -> Any:
    return returns.std(axis=0)


def _change(close: Any) -> Any:
    return close[-1] - close[0]


def test_each_input_is_scaled_by_its_degree() -> None:
    """3.3, 3.4: an input of degree 0 (a return) is left as it is when prices are scaled, so the
    volatility of a declared degree-0 return holds degree 0; rows whose result is 0 are skipped
    and the first non-zero one is checked; a volume input, of degree 1 in the quantity factor,
    leaves the declaration unchecked (E45)."""
    ret = nx.factor(window=2, inputs=[CLOSE], adjustment="degree 0")(_ratio)
    run([nx.factor(window=3, inputs=[ret], adjustment="degree 0")(_std)], CLOSES)
    close = CLOSES.copy()
    close[:6] = 100.0  # `_change` is 0 up to row 6
    run([nx.factor(window=2, inputs=[CLOSE], adjustment="degree 1")(_change)], close)
    with pytest.raises(nx.TermDomainError, match="_change is declared adjustment='degree 0'"):
        run([nx.factor(window=2, inputs=[CLOSE], adjustment="degree 0")(_change)], close)
    volume = nx.factor(window=2, inputs=[BoundColumn.of("Price", "volume")],
                       adjustment="degree 0")(_ratio)  # fmt: skip
    with pytest.warns(UserWarning, match="an input has no known degree in the price factor"):
        run([volume], CLOSES, column="volume")


def _nan(close: Any) -> Any:
    return close[-1] * np.nan


def test_a_declaration_no_row_could_check_is_E45() -> None:  # noqa: N802
    """6.6 no silent failure: a NaN or 0 result is the same under any scaling, so those rows
    are skipped; when no row is left, the run ends with E45 `declaration_unchecked`."""
    term = nx.factor(window=2, inputs=[CLOSE], adjustment="degree 0")(_nan)
    with pytest.warns(UserWarning, match=r"SkippedWorkNotice \[E45\]") as caught:
        run([term], CLOSES)
    text = str(caught[0].message)
    assert "declaration_unchecked" in text
    assert "_nan's adjustment='degree 0' was not checked" in text


def _tripled(close: Any) -> Any:
    close[-1] *= 3  # the user writes into the window: the check must not read this
    return close[-1]


def test_the_check_reads_copies_and_any_chunking_gives_one_verdict() -> None:
    """INV-03 and the owner's conditions (#246, 2026-11-18): the check runs on copies of the
    windows the function was given, so a function that writes into them is still degree 1;
    the rows before the first finite one are skipped; the values, the hash and the verdict are
    the same in one chunk and in two, the first checkable row lying in the second."""
    close = CLOSES.copy()
    close[:6] = np.nan  # the first finite result is at row 6
    term = nx.factor(window=2, inputs=[CLOSE], adjustment="degree 1")(_tripled)
    key = graph_hash(term)
    one, two = run([term], close), run([term], close, [(0, 4), (5, 9)])
    values = one[key]["value"].to_numpy()
    np.testing.assert_array_equal(values, two[key]["value"].to_numpy())  # NaN equal to NaN
    assert values[12:14].tolist() == [318.0, 3018.0]  # row 6, as the function gave it
    wrong = nx.factor(window=2, inputs=[CLOSE], adjustment="degree 0")(_tripled)
    for spans in (None, [(0, 4), (5, 9)]):
        with pytest.raises(nx.TermDomainError, match="_tripled is declared"):
            run([wrong], close, spans)
