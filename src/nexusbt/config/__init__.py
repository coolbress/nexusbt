"""Reading and validating nexusbt.toml (secret keys forbidden)."""

from __future__ import annotations

import copy
import difflib
import os
import re
import tomllib
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Any, NoReturn

from nexusbt.contracts import (
    AccountTypePolicy,
    BandEntriesPolicy,
    BandModePolicy,
    BonusSharesTradablePolicy,
    CapabilityError,
    ConfigError,
    CostProfilePolicy,
    DecimalRatioPolicy,
    DelistingPolicy,
    EditionPolicy,
    EvaluateTargetPolicy,
    ExecutionAtPolicy,
    FallbacksPolicy,
    LabelEntryPolicy,
    LimitFillPolicy,
    MissingPayDatePolicy,
    NexusBTError,
    OrderTypePolicy,
    PinsPolicy,
    RightsPolicy,
    RoundingModePolicy,
    TaxesBasisPolicy,
    TaxesPayPolicy,
    TaxesProfilePolicy,
    TiebreakPolicy,
    UnknownInclusionPolicy,
    UnknownTradabilityPolicy,
    UnsupportedPolicy,
    VerifyPolicy,
)

Check = Callable[[Any, tuple[str, ...]], Any]
SECRET = re.compile("key|secret|token|password", re.IGNORECASE)


@dataclass(frozen=True)
class Each:  # a per-market default the same in every market ("0 in every market")
    value: float


class _Pack:
    def __repr__(self) -> str:
        return "<rules pack>"


PACK = _Pack()  # a default the market rules pack gives (T0.5b)


class _Hidden:
    def __repr__(self) -> str:
        return "<hidden>"


_HIDDEN = _Hidden()  # a secret key's value, never echoed in an error
_NONE: Any = object()  # no value to show (a key's value may itself be None)


class _RejectedError(Exception):
    """A check's refusal, `(what, fix, error class)`; the caller names the key."""


def _raise(
    what: str,
    where: str,
    fix: str,
    why: str,
    error: type[NexusBTError] = ConfigError,
    value: Any = _NONE,
    at: str = "",
) -> NoReturn:
    """E16 or E18 at `where`, layer config (6.6): `[table] key = value` names `at` (default
    `where`) and `value`; a value not given is not shown, a secret's as `<hidden>`."""
    layer = f"config — nexusbt.toml {at or where}" + f" = {value!r}" * (value is not _NONE)
    where = f"nexusbt.toml {where}"
    raise error(what=what, where=where, why=why, fix=fix, more="spec 3.11", layer=layer)


def _apply(where: str, check: Check, value: Any, m: tuple[str, ...]) -> Any:
    try:
        return check(value, m)
    except _RejectedError as rejected:
        what, fix, error = rejected.args
        why = "v1 accepts only this value" if error is CapabilityError else "spec 3.11 limits it"
        _raise(f"{where} = {value!r}: {what}", where, fix, why, error, value)


def rule(ok: Callable[[Any], object], what: str, fix: str, error: type = ConfigError) -> Check:
    def check(v: Any, _: tuple[str, ...]) -> Any:
        if not ok(v):
            raise _RejectedError(what, fix, error)
        return v

    return check


def num(lo: float = -1e300, hi: float = 1e300, *, gt: bool = False, int_: bool = False) -> Check:
    kind, low = (int if int_ else (int, float)), ("(" if gt else "[")

    def ok(v: Any) -> bool:
        if not isinstance(v, kind) or isinstance(v, bool):
            return False
        return (lo < v if gt else lo <= v) and v <= hi

    return rule(ok, f"not {'an integer' if int_ else 'a number'} in {low}{lo:g}, {hi:g}]", "fix it")


def one(*choices: Any) -> Check:
    return rule(
        lambda v: v in choices, "not allowed", f"use one of {', '.join(map(repr, choices))}"
    )


def choice(enum: type[StrEnum]) -> Check:  # a 2.4 policy enum's values; loads the member
    check = one(*(member.value for member in enum))
    return lambda v, m: enum(check(v, m))


def policy(default: StrEnum) -> tuple[Any, Check]:  # the 3.11 default: not always the first member
    return default, choice(type(default))


