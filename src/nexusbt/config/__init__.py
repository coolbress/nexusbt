"""Reading and validating nexusbt.toml (secret keys forbidden)."""

from __future__ import annotations

import copy
import difflib
import re
import tomllib
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, NoReturn

from nexusbt.contracts import CapabilityError, ConfigError, NexusBTError

Check = Callable[[Any, tuple[str, ...]], Any]
SECRET = re.compile("key|secret|token|password", re.IGNORECASE)


@dataclass(frozen=True)
class Each:  # a per-market default the same in every market ("0 in every market")
    value: float


class _Pack:
    def __repr__(self) -> str:
        return "<rules pack>"


PACK = _Pack()  # a default the market rules pack gives (T0.5b)


class _RejectedError(Exception):
    """A check's refusal, `(what, fix, error class)`; the caller names the key."""


def _raise(
    what: str, where: str, fix: str, why: str, error: type[NexusBTError] = ConfigError
) -> NoReturn:
    raise error(what=what, where=f"nexusbt.toml {where}", why=why, fix=fix, more="spec 3.11")


def _apply(where: str, check: Check, value: Any, m: tuple[str, ...]) -> Any:
    try:
        return check(value, m)
    except _RejectedError as rejected:
        what, fix, error = rejected.args
        why = "v1 accepts only this value" if error is CapabilityError else "spec 3.11 limits it"
        _raise(f"{where} = {value!r}: {what}", where, fix, why, error)


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


def pick(*choices: Any) -> tuple[Any, Check]:  # the default is the first choice
    return choices[0], one(*choices)


def fixed(value: str) -> tuple[Any, Check]:  # a reserved key: anything but `value` is E18
    return value, rule(
        lambda v: v == value, "reserved", f"leave it out or {value!r}", CapabilityError
    )


def match(pattern: str) -> Check:
    ok = lambda v: isinstance(v, str) and re.fullmatch(pattern, v)  # noqa: E731
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
    return lambda v, m: {_known(k, schema): schema[k](x, m) for k, x in is_(dict)(v, m).items()}


def _fx_series(v: Any, m: tuple[str, ...]) -> Any:
    return named(STR)(v, m) if isinstance(v, dict) else STR(v, m)


STR, BOOL = is_(str), is_(bool)
CCY, DATE = match("[A-Z]{3}"), match(r"\d{4}-\d\d-\d\d|latest|start")
POS, COUNT, UNIT, ANY = num(1, int_=True), num(0, int_=True), num(0, 1, gt=True), num()
BPS, GE0, PER_STR = num(0, 2000), num(0), per_market(STR, scalar=True)
ROUNDING = named(fields(mode=one("half_up", "half_even", "down"), unit=num(0, gt=True)))
GROUP = fields(markets=list_of(_market), gains_rate=num(0, 0.6), annual_exemption=COUNT,
               basis=one("average", "fifo"))  # fmt: skip
SEGMENTS = named(list_of(DATE), match("[a-z0-9_]+"))
SPLIT = {"train": ["start", "2021-12-31"], "validation": ["2022-01-01", "latest"]}

