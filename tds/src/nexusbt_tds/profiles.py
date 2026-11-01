"""`PROFILES`: the TDS chapter 7 table, the datasets each profile requires (`tds:<name>@<M.m>`).

A requirement is a tuple of alternatives, met by any one dataset whose `kind` (for the 4.4
dictionaries, whose `path`) matches and whose `params` hold the listed values. The manifest
level sees only kinds, paths and params: required columns and row conditions are left to the
schema and full levels, and so are the "if continuous contracts" and "if perps" conditions.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

#: (kind or path, params it must carry): `bars(freq=1d)` is ("bars", (("freq", "1d"),)).
Need = tuple[str, tuple[tuple[str, str], ...]]
Needs = tuple[tuple[Need, ...], ...]


@dataclass(frozen=True, slots=True)
class Profile:
    name: str
    status: str  # "stable", or "experimental" where chapter 7 marks it
    requires: Needs
    #: Required only when the package declares more than one market (`fx_rates`).
    requires_multi_market: Needs = ()


def _needs(*groups: str) -> Needs:
    """`"bars:freq=1d"`; alternatives joined by `|`."""
    out: list[tuple[Need, ...]] = []
    for group in groups:
        alts: list[Need] = []
        for alt in group.split("|"):
            kind, _, params = alt.partition(":")
            pairs = tuple((k, v) for k, _, v in (p.partition("=") for p in params.split(",") if p))
            alts.append((kind, pairs))
        out.append(tuple(alts))
    return tuple(out)


_MINIMAL = ("instruments", "bars:freq=1d")
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
    Profile("tds:intraday-bars@1.0", _X, _needs("instruments", "calendar_sessions", "bars")),
    Profile("tds:l1-ticks@1.0", _X, _needs("trades", "quotes")),
    Profile("tds:l2-book@1.0", _X, _needs("book_deltas:depth_kind=mbp|book_snapshots")),
    Profile("tds:l3-book@1.0", _X, _needs("book_deltas:depth_kind=mbo")),
    Profile("tds:futures@1.0", _X, _needs("instruments", "market_statistics")),
    Profile("tds:options@1.0", _X, _needs("instruments", "option_chain_snapshots|quotes", "rates")),
    Profile("tds:crypto@1.0", _X, _needs("instruments", "bars|trades")),
    Profile("tds:fx@1.0", "stable", _needs("fx_rates|instruments")),
    Profile("tds:alt-events@1.0", "stable", _needs("events|series_observations")),
)

PROFILES: Mapping[str, Profile] = MappingProxyType({p.name: p for p in _TABLE})


def profile_id(declared: str) -> str:
    """Chapter 7 and 4.2: a name without `@` means `@1.0`."""
    return declared if "@" in declared else f"{declared}@1.0"
