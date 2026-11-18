"""Spec 3.3 and 3.4 "Degree of a term" (#499): a term of known non-zero degree fed to `shift(k ≥ 1)`
or, as a `Factor` input, to a window of two rows or more is E17 when the graph is checked."""

from __future__ import annotations

from typing import Any

import pytest

import nexusbt as nx
from nexusbt.contracts import SchemaRegistry
from nexusbt.factors import Returns
from nexusbt.pipeline import Factor, Pipeline, Price, Term, bind, graph_hash

NO_SNAPSHOT_COLUMNS = SchemaRegistry(columns={}, labels={})


def _last(x: Any) -> Any:
    return x[-1]


def window_of(rows: int, *inputs: Any) -> Factor:
    return nx.factor(window=rows, inputs=list(inputs))(_last)


def check(term: Term) -> None:
    bind(term, NO_SNAPSHOT_COLUMNS)


def test_a_price_level_through_shift_is_E17() -> None:  # noqa: N802 - the code's name
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
def test_a_price_level_into_a_window_of_two_rows_is_E17(term: Factor) -> None:  # noqa: N802
    with pytest.raises(nx.TermDomainError, match="cannot feed a window of 2 rows"):
        check(term)


def test_a_window_of_one_row_takes_a_price_level() -> None:
    check(window_of(1, Price.close.latest))
    check(Returns(1, inputs=[Price.close.latest]))


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