# 3.11, table by table: key → (default, check). A "*" key is any market name.
# fmt: off
SCHEMA: dict[str, dict[str, tuple[Any, Check]]] = {
    "project": {"name": (None, match("[A-Za-z0-9_-]+"))},
    "data": {
        "root": (None, STR), "snapshot": ("latest", STR), "path": (None, STR),
        "edition": pick("strict", "compare"), "verify": pick("manifest", "schema", "full"),
        "require_profiles": ([], list_of(STR)), "pins": pick("index+root", "index"),
        "fallbacks": pick("warn", "fail"), "history_mode": fixed("economic"),
        "share_count_kinds": (["listed", "outstanding"], list_of(STR)),
    },
    "defaults": {
        "universe": ("all", STR), "base_ccy": (None, CCY), "start": ("1995-01-01", DATE),
        "capital": (1_000_000_000, num(0, gt=True)), "end": ("latest", DATE),
        "clock": (None, STR), "preset": pick("realistic", "zipline"),
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
    "portfolio": {"anchor_date": ("start", DATE), "tiebreak": pick("hash", "id"),
                  "band_entries": pick("skip", "buy"), "max_missing_decisions": (1, POS)},
    "shorting": {
        "enabled": (False, BOOL), "max_gross": (1.0, num(0, 3, gt=True)),
        "max_net": ([-1.0, 1.0], list_of(ANY)), "borrow_bps": (Each(0), per_market(num(0, 5000))),
        "collateral_ratio": (Each(0.5), per_market(num(0, 2))),
        "short_rebate_bps": (Each(0), per_market(BPS)),
    },
    "account": {
        "cash_rate_bps": (0, per_market(BPS, scalar=True)), "type": pick("cash", "margin"),
        "initial_margin": (PACK, per_market(UNIT)), "maintenance_margin": (PACK, per_market(UNIT)),
        "debit_rate_bps": (0, per_market(num(0, 5000), scalar=True)),
    },
    "execution": {
        "order": pick("market", "limit"), "at": pick("open", "close"),
        "limit_offset_bps": (0.0, num(-500, 500)), "max_participation": (0.05, UNIT),
        "max_bar_participation": (0.10, UNIT), "min_trade_value": (0, per_market(GE0, scalar=True)),
        "min_trade_weight": (0.0, num(0, 0.1)), "rebalance_band": (None, UNIT),
        "band_mode": pick("edge", "target"), "adv_window": (20, num(5, int_=True)),
        "adv_min_obs": (10, POS), "max_order_age_sessions": (20, POS),
        "limit_fill": pick("through", "touch"), "kr_limit_tolerance": (0.005, num(0, 0.05)),
        "unknown_tradability": pick("assume_tradable", "block"),
        "cost_reserve_bps": (0.0, num(0, 500)), "intraday_proceeds": fixed("next_phase"),
    },
    "costs": {
        "profile": pick("provisional", "realistic", "none"), "table": ("default", STR),
        "sensitivity": ([0, 1, 2], list_of(ANY)), "provisional_table": (None, STR),
        "provisional_bps": (PACK, per_market(fields(buy=GE0, sell=GE0))), "impact_y": (0.5, GE0),
        "impact_a2": (0.5, num(0, 2, gt=True)), "impact_a3": (1.0, num(0, 2, gt=True)),
        "min_half_spread_bps": (PACK, per_market(GE0)), "max_half_spread_bps": (200, GE0),
    },
    "dividends": {
        "missing_pay_date": pick("estimate", "fail"), "estimate_window_years": (5, POS),
        "fallback_pay_lag_days": (PACK, per_market(num(1, 400, int_=True))),
        "estimate_min_obs": (20, POS), "withholding": (Each(0.0), per_market(num(0, 0.5))),
    },
    "corporate_actions": {
        "rights": pick("lapse", "fail"), "unsupported": pick("fail", "cash_at_adjustment"),
        "bonus_shares_tradable": pick("at_pay_date", "at_ex"),
        "decimal_ratio": pick("exclude_instrument", "require_exact", "literal"),
    },
    "delisting": {
        "unknown_inclusion": pick("conservative", "error"), "scenarios": (True, BOOL),
        "policy": pick("observed_then_policy", "observed_only", "lo", "hi"),
    },
    "settlement": {"model": fixed("immediate")},
    "taxes": {
        "profile": pick("none", "custom"), "currency": (None, CCY), "pay": pick("report", "cash"),
        "pay_month": (5, num(1, 12, int_=True)), "groups": ({}, named(GROUP)),
    },
    "fx": {"max_stale_days_decision": (10, COUNT), "max_stale_days_valuation": (10, COUNT),
           "series": ("auto", _fx_series)},
    "benchmarks": {"*": ("auto", STR)}, "fund": {"max_age_days": (550, COUNT)},
    "evaluate": {
        "freq": ("monthly", STR), "quantiles": (5, num(2, 20, int_=True)),
        "min_pairs": (20, num(3, int_=True)), "label_entry": pick("next_open", "close"),
        "target": pick("fwd_return", "fwd_return_adj"),
    },
    "meta": {"sector": ("auto", PER_STR), "industry": ("auto", PER_STR)},
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


def _known(name: str, names: Mapping[str, Any], where: str = "") -> str:
    if name not in names:
        near = difflib.get_close_matches(name, list(names), n=3)
        fix = f"did you mean: {', '.join(near)}?" if near else "remove it"
        why = "unknown keys would be silently ignored"
        _raise(f"{where}{name} is not a key", f"{where}{name}", fix, why)
    return name


def _no_secrets(table: Mapping[str, Any], where: str = "") -> None:
    for name, value in table.items():
        if SECRET.search(name):
            what = f"{where}{name}: secrets do not belong in nexusbt.toml; "
            what += "use environment variables or the OS keychain"
            _raise(what, f"{where}{name}", "remove the key", "the file is shared (spec 2.6)")
        if isinstance(value, dict):
            _no_secrets(value, f"{where}{name}." if where else f"[{name}] ")


def _merge(values: dict[str, dict[str, Any]], given: Mapping[str, Any], m: tuple[str, ...]) -> None:
    for table, keys in given.items():
        schema = SCHEMA[_known(table, SCHEMA, "[")]
        for key, value in _apply(f"[{table}]", is_(dict), keys, m).items():
            where = f"[{table}] {key}"
            if "*" in schema:
                _apply(where, _market, key, m)
            check = schema["*" if "*" in schema else _known(key, schema, f"[{table}] ")][1]
            value = value.isoformat() if isinstance(value, date) else value
            values[table][key] = _apply(where, check, value, m)


@dataclass(frozen=True, slots=True)
class Config:
    """The nexusbt.toml in effect: `values[table][key]` for every key of 3.11."""

    values: Mapping[str, Mapping[str, Any]]
    markets: tuple[str, ...] = ()

    def __str__(self) -> str:
        return "\n".join(
            f"[{t}] {k} = {v!r}" for t, kv in self.values.items() for k, v in kv.items()
        )


def load_config(
    path: Path | None = None,
    overrides: Mapping[str, Any] | None = None,
    *,
    markets: Sequence[str] | Mapping[str, str] | None = None,
) -> Config:
    """Defaults ← the file ← `overrides` (table → key → value); `markets`: names or name → ccy."""
    m = tuple(sorted(markets or (), key=lambda x: x.encode()))
    given = tomllib.loads(path.read_text(encoding="utf-8")) if path and path.is_file() else {}
    _no_secrets(given)
    values = copy.deepcopy(DEFAULTS)  # each Config owns its lists and tables
    _merge(values, given, m)
    _merge(values, {t: dict(v) for t, v in (overrides or {}).items()}, m)
    return Config(values, m)
