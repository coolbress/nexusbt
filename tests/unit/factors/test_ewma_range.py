"""Spec 3.4's `EWMA` row, 6.6 E16 (#666): `0 < decay_rate <= 1`, `span > 1`, `halflife > 0`,
`center_of_mass > 0`, each finite; any other value is refused when the term is built, with an
error naming the argument the person passed and its value. An argument inside its range that
gives a decay rate of 0.0 in float64 is refused the same way (decisions 2026-11-20, 7 and 8)."""

from __future__ import annotations

import math
from collections.abc import Callable

import pytest

from nexusbt.contracts import ConfigError
from nexusbt.factors import EWMA
from nexusbt.pipeline import Term

pytestmark = pytest.mark.unit

NAN, INF = math.nan, math.inf

REFUSED: list[tuple[str, float, Callable[[], Term]]] = [
    *(("decay_rate", d, lambda d=d: EWMA(2, d)) for d in (0.0, -1.0, 1.5, NAN, INF, -INF)),
    *(("span", s, lambda s=s: EWMA.from_span(2, s)) for s in (1.0, 0.0, INF, NAN)),
    *(("halflife", h, lambda h=h: EWMA.from_halflife(2, h)) for h in (0.0, -1.0, INF, 1e-300)),
    *(
        ("center_of_mass", c, lambda c=c: EWMA.from_center_of_mass(2, c))
        for c in (0.0, -0.5, INF, 1e-20)
    ),
    ("span", 1 + 2**-52, lambda: EWMA.from_span(2, 1 + 2**-52)),
    # An int beyond float64 is refused by name too, not with Python's bare OverflowError.
    ("decay_rate", 10**400, lambda: EWMA(2, 10**400)),
    ("span", 10**400, lambda: EWMA.from_span(2, 10**400)),
]


@pytest.mark.parametrize(
    ("name", "value", "build"), REFUSED, ids=[f"{n}={v!r:.24}" for n, v, _ in REFUSED]
)
def test_out_of_range_is_refused_at_build_naming_the_argument_passed(
    name: str, value: float, build: Callable[[], Term]
) -> None:
    with pytest.raises(ConfigError) as caught:
        build()
    error = caught.value
    assert error.code == "E16"
    assert f"{name}={value!r}" in error.parts["what"], error.parts["what"]
    assert error.layer.endswith(f"argument {name}={value!r}"), error.layer
    if name != "decay_rate":  # the person's argument, not the rate computed from it
        assert "decay_rate=" not in error.parts["what"], error.parts["what"]


@pytest.mark.parametrize(
    "build",
    [
        lambda: EWMA.from_span(2, 1 + 2**-52),
        lambda: EWMA.from_halflife(2, 1e-300),
        lambda: EWMA.from_center_of_mass(2, 1e-20),
    ],
)
def test_an_argument_rounding_to_a_zero_rate_says_why(build: Callable[[], Term]) -> None:
    with pytest.raises(ConfigError) as caught:
        build()
    assert "decay_rate 0.0" in caught.value.parts["why"], caught.value.parts["why"]


def rate(term: Term) -> float:
    found = dict(term.params)["decay_rate"]
    assert isinstance(found, float)
    return found


@pytest.mark.parametrize(
    ("build", "expected"),
    [
        (lambda: EWMA(2, 1.0), 1.0),  # equal weights (decision 4)
        (lambda: EWMA(2, 5e-324), 5e-324),
        (lambda: EWMA.from_span(2, 1e308), 1.0),
        (lambda: EWMA.from_halflife(2, 1e300), 1.0),
        (lambda: EWMA.from_center_of_mass(2, 1e308), 1.0),
    ],
)
def test_the_edges_are_accepted(build: Callable[[], Term], expected: float) -> None:
    assert rate(build()) == expected


@pytest.mark.parametrize(
    "build",
    [
        lambda: EWMA.from_span(2, 1 + 1e-9),
        lambda: EWMA.from_halflife(2, 1e-3),
        lambda: EWMA.from_center_of_mass(2, 1e-9),
    ],
)
def test_arguments_just_inside_their_ranges_are_accepted(build: Callable[[], Term]) -> None:
    assert 0.0 < rate(build()) < 1.0
