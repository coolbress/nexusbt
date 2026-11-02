"""Market rules packs (spec 4.7): `resources/markets/<MARKET>.toml` and their seed tables, CSVs
copied by hand from public sources. `python -m nexusbt.config.packs --describe KR` sums one up."""

from __future__ import annotations

import argparse
import csv
import re
import tomllib
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from importlib.resources import files
from importlib.resources.abc import Traversable
from typing import Any

from nexusbt.contracts import RoundingModePolicy

Row = dict[str, str]
ISO_DATE = re.compile(r"\d{4}-\d\d-\d\d")
TICK_COLUMNS = ("valid_from", "valid_to", "venue_group", "price_from", "price_to", "tick")
# file → the columns 4.7 gives it; every seed row also carries `source` and `verified`.
SEEDS: dict[str, tuple[str, ...]] = {
    "ticks/kr_tick_table_v1.csv": TICK_COLUMNS,
    "ticks/us_tick_table_v1.csv": TICK_COLUMNS,
    "shorting/kr_short_bans_v1.csv": ("valid_from", "valid_to", "scope", "except_universe_ids"),
    "limits/kr_price_limits_v1.csv": ("valid_from", "valid_to", "market", "limit_ratio"),
    "costs/default_v1.csv": (
        *("country", "market", "side", "component", "bps", "min_amount"),
        *("valid_from", "valid_to"),
    ),
    "costs/venue_groups_v1.csv": ("country", "venue_mic", "market"),  # venue_mic → price group
}
_SCOPE = re.compile(r"(all)|(index):([^,=\s]+(?:,[^,=\s]+)*)|(classification):([^=\s]+)=([^=\s]+)")


def scope(text: str) -> tuple[str, tuple[str, ...]]:
    """A ban row's `scope`: `all`, `index:<id>[,<id>…]` or `classification:<scheme>=<code>`."""
    found = _SCOPE.fullmatch(text)
    if not found:
        raise ValueError(f"scope {text!r} is not all, index:<id>[,<id>…] or classification:<s>=<c>")
    if found[1]:
        return "all", ()
    if found[2]:
        return "index", tuple(found[3].split(","))
    return "classification", (found[5], found[6])


def in_effect(rows: list[Row], day: str) -> list[Row]:
    """The rows whose half-open `[valid_from, valid_to)` holds `day`; an empty bound is open."""
    return [
        r for r in rows if r["valid_from"] <= day and (not r["valid_to"] or day < r["valid_to"])
    ]


@dataclass(frozen=True, slots=True)
class RuleRow:
    """One rule row a run applied: its table, effective bounds, source and verification."""

    table: str
    valid_from: str
    valid_to: str
    source: str
    verified: bool


@dataclass(frozen=True, slots=True)
class RuleListing:
    """The release evidence of the rule verification gate (4.7, R3-15)."""

    rows: tuple[RuleRow, ...]

    @property
    def total(self) -> int:
        return len(self.rows)

    @property
    def unverified(self) -> int:
        return sum(not r.verified for r in self.rows)

    @property
    def ratio(self) -> str:
        return f"{self.unverified}/{self.total}"

    def __str__(self) -> str:
        lines = [
            f"{r.table} [{r.valid_from or '…'}, {r.valid_to or '…'}) "
            f"verified = {str(r.verified).lower()} {r.source}"
            for r in self.rows
        ]
        return "\n".join([*lines, f"verified = false: {self.ratio}"])


def verified(row: Row) -> bool:
    """A seed row's `verified` column; `seed()` has already refused anything but true/false."""
    return row["verified"] == "true"


def rule_listing(applied: Mapping[str, list[Row]]) -> RuleListing:
    """Source, bounds and `verified` of the rows applied, table by table."""
    return RuleListing(
        tuple(
            RuleRow(table, r.get("valid_from", ""), r.get("valid_to", ""), r["source"], verified(r))
            for table, rows in applied.items()
            for r in rows
        )
    )


def _check(name: str, line: int, row: Row) -> None:
    def bad(what: str) -> ValueError:
        return ValueError(f"resources/{name} line {line}: {what}")

    if row["verified"] not in ("true", "false"):
        raise bad(f"verified = {row['verified']!r}, not true or false")
    if not row["source"]:
        raise bad("no source")
    bounds = [row[k] for k in ("valid_from", "valid_to") if row.get(k)]
    if any(not ISO_DATE.fullmatch(d) for d in bounds) or bounds != sorted(set(bounds)):
        raise bad(f"[{row.get('valid_from')}, {row.get('valid_to')}) is not a half-open interval")
    if "scope" in row:
        scope(row["scope"])
        for item in filter(None, row["except_universe_ids"].split(",")):
            if ":" not in item:
                raise bad(f"except_universe_ids item {item!r} is not <kind>:<id>")


def seed(name: str, root: Traversable | None = None) -> list[Row]:
    """The rows of one seed table, each checked; a broken file raises ValueError.

    `root` is the folder the tables are read from, by default the engine's `resources`."""
    root = root or files("nexusbt.resources")
    text = root.joinpath(name).read_text(encoding="utf-8")
    reader = csv.DictReader(text.splitlines())
    if tuple(reader.fieldnames or ()) != (*SEEDS[name], "source", "verified"):
        raise ValueError(f"resources/{name}: columns {reader.fieldnames} differ from spec 4.7")
    rows = list(reader)
    for line, row in enumerate(rows, start=2):
        _check(name, line, row)
    return rows


