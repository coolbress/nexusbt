"""3.4 "Degree of a term" and the refusal of 3.3 it is read by (E17, decision 2026-11-18, #513).

A degree counts the price factor `C` and the quantity factor `Q` of 5.3.3: `(1, 0)` is a price
level, `(0, 1)` a share count, `ZERO` neither. `SOME` is a degree that is not 0 but whose size
is not known (`log` of a price); None is no degree, which is never refused. The verdicts are
worked out on one walk and not kept on the terms, so building a term and its hash are as before.
"""

from __future__ import annotations

from collections.abc import Iterable
from fractions import Fraction
from typing import Literal

from nexusbt.contracts import TermDomainError

from ._terms import BoundColumn, Factor, Term, _user_line

type Degree = tuple[Fraction, Fraction] | Literal["some"] | None

ZERO: Degree = (Fraction(0), Fraction(0))
SOME: Degree = "some"
#: `.latest` of the `Price` columns the table of 3.2 adjusts to t, and of those it does not.
ADJUSTED: dict[str, Degree] = {
    **dict.fromkeys(("open", "high", "low", "close", "close_tr"), (Fraction(1), Fraction(0))),
    **dict.fromkeys(("volume", "shares_out"), (Fraction(0), Fraction(1))),
    **dict.fromkeys(("close_unadjusted", "volume_unadjusted", "value_traded", "market_cap"), ZERO),
}
_AS_INPUT = ("neg", "abs", "shift")
_CROSS = ("rank", "zscore", "demean", "winsorize", "pct_rank")
_ONE_TERM = ("log", "log1p", "exp", "clip", "to")  # a numeric function of one term and constants
_SIGN = {"mul": 1, "div": -1}


def check_degrees(roots: Iterable[Term]) -> None:
    """E17 for a term of known non-zero degree fed to `shift(k ≥ 1)` or, as a `Factor` input,
    to a window of two rows or more (3.3); a window over a column is not checked."""
    found: dict[str, Degree] = {}
    todo = list(roots)
    while todo:  # inputs before the term that reads them, as a loop: chains are deep
        term = todo[-1]
        children = [*term.inputs, *(v for _, v in term.params if isinstance(v, Term))]
        if waiting := [t for t in children if t._key not in found]:
            todo += waiting
            continue
        todo.pop()
        if term._key in found:
            continue
        ins = [found[t._key] for t in term.inputs]
        window = dict(term.params).get("window")
        for child, degree in zip(term.inputs, ins, strict=True):
            fed = term.op == "shift" or (isinstance(window, int) and window >= 2)
            if fed and isinstance(child, Factor) and degree not in (ZERO, None):
                raise _refused(term, child, degree)
        found[term._key] = degree_of(term, ins)


def degree_of(term: Term, ins: list[Degree]) -> Degree:
    """The 3.4 rules, given the degrees of the term's inputs."""
    op = term.op
    if not isinstance(term, Factor):
        return None  # a Filter or a Classifier is not refused; a column is read by its window
    if op == "constant":
        return ZERO
    if op == "latest":
        column = dict(term.inputs[0].params)
        return ADJUSTED.get(column["column"]) if column.get("dataset") == "Price" else None
    if op in _AS_INPUT:
        return ins[0]
    if op in _CROSS:
        return ZERO if ins[0] == ZERO else None
    if op in _ONE_TERM:
        return SOME if ins[0] not in (ZERO, None) else None
    if op in ("add", "sub", "fillna"):
        constants = [t.op == "constant" for t in term.inputs]
        if any(constants) and not all(constants):
            x = ins[constants.index(False)]
            if x not in (ZERO, None):
                return SOME
        return ins[0] if ins[0] == ins[1] and ins[0] != SOME else None
    if op in _SIGN:
        return _product(ins[0], ins[1], _SIGN[op])
    if op == "pow" and term.inputs[1].op == "constant":
        return _scaled(ins[0], Fraction(dict(term.inputs[1].params)["value"]))
    if op == "pow" and term.inputs[0].op == "constant":  # `c ** x`: a function of one term
        return SOME if ins[1] not in (ZERO, None) else None
    if op == "sqrt":
        return _scaled(ins[0], Fraction(1, 2))
    return None  # a built-in factor, a user function, `if_else`: no rule gives a degree yet


