"""`PROFILES`: the TDS chapter 7 table, the datasets each profile requires (`tds:<name>@<M.m>`).

A requirement is a tuple of alternatives, each one or more datasets that must all be present
(`instruments + bars`). A dataset is met by one whose `kind` (for the 4.4 dictionaries, whose
`path`) matches and whose `params` meet each condition: `=value`, declared at all (`""`), or
`<1d`, a `freq` under one day. The manifest level sees only kinds, paths and params: required
columns and row conditions (`instruments(fx_spot)`) are left to the schema and full levels, and
so are the "if continuous contracts" and "if perps" conditions.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

#: (kind or path, (param, condition) pairs): `bars(freq=1d)` is ("bars", (("freq", "=1d"),)).
Need = tuple[str, tuple[tuple[str, str], ...]]
Needs = tuple[tuple[tuple[Need, ...], ...], ...]


@dataclass(frozen=True, slots=True)
class Profile:
    name: str
    status: str  # "stable", or "experimental" where chapter 7 marks it
    requires: Needs
    #: Required only when the package declares more than one market (`fx_rates`).
    requires_multi_market: Needs = ()


_CONDITION = re.compile(r"([a-z_]+)([=<].*)?")


def _needs(*groups: str) -> Needs:
    """`"bars:freq=1d,price_basis"`; datasets together joined by `+`, alternatives by `|`."""
    out = []
    for group in groups:
        alts = []
        for alt in group.split("|"):
            together = []
            for need in alt.split("+"):
                kind, _, params = need.partition(":")
                conditions = []
                for p in params.split(",") if params else ():
                    if not (m := _CONDITION.fullmatch(p)):
                        raise ValueError(f"not a profile condition: {p!r}")  # a table typo
                    conditions.append((m[1], m[2] or ""))
                together.append((kind, tuple(conditions)))
            alts.append(tuple(together))
        out.append(tuple(alts))
    return tuple(out)


_DAY_SECONDS = 86_400
_SECONDS = {"h": 3600, "m": 60, "s": 1}
_FREQ = re.compile(r"(\d+)([hms])")


def meets(params: Mapping[str, Any], key: str, condition: str) -> bool:
    """Whether a dataset's `params` meet one condition of a `Need`."""
    if key not in params:
        return False
    value = params[key]
    if condition == "<1d":  # TDS 7 `bars(freq<1d)`; read as chosen in #80 Decisions
        match = _FREQ.fullmatch(value) if isinstance(value, str) else None
        return match is not None and 0 < int(match[1]) * _SECONDS[match[2]] < _DAY_SECONDS
    return condition == "" or value == condition.removeprefix("=")


def describe(alt: tuple[Need, ...]) -> str:
    """`bars(freq=1d, price_basis)`, datasets together joined by ` + `."""
    return " + ".join(
        f"{kind}({', '.join(k + c for k, c in conds)})" if conds else kind for kind, conds in alt
    )


_MINIMAL = ("instruments", "bars:freq=1d,price_basis")
_CORE = (
    "instruments",
    "bars:freq=1d,price_basis=raw,density=dense",
    "calendar_sessions",
    "corporate_actions",
    "delistings",
)
_RESEARCH = (
    *_CORE,
    "tradability_daily",
    "eligibility_daily",
    "instrument_symbols",
    "fundamentals_state",
    "classifications",
    "dictionary/columns",
    "dictionary/items",
)
_X = "experimental"

_TABLE = (
    Profile("tds:minimal-daily@1.0", "stable", _needs(*_MINIMAL)),
    Profile("tds:equity-daily-core@1.0", "stable", _needs(*_CORE)),
    Profile("tds:equity-daily-research@1.0", "stable", _needs(*_RESEARCH), _needs("fx_rates")),
    Profile(
        "tds:panels@1.0", "stable", _needs("feature_panels", "label_panels", "dictionary/columns")
    ),
    Profile(
        "tds:pit-fundamentals@1.0", "stable", _needs("fundamentals_events", "fundamentals_state")
    ),
    Profile("tds:bitemporal@1.0", "stable", ()),
    Profile(
        "tds:intraday-bars@1.0", _X, _needs("instruments", "calendar_sessions", "bars:freq<1d")
    ),
    Profile("tds:l1-ticks@1.0", _X, _needs("trades", "quotes")),
    Profile("tds:l2-book@1.0", _X, _needs("book_deltas:depth_kind=mbp|book_snapshots")),
    Profile("tds:l3-book@1.0", _X, _needs("book_deltas:depth_kind=mbo")),
    Profile("tds:futures@1.0", _X, _needs("instruments", "market_statistics")),
    Profile("tds:options@1.0", _X, _needs("instruments", "option_chain_snapshots|quotes", "rates")),
    Profile("tds:crypto@1.0", _X, _needs("instruments", "bars|trades")),
    Profile("tds:fx@1.0", "stable", _needs("fx_rates|instruments+bars")),
    Profile("tds:alt-events@1.0", "stable", _needs("events|series_observations")),
)

PROFILES: Mapping[str, Profile] = MappingProxyType({p.name: p for p in _TABLE})


def profile_id(declared: str) -> str:
    """Chapter 7 and 4.2: a name without `@` means `@1.0`."""
    return declared if "@" in declared else f"{declared}@1.0"