# The packs shipped, by codepoint; `_generic` runs a market under allow_untested. Read from the
# folder, so no market name is written in code (T4.11) and a new pack is only a new file.
PACKS = tuple(
    sorted(
        p.name.removesuffix(".toml")
        for p in files("nexusbt.resources").joinpath("markets").iterdir()
        if p.name.endswith(".toml")
    )
)
Ok = Callable[[Any], bool]


def _num(lo: float, hi: float = 1e300, *, int_: bool = False) -> Ok:
    kinds = int if int_ else (int, float)
    return lambda v: isinstance(v, kinds) and not isinstance(v, bool) and lo <= v <= hi


def _is(kind: type) -> Ok:
    return lambda v: isinstance(v, kind)


def _table(v: Any) -> bool:
    return v in SEEDS


def _match(pattern: str) -> Ok:
    return lambda v: isinstance(v, str) and re.fullmatch(pattern, v) is not None


def _rounding(v: Any) -> bool:
    if not isinstance(v, dict) or set(v) != {"mode", "unit"}:
        return False
    # unit: a multiple of the minor unit (3.11 [rounding.<MARKET>], 5.6.1)
    return v["mode"] in set(RoundingModePolicy) and _num(1, int_=True)(v["unit"])


def _bps(v: Any) -> bool:
    return isinstance(v, dict) and set(v) == {"buy", "sell"} and all(map(_num(0), v.values()))


COMPONENTS = ("proceeds", "commission", "tax", "dividend_withholding", "cash_in_lieu", "borrow_fee")
# section → key → (required, check), the 4.7 pack; a section left out is absent from the pack.
PACK_SCHEMA: dict[str, dict[str, tuple[bool, Ok]]] = {
    "pack": {
        "market": (True, _is(str)), "version": (True, _num(1, int_=True)),
        "calendar_ids": (True, lambda v: isinstance(v, list) and all(map(_is(str), v))),
        "currency": (False, _match("[A-Z]{3}")),
        "minor_unit": (False, _num(0, int_=True)), "benchmark_hint": (False, _is(str)),
    },
    "price_limits": {"table": (True, _table), "open_tolerance": (True, _num(0, 0.05))},
    "costs": {"provisional_bps": (False, _bps), "min_half_spread_bps": (True, _num(0)),
              "table_market_groups": (False, _table)},
    "dividends": {"fallback_pay_lag_days": (True, _num(1, 400, int_=True))},
    "tradability": {"unknown_status_before": (True, _match(r"(\d{4}-\d\d-\d\d)?"))},
    "grid": {"tick_table": (False, _table), "base_unit": (False, _num(1e-12))},
    "rounding": dict.fromkeys(COMPONENTS, (True, _rounding)),
    "shorting": {
        "allowed": (True, _is(bool)), "ban_table": (False, _table),
        "uptick_rule_modeled": (True, _is(bool)),
        "borrow_availability": (True, lambda v: v == "assume_all"),
        "day_count": (True, _num(1, int_=True)),
    },
}  # fmt: skip
OPTIONAL_SECTIONS = {"price_limits", "tradability"}


def load_pack(market: str, root: Traversable | None = None) -> dict[str, Any]:
    """`resources/markets/<market>.toml`, checked against the 4.7 sections; else ValueError."""
    root = root or files("nexusbt.resources")
    pack = tomllib.loads(root.joinpath(f"markets/{market}.toml").read_text(encoding="utf-8"))
    where = f"resources/markets/{market}.toml"
    if missing := sorted(PACK_SCHEMA.keys() - OPTIONAL_SECTIONS - pack.keys()):
        raise ValueError(f"{where}: missing [{'], ['.join(missing)}]")
    for section, keys in pack.items():
        if section not in PACK_SCHEMA:
            raise ValueError(f"{where}: [{section}] is not a 4.7 section")
        schema = PACK_SCHEMA[section]
        if missing := sorted({k for k, (needed, _) in schema.items() if needed} - keys.keys()):
            raise ValueError(f"{where}: [{section}] {', '.join(missing)} missing")
        for key, value in keys.items():
            if key not in schema or not schema[key][1](value):
                raise ValueError(f"{where}: [{section}] {key} = {value!r} is not allowed")
    if pack["pack"]["market"] != market:
        raise ValueError(f"{where}: [pack] market = {pack['pack']['market']!r}, not {market!r}")
    return pack


def describe(market: str) -> str:
    """The pack version, `base_unit`, rounding, `day_count` and its seed tables' rows."""
    pack = load_pack(market)
    base_unit = pack["grid"].get("base_unit", "the currency's minor unit (F-15)")
    rounding = ", ".join(f"{k} {c['mode']} {c['unit']}" for k, c in pack["rounding"].items())
    tables = [  # in pack order, with the cost table nexusbt.toml's default `[costs] table` names
        pack.get("price_limits", {}).get("table"),
        "costs/default_v1.csv",
        pack["costs"].get("table_market_groups"),
        pack["grid"].get("tick_table"),
        pack["shorting"].get("ban_table"),
    ]
    lines = [f"rules {market}@{pack['pack']['version']}", f"base_unit = {base_unit}"]
    lines += [f"rounding: {rounding}", f"day_count = {pack['shorting']['day_count']}"]
    rows = {  # the cost tables hold every market's rows: keep this market's
        name: [r for r in seed(name) if r.get("country", market) == market]
        for name in tables
        if name
    }
    for name, table in rows.items():
        part = rule_listing({name: table})
        lines.append(f"{name}: {part.total} rows, verified = false {part.ratio}")
    lines.append(f"verified = false: {rule_listing(rows).ratio}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m nexusbt.config.packs")
    parser.add_argument("--describe", metavar="MARKET", choices=PACKS, required=True)
    print(describe(parser.parse_args(argv).describe))


if __name__ == "__main__":
    main()