def fixed(value: str) -> tuple[Any, Check]:  # a reserved key: anything but `value` is E18
    return value, rule(
        lambda v: v == value, "reserved", f"leave it out or {value!r}", CapabilityError
    )


def match(pattern: str) -> Check:
    def ok(v: Any) -> bool:
        return isinstance(v, str) and re.fullmatch(pattern, v) is not None

    return rule(ok, f"does not match {pattern}", "write it in that form")


def is_(kind: type) -> Check:
    return rule(lambda v: isinstance(v, kind), f"not a {kind.__name__}", f"write a {kind.__name__}")


def _market(name: str, m: tuple[str, ...]) -> str:
    if m and name not in m:
        what = f"unknown market {name}; snapshot markets: {', '.join(m)}"
        raise _RejectedError(what, "use one of those", ConfigError)
    return name


def list_of(item: Check) -> Check:
    return lambda v, m: [item(x, m) for x in is_(list)(v, m)]


def named(item: Check, name: Check | None = None) -> Check:
    key = name or is_(str)
    return lambda v, m: {key(k, m): item(x, m) for k, x in is_(dict)(v, m).items()}


def per_market(item: Check, *, scalar: bool = False) -> Check:
    table = named(item, _market)
    return lambda v, m: item(v, m) if scalar and not isinstance(v, dict) else table(v, m)


def fields(**schema: Check) -> Check:
    return lambda v, m: {
        _known(k, schema, value=x): schema[k](x, m) for k, x in is_(dict)(v, m).items()
    }


def _clock(v: Any, m: tuple[str, ...]) -> Any:
    if isinstance(v, str) and v.startswith("utc:"):
        raise _RejectedError("utc:HH:MM is reserved (SC-25)", "use <MARKET>_close", CapabilityError)
    if v != "market_local":
        _market(match(r"\w+_close")(v, m).removesuffix("_close"), m)
    return v


def _net(v: Any, m: tuple[str, ...]) -> Any:
    lo_hi = list_of(num())(v, m)
    if len(lo_hi) != 2 or not lo_hi[0] <= 0 <= lo_hi[1]:
        what, fix = "not a closed interval [lo, hi] that contains 0", "e.g. [-1.0, 1.0]"
        raise _RejectedError(what, fix, ConfigError)
    return lo_hi


def _fx_series(v: Any, m: tuple[str, ...]) -> Any:
    # "<BASE><QUOTE>": 3.11 gives the form only; two currency codes is the rule chosen (#94)
    return named(STR, match("[A-Z]{6}"))(v, m) if isinstance(v, dict) else STR(v, m)


def _date(v: Any, m: tuple[str, ...]) -> Any:
    match(r"\d{4}-\d\d-\d\d|latest|start")(v, m)
    try:
        return v if v in ("latest", "start") else date.fromisoformat(v).isoformat()
    except ValueError:
        raise _RejectedError(
            "not a calendar date", "write a real YYYY-MM-DD", ConfigError
        ) from None


def whole(table: Check, *keys: str) -> Check:  # a table that writes every one of `keys`
    def check(v: Any, m: tuple[str, ...]) -> Any:
        if missing := [k for k in keys if k not in (got := table(v, m))]:
            what, fix = f"has no {', '.join(missing)}", f"write {{{', '.join(keys)}}}"
            raise _RejectedError(what, fix, ConfigError)
        return got

    return check


NAME = "[A-Za-z0-9_-]+"  # 3.11 [project] name; also the [meta] scheme (a rule chosen in #94)
STR, BOOL, CCY, DATE = is_(str), is_(bool), match("[A-Z]{3}"), _date
META = rule(  # "<scheme>@<level>": 3.11 gives the form; a level of digits is the rule chosen (#94)
    lambda v: isinstance(v, str) and re.fullmatch(rf"auto|{NAME}(@\d+)?", v) is not None,
    'not "auto" or a scheme', 'write "auto", <scheme> or <scheme>@<level>'
)  # fmt: skip
POS, COUNT, UNIT, ANY = num(1, int_=True), num(0, int_=True), num(0, 1, gt=True), num()
BPS, GE0, PER_META = num(0, 2000), num(0), per_market(META, scalar=True)
ROUNDING = named(fields(mode=choice(RoundingModePolicy), unit=num(0, gt=True)))
_GROUP = fields(markets=list_of(_market), gains_rate=num(0, 0.6), annual_exemption=COUNT,
                basis=choice(TaxesBasisPolicy))  # fmt: skip
