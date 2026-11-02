"""Market rules packs (spec 4.7). So far their seed tables: CSVs copied by hand from public sources.

The packs themselves, `resources/markets/<MARKET>.toml`, and `--describe` follow (T0.5b)."""

from __future__ import annotations

import csv
import re
from collections.abc import Mapping
from dataclasses import dataclass
from importlib.resources import files
from importlib.resources.abc import Traversable

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