def _product(a: Degree, b: Degree, sign: int) -> Degree:
    if a is None or b is None:
        return None
    if b == ZERO:
        return a
    if a == ZERO:
        return _scaled(b, Fraction(sign))
    if not (isinstance(a, tuple) and isinstance(b, tuple)):
        return None  # two terms of non-zero degree, one of unknown size
    price, quantity = a[0] + sign * b[0], a[1] + sign * b[1]
    return None if price and quantity else (price, quantity)  # the two factors mixed


def _scaled(x: Degree, p: Fraction) -> Degree:
    if x is None:
        return None
    if p == 0:
        return ZERO
    return (x[0] * p, x[1] * p) if isinstance(x, tuple) else SOME


def _refused(term: Term, child: Factor, degree: Degree) -> TermDomainError:
    """The message names a return, the earlier value on today's basis and, where the column
    has a raw twin, the value as it traded, over an adjusted `Price` column of the input's
    factor (the first one read, depth first)."""
    factor = (0 if degree[0] else 1) if isinstance(degree, tuple) else None
    column = _column(child, factor) or ("volume" if factor == 1 else "close")
    noun = {ADJUSTED["close"]: "price level", ADJUSTED["volume"]: "share count"}.get(
        degree, "value"
    )
    params = dict(term.params)
    shift = term.op == "shift"
    rows = params["k"] + 1 if shift else params["window"]
    feeds = f"shift({rows - 1})" if shift else f"a window of {rows} rows"
    raw = f"{column}_unadjusted"
    as_traded = ""
    if raw in ADJUSTED:
        written = f"Price.{raw}.latest.shift({rows - 1})" if shift else f"inputs=[Price.{raw}]"
        as_traded = f"; {written} for the value as it traded that day"
    line = _user_line()
    return TermDomainError(
        what=f"{text(child)} is a split-adjusted {noun} and cannot feed {feeds}",
        where=f"term {text(term)}",
        why="each row's value is adjusted as of that row, so across a split the earlier row stands"
        f" on another share basis and the split looks like a real change in the {noun}",
        fix=f"Returns({rows}, inputs=[Price.{column}]) for a return;"
        f" @nx.factor(window={rows}, inputs=[Price.{column}]) to read the earlier value on"
        f" today's basis{as_traded}",
        more="spec 3.3 (shift, window inputs) and 3.4",
        layer=f"your code — {line}",
        at=line.split(" in ")[0],
        subject=text(child),
    )


def _column(term: Term, factor: int | None) -> str | None:
    """The first adjusted `Price` column the term reads in `factor` (0 price, 1 quantity,
    None either)."""
    todo = [term]
    while todo:
        node = todo.pop()
        params = dict(node.params)
        price = isinstance(node, BoundColumn) and params["dataset"] == "Price"
        found = ADJUSTED.get(params["column"]) if price else None
        if isinstance(found, tuple) and found != ZERO and (factor is None or found[factor]):
            return str(params["column"])
        todo += reversed(node.inputs)
    return None


_INFIX = {"add": "+", "sub": "-", "mul": "*", "div": "/", "pow": "**"}


def text(term: Term, depth: int = 0) -> str:
    """The term as the person wrote it, near enough for an error's `what` and `where`; past 40
    nested operators, `…` (a chain deeper than the call stack would not print at all)."""
    if depth > 40:
        return "…"
    params, ins = dict(term.params), [text(t, depth + 1) for t in term.inputs]
    if term.op == "column":
        return f"{params['dataset']}.{params['column']}"
    if term.op == "constant":
        return f"{params['value']:g}"
    if term.op == "latest":
        return f"{ins[0]}.latest"
    if term.op in _INFIX:
        return f"({ins[0]} {_INFIX[term.op]} {ins[1]})"
    if term.op == "neg":
        return f"-{ins[0]}"
    if term.op == "user":
        return f"{params['function']}(inputs=[{', '.join(ins)}])"
    if term.op[0].isupper():
        return f"{term.op}({params.get('window', '')}, inputs=[{', '.join(ins)}])"
    shown = [*ins[1:], *(f"{v}" for n, v in params.items() if not isinstance(v, Term | None))]
    return f"{ins[0]}.{term.op}({', '.join(shown)})" if ins else f"{term.op}()"