_UNWRITTEN = {"gains_rate": 0.0, "annual_exemption": 0, "basis": TaxesBasisPolicy.AVERAGE}  # 3.11


def _group(v: Any, m: tuple[str, ...]) -> Any:
    return {**_UNWRITTEN, **_GROUP(v, m)}


SEGMENTS = named(list_of(DATE), match("[a-z0-9_]+"))
SPLIT = {"train": ["start", "2021-12-31"], "validation": ["2022-01-01", "latest"]}

# 3.11, table by table: key → (default, check). A "*" key is any market name.
# fmt: off
SCHEMA: dict[str, dict[str, tuple[Any, Check]]] = {
    "project": {"name": (None, match(NAME))},
    "data": {
        "root": (None, STR), "snapshot": ("latest", STR), "path": (None, STR),
        "edition": policy(EditionPolicy.STRICT), "verify": policy(VerifyPolicy.MANIFEST),
        "require_profiles": ([], list_of(STR)), "pins": policy(PinsPolicy.INDEX_ROOT),
        "fallbacks": policy(FallbacksPolicy.WARN), "history_mode": fixed("economic"),
        "share_count_kinds": (["listed", "outstanding"], list_of(STR)),
    },
    "defaults": {
        "universe": ("all", STR), "base_ccy": (None, CCY), "start": ("1995-01-01", DATE),
        "capital": (1_000_000_000, num(0, gt=True)), "end": ("latest", DATE),
        "clock": (None, _clock), "preset": ("realistic", one("realistic", "zipline")),
    },
    "split": {"segments": (SPLIT, SEGMENTS), "default_segment": ("train", STR),
              "embargo_sessions": (0, COUNT)},
    "validate": {"max_fits": (200, POS), "min_samples": (100, POS)}, "ml": {"threads": (1, POS)},
    "preview": {"years": (1, POS), "max_names": (200, POS)},
    "sleeves": {"weights": (None, per_market(GE0))}, "markets": {"allow_untested": (False, BOOL)},
    "universe": {
        "investable": (True, BOOL), "exclude_microcap": (False, BOOL),
        "exclude": ([], list_of(STR)), "microcap_pct": (0.20, num(0, 0.5, gt=True)),
        "eligibility_rule": ("investable-v1", STR),
    },
    "panels": {"feature": ("factor_pit_monthly", STR), "label": ("label_monthly", STR)},
    "portfolio": {"anchor_date": ("start", DATE), "tiebreak": policy(TiebreakPolicy.HASH),
                  "band_entries": policy(BandEntriesPolicy.SKIP),
                  "max_missing_decisions": (1, POS)},
    "shorting": {
        "enabled": (False, BOOL), "max_gross": (1.0, num(0, 3, gt=True)),
        "max_net": ([-1.0, 1.0], _net), "borrow_bps": (Each(0), per_market(num(0, 5000))),
        "collateral_ratio": (Each(0.5), per_market(num(0, 2))),
        "short_rebate_bps": (Each(0), per_market(BPS)),
    },
    "account": {
        "cash_rate_bps": (0, per_market(BPS, scalar=True)),
        "type": policy(AccountTypePolicy.CASH),
        "initial_margin": (PACK, per_market(UNIT)), "maintenance_margin": (PACK, per_market(UNIT)),
        "debit_rate_bps": (0, per_market(num(0, 5000), scalar=True)),
    },
    "execution": {
        "order": policy(OrderTypePolicy.MARKET), "at": policy(ExecutionAtPolicy.OPEN),
        "limit_offset_bps": (0.0, num(-500, 500)), "max_participation": (0.05, UNIT),
        "max_bar_participation": (0.10, UNIT), "min_trade_value": (0, per_market(GE0, scalar=True)),
        "min_trade_weight": (0.0, num(0, 0.1)), "rebalance_band": (None, UNIT),
        "band_mode": policy(BandModePolicy.EDGE), "adv_window": (20, num(5, int_=True)),
        "adv_min_obs": (10, POS), "max_order_age_sessions": (20, POS),
        "limit_fill": policy(LimitFillPolicy.THROUGH),
        "kr_limit_tolerance": (0.005, num(0, 0.05)),
        "unknown_tradability": policy(UnknownTradabilityPolicy.ASSUME_TRADABLE),
        "cost_reserve_bps": (0.0, num(0, 500)), "intraday_proceeds": fixed("next_phase"),
    },
    "costs": {
        "profile": policy(CostProfilePolicy.PROVISIONAL), "table": ("default", STR),
        "sensitivity": ([0, 1, 2], list_of(ANY)), "provisional_table": (None, STR),
        "provisional_bps": (PACK, per_market(whole(fields(buy=GE0, sell=GE0), "buy", "sell"))),
        "impact_y": (0.5, GE0),
        "impact_a2": (0.5, num(0, 2, gt=True)), "impact_a3": (1.0, num(0, 2, gt=True)),
        "min_half_spread_bps": (PACK, per_market(GE0)), "max_half_spread_bps": (200, GE0),
    },
    "dividends": {
        "missing_pay_date": policy(MissingPayDatePolicy.ESTIMATE),
        "estimate_window_years": (5, POS),
        "fallback_pay_lag_days": (PACK, per_market(num(1, 400, int_=True))),
        "estimate_min_obs": (20, POS), "withholding": (Each(0.0), per_market(num(0, 0.5))),
    },
    "corporate_actions": {
        "rights": policy(RightsPolicy.LAPSE), "unsupported": policy(UnsupportedPolicy.FAIL),
        "bonus_shares_tradable": policy(BonusSharesTradablePolicy.AT_PAY_DATE),
        "decimal_ratio": policy(DecimalRatioPolicy.EXCLUDE_INSTRUMENT),
    },
    "delisting": {
        "unknown_inclusion": policy(UnknownInclusionPolicy.CONSERVATIVE),
        "scenarios": (True, BOOL), "policy": policy(DelistingPolicy.OBSERVED_THEN_POLICY),
    },
    "settlement": {"model": fixed("immediate")},
    "taxes": {
        "profile": policy(TaxesProfilePolicy.NONE), "currency": (None, CCY),
        "pay": policy(TaxesPayPolicy.REPORT),
        "pay_month": (5, num(1, 12, int_=True)), "groups": ({}, named(_group)),
    },
    "fx": {"max_stale_days_decision": (10, COUNT), "max_stale_days_valuation": (10, COUNT),
           "series": ("auto", _fx_series)},
    "benchmarks": {"*": ("auto", STR)}, "fund": {"max_age_days": (550, COUNT)},
    "evaluate": {
        "freq": ("monthly", STR), "quantiles": (5, num(2, 20, int_=True)),
        "min_pairs": (20, num(3, int_=True)),
        "label_entry": policy(LabelEntryPolicy.NEXT_OPEN),
        "target": policy(EvaluateTargetPolicy.FWD_RETURN),
    },
    "meta": {"sector": ("auto", PER_META), "industry": ("auto", PER_META)},
    "gates": {"ic_t": (3.0, ANY), "dsr": (0.95, ANY)},
    "checks": {
        "auto_truncation_probe": (True, BOOL), "probes": (4, num(0, 64, int_=True)),
        "seed": (0, num(int_=True)), "start_probe": (False, BOOL),
        "start_probe_shift": (21, num(1, 252, int_=True)),
    },
    "runs": {"dir": ("runs", STR), "cache_max_gb": (20, GE0)},
    "compute": {"workers": (1, num(1, 8, int_=True)), "threads": (4, num(1, 16, int_=True)),
                "memory_budget_gb": (4.0, num(0.5)), "precision": fixed("float64")},
    "live": {
        "book_dir": ("runs/books", STR), "orders_dir": ("orders", STR),
        "max_price_jump": (PACK, per_market(num(0, 5, gt=True))),
        "spike_sigma": (8.0, num(0, gt=True)), "max_order_weight_mult": (2.0, num(1)),
        "liquidity_floor_pct": (0.10, num(0, 0.5)),
    },
    "rounding": {"*": (PACK, ROUNDING)},
    "report": {"rolling_windows_years": ([1, 3], list_of(num(1, 10, int_=True)))},
}
# fmt: on
DEFAULTS = {t: {k: d for k, (d, _) in kv.items() if k != "*"} for t, kv in SCHEMA.items()}
_MARGIN_ONLY = {"initial_margin", "maintenance_margin", "debit_rate_bps"}  # 3.11 [account] type


