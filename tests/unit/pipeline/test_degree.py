"""Spec 3.3 and 3.4 "Degree of a term" (#499): a term of known non-zero degree fed to `shift(k ≥ 1)`
or, as a `Factor` input, to a window of two rows or more is E17 when the graph is checked."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

import nexusbt as nx
from nexusbt.contracts import SchemaRegistry
from nexusbt.factors import (
    SMA,
    AnnualizedVolatility,
    AverageDollarVolume,
    AverageTradedValue,
    Returns,
    RollingStd,
)
from nexusbt.pipeline import Factor, Pipeline, Price, Term, bind, graph_hash
from nexusbt.pipeline._degree import ZERO, degree_of

NO_SNAPSHOT_COLUMNS = SchemaRegistry(columns={}, labels={})
ROOT = Path(__file__).resolve().parents[3]


def _last(x: Any) -> Any:
    return x[-1]


def window_of(rows: int, *inputs: Any) -> Factor:
    return nx.factor(window=rows, inputs=list(inputs))(_last)


def check(term: Term) -> None:
    bind(term, NO_SNAPSHOT_COLUMNS)


def test_a_price_level_through_shift_is_e17() -> None:
    term = Price.close.latest.shift(1)
    with pytest.raises(nx.TermDomainError) as caught:
        check(term)
    assert caught.value.code == "E17"


def test_the_refusal_is_on_the_walk_not_in_the_constructor() -> None:
    # building the term raises nothing; only the check does, and the hash is the plain node's
    term = Price.close.latest.shift(1)
    assert term.op == "shift"
    assert graph_hash(term) == term._key
    with pytest.raises(nx.TermDomainError):
        bind(Pipeline({"lag": term}), NO_SNAPSHOT_COLUMNS)
    with pytest.raises(nx.TermDomainError):
        bind(Pipeline({}, screen=term > 0), NO_SNAPSHOT_COLUMNS)


@pytest.mark.parametrize(
    "term",
    [Returns(2, inputs=[Price.close.latest]), window_of(2, Price.close.latest)],
    ids=["Returns", "user window"],
)
def test_a_price_level_into_a_window_of_two_rows_is_e17(term: Factor) -> None:
    with pytest.raises(nx.TermDomainError, match="cannot feed a window of 2 rows"):
        check(term)


def test_a_window_of_one_row_takes_a_price_level() -> None:
    check(window_of(1, Price.close.latest))
    check(Returns(1, inputs=[Price.close.latest]))


def test_e1_fix_agrees_with_the_refusal() -> None:
    """#243 Decisions 2026-11-18: E1's fix sends a price level to what E17 lets through, a
    built-in factor or a window over the column, and `.shift(k ≥ 1)` to a return or ratio."""
    with pytest.raises(nx.LookAheadError) as caught:
        Price.close.latest.shift(-1)
    fix = caught.value.parts["fix"]
    assert "for a price level" in fix
    assert "inputs=[Price.close]" in fix
    assert nx.LookAheadError.example().parts["fix"] == fix  # 6.6's example, the same words
    for spec in ("engine-spec-v3.4.md", "engine-spec-v3.4.ko.md"):
        assert f'"{fix}"' in (ROOT / "docs" / "spec" / spec).read_text(encoding="utf-8")
    check(Returns(2))
    check(window_of(2, Price.close))
    check(Returns(2).shift(1))
    check((Price.close.latest / Price.open.latest).shift(1))
    with pytest.raises(nx.TermDomainError):
        check(Price.close.latest.shift(1))


@pytest.mark.parametrize(
    "term",
    [
        (Price.close.latest * 1).shift(1),
        (Price.close.latest - Price.open.latest).shift(1),
        Price.close.latest.log().shift(1),
        Price.volume.latest.shift(1),
        (Price.close.latest + 1).shift(1),
        Price.close.latest.clip(lower=0.0).shift(1),
        (Price.close.latest**2).shift(1),
        (Price.close.latest / Price.open.latest * Price.high.latest).shift(1),
        (-Price.close.latest).shift(3).shift(1),
        Price.close.latest.log() - Price.close.latest.log().shift(1),  # the log return
        (Returns(2) * Price.close.latest).shift(1),  # degree 0 times a price level: 1
    ],
)
def test_terms_that_keep_the_row_basis_are_refused(term: Factor) -> None:
    with pytest.raises(nx.TermDomainError):
        check(term)


@pytest.mark.parametrize(
    "term",
    [
        Returns(2, inputs=[Price.close]),
        window_of(5, Price.close),
        Returns(2, inputs=[Price.close]).shift(5),
        (Price.close.latest / Price.open.latest).shift(1),
        Price.close_unadjusted.latest.shift(1),
        window_of(5, (Price.close.latest > Price.open.latest).as_factor()),
        (Price.close.latest > Price.open.latest).all(5).as_factor().shift(1),
        window_of(5, Price.close).shift(1),
        (Price.close.latest * Price.volume.latest).shift(1),  # both factors: no degree
        (Price.close.latest.log() - Price.open.latest.log()).shift(1),
        Price.close.latest.rank().shift(1).rank(),  # a cross-section of a price: no degree
        (Price.close.latest**0).shift(1),
        (Price.close.latest.sqrt().sqrt() ** 4 / Price.close.latest).shift(1),  # 1/4 * 4 - 1
        (Price.close.latest / Price.close.latest).shift(1),  # one node read twice
        (Returns(2) ** 2).shift(1),  # Returns: degree 0 over a column
        (Price.close.latest.log() * Price.close.latest).shift(1),  # a size not known
    ],
)
def test_terms_of_degree_zero_or_no_degree_pass(term: Factor) -> None:
    check(term)


def test_the_message_names_three_things_to_write_and_the_whole_term() -> None:
    with pytest.raises(nx.TermDomainError) as caught:
        check(Price.close.latest.shift(1))
    parts = caught.value.parts
    assert parts["what"] == (
        "Price.close.latest is a split-adjusted price level and cannot feed shift(1)"
    )
    assert parts["where"] == "term Price.close.latest.shift(1)"
    assert "Returns(2, inputs=[Price.close]) for a return" in parts["fix"]
    assert "@nx.factor(window=2, inputs=[Price.close])" in parts["fix"]
    assert "Price.close_unadjusted.latest.shift(1) for the value as it traded" in parts["fix"]
    with pytest.raises(nx.TermDomainError) as caught:
        check((Price.volume.latest * 2).shift(3))
    assert caught.value.parts["where"] == "term (Price.volume.latest * 2).shift(3)"
    assert "Price.volume_unadjusted.latest.shift(3)" in caught.value.parts["fix"]


def test_a_constant_raised_to_a_price_level_is_refused() -> None:
    with pytest.raises(nx.TermDomainError):
        check((2**Price.close.latest).shift(1))


def test_the_message_follows_the_degree_not_the_first_column() -> None:
    with pytest.raises(nx.TermDomainError) as caught:
        check((Price.close.latest / Price.open.latest * Price.volume.latest).shift(1))
    assert "split-adjusted share count" in caught.value.parts["what"]
    assert "inputs=[Price.volume]" in caught.value.parts["fix"]
    with pytest.raises(nx.TermDomainError) as caught:
        check(Price.shares_out.latest.shift(2))
    assert "unadjusted" not in caught.value.parts["fix"]  # no raw share count to name


@pytest.mark.parametrize(
    ("term", "refused"),
    [
        ((Price.close.latest / SMA(20)).shift(1), False),  # 1 - 1 = 0
        (SMA(20).shift(5), True),  # degree 1 over close
        (SMA(5, inputs=[SMA(20)]), True),  # a price level into a window of 5 rows
        (SMA(5, inputs=[Returns(2)]).shift(1), False),  # degree 1 over degree 0
    ],
    ids=["ratio to SMA", "SMA shifted", "SMA of SMA", "SMA of Returns shifted"],
)
def test_built_in_factor_degree_is_its_kernel_class(term: Factor, refused: bool) -> None:
    """#242, Decisions 2026-11-18 (#513's Decision on #499): a built-in factor's term has its
    kernel's class applied to its input (3.4), read from `pipeline.factors.ADJUSTMENT`."""
    if refused:
        with pytest.raises(nx.TermDomainError) as caught:
            check(term)
        assert caught.value.code == "E17"
    else:
        check(term)


@pytest.mark.parametrize(
    ("term", "degree"),
    [
        (AverageDollarVolume(20), ZERO),
        (AverageTradedValue(20), ZERO),
        (AnnualizedVolatility(20), ZERO),
        (RollingStd(20), (1, 0)),
        (SMA(20, inputs=[Price.volume]), (0, 1)),
        (Returns(2, inputs=[nx.factor(window=1, inputs=[Price.close])(_last)]), None),
    ],
    ids=["ADV", "ATV", "volatility", "RollingStd", "SMA of volume", "Returns of no degree"],
)
def test_each_built_in_class_gives_its_degree(term: Factor, degree: Any) -> None:
    """3.4: degree 1 gives the input's degree; degree 0 and invariant give 0 over a column or a
    degree-0 input, and no degree over an input with no degree."""
    ins = [degree_of(t, []) if not isinstance(t, Factor) else None for t in term.inputs]
    assert degree_of(term, ins) == degree


def test_a_deep_chain_is_refused_with_e17_not_a_recursion_error() -> None:
    term = Price.close.latest
    for _ in range(1000):
        term = term + 1.0
    with pytest.raises(nx.TermDomainError, match="…"):
        check(term.shift(1))