def _known(name: str, names: Mapping[str, Any], where: str = "", value: Any = _NONE) -> str:
    if name not in names:
        near = difflib.get_close_matches(name, list(names), n=3)
        fix = f"did you mean: {', '.join(near)}?" if near else "remove it"
        why = "unknown keys would be silently ignored"
        key = f"{where}{name}]" if where == "[" else f"{where}{name}"  # a table: `[name]`
        _raise(f"{key} is not a key", key, fix, why, value=value)
    return name


def _no_secrets(table: Mapping[str, Any], where: str = "") -> None:
    for name, value in table.items():
        if SECRET.search(name):
            what = f"{where}{name}: secrets do not belong in nexusbt.toml; "
            what += "use environment variables or the OS keychain"
            why = "the file is shared (spec 2.6)"
            _raise(what, f"{where}{name}", "remove the key", why, value=_HIDDEN)
        if isinstance(value, dict):
            _no_secrets(value, f"{where}{name}." if where else f"[{name}] ")


def _merge(values: dict[str, dict[str, Any]], given: Mapping[str, Any], m: tuple[str, ...]) -> None:
    for table, keys in given.items():
        schema = SCHEMA[_known(table, SCHEMA, "[")]
        for key, value in _apply(f"[{table}]", is_(dict), keys, m).items():
            where = f"[{table}] {key}"
            if "*" in schema:
                _apply(where, _market, key, m)
            name = "*" if "*" in schema else _known(key, schema, f"[{table}] ", value)
            values[table][key] = _apply(where, schema[name][1], _iso(value), m)


@dataclass(frozen=True, slots=True)
class Config:
    """The nexusbt.toml in effect: `values[table][key]` for every key of 3.11."""

    values: Mapping[str, Mapping[str, Any]]
    markets: tuple[str, ...] = ()
    resolved: Mapping[str, Any] = field(default_factory=dict)  # clock, base_ccy, sleeves (5.1.3)

    def __str__(self) -> str:
        return "\n".join(
            f"[{t}] {k} = {_plain(v)!r}" for t, kv in self.values.items() for k, v in kv.items()
        )


def _plain(value: Any) -> Any:
    """A policy member as its 3.11 string, inside lists and tables too, for printing."""
    if isinstance(value, dict):
        return {k: _plain(x) for k, x in value.items()}
    if isinstance(value, list):
        return [_plain(x) for x in value]
    return str(value) if isinstance(value, StrEnum) else value


def _data_root(root: str | None, package: str | None) -> str | None:
    root = root or os.environ.get("NEXUSBT_DATA_ROOT")
    path = Path(root or ".")
    if (
        root
        and not package
        and not (  # `[data] path` comes before `root` (3.11)
            path.is_dir()
            and (
                (path / "LATEST").is_file()
                or any((p / "tds.json").is_file() for p in path.iterdir())
            )
        )
    ):
        what = f"[data] root = {root!r} has no snapshot folder with LATEST or tds.json"
        why = "snapshots are read there (4.2)"
        _raise(what, "[data] root", "point it at a data root", why, value=root)
    return root


def _sleeves(values: dict[str, dict[str, Any]], m: tuple[str, ...]) -> dict[str, float] | None:
    universe = values["defaults"]["universe"]
    members = m if universe == "all" else universe.split("+")
    members = tuple(_apply("[defaults] universe", _market, x, m) for x in members)
    weights = values["sleeves"]["weights"]
    if weights is None:
        return dict.fromkeys(members, 1 / len(members)) if members else None
    kept = {k: w for k, w in weights.items() if not m or k in members}
    total = sum(kept.values())
    if abs(sum(weights.values()) - 1) > 1e-9 or total <= 0:
        what = f"[sleeves] weights sum to {sum(weights.values()):g}, {total:g} in the universe"
        why = "each sleeve's share of the capital comes from them (11.4.1)"
        _raise(what, "[sleeves] weights", "make them sum to 1 ± 1e-9", why, value=weights)
    return {k: w / total for k, w in kept.items()}  # markets outside the universe: rescaled


_ENDS = {"start": "0000-01-01", "latest": "9999-12-31"}  # from the beginning, to the end


def _segments(values: dict[str, dict[str, Any]]) -> None:
    last = ""
    for name, bounds in values["split"]["segments"].items():
        first, end = (_ENDS.get(d, d) for d in bounds) if len(bounds) == 2 else ("", "")
        if not last < first <= end:
            what = f"[split] segments: {name} = {bounds} overlaps, is out of order or is not [s, e]"
            fix = "give each segment [start, end], in time order, without overlap"
            why = "a decision belongs to one segment (R-57)"
            _raise(what, "[split] segments", fix, why, value=values["split"]["segments"])
        last = end


def _ties(values: dict[str, dict[str, Any]]) -> None:
    """The 3.11 Validation cells that name another key."""
    d, split, costs, account = (values[t] for t in ("defaults", "split", "costs", "account"))
    start, end = (_ENDS.get(d[k], d[k]) for k in ("start", "end"))
    adv, obs = values["execution"]["adv_window"], values["execution"]["adv_min_obs"]
    im, mm = account["initial_margin"], account["maintenance_margin"]
    segment, spread = split["default_segment"], costs["max_half_spread_bps"]
    both = isinstance(im, dict) and isinstance(mm, dict)  # a pack's default: not compared here
    over = [k for k, v in mm.items() if k in im and v > im[k]] if both else []
    mins = costs["min_half_spread_bps"]
    low = max(mins.values(), default=0) if isinstance(mins, dict) else 0  # a pack's: unwritten
    names, groups = [*split["segments"], "all"], values["taxes"]["groups"]
    seen = [x for g in groups.values() for x in set(g.get("markets", []))]  # per group, once
    twice = sorted({x for x in seen if seen.count(x) > 1})
    for key, value, ok, what, fix in (
        ("[taxes] groups", groups, not twice, f"put {', '.join(twice)} in two groups",
         "a market belongs to one group only"),
        ("[defaults] end", d["end"], end >= start, f"is before [defaults] start = {d['start']!r}",
         "use a date on or after start"),
        ("[split] default_segment", segment, segment in names, "is not a name of [split] segments",
         f"use one of {', '.join(map(repr, names))}"),
        ("[costs] sensitivity", costs["sensitivity"], 1 in costs["sensitivity"],
         "does not contain 1", "add 1, the cost table as written"),
        ("[execution] adv_min_obs", obs, obs <= adv, f"is more than [execution] adv_window = {adv}",
         f"use 1..{adv}"),
        ("[account] maintenance_margin", mm, not over,
         f"is above initial_margin in {', '.join(over)}", "use (0, initial_margin] in each market"),
        ("[costs] max_half_spread_bps", spread, spread >= low,
         f"is below [costs] min_half_spread_bps = {mins!r}", f"use {low:g} or more"),
    ):  # fmt: skip
        if not ok:
            why = "spec 3.11 limits it"
            _raise(f"{key} = {value!r} {what}", key, fix, why, value=value)


def _iso(value: Any) -> Any:
    """TOML dates as the 3.11 "YYYY-MM-DD" strings, inside lists and tables too."""
    if isinstance(value, list | dict):
        items = value.items() if isinstance(value, dict) else enumerate(value)
        done = [(k, _iso(x)) for k, x in items]
        return dict(done) if isinstance(value, dict) else [x for _, x in done]
    return value.isoformat() if isinstance(value, date) else value


def _per_market(value: Any, market: str, default: Any = None) -> Any:
    return value.get(market, default) if isinstance(value, dict) else getattr(value, "value", value)


def check_long_short(config: Config, market: str, long_weight: float, short_weight: float) -> None:
    """3.7's feasible region of one sleeve's long-short book, before the run (called by T4.14)."""
    shorting, account = config.values["shorting"], config.values["account"]
    if short_weight > 0 and not shorting["enabled"]:
        why = "shorting is off by default (3.7)"
        what = "short targets need [shorting] enabled = true"
        _raise(what, "[shorting] enabled", "set it", why, value=shorting["enabled"])
    if account["type"] is AccountTypePolicy.CASH:
        unwritten = DEFAULTS["shorting"]["collateral_ratio"].value  # 0.5, "in every market"
        x = (
            long_weight
            + _per_market(shorting["collateral_ratio"], market, unwritten) * short_weight
        )
        if x > 1:
            times = chr(0xD7)  # the 3.7 sentence's multiplication sign
            what = (
                f"long-short book needs margin: long_weight + collateral_ratio {times} short_weight"
            )
            why = "longs are fully cash-funded; no margin loan; short proceeds are collateral"
            where, fix = f"[account] type, sleeve {market}", "lower the weights"
            _raise(f"{what} = {x:g} > 1", where, fix, why, value="cash", at="[account] type")
        return
    im = _per_market(account["initial_margin"], market)
    if not isinstance(im, int | float):
        what = f"[account] initial_margin has no value for {market}"
        where, fix = "[account] initial_margin", f"write {market} = <ratio>"
        _raise(what, where, fix, "5.6.7a needs it", value=account["initial_margin"])
    cap, x = min(shorting["max_gross"], 1 / im), long_weight + short_weight
    if x > cap:
        what = f"margin book exceeds buying power: L + S = {x:g} > {cap:g}"
        where, fix = f"[account] type, sleeve {market}", "lower the weights"
        _raise(what, where, fix, "5.6.7a", value="margin", at="[account] type")


def load_config(
    path: Path | None = None,
    overrides: Mapping[str, Any] | None = None,
    *,
    markets: Sequence[str] | Mapping[str, str] | None = None,
) -> Config:
    """Defaults ← the file ← `overrides` (table → key → value); `markets`: names or name → ccy."""
    m = tuple(sorted(markets or (), key=lambda x: x.encode()))
    given = tomllib.loads(path.read_text(encoding="utf-8")) if path else {}  # missing: an error
    _no_secrets(given)
    values = copy.deepcopy(DEFAULTS)  # each Config owns its lists and tables
    code = {t: dict(v) for t, v in (overrides or {}).items()}
    _merge(values, given, m)  # checks the file's shape first
    if values["defaults"]["preset"] == "zipline":
        why = "zipline is for tests only (R-55)"
        what, fix = "[defaults] preset = 'zipline'", "pass it in test code"
        _raise(what, "[defaults] preset", fix, why, value="zipline")
    _merge(values, code, m)
    written = {k for src in (given, code) for k in src.get("account", {})} & _MARGIN_ONLY
    if written and values["account"]["type"] is AccountTypePolicy.CASH:
        what = f'margin settings need [account] type = "margin": {", ".join(sorted(written))}'
        fix, why = 'set type = "margin" or remove them', "3.11 [account] type"
        _raise(what, "[account]", fix, why, value="cash", at="[account] type")
    _segments(values)
    _ties(values)
    d = values["defaults"]
    if d["clock"] is None and m:
        d["clock"] = f"{m[0]}_close"  # the first market by UTF-8 bytes (5.1.3, R3-18)
    if d["base_ccy"] is None and isinstance(markets, Mapping) and m:
        d["base_ccy"] = _apply("[defaults] base_ccy", CCY, markets[m[0]], m)
    values["taxes"]["currency"] = values["taxes"]["currency"] or d["base_ccy"]
    for kv in values.values():  # "the same in every market", once the markets are known
        kv.update(
            {k: dict.fromkeys(m, v.value) for k, v in kv.items() if m and isinstance(v, Each)}
        )
    values["data"]["root"] = _data_root(values["data"]["root"], values["data"]["path"])
    folder = (path.resolve().parent if path else Path.cwd()).name
    if not values["project"]["name"] and not re.fullmatch(NAME, folder):  # the default, checked
        what = f"[project] name defaults to the folder name {folder!r}, outside {NAME}"
        fix = "set [project] name in nexusbt.toml"
        _raise(what, "[project] name", fix, "spec 3.11 limits it", value=folder)
    values["project"]["name"] = values["project"]["name"] or folder
    resolved = {"clock": d["clock"], "base_ccy": d["base_ccy"], "sleeves": _sleeves(values, m)}
    return Config(values, m, resolved)
